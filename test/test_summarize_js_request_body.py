"""Tests for summarize.js request body format.

Verifies that:
1. The Responses API and Chat Completions API request bodies use the correct
   format for Azure OpenAI.
2. Local server endpoints accept JSON request body (not query parameters).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


# ----- Local Server Request Body Tests -----


@pytest.fixture
def mock_cli_perform_azure_diarization():
    """Mock CLI's perform_azure_diarization function."""
    with patch("any2summary.cli.perform_azure_diarization") as mock_func:
        mock_func.return_value = {
            "speakers": ["Speaker 1"],
            "transcript": [{"text": "Hello", "start": 0.0, "end": 1.0}],
            "metadata": {"duration": 60},
        }
        yield mock_func


@pytest.fixture
def mock_cli_run_single():
    """Mock CLI's _run_single function."""
    with patch("any2summary.cli._run_single") as mock_func:
        mock_func.return_value = 0
        yield mock_func


@pytest.fixture
def test_client():
    """Create FastAPI test client."""
    from fastapi.testclient import TestClient
    from any2summary.server import create_app

    app = create_app()
    return TestClient(app)


def test_transcribe_accepts_json_body(
    test_client: Any,
    mock_cli_perform_azure_diarization: Any,
) -> None:
    """Verify /api/transcribe accepts JSON request body (not query params).

    This test ensures the server accepts POST requests with JSON body,
    matching the Chrome extension's fetch call format in summarize.js:

        fetch(`${serverUrl}/api/transcribe`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url, language, ... }),
        })
    """
    response = test_client.post(
        "/api/transcribe",
        json={
            "url": "https://www.youtube.com/watch?v=test123",
            "language": "en",
            "streaming": True,
        },
    )

    # Should succeed (not 422 Unprocessable Entity)
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    # Verify the mock was called with correct parameters
    mock_cli_perform_azure_diarization.assert_called_once()
    call_kwargs = mock_cli_perform_azure_diarization.call_args.kwargs
    assert call_kwargs["video_url"] == "https://www.youtube.com/watch?v=test123"
    assert call_kwargs["language"] == "en"
    assert call_kwargs["streaming"] is True


def test_transcribe_accepts_optional_params(
    test_client: Any,
    mock_cli_perform_azure_diarization: Any,
) -> None:
    """Verify /api/transcribe handles optional parameters in JSON body."""
    response = test_client.post(
        "/api/transcribe",
        json={
            "url": "https://www.youtube.com/watch?v=test456",
            "language": "zh",
            "max_speakers": 3,
            "known_speaker_names": ["Alice", "Bob"],
            "streaming": False,
        },
    )

    assert response.status_code == 200

    call_kwargs = mock_cli_perform_azure_diarization.call_args.kwargs
    assert call_kwargs["max_speakers"] == 3
    assert call_kwargs["known_speaker_names"] == ["Alice", "Bob"]
    assert call_kwargs["streaming"] is False


def test_summarize_accepts_json_body(
    test_client: Any,
    mock_cli_run_single: Any,
) -> None:
    """Verify /api/summarize accepts JSON request body (not query params).

    This test ensures the server accepts POST requests with JSON body,
    matching the Chrome extension's fetch call format in summarize.js:

        fetch(`${serverUrl}/api/summarize`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url, language, azure_summary, ... }),
        })
    """
    response = test_client.post(
        "/api/summarize",
        json={
            "url": "https://example.com/article",
            "language": "en",
            "azure_summary": True,
            "azure_streaming": True,
        },
    )

    # Should succeed (not 422 Unprocessable Entity)
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )


def test_transcribe_rejects_query_params_only(
    test_client: Any,
) -> None:
    """Verify /api/transcribe requires JSON body, not just query params.

    Before the fix, requests with only query params would work.
    After the fix using Pydantic BaseModel, the body is required.
    """
    # POST with query params but no body should fail validation
    response = test_client.post(
        "/api/transcribe?url=https://example.com&language=en"
    )

    # Should fail with 422 (missing required body)
    assert response.status_code == 422


