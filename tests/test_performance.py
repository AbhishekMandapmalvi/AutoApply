"""Tests for TASK-030 M8 — Performance: PDF cache, JD classifier, async upload.

Covers: core/pdf_cache.py, core/jd_classifier.py, routes/knowledge_base.py async endpoints.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# PDF Cache tests
# ---------------------------------------------------------------------------


class TestPDFCache:
    """Tests for core.pdf_cache module."""

    def test_content_hash_deterministic(self):
        from core.pdf_cache import content_hash

        h1 = content_hash("\\documentclass{article}")
        h2 = content_hash("\\documentclass{article}")
        assert h1 == h2

    def test_content_hash_length(self):
        from core.pdf_cache import content_hash

        h = content_hash("some latex content")
        assert len(h) == 16

    def test_content_hash_different_content(self):
        from core.pdf_cache import content_hash

        h1 = content_hash("content A")
        h2 = content_hash("content B")
        assert h1 != h2

    def test_cache_miss(self, tmp_path):
        from core.pdf_cache import get_cached

        with patch("core.pdf_cache._get_cache_dir", return_value=tmp_path):
            result = get_cached("nonexistent content")
        assert result is None

    def test_store_and_retrieve(self, tmp_path):
        from core.pdf_cache import get_cached, store

        tex = "\\documentclass{article}\\begin{document}Hello\\end{document}"
        pdf_bytes = b"%PDF-1.4 fake pdf content"

        with patch("core.pdf_cache._get_cache_dir", return_value=tmp_path):
            store(tex, pdf_bytes)
            result = get_cached(tex)

        assert result == pdf_bytes

    def test_evict_lru_no_eviction_needed(self, tmp_path):
        from core.pdf_cache import evict_lru

        with patch("core.pdf_cache._get_cache_dir", return_value=tmp_path):
            evicted = evict_lru()
        assert evicted == 0

    def test_evict_lru_removes_oldest(self, tmp_path):
        from core.pdf_cache import MAX_CACHE_SIZE, evict_lru

        # Create MAX_CACHE_SIZE + 5 files
        for i in range(MAX_CACHE_SIZE + 5):
            (tmp_path / f"{i:04d}.pdf").write_bytes(b"data")
            # Ensure different mtime
            (tmp_path / f"{i:04d}.pdf").touch()

        with patch("core.pdf_cache._get_cache_dir", return_value=tmp_path):
            evicted = evict_lru()

        assert evicted == 5
        remaining = list(tmp_path.glob("*.pdf"))
        assert len(remaining) == MAX_CACHE_SIZE

    def test_clear_cache(self, tmp_path):
        from core.pdf_cache import clear_cache

        for i in range(3):
            (tmp_path / f"{i}.pdf").write_bytes(b"data")

        with patch("core.pdf_cache._get_cache_dir", return_value=tmp_path):
            count = clear_cache()

        assert count == 3
        assert list(tmp_path.glob("*.pdf")) == []

    def test_cache_stats(self, tmp_path):
        from core.pdf_cache import cache_stats

        (tmp_path / "a.pdf").write_bytes(b"1234567890")
        (tmp_path / "b.pdf").write_bytes(b"12345")

        with patch("core.pdf_cache._get_cache_dir", return_value=tmp_path):
            stats = cache_stats()

        assert stats["count"] == 2
        assert stats["size_bytes"] == 15
        assert stats["max_size"] == 200


# ---------------------------------------------------------------------------
# JD Classifier tests
# ---------------------------------------------------------------------------


class TestJDClassifier:
    """Tests for core.jd_classifier module."""

    def test_classify_empty_text(self):
        from core.jd_classifier import classify_jd

        assert classify_jd("") == ["general"]

    def test_classify_no_match(self):
        from core.jd_classifier import classify_jd

        result = classify_jd("We are looking for a passionate team player.")
        assert result == ["general"]

    def test_classify_backend(self):
        from core.jd_classifier import classify_jd

        jd = "We need a backend developer with experience in Python, Django, REST API, and PostgreSQL."
        result = classify_jd(jd)
        assert "backend" in result

    def test_classify_frontend(self):
        from core.jd_classifier import classify_jd

        jd = "Looking for a frontend engineer skilled in React, TypeScript, CSS, and responsive design."
        result = classify_jd(jd)
        assert "frontend" in result

    def test_classify_devops(self):
        from core.jd_classifier import classify_jd

        jd = "DevOps engineer needed for Kubernetes, Docker, CI/CD, Terraform, and AWS infrastructure."
        result = classify_jd(jd)
        assert "devops" in result

    def test_classify_multiple_types(self):
        from core.jd_classifier import classify_jd

        jd = (
            "Full-stack developer: React frontend, Python Django backend, "
            "PostgreSQL database, Docker deployment."
        )
        result = classify_jd(jd)
        assert len(result) >= 2

    def test_classify_sorted_by_score(self):
        from core.jd_classifier import classify_jd

        # Backend-heavy JD
        jd = (
            "Backend developer: Python, Django, Flask, FastAPI, PostgreSQL, Redis, "
            "REST API, microservice. Some React knowledge helpful."
        )
        result = classify_jd(jd)
        assert result[0] == "backend"

    def test_get_relevant_types_general(self):
        from core.jd_classifier import get_relevant_types

        assert get_relevant_types(["general"]) == ["general"]

    def test_get_relevant_types_expands(self):
        from core.jd_classifier import get_relevant_types

        result = get_relevant_types(["backend"])
        assert "backend" in result
        assert "fullstack" in result
        assert "devops" in result

    def test_get_relevant_types_dedup(self):
        from core.jd_classifier import get_relevant_types

        result = get_relevant_types(["backend", "devops"])
        # Should not have duplicates
        assert len(result) == len(set(result))

    def test_filter_entries_general(self):
        from core.jd_classifier import filter_entries_by_type

        entries = [{"id": 1}, {"id": 2}]
        result = filter_entries_by_type(entries, ["general"])
        assert result == entries

    def test_filter_entries_by_type_match(self):
        from core.jd_classifier import filter_entries_by_type

        entries = [
            {"id": 1, "job_types": '["backend"]'},
            {"id": 2, "job_types": '["frontend"]'},
            {"id": 3, "job_types": None},  # universal
            {"id": 4, "job_types": '["backend", "devops"]'},
        ]
        result = filter_entries_by_type(entries, ["backend"], min_entries=1)
        ids = [e["id"] for e in result]
        assert 1 in ids
        assert 3 in ids  # universal always included
        assert 4 in ids
        assert 2 not in ids

    def test_filter_entries_fallback_when_too_few(self):
        from core.jd_classifier import filter_entries_by_type

        entries = [
            {"id": 1, "job_types": '["frontend"]'},
            {"id": 2, "job_types": '["frontend"]'},
        ]
        # Only 0 match backend, min_entries=5 → fallback to all
        result = filter_entries_by_type(entries, ["backend"], min_entries=5)
        assert len(result) == 2

    def test_filter_entries_empty(self):
        from core.jd_classifier import filter_entries_by_type

        result = filter_entries_by_type([], ["backend"])
        assert result == []


# ---------------------------------------------------------------------------
# Async upload endpoint tests
# ---------------------------------------------------------------------------


class TestAsyncUpload:
    """Tests for async upload endpoints."""

    @pytest.fixture()
    def async_client(self, tmp_path, monkeypatch):
        """Create Flask test client with KB routes."""
        import json

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
        (tmp_path / "config.json").write_text(
            json.dumps(minimal_config), encoding="utf-8",
        )

        test_db = Database(tmp_path / "test.db")
        monkeypatch.setattr("app.db", test_db)
        monkeypatch.setattr("app_state.db", test_db)

        from app import app

        app.config["TESTING"] = True
        yield app.test_client()

    def test_async_upload_no_file(self, async_client):
        resp = async_client.post("/api/kb/upload/async")
        assert resp.status_code == 400

    def test_async_upload_unsupported_type(self, async_client):
        from io import BytesIO

        data = {"file": (BytesIO(b"content"), "test.exe")}
        resp = async_client.post(
            "/api/kb/upload/async",
            data=data,
            content_type="multipart/form-data",
        )
        assert resp.status_code == 400

    def test_async_upload_returns_task_id(self, async_client):
        from io import BytesIO

        with patch("routes.knowledge_base._run_upload_async"):
            # Patch threading so it doesn't actually start
            with patch("routes.knowledge_base.threading") as mock_threading:
                mock_thread = MagicMock()
                mock_threading.Thread.return_value = mock_thread

                data = {"file": (BytesIO(b"resume content"), "resume.txt")}
                resp = async_client.post(
                    "/api/kb/upload/async",
                    data=data,
                    content_type="multipart/form-data",
                )

        assert resp.status_code == 202
        body = resp.get_json()
        assert "task_id" in body
        assert body["status"] == "processing"

    def test_upload_status_not_found(self, async_client):
        resp = async_client.get("/api/kb/upload/status/nonexistent123")
        assert resp.status_code == 404

    def test_upload_status_returns_task(self, async_client):
        from routes.knowledge_base import _upload_lock, _upload_tasks

        task_id = "test123abc"
        with _upload_lock:
            _upload_tasks[task_id] = {
                "status": "completed",
                "filename": "test.txt",
                "entries_created": 5,
                "error": None,
                "message": "Extracted 5 entries",
            }

        try:
            resp = async_client.get(f"/api/kb/upload/status/{task_id}")
            assert resp.status_code == 200
            body = resp.get_json()
            assert body["status"] == "completed"
            assert body["entries_created"] == 5
        finally:
            with _upload_lock:
                _upload_tasks.pop(task_id, None)


# ---------------------------------------------------------------------------
# LaTeX compiler cache integration test
# ---------------------------------------------------------------------------


class TestLatexCompilerCache:
    """Test that latex_compiler uses pdf_cache correctly."""

    def test_compile_latex_checks_cache(self):
        from core.latex_compiler import compile_latex

        fake_pdf = b"%PDF-1.4 cached"
        with patch("core.pdf_cache.get_cached", return_value=fake_pdf):
            result = compile_latex("\\documentclass{article}", use_cache=True)

        assert result == fake_pdf

    def test_compile_latex_cache_disabled(self):
        from core.latex_compiler import compile_latex

        with patch("core.latex_compiler.find_pdflatex", return_value=None):
            result = compile_latex("\\documentclass{article}", use_cache=False)

        assert result is None  # No pdflatex, no cache
