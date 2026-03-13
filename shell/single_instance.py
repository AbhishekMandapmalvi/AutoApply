"""Single-instance lock — prevents multiple app windows.

Implements: FR-092 (TASK-031).

Uses a PID-based lock file at ~/.autoapply/.lock.
Detects and cleans stale locks from crashed processes.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_lock_path() -> Path:
    """Return the lock file path (~/.autoapply/.lock)."""
    from config.settings import get_data_dir

    return get_data_dir() / ".lock"


def _is_pid_running(pid: int) -> bool:
    """Check if a process with the given PID is still running."""
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def acquire_lock() -> bool:
    """Try to acquire the single-instance lock.

    Returns True if lock acquired (this is the first instance).
    Returns False if another instance is already running.
    Cleans up stale locks from crashed processes.
    """
    lock_path = _get_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if lock_path.exists():
        try:
            existing_pid = int(lock_path.read_text().strip())
        except (ValueError, OSError):
            logger.warning("Corrupt lock file — removing")
            lock_path.unlink(missing_ok=True)
        else:
            if _is_pid_running(existing_pid):
                logger.warning(
                    "Another instance is running (PID %d)", existing_pid,
                )
                return False
            else:
                logger.info(
                    "Stale lock from PID %d — cleaning up", existing_pid,
                )
                lock_path.unlink(missing_ok=True)

    try:
        lock_path.write_text(str(os.getpid()), encoding="utf-8")
        logger.info("Acquired single-instance lock (PID %d)", os.getpid())
        return True
    except OSError as e:
        logger.error("Failed to write lock file: %s", e)
        return False


def release_lock() -> None:
    """Release the single-instance lock file."""
    lock_path = _get_lock_path()
    try:
        if lock_path.exists():
            stored_pid = int(lock_path.read_text().strip())
            if stored_pid == os.getpid():
                lock_path.unlink(missing_ok=True)
                logger.info("Released single-instance lock")
    except (ValueError, OSError) as e:
        logger.debug("Lock release cleanup: %s", e)
        lock_path.unlink(missing_ok=True)
