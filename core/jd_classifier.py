"""JD Classifier — lightweight keyword-based job type detection.

Implements: TASK-030 M8 — Classify job descriptions into types for
pre-filtering KB entries before scoring. No LLM calls required.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Job type keyword dictionaries
# ---------------------------------------------------------------------------

JOB_TYPE_KEYWORDS: dict[str, set[str]] = {
    "backend": {
        "backend", "server", "api", "rest", "graphql", "grpc", "microservice",
        "database", "sql", "postgresql", "mysql", "mongodb", "redis", "celery",
        "django", "flask", "fastapi", "spring", "express", "node.js",
        "java", "python", "golang", "go", "ruby", "rust", "c#", ".net",
    },
    "frontend": {
        "frontend", "front-end", "react", "angular", "vue", "svelte",
        "next.js", "nuxt", "gatsby", "webpack", "vite", "css", "tailwind",
        "html", "javascript", "typescript", "ui", "ux", "responsive",
        "accessibility", "wcag", "component", "spa", "single-page",
    },
    "fullstack": {
        "fullstack", "full-stack", "full stack",
    },
    "data_engineer": {
        "data engineer", "etl", "elt", "data pipeline", "spark", "airflow",
        "kafka", "kinesis", "redshift", "bigquery", "snowflake", "dbt",
        "data warehouse", "data lake", "hadoop", "hive", "presto",
    },
    "data_scientist": {
        "data scientist", "machine learning", "deep learning", "statistics",
        "pandas", "scikit-learn", "tensorflow", "pytorch", "jupyter",
        "model training", "feature engineering", "a/b test", "hypothesis",
    },
    "ml_engineer": {
        "ml engineer", "mlops", "model serving", "sagemaker", "mlflow",
        "kubeflow", "model deployment", "inference", "training pipeline",
        "feature store", "model registry", "embedding",
    },
    "devops": {
        "devops", "sre", "site reliability", "infrastructure", "terraform",
        "kubernetes", "k8s", "docker", "ci/cd", "jenkins", "github actions",
        "aws", "azure", "gcp", "cloud", "ansible", "helm", "monitoring",
        "prometheus", "grafana", "observability",
    },
    "mobile": {
        "mobile", "ios", "android", "swift", "kotlin", "react native",
        "flutter", "dart", "xcode", "app store", "google play",
    },
    "security": {
        "security", "cybersecurity", "penetration", "vulnerability",
        "soc", "siem", "incident response", "threat", "compliance",
        "owasp", "encryption", "iam", "zero trust",
    },
}

# Related types: if a JD matches one type, these are also likely relevant
RELATED_TYPES: dict[str, list[str]] = {
    "backend": ["fullstack", "devops"],
    "frontend": ["fullstack"],
    "fullstack": ["backend", "frontend"],
    "data_engineer": ["data_scientist", "backend"],
    "data_scientist": ["data_engineer", "ml_engineer"],
    "ml_engineer": ["data_scientist", "backend"],
    "devops": ["backend"],
    "mobile": ["frontend"],
    "security": ["devops", "backend"],
}

# Minimum entries threshold before expanding to related types
MIN_ENTRIES_THRESHOLD = 5

_TOKEN_RE = re.compile(r"[a-z][a-z0-9+#./-]*", re.IGNORECASE)


def classify_jd(jd_text: str) -> list[str]:
    """Classify a job description into one or more job types.

    Args:
        jd_text: Job description text.

    Returns:
        List of matching job type keys, sorted by match count (descending).
        Returns ["general"] if no specific type matches.
    """
    if not jd_text:
        return ["general"]

    text_lower = jd_text.lower()
    scores: dict[str, int] = {}

    for job_type, keywords in JOB_TYPE_KEYWORDS.items():
        count = 0
        for keyword in keywords:
            if keyword in text_lower:
                count += 1
        if count > 0:
            scores[job_type] = count

    if not scores:
        return ["general"]

    # Sort by match count descending
    sorted_types = sorted(scores.keys(), key=lambda t: scores[t], reverse=True)

    logger.debug(
        "JD classified as: %s (scores: %s)",
        sorted_types,
        {t: scores[t] for t in sorted_types},
    )

    return sorted_types


def get_relevant_types(primary_types: list[str]) -> list[str]:
    """Expand primary job types to include related types.

    Args:
        primary_types: Output of classify_jd().

    Returns:
        Expanded list including related types (deduplicated).
    """
    if primary_types == ["general"]:
        return ["general"]

    result = list(primary_types)
    for ptype in primary_types:
        for related in RELATED_TYPES.get(ptype, []):
            if related not in result:
                result.append(related)

    return result


def filter_entries_by_type(
    entries: list[dict],
    job_types: list[str],
    min_entries: int = MIN_ENTRIES_THRESHOLD,
) -> list[dict]:
    """Filter KB entries to those matching the detected job types.

    Each KB entry may have a `job_types` field (JSON string or list).
    Entries without job_types are always included (universal entries).

    If filtering yields fewer than min_entries, returns all entries.

    Args:
        entries: List of KB entry dicts.
        job_types: Job types from classify_jd() or get_relevant_types().
        min_entries: Minimum entries before fallback to all.

    Returns:
        Filtered list of entries.
    """
    if not entries or job_types == ["general"]:
        return entries

    import json

    type_set = set(job_types)
    filtered = []

    for entry in entries:
        entry_types = entry.get("job_types")
        if not entry_types:
            # No type restriction — include in all results
            filtered.append(entry)
            continue

        # Parse job_types if stored as JSON string
        if isinstance(entry_types, str):
            try:
                entry_types = json.loads(entry_types)
            except (json.JSONDecodeError, TypeError):
                entry_types = [entry_types]

        if isinstance(entry_types, list) and any(t in type_set for t in entry_types):
            filtered.append(entry)

    # Fallback if too few results
    if len(filtered) < min_entries:
        logger.debug(
            "Pre-filter yielded %d entries (< %d min), using all %d entries",
            len(filtered), min_entries, len(entries),
        )
        return entries

    logger.info(
        "Pre-filtered KB entries: %d/%d for types %s",
        len(filtered), len(entries), job_types,
    )
    return filtered
