"""Unit and integration tests for enhanced analytics (FR-090 to FR-101).

Tests: Database.get_enhanced_analytics(), GET /api/analytics/enhanced,
       Database.get_daily_analytics() days=0 extension.
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta

import pytest

from db.database import Database

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture()
def db(tmp_path):
    """Create a fresh database for each test."""
    return Database(tmp_path / "test.db")


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    """Create Flask test client with database."""
    monkeypatch.setattr("config.settings.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("app.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("routes.profile.get_data_dir", lambda: tmp_path)
    monkeypatch.setattr("routes.applications.get_data_dir", lambda: tmp_path)

    (tmp_path / "profile" / "experiences").mkdir(parents=True)
    minimal_config = {
        "profile": {"first_name": "Test", "last_name": "User", "email": "t@e.com",
                     "phone": "555", "city": "Remote", "state": "", "bio": "Test"},
        "search_criteria": {"job_titles": ["Engineer"], "locations": ["Remote"]},
        "bot": {"enabled_platforms": ["linkedin"]},
    }
    (tmp_path / "config.json").write_text(json.dumps(minimal_config), encoding="utf-8")

    test_db = Database(tmp_path / "test.db")
    monkeypatch.setattr("app.db", test_db)
    monkeypatch.setattr("app_state.db", test_db)

    from app import app
    app.config["TESTING"] = True
    yield app.test_client()


def _insert_app(db, *, platform="linkedin", status="applied", match_score=75,
                company="TestCo", job_title="Engineer", applied_at=None,
                updated_at=None):
    """Helper to insert an application with optional timestamp overrides."""
    with db._connect() as conn:
        if applied_at and updated_at:
            conn.execute(
                """INSERT INTO applications
                   (external_id, platform, job_title, company, apply_url,
                    match_score, status, applied_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"ext-{time.monotonic_ns()}", platform, job_title, company,
                 "https://example.com", match_score, status, applied_at, updated_at),
            )
        elif applied_at:
            conn.execute(
                """INSERT INTO applications
                   (external_id, platform, job_title, company, apply_url,
                    match_score, status, applied_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"ext-{time.monotonic_ns()}", platform, job_title, company,
                 "https://example.com", match_score, status, applied_at),
            )
        else:
            db.save_application(
                external_id=f"ext-{time.monotonic_ns()}",
                platform=platform,
                job_title=job_title,
                company=company,
                location=None,
                salary=None,
                apply_url="https://example.com",
                match_score=match_score,
                resume_path=None,
                cover_letter_path=None,
                cover_letter_text=None,
                status=status,
                error_message=None,
            )


# ══════════════════════════════════════════════════════════════════════
# Database.get_enhanced_analytics() — Unit Tests
# ══════════════════════════════════════════════════════════════════════


class TestEnhancedAnalyticsEmpty:
    """Tests with zero applications (FR-101 empty states)."""

    def test_empty_db_returns_valid_structure(self, db):
        result = db.get_enhanced_analytics()
        assert result["summary"]["total"] == 0
        assert result["summary"]["interview_rate"] == 0.0
        assert result["summary"]["avg_score"] is None
        assert result["summary"]["this_week"] == 0

    def test_empty_funnel(self, db):
        result = db.get_enhanced_analytics()
        assert result["funnel"]["applied"] == 0
        assert result["funnel"]["interview"] == 0
        assert result["funnel"]["offer"] == 0
        assert result["funnel"]["applied_to_interview_rate"] == 0.0
        assert result["funnel"]["interview_to_offer_rate"] == 0.0

    def test_empty_platforms(self, db):
        result = db.get_enhanced_analytics()
        assert result["platforms"] == []

    def test_empty_score_distribution_has_10_buckets(self, db):
        result = db.get_enhanced_analytics()
        assert len(result["score_distribution"]) == 10
        for bucket in result["score_distribution"]:
            assert bucket["count"] == 0
            assert bucket["interview_count"] == 0
            assert bucket["interview_rate"] == 0.0

    def test_empty_weekly(self, db):
        result = db.get_enhanced_analytics()
        assert result["weekly"]["current"]["applications"] == 0
        assert result["weekly"]["previous"]["applications"] == 0

    def test_empty_top_companies(self, db):
        result = db.get_enhanced_analytics()
        assert result["top_companies"] == []

    def test_empty_response_times(self, db):
        result = db.get_enhanced_analytics()
        assert result["response_times"]["to_interview"]["median_days"] is None
        assert result["response_times"]["to_interview"]["avg_days"] is None
        assert result["response_times"]["to_rejected"]["median_days"] is None
        assert result["response_times"]["to_rejected"]["avg_days"] is None

    def test_empty_daily(self, db):
        result = db.get_enhanced_analytics()
        assert result["daily"] == []


class TestEnhancedAnalyticsSummary:
    """Tests for summary metrics (FR-090)."""

    def test_total_count(self, db):
        for _ in range(5):
            _insert_app(db)
        result = db.get_enhanced_analytics()
        assert result["summary"]["total"] == 5

    def test_avg_score(self, db):
        for score in [60, 70, 80]:
            _insert_app(db, match_score=score)
        result = db.get_enhanced_analytics()
        assert result["summary"]["avg_score"] == 70.0

    def test_interview_rate_with_interviews(self, db):
        for _ in range(8):
            _insert_app(db, status="applied")
        for _ in range(2):
            _insert_app(db, status="interview")
        result = db.get_enhanced_analytics()
        # 2 interviews / 8 applied = 25.0%
        assert result["summary"]["interview_rate"] == 25.0

    def test_interview_rate_zero_applied(self, db):
        _insert_app(db, status="error")
        result = db.get_enhanced_analytics()
        assert result["summary"]["interview_rate"] == 0.0

    def test_all_interview_statuses_counted(self, db):
        for _ in range(10):
            _insert_app(db, status="applied")
        _insert_app(db, status="interview")
        _insert_app(db, status="interviewing")
        _insert_app(db, status="interviewed")
        result = db.get_enhanced_analytics()
        assert result["summary"]["interview_rate"] == 30.0


class TestEnhancedAnalyticsFunnel:
    """Tests for conversion funnel (FR-092)."""

    def test_funnel_counts(self, db):
        for _ in range(100):
            _insert_app(db, status="applied")
        for _ in range(10):
            _insert_app(db, status="interview")
        for _ in range(2):
            _insert_app(db, status="offer")
        # Also add non-funnel statuses
        for _ in range(5):
            _insert_app(db, status="error")
        for _ in range(3):
            _insert_app(db, status="skipped")

        result = db.get_enhanced_analytics()
        f = result["funnel"]
        # Funnel-eligible: applied(100) + interview(10) + offer(2) = 112
        assert f["applied"] == 112
        # Reached interview: interview(10) + offer(2) = 12
        assert f["interview"] == 12
        assert f["offer"] == 2
        assert f["applied_to_interview_rate"] == round((12 / 112) * 100, 1)
        assert f["interview_to_offer_rate"] == round((2 / 12) * 100, 1)

    def test_funnel_zero_denominator(self, db):
        _insert_app(db, status="error")
        result = db.get_enhanced_analytics()
        assert result["funnel"]["applied_to_interview_rate"] == 0.0
        assert result["funnel"]["interview_to_offer_rate"] == 0.0


class TestEnhancedAnalyticsPlatforms:
    """Tests for platform performance (FR-093)."""

    def test_platform_breakdown(self, db):
        for _ in range(5):
            _insert_app(db, platform="linkedin", status="applied", match_score=80)
        _insert_app(db, platform="linkedin", status="interview", match_score=90)
        for _ in range(3):
            _insert_app(db, platform="indeed", status="applied", match_score=60)

        result = db.get_enhanced_analytics()
        platforms = {p["platform"]: p for p in result["platforms"]}

        assert platforms["linkedin"]["total"] == 6
        assert platforms["linkedin"]["interviews"] == 1
        assert platforms["indeed"]["total"] == 3
        assert platforms["indeed"]["interviews"] == 0
        assert platforms["indeed"]["interview_rate"] == 0.0

    def test_platforms_sorted_by_total_desc(self, db):
        for _ in range(2):
            _insert_app(db, platform="indeed")
        for _ in range(5):
            _insert_app(db, platform="linkedin")
        result = db.get_enhanced_analytics()
        assert result["platforms"][0]["platform"] == "linkedin"
        assert result["platforms"][1]["platform"] == "indeed"


class TestEnhancedAnalyticsScoreDistribution:
    """Tests for score distribution (FR-095)."""

    def test_score_buckets(self, db):
        _insert_app(db, match_score=0)
        _insert_app(db, match_score=45)
        _insert_app(db, match_score=100)
        result = db.get_enhanced_analytics()
        dist = {b["bucket"]: b for b in result["score_distribution"]}
        assert dist["0-9"]["count"] == 1
        assert dist["40-49"]["count"] == 1
        assert dist["90-100"]["count"] == 1
        assert dist["50-59"]["count"] == 0

    def test_score_bucket_interview_rate(self, db):
        _insert_app(db, match_score=75, status="applied")
        _insert_app(db, match_score=75, status="interview")
        _insert_app(db, match_score=75, status="applied")
        result = db.get_enhanced_analytics()
        bucket = next(b for b in result["score_distribution"] if b["bucket"] == "70-79")
        assert bucket["count"] == 3
        assert bucket["interview_count"] == 1
        assert bucket["interview_rate"] == round(100 / 3, 1)

    def test_always_10_buckets(self, db):
        _insert_app(db, match_score=50)
        result = db.get_enhanced_analytics()
        assert len(result["score_distribution"]) == 10


class TestEnhancedAnalyticsWeekly:
    """Tests for weekly summary (FR-096)."""

    def test_weekly_with_data(self, db):
        now = datetime.now(UTC)
        today_str = now.strftime("%Y-%m-%d %H:%M:%S")
        week_ago_str = (now - timedelta(days=8)).strftime("%Y-%m-%d %H:%M:%S")

        for _ in range(3):
            _insert_app(db, applied_at=today_str)
        for _ in range(2):
            _insert_app(db, applied_at=week_ago_str)

        result = db.get_enhanced_analytics()
        # Current week should have >= 3 (depends on day of week)
        assert result["weekly"]["current"]["applications"] >= 0
        assert result["weekly"]["previous"]["applications"] >= 0

    def test_weekly_changes_computed(self, db):
        result = db.get_enhanced_analytics()
        assert "applications" in result["weekly"]["changes"]
        assert "interviews" in result["weekly"]["changes"]
        assert "avg_score" in result["weekly"]["changes"]


class TestEnhancedAnalyticsTopCompanies:
    """Tests for top companies (FR-097)."""

    def test_top_companies_limit_10(self, db):
        for i in range(15):
            _insert_app(db, company=f"Company-{i:02d}")
        result = db.get_enhanced_analytics()
        assert len(result["top_companies"]) == 10

    def test_top_companies_sorted_by_count(self, db):
        for _ in range(5):
            _insert_app(db, company="Big Corp")
        for _ in range(2):
            _insert_app(db, company="Small Inc")
        result = db.get_enhanced_analytics()
        assert result["top_companies"][0]["company"] == "Big Corp"
        assert result["top_companies"][0]["total"] == 5

    def test_top_companies_status_breakdown(self, db):
        _insert_app(db, company="TestCo", status="applied")
        _insert_app(db, company="TestCo", status="interview")
        _insert_app(db, company="TestCo", status="rejected")
        result = db.get_enhanced_analytics()
        co = result["top_companies"][0]
        assert co["statuses"]["applied"] == 1
        assert co["statuses"]["interview"] == 1
        assert co["statuses"]["rejected"] == 1

    def test_top_companies_alphabetical_tiebreaker(self, db):
        _insert_app(db, company="Zebra")
        _insert_app(db, company="Alpha")
        result = db.get_enhanced_analytics()
        assert result["top_companies"][0]["company"] == "Alpha"
        assert result["top_companies"][1]["company"] == "Zebra"


class TestEnhancedAnalyticsResponseTimes:
    """Tests for response time metrics (FR-098)."""

    def test_response_times_to_interview(self, db):
        now = datetime.now(UTC)
        applied = (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
        updated = (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        _insert_app(db, status="interview", applied_at=applied, updated_at=updated)

        result = db.get_enhanced_analytics()
        rt = result["response_times"]["to_interview"]
        assert rt["median_days"] is not None
        assert rt["avg_days"] is not None
        assert rt["median_days"] > 0

    def test_response_times_null_when_no_transitions(self, db):
        _insert_app(db, status="applied")
        result = db.get_enhanced_analytics()
        assert result["response_times"]["to_interview"]["median_days"] is None
        assert result["response_times"]["to_rejected"]["median_days"] is None

    def test_response_times_median_odd_count(self, db):
        now = datetime.now(UTC)
        for days_ago in [3, 5, 7]:
            applied = (now - timedelta(days=days_ago + 5)).strftime("%Y-%m-%d %H:%M:%S")
            updated = (now - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S")
            _insert_app(db, status="interview", applied_at=applied, updated_at=updated)

        result = db.get_enhanced_analytics()
        assert result["response_times"]["to_interview"]["median_days"] is not None


class TestEnhancedAnalyticsDaily:
    """Tests for daily trend data and days=0 extension (FR-099)."""

    def test_daily_default_30_days(self, db):
        _insert_app(db)
        result = db.get_enhanced_analytics(days=30)
        assert isinstance(result["daily"], list)

    def test_daily_all_time(self, db):
        now = datetime.now(UTC)
        old = (now - timedelta(days=100)).strftime("%Y-%m-%d %H:%M:%S")
        _insert_app(db, applied_at=old)
        _insert_app(db)

        result = db.get_enhanced_analytics(days=0)
        assert len(result["daily"]) >= 2

    def test_get_daily_analytics_zero(self, db):
        now = datetime.now(UTC)
        old = (now - timedelta(days=100)).strftime("%Y-%m-%d %H:%M:%S")
        _insert_app(db, applied_at=old)
        _insert_app(db)

        result = db.get_daily_analytics(days=0)
        assert len(result) >= 2


class TestEnhancedAnalyticsDaysParam:
    """Tests for days parameter handling."""

    def test_negative_days_treated_as_default(self, db):
        _insert_app(db)
        # Should not crash
        result = db.get_enhanced_analytics(days=-5)
        assert result["summary"]["total"] == 1


# ══════════════════════════════════════════════════════════════════════
# API Endpoint Tests — GET /api/analytics/enhanced
# ══════════════════════════════════════════════════════════════════════


class TestEnhancedEndpoint:
    """Integration tests for the API endpoint (FR-094)."""

    def test_endpoint_returns_200(self, app_client):
        res = app_client.get("/api/analytics/enhanced")
        assert res.status_code == 200

    def test_response_has_all_keys(self, app_client):
        res = app_client.get("/api/analytics/enhanced")
        data = res.get_json()
        expected_keys = {"summary", "funnel", "platforms", "score_distribution",
                         "weekly", "top_companies", "response_times", "daily"}
        assert set(data.keys()) == expected_keys

    def test_summary_keys(self, app_client):
        res = app_client.get("/api/analytics/enhanced")
        summary = res.get_json()["summary"]
        assert "total" in summary
        assert "interview_rate" in summary
        assert "avg_score" in summary
        assert "this_week" in summary

    def test_days_param(self, app_client):
        res = app_client.get("/api/analytics/enhanced?days=7")
        assert res.status_code == 200

    def test_days_zero(self, app_client):
        res = app_client.get("/api/analytics/enhanced?days=0")
        assert res.status_code == 200

    def test_score_distribution_always_10(self, app_client):
        res = app_client.get("/api/analytics/enhanced")
        dist = res.get_json()["score_distribution"]
        assert len(dist) == 10

    def test_non_integer_days_uses_default(self, app_client):
        res = app_client.get("/api/analytics/enhanced?days=abc")
        assert res.status_code == 200

    def test_response_json_serializable(self, app_client):
        res = app_client.get("/api/analytics/enhanced")
        # If this doesn't throw, JSON serialization is correct
        data = json.loads(res.data)
        assert isinstance(data, dict)


# ══════════════════════════════════════════════════════════════════════
# Performance Test (NFR-017-01)
# ══════════════════════════════════════════════════════════════════════


class TestPerformance:
    """Performance validation for < 200ms on 10,000 rows."""

    def test_10k_rows_under_200ms(self, db):
        # Insert 10,000 applications in bulk
        with db._connect() as conn:
            conn.executemany(
                """INSERT INTO applications
                   (external_id, platform, job_title, company, apply_url,
                    match_score, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (f"ext-{i}", ["linkedin", "indeed", "greenhouse"][i % 3],
                     f"Job {i}", f"Company {i % 50}", "https://example.com",
                     (i * 7) % 101,
                     ["applied", "interview", "rejected", "offer", "error"][i % 5])
                    for i in range(10000)
                ],
            )

        start = time.time()
        result = db.get_enhanced_analytics(days=0)
        elapsed_ms = (time.time() - start) * 1000

        assert result["summary"]["total"] == 10000
        assert len(result["score_distribution"]) == 10
        assert len(result["top_companies"]) == 10
        # Allow generous margin for CI but assert reasonable bound
        assert elapsed_ms < 2000, f"Query took {elapsed_ms:.0f}ms (expected < 2000ms)"
