"""Portal authentication credential vault API routes.

Implements: FR-086 (portal credential vault), FR-089 (browser handoff login decision).
"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from config.settings import get_data_dir
from core.i18n import t
from core.portal_auth import PortalAuthManager
from db.database import Database

logger = logging.getLogger(__name__)

portal_auth_bp = Blueprint("portal_auth", __name__)


def _get_db() -> Database:
    data_dir = get_data_dir()
    return Database(data_dir / "autoapply.db")


# ---------------------------------------------------------------------------
# Credential CRUD
# ---------------------------------------------------------------------------


@portal_auth_bp.route("/api/portal-credentials", methods=["GET"])
def list_credentials():
    """List all stored portal credentials (passwords masked)."""
    db = _get_db()
    auth = PortalAuthManager(db)
    creds = auth.list_credentials()
    return jsonify({"credentials": creds})


@portal_auth_bp.route("/api/portal-credentials", methods=["POST"])
def store_credential():
    """Store or update a portal credential."""
    data = request.get_json(silent=True) or {}
    domain = (data.get("domain") or "").strip()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    portal_type = (data.get("portal_type") or "generic").strip()
    notes = data.get("notes")

    if not domain or not username or not password:
        return jsonify({"error": t("portal_auth.missing_fields")}), 400

    db = _get_db()
    auth = PortalAuthManager(db)
    cred_id = auth.store_credential(
        domain=domain,
        username=username,
        password=password,
        portal_type=portal_type,
        notes=notes,
    )
    logger.info("Portal credential stored for domain: %s", domain)
    return jsonify({"id": cred_id, "message": t("portal_auth.credential_saved")}), 201


@portal_auth_bp.route("/api/portal-credentials/<domain>", methods=["DELETE"])
def delete_credential(domain: str):
    """Delete a portal credential by domain."""
    db = _get_db()
    auth = PortalAuthManager(db)
    deleted = auth.delete_credential(domain)
    if not deleted:
        return jsonify({"error": t("portal_auth.not_found")}), 404
    logger.info("Portal credential deleted for domain: %s", domain)
    return jsonify({"message": t("portal_auth.credential_deleted")})


# ---------------------------------------------------------------------------
# Login decision (browser handoff)
# ---------------------------------------------------------------------------


@portal_auth_bp.route("/api/portal-auth/login-decision", methods=["POST"])
def login_decision():
    """Set the user's login decision when the bot is waiting at a login gate.

    Body: {"decision": "done" | "skip", "username": "...", "password": "..."}
    When decision is "done" and credentials are provided, they are saved for
    future auto-login.
    """
    import app_state

    data = request.get_json(silent=True) or {}
    decision = (data.get("decision") or "").strip().lower()

    if decision not in ("done", "skip"):
        return jsonify({"error": t("portal_auth.invalid_decision")}), 400

    state = app_state.bot_state
    if not state.awaiting_login:
        return jsonify({"error": t("portal_auth.not_awaiting_login")}), 409

    # Save credentials if provided with "done" decision
    if decision == "done":
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if username and password:
            ctx = state.login_context
            domain = ctx["domain"] if ctx else "unknown"
            portal_type = ctx["portal_type"] if ctx else "generic"
            db = _get_db()
            auth = PortalAuthManager(db)
            auth.store_credential(
                domain=domain,
                username=username,
                password=password,
                portal_type=portal_type,
            )
            logger.info("Credentials saved for %s during login gate", domain)

    state.set_login_decision(decision)
    return jsonify({"message": t("portal_auth.decision_set")})


@portal_auth_bp.route("/api/portal-auth/login-status", methods=["GET"])
def login_status():
    """Get the current login gate status."""
    import app_state

    state = app_state.bot_state
    return jsonify({
        "awaiting_login": state.awaiting_login,
        "login_context": state.login_context,
    })


# ---------------------------------------------------------------------------
# Domain extraction utility
# ---------------------------------------------------------------------------


@portal_auth_bp.route("/api/portal-auth/extract-domain", methods=["POST"])
def extract_domain():
    """Extract the domain key from a URL (utility endpoint)."""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"error": "URL is required"}), 400

    domain = PortalAuthManager.extract_domain(url)
    portal_type = PortalAuthManager.detect_portal_type(url)
    return jsonify({"domain": domain, "portal_type": portal_type})