# ----- Azure OpenAI API Format Tests (existing) -----


def test_responses_api_input_uses_array_format() -> None:
    """Verify Responses API builds input as array with role and content objects.

    The Azure OpenAI Responses API (via OpenAI SDK) expects `input` to be an array
    with role and content objects, matching cli.py format:
    input: [{ role: "system", content: [...] }, { role: "user", content: [...] }]

    Reference: cli.py lines 2043-2056
    """
    summarize_js = Path("chrome_extension/src/summarize.js")
    assert summarize_js.is_file(), "summarize.js should exist"

    content = summarize_js.read_text(encoding="utf-8")

    # Verify buildResponsesApiBody function exists and builds input array
    assert "buildResponsesApiBody" in content, (
        "Should have buildResponsesApiBody function"
    )
    assert "input.push(" in content, (
        "Responses API should build input array using push"
    )
    assert 'role: "system"' in content or 'role: "user"' in content, (
        "Responses API input should include role field"
    )
    assert 'type: "input_text"' in content, (
        "Responses API input should use input_text content type"
    )


def test_chat_completions_api_uses_messages_array() -> None:
    """Verify Chat Completions API builds messages as array."""
    summarize_js = Path("chrome_extension/src/summarize.js")
    content = summarize_js.read_text(encoding="utf-8")

    # Verify buildChatCompletionsBody function exists and builds messages array
    assert "buildChatCompletionsBody" in content, (
        "Should have buildChatCompletionsBody function"
    )
    assert "messages.push(" in content, (
        "Chat Completions API should build messages array using push"
    )


def test_responses_api_url_uses_v1_endpoint() -> None:
    """Verify Responses API uses the correct /openai/v1/responses endpoint.

    Azure OpenAI Responses API (Azure AI Foundry) uses a different endpoint format:
    - Correct: /openai/v1/responses (model specified in request body, no api-version)
    - Wrong: /openai/deployments/{deployment}/responses (old format, returns 404)

    Reference: cli.py _build_responses_base_url function
    """
    summarize_js = Path("chrome_extension/src/summarize.js")
    content = summarize_js.read_text(encoding="utf-8")

    # Verify using the correct v1 endpoint format
    assert '"/openai/v1/responses"' in content, (
        "Responses API should use /openai/v1/responses endpoint format"
    )

    # Verify we're NOT using the old deployment-based path for Responses API
    assert '"/openai/deployments/" + settings.deployment + "/responses"' not in content, (
        "Responses API should NOT use deployment-based URL path"
    )

    # Verify Responses API returns URL directly without api-version
    assert 'return base + "/openai/v1/responses"' in content, (
        "Responses API URL should be returned directly without api-version query param"
    )


def test_chat_completions_api_uses_api_version() -> None:
    """Verify Chat Completions API uses api-version parameter.

    Only Chat Completions API needs api-version; Responses API doesn't use it.
    """
    summarize_js = Path("chrome_extension/src/summarize.js")
    content = summarize_js.read_text(encoding="utf-8")

    # Chat Completions API should set api-version
    assert 'url.searchParams.set("api-version"' in content, (
        "Chat Completions API should set api-version query parameter"
    )


def test_summarize_supports_both_apis() -> None:
    """Verify summarize.js supports both Responses API and Chat Completions API."""
    summarize_js = Path("chrome_extension/src/summarize.js")
    content = summarize_js.read_text(encoding="utf-8")

    # Should have logic to choose between APIs
    assert "use_responses_api" in content, (
        "Should check use_responses_api setting"
    )

    # Should call the appropriate body builder
    assert "buildResponsesApiBody" in content, "Should have Responses API body builder"
    assert "buildChatCompletionsBody" in content, "Should have Chat Completions body builder"
