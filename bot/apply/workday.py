"""Workday ATS application automation.

Implements: FR-070 (Workday ATS).

Workday is a React SPA using ``data-automation-id`` attributes for selectors.
Application pages live at ``*.myworkdayjobs.com/*/job/*`` and present a
multi-step form: Sign In/Create Account → My Information → My Experience →
Application Questions → Voluntary Disclosures → Self-Identification → Review → Submit.
"""

from __future__ import annotations

import logging

from bot.apply.base import ApplyResult, BaseApplier

logger = logging.getLogger(__name__)

class WorkdayApplier(BaseApplier):
    """Automate Workday job application submissions.

    Workday applications use a multi-step wizard with ``data-automation-id``
    attributes on all form elements.  Each step is navigated via a "Next"
    button at the bottom of the page.
    """

    # Override base timeouts for Workday's slow React SPA
    ELEMENT_TIMEOUT: int = 8000
    NAV_TIMEOUT: int = 45000

    def _do_apply(
        self, job, resume_pdf_path, cover_letter_text, profile
    ) -> ApplyResult:
        logger.info("Workday: applying to %s at %s", job.raw.title, job.raw.company)
        self._safe_goto(job.raw.apply_url)
        self._random_pause(2, 4)

        if self._detect_captcha():
            return ApplyResult(
                success=False, captcha_detected=True,
                error_message="CAPTCHA detected",
            )

        # Click the Apply button on the job detail page
        if not self._click_apply_button():
            return ApplyResult(
                success=False, manual_required=True,
                error_message="Workday Apply button not found",
            )

        self._random_pause(2, 4)

        # Handle account creation / sign-in page if present
        self._handle_auth_page(profile)

        # Process the multi-step application form
        max_steps = 12
        for step in range(max_steps):
            self._random_pause(1, 2)

            if self._detect_captcha():
                return ApplyResult(
                    success=False, captcha_detected=True,
                    error_message="CAPTCHA detected in application form",
                )

            # Check for submission confirmation
            if self._is_submitted():
                return ApplyResult(success=True)

            # Check for errors on the page
            error_text = self._get_page_errors()
            if error_text and step > 0:
                logger.warning("Workday form error on step %d: %s", step, error_text)

            # Fill whichever section is currently visible
            self._fill_my_information(profile)
            self._fill_my_experience(profile, resume_pdf_path)
            self._fill_application_questions(profile, cover_letter_text)
            self._fill_voluntary_disclosures(profile)
            self._fill_self_identification(profile)

            # Try to advance to next step
            if not self._click_next_or_submit():
                # Maybe we're on the final review page — try submit
                if self._click_submit():
                    self._random_pause(3, 5)
                    if self._is_submitted():
                        return ApplyResult(success=True)
                break

            self._random_pause(1, 3)

        # Final check
        if self._is_submitted():
            return ApplyResult(success=True)

        return ApplyResult(
            success=False,
            error_message="Could not complete Workday application — ran out of steps",
        )

    # ------------------------------------------------------------------
    # Apply button
    # ------------------------------------------------------------------

    def _click_apply_button(self) -> bool:
        """Click the initial Apply button on the Workday job page."""
        page = self.page

        # Quick Apply (adventureButton) or manual apply
        for selector in [
            '[data-automation-id="adventureButton"]',
            '[data-automation-id="applyManually"]',
            'a[data-automation-id="jobPostingApplyButton"]',
            'button[data-automation-id="jobPostingApplyButton"]',
        ]:
            btn = page.query_selector(selector)
            if btn and btn.is_visible():
                btn.click()
                return True

        # Fallback: any button or link with "Apply" text
        apply_el = page.query_selector(
            'a:has-text("Apply"), button:has-text("Apply")'
        )
        if apply_el and apply_el.is_visible():
            apply_el.click()
            return True

        return False

    # ------------------------------------------------------------------
    # Auth handling
    # ------------------------------------------------------------------

    def _handle_auth_page(self, profile) -> None:
        """Handle Workday sign-in or create-account page.

        If the user is already signed in (session cookie), this is a no-op.
        Otherwise, attempt to create an account with email/password or sign in.
        """
        page = self.page
        self._random_pause(1, 2)

        # Check if we're on a sign-in page
        create_link = page.query_selector(
            '[data-automation-id="createAccountLink"]'
        )
        email_input = page.query_selector(
            '[data-automation-id="email"], '
            '[data-automation-id="signIn-email"]'
        )

        if not create_link and not email_input:
            # Already authenticated or no auth step
            return

        # Fill email
        if email_input and not email_input.input_value():
            self._human_type(email_input, profile.email)
            self._random_pause(0.5, 1)

        # Fill password from screening_answers if available
        password = profile.screening_answers.get("workday_password", "")
        if password:
            pw_input = page.query_selector(
                '[data-automation-id="password"], '
                '[data-automation-id="signIn-password"]'
            )
            if pw_input:
                self._human_type(pw_input, password)
                self._random_pause(0.5, 1)

        # Try sign in
        signin_btn = page.query_selector(
            '[data-automation-id="signInSubmitButton"], '
            '[data-automation-id="createAccountSubmitButton"]'
        )
        if signin_btn and signin_btn.is_visible():
            signin_btn.click()
            self._random_pause(2, 4)

    # ------------------------------------------------------------------
    # My Information
    # ------------------------------------------------------------------

    def _fill_my_information(self, profile) -> None:
        """Fill the My Information section (name, phone, address)."""
        field_map = {
            '[data-automation-id="legalNameSection_firstName"]': profile.first_name,
            '[data-automation-id="legalNameSection_lastName"]': profile.last_name,
            '[data-automation-id="addressSection_addressLine1"]': profile.address_line1,
            '[data-automation-id="addressSection_city"]': profile.city,
            '[data-automation-id="addressSection_postalCode"]': profile.zip_code,
            '[data-automation-id="phone-number"]': profile.phone,
            '[data-automation-id="email"]': profile.email,
        }

        for selector, value in field_map.items():
            self._safe_fill(selector, value)

        # Country dropdown
        if profile.country:
            self._select_dropdown("country", profile.country)

        # State dropdown
        if profile.state:
            self._select_dropdown("addressSection_countryRegion", profile.state)

    # ------------------------------------------------------------------
    # My Experience
    # ------------------------------------------------------------------

    def _fill_my_experience(self, profile, resume_pdf_path) -> None:
        """Upload resume on the My Experience step."""
        if not resume_pdf_path:
            return

        self._safe_upload(resume_pdf_path, [
            '[data-automation-id="file-upload-input-ref"]',
            'input[type="file"][data-automation-id*="upload"]',
            'input[type="file"]',
        ])

    # ------------------------------------------------------------------
    # Application Questions
    # ------------------------------------------------------------------

    def _fill_application_questions(self, profile, cover_letter_text) -> None:
        """Fill application questions using screening_answers and cover letter."""
        page = self.page

        # Fill any visible text inputs/textareas that are empty
        # Workday uses data-automation-id for each question
        textareas = page.query_selector_all("textarea")
        for ta in textareas:
            if ta.is_visible() and not ta.input_value():
                # Use cover letter text for the first empty textarea
                if cover_letter_text:
                    ta.fill(cover_letter_text)
                    cover_letter_text = ""  # Only fill once
                    self._random_pause(0.5, 1)

        # Try to answer common screening questions from screening_answers
        self._answer_screening_questions(profile)

    def _answer_screening_questions(self, profile) -> None:
        """Answer common screening questions using profile.screening_answers.

        Workday screening questions appear as labeled form groups.
        Common ones: work authorization, visa sponsorship, years of experience,
        willing to relocate, etc.
        """
        answers = profile.screening_answers
        if not answers:
            return

        page = self.page

        # Look for radio buttons and dropdowns with common question patterns
        question_map = {
            "authorized": answers.get("work_authorization", ""),
            "sponsorship": answers.get("visa_sponsorship", ""),
            "relocate": answers.get("willing_to_relocate", ""),
            "experience": answers.get("years_experience", ""),
            "salary": answers.get("desired_salary", ""),
            "start date": answers.get("start_date", ""),
            "referred": answers.get("referred_by", ""),
        }

        # Try to match visible labels to answers
        labels = page.query_selector_all("label")
        for label in labels:
            try:
                label_text = label.inner_text().lower()
            except Exception as e:
                logger.debug("Workday: failed to read label text: %s", e)
                continue

            for keyword, answer in question_map.items():
                if not answer or keyword not in label_text:
                    continue

                # Find the associated input
                label_for = label.get_attribute("for")
                if label_for:
                    inp = page.query_selector(f"#{label_for}")
                    if inp and inp.is_visible() and not inp.input_value():
                        self._human_type(inp, answer)
                        self._random_pause(0.3, 0.6)

    # ------------------------------------------------------------------
    # Voluntary Disclosures & Self-Identification
    # ------------------------------------------------------------------

    def _fill_voluntary_disclosures(self, profile) -> None:
        """Handle voluntary disclosures (EEO) — typically skip or select defaults."""
        answers = profile.screening_answers

        gender = answers.get("gender", "")
        ethnicity = answers.get("ethnicity", "")
        veteran = answers.get("veteran_status", "")

        if gender:
            self._select_dropdown("gender", gender)
        if ethnicity:
            self._select_dropdown("ethnicity", ethnicity)
        if veteran:
            self._select_dropdown("veteranStatus", veteran)

    def _fill_self_identification(self, profile) -> None:
        """Handle disability self-identification — select default if configured."""
        answers = profile.screening_answers
        disability = answers.get("disability_status", "")
        if disability:
            self._select_dropdown("disability", disability)

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _click_next_or_submit(self) -> bool:
        """Click the Next button at the bottom of the Workday form."""
        page = self.page

        next_btn = page.query_selector(
            '[data-automation-id="bottom-navigation-next-button"]'
        )
        if next_btn and next_btn.is_visible():
            next_btn.click()
            return True

        # Fallback: any button with "Next" text
        next_el = page.query_selector('button:has-text("Next")')
        if next_el and next_el.is_visible():
            next_el.click()
            return True

        return False

    def _click_submit(self) -> bool:
        """Click the Submit button on the review page."""
        page = self.page

        for selector in [
            '[data-automation-id="bottom-navigation-next-button"]:has-text("Submit")',
            '[data-automation-id="submit-button"]',
            'button:has-text("Submit Application")',
            'button:has-text("Submit")',
        ]:
            btn = page.query_selector(selector)
            if btn and btn.is_visible():
                btn.click()
                return True
        return False

    def _is_submitted(self) -> bool:
        """Check if the application was successfully submitted."""
        page = self.page
        indicators = [
            '[data-automation-id="thankYouMessage"]',
            'text="Thank you"',
            'text="Application submitted"',
            'text="Your application has been submitted"',
            'h1:has-text("Thank")',
        ]
        for selector in indicators:
            try:
                el = page.query_selector(selector)
                if el and el.is_visible():
                    return True
            except Exception as e:
                logger.debug("Workday: error checking element %s: %s", selector, e)
                continue
        return False

    def _get_page_errors(self) -> str | None:
        """Return visible error text on the Workday page, if any."""
        page = self.page
        for selector in [
            '[data-automation-id="errorMessage"]',
            ".WDMN .WD56",  # Workday inline error class
            '[role="alert"]',
        ]:
            el = page.query_selector(selector)
            if el and el.is_visible():
                try:
                    return str(el.inner_text())[:200]
                except Exception as e:
                    logger.debug("Workday: failed to read error text: %s", e)
                    return "Unknown error"
        return None

    # ------------------------------------------------------------------
    # Dropdown helper
    # ------------------------------------------------------------------

    def _select_dropdown(self, automation_id_part: str, value: str) -> None:
        """Select a value in a Workday dropdown.

        Workday dropdowns use a button with ``aria-haspopup="listbox"``.
        Clicking it opens a listbox from which an option can be selected.
        """
        page = self.page

        # Find dropdown button by partial data-automation-id match
        dropdown_btn = page.query_selector(
            f'button[data-automation-id*="{automation_id_part}"][aria-haspopup="listbox"], '
            f'[data-automation-id*="{automation_id_part}"] button[aria-haspopup="listbox"]'
        )
        if not dropdown_btn or not dropdown_btn.is_visible():
            return

        dropdown_btn.click()
        self._random_pause(0.5, 1)

        # Wait briefly for the listbox to appear, then select matching option
        try:
            page.wait_for_selector('[role="listbox"]', timeout=3000)
        except Exception as e:
            logger.debug("Workday: listbox did not appear for dropdown: %s", e)
            return

        # Find the option that matches the value
        option = page.query_selector(
            f'[role="listbox"] [role="option"]:has-text("{value}")'
        )
        if option and option.is_visible():
            option.click()
            self._random_pause(0.3, 0.6)
