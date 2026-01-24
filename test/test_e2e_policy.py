"""Policy tests for Azure end-to-end guards."""

from __future__ import annotations

import pytest

import e2e_utils


def test_should_run_e2e_marker_detection() -> None:
    assert e2e_utils.should_run_e2e("e2e") is True
    assert e2e_utils.should_run_e2e("e2e and smoke") is True
    assert e2e_utils.should_run_e2e(None) is False
    assert e2e_utils.should_run_e2e("not e2e") is False


def test_require_azure_credentials_skips_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_SUMMARY_DEPLOYMENT", raising=False)

    with pytest.raises(pytest.skip.Exception):
        e2e_utils.require_azure_e2e_credentials()


def test_require_azure_credentials_returns_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "live-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://azure.invalid")
    monkeypatch.setenv("AZURE_OPENAI_SUMMARY_DEPLOYMENT", "gpt-e2e")
    monkeypatch.setenv("AZURE_OPENAI_SUMMARY_API_VERSION", "2024-02-15")

    credentials = e2e_utils.require_azure_e2e_credentials()

    assert credentials.api_key == "live-key"
    assert credentials.endpoint == "https://azure.invalid"
    assert credentials.summary_deployment == "gpt-e2e"
    assert credentials.api_version == "2024-02-15"
    assert "live-key" not in credentials.masked_api_key


def test_should_skip_e2e_when_marker_excludes(monkeypatch: pytest.MonkeyPatch) -> None:
    # Simulate pytest mark expression that excludes e2e.
    assert e2e_utils.should_run_e2e("not e2e and smoke") is False
