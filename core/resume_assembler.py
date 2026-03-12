"""Resume assembler — score KB entries, select best, render LaTeX, compile PDF.

Implements: TASK-030 M4, M9.

The assembler is the core pipeline that turns Knowledge Base entries into
a tailored resume PDF without any LLM API calls:

    1. Fetch all active KB entries
    2. Pre-filter entries by JD classification (M9)
    3. Score them against the job description (TF-IDF)
    4. Select top entries per category (experience, skills, education, etc.)
    5. Build a LaTeX template context
    6. Render and compile to PDF

If the KB has insufficient entries (below configured thresholds), the
assembler returns None so the caller can fall through to LLM generation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from config.settings import LatexConfig, ResumeReuseConfig
from core.latex_compiler import compile_resume, find_pdflatex
from core.resume_scorer import score_kb_entries

if TYPE_CHECKING:
    from core.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

# Minimum entries per category to consider KB assembly viable
_DEFAULT_CATEGORY_MINIMUMS = {
    "experience": 3,
    "skill": 2,
    "education": 1,
}


def assemble_resume(
    jd_text: str,
    profile: dict,
    kb: KnowledgeBase,
    reuse_config: ResumeReuseConfig | None = None,
    latex_config: LatexConfig | None = None,
) -> dict | None:
    """Assemble a tailored resume from KB entries scored against a JD.

    Args:
        jd_text: Job description text to score against.
        profile: Dict with keys: name, email, phone, location.
        kb: KnowledgeBase instance for fetching entries.
        reuse_config: Scoring and selection configuration.
        latex_config: LaTeX template and compilation configuration.

    Returns:
        Dict with keys (pdf_bytes, entry_ids, template, scoring_method)
        or None if KB has insufficient entries for assembly.
    """
    cfg = reuse_config or ResumeReuseConfig()
    lcfg = latex_config or LatexConfig()

    if not cfg.enabled:
        logger.debug("Resume reuse disabled in config")
        return None

    # 1. Fetch all active KB entries
    all_entries = kb.get_all_entries(active_only=True, limit=2000)
    if not all_entries:
        logger.info("KB is empty — cannot assemble resume")
        return None

    # 1b. Pre-filter by JD classification (M9)
    from core.jd_classifier import classify_jd, filter_entries_by_type, get_relevant_types

    job_types = classify_jd(jd_text)
    relevant_types = get_relevant_types(job_types)
    filtered_entries = filter_entries_by_type(all_entries, relevant_types)
    logger.debug(
        "JD classified as %s; %d/%d entries after pre-filter",
        job_types, len(filtered_entries), len(all_entries),
    )

    # 2. Score entries against JD
    scored = score_kb_entries(jd_text, filtered_entries, cfg)
    if not scored:
        logger.info("No KB entries scored above threshold (%.2f)", cfg.min_score)
        return None

    # 3. Select top entries per category
    selected = _select_entries(scored, cfg)
    if selected is None:
        return None

    # 4. Build LaTeX template context
    context = _build_context(profile, selected)

    # 5. Check pdflatex availability
    pdflatex = find_pdflatex()
    if pdflatex is None:
        logger.warning("pdflatex not found — cannot compile LaTeX resume")
        return None

    # 6. Render and compile
    pdf_bytes = compile_resume(lcfg.template, context, pdflatex_path=pdflatex)
    if pdf_bytes is None:
        logger.error("LaTeX compilation failed for template '%s'", lcfg.template)
        return None

    # Collect entry IDs used
    entry_ids: list[int] = []
    for entries in selected.values():
        entry_ids.extend(e["id"] for e in entries)

    scoring_method = scored[0].get("scoring_method", "tfidf") if scored else "tfidf"

    logger.info(
        "KB assembly success: %d entries, template=%s, %d bytes PDF",
        len(entry_ids), lcfg.template, len(pdf_bytes),
    )

    return {
        "pdf_bytes": pdf_bytes,
        "entry_ids": entry_ids,
        "template": lcfg.template,
        "scoring_method": scoring_method,
    }


def _select_entries(
    scored: list[dict],
    cfg: ResumeReuseConfig,
) -> dict[str, list[dict]] | None:
    """Select top entries per category from scored results.

    Returns:
        Dict mapping category → list of selected entries,
        or None if minimums not met.
    """
    by_category: dict[str, list[dict]] = {}
    for entry in scored:
        cat = entry.get("category", "")
        by_category.setdefault(cat, []).append(entry)

    # Check minimums
    for cat, minimum in _DEFAULT_CATEGORY_MINIMUMS.items():
        count = len(by_category.get(cat, []))
        if count < minimum:
            logger.info(
                "Insufficient KB entries for '%s': have %d, need %d",
                cat, count, minimum,
            )
            return None

    # Also check total experience bullets against config
    exp_count = len(by_category.get("experience", []))
    if exp_count < cfg.min_experience_bullets:
        logger.info(
            "Insufficient experience bullets: have %d, need %d",
            exp_count, cfg.min_experience_bullets,
        )
        return None

    # Select top entries per category (already sorted by score)
    max_per_category = {
        "experience": 8,
        "skill": 6,
        "education": 3,
        "project": 4,
        "certification": 3,
        "summary": 1,
    }

    selected: dict[str, list[dict]] = {}
    for cat, entries in by_category.items():
        limit = max_per_category.get(cat, 5)
        selected[cat] = entries[:limit]

    return selected


def _build_context(
    profile: dict,
    selected: dict[str, list[dict]],
) -> dict:
    """Build the LaTeX template context from profile and selected KB entries.

    Returns:
        Dict compatible with compile_resume() context parameter.
    """
    def _format_entries(entries: list[dict]) -> list[dict]:
        """Format KB entries for template consumption."""
        return [
            {
                "text": e.get("text", ""),
                "subsection": e.get("subsection", ""),
            }
            for e in entries
        ]

    # Use summary entry text if available, else empty
    summary_entries = selected.get("summary", [])
    summary = summary_entries[0].get("text", "") if summary_entries else ""

    return {
        "name": profile.get("name", ""),
        "email": profile.get("email", ""),
        "phone": profile.get("phone", ""),
        "location": profile.get("location", ""),
        "summary": summary,
        "experience": _format_entries(selected.get("experience", [])),
        "education": _format_entries(selected.get("education", [])),
        "skills": _format_entries(selected.get("skill", [])),
        "projects": _format_entries(selected.get("project", [])),
        "certifications": _format_entries(selected.get("certification", [])),
    }


def save_assembled_resume(
    pdf_bytes: bytes,
    output_dir: Path,
    company: str,
    job_title: str,
) -> Path:
    """Save assembled PDF to the output directory.

    Args:
        pdf_bytes: Raw PDF content.
        output_dir: Directory to write the PDF file.
        company: Company name (used in filename).
        job_title: Job title (used in filename).

    Returns:
        Path to the saved PDF file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    safe_company = "".join(c if c.isalnum() or c in " -_" else "" for c in company)
    safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in job_title)
    filename = f"resume_{safe_company}_{safe_title}.pdf".replace(" ", "_")[:100]

    pdf_path = output_dir / filename
    pdf_path.write_bytes(pdf_bytes)
    logger.info("Saved assembled resume: %s", pdf_path)
    return pdf_path


def ingest_llm_resume(
    resume_md: str,
    kb: KnowledgeBase,
    source_doc_id: int | None = None,
) -> int:
    """Parse an LLM-generated markdown resume and ingest entries into KB.

    This is called after a standard LLM generation to grow the KB
    automatically. Each section of the markdown resume is parsed
    and inserted as a KB entry via kb.ingest_entries().

    Args:
        resume_md: Markdown content of the LLM-generated resume.
        kb: KnowledgeBase instance.
        source_doc_id: Optional document ID for traceability.

    Returns:
        Number of entries inserted.
    """
    from core.resume_parser import parse_resume_md

    sections = parse_resume_md(resume_md)
    if not sections:
        logger.debug("No sections parsed from LLM resume")
        return 0

    # Tag all entries as LLM-generated
    for section in sections:
        existing_tags = section.get("tags", "")
        if existing_tags:
            section["tags"] = existing_tags.rstrip("]") + ', "llm-generated"]'
        else:
            section["tags"] = json.dumps(["llm-generated"])

    count = kb.ingest_entries(sections, doc_id=source_doc_id)
    logger.info("Ingested %d entries from LLM resume into KB", count)
    return count
