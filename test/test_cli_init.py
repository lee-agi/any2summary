"""Tests for `any2summary init` configuration wizard command."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

# Add package root to path
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from any2summary.cli import run, _run_init_command


class TestInitCommand:
    """Tests for the init subcommand."""

    def test_init_subcommand_is_recognized(self) -> None:
        """Verify that `init` subcommand is recognized and calls handler."""
        with mock.patch(
            "any2summary.cli._run_init_command", return_value=0
        ) as mock_handler:
            exit_code = run(["init"])
            mock_handler.assert_called_once()
            assert exit_code == 0

    def test_init_creates_env_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that init creates .env file with user input."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        # Mock user input
        inputs = iter([
            "https://test.openai.azure.com",  # endpoint
            "test-api-key",  # api_key
            "whisper-test",  # transcription_deployment
            "gpt-4-test",  # summary_deployment
        ])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        # Mock httpx to avoid actual network calls
        with mock.patch("any2summary.cli._HTTPX_AVAILABLE", False):
            exit_code = _run_init_command([])

        assert exit_code == 0
        env_file = tmp_path / ".env"
        assert env_file.exists()

        content = env_file.read_text()
        assert "AZURE_OPENAI_ENDPOINT=https://test.openai.azure.com" in content
        assert "AZURE_OPENAI_API_KEY=test-api-key" in content
        assert "AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT=whisper-test" in content
        assert "AZURE_OPENAI_SUMMARY_DEPLOYMENT=gpt-4-test" in content

    def test_init_prompts_before_overwrite(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that init asks before overwriting existing .env."""
        monkeypatch.chdir(tmp_path)

        # Create existing .env
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=value")

        # User declines overwrite
        inputs = iter(["n"])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        exit_code = _run_init_command([])

        assert exit_code == 0
        # Original file should be preserved
        assert env_file.read_text() == "EXISTING=value"

    def test_init_force_overwrites_without_prompt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that --force skips overwrite prompt."""
        monkeypatch.chdir(tmp_path)

        # Create existing .env
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING=value")

        # Mock user input for configuration
        inputs = iter([
            "https://new.openai.azure.com",
            "new-key",
            "",  # use default transcription
            "",  # use default summary
        ])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        with mock.patch("any2summary.cli._HTTPX_AVAILABLE", False):
            exit_code = _run_init_command(["--force"])

        assert exit_code == 0
        content = env_file.read_text()
        assert "https://new.openai.azure.com" in content
        assert "EXISTING=value" not in content

    def test_init_uses_defaults_for_empty_input(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that empty input uses default values."""
        monkeypatch.chdir(tmp_path)

        # All empty inputs
        inputs = iter(["", "", "", ""])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        with mock.patch("any2summary.cli._HTTPX_AVAILABLE", False):
            exit_code = _run_init_command([])

        assert exit_code == 0
        env_file = tmp_path / ".env"
        content = env_file.read_text()

        # Should have default deployment names
        assert "AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT=whisper" in content
        assert "AZURE_OPENAI_SUMMARY_DEPLOYMENT=gpt-5-pro" in content

    def test_init_adds_https_prefix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify that init adds https:// to endpoint if missing."""
        monkeypatch.chdir(tmp_path)

        inputs = iter([
            "test.openai.azure.com",  # without https://
            "key",
            "",
            "",
        ])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        with mock.patch("any2summary.cli._HTTPX_AVAILABLE", False):
            exit_code = _run_init_command([])

        assert exit_code == 0
        content = (tmp_path / ".env").read_text()
        assert "AZURE_OPENAI_ENDPOINT=https://test.openai.azure.com" in content

    def test_init_tests_connectivity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify that init tests Azure connectivity when credentials provided."""
        monkeypatch.chdir(tmp_path)

        inputs = iter([
            "https://test.openai.azure.com",
            "test-key",
            "",
            "",
        ])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        # Mock successful connectivity
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_client = mock.Mock()
        mock_client.get.return_value = mock_response

        with mock.patch("any2summary.cli._HTTPX_AVAILABLE", True):
            with mock.patch("any2summary.cli.httpx") as mock_httpx:
                mock_httpx.Client.return_value = mock_client
                exit_code = _run_init_command([])

        captured = capsys.readouterr()
        assert "连接成功" in captured.out or "验证" in captured.out

    def test_init_handles_connectivity_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify that init handles connectivity test failure gracefully."""
        monkeypatch.chdir(tmp_path)

        inputs = iter([
            "https://test.openai.azure.com",
            "test-key",
            "",
            "",
        ])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        # Mock connection failure
        with mock.patch("any2summary.cli._HTTPX_AVAILABLE", True):
            with mock.patch("any2summary.cli.httpx") as mock_httpx:
                mock_httpx.Client.return_value.get.side_effect = Exception("Connection error")
                exit_code = _run_init_command([])

        # Should still succeed (just warn about connectivity)
        assert exit_code == 0
        assert (tmp_path / ".env").exists()

    def test_init_shows_summary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify that init shows configuration summary."""
        monkeypatch.chdir(tmp_path)

        inputs = iter([
            "https://test.openai.azure.com",
            "secret-key",
            "whisper",
            "gpt-4",
        ])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        with mock.patch("any2summary.cli._HTTPX_AVAILABLE", False):
            exit_code = _run_init_command([])

        captured = capsys.readouterr()
        assert "配置摘要" in captured.out or "summary" in captured.out.lower()
        # API key should be masked
        assert "secret-key" not in captured.out
        assert "****" in captured.out or "********" in captured.out

    def test_init_shows_doctor_tip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify that init suggests running doctor command."""
        monkeypatch.chdir(tmp_path)

        inputs = iter(["", "", "", ""])
        monkeypatch.setattr("builtins.input", lambda prompt: next(inputs))

        with mock.patch("any2summary.cli._HTTPX_AVAILABLE", False):
            exit_code = _run_init_command([])

        captured = capsys.readouterr()
        assert "doctor" in captured.out
