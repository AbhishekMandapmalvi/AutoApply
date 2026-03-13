"""AutoApply Flask application — factory pattern with Blueprint registration.

Implements: FR-080 (Blueprint architecture), FR-082 (create_app factory),
            NFR-ME2 (auth middleware), NFR-ME4 (error handlers),
            NFR-ME8 (graceful shutdown), NFR-ME9 (rate limiting).
"""

from __future__ import annotations

import atexit
import logging
import os
import secrets as _secrets_mod
import threading
import time

from flask import Flask, jsonify, request
from flask_socketio import SocketIO

import app_state
from config.settings import get_data_dir
from core.i18n import t
from db.database import Database

logger = logging.getLogger(__name__)


def _get_or_create_secret_key() -> str:
    """Generate or load a persistent Flask SECRET_KEY."""
    secret_path = get_data_dir() / ".flask_secret"
    if secret_path.exists():
        return secret_path.read_text(encoding="utf-8").strip()
    key = _secrets_mod.token_hex(32)
    get_data_dir().mkdir(parents=True, exist_ok=True)
    secret_path.write_text(key, encoding="utf-8")
    try:
        secret_path.chmod(0o600)
    except OSError:
        pass  # Windows doesn't support Unix permissions
    return key


def _get_or_create_api_token() -> str:
    """Generate or load a persistent API auth token."""
    token_path = get_data_dir() / ".api_token"
    if token_path.exists():
        return token_path.read_text(encoding="utf-8").strip()
    token = _secrets_mod.token_hex(32)
    get_data_dir().mkdir(parents=True, exist_ok=True)
    token_path.write_text(token, encoding="utf-8")
    try:
        token_path.chmod(0o600)
    except OSError:
        pass  # Windows doesn't support Unix permissions
    return token


# ---------------------------------------------------------------------------
# Error handlers and auth middleware (module-level for inspect/test access)
# ---------------------------------------------------------------------------

def _check_auth():
    """Verify API token on all /api/* endpoints (except health)."""
    if os.environ.get("AUTOAPPLY_DEV"):
        return None
    if request.path == "/" or request.path.startswith("/static"):
        return None
    if request.path == "/api/health":
        return None
    if not request.path.startswith("/api/"):
        return None
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {app_state.api_token}":
        return jsonify({"error": t("errors.unauthorized")}), 401


# ---------------------------------------------------------------------------
# Rate limiter (NFR-ME9) — in-memory token bucket, no external dependencies
# ---------------------------------------------------------------------------

class _RateLimiter:
    """Simple token bucket rate limiter keyed by (client_ip, bucket)."""

    # Bucket config: (max_tokens, refill_per_second)
    BUCKETS = {
        "bot": (10, 10 / 60),       # 10 req/min for bot control
        "write": (30, 30 / 60),     # 30 req/min for mutations
        "read": (60, 60 / 60),      # 60 req/min for reads
    }

    def __init__(self):
        self._state: dict[tuple[str, str], tuple[float, float]] = {}
        self._lock = threading.Lock()

    def _classify(self, path: str, method: str) -> str | None:
        """Classify a request into a rate limit bucket."""
        if not path.startswith("/api/"):
            return None
        if path == "/api/health":
            return None
        if path.startswith("/api/bot/"):
            return "bot"
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            return "write"
        return "read"

    def check(self, client_ip: str, path: str, method: str) -> int | None:
        """Check rate limit. Returns None if allowed, or seconds to retry."""
        bucket_name = self._classify(path, method)
        if bucket_name is None:
            return None

        max_tokens, refill_rate = self.BUCKETS[bucket_name]
        key = (client_ip, bucket_name)
        now = time.monotonic()

        with self._lock:
            tokens, last_time = self._state.get(key, (max_tokens, now))
            elapsed = now - last_time
            tokens = min(max_tokens, tokens + elapsed * refill_rate)

            if tokens >= 1.0:
                self._state[key] = (tokens - 1.0, now)
                return None
            else:
                self._state[key] = (tokens, now)
                wait = (1.0 - tokens) / refill_rate
                return int(wait) + 1


_rate_limiter = _RateLimiter()


def _check_rate_limit():
    """Rate limit middleware — returns 429 if limit exceeded."""
    if os.environ.get("AUTOAPPLY_DEV"):
        return None
    retry_after = _rate_limiter.check(
        request.remote_addr or "unknown", request.path, request.method
    )
    if retry_after is not None:
        resp = jsonify({"error": t("errors.too_many_requests")})
        resp.status_code = 429
        resp.headers["Retry-After"] = str(retry_after)
        return resp


def handle_exception(e):
    if hasattr(e, "code") and isinstance(e.code, int):
        desc = getattr(e, "description", str(e))
        return jsonify({"error": desc}), e.code
    logger.exception("Unhandled exception")
    return jsonify({"error": t("errors.internal_error")}), 500


def handle_400(e):
    return jsonify({"error": t("errors.bad_request")}), 400


def handle_404(e):
    return jsonify({"error": t("errors.not_found")}), 404


def handle_405(e):
    return jsonify({"error": t("errors.method_not_allowed")}), 405


# ---------------------------------------------------------------------------
# Graceful shutdown (NFR-ME8)
# ---------------------------------------------------------------------------

