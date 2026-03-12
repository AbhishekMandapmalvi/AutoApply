"""KB Migrator — auto-migrate existing .txt and .md files into Knowledge Base.

Implements: TASK-030 M10 — Migrates legacy experience files and LLM-generated
resumes into KB entries. Runs once on startup, tracks migration state to avoid
re-processing.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

# Marker file to track migration completion
_MIGRATION_MARKER = ".kb_migrated"


def needs_migration(data_dir: Path) -> bool:
    """Check if KB migration has already been performed."""
    return not (data_dir / _MIGRATION_MARKER).exists()


def mark_migrated(data_dir: Path) -> None:
    """Write marker file to indicate migration is complete."""
    marker = data_dir / _MIGRATION_MARKER
    marker.write_text("migrated", encoding="utf-8")
    logger.info("KB migration marker written: %s", marker)


def migrate_experience_files(
    experience_dir: Path,
    kb: KnowledgeBase,
) -> int:
    """Migrate .txt experience files into KB entries.

    Each .txt file is split into individual lines/bullets and ingested
    as KB entries. Files are categorized based on filename heuristics.

    Args:
        experience_dir: Path to ~/.autoapply/profile/experiences/
        kb: KnowledgeBase instance.

    Returns:
        Number of entries inserted.
    """
    if not experience_dir.exists():
        logger.debug("Experience directory not found: %s", experience_dir)
        return 0

    txt_files = sorted(experience_dir.glob("*.txt"))
    txt_files = [f for f in txt_files if f.name.lower() != "readme.txt"]

    if not txt_files:
        logger.debug("No .txt experience files found in %s", experience_dir)
        return 0

    total_inserted = 0
    for txt_file in txt_files:
        try:
            content = txt_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as e:
            logger.warning("Skipping unreadable file %s: %s", txt_file.name, e)
            continue

        entries = _parse_txt_to_entries(content, txt_file.name)
        if entries:
            count = kb.ingest_entries(entries)
            total_inserted += count
            logger.info(
                "Migrated %s: %d entries inserted", txt_file.name, count,
            )

    return total_inserted


def migrate_resume_files(
    resumes_dir: Path,
    kb: KnowledgeBase,
) -> int:
    """Migrate .md resume files into KB entries.

    Uses existing resume_parser to parse markdown resumes.

    Args:
        resumes_dir: Path to directory containing .md resumes.
        kb: KnowledgeBase instance.

    Returns:
        Number of entries inserted.
    """
    if not resumes_dir.exists():
        logger.debug("Resumes directory not found: %s", resumes_dir)
        return 0

    md_files = sorted(resumes_dir.glob("*.md"))
    if not md_files:
        logger.debug("No .md resume files found in %s", resumes_dir)
        return 0

    from core.resume_parser import parse_resume_md

    total_inserted = 0
    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as e:
            logger.warning("Skipping unreadable file %s: %s", md_file.name, e)
            continue

        entries = parse_resume_md(content)
        if entries:
            # Tag as migrated
            for entry in entries:
                existing_tags = entry.get("tags")
                if existing_tags:
                    try:
                        tag_list = json.loads(existing_tags)
                    except (json.JSONDecodeError, TypeError):
                        tag_list = [existing_tags]
                else:
                    tag_list = []
                tag_list.append("migrated")
                entry["tags"] = json.dumps(tag_list)

            count = kb.ingest_entries(entries)
            total_inserted += count
            logger.info(
                "Migrated %s: %d entries inserted", md_file.name, count,
            )

    return total_inserted


def run_migration(data_dir: Path, kb: KnowledgeBase) -> dict:
    """Run full KB migration if not already done.

    Args:
        data_dir: Path to ~/.autoapply/
        kb: KnowledgeBase instance.

    Returns:
        Dict with migration results: {migrated, txt_entries, md_entries, skipped_reason}.
    """
    if not needs_migration(data_dir):
        return {"migrated": False, "skipped_reason": "already_migrated"}

    experience_dir = data_dir / "profile" / "experiences"
    resumes_dir = data_dir / "resumes"

    txt_count = migrate_experience_files(experience_dir, kb)
    md_count = migrate_resume_files(resumes_dir, kb)

    total = txt_count + md_count
    if total > 0:
        mark_migrated(data_dir)
        logger.info(
            "KB migration complete: %d txt entries + %d md entries = %d total",
            txt_count, md_count, total,
        )
    else:
        # Still mark as migrated even if nothing found — don't re-scan
        mark_migrated(data_dir)
        logger.info("KB migration complete: no legacy files found")

    return {
        "migrated": True,
        "txt_entries": txt_count,
        "md_entries": md_count,
    }


def _parse_txt_to_entries(content: str, filename: str) -> list[dict]:
    """Parse raw .txt experience file content into KB entries.

    Heuristics:
    - Lines starting with - or * are individual bullet entries (experience)
    - Non-empty lines without bullets are treated as experience text
    - Filename is used as subsection hint

    Args:
        content: Raw text content.
        filename: Source filename for subsection context.

    Returns:
        List of entry dicts ready for ingest_entries().
    """
    entries: list[dict] = []
    subsection = filename.replace(".txt", "").replace("_", " ").title()

    for line in content.strip().splitlines():
        line = line.strip()
        if not line:
            continue

        # Strip bullet markers
        if line.startswith(("-", "*")):
            text = line.lstrip("-* ").strip()
        else:
            text = line

        if len(text) < 5:
            continue

        # Categorize based on content heuristics
        category = _guess_category(text)

        entries.append({
            "category": category,
            "text": text,
            "subsection": subsection if category == "experience" else None,
            "job_types": json.dumps(["general"]),
            "tags": json.dumps(["migrated"]),
        })

    return entries


def _guess_category(text: str) -> str:
    """Guess KB category from text content using keyword heuristics."""
    text_lower = text.lower()

    skill_indicators = {
        "proficient", "skilled", "expertise", "technologies", "languages",
        "frameworks", "tools", "python", "java", "javascript", "sql",
    }
    edu_indicators = {
        "bachelor", "master", "phd", "degree", "university", "college",
        "graduated", "gpa", "diploma",
    }
    cert_indicators = {
        "certified", "certification", "certificate", "license", "aws certified",
    }

    if any(kw in text_lower for kw in cert_indicators):
        return "certification"
    if any(kw in text_lower for kw in edu_indicators):
        return "education"
    if any(kw in text_lower for kw in skill_indicators):
        return "skill"

    return "experience"
