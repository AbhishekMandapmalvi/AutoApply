"""Main bot loop — search, filter, generate documents, apply, repeat.

Implements: FR-042 (bot main loop), FR-050 (search-filter-generate-apply pipeline),
            FR-086–FR-089 (portal auth integration).
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from bot.apply.ashby import AshbyApplier
from bot.apply.base import ApplyResult, BaseApplier
from bot.apply.greenhouse import GreenhouseApplier
from bot.apply.indeed import IndeedApplier
from bot.apply.lever import LeverApplier
from bot.apply.linkedin import LinkedInApplier
from bot.apply.workday import WorkdayApplier
from bot.browser import BrowserManager
from bot.search.indeed import IndeedSearcher
from bot.search.linkedin import LinkedInSearcher
from core.filter import ScoredJob, detect_ats, score_job

if TYPE_CHECKING:
    from bot.state import BotState
    from config.settings import AppConfig
    from db.database import Database

logger = logging.getLogger(__name__)

SEARCHERS = {
    "linkedin": LinkedInSearcher,
    "indeed": IndeedSearcher,
}

APPLIERS: dict[str, type[BaseApplier]] = {
    "linkedin": LinkedInApplier,
    "indeed": IndeedApplier,
    "greenhouse": GreenhouseApplier,
    "lever": LeverApplier,
    "workday": WorkdayApplier,
    "ashby": AshbyApplier,
}


def run_bot(
    state: "BotState",
    config: "AppConfig",
    db: "Database",
    emit_func=None,
) -> None:
    """Main bot loop.

    Iterates: search → filter → generate docs → apply → save to DB.
    Respects stop_flag, pause state, and daily application limits.

    Args:
        state: Thread-safe bot state (status, counters, stop flag).
        config: Application configuration.
        db: Database for saving applications and dedup checks.
        emit_func: Callable to emit SocketIO events. Signature:
                   ``emit_func(event_name, data_dict)``.
    """
    profile_dir = Path.home() / ".autoapply" / "profile"
    browser = None

    def emit(event_type: str, **kwargs):
        """Emit a feed event via SocketIO and save to DB."""
        data = {"type": event_type, **kwargs}
        if emit_func:
            try:
                emit_func("feed_event", data)
            except Exception as e:
                logger.debug("Failed to emit feed event via SocketIO: %s", e)
        try:
            db.save_feed_event(
                event_type=event_type,
                job_title=kwargs.get("job_title"),
                company=kwargs.get("company"),
                platform=kwargs.get("platform"),
                message=kwargs.get("message"),
            )
        except Exception as e:
            logger.warning("Failed to save feed event to DB: %s", e)

    try:
        browser = BrowserManager(config)
        page = browser.get_page()

        enabled_searchers = [
            SEARCHERS[p]()
            for p in config.bot.enabled_platforms
            if p in SEARCHERS
        ]

        if not enabled_searchers:
            logger.warning("No enabled search platforms configured")
            return

        while not state.stop_flag:
            _wait_while_paused(state)
            if state.stop_flag:
                break

            for searcher in enabled_searchers:
                if state.stop_flag:
                    break

                try:
                    for raw_job in searcher.search(config.search_criteria, page=page):
                        if state.stop_flag:
                            break

                        _wait_while_paused(state)
                        if state.stop_flag:
                            break

                        state.increment_found()
                        emit(
                            "FOUND",
                            job_title=raw_job.title,
                            company=raw_job.company,
                            platform=raw_job.platform,
                            message=f"Found: {raw_job.title} at {raw_job.company}",
                        )

                        # Check daily limit
                        if state.applied_today >= config.bot.max_applications_per_day:
                            logger.info(
                                "Daily limit reached (%d). Waiting for next cycle.",
                                config.bot.max_applications_per_day,
                            )
                            break

                        # Score and filter
                        scored = score_job(raw_job, config, db)
                        if not scored.pass_filter:
                            emit(
                                "FILTERED",
                                job_title=raw_job.title,
                                company=raw_job.company,
                                platform=raw_job.platform,
                                message=f"Filtered: {scored.skip_reason}",
                            )
                            continue

                        # Save job description for interview prep
                        desc_path = _save_job_description(scored, profile_dir)

                        # Generate documents
                        emit(
                            "GENERATING",
                            job_title=raw_job.title,
                            company=raw_job.company,
                            platform=raw_job.platform,
                            message="Generating tailored resume and cover letter...",
                        )

                        resume_path, cl_path, cover_letter_text, version_meta = _generate_docs(
                            scored, config, profile_dir, db=db
                        )

                        # Review gate — pause for user approval in review/watch modes
                        if config.bot.apply_mode in ("review", "watch"):
                            emit(
                                "REVIEW",
                                job_title=raw_job.title,
                                company=raw_job.company,
                                platform=raw_job.platform,
                                match_score=scored.score,
                                cover_letter=cover_letter_text,
                                apply_url=raw_job.apply_url,
                                message=f"Review: {raw_job.title} at {raw_job.company} (score {scored.score})",
                            )

                            decision, edited_cl = _wait_for_review(state)
                            if decision == "stop":
                                break
                            if decision == "skip":
                                emit(
                                    "SKIPPED",
                                    job_title=raw_job.title,
                                    company=raw_job.company,
                                    platform=raw_job.platform,
                                    message=f"Skipped: {raw_job.title} at {raw_job.company}",
                                )
                                continue
                            if decision == "edit" and edited_cl:
                                cover_letter_text = edited_cl
                            if decision == "manual":
                                # User will apply themselves — save as manual_required
                                manual_result = ApplyResult(
                                    success=False,
                                    manual_required=True,
                                    error_message="User chose to apply manually",
                                )
                                _save_application(
                                    db, scored, resume_path, cl_path,
                                    cover_letter_text, manual_result,
                                    description_path=desc_path,
                                    version_meta=version_meta,
                                )
                                emit(
                                    "APPLIED",
                                    job_title=raw_job.title,
                                    company=raw_job.company,
                                    platform=raw_job.platform,
                                    message=f"Marked for manual apply: {raw_job.title} at {raw_job.company}",
                                )
                                continue

                        # Apply
                        emit(
                            "APPLYING",
                            job_title=raw_job.title,
                            company=raw_job.company,
                            platform=raw_job.platform,
                            message=f"Applying via {detect_ats(raw_job.apply_url) or raw_job.platform}...",
                        )

                        result = _apply_to_job(
                            scored, resume_path, cover_letter_text, config, page,
                            db=db,
                        )

                        # Login gate — pause for user to log in (FR-089)
                        if result.login_required:
                            domain = result.login_domain or "unknown"
                            portal_type = result.login_portal_type or "generic"
                            emit(
                                "LOGIN_REQUIRED",
                                job_title=raw_job.title,
                                company=raw_job.company,
                                platform=raw_job.platform,
                                domain=domain,
                                portal_type=portal_type,
                                message=f"Login required at {domain} — please log in manually",
                            )

                            state.begin_login_gate(
                                domain, portal_type, raw_job.apply_url,
                            )
                            login_decision = state.wait_for_login()

                            if login_decision == "stop":
                                break
                            if login_decision == "skip":
                                emit(
                                    "SKIPPED",
                                    job_title=raw_job.title,
                                    company=raw_job.company,
                                    platform=raw_job.platform,
                                    message=f"Skipped (login not completed): {raw_job.title}",
                                )
                                # Save as login_required so user can retry later
                                _save_application(
                                    db, scored, resume_path, cl_path,
                                    cover_letter_text, result,
                                    description_path=desc_path,
                                    version_meta=version_meta,
                                )
                                continue

                            # User logged in — retry the application
                            result = _apply_to_job(
                                scored, resume_path, cover_letter_text, config, page,
                                db=db,
                            )

                        # Save to DB
                        _save_application(
                            db, scored, resume_path, cl_path,
                            cover_letter_text, result,
                            description_path=desc_path,
                            version_meta=version_meta,
                        )

                        # Emit result
                        if result.success:
                            state.increment_applied()
                            emit(
                                "APPLIED",
                                job_title=raw_job.title,
                                company=raw_job.company,
                                platform=raw_job.platform,
                                message=f"Applied to {raw_job.title} at {raw_job.company}",
                            )
                        elif result.captcha_detected:
                            state.increment_errors()
                            emit(
                                "CAPTCHA",
                                job_title=raw_job.title,
                                company=raw_job.company,
                                platform=raw_job.platform,
                                message=f"CAPTCHA detected at {raw_job.company}",
                            )
                        else:
                            state.increment_errors()
                            emit(
                                "ERROR",
                                job_title=raw_job.title,
                                company=raw_job.company,
                                platform=raw_job.platform,
                                message=result.error_message or "Application failed",
                            )

                        # Rate limit between applications
                        if not state.stop_flag:
                            time.sleep(config.bot.delay_between_applications_seconds)

                except Exception as e:
                    logger.error("Search/apply cycle error: %s", e)
                    state.increment_errors()
                    emit(
                        "ERROR",
                        message=f"Search cycle error: {e}",
                    )

            # Wait for next search interval
            if not state.stop_flag:
                logger.info(
                    "Search cycle complete. Waiting %ds for next cycle.",
                    config.bot.search_interval_seconds,
                )
                _interruptible_sleep(state, config.bot.search_interval_seconds)

    except Exception as exc:
        logger.exception("Bot crashed")
        state.increment_errors()
        emit("ERROR", message=f"Bot crashed: {exc}")
    finally:
        if browser:
            browser.close()
        logger.info("Bot loop exited")


def _wait_while_paused(state: "BotState") -> None:
    """Block while bot is paused, checking every second."""
    while state.status == "paused" and not state.stop_flag:
        time.sleep(1)


def _interruptible_sleep(state: "BotState", seconds: int) -> None:
    """Sleep for `seconds` but wake up immediately if stop_flag is set."""
    for _ in range(seconds):
        if state.stop_flag:
            return
        time.sleep(1)


def _wait_for_review(state: "BotState") -> tuple[str, str | None]:
    """Block the bot thread until the user makes a review decision.

    Returns:
        (decision, edited_cover_letter) where decision is
        "approve", "skip", "edit", or "stop".
    """
    state.begin_review()
    return state.wait_for_review()


def _generate_docs(scored: ScoredJob, config, profile_dir: Path, db=None):
    """Generate resume and cover letter, KB-first with LLM fallback.

    Pipeline (TASK-030 M4):
      1. Try KB assembly (0 API calls) if resume reuse enabled + KB populated
      2. Fall through to LLM generation if KB assembly returns None
      3. After LLM generation, ingest new entries into KB for future reuse
    """
    from core.ai_engine import generate_documents

    resume_path = None
    cl_path = None
    cover_letter_text = ""
    version_meta = None

    skip_cover_letter = not config.bot.cover_letter_enabled

    # --- Phase 1: Try KB assembly (LLM-powered with strict KB data) ---
    kb_result = _try_kb_assembly(scored, config, profile_dir)
    if kb_result is not None:
        resume_path = kb_result["resume_path"]
        if not skip_cover_letter:
            cover_letter_text = config.bot.cover_letter_template or ""
        version_meta = {
            "resume_md_path": "",  # KB assembly has no .md
            "resume_pdf_path": str(resume_path),
            "llm_provider": None,
            "llm_model": None,
            "reuse_source": "kb_assembly",
            "source_entry_ids": kb_result["entry_ids"],
        }
        logger.info("KB assembly produced resume for %s at %s", scored.raw.company, scored.raw.title)
        return resume_path, cl_path, cover_letter_text, version_meta

    # --- Phase 2: LLM generation (standard path) ---
    try:
        resume_path, cl_path, version_meta = generate_documents(
            job=scored,
            profile=config.profile,
            experience_dir=profile_dir / "experiences",
            output_dir_resumes=profile_dir / "resumes",
            output_dir_cover_letters=profile_dir / "cover_letters",
            llm_config=config.llm,
            skip_cover_letter=skip_cover_letter,
        )
        if cl_path and cl_path.exists():
            cover_letter_text = cl_path.read_text(encoding="utf-8")

        # Tag as LLM-generated for version tracking
        if version_meta:
            version_meta["reuse_source"] = "llm_generated"
            version_meta["source_entry_ids"] = []

        # --- Phase 3: Ingest LLM output into KB for future reuse ---
        _ingest_llm_output(resume_path, config, db)

    except Exception as e:
        logger.warning("Document generation failed, using fallback: %s", e)
        # Fallback to static templates
        if config.profile.fallback_resume_path:
            fallback = Path(config.profile.fallback_resume_path)
            if fallback.exists():
                resume_path = fallback
        if not skip_cover_letter:
            cover_letter_text = config.bot.cover_letter_template or ""

    return resume_path, cl_path, cover_letter_text, version_meta


def _try_kb_assembly(scored: ScoredJob, config, profile_dir: Path) -> dict | None:
    """Attempt to assemble a resume from KB entries. Returns None if not viable."""
    try:
        from core.knowledge_base import KnowledgeBase
        from core.resume_assembler import assemble_resume, save_assembled_resume
        from db.database import Database

        data_dir = Path.home() / ".autoapply"
        db = Database(data_dir / "autoapply.db")
        kb = KnowledgeBase(db)

        profile = {
            "name": config.profile.full_name or "",
            "email": config.profile.email or "",
            "phone": config.profile.phone or "",
            "location": config.profile.location or "",
        }

        jd_text = scored.raw.description or ""
        if not jd_text:
            return None

        result = assemble_resume(
            jd_text=jd_text,
            profile=profile,
            kb=kb,
            reuse_config=config.resume_reuse,
            llm_config=config.llm,
        )

        if result is None:
            return None

        # Save PDF to resumes directory
        output_dir = profile_dir / "resumes"
        pdf_path = save_assembled_resume(
            pdf_bytes=result["pdf_bytes"],
            output_dir=output_dir,
            company=scored.raw.company or "unknown",
            job_title=scored.raw.title or "unknown",
        )

        return {
            "resume_path": pdf_path,
            "entry_ids": result["entry_ids"],
        }

    except Exception as e:
        logger.debug("KB assembly not available: %s", e)
        return None


def _ingest_llm_output(resume_path, config, db) -> None:
    """Ingest LLM-generated resume into KB for future reuse."""
    if not config.resume_reuse.enabled:
        return

    try:
        from core.knowledge_base import KnowledgeBase
        from core.resume_assembler import ingest_llm_resume
        from db.database import Database

        if db is None:
            data_dir = Path.home() / ".autoapply"
            db = Database(data_dir / "autoapply.db")
        kb = KnowledgeBase(db)

        # Try to read .md version (same name, .md extension)
        if resume_path and resume_path.exists():
            md_path = resume_path.with_suffix(".md")
            if md_path.exists():
                resume_md = md_path.read_text(encoding="utf-8")
                ingest_llm_resume(resume_md, kb)
    except Exception as e:
        logger.debug("LLM resume ingestion skipped: %s", e)


def _apply_to_job(scored, resume_path, cover_letter_text, config, page, db=None):
    """Apply to a job using the appropriate platform applier.

    Integrates portal auth: detects login walls after navigation,
    attempts auto-login with stored credentials, and signals login_required
    when manual intervention is needed (FR-086–FR-089).
    """
    from core.portal_auth import PortalAuthManager

    platform = detect_ats(scored.raw.apply_url) or scored.raw.platform

    applier_cls = APPLIERS.get(platform)
    if not applier_cls:
        return ApplyResult(
            success=False, manual_required=True,
            error_message=f"No applier for platform: {platform}",
        )

    # Navigate to the apply URL first to check for login walls
    try:
        page.goto(
            scored.raw.apply_url,
            wait_until="domcontentloaded",
            timeout=30000,
        )
    except Exception as e:
        logger.warning("Navigation failed for %s: %s", scored.raw.apply_url, e)

    # Login detection + auto-login (FR-087, FR-088)
    if db and PortalAuthManager.detect_login_wall(page):
        domain = PortalAuthManager.extract_domain(scored.raw.apply_url)
        portal_type = PortalAuthManager.detect_portal_type(scored.raw.apply_url)
        auth_mgr = PortalAuthManager(db)

        logger.info("Login wall detected at %s (domain: %s)", scored.raw.apply_url, domain)

        # Try auto-login with stored credentials
        if auth_mgr.get_credential(domain):
            if auth_mgr.try_auto_login(page, domain, portal_type):
                logger.info("Auto-login succeeded for %s", domain)
            else:
                # Auto-login failed — signal browser handoff (FR-089)
                logger.warning("Auto-login failed for %s, requesting manual login", domain)
                return ApplyResult(
                    success=False,
                    login_required=True,
                    login_domain=domain,
                    login_portal_type=portal_type,
                    error_message=f"Auto-login failed at {domain}",
                )
        else:
            # No stored credentials — signal browser handoff (FR-089)
            logger.info("No credentials for %s, requesting manual login", domain)
            return ApplyResult(
                success=False,
                login_required=True,
                login_domain=domain,
                login_portal_type=portal_type,
                error_message=f"Login required at {domain} (first visit)",
            )

    applier = applier_cls(page)
    return applier.apply(scored, resume_path, cover_letter_text, config.profile)


def _save_job_description(scored: ScoredJob, profile_dir: Path) -> Path | None:
    """Save the job description as an HTML file for later reference.

    Returns the path to the saved file, or None on failure.
    """
    try:
        desc_dir = profile_dir / "job_descriptions"
        desc_dir.mkdir(parents=True, exist_ok=True)

        safe_company = re.sub(r"[^a-zA-Z0-9]+", "-", scored.raw.company).strip("-").lower()
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        base_name = f"{scored.raw.external_id[:8]}_{safe_company}_{date_str}"
        desc_path = desc_dir / f"{base_name}.html"

        html = (
            "<!DOCTYPE html>\n<html lang='en'>\n<head>\n"
            "<meta charset='utf-8'>\n"
            f"<title>{_esc(scored.raw.title)} — {_esc(scored.raw.company)}</title>\n"
            "<style>body{font-family:system-ui,sans-serif;max-width:800px;"
            "margin:40px auto;padding:0 20px;line-height:1.6;color:#222}"
            "h1{font-size:1.4rem;margin-bottom:4px}"
            ".meta{color:#666;font-size:.9rem;margin-bottom:24px}"
            ".meta span{margin-right:16px}"
            "a{color:#2563eb}</style>\n"
            "</head>\n<body>\n"
            f"<h1>{_esc(scored.raw.title)}</h1>\n"
            f"<div class='meta'>"
            f"<span><strong>{_esc(scored.raw.company)}</strong></span>"
            f"<span>{_esc(scored.raw.location or '')}</span>"
            f"<span>{_esc(scored.raw.salary or '')}</span>"
            f"</div>\n"
            f"<div class='description'>\n{_plain_to_html(scored.raw.description)}\n</div>\n"
            f"<hr>\n<p class='meta'>Source: <a href='{_esc(scored.raw.apply_url)}'>"
            f"{_esc(scored.raw.apply_url)}</a> | Saved {date_str}</p>\n"
            "</body>\n</html>"
        )

        desc_path.write_text(html, encoding="utf-8")
        return desc_path
    except Exception as e:
        logger.warning("Failed to save job description: %s", e)
        return None


def _esc(text: str) -> str:
    """Minimal HTML escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _plain_to_html(text: str) -> str:
    """Convert plain text to simple HTML paragraphs."""
    escaped = _esc(text)
    paragraphs = escaped.split("\n\n")
    if len(paragraphs) > 1:
        return "\n".join(f"<p>{p.strip()}</p>" for p in paragraphs if p.strip())
    return escaped.replace("\n", "<br>\n")


