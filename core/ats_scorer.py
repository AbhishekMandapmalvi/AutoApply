"""ATS Scorer — composite ATS compatibility score with gap analysis.

Implements: TASK-030 M6 — Evaluates resume content against a job description
across 5 dimensions: keyword density, section completeness, skill match,
content length, and format compliance.
"""

from __future__ import annotations

import logging
import re

from core.jd_analyzer import analyze_jd, normalize_term

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Score component weights (sum to 1.0)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: dict[str, float] = {
    "keyword_match": 0.35,
    "section_completeness": 0.20,
    "skill_match": 0.20,
    "content_length": 0.15,
    "format_compliance": 0.10,
}

# Required resume sections for ATS
_REQUIRED_SECTIONS = {"experience", "skill", "education"}
_OPTIONAL_SECTIONS = {"summary", "project", "certification"}

# Token regex
_TOKEN_RE = re.compile(r"[a-z][a-z0-9+#./-]*", re.IGNORECASE)

# Stopwords
_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "shall", "should", "may", "might", "can", "could", "not", "no", "nor",
    "so", "if", "then", "than", "that", "this", "these", "those", "it",
    "its", "we", "our", "you", "your", "they", "their", "he", "she",
    "him", "her", "who", "whom", "which", "what", "when", "where", "how",
    "all", "each", "every", "both", "few", "more", "most", "other", "some",
    "such", "only", "own", "same", "also", "as", "about", "up", "out",
    "into", "over", "after", "before", "between", "through", "during",
    "above", "below", "very", "just", "because", "while", "until",
    "able", "across", "along", "already", "among", "any", "around",
    "etc", "via", "per", "including", "within", "without",
})


def _tokenize(text: str) -> list[str]:
    """Tokenize text into normalized terms."""
    tokens = _TOKEN_RE.findall(text.lower())
    return [normalize_term(t) for t in tokens if normalize_term(t) not in _STOPWORDS and len(t) > 1]


# ---------------------------------------------------------------------------
# Component scorers (each returns 0.0 to 1.0)
# ---------------------------------------------------------------------------


def _score_keyword_match(
    jd_keywords: list[str],
    resume_terms: set[str],
) -> tuple[float, list[str], list[str]]:
    """Score keyword overlap between JD and resume.

    Returns:
        (score, matched_keywords, missing_keywords)
    """
    if not jd_keywords:
        return 1.0, [], []

    jd_unique = list(dict.fromkeys(jd_keywords))
    matched = [kw for kw in jd_unique if kw in resume_terms]
    missing = [kw for kw in jd_unique if kw not in resume_terms]

    score = len(matched) / len(jd_unique) if jd_unique else 0.0
    return min(score, 1.0), matched, missing


def _score_section_completeness(
    categories_present: set[str],
) -> float:
    """Score based on presence of required and optional resume sections."""
    required_count = len(_REQUIRED_SECTIONS & categories_present)
    optional_count = len(_OPTIONAL_SECTIONS & categories_present)

    # Required sections: 70% weight, optional: 30% weight
    req_score = required_count / len(_REQUIRED_SECTIONS) if _REQUIRED_SECTIONS else 1.0
    opt_score = optional_count / len(_OPTIONAL_SECTIONS) if _OPTIONAL_SECTIONS else 0.0

    return min(0.7 * req_score + 0.3 * opt_score, 1.0)


def _score_skill_match(
    jd_tech: list[str],
    resume_terms: set[str],
) -> tuple[float, list[str], list[str]]:
    """Score technical skill alignment.

    Returns:
        (score, matched_skills, missing_skills)
    """
    if not jd_tech:
        return 1.0, [], []

    matched = [t for t in jd_tech if t in resume_terms]
    missing = [t for t in jd_tech if t not in resume_terms]

    score = len(matched) / len(jd_tech) if jd_tech else 0.0
    return min(score, 1.0), matched, missing


def _score_content_length(
    entries: list[dict],
) -> float:
    """Score based on total content volume (word count across entries).

    Ideal range: 300-800 words for a 1-2 page resume.
    """
    total_words = sum(len(e.get("text", "").split()) for e in entries)

    if total_words < 100:
        return 0.3
    if total_words < 200:
        return 0.6
    if total_words < 300:
        return 0.8
    if total_words <= 800:
        return 1.0
    if total_words <= 1200:
        return 0.8
    return 0.6  # Too long


