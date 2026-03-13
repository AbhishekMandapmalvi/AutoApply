"""Desktop shell — PyWebView window + pystray system tray.

Implements: FR-090 through FR-097 (TASK-031 PyWebView migration).

Provides launch_gui() as the single entry point for desktop mode.
"""

from shell.main import launch_gui

__all__ = ["launch_gui"]
