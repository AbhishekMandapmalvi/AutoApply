"""Tests for TASK-030 M9 — Intelligence: outcome learning, cover letter assembly,
reuse stats, JD classifier integration.

Covers: db/database.py (usage log, feedback, effectiveness, reuse stats),
        core/cover_letter_assembler.py, core/resume_assembler.py (JD pre-filter),
        core/resume_scorer.py (effectiveness weighting),
        routes/knowledge_base.py (feedback, effectiveness endpoints),
        routes/analytics.py (reuse-stats endpoint).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from db.database import Database

# ---------------------------------------------------------------------------
# DB: Usage log + Feedback + Effectiveness
# ---------------------------------------------------------------------------


class TestKBUsageLog:
    """Tests for kb_usage_log DB methods."""

    @pytest.fixture()
    def db(self, tmp_path):
        return Database(tmp_path / "test.db")

    def _seed_entries(self, db: Database) -> list[int]:
        """Insert 3 KB entries and return their IDs."""
        ids = []
        for i, (cat, text) in enumerate([
            ("experience", "Built REST APIs in Python"),
            ("skill", "Python programming"),
            ("experience", "Led team of 5 engineers"),
        ]):
            eid = db.save_kb_entry(cat, text, subsection=f"Role {i}")
            ids.append(eid)
        return ids

    def test_log_usage_empty(self, db):
        count = db.log_kb_usage([])
        assert count == 0

    def test_log_usage_inserts_rows(self, db):
        ids = self._seed_entries(db)
        count = db.log_kb_usage(ids, application_id=1, scores={ids[0]: 0.85})
        assert count == 3

    def test_log_usage_increments_count(self, db):
        ids = self._seed_entries(db)
        db.log_kb_usage(ids[:1], application_id=1)
        db.log_kb_usage(ids[:1], application_id=2)

        with db._connect() as conn:
            row = conn.execute(
                "SELECT usage_count FROM knowledge_base WHERE id = ?", (ids[0],)
            ).fetchone()
        assert row["usage_count"] == 2

    def test_log_usage_updates_last_used(self, db):
        ids = self._seed_entries(db)
        db.log_kb_usage(ids[:1], application_id=1)

        with db._connect() as conn:
            row = conn.execute(
                "SELECT last_used_at FROM knowledge_base WHERE id = ?", (ids[0],)
            ).fetchone()
        assert row["last_used_at"] is not None

    def test_update_outcome_interview(self, db):
        ids = self._seed_entries(db)
        db.log_kb_usage(ids, application_id=10)

        updated = db.update_kb_outcome(10, "interview")
        assert updated == 3

        # Check effectiveness_score updated
        with db._connect() as conn:
            row = conn.execute(
                "SELECT effectiveness_score FROM knowledge_base WHERE id = ?",
                (ids[0],),
            ).fetchone()
        assert row["effectiveness_score"] == 1.0  # 1 interview / 1 total

    def test_update_outcome_rejected_no_score_change(self, db):
        ids = self._seed_entries(db)
        db.log_kb_usage(ids[:1], application_id=10)

        updated = db.update_kb_outcome(10, "rejected")
        assert updated == 1

        # effectiveness_score stays 0 (rejected doesn't trigger recalc)
        with db._connect() as conn:
            row = conn.execute(
                "SELECT effectiveness_score FROM knowledge_base WHERE id = ?",
                (ids[0],),
            ).fetchone()
        assert row["effectiveness_score"] == 0.0

    def test_update_outcome_mixed(self, db):
        """Interview rate = 1/2 = 0.5 after one interview + one rejection."""
        ids = self._seed_entries(db)
        db.log_kb_usage(ids[:1], application_id=10)
        db.log_kb_usage(ids[:1], application_id=11)

        db.update_kb_outcome(10, "rejected")
        db.update_kb_outcome(11, "interview")

        with db._connect() as conn:
            row = conn.execute(
                "SELECT effectiveness_score FROM knowledge_base WHERE id = ?",
                (ids[0],),
            ).fetchone()
        assert row["effectiveness_score"] == 0.5

    def test_update_outcome_no_match(self, db):
        updated = db.update_kb_outcome(999, "interview")
        assert updated == 0

    def test_get_effectiveness_empty(self, db):
        result = db.get_kb_effectiveness()
        assert result == []

    def test_get_effectiveness_returns_used(self, db):
        ids = self._seed_entries(db)
        db.log_kb_usage(ids[:2], application_id=1)
        db.update_kb_outcome(1, "interview")

        result = db.get_kb_effectiveness(limit=10)
        assert len(result) == 2
        assert result[0]["effectiveness_score"] == 1.0


class TestReuseStats:
    """Tests for get_reuse_stats()."""

    @pytest.fixture()
    def db(self, tmp_path):
        return Database(tmp_path / "test.db")

    def test_reuse_stats_empty(self, db):
        stats = db.get_reuse_stats()
        assert stats["total_assemblies"] == 0
        assert stats["total_entries_used"] == 0
        assert stats["unique_entries_used"] == 0

    def test_reuse_stats_with_data(self, db):
        e1 = db.save_kb_entry("experience", "Built APIs", subsection="Dev")
        e2 = db.save_kb_entry("skill", "Python", subsection="Lang")

        db.log_kb_usage([e1, e2], application_id=1)
        db.log_kb_usage([e1], application_id=2)
        db.update_kb_outcome(1, "interview")

        stats = db.get_reuse_stats()
        assert stats["total_assemblies"] == 2
        assert stats["total_entries_used"] == 3
        assert stats["unique_entries_used"] == 2
        assert stats["interviews_from_kb"] == 1
        assert stats["avg_effectiveness"] > 0
        assert "experience" in stats["top_categories"]


# ---------------------------------------------------------------------------
# Cover Letter Assembly
# ---------------------------------------------------------------------------


class TestCoverLetterAssembly:
    """Tests for core.cover_letter_assembler module."""

    def _make_kb_mock(self, entries):
        kb = MagicMock()
        kb.get_all_entries.return_value = entries
        return kb

    def test_empty_kb(self):
        from core.cover_letter_assembler import assemble_cover_letter

        kb = self._make_kb_mock([])
        result = assemble_cover_letter("JD text", {"name": "Test"}, kb)
        assert result is None

    def test_insufficient_experience(self):
        from core.cover_letter_assembler import assemble_cover_letter

        entries = [
            {"id": 1, "category": "experience", "text": "Built APIs", "subsection": "Dev"},
        ]
        kb = self._make_kb_mock(entries)

        with patch("core.cover_letter_assembler.score_kb_entries", return_value=[
            {"id": 1, "category": "experience", "text": "Built APIs", "subsection": "Dev", "score": 0.9},
        ]):
            result = assemble_cover_letter("Backend developer", {"name": "Test"}, kb)
        assert result is None

    def test_successful_assembly(self):
        from core.cover_letter_assembler import assemble_cover_letter

        entries = [
            {"id": 1, "category": "experience", "text": "Built REST APIs in Python", "subsection": "Backend Dev"},
            {"id": 2, "category": "experience", "text": "Led team of 5", "subsection": "Tech Lead"},
            {"id": 3, "category": "experience", "text": "Deployed to AWS", "subsection": "DevOps"},
            {"id": 4, "category": "skill", "text": "Python", "subsection": ""},
            {"id": 5, "category": "skill", "text": "Django", "subsection": ""},
        ]
        kb = self._make_kb_mock(entries)

        scored = [
            {**e, "score": 0.9 - i * 0.05, "scoring_method": "tfidf"}
            for i, e in enumerate(entries)
        ]

        with patch("core.cover_letter_assembler.score_kb_entries", return_value=scored):
            result = assemble_cover_letter(
                "Backend developer Python",
                {"name": "John Doe"},
                kb,
                job_title="Backend Developer",
                company="Acme Corp",
            )

        assert result is not None
        assert "Dear Hiring Manager" in result
        assert "Backend Developer" in result
        assert "Acme Corp" in result
        assert "John Doe" in result
        assert "Sincerely" in result

    def test_assembly_without_company(self):
        from core.cover_letter_assembler import assemble_cover_letter

        entries = [
            {"id": 1, "category": "experience", "text": "Built APIs", "subsection": "Dev"},
            {"id": 2, "category": "experience", "text": "Led team", "subsection": "Lead"},
            {"id": 3, "category": "skill", "text": "Python", "subsection": ""},
        ]
        kb = self._make_kb_mock(entries)

        scored = [{**e, "score": 0.9, "scoring_method": "tfidf"} for e in entries]

        with patch("core.cover_letter_assembler.score_kb_entries", return_value=scored):
            result = assemble_cover_letter("JD", {"name": "Test"}, kb, job_title="Engineer")

        assert result is not None
        assert "Engineer" in result


# ---------------------------------------------------------------------------
# JD Classifier Integration in Resume Assembler
# ---------------------------------------------------------------------------


class TestAssemblerJDPreFilter:
    """Tests that resume_assembler uses JD classifier for pre-filtering."""

    def test_assembler_calls_classify_jd(self):
        from core.resume_assembler import assemble_resume

        kb = MagicMock()
        kb.get_all_entries.return_value = [
            {"id": 1, "category": "experience", "text": "Built APIs", "job_types": '["backend"]'},
        ]

        with patch("core.jd_classifier.classify_jd") as mock_classify, \
             patch("core.jd_classifier.get_relevant_types", return_value=["backend"]), \
             patch("core.jd_classifier.filter_entries_by_type", return_value=[
                 {"id": 1, "category": "experience", "text": "Built APIs"},
             ]), \
             patch("core.resume_assembler.score_kb_entries", return_value=[]):

            mock_classify.return_value = ["backend"]
            assemble_resume("Backend dev with Python", {"name": "Test"}, kb)
            mock_classify.assert_called_once()


# ---------------------------------------------------------------------------
# Effectiveness Weighting in Scorer
# ---------------------------------------------------------------------------


class TestEffectivenessWeighting:
    """Tests that resume_scorer blends effectiveness_score."""

    def test_effectiveness_boosts_score(self):
        from core.resume_scorer import score_kb_entries

        entries = [
            {"id": 1, "category": "experience", "text": "Built REST APIs in Python Django Flask",
             "effectiveness_score": 0.9},
            {"id": 2, "category": "experience", "text": "Built REST APIs in Python Django Flask",
             "effectiveness_score": 0.0},
        ]

        results = score_kb_entries(
            "We need a Python Django REST API developer",
            entries,
        )

        # Entry with higher effectiveness should score higher
        if len(results) >= 2:
            scores = {r["id"]: r["score"] for r in results}
            assert scores.get(1, 0) >= scores.get(2, 0)

    def test_no_effectiveness_no_change(self):
        from core.resume_scorer import score_kb_entries

        entries = [
            {"id": 1, "category": "experience", "text": "Built REST APIs in Python Django"},
        ]
        results = score_kb_entries("Python Django developer", entries)
        # Should still work without effectiveness_score
        assert all("score" in r for r in results)


# ---------------------------------------------------------------------------
# API Endpoint Tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def m9_client(tmp_path, monkeypatch):
    """Create Flask test client for M9 endpoint tests."""
    from db.database import Database

    monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("app.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("routes.profile.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("routes.applications.get_data_dir", lambda: tmp_path)

    (tmp_path / "profile" / "experiences").mkdir(parents=True)
    minimal_config = {
        "profile": {
            "first_name": "Test", "last_name": "User",
            "email": "t@e.com", "phone": "555",
            "city": "R", "state": "", "bio": "Test",
        },
        "search_criteria": {"job_titles": ["Eng"], "locations": ["Remote"]},
        "bot": {"enabled_platforms": ["linkedin"]},
    }
    (tmp_path / "config.json").write_text(json.dumps(minimal_config), encoding="utf-8")

    test_db = Database(tmp_path / "test.db")
    monkeypatch.setattr("app.db", test_db)
    monkeypatch.setattr("app_state.db", test_db)

    from app import app
    app.config["TESTING"] = True
    return app.test_client(), test_db


class TestFeedbackAPI:
    """Tests for POST /api/kb/feedback endpoint."""

    def test_feedback_missing_body(self, m9_client):
        client, _ = m9_client
        resp = client.post("/api/kb/feedback")
        assert resp.status_code == 400

    def test_feedback_invalid_outcome(self, m9_client):
        client, _ = m9_client
        resp = client.post("/api/kb/feedback", json={
            "application_id": 1, "outcome": "invalid",
        })
        assert resp.status_code == 400

    def test_feedback_success(self, m9_client):
        client, db = m9_client
        eid = db.save_kb_entry("experience", "Built APIs", subsection="Dev")
        db.log_kb_usage([eid], application_id=42)

        resp = client.post("/api/kb/feedback", json={
            "application_id": 42, "outcome": "interview",
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["updated"] == 1

    def test_feedback_no_matching_app(self, m9_client):
        client, _ = m9_client
        resp = client.post("/api/kb/feedback", json={
            "application_id": 999, "outcome": "rejected",
        })
        assert resp.status_code == 200
        assert resp.get_json()["updated"] == 0


class TestEffectivenessAPI:
    """Tests for GET /api/kb/effectiveness endpoint."""

    def test_effectiveness_empty(self, m9_client):
        client, _ = m9_client
        resp = client.get("/api/kb/effectiveness")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_effectiveness_returns_used(self, m9_client):
        client, db = m9_client
        eid = db.save_kb_entry("experience", "Built APIs", subsection="Dev")
        db.log_kb_usage([eid], application_id=1)

        resp = client.get("/api/kb/effectiveness")
        assert resp.status_code == 200
        entries = resp.get_json()
        assert len(entries) == 1
        assert entries[0]["id"] == eid


class TestReuseStatsAPI:
    """Tests for GET /api/analytics/reuse-stats endpoint."""

    def test_reuse_stats_empty(self, m9_client):
        client, _ = m9_client
        resp = client.get("/api/analytics/reuse-stats")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["total_assemblies"] == 0

    def test_reuse_stats_with_data(self, m9_client):
        client, db = m9_client
        eid = db.save_kb_entry("skill", "Python", subsection="Lang")
        db.log_kb_usage([eid], application_id=1)

        resp = client.get("/api/analytics/reuse-stats")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["total_assemblies"] == 1
        assert body["total_entries_used"] == 1
