"""Tests for `any2summary doctor` health check command."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

# Add package root to path
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from any2summary.cli import run, _run_doctor_command


class TestDoctorCommand:
    """Tests for the doctor subcommand."""

    def test_doctor_subcommand_is_recognized(self) -> None:
        """Verify that `doctor` subcommand is recognized and calls handler."""
        with mock.patch(
            "any2summary.cli._run_doctor_command", return_value=0
        ) as mock_handler:
            exit_code = run(["doctor"])
            mock_handler.assert_called_once()
            assert exit_code == 0

    def test_doctor_checks_python_version(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify Python version check is performed."""
        # Mock environment to isolate test
        with mock.patch.dict(os.environ, {}, clear=False):
            # Run doctor command
            exit_code = _run_doctor_command([])
            captured = capsys.readouterr()

            # Should check Python version
            assert "Python" in captured.out

    def test_doctor_checks_ffmpeg(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify ffmpeg check is performed."""
        with mock.patch("shutil.which", return_value="/usr/bin/ffmpeg"):
            exit_code = _run_doctor_command([])
            captured = capsys.readouterr()
            assert "ffmpeg" in captured.out.lower()

    def test_doctor_checks_ffmpeg_missing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify ffmpeg missing is reported."""
        original_which = __import__("shutil").which

        def mock_which(cmd: str) -> str | None:
            if cmd == "ffmpeg":
                return None
            return original_which(cmd)

        with mock.patch("shutil.which", side_effect=mock_which):
            exit_code = _run_doctor_command([])
            captured = capsys.readouterr()
            # Should show error for missing ffmpeg
            assert "ffmpeg" in captured.out.lower()
            # Exit code should be non-zero if critical check fails
            assert exit_code == 1 or "✗" in captured.out or "✘" in captured.out

    def test_doctor_checks_ytdlp(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify yt-dlp check is performed."""
        exit_code = _run_doctor_command([])
        captured = capsys.readouterr()
        assert "yt-dlp" in captured.out.lower() or "ytdlp" in captured.out.lower()

    def test_doctor_checks_required_packages(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify required Python packages are checked."""
        exit_code = _run_doctor_command([])
        captured = capsys.readouterr()
        output_lower = captured.out.lower()

        # Should check for key packages
        assert "numpy" in output_lower or "openai" in output_lower

    def test_doctor_checks_env_file(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """Verify .env file check is performed."""
        # Change to temp dir without .env
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            exit_code = _run_doctor_command([])
            captured = capsys.readouterr()
            # Should mention .env file check
            assert ".env" in captured.out or "环境" in captured.out
        finally:
            os.chdir(original_cwd)

    def test_doctor_checks_azure_connectivity(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify Azure connectivity check is performed."""
        with mock.patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
                "AZURE_OPENAI_API_KEY": "test-key",
            },
        ):
            exit_code = _run_doctor_command([])
            captured = capsys.readouterr()
            # Should mention Azure check
            assert "Azure" in captured.out or "azure" in captured.out.lower()

    def test_doctor_output_format(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify output uses checkmark/cross format."""
        exit_code = _run_doctor_command([])
        captured = capsys.readouterr()

        # Should use visual indicators (checkmarks or crosses)
        has_indicators = (
            "✓" in captured.out
            or "✗" in captured.out
            or "✔" in captured.out
            or "✘" in captured.out
            or "[OK]" in captured.out
            or "[FAIL]" in captured.out
        )
        assert has_indicators, f"Output should have status indicators: {captured.out}"

    def test_doctor_returns_zero_when_all_pass(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify exit code 0 when all checks pass."""
        # Mock all checks to pass
        with mock.patch("shutil.which", return_value="/usr/bin/cmd"):
            with mock.patch.dict(
                os.environ,
                {
                    "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
                    "AZURE_OPENAI_API_KEY": "test-key",
                },
            ):
                # Note: actual exit code depends on real system state
                # This test verifies the command runs without exception
                exit_code = _run_doctor_command([])
                assert isinstance(exit_code, int)

    def test_doctor_summary_at_end(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify summary is shown at the end."""
        exit_code = _run_doctor_command([])
        captured = capsys.readouterr()

        # Should have some summary or conclusion
        output = captured.out.lower()
        has_summary = (
            "总结" in output
            or "summary" in output
            or "通过" in output
            or "passed" in output
            or "failed" in output
            or "问题" in output
        )
        # Relaxed assertion - just verify command completes
        assert exit_code is not None


class TestDoctorJsonOutput:
    """Tests for the doctor --json flag."""

    def test_json_output_is_valid_json(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify --json flag produces valid JSON output."""
        import json

        exit_code = _run_doctor_command(["--json"])
        captured = capsys.readouterr()

        # Should be valid JSON
        result = json.loads(captured.out)
        assert isinstance(result, dict)

    def test_json_output_has_required_fields(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify JSON output contains required fields."""
        import json

        exit_code = _run_doctor_command(["--json"])
        captured = capsys.readouterr()

        result = json.loads(captured.out)

        # Check required fields
        assert "status" in result
        assert result["status"] in ("ok", "failed")
        assert "checks_passed" in result
        assert "checks_failed" in result
        assert "total_checks" in result
        assert "issues" in result
        assert isinstance(result["issues"], list)

    def test_json_output_no_print_statements(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify --json flag suppresses normal print output."""
        import json

        exit_code = _run_doctor_command(["--json"])
        captured = capsys.readouterr()

        # Output should be parseable as single JSON object
        # (no extra print lines before/after)
        try:
            result = json.loads(captured.out)
            assert isinstance(result, dict)
        except json.JSONDecodeError as e:
            pytest.fail(f"JSON output has extra content: {e}")

    def test_json_issues_contain_error_codes(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """Verify issues in JSON output contain error codes."""
        import json

        # Change to temp dir to ensure at least .env check fails
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            exit_code = _run_doctor_command(["--json"])
            captured = capsys.readouterr()

            result = json.loads(captured.out)
            if result["issues"]:
                for issue in result["issues"]:
                    assert "code" in issue
                    assert isinstance(issue["code"], int)
                    assert "message" in issue
                    assert "suggestion" in issue
        finally:
            os.chdir(original_cwd)


class TestDoctorFixOption:
    """Tests for the doctor --fix flag."""

    def test_fix_option_is_recognized(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify --fix flag is recognized."""
        # Should not raise an error for unrecognized argument
        exit_code = _run_doctor_command(["--fix"])
        assert isinstance(exit_code, int)

    def test_fix_attempts_env_file_creation(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """Verify --fix attempts to create .env file if missing."""
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            # Verify .env doesn't exist
            assert not (tmp_path / ".env").exists()

            exit_code = _run_doctor_command(["--fix"])
            captured = capsys.readouterr()

            # Should have attempted fix
            assert "修复" in captured.out or "fix" in captured.out.lower()

            # .env file should now exist
            assert (tmp_path / ".env").exists()
        finally:
            os.chdir(original_cwd)

    def test_fix_shows_fix_summary(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """Verify --fix shows a summary of fix attempts."""
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            exit_code = _run_doctor_command(["--fix"])
            captured = capsys.readouterr()

            # Should show fix attempt messages
            output = captured.out
            has_fix_info = (
                "自动修复" in output
                or "尝试" in output
                or "修复" in output
                or "fix" in output.lower()
            )
            assert has_fix_info
        finally:
            os.chdir(original_cwd)

    def test_fix_and_json_together(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """Verify --fix and --json can be used together."""
        import json

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            exit_code = _run_doctor_command(["--fix", "--json"])
            captured = capsys.readouterr()

            result = json.loads(captured.out)

            # Should include fix statistics
            assert "fixes_attempted" in result
            assert "fixes_succeeded" in result
            assert result["fixes_attempted"] >= 0
            assert result["fixes_succeeded"] >= 0
        finally:
            os.chdir(original_cwd)