def _save_application(db, scored, resume_path, cl_path, cover_letter_text, result,
                      description_path=None, version_meta=None):
    """Save an application record and optional resume version to the database."""
    try:
        status = "applied" if result.success else (
            "manual_required" if result.manual_required else "error"
        )
        app_id = db.save_application(
            external_id=scored.raw.external_id,
            platform=scored.raw.platform,
            job_title=scored.raw.title,
            company=scored.raw.company,
            location=scored.raw.location,
            salary=scored.raw.salary,
            apply_url=scored.raw.apply_url,
            match_score=scored.score,
            resume_path=str(resume_path) if resume_path else None,
            cover_letter_path=str(cl_path) if cl_path else None,
            cover_letter_text=cover_letter_text,
            status=status,
            error_message=result.error_message,
            description_path=str(description_path) if description_path else None,
        )

        # Record resume version if generated (FR-118, TASK-030 M4)
        if version_meta and app_id:
            try:
                import json as _json
                entry_ids = version_meta.get("source_entry_ids", [])
                db.save_resume_version(
                    application_id=app_id,
                    job_title=scored.raw.title,
                    company=scored.raw.company,
                    resume_md_path=version_meta.get("resume_md_path", ""),
                    resume_pdf_path=version_meta.get("resume_pdf_path", ""),
                    match_score=scored.score,
                    llm_provider=version_meta.get("llm_provider"),
                    llm_model=version_meta.get("llm_model"),
                    reuse_source=version_meta.get("reuse_source"),
                    source_entry_ids=_json.dumps(entry_ids) if entry_ids else None,
                )
            except Exception as e:
                logger.warning("Failed to save resume version: %s", e)
    except Exception as e:
        logger.error("Failed to save application to DB: %s", e)
