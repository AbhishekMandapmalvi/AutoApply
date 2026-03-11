"""Electron module tests for traceability coverage (TASK-025, #12).

Validates that the Electron source files contain the required code patterns
for 7 requirements currently at warning status: FR-019, FR-020, FR-021,
FR-022, FR-023, FR-024, FR-030.

Uses static code analysis — reads JS/HTML files and asserts expected patterns.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def main_js():
    """Read electron/main.js source."""
    return Path("electron/main.js").read_text(encoding="utf-8")


@pytest.fixture()
def backend_js():
    """Read electron/python-backend.js source."""
    return Path("electron/python-backend.js").read_text(encoding="utf-8")


@pytest.fixture()
def tray_js():
    """Read electron/tray.js source."""
    return Path("electron/tray.js").read_text(encoding="utf-8")


@pytest.fixture()
def splash_html():
    """Read electron/splash.html source."""
    return Path("electron/splash.html").read_text(encoding="utf-8")


# ===================================================================
# FR-019 — Electron App Launch
# ===================================================================


class TestFR019AppLaunch:
    """FR-019: Electron app launches as a native desktop application."""

    def test_main_js_exists(self):
        """electron/main.js exists as entry point."""
        assert Path("electron/main.js").exists()

    def test_creates_browser_window(self, main_js):
        """Main process creates a BrowserWindow."""
        assert "BrowserWindow" in main_js
        assert "createMainWindow" in main_js

    def test_window_dimensions(self, main_js):
        """Main window has defined width and height."""
        assert "width: 1280" in main_js
        assert "height: 850" in main_js

    def test_min_window_dimensions(self, main_js):
        """Main window has minimum dimensions."""
        assert "minWidth: 800" in main_js
        assert "minHeight: 600" in main_js

    def test_single_instance_lock(self, main_js):
        """App enforces single instance lock."""
        assert "requestSingleInstanceLock" in main_js

    def test_second_instance_handler(self, main_js):
        """App handles second-instance event (restores window)."""
        assert "second-instance" in main_js
        assert "mainWindow.show()" in main_js or "mainWindow.restore()" in main_js

    def test_loads_flask_url(self, main_js):
        """Main window loads Flask backend URL."""
        assert "http://127.0.0.1" in main_js
        assert "loadURL" in main_js

    def test_context_isolation(self, main_js):
        """Main window has context isolation enabled."""
        assert "contextIsolation: true" in main_js

    def test_node_integration_disabled(self, main_js):
        """Main window has node integration disabled."""
        assert "nodeIntegration: false" in main_js

    def test_preload_script(self, main_js):
        """Main window uses a preload script."""
        assert "preload" in main_js
        assert "preload.js" in main_js


# ===================================================================
# FR-020 — Python Backend Lifecycle
# ===================================================================


class TestFR020BackendLifecycle:
    """FR-020: Electron spawns and manages Python backend."""

    def test_backend_js_exists(self):
        """electron/python-backend.js exists."""
        assert Path("electron/python-backend.js").exists()

    def test_find_python_function(self, backend_js):
        """Backend module has findPython function."""
        assert "function findPython()" in backend_js

    def test_find_python_checks_venv(self, backend_js):
        """findPython checks local venv first."""
        assert "venv" in backend_js
        assert "Scripts" in backend_js or "bin" in backend_js

    def test_find_python_checks_bundled(self, backend_js):
        """findPython checks bundled Python runtime in packaged mode."""
        assert "python-runtime" in backend_js
        assert "isPackaged" in backend_js

    def test_find_python_system_fallback(self, backend_js):
        """findPython falls back to system Python."""
        assert "python3" in backend_js
        assert "execSync" in backend_js

    def test_spawn_backend(self, backend_js):
        """Backend uses spawn to start Python process."""
        assert "spawn(" in backend_js
        assert "scriptPath" in backend_js

    def test_start_backend_exports(self, backend_js):
        """Module exports startBackend and stopBackend."""
        assert "startBackend" in backend_js
        assert "stopBackend" in backend_js
        assert "module.exports" in backend_js

    def test_windows_hide(self, backend_js):
        """Spawn uses windowsHide to prevent console flash."""
        assert "windowsHide: true" in backend_js

    def test_sets_port_env(self, backend_js):
        """Backend sets AUTOAPPLY_PORT environment variable."""
        assert "AUTOAPPLY_PORT" in backend_js

    def test_error_handling(self, backend_js):
        """Backend handles spawn errors."""
        assert "backendProcess.on('error'" in backend_js

    def test_exit_detection(self, backend_js):
        """Backend detects process exit."""
        assert "backendProcess.on('exit'" in backend_js


# ===================================================================
# FR-021 — Health Check (Electron)
# ===================================================================


class TestFR021HealthCheck:
    """FR-021: Electron polls health endpoint before showing main window."""

    def test_wait_for_health_function(self, backend_js):
        """Backend module has waitForHealth function."""
        assert "function waitForHealth(" in backend_js

    def test_health_endpoint_polled(self, backend_js):
        """Health check polls /api/health."""
        assert "/api/health" in backend_js

    def test_health_check_timeout(self, backend_js):
        """Health check has a timeout (30s default)."""
        assert "30000" in backend_js
        assert "timeoutMs" in backend_js

    def test_health_check_interval(self, backend_js):
        """Health check polls at regular intervals (500ms default)."""
        assert "500" in backend_js
        assert "intervalMs" in backend_js

    def test_health_check_status_200(self, backend_js):
        """Health check expects HTTP 200 response."""
        assert "statusCode === 200" in backend_js

    def test_health_called_in_start(self, backend_js):
        """waitForHealth is called during startBackend."""
        assert "await waitForHealth(" in backend_js


# ===================================================================
# FR-022 — Splash Screen
# ===================================================================


class TestFR022SplashScreen:
    """FR-022: Splash screen shown during backend startup."""

    def test_splash_html_exists(self):
        """electron/splash.html exists."""
        assert Path("electron/splash.html").exists()

    def test_splash_has_logo(self, splash_html):
        """Splash screen shows AutoApply logo."""
        assert "AutoApply" in splash_html

    def test_splash_has_spinner(self, splash_html):
        """Splash screen has a loading spinner."""
        assert "spinner" in splash_html
        assert "animation" in splash_html

    def test_splash_has_status(self, splash_html):
        """Splash screen has status text."""
        assert "Starting..." in splash_html

    def test_splash_has_error_area(self, splash_html):
        """Splash screen has error display area."""
        assert 'id="error"' in splash_html

    def test_splash_frameless(self, main_js):
        """Splash window is frameless."""
        assert "frame: false" in main_js

    def test_splash_always_on_top(self, main_js):
        """Splash window is always on top."""
        assert "alwaysOnTop: true" in main_js

    def test_splash_created_first(self, main_js):
        """Splash is created before backend starts."""
        # createSplashWindow appears before startBackend in app.on('ready')
        assert "createSplashWindow()" in main_js
        splash_pos = main_js.index("createSplashWindow()")
        backend_pos = main_js.index("startBackend()")
        assert splash_pos < backend_pos

    def test_splash_closed_on_ready(self, main_js):
        """Splash is closed when main window is ready."""
        assert "splashWindow.close()" in main_js
        assert "ready-to-show" in main_js


# ===================================================================
# FR-023 — Graceful Shutdown
# ===================================================================


class TestFR023GracefulShutdown:
    """FR-023: Clean shutdown of Electron and Python backend."""

    def test_stop_backend_function(self, backend_js):
        """Backend module has stopBackend function."""
        assert "async function stopBackend()" in backend_js

    def test_graceful_api_call(self, backend_js):
        """Shutdown calls /api/shutdown endpoint."""
        assert "/api/shutdown" in backend_js
        assert "method: 'POST'" in backend_js

    def test_graceful_timeout(self, backend_js):
        """Shutdown has a 3-second timeout for graceful stop."""
        assert "timeout: 3000" in backend_js

    def test_wait_for_exit(self, backend_js):
        """Shutdown waits up to 5 seconds for process exit."""
        assert "5000" in backend_js

    def test_force_kill_windows(self, backend_js):
        """Shutdown uses taskkill on Windows as fallback."""
        assert "taskkill" in backend_js
        assert "/PID" in backend_js
        assert "/T /F" in backend_js

    def test_force_kill_unix(self, backend_js):
        """Shutdown uses SIGKILL on Unix as fallback."""
        assert "SIGKILL" in backend_js

    def test_before_quit_handler(self, main_js):
        """Main process handles before-quit event."""
        assert "before-quit" in main_js
        assert "stopBackend()" in main_js

    def test_shutdown_destroys_tray(self, main_js):
        """Shutdown destroys tray icon."""
        assert "destroyTray()" in main_js

    def test_log_stream_cleanup(self, backend_js):
        """Shutdown closes log stream."""
        assert "logStream.end()" in backend_js


# ===================================================================
# FR-024 — System Tray
# ===================================================================


class TestFR024SystemTray:
    """FR-024: System tray icon with context menu."""

    def test_tray_js_exists(self):
        """electron/tray.js exists."""
        assert Path("electron/tray.js").exists()

    def test_create_tray_function(self, tray_js):
        """Tray module has createTray function."""
        assert "function createTray(" in tray_js

    def test_tray_tooltip(self, tray_js):
        """Tray icon has AutoApply tooltip."""
        assert "setToolTip" in tray_js
        assert "AutoApply" in tray_js

    def test_tray_context_menu(self, tray_js):
        """Tray has context menu with Show and Quit."""
        assert "Show" in tray_js
        assert "Quit" in tray_js
        assert "buildFromTemplate" in tray_js

    def test_tray_click_shows_window(self, tray_js):
        """Clicking tray icon shows and focuses window."""
        assert "tray.on('click'" in tray_js
        assert "mainWindow.show()" in tray_js
        assert "mainWindow.focus()" in tray_js

    def test_minimize_to_tray(self, main_js):
        """Window close event hides to tray instead of quitting."""
        assert "event.preventDefault()" in main_js
        assert "mainWindow.hide()" in main_js

    def test_destroy_tray_function(self, tray_js):
        """Tray module has destroyTray function."""
        assert "function destroyTray()" in tray_js
        assert "tray.destroy()" in tray_js

    def test_tray_icon_platform_aware(self, tray_js):
        """Tray uses platform-specific icon format."""
        assert "icon.ico" in tray_js
        assert "icon.png" in tray_js
        assert "process.platform" in tray_js


# ===================================================================
# FR-030 — Backend Log Capture
# ===================================================================


class TestFR030LogCapture:
    """FR-030: Python backend stdout/stderr captured to log file."""

    def test_setup_log_file_function(self, backend_js):
        """Backend module has setupLogFile function."""
        assert "function setupLogFile()" in backend_js

    def test_log_path(self, backend_js):
        """Log file goes to .autoapply/backend.log."""
        assert "backend.log" in backend_js

    def test_log_rotation(self, backend_js):
        """Log file is rotated when exceeding 10MB."""
        assert "10 * 1024 * 1024" in backend_js
        assert "backend.log.1" in backend_js

    def test_stdout_piped(self, backend_js):
        """Backend stdout is piped to log stream."""
        assert "backendProcess.stdout.pipe(logStream)" in backend_js

    def test_stderr_piped(self, backend_js):
        """Backend stderr is piped to log stream."""
        assert "backendProcess.stderr.pipe(logStream)" in backend_js

    def test_log_stream_append(self, backend_js):
        """Log stream opens in append mode."""
        assert "flags: 'a'" in backend_js

    def test_log_dir_created(self, backend_js):
        """Log setup creates data directory if needed."""
        assert "mkdirSync" in backend_js
        assert "recursive: true" in backend_js
