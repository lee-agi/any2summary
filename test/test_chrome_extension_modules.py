"""Tests for Chrome extension JavaScript modules.

Verifies that all required modules exist and have the expected structure.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


CHROME_EXT_SRC = Path("chrome_extension/src")


def test_content_detector_module_exists() -> None:
    """Verify contentDetector.js exists and exports required functions."""
    module_path = CHROME_EXT_SRC / "contentDetector.js"
    assert module_path.is_file(), "contentDetector.js should exist"

    content = module_path.read_text(encoding="utf-8")

    # Check for required exports
    required_exports = [
        "detectContentType",
        "isYouTubeUrl",
        "extractYouTubeVideoId",
        "shouldForceAzureTranscription",
        "isProbableArticle",
    ]

    for export_name in required_exports:
        assert f"export function {export_name}" in content or f"export async function {export_name}" in content, (
            f"contentDetector.js should export {export_name}"
        )


def test_content_detector_has_platform_configs() -> None:
    """Verify contentDetector.js has platform configuration arrays."""
    module_path = CHROME_EXT_SRC / "contentDetector.js"
    content = module_path.read_text(encoding="utf-8")

    # Check for platform configurations from cli.py
    assert "MEDIA_HOST_SUFFIXES" in content, "Should have MEDIA_HOST_SUFFIXES config"
    assert "youtube.com" in content, "Should include YouTube in media hosts"
    assert "bilibili.com" in content, "Should include Bilibili in media hosts"
    assert "tiktok.com" in content, "Should include TikTok in video platforms"


def test_youtube_transcript_module_exists() -> None:
    """Verify youtubeTranscript.js exists and exports required functions."""
    module_path = CHROME_EXT_SRC / "youtubeTranscript.js"
    assert module_path.is_file(), "youtubeTranscript.js should exist"

    content = module_path.read_text(encoding="utf-8")

    # Check for required exports
    required_exports = [
        "fetchYouTubeTranscript",
        "formatTranscriptTimeline",
        "hasYouTubeCaptions",
        "getAvailableCaptionLanguages",
    ]

    for export_name in required_exports:
        assert f"export function {export_name}" in content or f"export async function {export_name}" in content, (
            f"youtubeTranscript.js should export {export_name}"
        )


def test_youtube_transcript_parses_player_response() -> None:
    """Verify youtubeTranscript.js can parse YouTube player response."""
    module_path = CHROME_EXT_SRC / "youtubeTranscript.js"
    content = module_path.read_text(encoding="utf-8")

    # Should have function to extract player response from HTML
    assert "extractPlayerResponse" in content, "Should have extractPlayerResponse function"
    assert "ytInitialPlayerResponse" in content, "Should look for ytInitialPlayerResponse in HTML"


def test_article_parser_module_exists() -> None:
    """Verify articleParser.js exists and exports required functions."""
    module_path = CHROME_EXT_SRC / "articleParser.js"
    assert module_path.is_file(), "articleParser.js should exist"

    content = module_path.read_text(encoding="utf-8")

    # Check for required exports
    # Note: parseArticleHtml was renamed to parseArticleHtmlWithRegex for Service Worker compatibility
    required_exports = [
        "parseArticleHtmlWithRegex",
        "fetchArticleContent",
        "formatArticleForSummary",
        "extractArticleMetadata",
    ]

    for export_name in required_exports:
        # Check for direct export or named export syntax
        has_direct_export = (
            f"export function {export_name}" in content or
            f"export async function {export_name}" in content
        )
        has_named_export = f"export {{ " in content and export_name in content
        assert has_direct_export or has_named_export, (
            f"articleParser.js should export {export_name}"
        )


def test_article_parser_extracts_metadata() -> None:
    """Verify articleParser.js extracts article metadata."""
    module_path = CHROME_EXT_SRC / "articleParser.js"
    content = module_path.read_text(encoding="utf-8")

    # Should extract standard metadata
    assert "og:description" in content, "Should extract Open Graph description"
    assert "og:image" in content, "Should extract Open Graph image"
    assert 'querySelector("title")' in content or "querySelector('title')" in content, "Should extract title"


def test_prompts_module_exists() -> None:
    """Verify prompts.js exists and exports required prompts."""
    module_path = CHROME_EXT_SRC / "prompts.js"
    assert module_path.is_file(), "prompts.js should exist"

    content = module_path.read_text(encoding="utf-8")

    # Check for required exports
    required_exports = [
        "VIDEO_SUMMARY_PROMPT",
        "ARTICLE_SUMMARY_PROMPT",
        "getPromptForContentType",
        "buildVideoPrompt",
        "buildArticlePrompt",
    ]

    for export_name in required_exports:
        pattern = rf"export\s+(const|function|async function)\s+{export_name}"
        assert re.search(pattern, content), f"prompts.js should export {export_name}"


def test_prompts_match_cli_py() -> None:
    """Verify prompts in prompts.js match those in cli.py prompt files."""
    module_path = CHROME_EXT_SRC / "prompts.js"
    content = module_path.read_text(encoding="utf-8")

    # Check for key phrases from the original prompts
    key_phrases = [
        "播客、视频等多模态信息",
        "时间线",
        "说话人",
        "markdown加粗",
        "翻译要求",
    ]

    for phrase in key_phrases:
        assert phrase in content, f"prompts.js should contain key phrase: {phrase}"


def test_summarize_js_imports_all_modules() -> None:
    """Verify summarize.js imports all required modules."""
    module_path = CHROME_EXT_SRC / "summarize.js"
    content = module_path.read_text(encoding="utf-8")

    # Check for required imports
    required_imports = [
        "contentDetector.js",
        "youtubeTranscript.js",
        "articleParser.js",
        "prompts.js",
    ]

    for import_file in required_imports:
        assert import_file in content, f"summarize.js should import {import_file}"


def test_summarize_js_handles_content_types() -> None:
    """Verify summarize.js handles different content types."""
    module_path = CHROME_EXT_SRC / "summarize.js"
    content = module_path.read_text(encoding="utf-8")

    # Check for content type handling
    assert "processYouTubeVideo" in content, "Should have YouTube video processing"
    assert "processArticle" in content, "Should have article processing"
    assert "processGenericUrl" in content, "Should have generic URL fallback"
    assert "detectContentType" in content, "Should use content type detection"


def test_summarize_js_supports_both_apis() -> None:
    """Verify summarize.js supports both Responses API and Chat Completions API."""
    module_path = CHROME_EXT_SRC / "summarize.js"
    content = module_path.read_text(encoding="utf-8")

    # Check for both API formats
    assert "buildResponsesApiBody" in content, "Should support Responses API"
    assert "buildChatCompletionsBody" in content, "Should support Chat Completions API"
    assert "use_responses_api" in content, "Should check use_responses_api setting"


def test_default_settings_has_new_options() -> None:
    """Verify default_settings.json has all required options."""
    settings_path = Path("chrome_extension/config/default_settings.json")
    assert settings_path.is_file(), "default_settings.json should exist"

    settings = json.loads(settings_path.read_text(encoding="utf-8"))

    required_keys = [
        "azure_endpoint",
        "azure_api_version",
        "deployment",
        "use_responses_api",
        "cache_enabled",
        "api_key",
        "preferred_languages",
        "auto_detect_content_type",
        "use_http_detection",
        "max_output_tokens",
    ]

    for key in required_keys:
        assert key in settings, f"default_settings.json should have {key}"


def test_preferred_languages_is_array() -> None:
    """Verify preferred_languages is an array with expected languages."""
    settings_path = Path("chrome_extension/config/default_settings.json")
    settings = json.loads(settings_path.read_text(encoding="utf-8"))

    languages = settings.get("preferred_languages", [])
    assert isinstance(languages, list), "preferred_languages should be a list"
    assert "en" in languages, "preferred_languages should include English"
    assert any(lang.startswith("zh") for lang in languages), "preferred_languages should include Chinese"


def test_all_js_modules_have_jsdoc() -> None:
    """Verify all JS modules have JSDoc comments for exported functions."""
    js_files = [
        "contentDetector.js",
        "youtubeTranscript.js",
        "articleParser.js",
        "prompts.js",
        "summarize.js",
    ]

    for js_file in js_files:
        module_path = CHROME_EXT_SRC / js_file
        if not module_path.exists():
            continue

        content = module_path.read_text(encoding="utf-8")

        # Find all export functions
        export_pattern = re.compile(r"export\s+(async\s+)?function\s+(\w+)")
        exports = export_pattern.findall(content)

        for _, func_name in exports:
            # Check if there's a JSDoc comment before the function
            jsdoc_pattern = re.compile(
                rf"/\*\*[\s\S]*?\*/\s*export\s+(async\s+)?function\s+{func_name}"
            )
            assert jsdoc_pattern.search(content), (
                f"{js_file}: function {func_name} should have JSDoc comment"
            )