def _score_format_compliance(
    entries: list[dict],
    categories_present: set[str],
) -> float:
    """Score based on ATS-friendly formatting indicators.

    Checks: entries have subsections, categories are standard, entries are
    not too short (< 10 chars) or too long (> 500 chars).
    """
    if not entries:
        return 0.0

    checks_passed = 0
    total_checks = 4

    # Check 1: Has subsections (context/headers for experience)
    exp_entries = [e for e in entries if e.get("category") == "experience"]
    if exp_entries:
        with_subsection = sum(1 for e in exp_entries if e.get("subsection"))
        if with_subsection / len(exp_entries) >= 0.5:
            checks_passed += 1
    else:
        checks_passed += 1  # N/A if no experience

    # Check 2: Uses standard categories
    standard_cats = _REQUIRED_SECTIONS | _OPTIONAL_SECTIONS
    if categories_present and categories_present <= (standard_cats | {"award", "volunteer"}):
        checks_passed += 1

    # Check 3: Entry lengths are reasonable (not too short)
    short_entries = sum(1 for e in entries if len(e.get("text", "")) < 10)
    if short_entries / len(entries) < 0.2:
        checks_passed += 1

    # Check 4: Entry lengths not too long
    long_entries = sum(1 for e in entries if len(e.get("text", "")) > 500)
    if long_entries / len(entries) < 0.3:
        checks_passed += 1

    return checks_passed / total_checks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def score_ats(
    jd_text: str,
    entries: list[dict],
    weights: dict[str, float] | None = None,
) -> dict:
    """Compute composite ATS compatibility score for KB entries against a JD.

    Args:
        jd_text: Job description text.
        entries: List of KB entry dicts (id, text, category, subsection).
        weights: Optional component weight overrides (must sum to 1.0).

    Returns:
        {
            "score": int (0-100),
            "components": {name: {score, weight, weighted}},
            "matched_keywords": list[str],
            "missing_keywords": list[str],
            "matched_skills": list[str],
            "missing_skills": list[str],
            "categories_present": list[str],
            "categories_missing": list[str],
            "entry_count": int,
            "word_count": int,
        }
    """
    w = weights or DEFAULT_WEIGHTS

    if not jd_text or not entries:
        return _empty_result()

    # Analyze JD
    jd_analysis = analyze_jd(jd_text)
    jd_keywords = jd_analysis.get("keywords", [])
    jd_tech = jd_analysis.get("tech_terms", [])
    jd_required = jd_analysis.get("required_keywords", [])

    # Combine all JD keywords for matching
    all_jd_kw = list(dict.fromkeys(jd_keywords + jd_required))

    # Build resume term set from all entries
    resume_terms: set[str] = set()
    for entry in entries:
        resume_terms.update(_tokenize(entry.get("text", "")))
        if entry.get("subsection"):
            resume_terms.update(_tokenize(entry["subsection"]))

    # Categories present
    categories_present = {e.get("category", "") for e in entries if e.get("category")}

    # Score each component
    kw_score, matched_kw, missing_kw = _score_keyword_match(all_jd_kw, resume_terms)
    section_score = _score_section_completeness(categories_present)
    skill_score, matched_skills, missing_skills = _score_skill_match(jd_tech, resume_terms)
    length_score = _score_content_length(entries)
    format_score = _score_format_compliance(entries, categories_present)

    # Compute weighted composite
    components = {
        "keyword_match": {"score": round(kw_score, 3), "weight": w["keyword_match"]},
        "section_completeness": {"score": round(section_score, 3), "weight": w["section_completeness"]},
        "skill_match": {"score": round(skill_score, 3), "weight": w["skill_match"]},
        "content_length": {"score": round(length_score, 3), "weight": w["content_length"]},
        "format_compliance": {"score": round(format_score, 3), "weight": w["format_compliance"]},
    }

    composite = sum(
        c["score"] * c["weight"]
        for c in components.values()
    )

    # Add weighted score to each component
    for name, comp in components.items():
        comp["weighted"] = round(comp["score"] * comp["weight"], 3)

    total_words = sum(len(e.get("text", "").split()) for e in entries)
    cats_missing = sorted(_REQUIRED_SECTIONS - categories_present)

    logger.info(
        "ATS score: %d/100 (%d entries, %d words, %d/%d keywords matched)",
        round(composite * 100), len(entries), total_words,
        len(matched_kw), len(all_jd_kw),
    )

    return {
        "score": round(composite * 100),
        "components": components,
        "matched_keywords": matched_kw,
        "missing_keywords": missing_kw,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "categories_present": sorted(categories_present),
        "categories_missing": cats_missing,
        "entry_count": len(entries),
        "word_count": total_words,
    }


def _empty_result() -> dict:
    """Return a zeroed-out ATS result."""
    return {
        "score": 0,
        "components": {
            name: {"score": 0.0, "weight": w, "weighted": 0.0}
            for name, w in DEFAULT_WEIGHTS.items()
        },
        "matched_keywords": [],
        "missing_keywords": [],
        "matched_skills": [],
        "missing_skills": [],
        "categories_present": [],
        "categories_missing": sorted(_REQUIRED_SECTIONS),
        "entry_count": 0,
        "word_count": 0,
    }
