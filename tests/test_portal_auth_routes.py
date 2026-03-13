"""Integration tests for portal auth API routes.

Tests: FR-086 (credential vault API), FR-089 (login decision endpoint).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app import create_app


@pytest.fixture()
def client(tmp_path):
    """Create a test Flask client with a temporary database."""
    with patch("config.settings.get_data_dir", return_value=tmp_path):
        flask_app, _ = create_app()
        flask_app.config["TESTING"] = True
        with flask_app.test_client() as c:
            yield c


class TestPortalCredentialRoutes:
    def test_list_empty(self, client):
        resp = client.get(
            "/api/portal-credentials",
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["credentials"] == []

    def test_store_credential(self, client):
        resp = client.post(
            "/api/portal-credentials",
            json={
                "domain": "example.com",
                "username": "user@test.com",
                "password": "secret",
                "portal_type": "generic",
            },
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["id"] > 0

    def test_store_missing_fields(self, client):
        resp = client.post(
            "/api/portal-credentials",
            json={"domain": "example.com"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 400

    def test_list_after_store(self, client):
        client.post(
            "/api/portal-credentials",
            json={
                "domain": "example.com",
                "username": "user@test.com",
                "password": "secret",
            },
            headers={"Authorization": "Bearer test"},
        )
        resp = client.get(
            "/api/portal-credentials",
            headers={"Authorization": "Bearer test"},
        )
        data = resp.get_json()
        assert len(data["credentials"]) == 1
        assert data["credentials"][0]["domain"] == "example.com"

    def test_delete_credential(self, client):
        client.post(
            "/api/portal-credentials",
            json={
                "domain": "example.com",
                "username": "user",
                "password": "pass",
            },
            headers={"Authorization": "Bearer test"},
        )
        resp = client.delete(
            "/api/portal-credentials/example.com",
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200

    def test_delete_not_found(self, client):
        resp = client.delete(
            "/api/portal-credentials/nonexistent.com",
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 404


class TestExtractDomainRoute:
    def test_extract_domain(self, client):
        resp = client.post(
            "/api/portal-auth/extract-domain",
            json={"url": "https://boards.greenhouse.io/stripe/jobs/123"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["domain"] == "boards.greenhouse.io/stripe"

    def test_extract_domain_missing_url(self, client):
        resp = client.post(
            "/api/portal-auth/extract-domain",
            json={},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 400


class TestLoginDecisionRoute:
    def test_not_awaiting_login(self, client):
        resp = client.post(
            "/api/portal-auth/login-decision",
            json={"decision": "done"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 409

    def test_invalid_decision(self, client):
        resp = client.post(
            "/api/portal-auth/login-decision",
            json={"decision": "invalid"},
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 400


class TestLoginStatusRoute:
    def test_login_status(self, client):
        resp = client.get(
            "/api/portal-auth/login-status",
            headers={"Authorization": "Bearer test"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["awaiting_login"] is False
        assert data["login_context"] is None
