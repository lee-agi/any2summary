"""Tests for `--summary-length` parameter."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, MutableMapping, Sequence
from unittest import mock

import pytest

# Add package root to path
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from any2summary.cli import (
    generate_translation_summary,
    _build_length_prompt_modifier,
    _get_summary_length_config,
    SUMMARY_LENGTH_CONFIGS,
)


class TestSummaryLengthConfig:
    """Tests for summary length configuration."""

    def test_summary_length_configs_exist(self) -> None:
        """Verify all expected length options are defined."""
        assert "brief" in SUMMARY_LENGTH_CONFIGS
        assert "standard" in SUMMARY_LENGTH_CONFIGS
        assert "detailed" in SUMMARY_LENGTH_CONFIGS
        assert "full" in SUMMARY_LENGTH_CONFIGS

    def test_summary_length_config_has_required_keys(self) -> None:
        """Verify each config has max_tokens and prompt_modifier."""
        for name, config in SUMMARY_LENGTH_CONFIGS.items():
            assert "max_tokens" in config, f"{name} missing max_tokens"
            assert "prompt_modifier" in config, f"{name} missing prompt_modifier"
            assert isinstance(config["max_tokens"], int)
            assert isinstance(config["prompt_modifier"], str)

    def test_get_summary_length_config_default(self) -> None:
        """Verify default returns standard config."""
        config = _get_summary_length_config(None)
        assert config == SUMMARY_LENGTH_CONFIGS["standard"]

    def test_get_summary_length_config_valid(self) -> None:
        """Verify valid length names return correct config."""
        for name in ["brief", "standard", "detailed", "full"]:
            config = _get_summary_length_config(name)
            assert config == SUMMARY_LENGTH_CONFIGS[name]

    def test_get_summary_length_config_invalid(self) -> None:
        """Verify invalid length name raises error."""
        with pytest.raises(ValueError, match="无效的摘要长度"):
            _get_summary_length_config("invalid")


class TestSummaryLengthPromptModifier:
    """Tests for prompt modifier building."""

    def test_build_length_prompt_modifier_brief(self) -> None:
        """Verify brief modifier adds concise instruction."""
        modifier = _build_length_prompt_modifier("brief")
        assert "简洁" in modifier or "3-5" in modifier or "brief" in modifier.lower()

    def test_build_length_prompt_modifier_standard(self) -> None:
        """Verify standard modifier is empty or minimal."""
        modifier = _build_length_prompt_modifier("standard")
        # Standard should not add extra constraints
        assert modifier == "" or "标准" in modifier

    def test_build_length_prompt_modifier_detailed(self) -> None:
        """Verify detailed modifier requests more detail."""
        modifier = _build_length_prompt_modifier("detailed")
        assert "详细" in modifier or "展开" in modifier or "detail" in modifier.lower()

    def test_build_length_prompt_modifier_full(self) -> None:
        """Verify full modifier requests complete translation."""
        modifier = _build_length_prompt_modifier("full")
        assert "完整" in modifier or "不压缩" in modifier or "full" in modifier.lower()

    def test_build_length_prompt_modifier_none(self) -> None:
        """Verify None returns empty modifier."""
        modifier = _build_length_prompt_modifier(None)
        assert modifier == ""


class TestGenerateTranslationSummaryLength:
    """Tests for summary length integration in generate_translation_summary."""

    @pytest.fixture
    def mock_segments(self) -> Sequence[MutableMapping[str, Any]]:
        """Create mock transcript segments for testing."""
        return [
            {"start": 0.0, "end": 10.0, "text": "Hello world."},
            {"start": 10.0, "end": 20.0, "text": "This is a test."},
        ]

    @pytest.fixture
    def mock_azure_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up mock Azure environment variables."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AZURE_OPENAI_SUMMARY_DEPLOYMENT", "gpt-4")

    def test_generate_summary_accepts_length_parameter(
        self,
        mock_segments: Sequence[MutableMapping[str, Any]],
        mock_azure_env: None,
    ) -> None:
        """Verify generate_translation_summary accepts summary_length parameter."""
        mock_response = mock.Mock()
        mock_response.choices = [mock.Mock(message=mock.Mock(content="Test summary"))]

        with mock.patch("openai.AzureOpenAI") as mock_client_class:
            mock_client = mock.Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_client_class.return_value = mock_client

            with mock.patch("any2summary.cli._fetch_video_metadata", return_value={"title": "Test"}):
                with mock.patch("any2summary.cli._compose_summary_documents", return_value={"summary": "Test"}):
                    # Should not raise
                    result = generate_translation_summary(
                        segments=list(mock_segments),
                        video_url="https://youtube.com/watch?v=test",
                        summary_length="brief",
                    )
                    assert result is not None

    def test_generate_summary_uses_brief_tokens(
        self,
        mock_segments: Sequence[MutableMapping[str, Any]],
        mock_azure_env: None,
    ) -> None:
        """Verify brief summary uses lower token limit."""
        mock_response = mock.Mock()
        mock_response.choices = [mock.Mock(message=mock.Mock(content="Test"))]

        with mock.patch("openai.AzureOpenAI") as mock_client_class:
            mock_client = mock.Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_client_class.return_value = mock_client

            with mock.patch("any2summary.cli._fetch_video_metadata", return_value={"title": "Test"}):
                with mock.patch("any2summary.cli._compose_summary_documents", return_value={}):
                    generate_translation_summary(
                        segments=list(mock_segments),
                        video_url="https://youtube.com/watch?v=test",
                        summary_length="brief",
                    )

            # Check that max_completion_tokens was set to brief config
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs.get("max_completion_tokens") == SUMMARY_LENGTH_CONFIGS["brief"]["max_tokens"]

    def test_generate_summary_uses_detailed_tokens(
        self,
        mock_segments: Sequence[MutableMapping[str, Any]],
        mock_azure_env: None,
    ) -> None:
        """Verify detailed summary uses higher token limit."""
        mock_response = mock.Mock()
        mock_response.choices = [mock.Mock(message=mock.Mock(content="Test"))]

        with mock.patch("openai.AzureOpenAI") as mock_client_class:
            mock_client = mock.Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_client_class.return_value = mock_client

            with mock.patch("any2summary.cli._fetch_video_metadata", return_value={"title": "Test"}):
                with mock.patch("any2summary.cli._compose_summary_documents", return_value={}):
                    generate_translation_summary(
                        segments=list(mock_segments),
                        video_url="https://youtube.com/watch?v=test",
                        summary_length="detailed",
                    )

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs.get("max_completion_tokens") == SUMMARY_LENGTH_CONFIGS["detailed"]["max_tokens"]

    def test_generate_summary_modifies_prompt_for_brief(
        self,
        mock_segments: Sequence[MutableMapping[str, Any]],
        mock_azure_env: None,
    ) -> None:
        """Verify brief summary adds concise instruction to prompt."""
        mock_response = mock.Mock()
        mock_response.choices = [mock.Mock(message=mock.Mock(content="Test"))]

        with mock.patch("openai.AzureOpenAI") as mock_client_class:
            mock_client = mock.Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_client_class.return_value = mock_client

            with mock.patch("any2summary.cli._fetch_video_metadata", return_value={"title": "Test"}):
                with mock.patch("any2summary.cli._compose_summary_documents", return_value={}):
                    generate_translation_summary(
                        segments=list(mock_segments),
                        video_url="https://youtube.com/watch?v=test",
                        summary_length="brief",
                    )

            # Check system message includes brief modifier
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            messages = call_kwargs.get("messages", [])
            system_content = messages[0]["content"] if messages else ""
            brief_modifier = SUMMARY_LENGTH_CONFIGS["brief"]["prompt_modifier"]
            assert brief_modifier in system_content


class TestSummaryLengthCLIArgument:
    """Tests for --summary-length CLI argument parsing."""

    def test_summarize_command_accepts_summary_length(self) -> None:
        """Verify _run_summarize_command accepts --summary-length argument."""
        from any2summary.cli import _run_summarize_command
        import argparse

        # Test that argument is recognized (will fail for other reasons but shouldn't raise on arg)
        with mock.patch("any2summary.cli._load_dotenv_if_present"):
            with mock.patch("any2summary.cli._run_single_with_retry", return_value=0) as mock_run:
                try:
                    _run_summarize_command([
                        "--url", "https://youtube.com/watch?v=test",
                        "--summary-length", "brief",
                    ])
                except Exception:
                    pass  # Expected to fail without real credentials

    def test_invalid_summary_length_rejected(self) -> None:
        """Verify invalid --summary-length values are rejected."""
        from any2summary.cli import _run_summarize_command
        import argparse

        with pytest.raises(SystemExit):
            with mock.patch("any2summary.cli._load_dotenv_if_present"):
                _run_summarize_command([
                    "--url", "https://youtube.com/watch?v=test",
                    "--summary-length", "invalid_length",
                ])
