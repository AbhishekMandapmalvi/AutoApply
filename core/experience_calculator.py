"""Experience calculator — compute years of experience by domain from roles.

Implements: TASK-030 M1 — domain-specific experience years from the roles table,
used for ATS scoring and resume section ordering.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db.database import Database

logger = logging.getLogger(__name__)


def calculate_experience(db: "Database") -> dict:
    """Calculate total and per-domain years of experience from stored roles.

    Args:
        db: Database instance with roles table.

    Returns:
        Dict with 'total_years' (float) and 'by_domain' (dict[str, float]).
    """
    roles = db.get_roles()
    if not roles:
        return {"total_years": 0.0, "by_domain": {}}

    total_months = 0.0
    domain_months: dict[str, float] = {}

    for role in roles:
        months = _role_duration_months(role.get("start_date"), role.get("end_date"))
        total_months += months

        domain = role.get("domain") or "general"
        domain_months[domain] = domain_months.get(domain, 0.0) + months

    total_years = round(total_months / 12.0, 1)
    by_domain = {d: round(m / 12.0, 1) for d, m in domain_months.items()}

    return {"total_years": total_years, "by_domain": by_domain}


def _role_duration_months(start_str: str | None, end_str: str | None) -> float:
    """Calculate duration of a role in months.

    Args:
        start_str: Start date string (YYYY-MM, YYYY-MM-DD, or YYYY).
        end_str: End date string, or None/empty/"Present" for current role.

    Returns:
        Duration in months (float). Returns 0 if start_str is invalid.
    """
    start = _parse_date(start_str)
    if start is None:
        return 0.0

    if not end_str or end_str.lower().strip() in ("present", "current", "now", ""):
        end: date = date.today()
    else:
        parsed_end = _parse_date(end_str)
        end = parsed_end if parsed_end is not None else date.today()

    if end < start:
        return 0.0

    months = (end.year - start.year) * 12 + (end.month - start.month)
    return max(0.0, float(months))


def _parse_date(date_str: str | None) -> date | None:
    """Parse a date string in various formats.

    Supports: YYYY-MM-DD, YYYY-MM, YYYY, and common variations.
    """
    if not date_str or not date_str.strip():
        return None

    date_str = date_str.strip()

    formats = ["%Y-%m-%d", "%Y-%m", "%Y", "%m/%Y", "%m/%d/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    logger.debug("Could not parse date: %s", date_str)
    return None
