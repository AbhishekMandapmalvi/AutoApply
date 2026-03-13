"""Configuration, setup status, and AI provider routes.

Implements: FR-009 (configuration API), FR-010 (setup status), FR-074 (AI provider validation).
"""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from config.settings import AppConfig, get_data_dir, is_first_run, load_config, save_config
from core.ai_engine import validate_api_key as _validate_api_key
from core.i18n import t
from routes.bot import check_ai_available

logger = logging.getLogger(__name__)

config_bp = Blueprint("config", __name__)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@config_bp.route("/api/config", methods=["GET"])
def get_config():
    config = load_config()
    if config is None:
        return jsonify({})
    return jsonify(config.model_dump())


@config_bp.route("/api/config", methods=["PUT"])
def update_config():
    data = request.get_json()
    if data is None:
        return jsonify({"error": t("errors.request_body_json")}), 400
    try:
        existing = load_config()
        if existing:
            merged = existing.model_dump()
            for key, value in data.items():
                if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                    merged[key].update(value)
                else:
                    merged[key] = value
            config = AppConfig(**merged)
        else:
            config = AppConfig(**data)
    except ValidationError as e:
        return jsonify({"error": t("errors.invalid_config", count=e.error_count())}), 400
    save_config(config)
    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

@config_bp.route("/api/setup/status", methods=["GET"])
def setup_status():
    return jsonify({
        "is_first_run": is_first_run(),
        "ai_available": check_ai_available(),
    })


# ---------------------------------------------------------------------------
# AI Provider
# ---------------------------------------------------------------------------

@config_bp.route("/api/ai/validate", methods=["POST"])
def validate_ai_key():
    data = request.get_json(force=True) or {}
    provider = data.get("provider", "")
    api_key = data.get("api_key", "")
    model = data.get("model", "")
    if not provider or not api_key:
        return jsonify({"error": t("errors.provider_key_required")}), 400
    if provider not in ("anthropic", "openai", "google", "deepseek"):
        return jsonify({"error": t("errors.unsupported_provider", provider=provider)}), 400
    valid = _validate_api_key(provider, api_key, model or None)
    return jsonify({"valid": valid})


# ---------------------------------------------------------------------------
# Default Resume
# ---------------------------------------------------------------------------

_ALLOWED_RESUME_EXT = {".pdf", ".docx"}
_MAX_RESUME_SIZE = 5 * 1024 * 1024  # 5 MB


@config_bp.route("/api/config/default-resume", methods=["POST"])
def upload_default_resume():
    """Upload a default resume file (PDF or DOCX, max 5 MB)."""
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "No file provided"}), 400

    ext = Path(f.filename).suffix.lower()
    if ext not in _ALLOWED_RESUME_EXT:
        return jsonify({"error": f"Unsupported format. Allowed: {', '.join(_ALLOWED_RESUME_EXT)}"}), 400

    data = f.read()
    if len(data) > _MAX_RESUME_SIZE:
        return jsonify({"error": "File too large (max 5 MB)"}), 400

    dest = get_data_dir() / f"default_resume{ext}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)

    # Save path in config
    config = load_config()
    if config:
        config.profile.fallback_resume_path = str(dest)
        save_config(config)

    logger.info("Default resume saved: %s", dest)
    return jsonify({"success": True, "filename": f.filename, "path": str(dest)})


@config_bp.route("/api/config/default-resume", methods=["GET"])
def get_default_resume():
    """Get current default resume info."""
    config = load_config()
    path = config.profile.fallback_resume_path if config else None
    if path and Path(path).exists():
        return jsonify({"filename": Path(path).name, "path": path})
    return jsonify({"filename": None, "path": None})


@config_bp.route("/api/config/default-resume", methods=["DELETE"])
def delete_default_resume():
    """Remove the default resume."""
    config = load_config()
    if config and config.profile.fallback_resume_path:
        p = Path(config.profile.fallback_resume_path)
        if p.exists():
            p.unlink()
        config.profile.fallback_resume_path = None
        save_config(config)
    return jsonify({"success": True})
