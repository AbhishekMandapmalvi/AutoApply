"""ATS Platform Profiles — vendor-specific scoring weight adjustments.

Implements: TASK-030 M6 — Different ATS platforms have different priorities.
For example, Workday emphasizes keyword density while Greenhouse prioritizes
section structure. These profiles adjust scoring weights accordingly.
"""

from __future__ import annotations

import logging

from core.ats_scorer import DEFAULT_WEIGHTS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform profile definitions
# ---------------------------------------------------------------------------

# Each profile overrides DEFAULT_WEIGHTS for a specific ATS vendor.
# Weights must sum to 1.0.

ATS_PROFILES: dict[str, dict] = {
    "default": {
        "name": "Default",
        "description": "Balanced scoring for unknown ATS platforms",
        "weights": dict(DEFAULT_WEIGHTS),
    },
    "greenhouse": {
        "name": "Greenhouse",
        "description": "Greenhouse emphasizes structured sections and keyword matching",
        "weights": {
            "keyword_match": 0.30,
            "section_completeness": 0.25,
            "skill_match": 0.20,
            "content_length": 0.15,
            "format_compliance": 0.10,
        },
    },
    "lever": {
        "name": "Lever",
        "description": "Lever prioritizes keyword density and technical skills",
        "weights": {
            "keyword_match": 0.35,
            "section_completeness": 0.15,
            "skill_match": 0.25,
            "content_length": 0.15,
            "format_compliance": 0.10,
        },
    },
    "workday": {
        "name": "Workday",
        "description": "Workday heavily weights keyword matching for automated screening",
        "weights": {
            "keyword_match": 0.40,
            "section_completeness": 0.15,
            "skill_match": 0.20,
            "content_length": 0.15,
            "format_compliance": 0.10,
        },
    },
    "ashby": {
        "name": "Ashby",
        "description": "Ashby balances skills and formatting for modern startups",
        "weights": {
            "keyword_match": 0.30,
            "section_completeness": 0.20,
            "skill_match": 0.25,
            "content_length": 0.10,
            "format_compliance": 0.15,
        },
    },
    "icims": {
        "name": "iCIMS",
        "description": "iCIMS emphasizes keyword density and content length",
        "weights": {
            "keyword_match": 0.40,
            "section_completeness": 0.15,
            "skill_match": 0.15,
            "content_length": 0.20,
            "format_compliance": 0.10,
        },
    },
    "taleo": {
        "name": "Taleo",
        "description": "Taleo (Oracle) focuses on keyword matching and format compliance",
        "weights": {
            "keyword_match": 0.35,
            "section_completeness": 0.20,
            "skill_match": 0.15,
            "content_length": 0.15,
            "format_compliance": 0.15,
        },
    },
}


def get_profile(platform: str) -> dict:
    """Get ATS profile for a platform.

    Args:
        platform: Platform name (greenhouse, lever, workday, etc.).

    Returns:
        Profile dict with name, description, and weights.
    """
    key = platform.lower().strip() if platform else "default"
    profile = ATS_PROFILES.get(key, ATS_PROFILES["default"])
    logger.debug("Using ATS profile: %s", profile["name"])
    return profile


def get_weights(platform: str) -> dict[str, float]:
    """Get scoring weights for a platform.

    Args:
        platform: Platform name.

    Returns:
        Dict mapping component name to weight (sums to 1.0).
    """
    weights: dict[str, float] = get_profile(platform)["weights"]
    return weights


def list_profiles() -> list[dict]:
    """List all available ATS profiles.

    Returns:
        List of {id, name, description} dicts.
    """
    return [
        {"id": pid, "name": p["name"], "description": p["description"]}
        for pid, p in ATS_PROFILES.items()
    ]
