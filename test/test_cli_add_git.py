"""Tests for `any2summary add_git` git diff statistics command."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Add package root to path
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from any2summary.cli import (
    run,
    _run_add_git_command,
    _is_git_repository,
    _parse_git_diff,
    _extract_line_ranges,
    FileDiffInfo,
    GitDiffSummary,
)


class TestAddGitSubcommand:
    """Tests for the add_git subcommand recognition."""

    def test_add_git_subcommand_is_recognized(self) -> None:
        """Verify that `add_git` subcommand is recognized and calls handler."""
        with mock.patch(
            "any2summary.cli._run_add_git_command", return_value=0
        ) as mock_handler:
            exit_code = run(["add_git"])
            mock_handler.assert_called_once()
            assert exit_code == 0

    def test_add_git_with_dry_run_flag(self) -> None:
        """Verify --dry-run flag is passed correctly."""
        with mock.patch(
            "any2summary.cli._run_add_git_command", return_value=0
        ) as mock_handler:
            exit_code = run(["add_git", "--dry-run"])
            mock_handler.assert_called_once_with(["--dry-run"])
            assert exit_code == 0

    def test_add_git_with_no_ai_flag(self) -> None:
        """Verify --no-ai flag is passed correctly."""
        with mock.patch(
            "any2summary.cli._run_add_git_command", return_value=0
        ) as mock_handler:
            exit_code = run(["add_git", "--no-ai"])
            mock_handler.assert_called_once_with(["--no-ai"])
            assert exit_code == 0

    def test_add_git_with_staged_flag(self) -> None:
        """Verify --staged flag is passed correctly."""
        with mock.patch(
            "any2summary.cli._run_add_git_command", return_value=0
        ) as mock_handler:
            exit_code = run(["add_git", "--staged"])
            mock_handler.assert_called_once_with(["--staged"])
            assert exit_code == 0


class TestIsGitRepository:
    """Tests for _is_git_repository function."""

    def test_is_git_repository_in_valid_repo(self) -> None:
        """Verify returns True when in a git repository."""
        # The test suite runs in a git repo
        result = _is_git_repository()
        assert result is True

    def test_is_git_repository_outside_repo(self, tmp_path: Path) -> None:
        """Verify returns False when not in a git repository."""
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = _is_git_repository()
            assert result is False
        finally:
            os.chdir(original_cwd)

    def test_is_git_repository_handles_error(self) -> None:
        """Verify handles subprocess errors gracefully."""
        with mock.patch(
            "subprocess.run", side_effect=Exception("git not found")
        ):
            result = _is_git_repository()
            assert result is False


class TestExtractLineRanges:
    """Tests for _extract_line_ranges function."""

    def test_extract_single_line_change(self) -> None:
        """Verify extraction of single line change."""
        diff_content = "@@ -10,0 +11,1 @@\n+new line"
        result = _extract_line_ranges(diff_content)
        assert result == [(11, 11)]

    def test_extract_multiple_line_change(self) -> None:
        """Verify extraction of multi-line change."""
        diff_content = "@@ -10,5 +10,10 @@\n+new lines"
        result = _extract_line_ranges(diff_content)
        assert result == [(10, 19)]

    def test_extract_multiple_hunks(self) -> None:
        """Verify extraction of multiple hunks."""
        diff_content = """@@ -10,3 +10,5 @@
