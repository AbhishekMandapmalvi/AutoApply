"""Knowledge Base — CRUD, LLM extraction, and resume ingestion.

Implements: TASK-030 M1 — core KB class for the smart resume reuse pipeline.
Processes uploaded documents via cloud LLM, stores categorized entries in SQLite,
and provides query/management operations.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from core.document_parser import extract_text

if TYPE_CHECKING:
    from db.database import Database

logger = logging.getLogger(__name__)

# Valid KB entry categories
VALID_CATEGORIES = frozenset({
    "experience", "skill", "education", "project", "summary",
    "certification", "award", "volunteer", "contact",
})

EXTRACTION_PROMPT = """
You are an expert career consultant. Parse this document into structured resume components.

For EACH item you extract, output it as a JSON object with these fields:
- "category": one of "experience", "skill", "education", "project", "summary", "certification", "award", "volunteer"
- "text": the polished, professional bullet point or entry. Use strong action verbs, quantify with metrics where present. Keep concise (1-2 lines max).
- "subsection": the role/company/institution context (e.g., "Senior Engineer — Acme Corp (2020-2023)"). Null for skills/certs.
- "job_types": array of job categories this entry is relevant to. Choose from: ["backend", "frontend", "fullstack", "data_engineer", "data_scientist", "devops", "cloud", "ml_engineer", "mobile", "security", "management", "product", "qa", "embedded", "general"]

Rules:
- Extract EVERY distinct achievement, skill, education entry, project, and certification
- Make bullet points professional and ATS-optimized: "Verb + What + Metric + Context"
- Do NOT invent metrics or facts not present in the source
- DO improve grammar, tense consistency, and professional tone
- Group related skills (e.g., "Python, Flask, Django" as one skill entry for "backend")
- For experience bullets, preserve the original company/role as subsection context
- Create 2-3 summary sentences that capture the person's overall profile, tagged by job type

Output ONLY a JSON array of objects. No preamble, no explanation.

