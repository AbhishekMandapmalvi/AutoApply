"""PyWebView desktop shell — main window lifecycle.

Implements: FR-090, FR-093, FR-094, FR-095 (TASK-031).

Launches Flask in a daemon thread, polls for readiness, then opens
a PyWebView window pointing at the Flask backend URL.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Health-check constants
_HEALTH_POLL_INTERVAL = 0.5  # seconds between polls
_HEALTH_TIMEOUT = 30  # seconds before giving up

# Inline HTML shown while Flask is starting
_LOADING_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AutoApply</title>
<style>
  body {
    margin: 0; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    height: 100vh; background: #0f1923; color: #e2e8f0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  }
  .logo { font-size: 28px; font-weight: 700; color: #60a5fa; margin-bottom: 24px; }
  .spinner {
    width: 32px; height: 32px;
    border: 3px solid rgba(96,165,250,0.2);
    border-top-color: #60a5fa;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .status { margin-top: 16px; font-size: 13px; color: #94a3b8; }
  .error { color: #ef4444; display: none; margin-top: 12px; font-size: 13px; }
</style>
</head>
<body>
  <div class="logo">AutoApply</div>
  <div class="spinner"></div>
  <div class="status">Starting...</div>
  <div class="error" id="error"></div>
</body>
</html>
"""

# Error HTML shown when Flask fails to start
_ERROR_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>AutoApply — Error</title>
<style>
  body {{
    margin: 0; display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    height: 100vh; background: #0f1923; color: #e2e8f0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  }}
  .logo {{ font-size: 28px; font-weight: 700; color: #60a5fa; margin-bottom: 24px; }}
  .error {{ color: #ef4444; font-size: 14px; max-width: 400px; text-align: center; }}
</style>
</head>
<body>
  <div class="logo">AutoApply</div>
  <div class="error">{message}</div>
</body>
</html>
"""


def _wait_for_health(host: str, port: int) -> bool:
    """Poll Flask /api/health until it responds 200 or timeout.

    Returns True if Flask is ready, False on timeout.
    """
    url = f"http://{host}:{port}/api/health"
    deadline = time.monotonic() + _HEALTH_TIMEOUT

    while time.monotonic() < deadline:
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                logger.info("Flask backend ready at %s:%d", host, port)
                return True
        except requests.ConnectionError:
            pass
        except Exception as e:
            logger.debug("Health check error: %s", e)
        time.sleep(_HEALTH_POLL_INTERVAL)

    logger.error("Flask backend did not become ready within %ds", _HEALTH_TIMEOUT)
    return False


def _start_flask_thread(host: str, port: int) -> threading.Thread:
    """Start Flask + SocketIO in a daemon thread.

    Returns the thread (already started).
    """

    def _run_flask():
        try:
            from app import app, socketio

            logger.info("Starting Flask on %s:%d", host, port)
            socketio.run(app, host=host, port=port, debug=False)
        except Exception as e:
            logger.error("Flask thread crashed: %s", e)

    thread = threading.Thread(target=_run_flask, daemon=True, name="flask")
    thread.start()
    return thread


def _shutdown(host: str, port: int) -> None:
    """Trigger graceful Flask shutdown."""
    from shell.single_instance import release_lock
    from shell.tray import destroy_tray

    destroy_tray()

    try:
        from app import graceful_shutdown

        graceful_shutdown()
    except Exception as e:
        logger.debug("Graceful shutdown error: %s", e)

    release_lock()
    logger.info("Shell shutdown complete")


def launch_gui(host: str = "127.0.0.1", port: int = 5000) -> None:
    """Launch the PyWebView desktop shell.

    This is the main entry point for GUI mode. It:
    1. Acquires single-instance lock
    2. Starts Flask in a daemon thread
    3. Creates a PyWebView window with loading HTML
    4. Polls for Flask readiness
    5. Navigates to Flask URL when ready
    6. Handles graceful shutdown on window close

    Args:
        host: Flask bind host (default 127.0.0.1).
        port: Flask bind port (default 5000).
    """
    import webview

    from shell.single_instance import acquire_lock
    from shell.tray import create_tray

    # 1. Single-instance lock
    if not acquire_lock():
        logger.error("Another instance is already running — exiting")
        sys.exit(1)

    # 2. Start Flask backend
    flask_url = f"http://{host}:{port}"
    _start_flask_thread(host, port)

    # 3. Create window with loading HTML
    window = webview.create_window(
        title="AutoApply",
        html=_LOADING_HTML,
        width=1280,
        height=800,
        min_size=(800, 600),
    )

    # Track whether we should minimize to tray on close
    _app_state: dict[str, Any] = {"quitting": False}

    def _on_closing():
        """Handle window close — minimize to tray unless quitting."""
        if _app_state["quitting"]:
            return True  # allow close
        window.hide()
        return False  # prevent close, hide instead

    window.events.closing += _on_closing

    def _on_show():
        """Restore window from tray."""
        window.show()
        window.restore()

    def _on_quit():
        """Quit from tray menu."""
        _app_state["quitting"] = True
        _shutdown(host, port)
        window.destroy()

    def _on_loaded():
        """After webview starts, poll Flask and navigate."""
        if _wait_for_health(host, port):
            window.load_url(flask_url)
        else:
            error_html = _ERROR_HTML_TEMPLATE.format(
                message="Failed to start backend. Check logs at ~/.autoapply/backend.log",
            )
            window.load_html(error_html)

    # 4. System tray
    create_tray(on_show=_on_show, on_quit=_on_quit)

    # 5. Start health check in background thread
    health_thread = threading.Thread(
        target=_on_loaded, daemon=True, name="health-check",
    )
    health_thread.start()

    # 6. Run PyWebView event loop (blocks until window is destroyed)
    try:
        webview.start()
    finally:
        if not _app_state["quitting"]:
            _shutdown(host, port)
