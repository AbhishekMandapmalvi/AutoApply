"""Tests for core/ats_scorer.py and core/ats_profiles.py — TASK-030 M6.

Tests ATS composite scoring, individual components, platform profiles,
gap analysis, and API endpoint.
"""

from __future__ import annotations

import json

import pytest

from core.ats_profiles import ATS_PROFILES, get_profile, get_weights, list_profiles
from core.ats_scorer import (
    _score_content_length,
    _score_format_compliance,
    _score_keyword_match,
    _score_section_completeness,
    _score_skill_match,
    score_ats,
)
from db.database import Database

# ---------------------------------------------------------------------------
# Component scorer tests
# ---------------------------------------------------------------------------


class TestKeywordMatch:
    """Tests for _score_keyword_match."""

    def test_full_match(self):
        score, matched, missing = _score_keyword_match(
            ["python", "flask", "docker"],
            {"python", "flask", "docker", "aws"},
        )
        assert score == 1.0
        assert set(matched) == {"python", "flask", "docker"}
        assert missing == []

    def test_partial_match(self):
        score, matched, missing = _score_keyword_match(
            ["python", "flask", "docker", "kubernetes"],
            {"python", "flask"},
        )
        assert 0.4 <= score <= 0.6
        assert "python" in matched
        assert "kubernetes" in missing

    def test_no_match(self):
        score, matched, missing = _score_keyword_match(
            ["java", "spring"],
            {"python", "flask"},
        )
        assert score == 0.0
        assert matched == []
        assert set(missing) == {"java", "spring"}

    def test_empty_jd_keywords(self):
        score, matched, missing = _score_keyword_match([], {"python"})
        assert score == 1.0


class TestSectionCompleteness:
    """Tests for _score_section_completeness."""

    def test_all_sections_present(self):
        score = _score_section_completeness(
            {"experience", "skill", "education", "summary", "project", "certification"}
        )
        assert score == 1.0

    def test_required_only(self):
        score = _score_section_completeness({"experience", "skill", "education"})
        assert 0.6 <= score <= 0.8

    def test_missing_required(self):
        score = _score_section_completeness({"skill"})
        assert score < 0.5

    def test_empty(self):
        score = _score_section_completeness(set())
        assert score == 0.0


class TestSkillMatch:
    """Tests for _score_skill_match."""

    def test_full_skill_match(self):
        score, matched, missing = _score_skill_match(
            ["python", "docker", "aws"],
            {"python", "docker", "aws", "flask"},
        )
        assert score == 1.0
        assert len(missing) == 0

    def test_partial_skill_match(self):
        score, matched, missing = _score_skill_match(
            ["python", "java", "kubernetes"],
            {"python"},
        )
        assert 0.3 <= score <= 0.4
        assert "java" in missing

    def test_empty_jd_tech(self):
        score, matched, missing = _score_skill_match([], {"python"})
        assert score == 1.0


class TestContentLength:
    """Tests for _score_content_length."""

    def test_ideal_length(self):
        entries = [{"text": "word " * 100} for _ in range(5)]  # 500 words
        assert _score_content_length(entries) == 1.0

    def test_too_short(self):
        entries = [{"text": "short"}]  # ~1 word
        assert _score_content_length(entries) < 0.5

    def test_too_long(self):
        entries = [{"text": "word " * 300} for _ in range(5)]  # 1500 words
        assert _score_content_length(entries) < 1.0


class TestFormatCompliance:
    """Tests for _score_format_compliance."""

    def test_good_format(self):
        entries = [
            {"category": "experience", "subsection": "TechCorp — Engineer", "text": "Built APIs using Python and Flask for production services"},
            {"category": "experience", "subsection": "StartupCo — Lead", "text": "Led team of 5 engineers building microservices"},
            {"category": "skill", "text": "Python, Flask, Docker, AWS"},
            {"category": "education", "subsection": "MIT", "text": "M.S. Computer Science, 2020"},
        ]
        cats = {"experience", "skill", "education"}
        score = _score_format_compliance(entries, cats)
        assert score >= 0.75

    def test_empty(self):
        assert _score_format_compliance([], set()) == 0.0


# ---------------------------------------------------------------------------
# Composite scorer tests
# ---------------------------------------------------------------------------


class TestScoreATS:
    """Tests for score_ats composite function."""

    def test_returns_all_fields(self):
        entries = [
            {"id": 1, "text": "Built Python Flask APIs with Docker deployment", "category": "experience", "subsection": "TechCorp"},
            {"id": 2, "text": "Python, Flask, Docker, AWS, Kubernetes", "category": "skill"},
            {"id": 3, "text": "M.S. Computer Science from Stanford", "category": "education", "subsection": "Stanford"},
        ]
        jd = "We need a Python developer with Flask and Docker experience. Must know AWS."
        result = score_ats(jd, entries)

        assert "score" in result
        assert 0 <= result["score"] <= 100
        assert "components" in result
        assert len(result["components"]) == 5
        assert "matched_keywords" in result
        assert "missing_keywords" in result
        assert "matched_skills" in result
        assert "missing_skills" in result
        assert "categories_present" in result
        assert "entry_count" in result
        assert "word_count" in result

    def test_empty_inputs(self):
        result = score_ats("", [])
        assert result["score"] == 0
        assert result["entry_count"] == 0

    def test_good_match_scores_high(self):
        entries = [
            {"id": i, "text": f"Developed Python Flask microservices with Docker on AWS. Led team of {i+2} engineers building scalable APIs.", "category": "experience", "subsection": f"Company {i}"}
            for i in range(5)
        ] + [
            {"id": 10, "text": "Python, Flask, Docker, AWS, Kubernetes, PostgreSQL, Redis, CI/CD", "category": "skill"},
            {"id": 11, "text": "M.S. Computer Science, Stanford University, 2020", "category": "education", "subsection": "Stanford"},
        ]
        jd = """
        Senior Python Developer
        Requirements:
        - 5+ years Python experience
        - Flask or Django web framework
        - Docker and Kubernetes
        - AWS cloud services
        - PostgreSQL database
        """
        result = score_ats(jd, entries)
        assert result["score"] >= 50  # Good match

    def test_custom_weights(self):
        entries = [
            {"id": 1, "text": "Python developer", "category": "experience"},
            {"id": 2, "text": "Python", "category": "skill"},
            {"id": 3, "text": "CS degree", "category": "education"},
        ]
        jd = "Python developer needed"

        # Heavy keyword weight
        w1 = {"keyword_match": 0.80, "section_completeness": 0.05, "skill_match": 0.05, "content_length": 0.05, "format_compliance": 0.05}
        r1 = score_ats(jd, entries, w1)

        # Heavy section weight
        w2 = {"keyword_match": 0.05, "section_completeness": 0.80, "skill_match": 0.05, "content_length": 0.05, "format_compliance": 0.05}
        r2 = score_ats(jd, entries, w2)

        # Scores should differ based on weights
        assert r1["score"] != r2["score"]


