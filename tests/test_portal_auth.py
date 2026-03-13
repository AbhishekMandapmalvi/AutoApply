"""Unit tests for core.portal_auth and bot.state login gate.

Tests: FR-086 (credential vault), FR-087 (login detection),
       FR-088 (auto-login), FR-089 (browser handoff login gate).
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

from bot.state import BotState
from core.portal_auth import PortalAuthManager

# ---------------------------------------------------------------------------
# Domain extraction (FR-086)
# ---------------------------------------------------------------------------


class TestExtractDomain:
    def test_workday_subdomain(self):
        url = "https://adobe.myworkdayjobs.com/en-us/job/12345"
        assert PortalAuthManager.extract_domain(url) == "adobe.myworkdayjobs.com"

    def test_greenhouse_shared_domain(self):
        url = "https://boards.greenhouse.io/stripe/jobs/12345"
        assert PortalAuthManager.extract_domain(url) == "boards.greenhouse.io/stripe"

    def test_lever_shared_domain(self):
        url = "https://jobs.lever.co/openai/abc-123"
        assert PortalAuthManager.extract_domain(url) == "jobs.lever.co/openai"

    def test_ashby_shared_domain(self):
        url = "https://jobs.ashbyhq.com/ramp/def-456"
        assert PortalAuthManager.extract_domain(url) == "jobs.ashbyhq.com/ramp"

    def test_custom_career_site(self):
        url = "https://careers.google.com/apply?id=123"
        assert PortalAuthManager.extract_domain(url) == "careers.google.com"

    def test_greenhouse_no_path(self):
        url = "https://boards.greenhouse.io/"
        # No company path segment, falls back to hostname
        assert PortalAuthManager.extract_domain(url) == "boards.greenhouse.io"

    def test_empty_url(self):
        assert PortalAuthManager.extract_domain("") == ""

    def test_case_insensitive(self):
        url = "https://BOARDS.GREENHOUSE.IO/Stripe/jobs/123"
        assert PortalAuthManager.extract_domain(url) == "boards.greenhouse.io/stripe"


# ---------------------------------------------------------------------------
# Login detection (FR-087)
# ---------------------------------------------------------------------------


class TestDetectLoginWall:
    def test_url_with_login_path(self):
        page = MagicMock()
        page.url = "https://example.com/login?next=/apply"
        result = PortalAuthManager.detect_login_wall(page)
        assert result is True

    def test_url_with_signin_path(self):
        page = MagicMock()
        page.url = "https://example.com/signin"
        result = PortalAuthManager.detect_login_wall(page)
        assert result is True

    def test_url_with_sso_path(self):
        page = MagicMock()
        page.url = "https://example.com/sso/callback"
        result = PortalAuthManager.detect_login_wall(page)
        assert result is True

    def test_url_with_auth_path(self):
        page = MagicMock()
        page.url = "https://example.com/auth/login"
        result = PortalAuthManager.detect_login_wall(page)
        assert result is True

    def test_no_login_url_checks_dom(self):
        page = MagicMock()
        page.url = "https://example.com/jobs/apply"
        page.query_selector.return_value = None
        result = PortalAuthManager.detect_login_wall(page)
        assert result is False

    def test_dom_password_field_detected(self):
        page = MagicMock()
        page.url = "https://example.com/apply"
        # First call (password field) returns a mock element
        pw_el = MagicMock()
        page.query_selector.side_effect = [pw_el, None, None, None, None]
        result = PortalAuthManager.detect_login_wall(page)
        assert result is True

    def test_dom_workday_signin(self):
        page = MagicMock()
        page.url = "https://company.myworkdayjobs.com/apply"
        # First 3 selectors return None, Workday selector returns element
        page.query_selector.side_effect = [None, None, None, MagicMock(), None]
        result = PortalAuthManager.detect_login_wall(page)
        assert result is True

    def test_url_error_handled_gracefully(self):
        page = MagicMock()
        page.url = None  # Will cause urlparse to fail
        page.query_selector.return_value = None
        # Should not crash
        result = PortalAuthManager.detect_login_wall(page)
        assert result is False


# ---------------------------------------------------------------------------
# Credential vault (FR-086)
# ---------------------------------------------------------------------------


class TestCredentialVault:
    def test_store_and_retrieve_db_fallback(self, tmp_path):
        """Store credential without keyring — password goes to DB."""
        from db.database import Database

        db = Database(tmp_path / "test.db")
        auth = PortalAuthManager(db)

        with patch("core.portal_auth._check_keyring", return_value=False):
            cred_id = auth.store_credential(
                domain="example.com",
                username="user@test.com",
                password="secret123",
                portal_type="generic",
            )

        assert cred_id is not None
        assert cred_id > 0

        cred = auth.get_credential("example.com")
        assert cred is not None
        assert cred == ("user@test.com", "secret123")

    def test_get_credential_not_found(self, tmp_path):
        from db.database import Database

        db = Database(tmp_path / "test.db")
        auth = PortalAuthManager(db)

        result = auth.get_credential("nonexistent.com")
        assert result is None

    def test_delete_credential(self, tmp_path):
        from db.database import Database

        db = Database(tmp_path / "test.db")
        auth = PortalAuthManager(db)

        with patch("core.portal_auth._check_keyring", return_value=False):
            auth.store_credential("example.com", "user", "pass")

        result = auth.delete_credential("example.com")
        assert result is True

        result = auth.delete_credential("nonexistent.com")
        assert result is False

    def test_list_credentials(self, tmp_path):
        from db.database import Database

        db = Database(tmp_path / "test.db")
        auth = PortalAuthManager(db)

        with patch("core.portal_auth._check_keyring", return_value=False):
            auth.store_credential("a.com", "user1", "pass1")
            auth.store_credential("b.com", "user2", "pass2")

        creds = auth.list_credentials()
        assert len(creds) == 2
        domains = [c["domain"] for c in creds]
        assert "a.com" in domains
        assert "b.com" in domains
        # Passwords should NOT be in the list
        for c in creds:
            assert "password_hash" not in c

    def test_store_with_keyring(self, tmp_path):
        """Store credential with keyring — password goes to OS keyring."""
        from db.database import Database

        db = Database(tmp_path / "test.db")
        auth = PortalAuthManager(db)

        mock_keyring = MagicMock()
        with (
            patch("core.portal_auth._check_keyring", return_value=True),
            patch("core.portal_auth.keyring", mock_keyring, create=True),
            patch.dict("sys.modules", {"keyring": mock_keyring}),
        ):
            # Store — password should go to keyring
            auth.store_credential("example.com", "user", "secret")
            mock_keyring.set_password.assert_called_once_with(
                "autoapply", "portal_example.com", "secret",
            )

    def test_upsert_credential(self, tmp_path):
        """Storing twice for the same domain updates the credential."""
        from db.database import Database

        db = Database(tmp_path / "test.db")
        auth = PortalAuthManager(db)

        with patch("core.portal_auth._check_keyring", return_value=False):
            auth.store_credential("example.com", "user1", "pass1")
            auth.store_credential("example.com", "user2", "pass2")

        cred = auth.get_credential("example.com")
        assert cred == ("user2", "pass2")


# ---------------------------------------------------------------------------
# Auto-login (FR-088)
# ---------------------------------------------------------------------------


class TestAutoLogin:
    def test_auto_login_no_credentials(self, tmp_path):
        from db.database import Database

        db = Database(tmp_path / "test.db")
        auth = PortalAuthManager(db)
        page = MagicMock()

        result = auth.try_auto_login(page, "example.com", "generic")
        assert result is False

    def test_generic_login_no_email_field(self, tmp_path):
        from db.database import Database

        db = Database(tmp_path / "test.db")
        auth = PortalAuthManager(db)

        with patch("core.portal_auth._check_keyring", return_value=False):
            auth.store_credential("example.com", "user", "pass")

        page = MagicMock()
        page.query_selector.return_value = None

        result = auth.try_auto_login(page, "example.com", "generic")
        assert result is False

    def test_workday_login_fallback_to_generic(self, tmp_path):
        """Workday login falls back to generic when data-automation selectors missing."""
        from db.database import Database

        db = Database(tmp_path / "test.db")
        auth = PortalAuthManager(db)

        with patch("core.portal_auth._check_keyring", return_value=False):
            auth.store_credential("company.wd5.myworkdayjobs.com", "u", "p")

        page = MagicMock()
        page.query_selector.return_value = None

        # All selectors return None — falls back to generic, which also fails
        result = auth.try_auto_login(page, "company.wd5.myworkdayjobs.com", "workday")
        assert result is False


# ---------------------------------------------------------------------------
# Login gate in BotState (FR-089)
# ---------------------------------------------------------------------------


class TestLoginGate:
    def test_begin_and_wait_for_login(self):
        state = BotState()
        state.start()

        state.begin_login_gate("example.com", "generic", "https://example.com/login")
        assert state.awaiting_login is True
        assert state.login_context is not None
        assert state.login_context["domain"] == "example.com"

        # Simulate user responding in another thread
        def respond():
            time.sleep(0.05)
            state.set_login_decision("done")

        t = threading.Thread(target=respond)
        t.start()

        decision = state.wait_for_login()
        assert decision == "done"
        assert state.awaiting_login is False
        t.join()

    def test_login_gate_skip(self):
        state = BotState()
        state.start()
        state.begin_login_gate("example.com", "generic", "https://example.com/login")

        def respond():
            time.sleep(0.05)
            state.set_login_decision("skip")

        t = threading.Thread(target=respond)
        t.start()

        decision = state.wait_for_login()
        assert decision == "skip"
        t.join()

    def test_login_gate_stop_unblocks(self):
        state = BotState()
        state.start()
        state.begin_login_gate("example.com", "generic", "https://example.com/login")

        def stop():
            time.sleep(0.05)
            state.stop()

        t = threading.Thread(target=stop)
        t.start()

        decision = state.wait_for_login()
        assert decision == "stop"
        t.join()

    def test_status_dict_includes_login(self):
        state = BotState()
        state.start()
        status = state.get_status_dict()
        assert status["awaiting_login"] is False
        assert status["login_context"] is None

        state.begin_login_gate("example.com", "generic", "https://example.com/login")
        status = state.get_status_dict()
        assert status["awaiting_login"] is True
        assert status["login_context"]["domain"] == "example.com"


# ---------------------------------------------------------------------------
# ApplyResult login_required fields
# ---------------------------------------------------------------------------


class TestApplyResultLoginFields:
    def test_login_required_defaults(self):
        from bot.apply.base import ApplyResult

        result = ApplyResult(success=False)
        assert result.login_required is False
        assert result.login_domain is None
        assert result.login_portal_type is None

    def test_login_required_set(self):
        from bot.apply.base import ApplyResult

        result = ApplyResult(
            success=False,
            login_required=True,
            login_domain="example.com",
            login_portal_type="workday",
        )
        assert result.login_required is True
        assert result.login_domain == "example.com"
        assert result.login_portal_type == "workday"


# ---------------------------------------------------------------------------
# DB portal_credentials CRUD
# ---------------------------------------------------------------------------


class TestDatabasePortalCredentials:
    def test_save_and_get(self, tmp_path):
        from db.database import Database

        db = Database(tmp_path / "test.db")
        cred_id = db.save_portal_credential(
            domain="test.com",
            portal_type="generic",
            username="user@test.com",
            password="pass123",
        )
        assert cred_id > 0

        cred = db.get_portal_credential_by_domain("test.com")
        assert cred is not None
        assert cred["username"] == "user@test.com"
        assert cred["password_hash"] == "pass123"
        assert cred["has_keyring_password"] is False

    def test_upsert(self, tmp_path):
        from db.database import Database

        db = Database(tmp_path / "test.db")
        db.save_portal_credential("test.com", "generic", "user1", "pass1")
        db.save_portal_credential("test.com", "generic", "user2", "pass2")

        cred = db.get_portal_credential_by_domain("test.com")
        assert cred["username"] == "user2"

    def test_delete(self, tmp_path):
        from db.database import Database

        db = Database(tmp_path / "test.db")
        db.save_portal_credential("test.com", "generic", "user", "pass")
        assert db.delete_portal_credential_by_domain("test.com") is True
        assert db.delete_portal_credential_by_domain("test.com") is False

    def test_list_all(self, tmp_path):
        from db.database import Database

        db = Database(tmp_path / "test.db")
        db.save_portal_credential("a.com", "generic", "u1", "p1")
        db.save_portal_credential("b.com", "workday", "u2", "p2")

        creds = db.get_all_portal_credentials()
        assert len(creds) == 2
        # Passwords are NOT in list view
        for c in creds:
            assert "password_hash" not in c

    def test_record_login_attempt(self, tmp_path):
        from db.database import Database

        db = Database(tmp_path / "test.db")
        db.save_portal_credential("test.com", "generic", "user", "pass")

        db.record_login_attempt("test.com", success=True)
        db.record_login_attempt("test.com", success=True)
        db.record_login_attempt("test.com", success=False)

        cred = db.get_portal_credential_by_domain("test.com")
        assert cred["login_success_count"] == 2
        assert cred["login_failure_count"] == 1
        assert cred["last_login_at"] is not None

    def test_get_nonexistent(self, tmp_path):
        from db.database import Database

        db = Database(tmp_path / "test.db")
        assert db.get_portal_credential_by_domain("nope.com") is None

    def test_keyring_flag(self, tmp_path):
        from db.database import Database

        db = Database(tmp_path / "test.db")
        db.save_portal_credential(
            "test.com", "generic", "user", "", has_keyring=True,
        )
        cred = db.get_portal_credential_by_domain("test.com")
        assert cred["has_keyring_password"] is True


# ---------------------------------------------------------------------------
# Detect portal type
# ---------------------------------------------------------------------------


class TestDetectPortalType:
    def test_workday(self):
        url = "https://company.myworkdayjobs.com/apply"
        assert PortalAuthManager.detect_portal_type(url) in ("workday", "generic")

    def test_generic_fallback(self):
        url = "https://unknown-careers.example.com/jobs"
        assert PortalAuthManager.detect_portal_type(url) == "generic"
