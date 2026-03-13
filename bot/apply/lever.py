"""Lever ATS application automation.

Implements: FR-058 (Lever ATS).
"""

from __future__ import annotations

import logging

from bot.apply.base import ApplyResult, BaseApplier

logger = logging.getLogger(__name__)


class LeverApplier(BaseApplier):
    """Automate Lever job application submissions.

    Lever application pages live at ``jobs.lever.co/{company}/{id}/apply``
    and present a single-page form with personal info, resume upload,
    cover letter textarea, and optional custom questions.
    """

    def _do_apply(
        self, job, resume_pdf_path, cover_letter_text, profile
    ) -> ApplyResult:
        # Lever job pages need /apply appended to reach the form
        apply_url = job.raw.apply_url
        if "/apply" not in apply_url:
            apply_url = apply_url.rstrip("/") + "/apply"

        logger.info("Lever: applying to %s at %s", job.raw.title, job.raw.company)
        self._safe_goto(apply_url)
        self._random_pause(1, 3)

        if self._detect_captcha():
            return ApplyResult(
                success=False, captcha_detected=True,
                error_message="CAPTCHA detected",
            )

        # Verify we're on the application form with explicit wait
        form = self._wait_and_query(
            "form.application-form, "
            "form[action*='apply'], "
            ".application-form, "
            "form.postings-form",
            timeout=8000,
        )
        if not form:
            return ApplyResult(
                success=False, manual_required=True,
                error_message="Lever application form not found",
            )

        self._fill_form_fields(profile)

        if resume_pdf_path:
            self._safe_upload(resume_pdf_path, [
                "input[type='file'][name='resume']",
                "input[type='file'][name*='resume']",
                "input[type='file']",
            ])

        self._fill_cover_letter(cover_letter_text)
        self._random_pause(0.5, 1)

        # Submit the form
        submit_btn = self._wait_and_query(
            "button.postings-btn[type='submit'], "
            "button[type='submit'], "
            "button.postings-btn-submit, "
            "input[type='submit']",
            timeout=5000,
        )

        if not submit_btn:
            return ApplyResult(
                success=False, manual_required=True,
                error_message="Submit button not found on Lever form",
            )

        submit_btn.click()
        self._random_pause(2, 4)

        # Check for errors
        error_el = self._wait_and_query(
            ".application-error, .error-message, .form-error",
            timeout=3000,
        )
        if error_el and error_el.is_visible():
            error_text = error_el.inner_text()[:200]
            return ApplyResult(
                success=False,
                error_message=f"Lever form error: {error_text}",
            )

        return ApplyResult(success=True)

    def _fill_form_fields(self, profile) -> None:
        """Fill Lever standard personal info fields."""
        field_map = {
            "input[name='name']": profile.full_name,
            "input[name='email']": profile.email,
            "input[name='phone']": profile.phone_full,
        }

        for selector, value in field_map.items():
            self._safe_fill(selector, value)

        # LinkedIn URL
        if profile.linkedin_url:
            self._safe_fill(
                "input[name='urls[LinkedIn]'], input[name*='linkedin'], input[placeholder*='LinkedIn']",
                profile.linkedin_url,
            )

        # Website/portfolio URL
        if profile.portfolio_url:
            self._safe_fill(
                "input[name='urls[Portfolio]'], input[name='urls[Other]'], "
                "input[name*='website'], input[placeholder*='Website']",
                profile.portfolio_url,
            )

    def _fill_cover_letter(self, text: str) -> None:
        """Fill cover letter textarea on Lever form."""
        if not text:
            return
        textarea = self.page.query_selector(
            "textarea[name='comments'], "
            "textarea[name*='cover'], "
            "textarea.application-answer-alternative"
        )
        if textarea and textarea.is_visible() and not textarea.input_value():
            textarea.fill(text)
            self._random_pause(0.5, 1)
