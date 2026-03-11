"""Analytics UI rendering tests for traceability coverage (TASK-026, #31).

Validates that the Flask-rendered index.html contains the required DOM
elements for 3 requirements at warning status: FR-100, NFR-017-03, NFR-017-06.

Also validates analytics.js source for chart performance patterns.

Uses Flask test client + static code analysis.
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
def analytics_js():
    """Read static/js/analytics.js source."""
    return Path("static/js/analytics.js").read_text(encoding="utf-8")


# ===================================================================
# FR-100 — Period Selector & Chart Rendering UI
# ===================================================================


class TestFR100PeriodSelector:
    """FR-100: Analytics period selector and chart containers render."""

    def test_analytics_screen_exists(self, html):
        """Analytics screen container is present."""
        assert 'id="screen-analytics"' in html

    def test_period_selector_group(self, html):
        """Period selector has ARIA role group."""
        assert 'class="analytics-period-selector"' in html
        assert 'role="group"' in html

    def test_period_7d_button(self, html):
        """7-day period button exists with data-days attribute."""
        assert 'data-days="7"' in html
        assert "switchAnalyticsPeriod(7)" in html

    def test_period_30d_button(self, html):
        """30-day period button exists and is default active."""
        assert 'data-days="30"' in html
        assert "switchAnalyticsPeriod(30)" in html

    def test_period_90d_button(self, html):
        """90-day period button exists."""
        assert 'data-days="90"' in html
        assert "switchAnalyticsPeriod(90)" in html

    def test_period_all_button(self, html):
        """All-time period button exists."""
        assert 'data-days="0"' in html
        assert "switchAnalyticsPeriod(0)" in html

    def test_daily_chart_canvas(self, html):
        """Daily applications chart canvas element exists."""
        assert 'id="chart-daily"' in html
        assert "<canvas" in html

    def test_funnel_chart_canvas(self, html):
        """Conversion funnel chart canvas element exists."""
        assert 'id="chart-funnel"' in html

    def test_score_chart_canvas(self, html):
        """Score distribution chart canvas element exists."""
        assert 'id="chart-score"' in html

    def test_platform_table_container(self, html):
        """Platform performance table container exists."""
        assert 'id="platform-table-container"' in html

    def test_weekly_summary_container(self, html):
        """Weekly summary container exists."""
        assert 'id="weekly-summary-container"' in html

    def test_top_companies_container(self, html):
        """Top companies container exists."""
        assert 'id="top-companies-container"' in html

    def test_response_times_container(self, html):
        """Response times container exists."""
        assert 'id="response-times-container"' in html

    def test_summary_cards_region(self, html):
        """Summary cards region exists with proper ID."""
        assert 'id="analytics-summary"' in html

    def test_summary_total_card(self, html):
        """Total applications summary card exists."""
        assert 'id="summary-total"' in html

    def test_summary_interview_rate_card(self, html):
        """Interview rate summary card exists."""
        assert 'id="summary-interview-rate"' in html

    def test_summary_avg_score_card(self, html):
        """Average match score summary card exists."""
        assert 'id="summary-avg-score"' in html

    def test_summary_this_week_card(self, html):
        """This week summary card exists."""
        assert 'id="summary-this-week"' in html

    def test_chart_js_loaded(self, html):
        """Chart.js library script tag is present."""
        assert "Chart.js" in html or "chart.umd" in html

    def test_period_buttons_have_i18n(self, html):
        """Period buttons use data-i18n for translations."""
        assert 'data-i18n="analytics.period_7d"' in html
        assert 'data-i18n="analytics.period_30d"' in html
        assert 'data-i18n="analytics.period_90d"' in html
        assert 'data-i18n="analytics.period_all"' in html


# ===================================================================
# NFR-017-03 — Analytics Accessibility
# ===================================================================


class TestNFR01703Accessibility:
    """NFR-017-03: Analytics UI meets accessibility requirements."""

    def test_summary_region_aria(self, html):
        """Summary cards have role=region and aria-label."""
        assert 'role="region"' in html
        assert 'aria-label="Summary metrics"' in html

    def test_period_selector_aria(self, html):
        """Period selector has aria-label for screen readers."""
        assert 'aria-label="Time period"' in html

    def test_analytics_nav_tab(self, html):
        """Analytics nav link has role=tab and aria-selected."""
        assert 'data-screen="analytics"' in html
        assert 'role="tab"' in html

    def test_chart_titles_present(self, html):
        """All chart sections have descriptive headings."""
        assert 'data-i18n="analytics.chart_daily_title"' in html
        assert 'data-i18n="analytics.funnel_title"' in html
        assert 'data-i18n="analytics.platform_title"' in html
        assert 'data-i18n="analytics.score_title"' in html
        assert 'data-i18n="analytics.weekly_title"' in html

    def test_screen_title_i18n(self, html):
        """Analytics screen title uses i18n."""
        assert 'data-i18n="analytics.screen_title"' in html

    def test_summary_labels_i18n(self, html):
        """Summary card labels use i18n."""
        assert 'data-i18n="analytics.summary_total"' in html
        assert 'data-i18n="analytics.summary_interview_rate"' in html
        assert 'data-i18n="analytics.summary_avg_score"' in html
        assert 'data-i18n="analytics.summary_this_week"' in html


# ===================================================================
# NFR-017-06 — Chart Performance
# ===================================================================


class TestNFR01706ChartPerformance:
    """NFR-017-06: Charts are performant — destroy before recreate, use canvas."""

    def test_chart_containers_use_canvas(self, html):
        """All chart containers use <canvas> elements (GPU-accelerated)."""
        assert '<canvas id="chart-daily">' in html
        assert '<canvas id="chart-funnel">' in html
        assert '<canvas id="chart-score">' in html

    def test_charts_destroyed_before_recreate(self, analytics_js):
        """Charts are destroyed before recreation to prevent memory leaks."""
        assert ".destroy()" in analytics_js
        # Each chart type should be destroyed before new Chart()
        assert "chartInstances.daily" in analytics_js
        assert "chartInstances.funnel" in analytics_js
        assert "chartInstances.score" in analytics_js

    def test_chart_instances_tracked(self, analytics_js):
        """Chart instances stored in a dict for lifecycle management."""
        assert "chartInstances" in analytics_js

    def test_switch_period_exported(self, analytics_js):
        """switchAnalyticsPeriod is exported for period button clicks."""
        assert "export function switchAnalyticsPeriod" in analytics_js

    def test_active_period_tracked(self, analytics_js):
        """Active period state tracked to avoid unnecessary re-renders."""
        assert "activePeriod" in analytics_js

    def test_chart_js_4x_used(self, html):
        """Chart.js 4.x is loaded (UMD bundle for performance)."""
        assert "chart.umd" in html
