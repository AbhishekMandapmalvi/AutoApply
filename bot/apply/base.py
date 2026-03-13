"""Base classes for job application automation.

Implements: FR-046 (applier abstraction), FR-086 (portal auth integration).
"""

from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from config.settings import UserProfile
    from core.filter import ScoredJob

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 2
RETRY_DELAYS = [3, 8]  # seconds before each retry


@dataclass
class ApplyResult:
    """Result of an application attempt."""

    success: bool
    error_message: str | None = None
    captcha_detected: bool = False
    manual_required: bool = False
    login_required: bool = False
    login_domain: str | None = None
    login_portal_type: str | None = None
    attempts: int = 1


class BaseApplier(ABC):
    """Abstract base for platform-specific job appliers."""

    # Default timeout (ms) for waiting on elements after navigation/click
    ELEMENT_TIMEOUT: int = 5000
    # Default timeout (ms) for page navigation
    NAV_TIMEOUT: int = 30000

    def __init__(self, page) -> None:
        self.page = page

    @abstractmethod
    def _do_apply(
        self,
        job: "ScoredJob",
        resume_pdf_path: Path | None,
        cover_letter_text: str,
        profile: "UserProfile",
    ) -> ApplyResult:
        """Core application logic — implemented by each applier."""
        ...

    def apply(
        self,
        job: "ScoredJob",
        resume_pdf_path: Path | None,
        cover_letter_text: str,
        profile: "UserProfile",
    ) -> ApplyResult:
        """Submit a job application with automatic retry on transient failures.

        Retries up to MAX_RETRIES times on network/timeout errors.
        Does NOT retry on CAPTCHA, manual_required, or form validation errors.

        Returns:
            ApplyResult indicating success or failure.
        """
        last_result = None
        platform = self.__class__.__name__.replace("Applier", "")

        for attempt in range(1, MAX_RETRIES + 2):  # 1 + MAX_RETRIES
            try:
                result = self._do_apply(job, resume_pdf_path, cover_letter_text, profile)
                result.attempts = attempt

                # Don't retry on non-transient results
                if result.success or result.captcha_detected or result.manual_required:
                    return result

                last_result = result

                # Don't retry form validation errors (they won't change)
                if result.error_message and any(
                    kw in (result.error_message or "").lower()
                    for kw in ("form error", "validation", "required field")
                ):
                    return result

            except Exception as e:
                logger.warning(
                    "%s: attempt %d/%d failed: %s",
                    platform, attempt, MAX_RETRIES + 1, e,
                )
                last_result = ApplyResult(
                    success=False, error_message=str(e), attempts=attempt,
                )

            # Retry if we have attempts left
            if attempt <= MAX_RETRIES:
                delay = RETRY_DELAYS[attempt - 1] if attempt - 1 < len(RETRY_DELAYS) else 8
                logger.info(
                    "%s: retrying in %ds (attempt %d/%d)",
                    platform, delay, attempt + 1, MAX_RETRIES + 1,
                )
                time.sleep(delay)

        return last_result or ApplyResult(
            success=False, error_message="All retry attempts exhausted",
        )

    def _human_type(self, locator, text: str) -> None:
        """Type text character by character with human-like delays."""
        for char in text:
            locator.type(char)
            time.sleep(random.uniform(0.03, 0.08))

    def _random_pause(self, min_s: float = 0.5, max_s: float = 2.0) -> None:
        """Sleep for a random duration to mimic human behavior."""
        time.sleep(random.uniform(min_s, max_s))

    def _detect_captcha(self) -> bool:
        """Check if a CAPTCHA challenge is present on the page."""
        captcha_indicators = [
            "iframe[src*='captcha']",
            "iframe[src*='recaptcha']",
            "#captcha",
            ".g-recaptcha",
            "[data-sitekey]",
        ]
        for selector in captcha_indicators:
            if self.page.query_selector(selector):
                return True
        return False

    def _safe_goto(self, url: str, **kwargs) -> None:
        """Navigate to URL with configurable timeout and wait."""
        kwargs.setdefault("wait_until", "domcontentloaded")
        kwargs.setdefault("timeout", self.NAV_TIMEOUT)
        self.page.goto(url, **kwargs)

    def _wait_and_query(self, selector: str, timeout: int | None = None) -> Any:
        """Wait for an element to appear, then return it. Returns None on timeout."""
        timeout = timeout or self.ELEMENT_TIMEOUT
        try:
            self.page.wait_for_selector(selector, timeout=timeout, state="visible")
            return self.page.query_selector(selector)
        except Exception:
            return None

    def _safe_fill(self, selector: str, value: str, clear_first: bool = True) -> bool:
        """Find an element, optionally clear it, then fill. Returns True if filled."""
        if not value:
            return False
        el = self.page.query_selector(selector)
        if not el or not el.is_visible():
            return False
        if clear_first:
            current = el.input_value()
            if current and current == value:
                return False  # already has correct value
            if current:
                el.fill("")  # clear before filling
        if not el.input_value():
            self._human_type(el, value)
            self._random_pause(0.2, 0.5)
            return True
        return False

    def _safe_upload(self, resume_path: Path, selectors: str | list[str]) -> bool:
        """Upload a file via file input. Returns True if uploaded successfully."""
        if isinstance(selectors, str):
            selectors = [selectors]
        for selector in selectors:
            file_input = self.page.query_selector(selector)
            if file_input:
                try:
                    file_input.set_input_files(str(resume_path))
                    self._random_pause(1, 2)
                    logger.debug("Resume uploaded via %s", selector)
                    return True
                except Exception as e:
                    logger.warning("Resume upload failed via %s: %s", selector, e)
        return False

    def _safe_click(self, selector: str, timeout: int | None = None) -> bool:
        """Wait for a button/element and click it. Returns True if clicked."""
        el = self._wait_and_query(selector, timeout=timeout or 3000)
        if el and el.is_visible():
            el.click()
            return True
        return False
