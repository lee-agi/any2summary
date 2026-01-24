"""Regression tests for the Chrome extension scaffolding."""

from __future__ import annotations

import json
from pathlib import Path


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)

    assert header.startswith(b"\x89PNG\r\n\x1a\n"), f"{path} must be a PNG"
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    return width, height


def test_manifest_core_fields_exist() -> None:
    manifest_path = Path("chrome_extension/manifest.json")
    assert manifest_path.is_file(), "manifest.json should exist for the Chrome extension"

    manifest = _load_json(manifest_path)
    assert manifest.get("manifest_version") == 3
    assert manifest.get("name"), "name is required"
    assert manifest.get("version"), "version is required"

    action = manifest.get("action", {})
    assert action.get("default_popup") == "src/popup.html"

    assert manifest.get("background", {}).get("service_worker") == "src/background.js"

    host_permissions = manifest.get("host_permissions", [])
    assert "<all_urls>" in host_permissions

    permissions = manifest.get("permissions", [])
    for needed in ["storage", "activeTab", "scripting"]:
        assert needed in permissions

    assert manifest.get("options_page") == "src/options.html"


def test_default_settings_contract() -> None:
    settings_path = Path("chrome_extension/config/default_settings.json")
    assert settings_path.is_file(), "Default settings must exist alongside the extension"

    settings = _load_json(settings_path)
    required_keys = {
        "azure_endpoint",
        "azure_api_version",
        "deployment",
        "use_responses_api",
        "cache_enabled",
        "cache_ttl_minutes",
        "cache_max_entries",
    }
    missing = required_keys.difference(settings)
    assert not missing, f"Missing keys in default_settings: {missing}"

    assert settings["cache_ttl_minutes"] > 0
    assert settings["cache_max_entries"] > 0
    assert not settings.get("api_key"), "API key must not be baked into defaults"
    # API version can be updated as Azure releases new versions
    assert "preview" in settings["azure_api_version"] or settings["azure_api_version"].startswith("202")
    assert settings["deployment"] == "llab-gpt-5"


def test_manifest_icons_exist_and_sizes_match() -> None:
    manifest_path = Path("chrome_extension/manifest.json")
    manifest = _load_json(manifest_path)

    icons = manifest.get("icons", {})
    assert icons, "icons must be defined for the extension"

    for size_key, relative_path in icons.items():
        expected_size = int(size_key)
        icon_path = manifest_path.parent / relative_path
        assert icon_path.is_file(), f"Missing icon: {relative_path}"

        width, height = _read_png_size(icon_path)
        assert width == expected_size and height == expected_size


def test_manifest_side_panel_and_permissions() -> None:
    manifest_path = Path("chrome_extension/manifest.json")
    manifest = _load_json(manifest_path)

    side_panel = manifest.get("side_panel", {})
    assert side_panel.get("default_path") == "src/sidepanel.html"

    permissions = set(manifest.get("permissions", []))
    assert "notifications" in permissions
    assert "downloads" in permissions, "downloads permission is required for auto-save feature"

    side_panel_path = manifest_path.parent / side_panel.get("default_path")
    assert side_panel_path.is_file(), "sidepanel.html must exist"


def test_manifest_commands_hotkey() -> None:
    manifest_path = Path("chrome_extension/manifest.json")
    manifest = _load_json(manifest_path)

    commands = manifest.get("commands", {})
    assert "run-summary" in commands, "Keyboard shortcut command is required"
    shortcut = commands["run-summary"].get("suggested_key", {}).get("default")
    assert shortcut == "Ctrl+Shift+S"


def test_auto_save_settings_exist() -> None:
    """Test that auto-save configuration options exist in default settings."""
    settings_path = Path("chrome_extension/config/default_settings.json")
    settings = _load_json(settings_path)

    assert "auto_save_summary" in settings, "auto_save_summary config is required"
    assert "save_subdirectory" in settings, "save_subdirectory config is required"

    assert isinstance(settings["auto_save_summary"], bool)
    assert isinstance(settings["save_subdirectory"], str)
    assert len(settings["save_subdirectory"]) > 0, "save_subdirectory should have a default value"


def test_file_saver_module_exists() -> None:
    """Test that the fileSaver.js module exists."""
    file_saver_path = Path("chrome_extension/src/fileSaver.js")
    assert file_saver_path.is_file(), "fileSaver.js module must exist"

    content = file_saver_path.read_text(encoding="utf-8")
    assert "saveSummaryAsMarkdown" in content, "saveSummaryAsMarkdown function must be exported"
    assert "chrome.downloads" in content, "Must use Chrome downloads API"


def test_options_html_has_auto_save_config() -> None:
    """Test that options.html includes auto-save configuration UI."""
    options_path = Path("chrome_extension/src/options.html")
    content = options_path.read_text(encoding="utf-8")

    assert 'id="autoSaveSummary"' in content, "autoSaveSummary toggle must exist"
    assert 'id="saveSubdirectory"' in content, "saveSubdirectory input must exist"


def test_options_js_handles_auto_save_config() -> None:
    """Test that options.js handles auto-save configuration."""
    options_path = Path("chrome_extension/src/options.js")
    content = options_path.read_text(encoding="utf-8")

    assert "autoSaveSummary" in content, "autoSaveSummary must be handled"
    assert "saveSubdirectory" in content, "saveSubdirectory must be handled"
    assert "auto_save_summary" in content, "auto_save_summary setting key must be used"
    assert "save_subdirectory" in content, "save_subdirectory setting key must be used"


def test_background_js_imports_file_saver() -> None:
    """Test that background.js imports and uses the fileSaver module."""
    background_path = Path("chrome_extension/src/background.js")
    content = background_path.read_text(encoding="utf-8")

    assert "import" in content and "fileSaver" in content, "Must import fileSaver module"
    assert "saveSummaryAsMarkdown" in content, "Must use saveSummaryAsMarkdown function"
    assert "auto_save_summary" in content, "Must check auto_save_summary setting"
