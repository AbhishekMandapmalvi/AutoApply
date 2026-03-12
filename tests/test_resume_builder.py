"""Tests for Resume Builder — presets CRUD + page estimation (TASK-030 M7).

Tests preset API endpoints and database methods.
"""

from __future__ import annotations

import json

import pytest

from db.database import Database

# ---------------------------------------------------------------------------
# Database preset tests
# ---------------------------------------------------------------------------


class TestPresetDB:
    """Tests for resume_presets DB methods."""

    def test_save_and_get_preset(self, tmp_path):
        db = Database(tmp_path / "test.db")
        pid = db.save_preset(name="Backend Resume", entry_ids="[1,5,12]", template="modern")
        assert pid > 0

        preset = db.get_preset(pid)
        assert preset is not None
        assert preset["name"] == "Backend Resume"
        assert preset["entry_ids"] == "[1,5,12]"
        assert preset["template"] == "modern"

    def test_list_presets(self, tmp_path):
        db = Database(tmp_path / "test.db")
        db.save_preset(name="Preset A", entry_ids="[1,2]")
        db.save_preset(name="Preset B", entry_ids="[3,4]")

        presets = db.get_presets()
        assert len(presets) == 2
        names = {p["name"] for p in presets}
        assert names == {"Preset A", "Preset B"}

    def test_update_preset(self, tmp_path):
        db = Database(tmp_path / "test.db")
        pid = db.save_preset(name="Old Name", entry_ids="[1]")

        updated = db.update_preset(pid, name="New Name", entry_ids="[1,2,3]", template="academic")
        assert updated is True

        preset = db.get_preset(pid)
        assert preset["name"] == "New Name"
        assert preset["entry_ids"] == "[1,2,3]"
        assert preset["template"] == "academic"
        assert preset["updated_at"] is not None

    def test_update_nonexistent_preset(self, tmp_path):
        db = Database(tmp_path / "test.db")
        updated = db.update_preset(9999, name="Nope")
        assert updated is False

    def test_delete_preset(self, tmp_path):
        db = Database(tmp_path / "test.db")
        pid = db.save_preset(name="To Delete", entry_ids="[1]")

        deleted = db.delete_preset(pid)
        assert deleted is True
        assert db.get_preset(pid) is None

    def test_delete_nonexistent_preset(self, tmp_path):
        db = Database(tmp_path / "test.db")
        deleted = db.delete_preset(9999)
        assert deleted is False

    def test_update_no_fields(self, tmp_path):
        db = Database(tmp_path / "test.db")
        pid = db.save_preset(name="Test", entry_ids="[1]")
        updated = db.update_preset(pid)
        assert updated is False


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def builder_client(tmp_path, monkeypatch):
    """Yield (test_client, db) with KB routes available."""
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
    return app.test_client(), test_db


class TestPresetsAPI:
    """Tests for preset CRUD endpoints."""

    def test_create_preset(self, builder_client):
        client, _db = builder_client
        resp = client.post("/api/kb/presets", json={
            "name": "My Backend Resume",
            "entry_ids": [1, 5, 12],
            "template": "modern",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "My Backend Resume"
        assert data["template"] == "modern"

    def test_create_preset_missing_name(self, builder_client):
        client, _db = builder_client
        resp = client.post("/api/kb/presets", json={"entry_ids": [1]})
        assert resp.status_code == 400

    def test_create_preset_invalid_ids(self, builder_client):
        client, _db = builder_client
        resp = client.post("/api/kb/presets", json={
            "name": "Bad", "entry_ids": "not_a_list",
        })
        assert resp.status_code == 400

    def test_list_presets(self, builder_client):
        client, db = builder_client
        db.save_preset("P1", "[1,2]")
        db.save_preset("P2", "[3,4]")

        resp = client.get("/api/kb/presets")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["presets"]) == 2

    def test_update_preset(self, builder_client):
        client, db = builder_client
        pid = db.save_preset("Old", "[1]")

        resp = client.put(f"/api/kb/presets/{pid}", json={"name": "New"})
        assert resp.status_code == 200

        preset = db.get_preset(pid)
        assert preset["name"] == "New"

    def test_update_nonexistent_preset(self, builder_client):
        client, _db = builder_client
        resp = client.put("/api/kb/presets/9999", json={"name": "Nope"})
        assert resp.status_code == 404

    def test_delete_preset(self, builder_client):
        client, db = builder_client
        pid = db.save_preset("Del", "[1]")

        resp = client.delete(f"/api/kb/presets/{pid}")
        assert resp.status_code == 200
        assert db.get_preset(pid) is None

    def test_delete_nonexistent_preset(self, builder_client):
        client, _db = builder_client
        resp = client.delete("/api/kb/presets/9999")
        assert resp.status_code == 404
