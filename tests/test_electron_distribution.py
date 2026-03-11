"""Electron distribution tests for traceability coverage (TASK-029, #34).

Validates that the Electron packaging configuration supports electron-only
distribution (FR-081): no browser fallback, proper build targets, bundled
Python backend, and platform-specific installers.

Uses static analysis of electron/package.json and electron/main.js.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture()
def package_json():
    """Read and parse electron/package.json."""
    return json.loads(Path("electron/package.json").read_text(encoding="utf-8"))


@pytest.fixture()
def main_js():
    """Read electron/main.js source."""
    return Path("electron/main.js").read_text(encoding="utf-8")


# ===================================================================
# FR-081 — Electron-Only Distribution
# ===================================================================


class TestFR081ElectronOnlyDistribution:
    """FR-081: App is distributed as Electron desktop app only."""

    def test_electron_is_entry_point(self, package_json):
        """package.json main field points to main.js (Electron entry)."""
        assert package_json["main"] == "main.js"

    def test_electron_start_script(self, package_json):
        """Start script runs 'electron .' — not a web server."""
        assert package_json["scripts"]["start"] == "electron ."

    def test_electron_builder_configured(self, package_json):
        """electron-builder is configured for packaging."""
        assert "electron-builder" in package_json.get("devDependencies", {})
        assert "build" in package_json

    def test_app_id_set(self, package_json):
        """Build config has a desktop app ID."""
        assert package_json["build"]["appId"] == "com.autoapply.desktop"

    def test_product_name_set(self, package_json):
        """Build config has product name."""
        assert package_json["build"]["productName"] == "AutoApply"

    def test_windows_target(self, package_json):
        """Windows build targets NSIS installer."""
        assert package_json["build"]["win"]["target"] == "nsis"

    def test_macos_target(self, package_json):
        """macOS build targets DMG."""
        assert package_json["build"]["mac"]["target"] == "dmg"

    def test_linux_target(self, package_json):
        """Linux build targets AppImage."""
        assert package_json["build"]["linux"]["target"] == "AppImage"

    def test_python_backend_bundled(self, package_json):
        """Python backend is bundled as extraResources."""
        resources = package_json["build"]["extraResources"]
        backend_resource = [r for r in resources if r.get("to") == "python-backend"]
        assert len(backend_resource) == 1
        assert "app.py" in backend_resource[0]["filter"]

    def test_python_runtime_bundled(self, package_json):
        """Python runtime is bundled as extraResources."""
        resources = package_json["build"]["extraResources"]
        runtime_resource = [r for r in resources if r.get("to") == "python-runtime"]
        assert len(runtime_resource) == 1

    def test_no_browser_fallback(self, main_js):
        """Main process uses BrowserWindow — no browser fallback mode."""
        assert "BrowserWindow" in main_js
        # No http.createServer or express — purely Electron
        assert "createServer" not in main_js
        assert "express()" not in main_js

    def test_loads_localhost_only(self, main_js):
        """App loads from localhost — not a public URL."""
        assert "127.0.0.1" in main_js
        assert "loadURL" in main_js

    def test_dist_scripts_exist(self, package_json):
        """Distribution build scripts exist for all platforms."""
        scripts = package_json["scripts"]
        assert "dist:win" in scripts
        assert "dist:mac" in scripts
        assert "dist:linux" in scripts

    def test_prebuild_bundles_python(self, package_json):
        """Prebuild script bundles Python runtime."""
        assert "bundle-python" in package_json["scripts"]["prebuild"]

    def test_prebuild_syncs_version(self, package_json):
        """Prebuild script syncs version from pyproject.toml."""
        assert "sync-version" in package_json["scripts"]["prebuild"]

    def test_icon_generation_script(self, package_json):
        """Icon generation script exists."""
        assert "icons:generate" in package_json["scripts"]

    def test_platform_icons_configured(self, package_json):
        """Each platform has icon configured."""
        assert "icon.ico" in package_json["build"]["win"]["icon"]
        assert "icon.icns" in package_json["build"]["mac"]["icon"]
        assert "icon.png" in package_json["build"]["linux"]["icon"]

    def test_nsis_installer_options(self, package_json):
        """NSIS installer allows custom install directory."""
        nsis = package_json["build"]["nsis"]
        assert nsis["allowToChangeInstallationDirectory"] is True

    def test_mac_hardened_runtime(self, package_json):
        """macOS build uses hardened runtime for notarization."""
        assert package_json["build"]["mac"]["hardenedRuntime"] is True
