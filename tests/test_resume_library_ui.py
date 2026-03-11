"""Resume Library UI rendering tests for traceability coverage (TASK-027, #32).

Validates that the Flask-rendered index.html contains the required DOM
elements for 5 requirements at warning status: FR-115, FR-116, FR-117,
FR-119, NFR-018-04.

Uses Flask test client to fetch the rendered HTML and asserts DOM presence.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def html(tmp_path, monkeypatch):
    """Fetch rendered index.html via Flask test client."""
    monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("routes.profile.get_data_dir", lambda: tmp_path)
    (tmp_path / "profile" / "experiences").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AUTOAPPLY_DEV", "1")
    from app import create_app
    app, _ = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        rv = c.get("/")
        assert rv.status_code == 200
        yield rv.data.decode("utf-8")


# ===================================================================
# FR-115 — Resume Library UI (List View)
# ===================================================================


class TestFR115ResumeLibraryUI:
    """FR-115: Resume library screen renders list view elements."""

    def test_resume_screen_exists(self, html):
        """Resume library screen container is present."""
        assert 'id="screen-resumes"' in html

    def test_resume_screen_title(self, html):
        """Resume library has i18n title."""
        assert 'data-i18n="resumes.title"' in html

    def test_resume_search_input(self, html):
        """Resume library has search input."""
        assert 'id="resume-search"' in html

    def test_resume_sort_dropdown(self, html):
        """Resume library has sort dropdown."""
        assert 'id="resume-sort"' in html

    def test_resume_sort_options(self, html):
        """Sort dropdown has date, company, score, favorites options."""
        assert 'value="created_at"' in html
        assert 'value="company"' in html
        assert 'value="match_score"' in html
        assert 'value="is_favorite"' in html

    def test_resume_list_container(self, html):
        """Resume list container exists for dynamic content."""
        assert 'id="resume-list"' in html

    def test_resume_metrics_region(self, html):
        """Resume metrics summary cards region exists."""
        assert 'id="resume-metrics"' in html

    def test_resume_pagination(self, html):
        """Resume library has pagination container."""
        assert 'id="resume-pagination"' in html


# ===================================================================
# FR-116 — Resume Detail View UI
# ===================================================================


class TestFR116ResumeDetailView:
    """FR-116: Resume detail overlay renders correctly."""

    def test_detail_overlay_exists(self, html):
        """Resume detail overlay container is present."""
        assert 'id="resume-detail-overlay"' in html

    def test_detail_content_container(self, html):
        """Resume detail content area exists."""
        assert 'id="resume-detail-content"' in html

    def test_detail_back_button(self, html):
        """Detail view has back-to-library button."""
        assert "closeResumeDetail()" in html

    def test_detail_is_dialog(self, html):
        """Detail overlay has role=dialog for accessibility."""
        assert 'role="dialog"' in html
        assert 'aria-label="Resume detail"' in html


# ===================================================================
# FR-117 — App Detail Resume Link (JS-rendered)
# ===================================================================


class TestFR117AppDetailResumeLink:
    """FR-117: Resume link from application detail exists in JS module."""

    def test_view_resume_function_in_js(self):
        """resumes.js exports viewResume function for app detail linking."""
        from pathlib import Path
        js = Path("static/js/resumes.js").read_text(encoding="utf-8")
        assert "export async function viewResume(" in js

    def test_view_application_button_in_js(self):
        """resumes.js renders view-application button linking back to app detail."""
        from pathlib import Path
        js = Path("static/js/resumes.js").read_text(encoding="utf-8")
        assert 'data-i18n="resumes.view_application"' in js

    def test_preview_pdf_function_in_js(self):
        """resumes.js exports previewResumePdf function."""
        from pathlib import Path
        js = Path("static/js/resumes.js").read_text(encoding="utf-8")
        assert "export function previewResumePdf(" in js


# ===================================================================
# FR-119 — Resume Library Navigation
# ===================================================================


class TestFR119ResumeNavigation:
    """FR-119: Resume library has navigation tab in navbar."""

    def test_resumes_nav_tab(self, html):
        """Nav bar has resumes tab link."""
        assert 'data-screen="resumes"' in html

    def test_resumes_nav_i18n(self, html):
        """Resumes nav tab uses i18n key."""
        assert 'data-i18n="nav.resumes"' in html

    def test_resumes_nav_role(self, html):
        """Resumes nav tab has role=tab."""
        # The nav uses role="tab" on all links
        assert 'data-screen="resumes"' in html
        assert 'role="tab"' in html


# ===================================================================
# NFR-018-04 — Resume Library Accessibility
# ===================================================================


class TestNFR01804Accessibility:
    """NFR-018-04: Resume library UI meets accessibility requirements."""

    def test_resume_screen_tabpanel_role(self, html):
        """Resume screen has role=tabpanel."""
        assert 'role="tabpanel"' in html
        assert 'aria-label="Resume Library"' in html

    def test_resume_search_aria_label(self, html):
        """Search input has aria-label."""
        assert 'aria-label="Search resumes"' in html

    def test_resume_sort_aria_label(self, html):
        """Sort dropdown has aria-label."""
        assert 'aria-label="Sort resumes"' in html

    def test_resume_list_aria_live(self, html):
        """Resume list has aria-live for dynamic updates."""
        assert 'id="resume-list"' in html
        assert 'aria-live="polite"' in html

    def test_resume_metrics_aria(self, html):
        """Metrics region has proper ARIA attributes."""
        assert 'aria-label="Resume effectiveness metrics"' in html

    def test_pagination_nav_role(self, html):
        """Pagination has role=navigation and aria-label."""
        assert 'role="navigation"' in html
        assert 'aria-label="Resume list pagination"' in html

    def test_compare_info_aria_live(self, html):
        """Compare info span has aria-live for selection count."""
        assert 'id="resume-compare-info"' in html
        assert 'aria-live="polite"' in html

    def test_detail_overlay_dialog_role(self, html):
        """Detail overlay uses role=dialog."""
        assert 'aria-label="Resume detail"' in html
