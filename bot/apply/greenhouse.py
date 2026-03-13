"""Greenhouse ATS application automation.

Implements: FR-057 (Greenhouse ATS).
"""

from __future__ import annotations

import logging

from bot.apply.base import ApplyResult, BaseApplier

logger = logging.getLogger(__name__)


class GreenhouseApplier(BaseApplier):
    """Automate Greenhouse job application submissions.

    Greenhouse application pages typically live at
    ``boards.greenhouse.io/{company}/jobs/{id}`` and present a single-page
    form with personal info fields, resume upload, cover letter textarea,
    and optional custom questions.
    """

    def _do_apply(
        self, job, resume_pdf_path, cover_letter_text, profile
    ) -> ApplyResult:
        logger.info("Greenhouse: applying to %s at %s", job.raw.title, job.raw.company)
        self._safe_goto(job.raw.apply_url)
        self._random_pause(1, 3)

        if self._detect_captcha():
            return ApplyResult(
                success=False, captcha_detected=True,
                error_message="CAPTCHA detected",
            )

        # Greenhouse may show an "Apply for this job" button first
        self._safe_click(
            "a#apply_button, "
            "a[href*='#app'], "
            "button[id*='apply'], "
            "a.btn[href*='apply']",
            timeout=3000,
        )
        self._random_pause(1, 2)

        # Fill personal info
        self._fill_form_fields(profile)

        # Upload resume
        if resume_pdf_path:
            self._safe_upload(resume_pdf_path, [
                "input[type='file'][name*='resume']",
                "input[type='file'][id*='resume']",
                "input[type='file'][data-field*='resume']",
                "input[type='file']",
            ])

        # Fill cover letter
        self._fill_cover_letter(cover_letter_text)

        self._random_pause(0.5, 1)

        # Submit the form
        submit_btn = self._wait_and_query(
            "input[type='submit']#submit_app, "
            "input[type='submit'][value*='Submit'], "
            "button[type='submit'], "
            "input#submit_app",
            timeout=5000,
        )

        if not submit_btn:
            return ApplyResult(
                success=False, manual_required=True,
                error_message="Submit button not found on Greenhouse form",
            )

        submit_btn.click()
        self._random_pause(2, 4)

        # Check for errors after submission
        error_el = self._wait_and_query(
            ".field_with_errors, .error, #application_errors",
            timeout=3000,
        )
        if error_el and error_el.is_visible():
            error_text = error_el.inner_text()[:200]
            return ApplyResult(
                success=False,
                error_message=f"Greenhouse form error: {error_text}",
            )

        return ApplyResult(success=True)

    def _fill_form_fields(self, profile) -> None:
        """Fill Greenhouse standard personal info fields."""
        field_map = {
            "#first_name, input[name*='first_name']": profile.first_name,
            "#last_name, input[name*='last_name']": profile.last_name,
            "#email, input[name*='email']": profile.email,
            "#phone, input[name*='phone']": profile.phone_full,
        }

        for selector, value in field_map.items():
            self._safe_fill(selector, value)

        # LinkedIn profile URL
        if profile.linkedin_url:
            self._safe_fill(
                "input[name*='linkedin'], input[id*='linkedin'], input[autocomplete*='url']",
                profile.linkedin_url,
            )

    def _fill_cover_letter(self, text: str) -> None:
        """Fill cover letter textarea on Greenhouse form."""
        if not text:
            return
        textarea = self.page.query_selector(
            "textarea[name*='cover_letter'], "
            "textarea[id*='cover_letter'], "
            "textarea[name*='cover'], "
            "#cover_letter"
        )
        if textarea and textarea.is_visible() and not textarea.input_value():
            textarea.fill(text)
            self._random_pause(0.5, 1)
