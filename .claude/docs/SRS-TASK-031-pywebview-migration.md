# Software Requirements Specification

**Document ID**: SRS-TASK-031-pywebview-migration
**Version**: 1.0
**Date**: 2026-03-13
**Status**: approved
**Author**: Claude (Requirements Analyst)
**Supersedes**: SRS-TASK-002-electron-shell (partial — shell layer only)

---

## 1. Purpose and Scope

### 1.1 Purpose
Specifies requirements for replacing the Electron desktop shell with PyWebView,
providing the same native application experience using the OS's built-in webview
engine and a pure-Python desktop integration layer.

### 1.2 Scope
- Python shell module using PyWebView for the application window
- System tray integration via pystray
- Single-instance lock via file-based locking
- Graceful startup with loading state
- Graceful shutdown with process cleanup
- PyInstaller-based packaging to replace electron-builder
- Removal of entire `electron/` directory and Node.js dependency

**Out of Scope**: Auto-update mechanism (future task), code signing (TASK-021),
backend changes (Flask + SocketIO unchanged), frontend changes (already platform-agnostic).

### 1.3 Definitions

| Term | Definition |
|------|-----------|
| PyWebView | Python library that creates a native OS window with a webview component |
| Edge WebView2 | Microsoft's Chromium-based webview runtime, built into Windows 10/11 |
| pystray | Python library for creating system tray icons with context menus |
| PyInstaller | Python tool that bundles a Python app into a standalone executable |
| Shell module | The `shell/` Python package that manages the desktop window lifecycle |

---

## 2. Assumptions

| # | Assumption | Risk if Wrong | Mitigation |
|---|-----------|---------------|------------|
| A1 | Edge WebView2 is available on Windows 10/11 | Window fails to create | PyWebView falls back to MSHTML; document WebView2 as requirement |
| A2 | PyWebView supports gevent async_mode | WebSocket connections fail | PyWebView runs in main thread, Flask in daemon thread — no conflict |
| A3 | pystray works on Windows/macOS/Linux | No system tray icon | Tray is optional; app still works without it |
| A4 | PyInstaller can bundle all deps including Playwright browsers | Packaging fails | Use --collect-all and explicit data includes |

---

## 3. Functional Requirements

### FR-090: PyWebView App Launch
**Priority**: P0 — Critical
**Traces to**: AC-1

The shell module SHALL launch a PyWebView window pointing at the Flask backend URL.

| AC | Given | When | Then |
|----|-------|------|------|
| AC-090.1 | App is installed | User double-clicks app icon | PyWebView window opens with Flask UI, no terminal visible |
| AC-090.2 | Flask is starting | Window is created | Loading page shown until Flask health check passes |
| AC-090.3 | Flask is ready | Health check returns 200 | Window navigates to Flask URL |

### FR-091: System Tray Integration
**Priority**: P1 — High
**Traces to**: AC-2, AC-3

The shell module SHALL create a system tray icon with context menu.

| AC | Given | When | Then |
|----|-------|------|------|
| AC-091.1 | App is running | Tray icon visible | Context menu has "Show" and "Quit" items |
| AC-091.2 | App window is open | User closes window (X button) | Window hides, tray icon remains, app continues running |
| AC-091.3 | Window is hidden | User clicks "Show" or tray icon | Window restores and focuses |
| AC-091.4 | App is running | User clicks "Quit" from tray | Graceful shutdown initiated |

### FR-092: Single-Instance Lock
**Priority**: P1 — High
**Traces to**: AC-4

The shell module SHALL prevent multiple instances of the application.

| AC | Given | When | Then |
|----|-------|------|------|
| AC-092.1 | App is running | User launches second instance | Second instance exits, first instance window focuses |
| AC-092.2 | App crashed (lock file exists) | User launches app | Stale lock detected and cleaned, app starts normally |

### FR-093: Splash / Loading State
**Priority**: P2 — Medium
**Traces to**: AC-5

The shell module SHALL show a loading state during backend startup.

| AC | Given | When | Then |
|----|-------|------|------|
| AC-093.1 | App is launching | Flask not yet ready | Window shows loading HTML with spinner |
| AC-093.2 | Flask becomes ready | Health check passes | Window loads Flask URL |
| AC-093.3 | Flask fails to start | Health check times out (30s) | Error message displayed |

### FR-094: Graceful Shutdown
**Priority**: P0 — Critical
**Traces to**: AC-6

The shell module SHALL cleanly shut down the Flask backend on exit.

| AC | Given | When | Then |
|----|-------|------|------|
| AC-094.1 | App is running | User quits via tray or window | Flask graceful_shutdown() called |
| AC-094.2 | Graceful shutdown called | Backend has active connections | Connections drained within 5s timeout |
| AC-094.3 | Shutdown timeout exceeded | Backend still running after 5s | Process force-terminated |

### FR-095: Port Auto-Detection
**Priority**: P1 — High
**Traces to**: AC-7

The shell module SHALL reuse existing port auto-detection logic (5000-5010).

| AC | Given | When | Then |
|----|-------|------|------|
| AC-095.1 | Port 5000 is occupied | App starts | Next available port (5001-5010) used |
| AC-095.2 | AUTOAPPLY_PORT env var set | App starts | Specified port used |

### FR-096: PyInstaller Packaging
**Priority**: P0 — Critical
**Traces to**: AC-8, AC-9

The application SHALL be packageable via PyInstaller into a distributable installer.

| AC | Given | When | Then |
|----|-------|------|------|
| AC-096.1 | PyInstaller spec exists | `pyinstaller autoapply.spec` run | Single-directory output created |
| AC-096.2 | Package built | Installer measured | Size < 100MB (excluding Playwright browsers) |
| AC-096.3 | Package installed | User runs app | All features work identically to dev mode |

### FR-097: Electron Removal
**Priority**: P0 — Critical
**Traces to**: AC-12

The `electron/` directory and all Node.js dependencies SHALL be completely removed.

| AC | Given | When | Then |
|----|-------|------|------|
| AC-097.1 | Migration complete | Check filesystem | `electron/` directory does not exist |
| AC-097.2 | Migration complete | Check dependencies | No Node.js, npm, or Electron references in project |

---

## 4. Non-Functional Requirements

### NFR-031.1: Startup Performance
The shell SHALL display a visible window within 2 seconds of launch.
Flask backend readiness within 10 seconds under normal conditions.

### NFR-031.2: Memory Footprint
The shell process (excluding Flask) SHALL use < 50MB RAM.

### NFR-031.3: Cross-Platform
The shell SHALL work on Windows 10+, macOS 12+, and Ubuntu 22.04+.

### NFR-031.4: Logging
All shell operations SHALL use Python `logging` module with `shell.*` logger names.

---

## 5. Traceability Seeds

| FR | Source Files | Test Files |
|----|-------------|------------|
| FR-090 | shell/main.py | tests/test_shell.py |
| FR-091 | shell/tray.py | tests/test_shell.py |
| FR-092 | shell/single_instance.py | tests/test_shell.py |
| FR-093 | shell/main.py | tests/test_shell.py |
| FR-094 | shell/main.py | tests/test_shell.py |
| FR-095 | run.py | tests/test_shell.py |
| FR-096 | autoapply.spec | tests/test_pyinstaller_packaging.py |
| FR-097 | (deletion) | tests/test_pyinstaller_packaging.py |
