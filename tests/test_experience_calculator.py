"""Tests for core/experience_calculator.py — TASK-030 M1.

Tests experience calculation from roles.
"""

from datetime import date

import pytest

from core.experience_calculator import (
    _parse_date,
    _role_duration_months,
    calculate_experience,
)
from db.database import Database


@pytest.fixture
def db(tmp_path):
    """Create a fresh database for each test."""
    return Database(tmp_path / "test.db")


class TestCalculateExperience:
    """Tests for calculate_experience()."""

    def test_no_roles(self, db):
        """Empty roles table returns 0 years."""
        result = calculate_experience(db)
        assert result["total_years"] == 0.0
        assert result["by_domain"] == {}

    def test_single_role(self, db):
        """Single role calculates correctly."""
        db.save_role(
            title="Engineer",
            company="Acme",
            start_date="2020-01",
            end_date="2023-01",
            domain="backend",
        )
        result = calculate_experience(db)
        assert result["total_years"] == 3.0
        assert result["by_domain"]["backend"] == 3.0

    def test_multiple_domains(self, db):
        """Multiple domains are tracked separately."""
        db.save_role(
            title="Backend Dev", company="A",
            start_date="2018-01", end_date="2020-01", domain="backend",
        )
        db.save_role(
            title="Frontend Dev", company="B",
            start_date="2020-01", end_date="2022-01", domain="frontend",
        )
        result = calculate_experience(db)
        assert result["total_years"] == 4.0
        assert result["by_domain"]["backend"] == 2.0
        assert result["by_domain"]["frontend"] == 2.0

    def test_present_end_date(self, db):
        """Roles with 'Present' end date use today's date."""
        db.save_role(
            title="Lead", company="C",
            start_date="2023-01", end_date="Present", domain="management",
        )
        result = calculate_experience(db)
        assert result["total_years"] > 0

    def test_null_domain_defaults_to_general(self, db):
        """Null domain maps to 'general'."""
        db.save_role(
            title="Dev", company="D",
            start_date="2020-01", end_date="2021-01",
        )
        result = calculate_experience(db)
        assert "general" in result["by_domain"]


class TestRoleDurationMonths:
    """Tests for _role_duration_months()."""

    def test_exact_year(self):
        assert _role_duration_months("2020-01", "2021-01") == 12.0

    def test_six_months(self):
        assert _role_duration_months("2020-01", "2020-07") == 6.0

    def test_present(self):
        result = _role_duration_months("2020-01", "Present")
        assert result > 0

    def test_none_start(self):
        assert _role_duration_months(None, "2020-01") == 0.0

    def test_end_before_start(self):
        assert _role_duration_months("2023-01", "2020-01") == 0.0

    def test_empty_end(self):
        """Empty end date treated as present."""
        result = _role_duration_months("2020-01", "")
        assert result > 0


class TestParseDate:
    """Tests for _parse_date()."""

    def test_yyyy_mm_dd(self):
        result = _parse_date("2023-06-15")
        assert result == date(2023, 6, 15)

    def test_yyyy_mm(self):
        result = _parse_date("2023-06")
        assert result == date(2023, 6, 1)

    def test_yyyy(self):
        result = _parse_date("2023")
        assert result == date(2023, 1, 1)

    def test_none(self):
        assert _parse_date(None) is None

    def test_empty(self):
        assert _parse_date("") is None

    def test_invalid(self):
        assert _parse_date("not-a-date") is None
