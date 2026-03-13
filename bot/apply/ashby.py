"""Ashby ATS application automation.

Implements: FR-071 (Ashby ATS).

Ashby is used by OpenAI, YC startups, and other tech companies.
Application pages live at ``jobs.ashbyhq.com/{company}/application/{id}``
and present a single-page form with personal info, resume upload,
cover letter, and custom questions.
"""

from __future__ import annotations

import logging

from bot.apply.base import ApplyResult, BaseApplier

logger = logging.getLogger(__name__)


class AshbyApplier(BaseApplier):
    """Automate Ashby job application submissions.

    Ashby uses a clean single-page React form with standard HTML inputs,
    file upload, and optional custom questions.
    """

    def _do_apply(
        self, job, resume_pdf_path, cover_letter_text, profile
    ) -> ApplyResult:
        logger.info("Ashby: applying to %s at %s", job.raw.title, job.raw.company)
        self._safe_goto(job.raw.apply_url)
        self._random_pause(1, 3)

        if self._detect_captcha():
            return ApplyResult(
                success=False, captcha_detected=True,
                error_message="CAPTCHA detected",
            )

        # Ashby may show a job detail page first — click "Apply" if present
        self._safe_click(
            'a:has-text("Apply for this job"), '
            'button:has-text("Apply for this job"), '
            'a:has-text("Apply"), '
            'button:has-text("Apply")',
            timeout=3000,
        )
        self._random_pause(1, 2)

        self._fill_form_fields(profile)

        if resume_pdf_path:
            self._safe_upload(resume_pdf_path, [
                'input[type="file"][name*="resume"]',
                'input[type="file"][accept*="pdf"]',
                'input[type="file"]',
            ])

        self._fill_cover_letter(cover_letter_text)
        self._answer_custom_questions(profile)
        self._random_pause(0.5, 1)

        # Submit
        submit_btn = self._wait_and_query(
            'button[type="submit"]:has-text("Submit"), '
            'button[type="submit"]:has-text("Apply"), '
            'button[type="submit"]',
            timeout=5000,
        )

        if not submit_btn:
            return ApplyResult(
                success=False, manual_required=True,
                error_message="Submit button not found on Ashby form",
            )

        submit_btn.click()
        self._random_pause(2, 4)

        # Check for success
        success_el = self._wait_and_query(
            'text="Your application has been submitted", '
            'text="Application submitted", '
            'text="Thank you", '
            'h1:has-text("Thank"), '
            'h2:has-text("Thank")',
            timeout=5000,
        )
        if success_el:
            return ApplyResult(success=True)

        # Check for errors
        error_el = self.page.query_selector(
            '[role="alert"], .error-message, .form-error'
        )
        if error_el and error_el.is_visible():
            error_text = error_el.inner_text()[:200]
            return ApplyResult(
                success=False,
                error_message=f"Ashby form error: {error_text}",
            )

        # No clear success or error — assume success if no error visible
        return ApplyResult(success=True)

    def _fill_form_fields(self, profile) -> None:
        """Fill Ashby personal info fields."""
        field_map = {
            'input[name="name"], input[name*="Name"]:not([name*="last"])': profile.full_name,
            'input[name*="firstName"], input[name*="first_name"]': profile.first_name,
            'input[name*="lastName"], input[name*="last_name"]': profile.last_name,
            'input[name="email"], input[name*="email"], input[type="email"]': profile.email,
            'input[name="phone"], input[name*="phone"], input[type="tel"]': profile.phone_full,
        }

        for selector, value in field_map.items():
            self._safe_fill(selector, value)

        # LinkedIn URL
        if profile.linkedin_url:
            self._safe_fill(
                'input[name*="linkedin"], input[name*="LinkedIn"], '
                'input[placeholder*="LinkedIn"], input[placeholder*="linkedin"]',
                profile.linkedin_url,
            )

        # Portfolio / website
        if profile.portfolio_url:
            self._safe_fill(
                'input[name*="website"], input[name*="portfolio"], '
                'input[placeholder*="Website"], input[placeholder*="Portfolio"]',
                profile.portfolio_url,
            )

        # Location
        self._safe_fill(
            'input[name*="location"], input[name*="Location"], '
            'input[placeholder*="location"]',
            profile.location,
        )

    def _fill_cover_letter(self, text: str) -> None:
        """Fill cover letter textarea on Ashby form."""
        if not text:
            return

        page = self.page

        textarea = page.query_selector(
            'textarea[name*="cover"], '
            'textarea[name*="Cover"], '
            'textarea[name*="letter"], '
            'textarea[placeholder*="cover letter"], '
            'textarea[placeholder*="Cover Letter"]'
        )
        if textarea and textarea.is_visible() and not textarea.input_value():
            textarea.fill(text)
            self._random_pause(0.5, 1)
            return

        # Ashby sometimes uses a generic "Additional information" textarea
        additional = page.query_selector(
            'textarea[name*="additional"], '
            'textarea[placeholder*="additional"], '
            'textarea[placeholder*="anything else"]'
        )
        if additional and additional.is_visible() and not additional.input_value():
            additional.fill(text)
            self._random_pause(0.5, 1)

    def _answer_custom_questions(self, profile) -> None:
        """Attempt to answer Ashby custom questions from screening_answers."""
        answers = profile.screening_answers
        if not answers:
            return

        page = self.page

        # Ashby renders custom questions as labeled form groups
        # Try to match label text to screening_answers keys
        labels = page.query_selector_all("label")
        for label in labels:
            try:
                label_text = label.inner_text().strip().lower()
            except Exception as e:
                logger.debug("Ashby: failed to read label text: %s", e)
                continue

            # Match against screening_answers
            for key, value in answers.items():
                if not value:
                    continue
                key_lower = key.replace("_", " ").lower()
                if key_lower in label_text or label_text in key_lower:
                    label_for = label.get_attribute("for")
                    if label_for:
                        inp = page.query_selector(f"#{label_for}")
                        if inp and inp.is_visible() and not inp.input_value():
                            tag = inp.evaluate("el => el.tagName.toLowerCase()")
                            if tag == "select":
                                inp.select_option(label=value)
                            elif tag == "textarea":
                                inp.fill(value)
                            else:
                                self._human_type(inp, value)
                            self._random_pause(0.3, 0.6)
                    break
