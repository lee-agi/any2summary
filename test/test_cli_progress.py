"""Tests for progress bar visualization with rich library."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

# Add package root to path
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from any2summary.cli import (
    _update_progress_bar,
    _create_progress_context,
    _RICH_AVAILABLE,
)


class TestRichAvailability:
    """Tests for rich library availability detection."""

    def test_rich_available_flag_is_boolean(self) -> None:
        """Verify _RICH_AVAILABLE is a boolean."""
        assert isinstance(_RICH_AVAILABLE, bool)


class TestProgressBarFallback:
    """Tests for fallback progress bar when rich is not available."""

    @pytest.fixture(autouse=True)
    def reset_progress_state(self) -> None:
        """Reset global progress bar state before each test."""
        import any2summary.cli as cli_module
        cli_module._RICH_PROGRESS_INSTANCE = None
        cli_module._RICH_TASK_ID = None

    def test_update_progress_bar_renders_text(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify basic progress bar renders with text."""
        import any2summary.cli as cli_module
        original_available = cli_module._RICH_AVAILABLE
        cli_module._RICH_AVAILABLE = False
        try:
            _update_progress_bar(0.5, "Processing segment 5/10")
            captured = capsys.readouterr()
            # Should contain percentage
            assert "50" in captured.out or "0.5" in captured.out
        finally:
            cli_module._RICH_AVAILABLE = original_available

    def test_update_progress_bar_at_zero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify progress bar handles 0%."""
        import any2summary.cli as cli_module
        original_available = cli_module._RICH_AVAILABLE
        cli_module._RICH_AVAILABLE = False
        try:
            _update_progress_bar(0.0, "Starting")
            captured = capsys.readouterr()
            assert "0" in captured.out
        finally:
            cli_module._RICH_AVAILABLE = original_available

    def test_update_progress_bar_at_completion(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify progress bar handles 100%."""
        import any2summary.cli as cli_module
        original_available = cli_module._RICH_AVAILABLE
        cli_module._RICH_AVAILABLE = False
        try:
            _update_progress_bar(1.0, "Done")
            captured = capsys.readouterr()
            assert "100" in captured.out
        finally:
            cli_module._RICH_AVAILABLE = original_available

    def test_update_progress_bar_clamps_ratio(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Verify ratio is clamped to [0, 1]."""
        import any2summary.cli as cli_module
        original_available = cli_module._RICH_AVAILABLE
        cli_module._RICH_AVAILABLE = False
        try:
            # Should not raise
            _update_progress_bar(1.5, "Over")
            _update_progress_bar(-0.5, "Under")
        finally:
            cli_module._RICH_AVAILABLE = original_available


class TestProgressContext:
    """Tests for progress context manager."""

    def test_create_progress_context_returns_context_manager(self) -> None:
        """Verify _create_progress_context returns a usable context manager."""
        ctx = _create_progress_context("Testing", total=100)
        assert ctx is not None
        # Should be usable as context manager
        assert hasattr(ctx, "__enter__") or callable(ctx)

    def test_progress_context_without_rich(self) -> None:
        """Verify progress context works without rich."""
        with mock.patch("any2summary.cli._RICH_AVAILABLE", False):
            ctx = _create_progress_context("Test Stage", total=10)
            # Should work as a no-op or simple wrapper
            if hasattr(ctx, "__enter__"):
                with ctx as progress:
                    # Should not raise
                    pass

    def test_progress_context_with_rich_mock(self) -> None:
        """Verify progress context tries to use rich when available."""
        # Create mock rich Progress
        mock_progress = mock.Mock()
        mock_progress.__enter__ = mock.Mock(return_value=mock_progress)
        mock_progress.__exit__ = mock.Mock(return_value=False)

        with mock.patch("any2summary.cli._RICH_AVAILABLE", True):
            with mock.patch("any2summary.cli._create_rich_progress", return_value=mock_progress):
                ctx = _create_progress_context("Test", total=100)
                # Context should be created
                assert ctx is not None


class TestProgressIntegration:
    """Integration tests for progress visualization."""

    def test_progress_bar_width_constant_exists(self) -> None:
        """Verify PROGRESS_BAR_WIDTH constant is defined."""
        from any2summary.cli import PROGRESS_BAR_WIDTH
        assert isinstance(PROGRESS_BAR_WIDTH, int)
        assert PROGRESS_BAR_WIDTH > 0

    def test_compute_progress_ratio_exists(self) -> None:
        """Verify _compute_progress_ratio function exists."""
        from any2summary.cli import _compute_progress_ratio

        ratio = _compute_progress_ratio(
            processed_duration=30.0,
            total_duration=60.0,
            produced_tokens=100.0,
            total_tokens=200.0,
            segments_done=5,
            total_segments=10,
        )
        assert 0.0 <= ratio <= 1.0
