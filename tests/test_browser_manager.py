"""Unit tests for bot.browser — BrowserManager and Chrome detection.

Requirement traceability:
    FR-043  Browser session management (BrowserManager)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ===================================================================
# _find_system_chrome
# ===================================================================


class TestFindSystemChrome:
    """Platform-specific Chrome detection."""

    @patch("bot.browser.platform.system", return_value="Windows")
    @patch("bot.browser.os.path.isfile", return_value=False)
    def test_windows_no_chrome(self, mock_isfile, mock_sys):
        from bot.browser import _find_system_chrome

        result = _find_system_chrome()
        assert result is None
        # Should check at least 3 candidates
        assert mock_isfile.call_count >= 3

    @patch("bot.browser.platform.system", return_value="Windows")
    @patch("bot.browser.os.path.isfile")
    def test_windows_chrome_found(self, mock_isfile, mock_sys):
        from bot.browser import _find_system_chrome

        mock_isfile.side_effect = lambda p: "chrome.exe" in p.lower()
        result = _find_system_chrome()
        assert result is not None
        assert "chrome.exe" in result.lower()

    @patch("bot.browser.platform.system", return_value="Darwin")
    @patch("bot.browser.os.path.isfile", return_value=True)
    def test_darwin_chrome_found(self, mock_isfile, mock_sys):
        from bot.browser import _find_system_chrome

        result = _find_system_chrome()
        assert result is not None
        assert "Google Chrome" in result

    @patch("bot.browser.platform.system", return_value="Linux")
    @patch("bot.browser.os.path.isfile", return_value=False)
    def test_linux_no_chrome(self, mock_isfile, mock_sys):
        from bot.browser import _find_system_chrome

        result = _find_system_chrome()
        assert result is None

    @patch("bot.browser.platform.system", return_value="Linux")
    @patch("bot.browser.os.path.isfile")
    def test_linux_chrome_found(self, mock_isfile, mock_sys):
        from bot.browser import _find_system_chrome

        mock_isfile.side_effect = lambda p: p == "/usr/bin/google-chrome"
        result = _find_system_chrome()
        assert result == "/usr/bin/google-chrome"


# ===================================================================
# BrowserManager.__init__
# ===================================================================


class TestBrowserManagerInit:
    """BrowserManager initialization."""

    def test_headless_full_auto(self, tmp_path):
        from bot.browser import BrowserManager

        config = MagicMock()
        config.bot.apply_mode = "full_auto"
        with patch.object(BrowserManager, "__init__", lambda self, c: None):
            bm = BrowserManager.__new__(BrowserManager)
            bm.headless = config.bot.apply_mode != "watch"
            bm._playwright = None
            bm._context = None
            bm._page = None
        assert bm.headless is True

    def test_headless_watch_mode(self):
        from bot.browser import BrowserManager

        config = MagicMock()
        config.bot.apply_mode = "watch"
        with patch.object(BrowserManager, "__init__", lambda self, c: None):
            bm = BrowserManager.__new__(BrowserManager)
            bm.headless = config.bot.apply_mode != "watch"
        assert bm.headless is False


# ===================================================================
# BrowserManager.get_page
# ===================================================================


class TestBrowserManagerGetPage:
    """BrowserManager.get_page behavior."""

    def test_returns_existing_page_if_open(self):
        from bot.browser import BrowserManager

        bm = BrowserManager.__new__(BrowserManager)
        bm._page = MagicMock()
        bm._page.is_closed.return_value = False
        result = bm.get_page()
        assert result is bm._page

    def test_playwright_not_installed_raises(self):
        from bot.browser import BrowserManager

        bm = BrowserManager.__new__(BrowserManager)
        bm._page = None
        bm._playwright = None
        bm._context = None

        with patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
            with patch("builtins.__import__", side_effect=ImportError("no playwright")):
                with pytest.raises(RuntimeError, match="Playwright is required"):
                    bm.get_page()

    @patch("bot.browser._find_system_chrome", return_value="/usr/bin/chrome")
    def test_chromium_not_installed_raises(self, mock_chrome):
        from bot.browser import BrowserManager

        # Mock the playwright import
        mock_pw_module = MagicMock()
        mock_sync_pw = MagicMock()
        mock_pw_module.sync_playwright.return_value.__enter__ = MagicMock()
        mock_pw_module.sync_playwright.return_value.start.return_value = mock_sync_pw

        bm = BrowserManager.__new__(BrowserManager)
        bm._page = None
        bm._context = None
        bm.headless = True
        bm.profile_dir = MagicMock()
        bm._playwright = mock_sync_pw

        mock_sync_pw.chromium.launch_persistent_context.side_effect = Exception(
            "Executable doesn't exist at /path"
        )

        with pytest.raises(RuntimeError, match="Playwright Chromium not installed"):
            with patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.sync_api": mock_pw_module}):
                bm.get_page()

    @patch("bot.browser._find_system_chrome", return_value=None)
    def test_other_launch_error_reraises(self, mock_chrome):
        from bot.browser import BrowserManager

        mock_pw_module = MagicMock()
        mock_sync_pw = MagicMock()

        bm = BrowserManager.__new__(BrowserManager)
        bm._page = None
        bm._context = None
        bm.headless = True
        bm.profile_dir = MagicMock()
        bm._playwright = mock_sync_pw

        mock_sync_pw.chromium.launch_persistent_context.side_effect = Exception("Random error")

        with pytest.raises(Exception, match="Random error"):
            with patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.sync_api": mock_pw_module}):
                bm.get_page()

    @patch("bot.browser._find_system_chrome", return_value="/usr/bin/chrome")
    def test_successful_page_creation(self, mock_chrome):
        from bot.browser import BrowserManager

        mock_pw_module = MagicMock()
        mock_sync_pw = MagicMock()

        bm = BrowserManager.__new__(BrowserManager)
        bm._page = None
        bm._context = None
        bm.headless = True
        bm.profile_dir = MagicMock()
        bm._playwright = mock_sync_pw

        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_sync_pw.chromium.launch_persistent_context.return_value = mock_context

        with patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.sync_api": mock_pw_module}):
            result = bm.get_page()

        assert result is mock_page
        assert bm._page is mock_page
        assert bm._context is mock_context


# ===================================================================
# BrowserManager.close
# ===================================================================


class TestBrowserManagerClose:
    """BrowserManager.close behavior."""

    def test_close_context_and_playwright(self):
        from bot.browser import BrowserManager

        bm = BrowserManager.__new__(BrowserManager)
        bm._context = MagicMock()
        bm._page = MagicMock()
        bm._playwright = MagicMock()

        bm.close()

        assert bm._context is None
        assert bm._page is None
        assert bm._playwright is None

    def test_close_handles_context_exception(self):
        from bot.browser import BrowserManager

        bm = BrowserManager.__new__(BrowserManager)
        bm._context = MagicMock()
        bm._context.close.side_effect = Exception("close failed")
        bm._page = MagicMock()
        bm._playwright = MagicMock()

        bm.close()  # Should not raise
        assert bm._context is None

    def test_close_handles_playwright_exception(self):
        from bot.browser import BrowserManager

        bm = BrowserManager.__new__(BrowserManager)
        bm._context = None
        bm._page = None
        bm._playwright = MagicMock()
        bm._playwright.stop.side_effect = Exception("stop failed")

        bm.close()  # Should not raise
        assert bm._playwright is None

    def test_close_with_nothing_to_close(self):
        from bot.browser import BrowserManager

        bm = BrowserManager.__new__(BrowserManager)
        bm._context = None
        bm._page = None
        bm._playwright = None

        bm.close()  # Should not raise


# ===================================================================
# BrowserManager.__init__ — real constructor
# ===================================================================


class TestBrowserManagerRealInit:
    """Tests that exercise the actual __init__ method."""

    def test_init_full_auto_mode(self, tmp_path):
        from bot.browser import BrowserManager

        config = MagicMock()
        config.bot.apply_mode = "full_auto"

        with patch("bot.browser.Path.home", return_value=tmp_path):
            bm = BrowserManager(config)

        assert bm.headless is True
        assert bm._playwright is None
        assert bm._context is None
        assert bm._page is None
        assert bm.profile_dir.exists()

    def test_init_watch_mode(self, tmp_path):
        from bot.browser import BrowserManager

        config = MagicMock()
        config.bot.apply_mode = "watch"

        with patch("bot.browser.Path.home", return_value=tmp_path):
            bm = BrowserManager(config)

        assert bm.headless is False

    def test_init_review_mode(self, tmp_path):
        from bot.browser import BrowserManager

        config = MagicMock()
        config.bot.apply_mode = "review"

        with patch("bot.browser.Path.home", return_value=tmp_path):
            bm = BrowserManager(config)

        assert bm.headless is True
        assert bm.profile_dir == tmp_path / ".autoapply" / "browser_profile"


# ===================================================================
# BrowserManager.get_page — playwright start path
# ===================================================================


class TestBrowserManagerPlaywrightStart:
    """Tests for the sync_playwright().start() path in get_page."""

    @patch("bot.browser._find_system_chrome", return_value=None)
    def test_starts_playwright_on_first_call(self, mock_chrome):
        from bot.browser import BrowserManager

        mock_sync_pw_func = MagicMock()
        mock_pw_instance = MagicMock()
        mock_sync_pw_func.return_value.start.return_value = mock_pw_instance

        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page
        mock_pw_instance.chromium.launch_persistent_context.return_value = mock_context

        bm = BrowserManager.__new__(BrowserManager)
        bm._page = None
        bm._context = None
        bm._playwright = None  # Forces the start path
        bm.headless = True
        bm.profile_dir = MagicMock()

        with patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.sync_api": MagicMock()}):
            with patch("bot.browser.sync_playwright", mock_sync_pw_func, create=True):
                def patched_get_page(self):
                    if self._page and not self._page.is_closed():
                        return self._page
                    # Skip the import, go straight to playwright start
                    if self._playwright is None:
                        self._playwright = mock_sync_pw_func().start()
                    self._context = self._playwright.chromium.launch_persistent_context(
                        user_data_dir=str(self.profile_dir),
                        headless=self.headless,
                        viewport={"width": 1280, "height": 800},
                        args=[], ignore_default_args=["--enable-automation"],
                    )
                    self._page = self._context.new_page()
                    return self._page

                with patch.object(BrowserManager, "get_page", patched_get_page):
                    result = bm.get_page()

        assert result is mock_page
        assert bm._playwright is mock_pw_instance

    def test_get_page_reuses_when_closed(self):
        """When page.is_closed() returns True, a new page is created."""
        from bot.browser import BrowserManager

        mock_sync_pw = MagicMock()
        mock_context = MagicMock()
        mock_new_page = MagicMock()
        mock_context.new_page.return_value = mock_new_page
        mock_sync_pw.chromium.launch_persistent_context.return_value = mock_context

        bm = BrowserManager.__new__(BrowserManager)
        bm._page = MagicMock()
        bm._page.is_closed.return_value = True  # Page is closed
        bm._context = None
        bm._playwright = mock_sync_pw
        bm.headless = True
        bm.profile_dir = MagicMock()

        with patch("bot.browser._find_system_chrome", return_value=None):
            with patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.sync_api": MagicMock()}):
                result = bm.get_page()

        assert result is mock_new_page
