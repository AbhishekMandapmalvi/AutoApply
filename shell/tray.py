"""System tray integration via pystray.

Implements: FR-091 (TASK-031).

Creates a system tray icon with Show/Quit context menu.
Runs in a background thread to avoid blocking PyWebView.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

logger = logging.getLogger(__name__)

_tray_instance = None
_tray_thread: threading.Thread | None = None


def _get_icon_image():
    """Load the app icon as a PIL Image."""
    from PIL import Image

    # Look for icon in static/icons/ relative to project root
    icon_paths = [
        Path(__file__).parent.parent / "static" / "icons" / "icon.png",
        Path(__file__).parent.parent / "static" / "icons" / "icon.ico",
    ]

    for icon_path in icon_paths:
        if icon_path.exists():
            try:
                return Image.open(str(icon_path))
            except Exception as e:
                logger.warning("Failed to load icon %s: %s", icon_path, e)

    # Fallback: generate a simple blue square icon
    logger.info("No icon file found — generating fallback icon")
    img = Image.new("RGBA", (64, 64), (96, 165, 250, 255))
    return img


def create_tray(on_show: Callable[[], None], on_quit: Callable[[], None]) -> None:
    """Create and start the system tray icon in a background thread.

    Args:
        on_show: Callback when user clicks "Show" or the tray icon.
        on_quit: Callback when user clicks "Quit".
    """
    global _tray_instance, _tray_thread

    try:
        import pystray
    except ImportError:
        logger.warning("pystray not available — skipping system tray")
        return

    icon_image = _get_icon_image()

    menu = pystray.Menu(
        pystray.MenuItem("Show", lambda _icon, _item: on_show(), default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", lambda _icon, _item: on_quit()),
    )

    _tray_instance = pystray.Icon(
        name="AutoApply",
        icon=icon_image,
        title="AutoApply",
        menu=menu,
    )

    def _run_tray():
        try:
            _tray_instance.run()
        except Exception as e:
            logger.error("System tray error: %s", e)

    _tray_thread = threading.Thread(target=_run_tray, daemon=True, name="tray")
    _tray_thread.start()
    logger.info("System tray started")


def destroy_tray() -> None:
    """Stop and clean up the system tray icon."""
    global _tray_instance, _tray_thread

    if _tray_instance is not None:
        try:
            _tray_instance.stop()
            logger.info("System tray stopped")
        except Exception as e:
            logger.debug("Tray cleanup: %s", e)
        _tray_instance = None
        _tray_thread = None
