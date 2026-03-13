"""LinkedIn Easy Apply automation.

Implements: FR-047 (LinkedIn Easy Apply).
"""

from __future__ import annotations

import logging

from bot.apply.base import ApplyResult, BaseApplier

logger = logging.getLogger(__name__)


class LinkedInApplier(BaseApplier):
    """Automate LinkedIn Easy Apply submissions."""

    def _do_apply(
        self, job, resume_pdf_path, cover_letter_text, profile
    ) -> ApplyResult:
        logger.info("LinkedIn: applying to %s at %s", job.raw.title, job.raw.company)
        self._safe_goto(job.raw.apply_url)
        self._random_pause(1, 3)

        if self._detect_captcha():
            return ApplyResult(
                success=False, captcha_detected=True,
                error_message="CAPTCHA detected",
            )

        # Find and click Easy Apply button with explicit wait
        easy_apply_btn = self._wait_and_query(
            "button.jobs-apply-button, "
            "button[aria-label*='Easy Apply'], "
            ".jobs-apply-button--top-card",
            timeout=8000,
        )

        if not easy_apply_btn:
            return ApplyResult(
                success=False, manual_required=True,
                error_message="Easy Apply button not found — external application required",
            )

        easy_apply_btn.click()
        self._random_pause(1, 2)

        # Process multi-step Easy Apply modal
        max_steps = 10
        for step in range(max_steps):
            if self._detect_captcha():
                return ApplyResult(
                    success=False, captcha_detected=True,
                    error_message="CAPTCHA detected in application form",
                )

            self._fill_form_fields(profile)

            if resume_pdf_path:
                self._safe_upload(resume_pdf_path, [
                    "input[type='file'][name*='resume']",
                    "input[type='file']",
                ])

            self._fill_cover_letter(cover_letter_text)

            # Check for submit button (final step)
            if self._safe_click(
                "button[aria-label*='Submit application'], "
                "button[aria-label*='Submit']",
                timeout=2000,
            ):
                self._random_pause(2, 4)

                # Close confirmation modal if present
                self._safe_click(
                    "button[aria-label*='Dismiss'], "
                    "[data-test-modal-close-btn]",
                    timeout=3000,
                )
                return ApplyResult(success=True)

            # Click "Next" or "Review" to advance
            if self._safe_click(
                "button[aria-label*='Continue'], "
                "button[aria-label*='Next'], "
                "button[aria-label*='Review']",
                timeout=2000,
            ):
                self._random_pause(1, 2)
            else:
                break

        return ApplyResult(
            success=False,
            error_message="Could not complete Easy Apply — ran out of steps",
        )

    def _fill_form_fields(self, profile) -> None:
        """Fill common form fields if they are empty."""
        self._safe_fill(
            "input[name*='phone'], input[id*='phone']",
            profile.phone_full,
        )

    def _fill_cover_letter(self, text: str) -> None:
        """Fill cover letter textarea if visible."""
        if not text:
            return
        textarea = self.page.query_selector(
            "textarea[name*='cover'], "
            "textarea[id*='cover'], "
            "textarea[aria-label*='cover']"
        )
        if textarea and textarea.is_visible() and not textarea.input_value():
            textarea.fill(text)
            self._random_pause(0.5, 1)
