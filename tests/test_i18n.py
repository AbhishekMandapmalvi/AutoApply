"""Unit tests for internationalization (LE-3).

Tests cover: core/i18n.py backend translation, locale loading,
static/locales/en.json structure, and API endpoint.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ===================================================================
# LE-3-01 — en.json Locale File
# ===================================================================


class TestLocaleFile:
    """LE-3: English locale file exists and is valid JSON."""

    def test_en_json_exists(self):
        """en.json exists in static/locales/.  # AC-LE3.1"""
        path = Path("static/locales/en.json")
        assert path.exists(), "static/locales/en.json not found"

    def test_en_json_valid(self):
        """en.json is valid JSON.  # AC-LE3.2"""
        path = Path("static/locales/en.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_en_json_has_required_sections(self):
        """en.json has all required top-level sections.  # AC-LE3.3"""
        path = Path("static/locales/en.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        required = [
            "app", "nav", "wizard", "form", "placeholder", "button",
            "bot", "ai", "applications", "profile", "settings",
            "login", "review", "feed", "analytics", "status",
            "schedule", "experience_levels", "errors",
        ]
        for section in required:
            assert section in data, f"Missing section: {section}"

    def test_en_json_error_keys_present(self):
        """en.json errors section has all backend error keys.  # AC-LE3.4"""
        path = Path("static/locales/en.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        errors = data["errors"]
        required_keys = [
            "unauthorized", "too_many_requests", "internal_error",
            "bad_request", "not_found", "method_not_allowed",
            "request_too_large", "forbidden", "application_not_found",
            "request_body_required", "request_body_json",
            "invalid_status", "resume_not_found", "description_not_found",
            "bot_already_running", "config_not_found", "no_review_pending",
            "cover_letter_required", "invalid_days", "invalid_time_format",
            "url_required", "invalid_url", "unsupported_login_url",
            "chrome_not_found", "chrome_failed", "provider_key_required",
            "unsupported_provider", "invalid_config",
            "filename_content_required", "filename_required",
            "invalid_filename", "invalid_filename_detail",
            "content_required", "file_not_found",
        ]
        for key in required_keys:
            assert key in errors, f"Missing error key: {key}"


# ===================================================================
# LE-3-02 — Backend i18n Module
# ===================================================================


class TestBackendI18n:
    """LE-3: core/i18n.py translation functions."""

    def test_t_returns_string(self):
        """t() returns translated string for valid key.  # AC-LE3.5"""
        from core.i18n import t
        result = t("errors.unauthorized")
        assert result == "Unauthorized"

    def test_t_nested_key(self):
        """t() resolves nested dot-notation keys.  # AC-LE3.6"""
        from core.i18n import t
        assert t("bot.running") == "Running"
        assert t("wizard.back") == "Back"

    def test_t_interpolation(self):
        """t() interpolates {placeholder} values.  # AC-LE3.7"""
        from core.i18n import t
        result = t("errors.invalid_status", valid_statuses="a, b, c")
        assert "a, b, c" in result
        assert "{valid_statuses}" not in result

    def test_t_missing_key_returns_key(self):
        """t() returns the key itself if translation not found.  # AC-LE3.8"""
        from core.i18n import t
        assert t("nonexistent.key.path") == "nonexistent.key.path"

    def test_t_missing_interpolation_kept(self):
        """t() keeps {placeholder} if param not provided.  # AC-LE3.9"""
        from core.i18n import t
        result = t("errors.chrome_failed")
        assert "{error}" in result

    def test_get_locale_returns_en(self):
        """get_locale() returns 'en' by default.  # AC-LE3.10"""
        from core.i18n import get_locale
        assert get_locale() == "en"

    def test_get_available_locales(self):
        """get_available_locales() includes 'en'.  # AC-LE3.11"""
        from core.i18n import get_available_locales
        locales = get_available_locales()
        assert "en" in locales

    def test_set_locale_fallback(self):
        """set_locale() falls back to 'en' for unknown locale.  # AC-LE3.12"""
        from core.i18n import get_locale, set_locale
        set_locale("xx_nonexistent")
        assert get_locale() == "en"
        # Verify translations still work
        from core.i18n import t
        assert t("errors.unauthorized") == "Unauthorized"


# ===================================================================
# LE-3-03 — API Endpoint
# ===================================================================


class TestLocalesAPI:
    """LE-3: /api/locales endpoint."""

    @pytest.fixture()
    def client(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr("routes.profile.get_data_dir", lambda: tmp_path)
        (tmp_path / "profile" / "experiences").mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("AUTOAPPLY_DEV", "1")
        from app import create_app
        app, _ = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_locales_endpoint(self, client):
        """GET /api/locales returns current and available locales.  # AC-LE3.13"""
        rv = client.get("/api/locales")
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["current"] == "en"
        assert "en" in data["available"]


# ===================================================================
# LE-3-04 — Backend Routes Use t()
# ===================================================================


class TestRoutesUseI18n:
    """LE-3: Backend routes return translated error messages."""

    @pytest.fixture()
    def client(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr("routes.profile.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr("routes.login.get_data_dir", lambda: tmp_path)
        (tmp_path / "profile" / "experiences").mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("AUTOAPPLY_DEV", "1")
        from app import create_app
        app, _ = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_404_uses_translated_string(self, client):
        """404 error returns translated 'Not found'.  # AC-LE3.14"""
        rv = client.get("/api/nonexistent")
        assert rv.status_code == 404
        data = rv.get_json()
        assert data["error"] == "Not found"

    def test_application_not_found_translated(self, client):
        """GET /api/applications/999 returns translated error.  # AC-LE3.15"""
        rv = client.get("/api/applications/999")
        assert rv.status_code == 404
        data = rv.get_json()
        assert data["error"] == "Application not found"

    def test_bot_config_not_found_translated(self, client):
        """POST /api/bot/start with no config returns translated error.  # AC-LE3.16"""
        rv = client.post("/api/bot/start")
        data = rv.get_json()
        assert data["error"] == "Configuration not found. Complete setup first."

    def test_invalid_json_config_translated(self, client):
        """PUT /api/config with null JSON returns translated error.  # AC-LE3.17"""
        rv = client.put(
            "/api/config",
            data="null",
            content_type="application/json",
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["error"] == "Request body must be valid JSON"

    def test_filename_validation_translated(self, client):
        """POST experience with invalid filename returns translated error.  # AC-LE3.18"""
        rv = client.post(
            "/api/profile/experiences",
            json={"filename": "../evil.txt", "content": "test"},
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["error"] == "Invalid filename"


# ===================================================================
# LE-3-05 — Frontend i18n Module
# ===================================================================


class TestFrontendI18nModule:
    """LE-3: static/js/i18n.js module exists with required exports."""

    def test_i18n_js_exists(self):
        """i18n.js exists in static/js/.  # AC-LE3.19"""
        assert Path("static/js/i18n.js").exists()

    def test_i18n_js_exports(self):
        """i18n.js exports t, getLocale, setLocale, onReady.  # AC-LE3.20"""
        content = Path("static/js/i18n.js").read_text(encoding="utf-8")
        assert "export function t(" in content
        assert "export function getLocale(" in content
        assert "export async function setLocale(" in content
        assert "export function onReady(" in content

    def test_app_js_imports_i18n(self):
        """app.js imports from i18n.js.  # AC-LE3.21"""
        content = Path("static/js/app.js").read_text(encoding="utf-8")
        assert "from './i18n.js'" in content
        assert "window.t = t" in content


# ===================================================================
# TASK-022 — Locale Switcher UI
# ===================================================================


class TestSetLocaleEndpoint:
    """TASK-022: PUT /api/locale endpoint (FR-133)."""

    @pytest.fixture()
    def client(self, tmp_path, monkeypatch):
        monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr("routes.profile.get_data_dir", lambda: tmp_path)
        (tmp_path / "profile" / "experiences").mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("AUTOAPPLY_DEV", "1")
        from app import create_app
        app, _ = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_set_locale_valid(self, client):
        """PUT /api/locale with valid locale returns 200.  # AC-133-1"""
        rv = client.put(
            "/api/locale",
            json={"locale": "en"},
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["locale"] == "en"

    def test_set_locale_invalid(self, client):
        """PUT /api/locale with invalid locale returns 400.  # AC-133-2"""
        rv = client.put(
            "/api/locale",
            json={"locale": "xx_invalid"},
        )
        assert rv.status_code == 400

    def test_set_locale_empty_body(self, client):
        """PUT /api/locale with no locale field returns 400."""
        rv = client.put(
            "/api/locale",
            json={},
        )
        assert rv.status_code == 400

    def test_set_locale_no_json(self, client):
        """PUT /api/locale with no JSON body returns 400."""
        rv = client.put("/api/locale")
        assert rv.status_code == 400

    def test_set_locale_changes_backend(self, client):
        """PUT /api/locale updates backend locale returned by GET /api/locales."""
        client.put("/api/locale", json={"locale": "en"})
        rv = client.get("/api/locales")
        data = rv.get_json()
        assert data["current"] == "en"


class TestLocaleSwitcherFrontend:
    """TASK-022: Frontend locale switcher code (FR-131, FR-132, FR-134)."""

    def test_i18n_js_has_localstorage(self):
        """i18n.js uses localStorage for persistence.  # AC-132-1"""
        content = Path("static/js/i18n.js").read_text(encoding="utf-8")
        assert "localStorage.getItem('autoapply_locale')" in content
        assert "localStorage.setItem('autoapply_locale'" in content

    def test_i18n_js_syncs_backend(self):
        """i18n.js calls PUT /api/locale for backend sync.  # AC-133-1"""
        content = Path("static/js/i18n.js").read_text(encoding="utf-8")
        assert "/api/locale" in content
        assert "PUT" in content

    def test_settings_js_has_locale_names(self):
        """settings.js has LOCALE_NAMES map.  # AC-134-1"""
        content = Path("static/js/settings.js").read_text(encoding="utf-8")
        assert "LOCALE_NAMES" in content
        assert "'English'" in content
        assert "'Español'" in content

    def test_settings_js_exports_onLocaleChange(self):
        """settings.js exports onLocaleChange.  # FR-131"""
        content = Path("static/js/settings.js").read_text(encoding="utf-8")
        assert "export async function onLocaleChange" in content

    def test_app_js_exports_onLocaleChange(self):
        """app.js exports onLocaleChange to window.  # FR-131"""
        content = Path("static/js/app.js").read_text(encoding="utf-8")
        assert "window.onLocaleChange = onLocaleChange" in content

    def test_html_has_locale_dropdown(self):
        """index.html has locale select dropdown.  # AC-131-1"""
        content = Path("templates/index.html").read_text(encoding="utf-8")
        assert 'id="set-locale"' in content
        assert 'onchange="onLocaleChange()"' in content

    def test_en_json_has_language_keys(self):
        """en.json has settings.section_language and settings.label_language."""
        data = json.loads(Path("static/locales/en.json").read_text(encoding="utf-8"))
        assert data["settings"]["section_language"] == "Language"
        assert data["settings"]["label_language"] == "Language"


# ===================================================================
# TASK-023 — Sample Spanish Translation (QOL-4)
# ===================================================================


class TestSpanishTranslation:
    """TASK-023: es.json locale file (FR-135, FR-136)."""

    def test_es_json_exists(self):
        """es.json exists in static/locales/.  # FR-135"""
        assert Path("static/locales/es.json").exists()

    def test_es_json_valid(self):
        """es.json is valid JSON."""
        data = json.loads(Path("static/locales/es.json").read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_es_json_key_parity(self):
        """es.json has all the same keys as en.json.  # NFR-023-02"""
        en = json.loads(Path("static/locales/en.json").read_text(encoding="utf-8"))
        es = json.loads(Path("static/locales/es.json").read_text(encoding="utf-8"))

        def _get_keys(d, prefix=""):
            keys = set()
            for k, v in d.items():
                full = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    keys |= _get_keys(v, full)
                else:
                    keys.add(full)
            return keys

        en_keys = _get_keys(en)
        es_keys = _get_keys(es)
        missing = en_keys - es_keys
        assert not missing, f"Keys in en.json missing from es.json: {missing}"

    def test_es_json_no_extra_keys(self):
        """es.json has no keys that don't exist in en.json."""
        en = json.loads(Path("static/locales/en.json").read_text(encoding="utf-8"))
        es = json.loads(Path("static/locales/es.json").read_text(encoding="utf-8"))

        def _get_keys(d, prefix=""):
            keys = set()
            for k, v in d.items():
                full = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    keys |= _get_keys(v, full)
                else:
                    keys.add(full)
            return keys

        en_keys = _get_keys(en)
        es_keys = _get_keys(es)
        extra = es_keys - en_keys
        assert not extra, f"Keys in es.json not in en.json: {extra}"

    def test_es_json_no_untranslated(self):
        """es.json values differ from en.json (spot check key sections)."""
        en = json.loads(Path("static/locales/en.json").read_text(encoding="utf-8"))
        es = json.loads(Path("static/locales/es.json").read_text(encoding="utf-8"))
        # Check that major sections are translated (not just copied)
        assert es["nav"]["dashboard"] != en["nav"]["dashboard"]
        assert es["button"]["save"] != en["button"]["save"]
        assert es["settings"]["screen_title"] != en["settings"]["screen_title"]
        assert es["errors"]["unauthorized"] != en["errors"]["unauthorized"]

    def test_es_json_preserves_placeholders(self):
        """es.json preserves {placeholder} tokens for interpolation."""
        es = json.loads(Path("static/locales/es.json").read_text(encoding="utf-8"))
        assert "{valid_statuses}" in es["errors"]["invalid_status"]
        assert "{days}" in es["errors"]["invalid_days"]
        assert "{error}" in es["errors"]["chrome_failed"]
        assert "{count}" in es["analytics"]["score_tooltip_interviews"]
        assert "{rate}" in es["analytics"]["score_tooltip_interviews"]
        assert "{days}" in es["analytics"]["response_days"]

    def test_locales_api_includes_es(self, tmp_path, monkeypatch):
        """GET /api/locales includes 'es' in available.  # FR-136"""
        monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr("routes.profile.get_data_dir", lambda: tmp_path)
        (tmp_path / "profile" / "experiences").mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("AUTOAPPLY_DEV", "1")
        from app import create_app
        app, _ = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            rv = c.get("/api/locales")
            data = rv.get_json()
            assert "es" in data["available"]

    def test_set_locale_to_es(self, tmp_path, monkeypatch):
        """PUT /api/locale with 'es' succeeds."""
        monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
        monkeypatch.setattr("routes.profile.get_data_dir", lambda: tmp_path)
        (tmp_path / "profile" / "experiences").mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("AUTOAPPLY_DEV", "1")
        from app import create_app
        app, _ = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            rv = c.put("/api/locale", json={"locale": "es"})
            assert rv.status_code == 200
            assert rv.get_json()["locale"] == "es"