# ---------------------------------------------------------------------------
# Platform profiles tests
# ---------------------------------------------------------------------------


class TestATSProfiles:
    """Tests for core/ats_profiles.py."""

    def test_default_profile_exists(self):
        profile = get_profile("default")
        assert profile["name"] == "Default"
        assert sum(profile["weights"].values()) == pytest.approx(1.0)

    def test_all_profiles_weights_sum_to_one(self):
        for pid, profile in ATS_PROFILES.items():
            total = sum(profile["weights"].values())
            assert total == pytest.approx(1.0), f"Profile {pid} weights sum to {total}"

    def test_unknown_platform_returns_default(self):
        profile = get_profile("unknown_ats")
        assert profile["name"] == "Default"

    def test_get_weights(self):
        weights = get_weights("greenhouse")
        assert "keyword_match" in weights
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_list_profiles(self):
        profiles = list_profiles()
        assert len(profiles) == len(ATS_PROFILES)
        for p in profiles:
            assert "id" in p
            assert "name" in p
            assert "description" in p

    def test_workday_heavier_keyword_weight(self):
        default_kw = get_weights("default")["keyword_match"]
        workday_kw = get_weights("workday")["keyword_match"]
        assert workday_kw > default_kw


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def kb_client(tmp_path, monkeypatch):
    """Yield (test_client, db, tmp_path) with KB routes available."""
    monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("app.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("routes.profile.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("routes.applications.get_data_dir", lambda: tmp_path)

    (tmp_path / "profile" / "experiences").mkdir(parents=True)
    minimal_config = {
        "profile": {
            "first_name": "Test", "last_name": "User",
            "email": "test@example.com", "phone": "555-0100",
            "city": "Remote", "state": "", "bio": "Test bio",
        },
        "search_criteria": {"job_titles": ["Engineer"], "locations": ["Remote"]},
        "bot": {"enabled_platforms": ["linkedin"]},
    }
    (tmp_path / "config.json").write_text(json.dumps(minimal_config), encoding="utf-8")

    test_db = Database(tmp_path / "test.db")
    monkeypatch.setattr("app.db", test_db)
    monkeypatch.setattr("app_state.db", test_db)

    from app import app
    app.config["TESTING"] = True
    return app.test_client(), test_db, tmp_path


def _insert_entries(db):
    """Insert sample KB entries for testing."""
    db.save_kb_entry(category="experience", text="Built Python Flask APIs with Docker", subsection="TechCorp", job_types=None, tags=None, source_doc_id=None)
    db.save_kb_entry(category="skill", text="Python, Flask, Docker, AWS", subsection="", job_types=None, tags=None, source_doc_id=None)
    db.save_kb_entry(category="education", text="M.S. Computer Science", subsection="Stanford", job_types=None, tags=None, source_doc_id=None)


class TestATSEndpoint:
    """Tests for POST /api/kb/ats-score."""

    def test_ats_score_success(self, kb_client):
        client, db, _tmp = kb_client
        _insert_entries(db)
        resp = client.post("/api/kb/ats-score", json={
            "jd_text": "We need a Python Flask developer with Docker experience",
            "platform": "default",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert "score" in data
        assert 0 <= data["score"] <= 100
        assert data["platform"] == "default"

    def test_ats_score_with_platform(self, kb_client):
        client, db, _tmp = kb_client
        _insert_entries(db)
        resp = client.post("/api/kb/ats-score", json={
            "jd_text": "Python developer needed",
            "platform": "workday",
        })
        assert resp.status_code == 200
        assert resp.get_json()["platform"] == "workday"

    def test_ats_score_no_jd(self, kb_client):
        client, _db, _tmp = kb_client
        resp = client.post("/api/kb/ats-score", json={})
        assert resp.status_code == 400

    def test_ats_score_empty_kb(self, kb_client):
        client, _db, _tmp = kb_client
        resp = client.post("/api/kb/ats-score", json={"jd_text": "Python developer"})
        assert resp.status_code == 400


class TestATSProfilesEndpoint:
    """Tests for GET /api/kb/ats-profiles."""

    def test_list_profiles(self, kb_client):
        client, _db, _tmp = kb_client
        resp = client.get("/api/kb/ats-profiles")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "profiles" in data
        assert len(data["profiles"]) >= 7