+changes
@@ -50,2 +52,4 @@
+more changes"""
        result = _extract_line_ranges(diff_content)
        assert result == [(10, 14), (52, 55)]

    def test_extract_empty_diff(self) -> None:
        """Verify empty diff returns empty list."""
        result = _extract_line_ranges("")
        assert result == []

    def test_extract_no_hunk_headers(self) -> None:
        """Verify diff without hunk headers returns empty list."""
        diff_content = "diff --git a/file.py b/file.py\nsome content"
        result = _extract_line_ranges(diff_content)
        assert result == []


class TestParseGitDiff:
    """Tests for _parse_git_diff function."""

    def test_parse_empty_diff(self) -> None:
        """Verify parsing when no changes exist."""
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=0, stdout="", stderr=""
            )
            result = _parse_git_diff()
            assert result.files == []
            assert result.total_additions == 0
            assert result.total_deletions == 0

    def test_parse_single_file_modification(self) -> None:
        """Verify parsing a single modified file."""
        numstat_output = "10\t5\tsrc/main.py"
        status_output = "M\tsrc/main.py"
        diff_output = "@@ -1,5 +1,10 @@\n+new code"

        def mock_run_side_effect(cmd, **kwargs):
            if "--numstat" in cmd:
                return mock.Mock(returncode=0, stdout=numstat_output, stderr="")
            elif "--name-status" in cmd:
                return mock.Mock(returncode=0, stdout=status_output, stderr="")
            else:
                return mock.Mock(returncode=0, stdout=diff_output, stderr="")

        with mock.patch("subprocess.run", side_effect=mock_run_side_effect):
            result = _parse_git_diff()
            assert len(result.files) == 1
            assert result.files[0].filepath == "src/main.py"
            assert result.files[0].status == "M"
            assert result.files[0].additions == 10
            assert result.files[0].deletions == 5
            assert result.total_additions == 10
            assert result.total_deletions == 5

    def test_parse_multiple_files(self) -> None:
        """Verify parsing multiple changed files."""
        numstat_output = "10\t5\tsrc/main.py\n20\t0\tsrc/new.py"
        status_output = "M\tsrc/main.py\nA\tsrc/new.py"
        diff_output = "@@ -1,5 +1,10 @@\n+new code"

        def mock_run_side_effect(cmd, **kwargs):
            if "--numstat" in cmd:
                return mock.Mock(returncode=0, stdout=numstat_output, stderr="")
            elif "--name-status" in cmd:
                return mock.Mock(returncode=0, stdout=status_output, stderr="")
            else:
                return mock.Mock(returncode=0, stdout=diff_output, stderr="")

        with mock.patch("subprocess.run", side_effect=mock_run_side_effect):
            result = _parse_git_diff()
            assert len(result.files) == 2
            assert result.total_additions == 30
            assert result.total_deletions == 5

    def test_parse_binary_file(self) -> None:
        """Verify parsing binary file (marked as - in numstat)."""
        numstat_output = "-\t-\timage.png"
        status_output = "A\timage.png"

        def mock_run_side_effect(cmd, **kwargs):
            if "--numstat" in cmd:
                return mock.Mock(returncode=0, stdout=numstat_output, stderr="")
            elif "--name-status" in cmd:
                return mock.Mock(returncode=0, stdout=status_output, stderr="")
            else:
                return mock.Mock(returncode=0, stdout="", stderr="")

        with mock.patch("subprocess.run", side_effect=mock_run_side_effect):
            result = _parse_git_diff()
            assert len(result.files) == 1
            assert result.files[0].additions == 0
            assert result.files[0].deletions == 0

    def test_parse_staged_changes(self) -> None:
        """Verify --cached flag is passed when staged=True."""
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.Mock(
                returncode=0, stdout="", stderr=""
            )
            _parse_git_diff(staged=True)
            # Verify --cached was passed in the numstat call
            calls = mock_run.call_args_list
            assert any("--cached" in str(call) for call in calls)

    def test_parse_handles_timeout(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify timeout is handled gracefully."""
        with mock.patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired("git", 30)
        ):
            result = _parse_git_diff()
            assert result.files == []
            captured = capsys.readouterr()
            assert "超时" in captured.err


