"""PyInstaller packaging tests for traceability coverage (TASK-031).

Validates that the PyInstaller spec and build configuration support
PyWebView-based distribution (FR-096, FR-097): proper spec file,
data includes, hidden imports, and Electron removal.

Replaces: test_electron_modules.py, test_electron_distribution.py
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def spec_content():
    """Read autoapply.spec source."""
    return Path("autoapply.spec").read_text(encoding="utf-8")


# ===================================================================
# FR-096 — PyInstaller Packaging
# ===================================================================


class TestFR096PyInstallerPackaging:
    """FR-096: App packaged via PyInstaller into distributable installer."""

    def test_spec_file_exists(self):
        """autoapply.spec exists as build config."""
        assert Path("autoapply.spec").exists()

    def test_spec_entry_point(self, spec_content):
        """Spec uses run.py as entry point."""
        assert "run.py" in spec_content

    def test_spec_includes_templates(self, spec_content):
        """Spec bundles templates/ directory."""
        assert '"templates"' in spec_content

    def test_spec_includes_static(self, spec_content):
        """Spec bundles static/ directory."""
        assert '"static"' in spec_content

    def test_spec_hidden_imports_gevent(self, spec_content):
        """Spec includes gevent in hidden imports."""
        assert '"gevent"' in spec_content

    def test_spec_hidden_imports_webview(self, spec_content):
        """Spec includes webview in hidden imports."""
        assert '"webview"' in spec_content

    def test_spec_hidden_imports_pystray(self, spec_content):
        """Spec includes pystray in hidden imports."""
        assert '"pystray"' in spec_content

    def test_spec_hidden_imports_shell(self, spec_content):
        """Spec includes shell module in hidden imports."""
        assert '"shell"' in spec_content
        assert '"shell.main"' in spec_content
        assert '"shell.tray"' in spec_content
        assert '"shell.single_instance"' in spec_content

    def test_spec_windowed_mode(self, spec_content):
        """Spec builds as windowed app (no console)."""
        assert "console=False" in spec_content

    def test_spec_app_name(self, spec_content):
        """Spec uses AutoApply as app name."""
        assert 'name="AutoApply"' in spec_content

    def test_spec_icon_configured(self, spec_content):
        """Spec has icon configured for Windows."""
        assert "icon.ico" in spec_content

    def test_spec_one_dir_mode(self, spec_content):
        """Spec uses COLLECT (one-dir mode, not one-file)."""
        assert "COLLECT(" in spec_content


# ===================================================================
# FR-097 — Electron Removal
# ===================================================================


class TestFR097ElectronRemoval:
    """FR-097: electron/ directory and Node.js deps completely removed."""

    def test_electron_main_js_removed(self):
        """electron/main.js (source) does not exist."""
        assert not Path("electron/main.js").exists()

    def test_electron_package_json_removed(self):
        """electron/package.json (source) does not exist."""
        assert not Path("electron/package.json").exists()

    def test_electron_preload_removed(self):
        """electron/preload.js (source) does not exist."""
        assert not Path("electron/preload.js").exists()

    def test_electron_tray_removed(self):
        """electron/tray.js (source) does not exist."""
        assert not Path("electron/tray.js").exists()

    def test_no_electron_in_pyproject(self):
        """pyproject.toml does not reference Electron."""
        content = Path("pyproject.toml").read_text(encoding="utf-8")
        assert "Electron" not in content
        assert "electron" not in content.lower().split("exclude")[0]

    def test_icons_preserved(self):
        """App icons exist in static/icons/."""
        assert Path("static/icons/icon.png").exists()
        assert Path("static/icons/icon.ico").exists()

    def test_pywebview_in_deps(self):
        """pywebview is listed in pyproject.toml dependencies."""
        content = Path("pyproject.toml").read_text(encoding="utf-8")
        assert "pywebview" in content

    def test_pystray_in_deps(self):
        """pystray is listed in pyproject.toml dependencies."""
        content = Path("pyproject.toml").read_text(encoding="utf-8")
        assert "pystray" in content
