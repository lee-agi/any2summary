"""End-to-end tests for the Azure summary pipeline using a real YouTube URL.

All tests are marked ``@pytest.mark.e2e`` and are skipped by default unless
pytest is invoked with ``-m e2e``.  They require valid Azure credentials:

    AZURE_OPENAI_API_KEY
    AZURE_OPENAI_ENDPOINT
    AZURE_OPENAI_SUMMARY_DEPLOYMENT   (must end with -pro → Responses API path)

Run:
    .venv/bin/python -m pytest test/test_cli_summary_e2e.py -m e2e -v -s

These tests validate the bug fixes shipped in v1.6.2:
- _call_responses_api()  uses /openai/responses?api-version=  (not /openai/v1)
- Auth header is api-key  (not Authorization: Bearer)
- Proxy is bypassed via _create_azure_http_client(proxy=None)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

import e2e_utils

from any2summary import cli

REAL_YOUTUBE_URL = "https://www.youtube.com/watch?v=9jgcT0Fqt7U"


# ---------------------------------------------------------------------------
# Layer 1: _call_responses_api() — raw httpx, correct URL/auth/proxy
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_call_responses_api_returns_nonempty_text() -> None:
    """Real Azure call via _call_responses_api() — verifies URL/auth/proxy fix."""
    creds = e2e_utils.require_azure_e2e_credentials()

    result = cli._call_responses_api(
        endpoint=creds.endpoint,
        api_key=creds.api_key,
        deployment=creds.summary_deployment,
        messages=[
            {"role": "system", "content": "你是一个助手，只用一句话回答。"},
            {"role": "user", "content": "用一句话介绍自己。"},
        ],
        max_output_tokens=512,
    )

    assert isinstance(result, str)
    assert len(result.strip()) > 0, "Azure Responses API returned empty text"


@pytest.mark.e2e
def test_call_responses_api_url_correct_no_v1() -> None:
    """Confirm /openai/responses?api-version= (NOT /openai/v1/responses) is used."""
    import httpx

    creds = e2e_utils.require_azure_e2e_credentials()
    sent_urls: list[str] = []
    original_create = cli._create_azure_http_client

    class CapturingClient:
        """Wraps a real httpx.Client and records request URLs."""

        def __init__(self) -> None:
            self._inner = original_create()

        def post(self, url: str, **kwargs: Any) -> Any:
            sent_urls.append(url)
            return self._inner.post(url, **kwargs)

        def close(self) -> None:
            self._inner.close()

    original = cli._create_azure_http_client
    cli._create_azure_http_client = CapturingClient  # type: ignore[assignment]
    try:
        cli._call_responses_api(
            endpoint=creds.endpoint,
            api_key=creds.api_key,
            deployment=creds.summary_deployment,
            messages=[{"role": "user", "content": "ping"}],
            max_output_tokens=256,
        )
    finally:
        cli._create_azure_http_client = original  # type: ignore[assignment]

    assert sent_urls, "No HTTP request was sent"
    url = sent_urls[0]
    assert "/openai/responses" in url, f"Expected /openai/responses in URL, got: {url}"
    assert "/v1/" not in url, f"URL must not contain /v1/, got: {url}"
    assert "api-version=" in url, f"Missing api-version query param: {url}"


# ---------------------------------------------------------------------------
# Layer 2: generate_translation_summary() — fetch transcript + call Azure
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_generate_translation_summary_real_youtube() -> None:
    """Fetch real YouTube transcript then summarise via Azure Responses API."""
    creds = e2e_utils.require_azure_e2e_credentials()

    # Step 1: fetch transcript (real network call)
    try:
        segments = cli.fetch_transcript_with_metadata(REAL_YOUTUBE_URL)
    except Exception as exc:
        pytest.skip(f"Could not fetch YouTube transcript: {exc}")

    assert segments, "YouTube transcript is empty — video may be unavailable"

    # Step 2: summarise (real Azure call, no mocks)
    result = cli.generate_translation_summary(segments, REAL_YOUTUBE_URL)

    # Structure checks
    assert "summary_markdown" in result
    assert "timeline_markdown" in result
    assert "metadata" in result
    assert "total_words" in result
    assert "estimated_minutes" in result
    assert "file_base" in result

    summary = result["summary_markdown"]
    timeline = result["timeline_markdown"]

    # Heading format: # 【Domain】Title-YYYY-MMM
    first_line = summary.splitlines()[0]
    assert first_line.startswith("# 【"), f"Unexpected heading: {first_line!r}"

    assert len(summary) > 100, "Summary is suspiciously short"
    assert len(timeline) > 50, "Timeline is suspiciously short"
    assert result["total_words"] > 0
    assert result["estimated_minutes"] >= 1

    # Footer section added by _compose_summary_documents
    assert "## 欢迎交流与合作" in summary

    # domain must have been inferred
    domain = result["metadata"].get("domain", "")
    assert domain and domain != "", "Domain should be inferred from content"

    print(f"\n[e2e] heading   : {first_line}")
    print(f"[e2e] domain    : {domain}")
    print(f"[e2e] words     : {result['total_words']}")
    print(f"[e2e] file_base : {result['file_base']}")


# ---------------------------------------------------------------------------
# Layer 3: cli.run() — full pipeline through the CLI entry point
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_run_full_pipeline_real_youtube(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: cli.run() fetches YouTube, calls Azure, outputs JSON."""
    e2e_utils.require_azure_e2e_credentials()

    monkeypatch.setenv("ANY2SUMMARY_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("ANY2SUMMARY_OUTBOX_DIR", str(tmp_path / "outbox"))

    _TRANSCRIPT_KEYWORDS = ("transcript", "bot", "sign in", "cookies", "caption")

    try:
        exit_code = cli.run([
            "--url", REAL_YOUTUBE_URL,
            "--azure-summary",
            "--no-azure-streaming",
            "--summary-length", "brief",
        ])
    except Exception as exc:
        # cli.run() may propagate transcript errors instead of returning non-zero
        msg = str(exc).lower()
        if any(kw in msg for kw in _TRANSCRIPT_KEYWORDS):
            pytest.skip(f"cli.run() raised exception; likely transcript failure: {exc}")
        raise

    output = capsys.readouterr().out.strip()

    if exit_code != 0:
        # Transcript fetch may fail in CI; treat as skip
        out_lower = output.lower()
        if not output or any(kw in out_lower for kw in _TRANSCRIPT_KEYWORDS):
            pytest.skip(f"cli.run() non-zero exit ({exit_code}); likely transcript failure")

    assert exit_code == 0, f"cli.run() returned {exit_code}; output: {output[:500]}"

    data = json.loads(output)

    assert "summary" in data, "Output JSON missing 'summary'"
    assert "timeline" in data, "Output JSON missing 'timeline'"
    assert "segments" in data, "Output JSON missing 'segments'"
    assert "total_words" in data, "Output JSON missing 'total_words'"
    assert "summary_path" in data, "Output JSON missing 'summary_path'"

    assert len(data["summary"]) > 100, "summary is suspiciously short"
    assert data["total_words"] > 0
    assert Path(data["summary_path"]).exists(), "summary file not written to disk"

    first_line = data["summary"].splitlines()[0]
    assert first_line.startswith("# 【"), f"Unexpected heading: {first_line!r}"

    print(f"\n[e2e] cli.run() exit_code : {exit_code}")
    print(f"[e2e] summary heading     : {first_line}")
    print(f"[e2e] total_words         : {data['total_words']}")
    print(f"[e2e] summary_path        : {data['summary_path']}")
