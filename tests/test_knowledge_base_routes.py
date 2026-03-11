"""Tests for routes/knowledge_base.py — TASK-030 M5.

Tests KB CRUD endpoints, upload, stats, documents list, and preview.
"""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from db.database import Database

# ---------------------------------------------------------------------------
# Fixtures
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


def _insert_kb_entry(db, text="Built APIs", category="experience",
                     subsection="TechCorp", tags=None):
    """Insert a KB entry and return its ID."""
    return db.save_kb_entry(
        category=category,
        text=text,
        subsection=subsection,
        job_types=None,
        tags=tags or json.dumps(["test"]),
        source_doc_id=None,
    )


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------


class TestKBStats:
    """Tests for GET /api/kb/stats."""

    def test_stats_empty(self, kb_client):
        client, _db, _tmp = kb_client
        resp = client.get("/api/kb/stats")
        assert resp.status_code == 200

    def test_stats_with_entries(self, kb_client):
        client, db, _tmp = kb_client
        _insert_kb_entry(db, "Exp 1", "experience")
        _insert_kb_entry(db, "Skill 1", "skill")
        resp = client.get("/api/kb/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# List entries
# ---------------------------------------------------------------------------


class TestKBList:
    """Tests for GET /api/kb."""

    def test_list_empty(self, kb_client):
        client, _db, _tmp = kb_client
        resp = client.get("/api/kb")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["entries"] == []
        assert data["count"] == 0

    def test_list_with_entries(self, kb_client):
        client, db, _tmp = kb_client
        _insert_kb_entry(db, "Built APIs", "experience")
        _insert_kb_entry(db, "Python, Flask", "skill")
        resp = client.get("/api/kb")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["count"] == 2

    def test_list_filter_by_category(self, kb_client):
        client, db, _tmp = kb_client
        _insert_kb_entry(db, "Built APIs", "experience")
        _insert_kb_entry(db, "Python", "skill")
        resp = client.get("/api/kb?category=experience")
        data = resp.get_json()
        assert data["count"] == 1
        assert data["entries"][0]["category"] == "experience"

    def test_list_with_limit(self, kb_client):
        client, db, _tmp = kb_client
        for i in range(5):
            _insert_kb_entry(db, f"Entry {i}", "experience")
        resp = client.get("/api/kb?limit=2")
        data = resp.get_json()
        assert len(data["entries"]) == 2


# ---------------------------------------------------------------------------
# Get single entry
# ---------------------------------------------------------------------------


class TestKBGetEntry:
    """Tests for GET /api/kb/<id>."""

    def test_get_existing(self, kb_client):
        client, db, _tmp = kb_client
        eid = _insert_kb_entry(db, "Built APIs", "experience")
        resp = client.get(f"/api/kb/{eid}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["text"] == "Built APIs"

    def test_get_not_found(self, kb_client):
        client, _db, _tmp = kb_client
        resp = client.get("/api/kb/99999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update entry
# ---------------------------------------------------------------------------


class TestKBUpdateEntry:
    """Tests for PUT /api/kb/<id>."""

    def test_update_text(self, kb_client):
        client, db, _tmp = kb_client
        eid = _insert_kb_entry(db, "Original text", "experience")
        resp = client.put(
            f"/api/kb/{eid}",
            json={"text": "Updated text"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_update_not_found(self, kb_client):
        client, _db, _tmp = kb_client
        resp = client.put("/api/kb/99999", json={"text": "Nope"})
        assert resp.status_code == 404

    def test_update_no_body(self, kb_client):
        client, _db, _tmp = kb_client
        resp = client.put("/api/kb/1")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Delete entry
# ---------------------------------------------------------------------------


class TestKBDeleteEntry:
    """Tests for DELETE /api/kb/<id>."""

    def test_delete_existing(self, kb_client):
        client, db, _tmp = kb_client
        eid = _insert_kb_entry(db, "To delete", "experience")
        resp = client.delete(f"/api/kb/{eid}")
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_delete_not_found(self, kb_client):
        client, _db, _tmp = kb_client
        resp = client.delete("/api/kb/99999")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Upload endpoint
# ---------------------------------------------------------------------------


class TestKBUpload:
    """Tests for POST /api/kb/upload."""

    def test_upload_no_file(self, kb_client):
        client, _db, _tmp = kb_client
        resp = client.post("/api/kb/upload")
        assert resp.status_code == 400

    def test_upload_unsupported_type(self, kb_client):
        client, _db, _tmp = kb_client
        data = {"file": (io.BytesIO(b"content"), "test.exe")}
        resp = client.post("/api/kb/upload", data=data, content_type="multipart/form-data")
        assert resp.status_code == 400

    def test_upload_success(self, kb_client):
        client, _db, tmp = kb_client
        with patch("core.knowledge_base.KnowledgeBase") as MockKB:
            mock_kb = MagicMock()
            mock_kb.process_upload.return_value = 5
            MockKB.return_value = mock_kb

            data = {"file": (io.BytesIO(b"Resume content here"), "resume.txt")}
            resp = client.post("/api/kb/upload", data=data, content_type="multipart/form-data")

        assert resp.status_code == 201
        rdata = resp.get_json()
        assert rdata["success"] is True
        assert rdata["entries_created"] == 5


# ---------------------------------------------------------------------------
# Documents list
# ---------------------------------------------------------------------------


class TestKBDocuments:
    """Tests for GET /api/kb/documents."""

    def test_documents_empty(self, kb_client):
        client, _db, _tmp = kb_client
        resp = client.get("/api/kb/documents")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["documents"] == []


# ---------------------------------------------------------------------------
# Preview endpoint
# ---------------------------------------------------------------------------


class TestKBPreview:
    """Tests for POST /api/kb/preview."""

    def test_preview_no_body(self, kb_client):
        client, _db, _tmp = kb_client
        resp = client.post("/api/kb/preview")
        assert resp.status_code == 400

    def test_preview_no_entries_or_jd(self, kb_client):
        client, _db, _tmp = kb_client
        resp = client.post("/api/kb/preview", json={"template": "classic"})
        assert resp.status_code == 400
