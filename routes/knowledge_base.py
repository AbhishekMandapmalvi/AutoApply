"""Knowledge Base routes — upload, CRUD, search, preview.

Implements: TASK-030 M5 — Upload API, KB entry management, resume preview.
"""

from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path

from flask import Blueprint, abort, jsonify, request

import app_state
from core.i18n import t

logger = logging.getLogger(__name__)

kb_bp = Blueprint("knowledge_base", __name__)

# Allowed upload extensions
_ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "md"}
_MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


def _get_db():
    db = app_state.db
    if db is None:
        abort(503, description=t("errors.database_not_initialized"))
    return db


def _allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in _ALLOWED_EXTENSIONS


def _safe_filename(filename: str) -> str:
    """Sanitize filename — allow only alphanumeric, dash, underscore, dot."""
    return re.sub(r"[^a-zA-Z0-9._-]", "_", filename)[:100]


# ---------------------------------------------------------------------------
# Upload endpoint
# ---------------------------------------------------------------------------


@kb_bp.route("/api/kb/upload", methods=["POST"])
def upload_document():
    """Upload a document (PDF/DOCX/TXT/MD) and extract KB entries via LLM."""
    db = _get_db()

    if "file" not in request.files:
        abort(400, description=t("kb.upload_error", error="No file provided"))

    file = request.files["file"]
    if not file.filename:
        abort(400, description=t("kb.upload_error", error="Empty filename"))

    if not _allowed_file(file.filename):
        abort(400, description=t("kb.upload_error", error="Unsupported file type"))

    # Check file size
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > _MAX_UPLOAD_SIZE:
        abort(413, description=t("kb.upload_error", error="File exceeds 10 MB limit"))

    # Save to temp file then process
    safe_name = _safe_filename(file.filename)
    suffix = Path(safe_name).suffix

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            file.save(tmp)
            tmp_path = Path(tmp.name)

        # Get LLM config from app state
        llm_config = getattr(app_state, "config", None)
        llm_cfg = getattr(llm_config, "llm", None) if llm_config else None

        from core.knowledge_base import KnowledgeBase

        kb = KnowledgeBase(db)

        # Upload dir for permanent storage
        upload_dir = Path.home() / ".autoapply" / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)

        count = kb.process_upload(tmp_path, llm_config=llm_cfg, upload_dir=upload_dir)

        return jsonify({
            "success": True,
            "entries_created": count,
            "message": t("kb.upload_success", count=count),
        }), 201

    except Exception as e:
        logger.error("Upload processing failed: %s", e)
        abort(500, description=t("kb.upload_error", error=str(e)))
    finally:
        # Cleanup temp file
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# ATS Scoring
# ---------------------------------------------------------------------------


@kb_bp.route("/api/kb/ats-score", methods=["POST"])
def ats_score():
    """Score KB entries against a JD for ATS compatibility.

    Request body:
        jd_text: str (required)
        platform: str (optional — greenhouse/lever/workday/ashby/icims/taleo)
        entry_ids: list[int] (optional — if omitted, uses all active entries)
    """
    db = _get_db()
    data = request.get_json(silent=True)
    if not data or not data.get("jd_text"):
        abort(400, description=t("errors.invalid_request"))

    jd_text = data["jd_text"]
    platform = data.get("platform", "default")
    entry_ids = data.get("entry_ids")

    from core.ats_profiles import get_weights
    from core.ats_scorer import score_ats

    # Get entries
    if entry_ids:
        entries = db.get_kb_entries_by_ids(entry_ids)
    else:
        entries = db.get_kb_entries(active_only=True, limit=2000)

    if not entries:
        abort(400, description=t("kb.entries_empty"))

    weights = get_weights(platform)
    result = score_ats(jd_text, entries, weights)
    result["platform"] = platform

    return jsonify(result)


@kb_bp.route("/api/kb/ats-profiles", methods=["GET"])
def ats_profiles():
    """List available ATS platform profiles."""
    from core.ats_profiles import list_profiles

    return jsonify({"profiles": list_profiles()})


# ---------------------------------------------------------------------------
# KB entries CRUD
# ---------------------------------------------------------------------------


@kb_bp.route("/api/kb/stats", methods=["GET"])
def get_stats():
    """Return KB statistics (counts by category)."""
    db = _get_db()
    stats = db.get_kb_stats()
    return jsonify(stats)


@kb_bp.route("/api/kb", methods=["GET"])
def list_entries():
    """List KB entries with optional filtering."""
    db = _get_db()

    category = request.args.get("category")
    search = request.args.get("search")
    limit = min(int(request.args.get("limit", 100)), 500)
    offset = int(request.args.get("offset", 0))

    entries = db.get_kb_entries(
        category=category,
        active_only=True,
        search=search,
        limit=limit,
        offset=offset,
    )

    return jsonify({"entries": entries, "count": len(entries)})


