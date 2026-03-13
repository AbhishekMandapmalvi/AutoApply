"""Resume assembler — score KB entries, select best, generate via LLM, render PDF.

Implements: TASK-030 M4, M9.

The assembler is the core pipeline that turns Knowledge Base entries into
a tailored resume PDF using LLM generation with strict KB-only constraints:

    1. Fetch all active KB entries
    2. Pre-filter entries by JD classification (M9)
    3. Score them against the job description (TF-IDF)
    4. Select top entries per category (experience, skills, education, etc.)
    5. Build structured context from selected entries
    6. Send to LLM with strict "only use provided data" instructions
    7. Render LLM markdown output to PDF via ReportLab

If the KB has insufficient entries (below configured thresholds), the
assembler returns None so the caller can fall through to standard LLM generation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from config.settings import ResumeReuseConfig
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
    llm_config=None,
) -> dict | None:
    """Assemble a tailored resume from KB entries scored against a JD.

    Scores KB entries, selects the best, sends them to the LLM with strict
    instructions to use ONLY the provided data, and renders the output to PDF.

    Args:
        jd_text: Job description text to score against.
        profile: Dict with keys: name, email, phone, location.
        kb: KnowledgeBase instance for fetching entries.
        reuse_config: Scoring and selection configuration.
        llm_config: LLMConfig with provider, api_key, model for generation.

    Returns:
        Dict with keys (pdf_bytes, resume_md, entry_ids, scoring_method)
        or None if KB has insufficient entries or LLM is unavailable.
    """
    cfg = reuse_config or ResumeReuseConfig()

    if not cfg.enabled:
        logger.debug("Resume reuse disabled in config")
        return None

    # Check LLM availability
    from core.ai_engine import check_ai_available

    if not check_ai_available(llm_config):
        logger.info("No LLM configured — cannot generate KB resume")
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

    # 4. Build structured context
    context = _build_context(profile, selected)

    # 5. Generate resume via LLM (strict KB-only)
    from core.ai_engine import generate_resume_from_kb

    try:
        resume_md = generate_resume_from_kb(context, jd_text, llm_config)
    except RuntimeError as e:
        logger.error("LLM generation failed: %s", e)
        return None

    if not resume_md or not resume_md.strip():
        logger.error("LLM returned empty resume")
        return None

    # 6. Render markdown to PDF via ReportLab
    import tempfile

    from core.resume_renderer import render_resume_to_pdf

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        render_resume_to_pdf(resume_md, tmp_path)
        pdf_bytes = tmp_path.read_bytes()
    except Exception as e:
        logger.error("PDF rendering failed: %s", e)
        return None
    finally:
        tmp_path.unlink(missing_ok=True)

    # Collect entry IDs used
    entry_ids: list[int] = []
    for entries in selected.values():
        entry_ids.extend(e["id"] for e in entries)

    scoring_method = scored[0].get("scoring_method", "tfidf") if scored else "tfidf"

    logger.info(
        "KB+LLM assembly success: %d entries, %d bytes PDF",
        len(entry_ids), len(pdf_bytes),
    )

    return {
        "pdf_bytes": pdf_bytes,
        "resume_md": resume_md,
        "entry_ids": entry_ids,
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
    # Send generous amounts — LLM will trim to fit exactly 1 page
    max_per_category = {
        "experience": 15,
        "skill": 20,
        "education": 4,
        "project": 6,
        "certification": 5,
        "summary": 1,
    }

    selected: dict[str, list[dict]] = {}
    for cat, entries in by_category.items():
        limit = max_per_category.get(cat, 5)
        selected[cat] = entries[:limit]

    return selected


def _format_date(date_str: str) -> str:
    """Format a date string like '2022-01-15' or '2022-01' to 'Jan 2022'."""
    if not date_str:
        return ""
    months = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    parts = date_str.split("-")
    if len(parts) >= 2:
        try:
            month_idx = int(parts[1]) - 1
            if 0 <= month_idx < 12:
                return f"{months[month_idx]} {parts[0]}"
        except ValueError:
            pass
    return parts[0]


def _format_date_range(start: str, end: str) -> str:
    """Format a start–end date range for display."""
    start_fmt = _format_date(start)
    end_fmt = _format_date(end) if end else "Present"
    if not end_fmt:
        end_fmt = "Present"
    if start_fmt and end_fmt:
        return f"{start_fmt} -- {end_fmt}"
    if start_fmt:
        return start_fmt
    return end_fmt


def _build_experience_groups(entries: list[dict]) -> list[dict]:
    """Group experience entries by company, then by role within each company.

    Returns:
        List of dicts: [{company, location, roles: [{title, dates, bullets}]}]
    """
    from collections import OrderedDict

    companies: OrderedDict[str, dict] = OrderedDict()
    for e in entries:
        company = e.get("role_company") or ""
        title = e.get("role_title") or ""
        location = e.get("role_location") or ""
        start = e.get("role_start_date") or ""
        end = e.get("role_end_date") or ""

        # Fallback: if no role data, derive from subsection
        if not company and not title:
            subsection = e.get("subsection") or ""
            if " — " in subsection:
                parts = subsection.split(" — ", 1)
                title, company = parts[0].strip(), parts[1].strip()
            elif subsection:
                company = subsection

        comp_key = company or "Other"
        if comp_key not in companies:
            companies[comp_key] = {
                "company": company,
                "location": location,
                "roles": OrderedDict(),
            }

        role_key = f"{title}|{start}|{end}"
        if role_key not in companies[comp_key]["roles"]:
            companies[comp_key]["roles"][role_key] = {
                "title": title,
                "dates": _format_date_range(start, end),
                "sort_key": start or "0000",
                "bullets": [],
            }
        companies[comp_key]["roles"][role_key]["bullets"].append(e.get("text", ""))

    result = []
    for comp_data in companies.values():
        roles_sorted = sorted(
            comp_data["roles"].values(),
            key=lambda r: r["sort_key"],
            reverse=True,
        )
        roles = [
            {"title": r["title"], "dates": r["dates"], "bullets": r["bullets"]}
            for r in roles_sorted
        ]
        result.append({
            "company": comp_data["company"],
            "location": comp_data["location"],
            "roles": roles,
        })
    return result


def _build_education_entries(entries: list[dict]) -> list[dict]:
    """Build structured education entries.

    Returns:
        List of dicts: [{institution, location, degree, dates}]
    """
    result = []
    for e in entries:
        institution = e.get("role_company") or e.get("subsection") or ""
        location = e.get("role_location") or ""
        degree = e.get("text") or ""
        start = e.get("role_start_date") or ""
        end = e.get("role_end_date") or ""
        dates = _format_date_range(start, end) if (start or end) else ""
        result.append({
            "institution": institution,
            "location": location,
            "degree": degree,
            "dates": dates,
        })
    return result


def _build_skill_groups(entries: list[dict]) -> list[dict]:
    """Group skill entries by subsection category.

    Returns:
        List of dicts: [{category, items}] where items is comma-joined string.
    """
    from collections import OrderedDict

    groups: OrderedDict[str, list[str]] = OrderedDict()
    for e in entries:
        category = e.get("subsection") or "Technical Skills"
        text = e.get("text") or ""
        if text:
            groups.setdefault(category, []).append(text)

    return [
        {"category": cat, "entries": ", ".join(items)}
        for cat, items in groups.items()
    ]


def _build_project_groups(entries: list[dict]) -> list[dict]:
    """Group project entries by project name (subsection).

    Returns:
        List of dicts: [{name, bullets}]
    """
    from collections import OrderedDict

    projects: OrderedDict[str, list[str]] = OrderedDict()
    for e in entries:
        name = e.get("subsection") or ""
        text = e.get("text") or ""
        if text:
            projects.setdefault(name, []).append(text)

    return [
        {"name": name, "bullets": bullets}
        for name, bullets in projects.items()
    ]


def _build_context(
    profile: dict,
    selected: dict[str, list[dict]],
) -> dict:
    """Build structured resume context from profile and selected KB entries.

    Returns:
        Dict used by generate_resume_from_kb() for LLM prompt building.
        Structure:
            - name, email, phone, location, linkedin_url: str
            - summary: str
            - experience: [{company, location, roles: [{title, dates, bullets}]}]
            - education: [{institution, location, degree, dates}]
            - skills: [{category, entries}]
            - projects: [{name, bullets}]
            - certifications: [{text}]
    """
    summary_entries = selected.get("summary", [])
    summary = summary_entries[0].get("text", "") if summary_entries else ""

    return {
        "name": profile.get("name", ""),
        "email": profile.get("email", ""),
        "phone": profile.get("phone", ""),
        "location": profile.get("location", ""),
        "linkedin_url": profile.get("linkedin_url", ""),
        "summary": summary,
        "experience": _build_experience_groups(selected.get("experience", [])),
        "education": _build_education_entries(selected.get("education", [])),
        "skills": _build_skill_groups(selected.get("skill", [])),
        "projects": _build_project_groups(selected.get("project", [])),
        "certifications": [
            {"text": e.get("text", "")}
            for e in selected.get("certification", [])
        ],
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
