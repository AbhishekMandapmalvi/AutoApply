"""Analytics and feed event routes.

Implements: FR-013 (analytics API), FR-014 (feed events).
"""

from __future__ import annotations

from flask import Blueprint, abort, jsonify, request

import app_state

analytics_bp = Blueprint("analytics", __name__)


def _get_db():
    """Return the database instance or abort 503 if not initialized."""
    db = app_state.db
    if db is None:
        abort(503, description="Database not initialized")
    return db


@analytics_bp.route("/api/analytics/enhanced", methods=["GET"])
def analytics_enhanced():
    days = request.args.get("days", 30, type=int)
    if days < 0:
        days = 30
    elif days > 3650:
        days = 3650
    return jsonify(_get_db().get_enhanced_analytics(days))


@analytics_bp.route("/api/analytics/summary", methods=["GET"])
def analytics_summary():
    return jsonify(_get_db().get_analytics_summary())


@analytics_bp.route("/api/analytics/daily", methods=["GET"])
def analytics_daily():
    days = request.args.get("days", 30, type=int)
    return jsonify(_get_db().get_daily_analytics(days))


@analytics_bp.route("/api/feed", methods=["GET"])
def get_feed_events():
    limit = request.args.get("limit", 50, type=int)
    events = _get_db().get_feed_events(limit=limit)
    return jsonify([e.model_dump() for e in events])
