"""Bot state machine — tracks status, counters, review gate, and login gate.

Implements: FR-041 (bot state machine), FR-089 (browser handoff login gate).
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone


class BotState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._status: str = "stopped"
        self._stop_flag: bool = False
        self._jobs_found_today: int = 0
        self._applied_today: int = 0
        self._start_time: datetime | None = None
        self._errors_today: int = 0

        # Review gate — bot blocks here until user decides
        self._review_event = threading.Event()
        self._review_decision: str | None = None  # "approve" | "skip" | "edit"
        self._review_edits: str | None = None  # edited cover letter text
        self._awaiting_review: bool = False

        # Login gate — bot blocks here until user logs in manually (FR-089)
        self._login_event = threading.Event()
        self._login_decision: str | None = None  # "done" | "skip"
        self._awaiting_login: bool = False
        self._login_context: dict | None = None  # domain, portal_type, url

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @property
    def stop_flag(self) -> bool:
        with self._lock:
            return self._stop_flag

    @property
    def jobs_found_today(self) -> int:
        with self._lock:
            return self._jobs_found_today

    @property
    def applied_today(self) -> int:
        with self._lock:
            return self._applied_today

    @property
    def start_time(self) -> datetime | None:
        with self._lock:
            return self._start_time

    @property
    def errors_today(self) -> int:
        with self._lock:
            return self._errors_today

    @property
    def awaiting_review(self) -> bool:
        with self._lock:
            return self._awaiting_review

    @property
    def awaiting_login(self) -> bool:
        with self._lock:
            return self._awaiting_login

    @property
    def login_context(self) -> dict | None:
        with self._lock:
            return self._login_context

    def start(self) -> None:
        with self._lock:
            self._status = "running"
            self._stop_flag = False
            self._start_time = datetime.now(timezone.utc)

    def pause(self) -> None:
        with self._lock:
            self._status = "paused"

    def stop(self) -> None:
        with self._lock:
            self._status = "stopped"
            self._stop_flag = True
            self._start_time = None
            # Unblock gates so bot thread can exit
            self._review_event.set()
            self._login_event.set()

    def resume(self) -> None:
        with self._lock:
            self._status = "running"

    def increment_found(self) -> None:
        with self._lock:
            self._jobs_found_today += 1

    def increment_applied(self) -> None:
        with self._lock:
            self._applied_today += 1

    def increment_errors(self) -> None:
        with self._lock:
            self._errors_today += 1

    def reset_daily(self) -> None:
        with self._lock:
            self._jobs_found_today = 0
            self._applied_today = 0
            self._errors_today = 0

    def begin_review(self) -> None:
        """Signal that the bot is waiting for a user review decision."""
        with self._lock:
            self._review_event.clear()
            self._review_decision = None
            self._review_edits = None
            self._awaiting_review = True

    def set_review_decision(self, decision: str, edits: str | None = None) -> None:
        """Set the user's review decision and unblock the bot thread.

        Args:
            decision: One of ``"approve"``, ``"skip"``, or ``"edit"``.
            edits: Edited cover letter text (only used when decision is ``"edit"``).
        """
        with self._lock:
            self._review_decision = decision
            self._review_edits = edits
            self._awaiting_review = False
            self._review_event.set()

    def wait_for_review(self) -> tuple[str, str | None]:
        """Block until a review decision is set or stop is requested.

        Returns:
            ``(decision, edited_cover_letter)`` where decision is
            ``"approve"``, ``"skip"``, ``"edit"``, or ``"stop"``
            if the bot was stopped while waiting.
        """
        self._review_event.wait()
        with self._lock:
            if self._stop_flag:
                return "stop", None
            return self._review_decision or "skip", self._review_edits

    # ------------------------------------------------------------------
    # Login gate (FR-089)
    # ------------------------------------------------------------------

    def begin_login_gate(self, domain: str, portal_type: str, url: str) -> None:
        """Signal that the bot is waiting for the user to log in manually."""
        with self._lock:
            self._login_event.clear()
            self._login_decision = None
            self._awaiting_login = True
            self._login_context = {
                "domain": domain,
                "portal_type": portal_type,
                "url": url,
            }

    def set_login_decision(self, decision: str) -> None:
        """Set the user's login decision and unblock the bot thread.

        Args:
            decision: ``"done"`` (user logged in) or ``"skip"`` (skip this job).
        """
        with self._lock:
            self._login_decision = decision
            self._awaiting_login = False
            self._login_context = None
            self._login_event.set()

    def wait_for_login(self) -> str:
        """Block until a login decision is set or stop is requested.

        Returns:
            ``"done"``, ``"skip"``, or ``"stop"`` if the bot was stopped.
        """
        self._login_event.wait()
        with self._lock:
            if self._stop_flag:
                return "stop"
            return self._login_decision or "skip"

    def get_status_dict(self) -> dict:
        with self._lock:
            uptime_seconds = 0.0
            if self._start_time is not None:
                uptime_seconds = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            return {
                "status": self._status,
                "stop_flag": self._stop_flag,
                "jobs_found_today": self._jobs_found_today,
                "applied_today": self._applied_today,
                "errors_today": self._errors_today,
                "start_time": self._start_time.isoformat() if self._start_time else None,
                "uptime_seconds": uptime_seconds,
                "awaiting_review": self._awaiting_review,
                "awaiting_login": self._awaiting_login,
                "login_context": self._login_context,
            }