class TestRunAddGitCommand:
    """Tests for _run_add_git_command function."""

    def test_non_git_repository_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify error when not in git repository."""
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            exit_code = _run_add_git_command([])
            assert exit_code == 1
            captured = capsys.readouterr()
            assert "git 仓库" in captured.err or "git repository" in captured.err.lower()
        finally:
            os.chdir(original_cwd)

    def test_no_changes_message(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify message when no changes detected."""
        with mock.patch(
            "any2summary.cli._is_git_repository", return_value=True
        ):
            with mock.patch(
                "any2summary.cli._parse_git_diff",
                return_value=GitDiffSummary(),
            ):
                exit_code = _run_add_git_command(["--no-ai"])
                assert exit_code == 0
                captured = capsys.readouterr()
                assert "没有检测到" in captured.out or "no changes" in captured.out.lower()

    def test_dry_run_skips_git_add(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify --dry-run does not execute git add."""
        summary = GitDiffSummary(
            files=[
                FileDiffInfo(
                    filepath="test.py",
                    status="M",
                    additions=10,
                    deletions=5,
                    line_ranges=[(1, 10)],
                    diff_content="",
                )
            ],
            total_additions=10,
            total_deletions=5,
        )

        with mock.patch(
            "any2summary.cli._is_git_repository", return_value=True
        ):
            with mock.patch(
                "any2summary.cli._parse_git_diff", return_value=summary
            ):
                with mock.patch("subprocess.run") as mock_run:
                    exit_code = _run_add_git_command(["--dry-run", "--no-ai"])
                    # git add should not be called
                    git_add_calls = [
                        c for c in mock_run.call_args_list
                        if "add" in str(c) and "git" in str(c)
                    ]
                    assert len(git_add_calls) == 0
                    assert exit_code == 0
                    captured = capsys.readouterr()
                    assert "dry-run" in captured.out.lower()

    def test_no_ai_flag_skips_ai_call(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify --no-ai skips AI description generation."""
        summary = GitDiffSummary(
            files=[
                FileDiffInfo(
                    filepath="test.py",
                    status="M",
                    additions=10,
                    deletions=5,
                    line_ranges=[],
                    diff_content="",
                )
            ],
            total_additions=10,
            total_deletions=5,
        )

        with mock.patch(
            "any2summary.cli._is_git_repository", return_value=True
        ):
            with mock.patch(
                "any2summary.cli._parse_git_diff", return_value=summary
            ):
                with mock.patch(
                    "any2summary.cli._generate_change_description_haiku"
                ) as mock_ai:
                    with mock.patch("subprocess.run") as mock_run:
                        mock_run.return_value = mock.Mock(returncode=0, stderr="")
                        exit_code = _run_add_git_command(["--no-ai"])
                        # AI function should not be called
                        mock_ai.assert_not_called()
                        assert exit_code == 0

    def test_output_format(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify output format matches expected structure."""
        summary = GitDiffSummary(
            files=[
                FileDiffInfo(
                    filepath="any2summary/cli.py",
                    status="M",
                    additions=45,
                    deletions=12,
                    line_ranges=[(686, 730), (947, 980)],
                    diff_content="",
                ),
                FileDiffInfo(
                    filepath="test/test_add_git.py",
                    status="A",
                    additions=120,
                    deletions=0,
                    line_ranges=[(1, 120)],
                    diff_content="",
                ),
            ],
            total_additions=165,
            total_deletions=12,
        )

        with mock.patch(
            "any2summary.cli._is_git_repository", return_value=True
        ):
            with mock.patch(
                "any2summary.cli._parse_git_diff", return_value=summary
            ):
                with mock.patch("subprocess.run") as mock_run:
                    mock_run.return_value = mock.Mock(returncode=0, stderr="")
                    exit_code = _run_add_git_command(["--no-ai"])
                    captured = capsys.readouterr()

                    # Verify structure
                    assert "Git 变更统计" in captured.out
                    assert "修改的文件" in captured.out
                    assert "any2summary/cli.py" in captured.out
                    assert "test/test_add_git.py" in captured.out
                    assert "+45" in captured.out
                    assert "-12" in captured.out
                    assert "总计" in captured.out
                    assert "+165" in captured.out
                    assert "git add" in captured.out.lower()

    def test_git_add_failure_returns_error(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify error code when git add fails."""
        summary = GitDiffSummary(
            files=[
                FileDiffInfo(
                    filepath="test.py",
                    status="M",
                    additions=10,
                    deletions=5,
                    line_ranges=[],
                    diff_content="",
                )
            ],
            total_additions=10,
            total_deletions=5,
        )

        with mock.patch(
            "any2summary.cli._is_git_repository", return_value=True
        ):
            with mock.patch(
                "any2summary.cli._parse_git_diff", return_value=summary
            ):
                with mock.patch("subprocess.run") as mock_run:
                    mock_run.return_value = mock.Mock(
                        returncode=1, stderr="fatal: error"
                    )
                    exit_code = _run_add_git_command(["--no-ai"])
                    assert exit_code == 1
                    captured = capsys.readouterr()
                    assert "git add 失败" in captured.err or "error" in captured.err.lower()


class TestAIDescriptionFallback:
    """Tests for AI description fallback behavior."""

    def test_ai_unavailable_shows_warning(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify warning when boto3 is not available."""
        summary = GitDiffSummary(
            files=[
                FileDiffInfo(
                    filepath="test.py",
                    status="M",
                    additions=10,
                    deletions=5,
                    line_ranges=[],
                    diff_content="",
                )
            ],
            total_additions=10,
            total_deletions=5,
        )

        with mock.patch(
            "any2summary.cli._is_git_repository", return_value=True
        ):
            with mock.patch(
                "any2summary.cli._parse_git_diff", return_value=summary
            ):
                with mock.patch("any2summary.cli._BOTO3_AVAILABLE", False):
                    with mock.patch("subprocess.run") as mock_run:
                        mock_run.return_value = mock.Mock(returncode=0, stderr="")
                        exit_code = _run_add_git_command([])
                        assert exit_code == 0
                        captured = capsys.readouterr()
                        assert "boto3" in captured.err or "未安装" in captured.err

    def test_ai_failure_shows_warning(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify warning when AI call fails."""
        summary = GitDiffSummary(
            files=[
                FileDiffInfo(
                    filepath="test.py",
                    status="M",
                    additions=10,
                    deletions=5,
                    line_ranges=[],
                    diff_content="",
                )
            ],
            total_additions=10,
            total_deletions=5,
        )

        with mock.patch(
            "any2summary.cli._is_git_repository", return_value=True
        ):
            with mock.patch(
                "any2summary.cli._parse_git_diff", return_value=summary
            ):
                with mock.patch("any2summary.cli._BOTO3_AVAILABLE", True):
                    with mock.patch(
                        "any2summary.cli._generate_change_description_haiku",
                        return_value=None,
                    ):
                        with mock.patch("subprocess.run") as mock_run:
                            mock_run.return_value = mock.Mock(returncode=0, stderr="")
                            exit_code = _run_add_git_command([])
                            assert exit_code == 0
                            captured = capsys.readouterr()
                            assert "AI" in captured.err or "凭据" in captured.err


class TestDataClasses:
    """Tests for data class structures."""

    def test_file_diff_info_creation(self) -> None:
        """Verify FileDiffInfo can be created with all fields."""
        info = FileDiffInfo(
            filepath="test.py",
            status="M",
            additions=10,
            deletions=5,
            line_ranges=[(1, 10), (20, 30)],
            diff_content="diff content",
        )
        assert info.filepath == "test.py"
        assert info.status == "M"
        assert info.additions == 10
        assert info.deletions == 5
        assert info.line_ranges == [(1, 10), (20, 30)]
        assert info.diff_content == "diff content"

    def test_file_diff_info_defaults(self) -> None:
        """Verify FileDiffInfo defaults."""
        info = FileDiffInfo(
            filepath="test.py",
            status="A",
            additions=100,
            deletions=0,
        )
        assert info.line_ranges == []
        assert info.diff_content == ""

    def test_git_diff_summary_creation(self) -> None:
        """Verify GitDiffSummary can be created."""
        summary = GitDiffSummary(
            files=[
                FileDiffInfo("a.py", "M", 10, 5),
                FileDiffInfo("b.py", "A", 20, 0),
            ],
            total_additions=30,
            total_deletions=5,
        )
        assert len(summary.files) == 2
        assert summary.total_additions == 30
        assert summary.total_deletions == 5

    def test_git_diff_summary_defaults(self) -> None:
        """Verify GitDiffSummary defaults."""
        summary = GitDiffSummary()
        assert summary.files == []
        assert summary.total_additions == 0
        assert summary.total_deletions == 0
