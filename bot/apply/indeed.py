"""Indeed Quick Apply automation.

Implements: FR-048 (Indeed Quick Apply).
"""

from __future__ import annotations

import logging

from bot.apply.base import ApplyResult, BaseApplier

logger = logging.getLogger(__name__)


class IndeedApplier(BaseApplier):
    """Automate Indeed Quick Apply submissions."""

    def _do_apply(
        self, job, resume_pdf_path, cover_letter_text, profile
    ) -> ApplyResult:
        page = self.page

        logger.info("Indeed: applying to %s at %s", job.raw.title, job.raw.company)
        self._safe_goto(job.raw.apply_url)
        self._random_pause(1, 3)

        if self._detect_captcha():
            return ApplyResult(
                success=False, captcha_detected=True,
                error_message="CAPTCHA detected",
            )

        # Find apply button with explicit wait
        apply_btn = self._wait_and_query(
            "button#indeedApplyButton, "
            "button[id*='indeedApply'], "
            ".jobsearch-IndeedApplyButton-newDesign, "
            "button[aria-label*='Apply now']",
            timeout=8000,
        )

        if not apply_btn:
            if "indeed.com" not in page.url:
                return ApplyResult(
                    success=False, manual_required=True,
                    error_message="Redirected to external ATS",
                )
            return ApplyResult(
                success=False, manual_required=True,
                error_message="Apply button not found",
            )

        apply_btn.click()
        self._random_pause(2, 3)

        if "indeed.com" not in page.url:
            return ApplyResult(
                success=False, manual_required=True,
                error_message="Redirected to external ATS",
            )

        # Process the application form (may have multiple steps)
        max_steps = 8
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

            # Check for final submit
            if self._safe_click(
                "button[aria-label*='Submit'], "
                "button.ia-continueButton[type='submit'], "
                "button[id*='submit']",
                timeout=2000,
            ):
                self._random_pause(2, 4)
                return ApplyResult(success=True)

            if self._safe_click(
                "button.ia-continueButton, "
                "button[aria-label*='Continue'], "
                "button[id*='continue']",
                timeout=2000,
            ):
                self._random_pause(1, 2)
            else:
                break

        return ApplyResult(
            success=False,
            error_message="Could not complete Indeed application — ran out of steps",
        )

    def _fill_form_fields(self, profile) -> None:
        """Fill common form fields if they are empty."""
        field_map = {
            "input[name*='name'], input[id*='name']": profile.full_name,
            "input[name*='email'], input[id*='email']": profile.email,
            "input[name*='phone'], input[id*='phone']": profile.phone_full,
        }

        for selector, value in field_map.items():
            self._safe_fill(selector, value)
