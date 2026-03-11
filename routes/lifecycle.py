"""Lifecycle routes: health check, shutdown, index page, SocketIO connect.

Implements: FR-015 (health check), FR-016 (shutdown), FR-017 (index page).
"""

from __future__ import annotations

import os
import signal

from flask import Blueprint, abort, jsonify, render_template, request
from flask_socketio import emit

import app_state
from core.i18n import get_available_locales, get_locale, set_locale, t

lifecycle_bp = Blueprint("lifecycle", __name__)


@lifecycle_bp.route("/")
def index():
    return render_template("index.html", api_token=app_state.api_token)


@lifecycle_bp.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"})


@lifecycle_bp.route("/api/locales", methods=["GET"])
def list_locales():
    """List available locales and current locale (LE-3)."""
    return jsonify({
        "current": get_locale(),
        "available": get_available_locales(),
    })


@lifecycle_bp.route("/api/locale", methods=["PUT"])
def set_locale_endpoint():
    """Set the active locale for backend responses (FR-133)."""
    data = request.get_json(silent=True) or {}
    locale = data.get("locale", "")
    available = get_available_locales()
    if locale not in available:
        abort(400, description=t("errors.bad_request"))
    set_locale(locale)
    return jsonify({"locale": locale})


@lifecycle_bp.route("/api/shutdown", methods=["POST"])
def shutdown():
    if request.remote_addr not in ("127.0.0.1", "::1"):
        return jsonify({"error": t("errors.forbidden")}), 403
    pid = os.getpid()

    def _shutdown():
        import time
        time.sleep(0.5)
        # Graceful resource cleanup before process exit (NFR-ME8)
        from app import graceful_shutdown
        graceful_shutdown()
        os.kill(pid, signal.SIGTERM)

    import threading
    threading.Thread(target=_shutdown, daemon=True).start()
    return jsonify({"status": "shutting_down"})


def register_socketio_handlers(socketio):
    """Register SocketIO event handlers. Called by create_app()."""
    @socketio.on("connect")
    def handle_connect():
        status_dict = app_state.bot_state.get_status_dict()
        status_dict["schedule_enabled"] = (
            app_state.bot_scheduler.running if app_state.bot_scheduler else False
        )
        emit("bot_status", status_dict)
