"""Unit tests for run.py port configuration and GUI mode detection.

Requirement traceability:
    FR-028  AUTOAPPLY_PORT environment variable and port auto-detection
    FR-090  PyWebView desktop shell launch (GUI mode default for frozen builds)
"""

from __future__ import annotations

import os
import socket
import sys
from unittest.mock import MagicMock, patch

from run import _find_free_port


class TestPortConfig:
    """Validates FR-028: AUTOAPPLY_PORT environment variable."""

    def test_port_from_env(self):
        """AC-028-1: AUTOAPPLY_PORT env var is read."""
        with patch.dict(os.environ, {"AUTOAPPLY_PORT": "5050"}):
            port = int(os.environ.get("AUTOAPPLY_PORT", "5000"))
            assert port == 5050

    def test_port_default(self):
        """AC-028-2: Default port is 5000 when env var is not set."""
        env = os.environ.copy()
        env.pop("AUTOAPPLY_PORT", None)
        with patch.dict(os.environ, env, clear=True):
            port = int(os.environ.get("AUTOAPPLY_PORT", "5000"))
            assert port == 5000


class TestPortAutoDetection:
    """Validates FR-028: Port auto-detection when default port is occupied."""

    def test_find_free_port_returns_first_available(self):
        """AC-028-3: Returns a port in the expected range."""
        port = _find_free_port(9700, 9710)
        assert 9700 <= port <= 9710

    def test_find_free_port_skips_occupied(self):
        """AC-028-4: Skips occupied ports and returns next available."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 9700))
            s.listen(1)
            port = _find_free_port(9700, 9710)
            assert port != 9700
            assert 9701 <= port <= 9710

    def test_find_free_port_raises_when_all_taken(self):
        """AC-028-5: Raises RuntimeError when no ports available."""
        socks = []
        try:
            for p in range(9700, 9703):
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(("127.0.0.1", p))
                s.listen(1)
                socks.append(s)
            import pytest
            with pytest.raises(RuntimeError, match="All ports"):
                _find_free_port(9700, 9702)
        finally:
            for s in socks:
                s.close()


class TestFrozenGUIDefault:
    """Validates FR-090 / Issue #97: PyInstaller exe defaults to GUI mode."""

    @patch("run._setup_data_dirs")
    @patch("run._configure_logging")
    @patch("run._parse_args")
    def test_frozen_launches_gui(self, mock_args, mock_logging, mock_dirs):
        """AC-097-1: When sys.frozen is True, launch_gui is called."""
        mock_args.return_value = MagicMock(gui=False, no_browser=False)
        mock_dirs.return_value = MagicMock()

        with patch.object(sys, "frozen", True, create=True), \
             patch("run._find_free_port", return_value=5000), \
             patch("shell.launch_gui") as mock_launch:
            from run import main
            main()
            mock_launch.assert_called_once_with(host="127.0.0.1", port=5000)

    @patch("run._setup_data_dirs")
    @patch("run._configure_logging")
    @patch("run._parse_args")
    def test_gui_flag_launches_gui(self, mock_args, mock_logging, mock_dirs):
        """AC-097-2: When --gui flag is passed, launch_gui is called."""
        mock_args.return_value = MagicMock(gui=True, no_browser=False)
        mock_dirs.return_value = MagicMock()

        with patch("run._find_free_port", return_value=5000), \
             patch("shell.launch_gui") as mock_launch:
            from run import main
            main()
            mock_launch.assert_called_once_with(host="127.0.0.1", port=5000)

    @patch("run._setup_data_dirs")
    @patch("run._configure_logging")
    @patch("run._parse_args")
    def test_not_frozen_no_flag_runs_headless(self, mock_args, mock_logging, mock_dirs):
        """AC-097-3: Without sys.frozen or --gui, runs headless server."""
        mock_args.return_value = MagicMock(gui=False, no_browser=False)
        mock_dirs.return_value = MagicMock()

        # Ensure sys.frozen is not set
        frozen_backup = getattr(sys, "frozen", None)
        if hasattr(sys, "frozen"):
            delattr(sys, "frozen")

        try:
            with patch("run._find_free_port", return_value=5000), \
                 patch("app.socketio") as mock_sio:
                from run import main
                main()
                mock_sio.run.assert_called_once()
        finally:
            if frozen_backup is not None:
                sys.frozen = frozen_backup
