"""Additional coverage tests for all applier modules — targeting uncovered branches.

Requirement traceability:
    ME-5   — Test coverage increase to 70%
    FR-047 — LinkedIn Easy Apply (uncovered branches)
    FR-048 — Indeed Quick Apply (uncovered branches)
    FR-057 — Greenhouse ATS (uncovered branches)
    FR-058 — Lever ATS (uncovered branches)
    FR-070 — Workday ATS (uncovered branches)
    FR-071 — Ashby ATS (uncovered branches)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from bot.apply.ashby import AshbyApplier
from bot.apply.greenhouse import GreenhouseApplier
from bot.apply.indeed import IndeedApplier
from bot.apply.lever import LeverApplier
from bot.apply.linkedin import LinkedInApplier
from bot.apply.workday import WorkdayApplier
from bot.search.base import RawJob
from core.filter import ScoredJob

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_profile(**overrides):
    profile = MagicMock()
    profile.full_name = overrides.get("full_name", "Jane Doe")
    profile.first_name = overrides.get("first_name", "Jane")
    profile.last_name = overrides.get("last_name", "Doe")
    profile.email = overrides.get("email", "jane@example.com")
    profile.phone = overrides.get("phone", "555-0100")
    profile.phone_full = overrides.get("phone_full", "+1-555-0100")
    profile.phone_country_code = overrides.get("phone_country_code", "+1")
    profile.linkedin_url = overrides.get("linkedin_url", "https://linkedin.com/in/janedoe")
    profile.portfolio_url = overrides.get("portfolio_url", "https://janedoe.dev")
    profile.location = overrides.get("location", "New York, NY")
    profile.city = overrides.get("city", "New York")
    profile.state = overrides.get("state", "NY")
    profile.zip_code = overrides.get("zip_code", "10001")
    profile.country = overrides.get("country", "United States")
    profile.address_line1 = overrides.get("address_line1", "123 Main St")
    profile.bio = overrides.get("bio", "Experienced engineer.")
    profile.screening_answers = overrides.get("screening_answers", {})
    return profile


def _make_scored_job(apply_url, platform):
    raw = RawJob(
        title="Software Engineer", company="Acme",
        location="Remote", salary="$130K",
        description="Build things.", apply_url=apply_url,
        platform=platform, external_id=f"{platform}-123", posted_at=None,
    )
    return ScoredJob(id="test-uuid", raw=raw, score=85,
                     pass_filter=True, skip_reason=None)


def _make_page(url="https://example.com"):
    page = MagicMock()
    page.url = url
    page.query_selector.return_value = None
    page.query_selector_all.return_value = []
    return page


# ===================================================================
# LinkedIn — uncovered branches
# ===================================================================


class TestLinkedInUploadResumeException:
    """FR-047: Resume upload exception is silently handled."""

    @patch("bot.apply.base.time.sleep")
    def test_upload_resume_exception_handled(self, _sleep):
        page = _make_page()
        fi = MagicMock()
        fi.set_input_files.side_effect = Exception("Upload failed")
        page.query_selector.return_value = fi
        applier = LinkedInApplier(page)
        applier._upload_resume(Path("/tmp/resume.pdf"))
        # No exception raised

    @patch("bot.apply.base.time.sleep")
    def test_upload_resume_no_input(self, _sleep):
        page = _make_page()
        page.query_selector.return_value = None
        applier = LinkedInApplier(page)
        applier._upload_resume(Path("/tmp/resume.pdf"))
        # No exception raised

    @patch("bot.apply.base.time.sleep")
    def test_fill_phone_skips_prefilled(self, _sleep):
        page = _make_page()
        phone_input = MagicMock()
        phone_input.input_value.return_value = "+1-555-9999"

        def qs(selector):
            if "phone" in selector:
                return phone_input
            return None

        page.query_selector.side_effect = qs
        applier = LinkedInApplier(page)
        applier._fill_form_fields(_make_profile())
        phone_input.type.assert_not_called()

    @patch("bot.apply.base.time.sleep")
    def test_fill_cover_letter_skips_prefilled(self, _sleep):
        page = _make_page()
        ta = MagicMock()
        ta.input_value.return_value = "Already has cover letter"

        def qs(selector):
            if "cover" in selector:
                return ta
            return None

        page.query_selector.side_effect = qs
        applier = LinkedInApplier(page)
        applier._fill_cover_letter("New letter")
        ta.fill.assert_not_called()

    @patch("bot.apply.base.time.sleep")
    def test_multi_step_with_next_button(self, _sleep):
        """Test multi-step modal with Next button before Submit."""
        page = _make_page("https://www.linkedin.com/jobs/view/123/")
        easy_btn = MagicMock()
        submit_btn = MagicMock()
        submit_btn.is_visible.return_value = True
        next_btn = MagicMock()
        next_btn.is_visible.return_value = True
        confirm = MagicMock()

        call_count = {"n": 0}

        def qs(selector):
            call_count["n"] += 1
            if "Easy Apply" in selector or "jobs-apply-button" in selector:
                return easy_btn
            if "Submit" in selector:
                # Only return submit on second step
                if call_count["n"] > 8:
                    return submit_btn
                return None
            if "Continue" in selector or "Next" in selector:
                return next_btn
            if "artdeco-modal" in selector:
                return confirm
            return None

        page.query_selector.side_effect = qs
        applier = LinkedInApplier(page)
        job = _make_scored_job("https://www.linkedin.com/jobs/view/123/", "linkedin")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is True

    @patch("bot.apply.base.time.sleep")
    def test_captcha_in_modal(self, _sleep):
        """Test CAPTCHA detected inside modal step."""
        page = _make_page("https://www.linkedin.com/jobs/view/123/")
        easy_btn = MagicMock()

        step = {"n": 0}

        def qs(selector):
            step["n"] += 1
            if step["n"] <= 2 and ("Easy Apply" in selector or "jobs-apply-button" in selector):
                return easy_btn
            # After clicking Easy Apply, CAPTCHA appears
            if step["n"] > 2:
                return MagicMock()  # CAPTCHA element
            return None

        page.query_selector.side_effect = qs
        applier = LinkedInApplier(page)
        job = _make_scored_job("https://www.linkedin.com/jobs/view/123/", "linkedin")
        result = applier.apply(job, Path("/tmp/r.pdf"), "cover", _make_profile())
        assert result.success is False
        assert result.captcha_detected is True

    @patch("bot.apply.base.time.sleep")
    def test_exception_returns_failure(self, _sleep):
        """Lines 45-47: exception in _do_apply returns ApplyResult."""
        page = _make_page("https://www.linkedin.com/jobs/view/123/")
        page.goto.side_effect = Exception("Network error")
        applier = LinkedInApplier(page)
        job = _make_scored_job("https://www.linkedin.com/jobs/view/123/", "linkedin")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is False
        assert "Network error" in result.error_message

    @patch("bot.apply.base.time.sleep")
    def test_no_easy_apply_button(self, _sleep):
        """Line 74: Easy Apply button not found."""
        page = _make_page("https://www.linkedin.com/jobs/view/123/")
        page.query_selector.return_value = None
        applier = LinkedInApplier(page)
        job = _make_scored_job("https://www.linkedin.com/jobs/view/123/", "linkedin")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is False
        assert result.manual_required is True
        assert "Easy Apply" in result.error_message

    @patch("bot.apply.base.time.sleep")
    def test_submit_with_confirmation_close(self, _sleep):
        """Lines 117-126: submit found, confirmation modal, close button clicked."""
        page = _make_page("https://www.linkedin.com/jobs/view/123/")
        easy_btn = MagicMock()
        submit_btn = MagicMock()
        submit_btn.is_visible.return_value = True
        confirmation = MagicMock()
        close_btn = MagicMock()

        def qs(selector):
            if "Easy Apply" in selector or "jobs-apply-button" in selector:
                return easy_btn
            if "captcha" in selector or "recaptcha" in selector or "sitekey" in selector:
                return None
            if "Submit" in selector:
                return submit_btn
            if "artdeco-modal" in selector or "jpac-modal" in selector or "modal-close" in selector:
                return confirmation
            if "Dismiss" in selector or "modal-close" in selector:
                return close_btn
            return None

        page.query_selector.side_effect = qs
        applier = LinkedInApplier(page)
        job = _make_scored_job("https://www.linkedin.com/jobs/view/123/", "linkedin")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is True

    @patch("bot.apply.base.time.sleep")
    def test_ran_out_of_steps(self, _sleep):
        """Lines 129-140: no next button found, breaks out, returns failure."""
        page = _make_page("https://www.linkedin.com/jobs/view/123/")
        easy_btn = MagicMock()

        def qs(selector):
            if "Easy Apply" in selector or "jobs-apply-button" in selector:
                return easy_btn
            if "captcha" in selector or "recaptcha" in selector or "sitekey" in selector:
                return None
            return None

        page.query_selector.side_effect = qs
        applier = LinkedInApplier(page)
        job = _make_scored_job("https://www.linkedin.com/jobs/view/123/", "linkedin")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is False
        assert "ran out of steps" in result.error_message

    @patch("bot.apply.base.time.sleep")
    def test_fill_phone_fills_empty(self, _sleep):
        """Lines 155-156: phone field filled when empty."""
        page = _make_page()
        phone_input = MagicMock()
        phone_input.input_value.return_value = ""

        def qs(selector):
            if "phone" in selector:
                return phone_input
            return None

        page.query_selector.side_effect = qs
        applier = LinkedInApplier(page)
        applier._fill_form_fields(_make_profile(phone_full="+1-555-0100"))
        assert phone_input.type.call_count == len("+1-555-0100")

    @patch("bot.apply.base.time.sleep")
    def test_upload_resume_success(self, _sleep):
        """Line 167: file input found and resume uploaded."""
        page = _make_page()
        fi = MagicMock()

        def qs(selector):
            if "file" in selector:
                return fi
            return None

        page.query_selector.side_effect = qs
        applier = LinkedInApplier(page)
        applier._upload_resume(Path("/tmp/resume.pdf"))
        fi.set_input_files.assert_called_once_with(str(Path("/tmp/resume.pdf")))

    @patch("bot.apply.base.time.sleep")
    def test_fill_cover_letter_success(self, _sleep):
        """Lines 182-183: cover letter textarea filled."""
        page = _make_page()
        ta = MagicMock()
        ta.input_value.return_value = ""

        def qs(selector):
            if "cover" in selector:
                return ta
            return None

        page.query_selector.side_effect = qs
        applier = LinkedInApplier(page)
        applier._fill_cover_letter("My cover letter")
        ta.fill.assert_called_once_with("My cover letter")

    @patch("bot.apply.base.time.sleep")
    def test_resume_upload_in_loop(self, _sleep):
        """Line 97: resume uploaded inside the multi-step loop."""
        page = _make_page("https://www.linkedin.com/jobs/view/123/")
        easy_btn = MagicMock()
        submit_btn = MagicMock()
        submit_btn.is_visible.return_value = True
        fi = MagicMock()

        def qs(selector):
            if "Easy Apply" in selector or "jobs-apply-button" in selector:
                return easy_btn
            if "captcha" in selector or "recaptcha" in selector or "sitekey" in selector:
                return None
            if "file" in selector:
                return fi
            if "Submit" in selector:
                return submit_btn
            if "artdeco-modal" in selector or "jpac-modal" in selector:
                return MagicMock()
            return None

        page.query_selector.side_effect = qs
        applier = LinkedInApplier(page)
        job = _make_scored_job("https://www.linkedin.com/jobs/view/123/", "linkedin")
        result = applier.apply(job, Path("/tmp/resume.pdf"), "", _make_profile())
        assert result.success is True
        fi.set_input_files.assert_called()

    @patch("bot.apply.base.time.sleep")
    def test_captcha_in_loop_precise(self, _sleep):
        """Line 87: CAPTCHA detected inside the for-loop (not at start)."""
        page = _make_page("https://www.linkedin.com/jobs/view/123/")
        easy_btn = MagicMock()
        loop_entered = {"v": False}

        def qs(selector):
            # Easy Apply button found
            if "Easy Apply" in selector or "jobs-apply-button" in selector:
                if not loop_entered["v"]:
                    return easy_btn
                return None
            # CAPTCHA: not present at start, present in loop
            if "captcha" in selector or "recaptcha" in selector or "sitekey" in selector:
                if loop_entered["v"]:
                    return MagicMock()  # CAPTCHA in loop
                return None
            return None

        page.query_selector.side_effect = qs
        # Mark loop entered after Easy Apply click
        def on_click():
            loop_entered["v"] = True
        easy_btn.click.side_effect = on_click

        applier = LinkedInApplier(page)
        job = _make_scored_job("https://www.linkedin.com/jobs/view/123/", "linkedin")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is False
        assert result.captcha_detected is True
        assert "application form" in result.error_message

    @patch("bot.apply.base.time.sleep")
    def test_next_button_advances_then_submit(self, _sleep):
        """Lines 135-136: Next button clicked, then submit on next iteration."""
        page = _make_page("https://www.linkedin.com/jobs/view/123/")
        easy_btn = MagicMock()
        next_btn = MagicMock()
        next_btn.is_visible.return_value = True
        submit_btn = MagicMock()
        submit_btn.is_visible.return_value = True
        step = {"n": 0}

        def qs(selector):
            if "Easy Apply" in selector or "jobs-apply-button" in selector:
                return easy_btn
            if "captcha" in selector or "recaptcha" in selector or "sitekey" in selector:
                return None
            if "Submit" in selector:
                step["n"] += 1
                if step["n"] > 1:
                    return submit_btn
                return None
            if "Continue" in selector or "Next" in selector or "Review" in selector:
                if step["n"] <= 1:
                    return next_btn
                return None
            if "artdeco-modal" in selector or "jpac-modal" in selector:
                return MagicMock()
            return None

        page.query_selector.side_effect = qs
        applier = LinkedInApplier(page)
        job = _make_scored_job("https://www.linkedin.com/jobs/view/123/", "linkedin")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is True
        assert next_btn.click.call_count >= 1


# ===================================================================
# Indeed — uncovered branches
# ===================================================================


class TestIndeedRanOutOfSteps:
    """FR-048: Indeed ran out of steps path."""

    @patch("bot.apply.base.time.sleep")
    def test_ran_out_of_steps(self, _sleep):
        page = _make_page("https://www.indeed.com/viewjob?jk=abc")
        apply_btn = MagicMock()

        def qs(selector):
            if "indeedApply" in selector or "Apply now" in selector:
                return apply_btn
            return None

        page.query_selector.side_effect = qs
        applier = IndeedApplier(page)
        job = _make_scored_job("https://www.indeed.com/viewjob?jk=abc", "indeed")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is False
        assert "ran out of steps" in result.error_message

    @patch("bot.apply.base.time.sleep")
    def test_upload_resume_exception_handled(self, _sleep):
        page = _make_page()
        fi = MagicMock()
        fi.set_input_files.side_effect = Exception("Upload failed")
        page.query_selector.return_value = fi
        applier = IndeedApplier(page)
        applier._upload_resume(Path("/tmp/resume.pdf"))

    @patch("bot.apply.base.time.sleep")
    def test_upload_resume_no_input(self, _sleep):
        page = _make_page()
        page.query_selector.return_value = None
        applier = IndeedApplier(page)
        applier._upload_resume(Path("/tmp/resume.pdf"))

    @patch("bot.apply.base.time.sleep")
    def test_fill_form_skips_prefilled(self, _sleep):
        page = _make_page()
        name_input = MagicMock()
        name_input.input_value.return_value = "Prefilled Name"

        page.query_selector.return_value = name_input
        applier = IndeedApplier(page)
        applier._fill_form_fields(_make_profile())
        name_input.type.assert_not_called()

    @patch("bot.apply.base.time.sleep")
    def test_redirect_before_apply_button(self, _sleep):
        """Redirect detected before finding apply button."""
        page = _make_page("https://external-ats.com/apply")
        page.query_selector.return_value = None
        applier = IndeedApplier(page)
        job = _make_scored_job("https://www.indeed.com/viewjob?jk=abc", "indeed")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is False
        assert result.manual_required is True
        assert "external ATS" in result.error_message

    @patch("bot.apply.base.time.sleep")
    def test_captcha_in_form_step(self, _sleep):
        """CAPTCHA detected during multi-step form."""
        page = _make_page("https://www.indeed.com/viewjob?jk=abc")
        apply_btn = MagicMock()
        continue_btn = MagicMock()
        continue_btn.is_visible.return_value = True

        step = {"n": 0}

        def qs(selector):
            step["n"] += 1
            if step["n"] <= 2 and ("indeedApply" in selector or "Apply now" in selector):
                return apply_btn
            if step["n"] > 4 and ("continueButton" in selector or "Continue" in selector):
                return continue_btn
            # After first Continue click, CAPTCHA appears
            if step["n"] > 6:
                return MagicMock()  # CAPTCHA element
            return None

        page.query_selector.side_effect = qs
        applier = IndeedApplier(page)
        job = _make_scored_job("https://www.indeed.com/viewjob?jk=abc", "indeed")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is False

    @patch("bot.apply.base.time.sleep")
    def test_exception_returns_failure(self, _sleep):
        """Lines 44-46: exception in _do_apply returns ApplyResult."""
        page = _make_page("https://www.indeed.com/viewjob?jk=abc")
        page.goto.side_effect = Exception("DNS error")
        applier = IndeedApplier(page)
        job = _make_scored_job("https://www.indeed.com/viewjob?jk=abc", "indeed")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is False
        assert "DNS error" in result.error_message

    @patch("bot.apply.base.time.sleep")
    def test_captcha_at_start(self, _sleep):
        """Line 59: CAPTCHA detected before finding apply button."""
        page = _make_page("https://www.indeed.com/viewjob?jk=abc")
        page.query_selector.return_value = MagicMock()  # everything matches = CAPTCHA
        applier = IndeedApplier(page)
        job = _make_scored_job("https://www.indeed.com/viewjob?jk=abc", "indeed")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is False
        assert result.captcha_detected is True

    @patch("bot.apply.base.time.sleep")
    def test_redirect_after_apply_click(self, _sleep):
        """Line 89: redirect to external ATS after clicking apply."""
        page = _make_page("https://www.indeed.com/viewjob?jk=abc")
        apply_btn = MagicMock()

        def qs(selector):
            if "indeedApply" in selector or "Apply now" in selector:
                return apply_btn
            if "captcha" in selector or "recaptcha" in selector or "sitekey" in selector:
                return None
            return None

        page.query_selector.side_effect = qs
        # After clicking apply, URL changes to external
        def fake_goto(*args, **kwargs):
            page.url = "https://external-ats.com/apply"
        page.goto.side_effect = fake_goto
        # url starts as indeed, but changes after apply click
        page.url = "https://www.indeed.com/viewjob?jk=abc"

        applier = IndeedApplier(page)
        job = _make_scored_job("https://www.indeed.com/viewjob?jk=abc", "indeed")
        # We need the redirect to happen after apply_btn.click
        def click_redirect():
            page.url = "https://external-ats.com/apply"
        apply_btn.click.side_effect = click_redirect

        result = applier.apply(job, None, "", _make_profile())
        assert result.success is False
        assert result.manual_required is True
        assert "external ATS" in result.error_message

    @patch("bot.apply.base.time.sleep")
    def test_submit_button_success(self, _sleep):
        """Lines 124-126: submit button found and clicked."""
        page = _make_page("https://www.indeed.com/viewjob?jk=abc")
        apply_btn = MagicMock()
        submit_btn = MagicMock()
        submit_btn.is_visible.return_value = True

        def qs(selector):
            if "indeedApply" in selector or "Apply now" in selector:
                return apply_btn
            if "captcha" in selector or "recaptcha" in selector or "sitekey" in selector:
                return None
            if "Submit" in selector or "submit" in selector:
                return submit_btn
            return None

        page.query_selector.side_effect = qs
        applier = IndeedApplier(page)
        job = _make_scored_job("https://www.indeed.com/viewjob?jk=abc", "indeed")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is True
        submit_btn.click.assert_called_once()

    @patch("bot.apply.base.time.sleep")
    def test_continue_button_advances(self, _sleep):
        """Lines 129-130: continue button clicked to advance step."""
        page = _make_page("https://www.indeed.com/viewjob?jk=abc")
        apply_btn = MagicMock()
        continue_btn = MagicMock()
        continue_btn.is_visible.return_value = True
        submit_btn = MagicMock()
        submit_btn.is_visible.return_value = True
        step = {"n": 0}

        def qs(selector):
            if "indeedApply" in selector or "Apply now" in selector:
                return apply_btn
            if "captcha" in selector or "recaptcha" in selector or "sitekey" in selector:
                return None
            step["n"] += 1
            if "Submit" in selector or "submit" in selector:
                if step["n"] > 4:
                    return submit_btn
                return None
            if "continueButton" in selector or "Continue" in selector or "continue" in selector:
                return continue_btn
            return None

        page.query_selector.side_effect = qs
        applier = IndeedApplier(page)
        job = _make_scored_job("https://www.indeed.com/viewjob?jk=abc", "indeed")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is True
        assert continue_btn.click.call_count >= 1

    @patch("bot.apply.base.time.sleep")
    def test_fill_form_fills_empty_fields(self, _sleep):
        """Lines 152-153: form fields filled when empty."""
        page = _make_page()
        name_input = MagicMock()
        name_input.input_value.return_value = ""
        email_input = MagicMock()
        email_input.input_value.return_value = ""
        phone_input = MagicMock()
        phone_input.input_value.return_value = ""

        def qs(selector):
            if "email" in selector:
                return email_input
            if "phone" in selector:
                return phone_input
            if "name" in selector:
                return name_input
            return None

        page.query_selector.side_effect = qs
        applier = IndeedApplier(page)
        applier._fill_form_fields(_make_profile(full_name="Jane Doe"))
        assert name_input.type.call_count == len("Jane Doe")

    @patch("bot.apply.base.time.sleep")
    def test_upload_resume_success(self, _sleep):
        """Line 164: file input found and resume uploaded."""
        page = _make_page()
        fi = MagicMock()

        def qs(selector):
            if "file" in selector:
                return fi
            return None

        page.query_selector.side_effect = qs
        applier = IndeedApplier(page)
        applier._upload_resume(Path("/tmp/resume.pdf"))
        fi.set_input_files.assert_called_once_with(str(Path("/tmp/resume.pdf")))

    @patch("bot.apply.base.time.sleep")
    def test_captcha_in_loop_precise(self, _sleep):
        """Line 98: CAPTCHA detected inside the for-loop (not at start)."""
        page = _make_page("https://www.indeed.com/viewjob?jk=abc")
        apply_btn = MagicMock()
        loop_entered = {"v": False}

        def qs(selector):
            if "indeedApply" in selector or "Apply now" in selector:
                if not loop_entered["v"]:
                    return apply_btn
                return None
            if "captcha" in selector or "recaptcha" in selector or "sitekey" in selector:
                if loop_entered["v"]:
                    return MagicMock()
                return None
            return None

        page.query_selector.side_effect = qs
        def on_click():
            loop_entered["v"] = True
        apply_btn.click.side_effect = on_click

        applier = IndeedApplier(page)
        job = _make_scored_job("https://www.indeed.com/viewjob?jk=abc", "indeed")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is False
        assert result.captcha_detected is True
        assert "application form" in result.error_message

    @patch("bot.apply.base.time.sleep")
    def test_resume_upload_in_loop(self, _sleep):
        """Line 108: resume uploaded inside multi-step loop."""
        page = _make_page("https://www.indeed.com/viewjob?jk=abc")
        apply_btn = MagicMock()
        submit_btn = MagicMock()
        submit_btn.is_visible.return_value = True
        fi = MagicMock()

        def qs(selector):
            if "indeedApply" in selector or "Apply now" in selector:
                return apply_btn
            if "captcha" in selector or "recaptcha" in selector or "sitekey" in selector:
                return None
            if "file" in selector:
                return fi
            if "Submit" in selector or "submit" in selector:
                return submit_btn
            return None

        page.query_selector.side_effect = qs
        applier = IndeedApplier(page)
        job = _make_scored_job("https://www.indeed.com/viewjob?jk=abc", "indeed")
        result = applier.apply(job, Path("/tmp/resume.pdf"), "", _make_profile())
        assert result.success is True
        fi.set_input_files.assert_called()


# ===================================================================
# Greenhouse — uncovered branches
# ===================================================================


class TestGreenhouseFormFieldsBranches:
    """FR-057: Greenhouse form field filling — uncovered branches."""

    @patch("bot.apply.base.time.sleep")
    def test_fills_linkedin_url(self, _sleep):
        page = _make_page()
        li_input = MagicMock()
        li_input.input_value.return_value = ""

        def qs(selector):
            if "linkedin" in selector.lower():
                return li_input
            return None

        page.query_selector.side_effect = qs
        applier = GreenhouseApplier(page)
        profile = _make_profile(linkedin_url="https://linkedin.com/in/alice")
        applier._fill_form_fields(profile)
        assert li_input.type.call_count == len("https://linkedin.com/in/alice")

    @patch("bot.apply.base.time.sleep")
    def test_skips_linkedin_when_no_url(self, _sleep):
        page = _make_page()
        applier = GreenhouseApplier(page)
        profile = _make_profile(linkedin_url="")
        applier._fill_form_fields(profile)

    @patch("bot.apply.base.time.sleep")
    def test_skips_field_when_value_empty(self, _sleep):
        page = _make_page()
        applier = GreenhouseApplier(page)
        profile = _make_profile(first_name="", last_name="", email="", phone_full="")
        applier._fill_form_fields(profile)

    @patch("bot.apply.base.time.sleep")
    def test_resume_upload_exception_handled(self, _sleep):
        page = _make_page()
        fi = MagicMock()
        fi.set_input_files.side_effect = Exception("Upload failed")
        page.query_selector.return_value = fi
        applier = GreenhouseApplier(page)
        applier._upload_resume(Path("/tmp/resume.pdf"))

    @patch("bot.apply.base.time.sleep")
    def test_resume_upload_no_input(self, _sleep):
        page = _make_page()
        page.query_selector.return_value = None
        applier = GreenhouseApplier(page)
        applier._upload_resume(Path("/tmp/resume.pdf"))

    @patch("bot.apply.base.time.sleep")
    def test_cover_letter_empty_noop(self, _sleep):
        page = _make_page()
        applier = GreenhouseApplier(page)
        applier._fill_cover_letter("")
        page.query_selector.assert_not_called()

    @patch("bot.apply.base.time.sleep")
    def test_cover_letter_skips_prefilled(self, _sleep):
        page = _make_page()
        ta = MagicMock()
        ta.input_value.return_value = "Already filled"

        def qs(selector):
            if "cover" in selector:
                return ta
            return None

        page.query_selector.side_effect = qs
        applier = GreenhouseApplier(page)
        applier._fill_cover_letter("New text")
        ta.fill.assert_not_called()

    @patch("bot.apply.base.time.sleep")
    def test_apply_button_click(self, _sleep):
        """Greenhouse apply button found and clicked before form."""
        page = _make_page()
        apply_btn = MagicMock()
        apply_btn.is_visible.return_value = True
        submit_btn = MagicMock()

        def qs(selector):
            if "apply_button" in selector or "apply" in selector.lower() and "btn" in selector:
                return apply_btn
            if "submit" in selector.lower():
                return submit_btn
            if "error" in selector.lower():
                return None
            return None

        page.query_selector.side_effect = qs
        applier = GreenhouseApplier(page)
        job = _make_scored_job("https://boards.greenhouse.io/acme/jobs/123", "greenhouse")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is True


# ===================================================================
# Lever — uncovered branches
# ===================================================================


class TestLeverFormFieldsBranches:
    """FR-058: Lever form field filling — uncovered branches."""

    @patch("bot.apply.base.time.sleep")
    def test_fills_linkedin_url(self, _sleep):
        page = _make_page()
        li_input = MagicMock()
        li_input.input_value.return_value = ""

        def qs(selector):
            if "linkedin" in selector.lower():
                return li_input
            return None

        page.query_selector.side_effect = qs
        applier = LeverApplier(page)
        profile = _make_profile(linkedin_url="https://linkedin.com/in/alice")
        applier._fill_form_fields(profile)
        assert li_input.type.call_count == len("https://linkedin.com/in/alice")

    @patch("bot.apply.base.time.sleep")
    def test_fills_portfolio_url(self, _sleep):
        page = _make_page()
        web_input = MagicMock()
        web_input.input_value.return_value = ""

        def qs(selector):
            if "Portfolio" in selector or "website" in selector or "Other" in selector:
                return web_input
            return None

        page.query_selector.side_effect = qs
        applier = LeverApplier(page)
        profile = _make_profile(portfolio_url="https://janedoe.dev")
        applier._fill_form_fields(profile)
        assert web_input.type.call_count == len("https://janedoe.dev")

    @patch("bot.apply.base.time.sleep")
    def test_skips_empty_linkedin(self, _sleep):
        page = _make_page()
        applier = LeverApplier(page)
        profile = _make_profile(linkedin_url="")
        applier._fill_form_fields(profile)

    @patch("bot.apply.base.time.sleep")
    def test_skips_empty_portfolio(self, _sleep):
        page = _make_page()
        applier = LeverApplier(page)
        profile = _make_profile(portfolio_url="")
        applier._fill_form_fields(profile)

    @patch("bot.apply.base.time.sleep")
    def test_resume_upload_exception_handled(self, _sleep):
        page = _make_page()
        fi = MagicMock()
        fi.set_input_files.side_effect = Exception("Upload failed")
        page.query_selector.return_value = fi
        applier = LeverApplier(page)
        applier._upload_resume(Path("/tmp/resume.pdf"))

    @patch("bot.apply.base.time.sleep")
    def test_resume_upload_no_input(self, _sleep):
        page = _make_page()
        page.query_selector.return_value = None
        applier = LeverApplier(page)
        applier._upload_resume(Path("/tmp/resume.pdf"))

    @patch("bot.apply.base.time.sleep")
    def test_cover_letter_empty_noop(self, _sleep):
        page = _make_page()
        applier = LeverApplier(page)
        applier._fill_cover_letter("")
        page.query_selector.assert_not_called()

    @patch("bot.apply.base.time.sleep")
    def test_cover_letter_skips_prefilled(self, _sleep):
        page = _make_page()
        ta = MagicMock()
        ta.input_value.return_value = "Already filled"

        def qs(selector):
            if "comments" in selector or "cover" in selector:
                return ta
            return None

        page.query_selector.side_effect = qs
        applier = LeverApplier(page)
        applier._fill_cover_letter("New text")
        ta.fill.assert_not_called()


# ===================================================================
# Workday — uncovered branches
# ===================================================================


class TestWorkdayDropdownBranches:
    """FR-070: Workday dropdown — uncovered edge cases."""

    @patch("bot.apply.base.time.sleep")
    def test_dropdown_listbox_timeout(self, _sleep):
        """Listbox never appears — should handle gracefully."""
        page = _make_page()
        btn = MagicMock()
        btn.is_visible.return_value = True

        def qs(selector):
            if "gender" in selector:
                return btn
            return None

        page.query_selector.side_effect = qs
        page.wait_for_selector.side_effect = Exception("Timeout waiting for listbox")

        applier = WorkdayApplier(page)
        applier._select_dropdown("gender", "Male")
        btn.click.assert_called_once()

    @patch("bot.apply.base.time.sleep")
    def test_dropdown_option_not_visible(self, _sleep):
        """Option found but not visible — should not click."""
        page = _make_page()
        btn = MagicMock()
        btn.is_visible.return_value = True
        option = MagicMock()
        option.is_visible.return_value = False

        def qs(selector):
            if "listbox" in selector and "option" in selector:
                return option
            if "gender" in selector:
                return btn
            return None

        page.query_selector.side_effect = qs
        applier = WorkdayApplier(page)
        applier._select_dropdown("gender", "Male")
        option.click.assert_not_called()

    @patch("bot.apply.base.time.sleep")
    def test_dropdown_no_matching_option(self, _sleep):
        """No option matches the value — should not crash."""
        page = _make_page()
        btn = MagicMock()
        btn.is_visible.return_value = True

        def qs(selector):
            if "gender" in selector:
                return btn
            return None

        page.query_selector.side_effect = qs
        applier = WorkdayApplier(page)
        applier._select_dropdown("gender", "Nonexistent")


class TestWorkdayIsSubmittedException:
    """FR-070: _is_submitted exception handling."""

    @patch("bot.apply.base.time.sleep")
    def test_exception_in_selector(self, _sleep):
        page = _make_page()
        el = MagicMock()
        el.is_visible.side_effect = Exception("Element detached")

        page.query_selector.return_value = el
        applier = WorkdayApplier(page)
        result = applier._is_submitted()
        # Should not crash, returns False eventually
        assert isinstance(result, bool)


class TestWorkdayGetPageErrorsBranches:
    """FR-070: _get_page_errors — error reading text."""

    @patch("bot.apply.base.time.sleep")
    def test_inner_text_exception(self, _sleep):
        page = _make_page()
        err = MagicMock()
        err.is_visible.return_value = True
        err.inner_text.side_effect = Exception("detached")

        def qs(selector):
            if "errorMessage" in selector:
                return err
            return None

        page.query_selector.side_effect = qs
        applier = WorkdayApplier(page)
        result = applier._get_page_errors()
        assert result == "Unknown error"


class TestWorkdayScreeningLabelException:
    """FR-070: label inner_text failure in screening questions."""

    @patch("bot.apply.base.time.sleep")
    def test_label_inner_text_exception(self, _sleep):
        page = _make_page()
        label = MagicMock()
        label.inner_text.side_effect = Exception("detached")
        page.query_selector_all.return_value = [label]

        profile = _make_profile(screening_answers={"work_authorization": "Yes"})
        applier = WorkdayApplier(page)
        applier._answer_screening_questions(profile)
        # Should not crash


class TestWorkdayClickApplyFallback:
    """FR-070: Apply button fallback to text match."""

    @patch("bot.apply.base.time.sleep")
    def test_fallback_apply_link(self, _sleep):
        page = _make_page()
        apply_el = MagicMock()
        apply_el.is_visible.return_value = True

        call_count = {"n": 0}

        def qs(selector):
            call_count["n"] += 1
            # First 4 calls (data-automation-id selectors) return None
            if call_count["n"] <= 4:
                return None
            if "Apply" in selector:
                return apply_el
            return None

        page.query_selector.side_effect = qs
        applier = WorkdayApplier(page)
        assert applier._click_apply_button() is True
        apply_el.click.assert_called_once()


class TestWorkdayAuthPassword:
    """FR-070: Auth page with password filling."""

    @patch("bot.apply.base.time.sleep")
    def test_fill_password_from_screening_answers(self, _sleep):
        page = _make_page()
        email_input = MagicMock()
        email_input.input_value.return_value = ""
        pw_input = MagicMock()
        signin_btn = MagicMock()
        signin_btn.is_visible.return_value = True

        def qs(selector):
            if "createAccountLink" in selector:
                return MagicMock()
            if 'data-automation-id="email"' in selector:
                return email_input
            if 'data-automation-id="password"' in selector or "password" in selector:
                return pw_input
            if "signInSubmitButton" in selector or "createAccountSubmitButton" in selector:
                return signin_btn
            return None

        page.query_selector.side_effect = qs
        profile = _make_profile(
            email="test@corp.com",
            screening_answers={"workday_password": "Secret123!"},
        )
        applier = WorkdayApplier(page)
        applier._handle_auth_page(profile)
        assert pw_input.type.call_count == len("Secret123!")


class TestWorkdayFillMyInformationDropdowns:
    """FR-070: Country and state dropdown calls."""

    @patch("bot.apply.base.time.sleep")
    def test_country_dropdown_called(self, _sleep):
        page = _make_page()
        page.query_selector.return_value = None
        applier = WorkdayApplier(page)
        profile = _make_profile(country="United States", state="NY")
        with patch.object(applier, "_select_dropdown") as mock_dd:
            applier._fill_my_information(profile)
            assert mock_dd.call_count == 2
            mock_dd.assert_any_call("country", "United States")
            mock_dd.assert_any_call("addressSection_countryRegion", "NY")

    @patch("bot.apply.base.time.sleep")
    def test_no_country_skips_dropdown(self, _sleep):
        page = _make_page()
        page.query_selector.return_value = None
        applier = WorkdayApplier(page)
        profile = _make_profile(country="", state="")
        with patch.object(applier, "_select_dropdown") as mock_dd:
            applier._fill_my_information(profile)
            mock_dd.assert_not_called()


class TestWorkdayFillMyExperienceException:
    """FR-070: Resume upload exception in Workday."""

    @patch("bot.apply.base.time.sleep")
    def test_upload_exception_handled(self, _sleep):
        page = _make_page()
        fi = MagicMock()
        fi.set_input_files.side_effect = Exception("Upload failed")

        def qs(selector):
            if "file" in selector:
                return fi
            return None

        page.query_selector.side_effect = qs
        applier = WorkdayApplier(page)
        applier._fill_my_experience(_make_profile(), Path("/tmp/resume.pdf"))
        # Should not raise


class TestWorkdayMultipleTextareas:
    """FR-070: Multiple textareas — only first gets cover letter."""

    @patch("bot.apply.base.time.sleep")
    def test_only_first_textarea_filled(self, _sleep):
        page = _make_page()
        ta1 = MagicMock()
        ta1.is_visible.return_value = True
        ta1.input_value.return_value = ""
        ta2 = MagicMock()
        ta2.is_visible.return_value = True
        ta2.input_value.return_value = ""
        page.query_selector_all.return_value = [ta1, ta2]

        applier = WorkdayApplier(page)
        applier._fill_application_questions(_make_profile(), "My cover letter")
        ta1.fill.assert_called_once_with("My cover letter")
        ta2.fill.assert_not_called()


class TestWorkdayVoluntaryEmpty:
    """FR-070: Voluntary disclosures with empty answers."""

    @patch("bot.apply.base.time.sleep")
    def test_empty_answers_skips_dropdowns(self, _sleep):
        page = _make_page()
        applier = WorkdayApplier(page)
        profile = _make_profile(screening_answers={})
        with patch.object(applier, "_select_dropdown") as mock_dd:
            applier._fill_voluntary_disclosures(profile)
            mock_dd.assert_not_called()

    @patch("bot.apply.base.time.sleep")
    def test_self_id_empty_skips(self, _sleep):
        page = _make_page()
        applier = WorkdayApplier(page)
        profile = _make_profile(screening_answers={})
        with patch.object(applier, "_select_dropdown") as mock_dd:
            applier._fill_self_identification(profile)
            mock_dd.assert_not_called()


# ===================================================================
# Ashby — uncovered branches
# ===================================================================


class TestAshbyFormFieldsBranches:
    """FR-071: Ashby form field filling — uncovered branches."""

    @patch("bot.apply.base.time.sleep")
    def test_fills_portfolio_url(self, _sleep):
        page = _make_page()
        web_input = MagicMock()
        web_input.is_visible.return_value = True
        web_input.input_value.return_value = ""

        def qs(selector):
            if "website" in selector.lower() or "portfolio" in selector.lower():
                return web_input
            return None

        page.query_selector.side_effect = qs
        applier = AshbyApplier(page)
        profile = _make_profile(portfolio_url="https://janedoe.dev")
        applier._fill_form_fields(profile)
        assert web_input.type.call_count == len("https://janedoe.dev")

    @patch("bot.apply.base.time.sleep")
    def test_fills_location(self, _sleep):
        page = _make_page()
        loc_input = MagicMock()
        loc_input.is_visible.return_value = True
        loc_input.input_value.return_value = ""

        def qs(selector):
            if "location" in selector.lower():
                return loc_input
            return None

        page.query_selector.side_effect = qs
        applier = AshbyApplier(page)
        profile = _make_profile(location="San Francisco, CA")
        applier._fill_form_fields(profile)
        assert loc_input.type.call_count == len("San Francisco, CA")

    @patch("bot.apply.base.time.sleep")
    def test_skips_empty_portfolio(self, _sleep):
        page = _make_page()
        applier = AshbyApplier(page)
        profile = _make_profile(portfolio_url="")
        applier._fill_form_fields(profile)

    @patch("bot.apply.base.time.sleep")
    def test_skips_hidden_location(self, _sleep):
        page = _make_page()
        loc_input = MagicMock()
        loc_input.is_visible.return_value = False

        def qs(selector):
            if "location" in selector.lower():
                return loc_input
            return None

        page.query_selector.side_effect = qs
        applier = AshbyApplier(page)
        profile = _make_profile()
        applier._fill_form_fields(profile)
        loc_input.type.assert_not_called()


class TestAshbyCustomQuestionsBranches:
    """FR-071: Ashby custom questions — uncovered branches."""

    @patch("bot.apply.base.time.sleep")
    def test_label_inner_text_exception(self, _sleep):
        page = _make_page()
        label = MagicMock()
        label.inner_text.side_effect = Exception("detached")
        page.query_selector_all.return_value = [label]

        profile = _make_profile(screening_answers={"work auth": "Yes"})
        applier = AshbyApplier(page)
        applier._answer_custom_questions(profile)
        # Should not crash

    @patch("bot.apply.base.time.sleep")
    def test_label_no_for_attribute(self, _sleep):
        page = _make_page()
        label = MagicMock()
        label.inner_text.return_value = "Years of experience"
        label.get_attribute.return_value = None  # no "for" attribute
        page.query_selector_all.return_value = [label]

        profile = _make_profile(screening_answers={"years of experience": "5"})
        applier = AshbyApplier(page)
        applier._answer_custom_questions(profile)
        # Should not crash, no input found

    @patch("bot.apply.base.time.sleep")
    def test_input_not_visible(self, _sleep):
        page = _make_page()
        label = MagicMock()
        label.inner_text.return_value = "Years of experience"
        label.get_attribute.return_value = "exp-input"
        page.query_selector_all.return_value = [label]

        inp = MagicMock()
        inp.is_visible.return_value = False

        def qs(selector):
            if "#exp-input" in selector:
                return inp
            return None

        page.query_selector.side_effect = qs
        profile = _make_profile(screening_answers={"years of experience": "5"})
        applier = AshbyApplier(page)
        applier._answer_custom_questions(profile)
        inp.type.assert_not_called()

    @patch("bot.apply.base.time.sleep")
    def test_input_already_filled(self, _sleep):
        page = _make_page()
        label = MagicMock()
        label.inner_text.return_value = "Years of experience"
        label.get_attribute.return_value = "exp-input"
        page.query_selector_all.return_value = [label]

        inp = MagicMock()
        inp.is_visible.return_value = True
        inp.input_value.return_value = "3"  # already filled

        def qs(selector):
            if "#exp-input" in selector:
                return inp
            return None

        page.query_selector.side_effect = qs
        profile = _make_profile(screening_answers={"years of experience": "5"})
        applier = AshbyApplier(page)
        applier._answer_custom_questions(profile)
        inp.type.assert_not_called()


class TestAshbyCoverLetterBranches:
    """FR-071: Ashby cover letter — additional info textarea not visible."""

    @patch("bot.apply.base.time.sleep")
    def test_additional_info_not_visible_skips(self, _sleep):
        page = _make_page()
        ta = MagicMock()
        ta.is_visible.return_value = False

        def qs(selector):
            if "additional" in selector.lower():
                return ta
            return None

        page.query_selector.side_effect = qs
        applier = AshbyApplier(page)
        applier._fill_cover_letter("Text")
        ta.fill.assert_not_called()

    @patch("bot.apply.base.time.sleep")
    def test_additional_info_already_filled(self, _sleep):
        page = _make_page()
        ta = MagicMock()
        ta.is_visible.return_value = True
        ta.input_value.return_value = "Already filled"

        def qs(selector):
            if "additional" in selector.lower():
                return ta
            return None

        page.query_selector.side_effect = qs
        applier = AshbyApplier(page)
        applier._fill_cover_letter("Text")
        ta.fill.assert_not_called()


class TestAshbyApplyBtnClick:
    """FR-071: Ashby Apply button before form."""

    @patch("bot.apply.base.time.sleep")
    def test_apply_button_clicked(self, _sleep):
        page = _make_page("https://jobs.ashbyhq.com/acme/app/123")
        apply_btn = MagicMock()
        apply_btn.is_visible.return_value = True
        submit_btn = MagicMock()
        success_el = MagicMock()

        def qs(selector):
            # CAPTCHA selectors — not present
            if "captcha" in selector or "recaptcha" in selector or "sitekey" in selector:
                return None
            # Apply button on detail page
            if "Apply" in selector and 'type="submit"' not in selector:
                return apply_btn
            if 'type="submit"' in selector:
                return submit_btn
            if "submitted" in selector.lower() or "Thank" in selector:
                return success_el
            return None

        page.query_selector.side_effect = qs
        applier = AshbyApplier(page)
        job = _make_scored_job("https://jobs.ashbyhq.com/acme/app/123", "ashby")
        result = applier.apply(job, None, "", _make_profile())
        assert result.success is True
        apply_btn.click.assert_called_once()


class TestAshbyResumeUploadException:
    """FR-071: Ashby resume upload exception."""

    @patch("bot.apply.base.time.sleep")
    def test_upload_exception_handled(self, _sleep):
        page = _make_page()
        fi = MagicMock()
        fi.set_input_files.side_effect = Exception("Upload failed")

        def qs(selector):
            if 'type="file"' in selector:
                return fi
            return None

        page.query_selector.side_effect = qs
        applier = AshbyApplier(page)
        applier._upload_resume(Path("/tmp/resume.pdf"))
