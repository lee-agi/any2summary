"""Tests for YouTube transcript fallback to audio transcription.

Verifies that when YouTube transcript fetch fails, the extension falls back
to local server audio transcription instead of generic URL processing.

Test cases:
1. Transcript success - should use transcript directly
2. Transcript fail + local server available - should fallback to audio transcription
3. Transcript fail + local server unavailable - should throw error (not silent fallback to generic)
"""

from __future__ import annotations

import re
from pathlib import Path


CHROME_EXT_SRC = Path("chrome_extension/src")


def test_process_youtube_video_has_fallback_logic() -> None:
    """Verify processYouTubeVideo function has try-catch with local server fallback.

    The function should:
    1. Try to fetch transcript first
    2. On failure, check if local server is available
    3. If local server available, fallback to processWithLocalServer
    4. If local server unavailable, re-throw the error
    """
    summarize_js = CHROME_EXT_SRC / "summarize.js"
    assert summarize_js.is_file(), "summarize.js should exist"

    content = summarize_js.read_text(encoding="utf-8")

    # Find processYouTubeVideo function
    assert "async function processYouTubeVideo" in content, (
        "Should have processYouTubeVideo function"
    )

    # Extract the function body (simplified check)
    func_match = re.search(
        r"async function processYouTubeVideo\([^)]*\)\s*\{([\s\S]*?)^\}",
        content,
        re.MULTILINE
    )
    assert func_match, "Should be able to find processYouTubeVideo function body"
    func_body = func_match.group(1)

    # Should have try-catch block for transcript fetch
    assert "try {" in func_body or "try{" in func_body, (
        "processYouTubeVideo should have try-catch block for transcript fetch"
    )
    assert "catch" in func_body, (
        "processYouTubeVideo should have catch block"
    )

    # Should check local server availability in catch block
    assert "isLocalServerAvailable" in func_body, (
        "processYouTubeVideo should check isLocalServerAvailable in fallback logic"
    )

    # Should call processWithLocalServer as fallback
    assert "processWithLocalServer" in func_body, (
        "processYouTubeVideo should call processWithLocalServer as fallback"
    )


def test_fallback_does_not_use_generic_url() -> None:
    """Verify processYouTubeVideo does NOT fallback to processGenericUrl.

    The previous buggy behavior was falling back to processGenericUrl,
    which just sends the URL to AI without transcript/audio content.
    The correct behavior is to use processWithLocalServer for audio transcription.
    """
    summarize_js = CHROME_EXT_SRC / "summarize.js"
    content = summarize_js.read_text(encoding="utf-8")

    # Extract processYouTubeVideo function body
    func_match = re.search(
        r"async function processYouTubeVideo\([^)]*\)\s*\{([\s\S]*?)^\}",
        content,
        re.MULTILINE
    )
    assert func_match, "Should be able to find processYouTubeVideo function body"
    func_body = func_match.group(1)

    # Should NOT call processGenericUrl directly in processYouTubeVideo
    assert "processGenericUrl" not in func_body, (
        "processYouTubeVideo should NOT fallback to processGenericUrl directly - "
        "it should use processWithLocalServer for better results"
    )


def test_fallback_re_throws_when_local_server_unavailable() -> None:
    """Verify that when local server is unavailable, the error is re-thrown.

    This ensures that the outer catch block in summarizeUrl can still handle
    the error appropriately, rather than silently failing.
    """
    summarize_js = CHROME_EXT_SRC / "summarize.js"
    content = summarize_js.read_text(encoding="utf-8")

    # Extract processYouTubeVideo function body
    func_match = re.search(
        r"async function processYouTubeVideo\([^)]*\)\s*\{([\s\S]*?)^\}",
        content,
        re.MULTILINE
    )
    assert func_match, "Should be able to find processYouTubeVideo function body"
    func_body = func_match.group(1)

    # Should have throw statement to re-throw error when local server unavailable
    assert "throw" in func_body, (
        "processYouTubeVideo should re-throw error when local server unavailable"
    )


def test_is_local_server_available_function_exists() -> None:
    """Verify isLocalServerAvailable helper function exists.

    This function checks if the local companion server is:
    1. Enabled in settings
    2. Actually running and healthy
    """
    summarize_js = CHROME_EXT_SRC / "summarize.js"
    content = summarize_js.read_text(encoding="utf-8")

    # Function should exist
    assert "async function isLocalServerAvailable" in content, (
        "Should have isLocalServerAvailable helper function"
    )

    # Function should check settings.local_server_enabled
    assert "local_server_enabled" in content, (
        "isLocalServerAvailable should check local_server_enabled setting"
    )

    # Function should call checkLocalServerHealth
    assert "checkLocalServerHealth" in content, (
        "isLocalServerAvailable should check server health"
    )


def test_process_with_local_server_function_exists() -> None:
    """Verify processWithLocalServer function exists for audio transcription.

    This function should:
    1. Call local server's /api/transcribe endpoint
    2. Process the transcription result
    3. Build summary using Azure OpenAI
    """
    summarize_js = CHROME_EXT_SRC / "summarize.js"
    content = summarize_js.read_text(encoding="utf-8")

    assert "async function processWithLocalServer" in content, (
        "Should have processWithLocalServer function"
    )

    # Should call local server for transcription
    assert "callLocalServerTranscribe" in content, (
        "processWithLocalServer should call local server for transcription"
    )


def test_fallback_logs_warning_message() -> None:
    """Verify that fallback logs a warning for debugging purposes."""
    summarize_js = CHROME_EXT_SRC / "summarize.js"
    content = summarize_js.read_text(encoding="utf-8")

    # Extract processYouTubeVideo function body
    func_match = re.search(
        r"async function processYouTubeVideo\([^)]*\)\s*\{([\s\S]*?)^\}",
        content,
        re.MULTILINE
    )
    assert func_match, "Should be able to find processYouTubeVideo function body"
    func_body = func_match.group(1)

    # Should have console.warn or console.log for fallback
    has_log = "console.warn" in func_body or "console.log" in func_body
    assert has_log, (
        "processYouTubeVideo should log when falling back to audio transcription"
    )
