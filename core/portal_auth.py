"""Portal authentication manager — credential vault, login detection, auto-login.

Implements: FR-086 (portal credential vault), FR-087 (login detection),
            FR-088 (auto-login), FR-089 (browser handoff).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from db.database import Database

logger = logging.getLogger(__name__)

# Reuse the keyring helpers from config.settings
KEYRING_SERVICE = "autoapply"
KEYRING_PREFIX = "portal_"

# Login-related URL path segments
_LOGIN_PATH_SEGMENTS = {
    "login", "signin", "sign-in", "sign_in", "auth", "sso",
    "account/login", "account/signin", "authenticate",
}

# Shared-domain ATS portals where company is a path segment
_SHARED_DOMAIN_ATS = {
    "boards.greenhouse.io",
    "jobs.lever.co",
    "jobs.ashbyhq.com",
}


def _check_keyring() -> bool:
    """Return True if OS keyring is usable (cached)."""
    from config.settings import _check_keyring as _ck
    return _ck()


class PortalAuthManager:
    """Manages portal credentials, login detection, and auto-login."""

    def __init__(self, db: "Database") -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Domain extraction
    # ------------------------------------------------------------------

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract the company-specific domain key from a job URL.

        Examples:
            https://adobe.myworkdayjobs.com/... → adobe.myworkdayjobs.com
            https://boards.greenhouse.io/stripe/... → boards.greenhouse.io/stripe
            https://jobs.lever.co/openai/... → jobs.lever.co/openai
            https://careers.google.com/apply → careers.google.com
        """
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        path_parts = [p for p in parsed.path.split("/") if p]

        # Shared-domain portals: company is the first path segment
        if hostname in _SHARED_DOMAIN_ATS and path_parts:
            return f"{hostname}/{path_parts[0].lower()}"

        # Everything else (Workday subdomains, custom career sites): hostname
        return hostname

    @staticmethod
    def detect_portal_type(url: str) -> str:
        """Detect ATS type from URL, falling back to 'generic'."""
        from core.filter import detect_ats
        return detect_ats(url) or "generic"

    # ------------------------------------------------------------------
    # Credential CRUD (wraps DB + keyring)
    # ------------------------------------------------------------------

    def store_credential(
        self, domain: str, username: str, password: str,
        portal_type: str = "generic", notes: str | None = None,
    ) -> int:
        """Store a portal credential. Returns the credential ID."""
        use_keyring = _check_keyring()

        cred_id = self.db.save_portal_credential(
            domain=domain,
            portal_type=portal_type,
            username=username,
            password="" if use_keyring else password,
            has_keyring=use_keyring,
            notes=notes,
        )

        if use_keyring:
            import keyring
            keyring.set_password(KEYRING_SERVICE, f"{KEYRING_PREFIX}{domain}", password)
            logger.info("Portal credential for %s stored in OS keyring", domain)
        else:
            logger.warning("Keyring unavailable — portal password for %s stored in database", domain)

        return cred_id

    def get_credential(self, domain: str) -> tuple[str, str] | None:
        """Get (username, password) for a domain, or None if not found."""
        cred = self.db.get_portal_credential_by_domain(domain)
        if not cred:
            return None

        username = cred["username"]

        if cred["has_keyring_password"] and _check_keyring():
            import keyring
            password = keyring.get_password(KEYRING_SERVICE, f"{KEYRING_PREFIX}{domain}")
            if password:
                return username, password

        # Fallback to DB-stored password
        password = cred.get("password_hash", "")
        if password:
            return username, password

        return None

    def delete_credential(self, domain: str) -> bool:
        """Delete a credential from vault and keyring."""
        if _check_keyring():
            try:
                import keyring
                keyring.delete_password(KEYRING_SERVICE, f"{KEYRING_PREFIX}{domain}")
            except Exception:
                pass  # May not exist in keyring

        return self.db.delete_portal_credential_by_domain(domain)

    def list_credentials(self) -> list[dict]:
        """List all credentials (passwords masked)."""
        return self.db.get_all_portal_credentials()

    # ------------------------------------------------------------------
    # Login detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_login_wall(page) -> bool:
        """Check if the current page is a login/signup wall.

        Uses URL patterns first (fast), then DOM inspection (slower).
        """
        # Tier 1: URL-based detection
        try:
            current_url = page.url.lower()
            parsed = urlparse(current_url)
            path = parsed.path

            for segment in _LOGIN_PATH_SEGMENTS:
                if segment in path:
                    return True
        except Exception:
            pass

        # Tier 2: DOM-based detection
        login_selectors = [
            'input[type="password"]:visible',
            'form[action*="login"]',
            'form[action*="signin"]',
            '[data-automation-id="signIn-email"]',  # Workday
            '[data-automation-id="createAccountLink"]',  # Workday
        ]
        for selector in login_selectors:
            try:
                el = page.query_selector(selector)
                if el:
                    return True
            except Exception:
                continue

        return False

    # ------------------------------------------------------------------
    # Auto-login
    # ------------------------------------------------------------------

    def try_auto_login(self, page, domain: str, portal_type: str) -> bool:
        """Attempt to log in using stored credentials.

        Returns True if login succeeded (navigated past login wall).
        """
        cred = self.get_credential(domain)
        if not cred:
            logger.debug("No credentials stored for %s", domain)
            return False

        username, password = cred
        logger.info("Attempting auto-login at %s with stored credentials", domain)

        success = False
        if portal_type == "workday":
            success = self._login_workday(page, username, password)
        else:
            success = self._login_generic(page, username, password)

        # Record the attempt
        self.db.record_login_attempt(domain, success)

        if success:
            logger.info("Auto-login succeeded at %s", domain)
        else:
            logger.warning("Auto-login failed at %s", domain)

        return success

    def _login_generic(self, page, username: str, password: str) -> bool:
        """Generic login: find email/username + password fields, fill, submit."""
        import random
        import time

        # Find email/username field
        email_selectors = [
            'input[type="email"]',
            'input[name="email"]',
            'input[name="username"]',
            'input[id*="email"]',
            'input[id*="user"]',
            'input[autocomplete="email"]',
            'input[autocomplete="username"]',
        ]
        email_input = None
        for sel in email_selectors:
            el = page.query_selector(sel)
            if el and el.is_visible():
                email_input = el
                break

        if not email_input:
            logger.debug("No email/username input found for generic login")
            return False

        # Find password field
        pw_input = page.query_selector('input[type="password"]:visible')
        if not pw_input:
            logger.debug("No password input found for generic login")
            return False

        # Fill fields with human-like typing
        email_input.fill("")
        for char in username:
            email_input.type(char)
            time.sleep(random.uniform(0.03, 0.08))
        time.sleep(random.uniform(0.3, 0.8))

        pw_input.fill("")
        for char in password:
            pw_input.type(char)
            time.sleep(random.uniform(0.03, 0.08))
        time.sleep(random.uniform(0.3, 0.8))

        # Click submit
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Sign In")',
            'button:has-text("Log In")',
            'button:has-text("Sign in")',
            'button:has-text("Log in")',
        ]
        for sel in submit_selectors:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                break

        time.sleep(random.uniform(2, 4))

        # Check if we're still on a login page
        return not self.detect_login_wall(page)

    def _login_workday(self, page, username: str, password: str) -> bool:
        """Workday-specific login using data-automation-id selectors."""
        import random
        import time

        # Email field
        email_input = page.query_selector(
            '[data-automation-id="email"], '
            '[data-automation-id="signIn-email"]'
        )
        if not email_input:
            return self._login_generic(page, username, password)

        email_input.fill("")
        for char in username:
            email_input.type(char)
            time.sleep(random.uniform(0.03, 0.08))
        time.sleep(random.uniform(0.5, 1))

        # Password field
        pw_input = page.query_selector(
            '[data-automation-id="password"], '
            '[data-automation-id="signIn-password"]'
        )
        if pw_input:
            pw_input.fill("")
            for char in password:
                pw_input.type(char)
                time.sleep(random.uniform(0.03, 0.08))
            time.sleep(random.uniform(0.5, 1))

        # Submit
        signin_btn = page.query_selector(
            '[data-automation-id="signInSubmitButton"], '
            '[data-automation-id="createAccountSubmitButton"]'
        )
        if signin_btn and signin_btn.is_visible():
            signin_btn.click()
            time.sleep(random.uniform(2, 4))

        return not self.detect_login_wall(page)