@kb_bp.route("/api/kb/<int:entry_id>", methods=["GET"])
def get_entry(entry_id: int):
    """Get a single KB entry."""
    db = _get_db()
    entry = db.get_kb_entry(entry_id)
    if entry is None:
        abort(404, description=t("errors.not_found"))
    return jsonify(entry)


@kb_bp.route("/api/kb/<int:entry_id>", methods=["PUT"])
def update_entry(entry_id: int):
    """Update a KB entry's text, subsection, job_types, or tags."""
    db = _get_db()
    data = request.get_json(silent=True)
    if not data:
        abort(400, description=t("errors.invalid_request"))

    updated = db.update_kb_entry(
        entry_id=entry_id,
        text=data.get("text"),
        subsection=data.get("subsection"),
        job_types=data.get("job_types"),
        tags=data.get("tags"),
    )

    if not updated:
        abort(404, description=t("errors.not_found"))

    return jsonify({"success": True})


@kb_bp.route("/api/kb/<int:entry_id>", methods=["DELETE"])
def delete_entry(entry_id: int):
    """Soft-delete a KB entry."""
    db = _get_db()
    deleted = db.soft_delete_kb_entry(entry_id)
    if not deleted:
        abort(404, description=t("errors.not_found"))

    return jsonify({"success": True})


# ---------------------------------------------------------------------------
# Documents list
# ---------------------------------------------------------------------------


@kb_bp.route("/api/kb/documents", methods=["GET"])
def list_documents():
    """List all uploaded documents."""
    db = _get_db()
    docs = db.get_uploaded_documents()
    return jsonify({"documents": docs})


# ---------------------------------------------------------------------------
# Resume preview
# ---------------------------------------------------------------------------


@kb_bp.route("/api/kb/preview", methods=["POST"])
def preview_resume():
    """Preview a resume assembled from KB entries with a chosen template.

    Request body:
        template: str (classic/modern/academic/minimal)
        entry_ids: list[int] (optional — if omitted, auto-select from JD)
        jd_text: str (optional — for auto-selection scoring)
    """
    db = _get_db()
    data = request.get_json(silent=True)
    if not data:
        abort(400, description=t("errors.invalid_request"))

    template = data.get("template", "classic")
    entry_ids = data.get("entry_ids")
    jd_text = data.get("jd_text", "")

    from core.knowledge_base import KnowledgeBase
    from core.latex_compiler import compile_resume, find_pdflatex
    from core.resume_assembler import _build_context, _select_entries
    from core.resume_scorer import score_kb_entries

    kb = KnowledgeBase(db)

    # Get profile from config
    config = getattr(app_state, "config", None)
    profile_cfg = getattr(config, "profile", None) if config else None
    profile = {
        "name": getattr(profile_cfg, "full_name", "") or "",
        "email": getattr(profile_cfg, "email", "") or "",
        "phone": getattr(profile_cfg, "phone", "") or "",
        "location": getattr(profile_cfg, "location", "") or "",
    }

    if entry_ids:
        # Use specific entries
        entries = db.get_kb_entries_by_ids(entry_ids)
        # Group by category
        selected: dict[str, list[dict]] = {}
        for e in entries:
            cat = e.get("category", "experience")
            selected.setdefault(cat, []).append(e)
    elif jd_text:
        # Auto-select via scoring
        all_entries = kb.get_all_entries(active_only=True, limit=2000)
        if not all_entries:
            abort(400, description=t("kb.entries_empty"))
        reuse_cfg = getattr(config, "resume_reuse", None) if config else None
        scored = score_kb_entries(jd_text, all_entries, reuse_cfg)
        if not scored:
            abort(400, description=t("kb.entries_empty"))
        from config.settings import ResumeReuseConfig
        selected_result = _select_entries(scored, reuse_cfg or ResumeReuseConfig())
        if selected_result is None:
            abort(400, description=t("kb.entries_empty"))
        selected = selected_result
    else:
        abort(400, description=t("errors.invalid_request"))

    # Build context and compile
    context = _build_context(profile, selected)

    pdflatex = find_pdflatex()
    if pdflatex is None:
        abort(503, description=t("errors.pdflatex_not_found"))

    pdf_bytes = compile_resume(template, context, pdflatex_path=pdflatex)
    if pdf_bytes is None:
        abort(500, description=t("errors.compilation_failed"))

    from flask import Response

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename=preview_{template}.pdf"},
    )