---
DOCUMENT CONTENT:
{document_text}
"""


class KnowledgeBase:
    """Manages the resume knowledge base: upload processing, CRUD, and queries."""

    def __init__(self, db: "Database") -> None:
        self.db = db

    def process_upload(
        self,
        file_path: Path,
        llm_config,
        upload_dir: Path | None = None,
    ) -> int:
        """Full pipeline: extract text -> LLM -> insert entries.

        Args:
            file_path: Path to the uploaded document.
            llm_config: LLMConfig with provider, api_key, model.
            upload_dir: Optional directory to copy file to for storage.

        Returns:
            Number of entries inserted.
        """
        # 1. Extract raw text
        raw_text = extract_text(file_path)
        if not raw_text.strip():
            logger.warning("Empty text extracted from %s", file_path.name)
            return 0

        # 2. Store upload record
        file_type = file_path.suffix.lstrip(".").lower()
        stored_path = str(file_path)
        if upload_dir:
            upload_dir.mkdir(parents=True, exist_ok=True)
            dest = upload_dir / file_path.name
            if not dest.exists():
                import shutil
                shutil.copy2(str(file_path), str(dest))
            stored_path = str(dest)

        llm_provider = getattr(llm_config, "provider", None) if llm_config else None
        llm_model = getattr(llm_config, "model", None) if llm_config else None

        doc_id = self.db.save_uploaded_document(
            filename=file_path.name,
            file_type=file_type,
            file_path=stored_path,
            raw_text=raw_text,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )

        # 3. Extract entries via LLM
        entries = self._extract_via_llm(raw_text, llm_config)

        # 4. Insert entries with dedup
        inserted = self._insert_entries(entries, doc_id)
        logger.info(
            "Processed upload %s: %d entries extracted, %d inserted (deduped)",
            file_path.name, len(entries), inserted,
        )
        return inserted

    def _extract_via_llm(self, text: str, llm_config) -> list[dict]:
        """Call cloud LLM to extract structured entries from raw text."""
        from core.ai_engine import invoke_llm

        # Truncate very long documents to avoid token limits
        truncated = text[:12000]
        prompt = EXTRACTION_PROMPT.format(document_text=truncated)

        response = invoke_llm(prompt, llm_config)

        # Parse JSON response — handle potential markdown fences
        cleaned = response.strip()
        if cleaned.startswith("```"):
            # Strip markdown code block
            lines = cleaned.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        try:
            entries = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM extraction response: %s", e)
            return []

        if not isinstance(entries, list):
            logger.error("LLM extraction response is not a JSON array")
            return []

        # Validate entries
        valid = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            category = entry.get("category", "").strip().lower()
            text = entry.get("text", "").strip()
            if category not in VALID_CATEGORIES or not text:
                continue
            valid.append({
                "category": category,
                "text": text,
                "subsection": entry.get("subsection"),
                "job_types": json.dumps(entry.get("job_types", ["general"])),
            })

        return valid

    def _insert_entries(self, entries: list[dict], doc_id: int) -> int:
        """Insert entries into KB with dedup. Returns count of new entries."""
        inserted = 0
        for entry in entries:
            result = self.db.save_kb_entry(
                category=entry["category"],
                text=entry["text"],
                subsection=entry.get("subsection"),
                job_types=entry.get("job_types"),
                tags=entry.get("tags"),
                source_doc_id=doc_id,
            )
            if result is not None:
                inserted += 1
        return inserted

    def ingest_entries(self, entries: list[dict], doc_id: int | None = None) -> int:
        """Insert pre-parsed entries (from resume_parser or manual add).

        Args:
            entries: List of dicts with category, text, subsection, job_types, tags.
            doc_id: Optional source document id.

        Returns:
            Number of entries inserted.
        """
        inserted = 0
        for entry in entries:
            category = entry.get("category", "").strip().lower()
            text = entry.get("text", "").strip()
            if category not in VALID_CATEGORIES or not text:
                continue
            result = self.db.save_kb_entry(
                category=category,
                text=text,
                subsection=entry.get("subsection"),
                job_types=entry.get("job_types"),
                tags=entry.get("tags"),
                source_doc_id=doc_id,
            )
            if result is not None:
                inserted += 1
        return inserted

    def ingest_generated_resume(self, resume_md_path: Path) -> int:
        """Parse an LLM-generated resume and ingest its entries into KB.

        Args:
            resume_md_path: Path to the markdown resume file.

        Returns:
            Number of entries inserted.
        """
        from core.resume_parser import parse_resume_md

        if not resume_md_path.exists():
            logger.warning("Resume file not found for ingestion: %s", resume_md_path)
            return 0

        md_text = resume_md_path.read_text(encoding="utf-8")
        entries = parse_resume_md(md_text)
        return self.ingest_entries(entries)

    def get_all_entries(
        self,
        category: str | None = None,
        active_only: bool = True,
        search: str | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict]:
        """Return KB entries with optional filtering."""
        return self.db.get_kb_entries(
            category=category,
            active_only=active_only,
            search=search,
            limit=limit,
            offset=offset,
        )

    def get_entry(self, entry_id: int) -> dict | None:
        """Return a single KB entry."""
        return self.db.get_kb_entry(entry_id)

    def get_entries_by_ids(self, entry_ids: list[int]) -> list[dict]:
        """Fetch specific entries by IDs."""
        return self.db.get_kb_entries_by_ids(entry_ids)

    def update_entry(
        self,
        entry_id: int,
        text: str | None = None,
        subsection: str | None = None,
        job_types: str | None = None,
        tags: str | None = None,
    ) -> bool:
        """Update an entry. Returns True if found and updated."""
        return self.db.update_kb_entry(
            entry_id=entry_id,
            text=text,
            subsection=subsection,
            job_types=job_types,
            tags=tags,
        )

    def soft_delete_entry(self, entry_id: int) -> bool:
        """Soft-delete an entry. Returns True if found."""
        return self.db.soft_delete_kb_entry(entry_id)

    def get_stats(self) -> dict:
        """Return KB statistics."""
        return self.db.get_kb_stats()
