"""Cover Letter KB Assembler — generate cover letters from KB entries (0 API calls).

Implements: TASK-030 M9 — Assembles cover letters from KB entries using
template-based generation. No LLM calls required.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from config.settings import ResumeReuseConfig
from core.resume_scorer import score_kb_entries

if TYPE_CHECKING:
    from core.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)

# Section templates for cover letter assembly
_GREETING = "Dear Hiring Manager,"

_INTRO_TEMPLATE = (
    "I am writing to express my strong interest in the {job_title} position"
    "{company_clause}. With my background in {domains}, I am confident I can "
    "contribute meaningfully to your team."
)

_BODY_TEMPLATE = (
    "In my experience as {role}, {achievement}. "
    "This experience has given me strong skills in {skills_summary}."
)

_CLOSING = (
    "I am excited about the opportunity to bring my skills and experience "
    "to your organization. I would welcome the chance to discuss how my "
    "background aligns with your needs. Thank you for considering my application."
)

_SIGNOFF = "Sincerely,"


def assemble_cover_letter(
    jd_text: str,
    profile: dict,
    kb: KnowledgeBase,
    job_title: str = "",
    company: str = "",
    reuse_config: ResumeReuseConfig | None = None,
) -> str | None:
    """Assemble a cover letter from KB entries scored against a JD.

    Uses the top-scoring experience and skill entries to compose a
    template-based cover letter. No LLM API calls.

    Args:
        jd_text: Job description text to score against.
        profile: Dict with keys: name, email, phone.
        kb: KnowledgeBase instance.
        job_title: Target job title (for intro paragraph).
        company: Target company name (for intro paragraph).
        reuse_config: Scoring configuration.

    Returns:
        Cover letter text as string, or None if KB has insufficient entries.
    """
    cfg = reuse_config or ResumeReuseConfig()

    all_entries = kb.get_all_entries(active_only=True, limit=2000)
    if not all_entries:
        logger.info("KB is empty — cannot assemble cover letter")
        return None

    scored = score_kb_entries(jd_text, all_entries, cfg)
    if not scored:
        logger.info("No KB entries scored above threshold for cover letter")
        return None

    # Group by category
    by_cat: dict[str, list[dict]] = {}
    for entry in scored:
        cat = entry.get("category", "")
        by_cat.setdefault(cat, []).append(entry)

    experiences = by_cat.get("experience", [])
    skills = by_cat.get("skill", [])

    if len(experiences) < 2:
        logger.info("Insufficient experience entries for cover letter")
        return None

    # Build cover letter parts
    name = profile.get("name", "Applicant")
    company_clause = f" at {company}" if company else ""

    # Extract domains from top skill entries
    skill_texts = [s.get("text", "") for s in skills[:4]]
    domains = ", ".join(skill_texts[:3]) if skill_texts else "the relevant field"

    # Intro paragraph
    intro = _INTRO_TEMPLATE.format(
        job_title=job_title or "open",
        company_clause=company_clause,
        domains=domains,
    )

    # Body paragraphs from top experiences
    body_parts: list[str] = []
    for exp in experiences[:3]:
        role = exp.get("subsection", "a professional")
        achievement = exp.get("text", "")
        if achievement:
            skills_summary = ", ".join(s.get("text", "") for s in skills[:2]) or "the relevant areas"
            body_parts.append(
                _BODY_TEMPLATE.format(
                    role=role,
                    achievement=achievement.rstrip("."),
                    skills_summary=skills_summary,
                )
            )

    if not body_parts:
        return None

    # Assemble
    paragraphs = [
        _GREETING,
        "",
        intro,
        "",
    ]
    for part in body_parts:
        paragraphs.append(part)
        paragraphs.append("")
    paragraphs.extend([
        _CLOSING,
        "",
        _SIGNOFF,
        name,
    ])

    letter = "\n".join(paragraphs)

    logger.info(
        "Cover letter assembled from %d experience + %d skill entries",
        min(len(experiences), 3), min(len(skills), 4),
    )

    return letter
