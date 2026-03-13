"""Unit tests for bot.state.BotState.

Requirement traceability:
    FR-005  — Bot runtime state management
    AC-005-1 — Initial state defaults
    AC-005-2 — Start transition
    AC-005-3 — Pause transition
    AC-005-4 — Stop transition
    AC-005-5 — Uptime tracking
    AC-005-6 — Daily counter reset
    AC-005-N1 — Thread-safety guarantee
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from bot.state import BotState

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def state() -> BotState:
    """Return a fresh BotState instance."""
    return BotState()


# ===================================================================
# Initial state (AC-005-1)
# ===================================================================

class TestInitialState:
    """Verify all defaults immediately after construction."""

    def test_initial_status_stopped(self, state: BotState) -> None:
        """AC-005-1: status must default to 'stopped'."""
        assert state.status == "stopped"

    def test_initial_stop_flag_false(self, state: BotState) -> None:
        """AC-005-1: stop_flag must default to False."""
        assert state.stop_flag is False

    def test_initial_counters_zero(self, state: BotState) -> None:
        """AC-005-1: all daily counters must default to 0."""
        assert state.jobs_found_today == 0
        assert state.applied_today == 0
        assert state.errors_today == 0

    def test_initial_start_time_none(self, state: BotState) -> None:
        """AC-005-1: start_time must default to None."""
        assert state.start_time is None


# ===================================================================
# State transitions (AC-005-2, AC-005-3, AC-005-4, FR-005)
# ===================================================================

class TestStateTransitions:
    """Verify start / pause / stop / resume transitions."""

    def test_start_sets_running(self, state: BotState) -> None:
        """AC-005-2: start() must set status to 'running'."""
        state.start()
        assert state.status == "running"

    def test_start_sets_start_time(self, state: BotState) -> None:
        """AC-005-2: start() must record a UTC start_time."""
        before = datetime.now(timezone.utc)
        state.start()
        after = datetime.now(timezone.utc)

        assert state.start_time is not None
        assert before <= state.start_time <= after

    def test_start_clears_stop_flag(self, state: BotState) -> None:
        """AC-005-2: start() must clear the stop_flag."""
        # Put state into stopped (sets stop_flag True), then start.
        state.stop()
        assert state.stop_flag is True

        state.start()
        assert state.stop_flag is False

    def test_pause_sets_paused(self, state: BotState) -> None:
        """AC-005-3: pause() must set status to 'paused'."""
        state.start()
        state.pause()
        assert state.status == "paused"

    def test_stop_sets_stopped(self, state: BotState) -> None:
        """AC-005-4: stop() must set status to 'stopped'."""
        state.start()
        state.stop()
        assert state.status == "stopped"

    def test_stop_sets_stop_flag_true(self, state: BotState) -> None:
        """AC-005-4: stop() must set stop_flag to True."""
        state.start()
        state.stop()
        assert state.stop_flag is True

    def test_stop_clears_start_time(self, state: BotState) -> None:
        """AC-005-4: stop() must reset start_time to None."""
        state.start()
        assert state.start_time is not None

        state.stop()
        assert state.start_time is None

    def test_resume_sets_running(self, state: BotState) -> None:
        """FR-005: resume() must set status back to 'running'."""
        state.start()
        state.pause()
        state.resume()
        assert state.status == "running"


# ===================================================================
# Counters (FR-005)
# ===================================================================

class TestCounters:
    """Verify counter increment and daily reset behaviour."""

    def test_increment_found(self, state: BotState) -> None:
        """FR-005: increment_found() must increase jobs_found_today by 1."""
        state.increment_found()
        state.increment_found()
        assert state.jobs_found_today == 2

    def test_increment_applied(self, state: BotState) -> None:
        """FR-005: increment_applied() must increase applied_today by 1."""
        state.increment_applied()
        state.increment_applied()
        state.increment_applied()
        assert state.applied_today == 3

    def test_increment_errors(self, state: BotState) -> None:
        """FR-005: increment_errors() must increase errors_today by 1."""
        state.increment_errors()
        assert state.errors_today == 1

    def test_reset_daily_clears_all_counters(self, state: BotState) -> None:
        """AC-005-6: reset_daily() must zero every daily counter."""
        state.increment_found()
        state.increment_applied()
        state.increment_errors()

        state.reset_daily()

        assert state.jobs_found_today == 0
        assert state.applied_today == 0
        assert state.errors_today == 0


# ===================================================================
# Status dict (FR-005, AC-005-5)
# ===================================================================

class TestGetStatusDict:
    """Verify the shape and values of get_status_dict()."""

    EXPECTED_KEYS = {
        "status",
        "stop_flag",
        "jobs_found_today",
        "applied_today",
        "errors_today",
        "start_time",
        "uptime_seconds",
        "awaiting_review",
        "awaiting_login",
        "login_context",
    }

    def test_get_status_dict_structure(self, state: BotState) -> None:
        """FR-005: returned dict must contain all required keys."""
        result = state.get_status_dict()
        assert set(result.keys()) == self.EXPECTED_KEYS

    def test_get_status_dict_uptime_positive_when_running(self, state: BotState) -> None:
        """AC-005-5: uptime_seconds must be > 0 while running."""
        # Pin "now" so we can control the elapsed time.
        fixed_start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        fixed_now = datetime(2026, 1, 1, 0, 5, 0, tzinfo=timezone.utc)  # +300 s

        with patch("bot.state.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_start
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            state.start()

        with patch("bot.state.datetime") as mock_dt:
            mock_dt.now.return_value = fixed_now
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            result = state.get_status_dict()

        assert result["uptime_seconds"] == pytest.approx(300.0)

    def test_get_status_dict_uptime_zero_when_stopped(self, state: BotState) -> None:
        """FR-005: uptime_seconds must be 0 when bot is stopped."""
        result = state.get_status_dict()
        assert result["uptime_seconds"] == 0.0


# ===================================================================
# Thread safety (AC-005-N1)
# ===================================================================

class TestThreadSafety:
    """Verify concurrent mutations do not cause data races."""

    def test_concurrent_increment_applied_thread_safe(self, state: BotState) -> None:
        """AC-005-N1: 10 threads x 1000 increments must yield exactly 10000."""
        num_threads = 10
        increments_per_thread = 1000
        barrier = threading.Barrier(num_threads)

        def _worker() -> None:
            barrier.wait()  # ensure all threads start at the same time
            for _ in range(increments_per_thread):
                state.increment_applied()

        threads = [threading.Thread(target=_worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert state.applied_today == num_threads * increments_per_thread


# ===================================================================
# Review gate (FR-053)
# ===================================================================

class TestReviewGate:
    """FR-053: Review mode pause and decision signaling."""

    def test_initial_not_awaiting_review(self, state: BotState) -> None:
        """FR-053: Initially not awaiting review."""
        assert state.awaiting_review is False

    def test_begin_review_sets_awaiting(self, state: BotState) -> None:
        """FR-053: begin_review() sets awaiting_review to True."""
        state.begin_review()
        assert state.awaiting_review is True

    def test_set_review_decision_clears_awaiting(self, state: BotState) -> None:
        """FR-053: set_review_decision() clears awaiting_review."""
        state.begin_review()
        state.set_review_decision("approve")
        assert state.awaiting_review is False

    def test_approve_decision(self, state: BotState) -> None:
        """FR-053: approve decision is received correctly."""
        state.begin_review()
        state.set_review_decision("approve")
        decision, edits = state.wait_for_review()
        assert decision == "approve"
        assert edits is None

    def test_skip_decision(self, state: BotState) -> None:
        """FR-053: skip decision is received correctly."""
        state.begin_review()
        state.set_review_decision("skip")
        decision, edits = state.wait_for_review()
        assert decision == "skip"
        assert edits is None

    def test_edit_decision_with_cover_letter(self, state: BotState) -> None:
        """FR-053: edit decision passes cover letter edits."""
        state.begin_review()
        state.set_review_decision("edit", edits="New cover letter")
        decision, edits = state.wait_for_review()
        assert decision == "edit"
        assert edits == "New cover letter"

    def test_stop_unblocks_review(self, state: BotState) -> None:
        """FR-053: stop() unblocks a waiting review with 'stop' decision."""
        state.begin_review()
        state.stop()
        decision, edits = state.wait_for_review()
        assert decision == "stop"
        assert edits is None

    def test_review_gate_thread_safe(self, state: BotState) -> None:
        """FR-053: review gate works across threads."""
        results = []

        def reviewer():
            import time
            time.sleep(0.05)  # Small delay to ensure bot is waiting
            state.set_review_decision("approve")

        def bot():
            state.begin_review()
            decision, edits = state.wait_for_review()
            results.append((decision, edits))

        t_bot = threading.Thread(target=bot)
        t_reviewer = threading.Thread(target=reviewer)

        t_bot.start()
        t_reviewer.start()
        t_bot.join(timeout=5)
        t_reviewer.join(timeout=5)

        assert len(results) == 1
        assert results[0] == ("approve", None)

    def test_status_dict_includes_awaiting_review(self, state: BotState) -> None:
        """FR-053: get_status_dict includes awaiting_review field."""
        assert state.get_status_dict()["awaiting_review"] is False
        state.begin_review()
        assert state.get_status_dict()["awaiting_review"] is True
