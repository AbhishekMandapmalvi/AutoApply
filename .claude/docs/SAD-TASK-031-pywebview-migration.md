# System Architecture Document

**Document ID**: SAD-TASK-031-pywebview-migration
**Version**: 1.0
**Date**: 2026-03-13
**Status**: approved
**Author**: Claude (System Engineer)
**Supersedes**: SAD-TASK-002-electron-shell (shell layer)

---

## 1. Overview

Replace Electron (Node.js + Chromium) with PyWebView (Python + OS webview) as the
desktop shell for AutoApply. This eliminates the Node.js runtime, reduces installer
size by ~60%, and unifies the entire application under a single Python ecosystem.

### 1.1 Architecture Comparison

```
BEFORE (Electron):                    AFTER (PyWebView):
┌─────────────────────┐              ┌─────────────────────┐
│ Electron (Node.js)  │              │ PyWebView (Python)   │
│ ┌─────────────────┐ │              │ ┌─────────────────┐ │
│ │ Chromium (150MB) │ │              │ │ OS WebView (0MB) │ │
│ └─────────────────┘ │              │ └─────────────────┘ │
│ IPC: HTTP to Flask   │              │ Same process/thread  │
├─────────────────────┤              ├─────────────────────┤
│ Flask + SocketIO    │              │ Flask + SocketIO    │
│ (Python subprocess) │              │ (daemon thread)     │
└─────────────────────┘              └─────────────────────┘
~200MB overhead                      ~5MB overhead
```

---

## 2. ADR-034: Replace Electron with PyWebView

**Status**: Accepted
**Supersedes**: ADR-005 (Electron over PyWebView)
**Date**: 2026-03-13

### Context
Electron was chosen (ADR-005) for its mature ecosystem. After 9 months of development,
we found that:
1. The Electron shell uses <5% of Electron's capabilities (just a webview + process launcher)
2. Frontend code has zero `electronAPI` calls — already platform-agnostic
3. Two runtimes (Node.js + Python) complicate packaging and increase installer size
4. The app is accessible via localhost browser, making Electron feel disconnected

### Decision
Replace Electron with PyWebView + pystray.

### Consequences
- **Positive**: ~60% smaller installer, single runtime, simpler build pipeline
- **Positive**: No Node.js/npm dependency in project
- **Positive**: Shell code is Python — same language as backend
- **Negative**: Lose electron-builder's mature packaging (mitigated by PyInstaller)
- **Negative**: No built-in auto-updater (was never implemented anyway)
- **Negative**: WebView rendering varies slightly across OS (mitigated: standard HTML/CSS)

### Retained Decisions
- **ADR-006** (revised): Playwright still uses its own Chromium — unchanged
- **ADR-007**: Python process management concept retained (now same-process threading)
- **ADR-008**: Port auto-detection (5000-5010) — unchanged

---

## 3. Component Design

### 3.1 Module Structure

```
shell/
├── __init__.py          # Package exports: launch_gui()
├── main.py              # PyWebView window lifecycle, Flask thread, health check
├── tray.py              # pystray system tray (icon, context menu, minimize-to-tray)
└── single_instance.py   # File-lock based single-instance guard
```

### 3.2 shell/main.py — Window Lifecycle

```python
# Key interface
def launch_gui(host: str, port: int) -> None:
    """Main entry point. Blocks until window is closed."""
    # 1. Acquire single-instance lock
    # 2. Start Flask in daemon thread
    # 3. Poll /api/health until ready
    # 4. Create PyWebView window
    # 5. Start system tray (separate thread)
    # 6. webview.start() — blocks
    # 7. On exit: graceful shutdown
```

**Threading Model**:
```
Main Thread:     PyWebView event loop (webview.start())
Thread 1:        Flask + SocketIO (gevent WSGI server)
Thread 2:        pystray system tray event loop
Thread 3+:       Bot, scheduler, etc. (managed by Flask)
```

