"""Tests for rate limiting middleware (NFR-ME9).

Verifies the token bucket rate limiter enforces limits correctly
and returns 429 with Retry-After header when exceeded.
"""

from __future__ import annotations

import pytest

from app import _RateLimiter, app


@pytest.fixture
def rate_limiter():
    """Fresh rate limiter instance for isolated tests."""
    return _RateLimiter()


class TestRateLimiterUnit:
    """Unit tests for _RateLimiter token bucket logic."""

    def test_allows_requests_within_limit(self, rate_limiter):
        for _ in range(10):
            result = rate_limiter.check("127.0.0.1", "/api/bot/start", "POST")
            assert result is None

    def test_blocks_after_limit_exceeded(self, rate_limiter):
        # Exhaust bot bucket (10 tokens)
        for _ in range(10):
            rate_limiter.check("127.0.0.1", "/api/bot/start", "POST")
        # 11th should be blocked
        result = rate_limiter.check("127.0.0.1", "/api/bot/start", "POST")
        assert result is not None
        assert isinstance(result, int)
        assert result > 0

    def test_health_exempt(self, rate_limiter):
        for _ in range(100):
            result = rate_limiter.check("127.0.0.1", "/api/health", "GET")
            assert result is None

    def test_non_api_exempt(self, rate_limiter):
        for _ in range(100):
            result = rate_limiter.check("127.0.0.1", "/", "GET")
            assert result is None

    def test_different_ips_independent(self, rate_limiter):
        # Exhaust bucket for IP A
        for _ in range(10):
            rate_limiter.check("10.0.0.1", "/api/bot/start", "POST")
        # IP A blocked
        assert rate_limiter.check("10.0.0.1", "/api/bot/start", "POST") is not None
        # IP B still allowed
        assert rate_limiter.check("10.0.0.2", "/api/bot/start", "POST") is None

    def test_read_bucket_separate_from_write(self, rate_limiter):
        # Exhaust write bucket (30 tokens)
        for _ in range(30):
            rate_limiter.check("127.0.0.1", "/api/applications/1", "PATCH")
        # Write blocked
        assert rate_limiter.check("127.0.0.1", "/api/applications/1", "PATCH") is not None
        # Read still allowed
        assert rate_limiter.check("127.0.0.1", "/api/applications", "GET") is None

    def test_classify_bot_bucket(self, rate_limiter):
        assert rate_limiter._classify("/api/bot/start", "POST") == "bot"
        assert rate_limiter._classify("/api/bot/status", "GET") == "bot"

    def test_classify_write_bucket(self, rate_limiter):
        assert rate_limiter._classify("/api/config", "PUT") == "write"
        assert rate_limiter._classify("/api/applications/1", "PATCH") == "write"
        assert rate_limiter._classify("/api/applications/1", "DELETE") == "write"

    def test_classify_read_bucket(self, rate_limiter):
        assert rate_limiter._classify("/api/applications", "GET") == "read"
        assert rate_limiter._classify("/api/analytics/summary", "GET") == "read"

    def test_classify_exempt(self, rate_limiter):
        assert rate_limiter._classify("/", "GET") is None
        assert rate_limiter._classify("/api/health", "GET") is None
        assert rate_limiter._classify("/static/style.css", "GET") is None


class TestRateLimitMiddleware:
    """Integration test: rate limiter returns 429 via Flask middleware."""

    def test_429_when_rate_exceeded(self, monkeypatch):
        # Disable dev mode so both auth and rate limiting are active
        monkeypatch.delenv("AUTOAPPLY_DEV", raising=False)

        import app_state
        token = app_state.api_token
        headers = {"Authorization": f"Bearer {token}"}

        # Use a fresh rate limiter to avoid cross-test state
        fresh_limiter = _RateLimiter()
        monkeypatch.setattr("app._rate_limiter", fresh_limiter)

        client = app.test_client()
        # Exhaust bot bucket (10 tokens)
        for _ in range(10):
            client.post("/api/bot/status", headers=headers)

        resp = client.post("/api/bot/status", headers=headers)
        assert resp.status_code == 429
        data = resp.get_json()
        assert data["error"] == "Too many requests"
        assert "Retry-After" in resp.headers

    def test_dev_mode_bypasses_rate_limit(self, monkeypatch):
        monkeypatch.setenv("AUTOAPPLY_DEV", "1")

        client = app.test_client()
        # Even after many requests, should never get 429 in dev mode
        for _ in range(20):
            resp = client.get("/api/bot/status")
            assert resp.status_code != 429
