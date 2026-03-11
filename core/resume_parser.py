"""Parse markdown resumes into structured Knowledge Base entries.

Implements: TASK-030 M1 — convert existing .md resumes (LLM-generated or manual)
into KB entries for the smart reuse pipeline.
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

# Section heading patterns in LLM-generated resumes
_SECTION_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_SUBSECTION_RE = re.compile(r"^###\s+(.+)$", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+)$", re.MULTILINE)

# Category mapping from section headings
_CATEGORY_MAP = {
    "summary": "summary",
    "professional summary": "summary",
    "objective": "summary",
    "experience": "experience",
    "work experience": "experience",
    "professional experience": "experience",
    "employment": "experience",
    "skills": "skill",
    "technical skills": "skill",
    "core competencies": "skill",
    "education": "education",
    "academic background": "education",
    "projects": "project",
    "key projects": "project",
    "certifications": "certification",
    "certificates": "certification",
    "awards": "award",
    "honors": "award",
    "volunteer": "volunteer",
    "volunteering": "volunteer",
}


def parse_resume_md(md_text: str) -> list[dict]:
    """Parse a markdown resume into structured KB entries.

    Args:
        md_text: Markdown text content of a resume.

    Returns:
        List of dicts with keys: category, text, subsection, job_types, tags.
    """
    entries: list[dict] = []
    if not md_text or not md_text.strip():
        return entries

    # Split into sections by ## headings
    sections = _split_sections(md_text)

    for heading, content in sections:
        category = _map_category(heading)
        if category is None:
            continue

        if category == "summary":
            _parse_summary(content, entries)
        elif category == "experience":
            _parse_experience(content, entries)
        elif category == "skill":
            _parse_skills(content, entries)
        elif category == "education":
            _parse_education(content, entries)
        elif category in ("project", "certification", "award", "volunteer"):
            _parse_generic(content, category, entries)

    return entries


def _split_sections(md_text: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, content) tuples by ## headings."""
    sections: list[tuple[str, str]] = []
    matches = list(_SECTION_RE.finditer(md_text))

    for i, match in enumerate(matches):
        heading = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        content = md_text[start:end].strip()
        sections.append((heading, content))

    return sections


def _map_category(heading: str) -> str | None:
    """Map a section heading to a KB category."""
    normalized = heading.lower().strip()
    # Try exact match first, then prefix match
    if normalized in _CATEGORY_MAP:
        return _CATEGORY_MAP[normalized]
    for key, cat in _CATEGORY_MAP.items():
        if normalized.startswith(key) or key.startswith(normalized):
            return cat
    return None


def _parse_summary(content: str, entries: list[dict]) -> None:
    """Extract summary sentences from content."""
    # Summary is usually 2-3 sentences as a paragraph
    text = content.strip()
    if not text:
        return
    # Remove any bullet markers
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
    text = " ".join(text.split())  # collapse whitespace
    if text:
        entries.append({
            "category": "summary",
            "text": text,
            "subsection": None,
            "job_types": json.dumps(["general"]),
            "tags": None,
        })


def _parse_experience(content: str, entries: list[dict]) -> None:
    """Extract experience bullets grouped by subsection (role/company)."""
    current_subsection = None
    lines = content.split("\n")

    for line in lines:
        subsection_match = _SUBSECTION_RE.match(line)
        if subsection_match:
            current_subsection = subsection_match.group(1).strip()
            continue

        bullet_match = _BULLET_RE.match(line)
        if bullet_match:
            text = bullet_match.group(1).strip()
            if text:
                entries.append({
                    "category": "experience",
                    "text": text,
                    "subsection": current_subsection,
                    "job_types": json.dumps(["general"]),
                    "tags": None,
                })


def _parse_skills(content: str, entries: list[dict]) -> None:
    """Extract skill groups from content."""
    # Skills may be comma-separated, bullet-pointed, or in categories
    text = content.strip()
    if not text:
        return

    # Remove bullet markers and join
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
    text = " ".join(text.split())
    if text:
        entries.append({
            "category": "skill",
            "text": text,
            "subsection": None,
            "job_types": json.dumps(["general"]),
            "tags": None,
        })


def _parse_education(content: str, entries: list[dict]) -> None:
    """Extract education entries."""
    lines = content.split("\n")
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Remove bullet markers
        line = re.sub(r"^\s*[-*]\s+", "", line).strip()
        if line:
            entries.append({
                "category": "education",
                "text": line,
                "subsection": None,
                "job_types": json.dumps(["general"]),
                "tags": None,
            })


def _parse_generic(content: str, category: str, entries: list[dict]) -> None:
    """Extract entries from a generic section (projects, certs, awards)."""
    current_subsection = None
    lines = content.split("\n")

    for line in lines:
        subsection_match = _SUBSECTION_RE.match(line)
        if subsection_match:
            current_subsection = subsection_match.group(1).strip()
            continue

        bullet_match = _BULLET_RE.match(line)
        if bullet_match:
            text = bullet_match.group(1).strip()
            if text:
                entries.append({
                    "category": category,
                    "text": text,
                    "subsection": current_subsection,
                    "job_types": json.dumps(["general"]),
                    "tags": None,
                })
        elif line.strip() and not line.startswith("#"):
            text = line.strip()
            text = re.sub(r"^\s*[-*]\s+", "", text).strip()
            if text:
                entries.append({
                    "category": category,
                    "text": text,
                    "subsection": current_subsection,
                    "job_types": json.dumps(["general"]),
                    "tags": None,
                })