**Health Check Loop**:
- Poll `GET http://127.0.0.1:{port}/api/health` every 500ms
- Timeout after 30 seconds
- On success: `window.load_url(f"http://127.0.0.1:{port}")`
- On timeout: show error in window

**Loading State**:
- PyWebView window created immediately with inline HTML (spinner + "Starting...")
- Once Flask is ready, window navigates to Flask URL
- No separate splash window needed — PyWebView supports `load_html()` then `load_url()`

### 3.3 shell/tray.py — System Tray

```python
# Key interface
def create_tray(on_show: Callable, on_quit: Callable) -> None:
    """Create system tray icon with Show/Quit menu. Runs in background thread."""

def destroy_tray() -> None:
    """Clean up tray icon."""
```

**Icon Strategy**:
- Use existing `electron/icons/icon.png` (copy to `static/icons/`)
- pystray requires PIL Image — use Pillow to load PNG
- Fallback: generate simple colored square if icon missing

**Menu Items**:
- "Show" → calls `on_show` callback (window.restore + window.on_top)
- "Quit" → calls `on_quit` callback (triggers graceful shutdown)

### 3.4 shell/single_instance.py — Instance Lock

```python
# Key interface
def acquire_lock() -> bool:
    """Try to acquire single-instance lock. Returns True if acquired."""

def release_lock() -> None:
    """Release the lock file."""
```

**Implementation**:
- Lock file: `~/.autoapply/.lock`
- Contains PID of owning process
- On startup: check if lock file exists AND PID is still running
- If stale (PID not running): clean up and acquire
- If active: exit with message

### 3.5 run.py Changes

```python
# New CLI flag
parser.add_argument("--gui", action="store_true", help="Launch with PyWebView GUI")
parser.add_argument("--no-browser", action="store_true", help="Headless mode")

# If --gui:
#   from shell.main import launch_gui
#   launch_gui(host, port)
# Else:
#   socketio.run(app, host=host, port=port)  # existing behavior
```

---

## 4. Packaging Design

### 4.1 PyInstaller Spec

```
autoapply.spec:
  - Entry point: run.py --gui
  - Hidden imports: gevent, engineio, socketio, webview, pystray
  - Data files: templates/, static/, static/locales/
  - Icon: static/icons/icon.ico
  - Console: False (windowed mode)
  - One-dir mode (not one-file — faster startup)
```

### 4.2 Release Workflow Update

```yaml
# .github/workflows/release.yml
# Replace electron-builder steps with:
- pip install pyinstaller
- pyinstaller autoapply.spec
- Package dist/autoapply/ into zip/installer
```

---

## 5. Migration Checklist

- [ ] Create `shell/` package (main.py, tray.py, single_instance.py)
- [ ] Copy icon from electron/icons/ to static/icons/
- [ ] Update run.py with --gui flag
- [ ] Add pywebview, pystray, Pillow to pyproject.toml
- [ ] Create autoapply.spec for PyInstaller
- [ ] Update .github/workflows/release.yml
- [ ] Remove electron/ directory
- [ ] Update/replace electron test files
- [ ] Write shell unit tests (>=90% coverage)
- [ ] Update traceability matrix

---

## 6. Design Traceability

| Requirement | Design Section | Implementation |
|-------------|---------------|----------------|
| FR-090 (App Launch) | §3.2 main.py | shell/main.py:launch_gui() |
| FR-091 (System Tray) | §3.3 tray.py | shell/tray.py:create_tray() |
| FR-092 (Single Instance) | §3.4 single_instance.py | shell/single_instance.py:acquire_lock() |
| FR-093 (Splash/Loading) | §3.2 Loading State | shell/main.py:_LOADING_HTML |
| FR-094 (Graceful Shutdown) | §3.2 Window Lifecycle | shell/main.py:_shutdown() |
| FR-095 (Port Detection) | §3.5 run.py Changes | run.py:_find_free_port() (existing) |
| FR-096 (PyInstaller) | §4.1 Spec | autoapply.spec |
| FR-097 (Electron Removal) | §5 Migration Checklist | git rm -r electron/ |
