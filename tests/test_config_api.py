"""Tests for default resume API, BotConfig/LatexConfig defaults, and generate_documents skip_cover_letter.

Covers:
  - FR-XXX: Default resume upload/get/delete endpoints
  - BotConfig.cover_letter_enabled default and toggle
  - LatexConfig.template default
  - generate_documents skip_cover_letter parameter
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from config.settings import BotConfig, LatexConfig
from db.database import Database

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config_payload() -> dict:
    """Return a minimal valid AppConfig payload."""
    return {
        "profile": {
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "phone": "555-0100",
            "city": "NYC",
            "state": "NY",
            "bio": "A test user",
        },
        "search_criteria": {
            "job_titles": ["Engineer"],
            "locations": ["NYC"],
        },
        "bot": {},
    }


def _write_config(tmp_path: Path, extra: dict | None = None) -> None:
    """Write a minimal config.json to tmp_path, optionally merging extra keys."""
    payload = _make_config_payload()
    if extra:
        for key, value in extra.items():
            if key in payload and isinstance(payload[key], dict) and isinstance(value, dict):
                payload[key].update(value)
            else:
                payload[key] = value
    (tmp_path / "config.json").write_text(json.dumps(payload), encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    """Yield (test_client, tmp_path) with all paths redirected to tmp_path."""
    monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("app.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("routes.config.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("routes.profile.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("routes.applications.get_data_dir", lambda: tmp_path)

    # Create required directory structure
    (tmp_path / "profile" / "experiences").mkdir(parents=True)

    # Write a minimal config
    _write_config(tmp_path)

    # Re-initialise database in the tmp location
    test_db = Database(tmp_path / "test.db")
    monkeypatch.setattr("app.db", test_db)
    monkeypatch.setattr("app_state.db", test_db)

    from app import app

    app.config["TESTING"] = True
    return app.test_client(), tmp_path


# ---------------------------------------------------------------------------
# TestDefaultResumeAPI
# ---------------------------------------------------------------------------


class TestDefaultResumeAPI:
    """Tests for POST/GET/DELETE /api/config/default-resume."""

    def test_upload_default_resume_pdf(self, app_client):
        """POST a PDF file: 200, filename in response, file on disk, config updated."""
        client, tmp_path = app_client

        pdf_content = b"%PDF-1.4 fake pdf content for testing"
        data = {
            "file": (io.BytesIO(pdf_content), "my_resume.pdf"),
        }
        resp = client.post(
            "/api/config/default-resume",
            data=data,
            content_type="multipart/form-data",
        )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["filename"] == "my_resume.pdf"

        # File should exist on disk
        dest = tmp_path / "default_resume.pdf"
        assert dest.exists()
        assert dest.read_bytes() == pdf_content

        # Config should be updated with fallback_resume_path
        config_data = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert config_data["profile"]["fallback_resume_path"] == str(dest)

    def test_upload_default_resume_docx(self, app_client):
        """POST a DOCX file: 200, success."""
        client, tmp_path = app_client

        docx_content = b"PK\x03\x04 fake docx content"
        data = {
            "file": (io.BytesIO(docx_content), "resume.docx"),
        }
        resp = client.post(
            "/api/config/default-resume",
            data=data,
            content_type="multipart/form-data",
        )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["filename"] == "resume.docx"

        dest = tmp_path / "default_resume.docx"
        assert dest.exists()

    def test_upload_rejects_unsupported_type(self, app_client):
        """POST a .txt file: 400, unsupported format."""
        client, _ = app_client

        data = {
            "file": (io.BytesIO(b"plain text"), "resume.txt"),
        }
        resp = client.post(
            "/api/config/default-resume",
            data=data,
            content_type="multipart/form-data",
        )

        assert resp.status_code == 400
        body = resp.get_json()
        assert "Unsupported" in body["error"]

    def test_upload_rejects_oversized_file(self, app_client):
        """POST a 6 MB file: 400, file too large."""
        client, _ = app_client

        # 6 MB exceeds the 5 MB limit
        big_content = b"\x00" * (6 * 1024 * 1024)
        data = {
            "file": (io.BytesIO(big_content), "huge_resume.pdf"),
        }
        resp = client.post(
            "/api/config/default-resume",
            data=data,
            content_type="multipart/form-data",
        )

        assert resp.status_code == 400
        body = resp.get_json()
        assert "too large" in body["error"].lower()

    def test_get_default_resume_none(self, app_client):
        """GET when no resume set: filename is null."""
        client, _ = app_client

        resp = client.get("/api/config/default-resume")

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["filename"] is None
        assert body["path"] is None

    def test_get_default_resume_exists(self, app_client):
        """Upload then GET: filename returned."""
        client, tmp_path = app_client

        # Upload first
        data = {
            "file": (io.BytesIO(b"%PDF-1.4 content"), "uploaded.pdf"),
        }
        upload_resp = client.post(
            "/api/config/default-resume",
            data=data,
            content_type="multipart/form-data",
        )
        assert upload_resp.status_code == 200

        # Now GET
        resp = client.get("/api/config/default-resume")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["filename"] == "default_resume.pdf"
        assert body["path"] is not None

    def test_delete_default_resume(self, app_client):
        """Upload then DELETE: file removed and config cleared."""
        client, tmp_path = app_client

        # Upload first
        data = {
            "file": (io.BytesIO(b"%PDF-1.4 content"), "to_delete.pdf"),
        }
        upload_resp = client.post(
            "/api/config/default-resume",
            data=data,
            content_type="multipart/form-data",
        )
        assert upload_resp.status_code == 200
        dest = tmp_path / "default_resume.pdf"
        assert dest.exists()

        # Delete
        resp = client.delete("/api/config/default-resume")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True

        # File should be gone
        assert not dest.exists()

        # Config should have fallback_resume_path cleared
        config_data = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert config_data["profile"].get("fallback_resume_path") is None

    def test_delete_default_resume_when_none(self, app_client):
        """DELETE when nothing set: 200, no error."""
        client, _ = app_client

        resp = client.delete("/api/config/default-resume")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True


# ---------------------------------------------------------------------------
# TestBotConfigFields
# ---------------------------------------------------------------------------


class TestBotConfigFields:
    """Tests for BotConfig and LatexConfig default values."""

    def test_cover_letter_enabled_default(self):
        """BotConfig().cover_letter_enabled defaults to True."""
        config = BotConfig()
        assert config.cover_letter_enabled is True

    def test_latex_config_template_default(self):
        """LatexConfig().template defaults to 'classic'."""
        config = LatexConfig()
        assert config.template == "classic"

    def test_cover_letter_enabled_toggle(self, app_client):
        """PUT /api/config with bot.cover_letter_enabled=false: persists."""
        client, tmp_path = app_client

        # Set cover_letter_enabled to false
        resp = client.put(
            "/api/config",
            data=json.dumps({"bot": {"cover_letter_enabled": False}}),
            content_type="application/json",
        )
        assert resp.status_code == 200

        # Verify it persisted
        config_data = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert config_data["bot"]["cover_letter_enabled"] is False

        # GET should also reflect the change
        resp = client.get("/api/config")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["bot"]["cover_letter_enabled"] is False


# ---------------------------------------------------------------------------
# TestGenerateDocumentsSkipCL
# ---------------------------------------------------------------------------


class TestGenerateDocumentsSkipCL:
    """Tests for generate_documents with skip_cover_letter=True."""

    @staticmethod
    def _make_job():
        """Create a mock job object."""
        job = MagicMock()
        job.id = "job-123"
        job.raw.company = "TestCorp"
        job.raw.description = "We need a Python developer."
        return job

    @staticmethod
    def _make_profile():
        """Create a mock profile object."""
        profile = MagicMock()
        profile.full_name = "Jane Doe"
        profile.email = "jane@example.com"
        profile.phone_full = "+1555-0100"
        profile.location = "NYC, NY"
        profile.linkedin_url = "https://linkedin.com/in/janedoe"
        profile.portfolio_url = None
        profile.bio = "Experienced engineer."
        return profile

    @staticmethod
    def _make_llm_config():
        """Create a mock LLM config."""
        cfg = MagicMock()
        cfg.provider = "anthropic"
        cfg.api_key = "test-key-123"
        cfg.model = "claude-sonnet-4-20250514"
        return cfg

    def test_skip_cover_letter_returns_none_cl_path(self, tmp_path):
        """With skip_cover_letter=True, cl_path should be None."""
        from core.ai_engine import generate_documents

        job = self._make_job()
        profile = self._make_profile()
        llm_config = self._make_llm_config()

        resumes_dir = tmp_path / "resumes"
        cl_dir = tmp_path / "cover_letters"

        with patch("core.ai_engine.invoke_llm", return_value="# Jane Doe\n## Experience\n- Built APIs"), \
             patch("core.resume_renderer.render_resume_to_pdf"):
            resume_path, cl_path, version_meta = generate_documents(
                job=job,
                profile=profile,
                experience_dir=tmp_path / "experiences",
                output_dir_resumes=resumes_dir,
                output_dir_cover_letters=cl_dir,
                llm_config=llm_config,
                skip_cover_letter=True,
            )

        assert resume_path is not None
        assert cl_path is None

    def test_skip_cover_letter_no_llm_call_for_cl(self, tmp_path):
        """With skip_cover_letter=True, invoke_llm should be called only once (for resume)."""
        from core.ai_engine import generate_documents

        job = self._make_job()
        profile = self._make_profile()
        llm_config = self._make_llm_config()

        resumes_dir = tmp_path / "resumes"
        cl_dir = tmp_path / "cover_letters"

        with patch("core.ai_engine.invoke_llm", return_value="# Jane Doe\n## Experience\n- Built APIs") as mock_llm, \
             patch("core.resume_renderer.render_resume_to_pdf"):
            generate_documents(
                job=job,
                profile=profile,
                experience_dir=tmp_path / "experiences",
                output_dir_resumes=resumes_dir,
                output_dir_cover_letters=cl_dir,
                llm_config=llm_config,
                skip_cover_letter=True,
            )

        # Only one call for resume, none for cover letter
        assert mock_llm.call_count == 1
