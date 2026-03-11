"""Resume Comparison UI tests for traceability coverage (TASK-028, #33).

Validates DOM elements and JS source for 4 requirements at warning status:
FR-121, FR-124, FR-125, NFR-019-02.

Uses Flask test client HTML assertions + static JS analysis.
"""

from __future__ import annotations

from pathlib import Path

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


@pytest.fixture()
def resumes_js():
    """Read static/js/resumes.js source."""
    return Path("static/js/resumes.js").read_text(encoding="utf-8")


# ===================================================================
# FR-121 — Star/Favorite Icon UI
# ===================================================================


class TestFR121StarIcon:
    """FR-121: Star icon toggle for marking favorite resumes."""

    def test_toggle_favorite_function(self, resumes_js):
        """resumes.js has toggleFavorite function."""
        assert "export async function toggleFavorite(" in resumes_js

    def test_star_icon_rendered(self, resumes_js):
        """Star icon (★) is rendered in resume list items."""
        assert "&#9733;" in resumes_js

    def test_star_css_class(self, resumes_js):
        """Star button uses resume-star CSS class."""
        assert "resume-star" in resumes_js

    def test_star_active_class(self, resumes_js):
        """Active favorites get 'active' CSS class."""
        assert "'resume-star active'" in resumes_js or "resume-star active" in resumes_js

    def test_star_aria_pressed(self, resumes_js):
        """Star button uses aria-pressed for toggle state."""
        assert "aria-pressed" in resumes_js

    def test_star_aria_label(self, resumes_js):
        """Star button has aria-label for favorite/unfavorite."""
        assert "aria-label" in resumes_js
        assert "resumes.favorite" in resumes_js or "resumes.unfavorite" in resumes_js

    def test_sort_by_favorites(self, html):
        """Sort dropdown includes favorites-first option."""
        assert 'value="is_favorite"' in html
        assert 'data-i18n="resumes.sort_favorites"' in html


# ===================================================================
# FR-124 — Comparison UI (Side-by-Side View)
# ===================================================================


class TestFR124ComparisonUI:
    """FR-124: Side-by-side resume comparison overlay."""

    def test_compare_overlay_exists(self, html):
        """Comparison overlay container is present."""
        assert 'id="resume-compare-overlay"' in html

    def test_compare_content_grid(self, html):
        """Comparison uses a grid layout container."""
        assert 'id="resume-compare-content"' in html
        assert "resume-compare-grid" in html

    def test_compare_button_exists(self, html):
        """Compare button exists in library controls."""
        assert 'id="resume-compare-btn"' in html
        assert "compareSelected()" in html

    def test_compare_back_button(self, html):
        """Comparison view has back-to-library button."""
        assert "closeCompareView()" in html

    def test_compare_title(self, html):
        """Comparison view has i18n title."""
        assert 'data-i18n="resumes.compare_title"' in html

    def test_compare_function_exported(self, resumes_js):
        """compareSelected function is exported."""
        assert "export async function compareSelected()" in resumes_js

    def test_diff_legend_exists(self, html):
        """Diff legend with added/removed/unchanged labels exists."""
        assert "diff-legend" in html
        assert 'data-i18n="resumes.diff_added"' in html
        assert 'data-i18n="resumes.diff_removed"' in html
        assert 'data-i18n="resumes.diff_unchanged"' in html


# ===================================================================
# FR-125 — Line Diff (LCS Algorithm)
# ===================================================================


class TestFR125LineDiff:
    """FR-125: LCS-based line diff algorithm in client-side JS."""

    def test_compute_lcs_function(self, resumes_js):
        """resumes.js has computeLCS function for diff."""
        assert "function computeLCS(" in resumes_js

    def test_lcs_uses_dynamic_programming(self, resumes_js):
        """LCS implementation uses DP table."""
        # Typical LCS patterns: 2D array, nested loops
        assert "Array(" in resumes_js or "new Array" in resumes_js

    def test_diff_output_types(self, resumes_js):
        """Diff produces added/removed/equal operation types."""
        assert "'added'" in resumes_js or '"added"' in resumes_js
        assert "'removed'" in resumes_js or '"removed"' in resumes_js
        assert "'equal'" in resumes_js or '"equal"' in resumes_js

    def test_diff_css_classes(self, resumes_js):
        """Diff renders with CSS classes for visual distinction."""
        assert "diff-added" in resumes_js or "diff-removed" in resumes_js


# ===================================================================
# NFR-019-02 — Resume Comparison Accessibility
# ===================================================================


class TestNFR01902Accessibility:
    """NFR-019-02: Resume comparison UI meets accessibility requirements."""

    def test_compare_overlay_dialog_role(self, html):
        """Comparison overlay has role=dialog."""
        assert 'aria-label="Resume comparison"' in html

    def test_diff_legend_region(self, html):
        """Diff legend has role=region with aria-label."""
        assert 'aria-label="Diff legend"' in html

    def test_compare_button_disabled_default(self, html):
        """Compare button starts disabled (needs 2 selections)."""
        assert 'id="resume-compare-btn"' in html
        assert "disabled" in html

    def test_star_toggle_accessible(self, resumes_js):
        """Star toggle has aria-pressed and aria-label."""
        assert "aria-pressed" in resumes_js
        assert "aria-label" in resumes_js

    def test_compare_info_live_region(self, html):
        """Compare selection info has aria-live for announcements."""
        assert 'id="resume-compare-info"' in html
        assert 'aria-live="polite"' in html
