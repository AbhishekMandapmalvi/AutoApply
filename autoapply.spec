# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for AutoApply desktop application.

Implements: FR-096 (TASK-031).

Build:
    pyinstaller autoapply.spec

Output:
    dist/AutoApply/  (one-dir mode for faster startup)
"""

import sys
from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH)

a = Analysis(
    [str(project_root / "run.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "templates"), "templates"),
        (str(project_root / "static"), "static"),
    ],
    hiddenimports=[
        # Gevent + SocketIO
        "gevent",
        "gevent.monkey",
        "gevent._ssl3",
        "geventwebsocket",
        "engineio.async_drivers.gevent",
        # Flask + extensions
        "flask",
        "flask_socketio",
        # PyWebView
        "webview",
        # System tray
        "pystray",
        "PIL",
        # App modules
        "app",
        "app_state",
        "bot",
        "bot.bot",
        "bot.state",
        "bot.apply",
        "config",
        "config.settings",
        "core",
        "db",
        "db.database",
        "routes",
        "shell",
        "shell.main",
        "shell.tray",
        "shell.single_instance",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "test",
        "tests",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutoApply",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed mode — no terminal
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "static" / "icons" / "icon.ico")
    if sys.platform == "win32"
    else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AutoApply",
)