_shutdown_lock = threading.Lock()
_shutdown_done = False


def graceful_shutdown() -> None:
    """Tear down all resources: bot thread, scheduler, login browser, database.

    Safe to call multiple times (idempotent via _shutdown_done flag).
    """
    global _shutdown_done
    with _shutdown_lock:
        if _shutdown_done:
            return
        _shutdown_done = True

    logger.info("Graceful shutdown initiated")

    # 1. Stop bot state (signals bot loop to exit)
    try:
        app_state.bot_state.stop()
    except Exception as e:
        logger.debug("Error stopping bot state: %s", e)

    # 2. Join bot thread (wait up to 10s)
    with app_state.bot_lock:
        thread = app_state.bot_thread
    if thread and thread.is_alive():
        logger.info("Waiting for bot thread to finish...")
        thread.join(timeout=10)
        if thread.is_alive():
            logger.warning("Bot thread did not stop within 10s")

    # 3. Stop scheduler
    scheduler = app_state.bot_scheduler
    if scheduler is not None:
        try:
            scheduler.stop()
        except Exception as e:
            logger.debug("Error stopping scheduler: %s", e)

    # 4. Kill login browser process
    with app_state.login_lock:
        proc = app_state.login_proc
        app_state.login_proc = None
    if proc is not None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception as e:
            logger.debug("Error terminating login browser: %s", e)

    # 5. Close database
    db = app_state.db
    if db is not None:
        try:
            db.close()
        except Exception as e:
            logger.debug("Error closing database: %s", e)

    logger.info("Graceful shutdown complete")


# ---------------------------------------------------------------------------
# Security headers (NFR-SEC1)
# ---------------------------------------------------------------------------

def _add_security_headers(response):
    """Add security headers to all responses."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Prevent caching of API responses containing sensitive data
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
    return response


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> tuple[Flask, SocketIO]:
    """Application factory — creates Flask app, SocketIO, registers all blueprints."""
    flask_app = Flask(__name__)
    flask_app.config["SECRET_KEY"] = _get_or_create_secret_key()

    sio = SocketIO(
        flask_app,
        cors_allowed_origins=["http://localhost:*", "http://127.0.0.1:*"],
        async_mode="gevent",
    )

    # Initialize shared state
    app_state.socketio = sio
    app_state.db = Database(get_data_dir() / "autoapply.db")
    app_state.api_token = _get_or_create_api_token()

    # Register blueprints
    from routes.analytics import analytics_bp
    from routes.applications import applications_bp
    from routes.bot import bot_bp, init_scheduler
    from routes.config import config_bp
    from routes.knowledge_base import kb_bp
    from routes.lifecycle import lifecycle_bp, register_socketio_handlers
    from routes.login import login_bp
    from routes.portal_auth import portal_auth_bp
    from routes.profile import profile_bp
    from routes.resumes import resumes_bp

    flask_app.register_blueprint(applications_bp)
    flask_app.register_blueprint(bot_bp)
    flask_app.register_blueprint(config_bp)
    flask_app.register_blueprint(profile_bp)
    flask_app.register_blueprint(login_bp)
    flask_app.register_blueprint(analytics_bp)
    flask_app.register_blueprint(resumes_bp)
    flask_app.register_blueprint(kb_bp)
    flask_app.register_blueprint(portal_auth_bp)
    flask_app.register_blueprint(lifecycle_bp)

    # Register SocketIO handlers
    register_socketio_handlers(sio)

    # Initialize scheduler
    init_scheduler()

    # Security: max request size (16 MB) to prevent DoS via large uploads
    flask_app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

    # Register auth middleware, rate limiter, security headers, and error handlers
    flask_app.before_request(_check_auth)
    flask_app.before_request(_check_rate_limit)
    flask_app.after_request(_add_security_headers)
    flask_app.register_error_handler(Exception, handle_exception)
    flask_app.register_error_handler(400, handle_400)
    flask_app.register_error_handler(404, handle_404)
    flask_app.register_error_handler(405, handle_405)
    flask_app.register_error_handler(413, lambda e: (jsonify({"error": t("errors.request_too_large")}), 413))
    flask_app.register_error_handler(429, lambda e: (jsonify({"error": t("errors.too_many_requests")}), 429))

    # Register atexit handler for graceful shutdown (NFR-ME8)
    atexit.register(graceful_shutdown)

    return flask_app, sio


# Module-level app and socketio for backward compatibility with run.py and tests
app, socketio = create_app()

# Re-exports for backward compatibility with tests that import from app module.
# These reference the shared state in app_state so monkeypatching works correctly.
bot_state = app_state.bot_state
bot_scheduler = app_state.bot_scheduler
db = app_state.db
_bot_lock = app_state.bot_lock
_api_token = app_state.api_token
_login_proc = app_state.login_proc
_login_lock = app_state.login_lock

# Re-export functions that tests reference via app module
from routes.applications import export_applications  # noqa: E402, F401
from routes.bot import (  # noqa: E402, F401
    _is_bot_running,
    _scheduler_start_bot,
    _scheduler_stop_bot,
)
from routes.profile import validate_filename  # noqa: E402, F401
