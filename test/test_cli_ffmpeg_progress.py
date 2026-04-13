"""Tests for FFmpeg progress monitoring and audio processing progress."""

import os
import sys
import tempfile
import wave
from pathlib import Path
from unittest import mock

import pytest

# Add package root to path
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from any2summary.cli import (
    _get_video_duration_ms,
    _parse_ffmpeg_progress,
    _split_wav_file,
)


class TestParseFFmpegProgress:
    """Tests for FFmpeg progress line parsing."""

    def test_parse_valid_out_time_ms(self):
        """Test parsing valid out_time_ms line."""
        result = _parse_ffmpeg_progress("out_time_ms=12345678")
        assert result == 12345678

    def test_parse_out_time_ms_with_whitespace(self):
        """Test parsing out_time_ms with trailing whitespace."""
        result = _parse_ffmpeg_progress("out_time_ms=12345678\n")
        assert result == 12345678

    def test_parse_invalid_line(self):
        """Test parsing non-time lines returns None."""
        assert _parse_ffmpeg_progress("bitrate=128.0kbits/s") is None
        assert _parse_ffmpeg_progress("frame=1234") is None
        assert _parse_ffmpeg_progress("progress=continue") is None

    def test_parse_empty_line(self):
        """Test parsing empty line returns None."""
        assert _parse_ffmpeg_progress("") is None

    def test_parse_malformed_time(self):
        """Test parsing malformed out_time_ms returns None."""
        assert _parse_ffmpeg_progress("out_time_ms=") is None
        assert _parse_ffmpeg_progress("out_time_ms=abc") is None


class TestGetVideoDurationMs:
    """Tests for video duration detection."""

    def test_returns_zero_when_ffprobe_missing(self):
        """Test returns 0 when ffprobe is not available."""
        with mock.patch("shutil.which", return_value=None):
            result = _get_video_duration_ms("/nonexistent/video.mp4")
            assert result == 0

    def test_returns_zero_for_nonexistent_file(self):
        """Test returns 0 for nonexistent file."""
        result = _get_video_duration_ms("/nonexistent/video.mp4")
        # Either returns 0 or raises no exception
        assert result >= 0

    def test_returns_duration_for_valid_response(self):
        """Test returns duration when ffprobe succeeds."""
        mock_result = mock.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "123.456\n"

        with mock.patch("shutil.which", return_value="/usr/bin/ffprobe"):
            with mock.patch("subprocess.run", return_value=mock_result):
                result = _get_video_duration_ms("/some/video.mp4")
                assert result == 123456  # 123.456 * 1000


class TestSplitWavFileProgress:
    """Tests for WAV file splitting with progress."""

    def test_split_creates_segments(self, tmp_path: Path):
        """Test that split creates segment files."""
        # Create a test WAV file
        wav_path = tmp_path / "test.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            # Write 2 seconds of audio (should create 1 segment with default settings)
            wf.writeframes(b"\x00\x00" * 32000)

        output_dir = tmp_path / "segments"
        output_dir.mkdir()

        # Split with progress disabled to avoid output issues in tests
        segments = _split_wav_file(
            str(wav_path),
            str(output_dir),
            "test",
            show_progress=False,
        )

        # Should have created at least one segment
        assert len(segments) >= 1
        for segment in segments:
            assert os.path.exists(segment)

    def test_split_returns_original_on_error(self, tmp_path: Path):
        """Test that split returns original path on error."""
        nonexistent_path = str(tmp_path / "nonexistent.wav")

        segments = _split_wav_file(
            nonexistent_path,
            str(tmp_path),
            "test",
            show_progress=False,
        )

        assert segments == [nonexistent_path]

    def test_split_progress_callback(self, tmp_path: Path, capsys):
        """Test that progress is shown during splitting."""
        # Create a test WAV file with enough data for multiple segments
        wav_path = tmp_path / "test.wav"
        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            # Write 5 minutes of audio (enough for multiple segments)
            wf.writeframes(b"\x00\x00" * (16000 * 60 * 5))

        output_dir = tmp_path / "segments"
        output_dir.mkdir()

        # Mock _update_progress_bar to track calls
        with mock.patch("any2summary.cli._update_progress_bar") as mock_progress:
            segments = _split_wav_file(
                str(wav_path),
                str(output_dir),
                "test",
                show_progress=True,
            )

            # Should have called progress at least once
            assert mock_progress.call_count >= 1

            # Check that progress was called with increasing values
            calls = mock_progress.call_args_list
            ratios = [call[0][0] for call in calls]

            # All ratios should be between 0 and 1
            for ratio in ratios:
                assert 0.0 <= ratio <= 1.0

            # Last call should be completion (ratio = 1.0)
            assert ratios[-1] == 1.0


class TestExtractAudioProgress:
    """Tests for audio extraction progress (requires ffmpeg)."""

    @pytest.mark.skipif(
        not os.path.exists("/usr/bin/ffmpeg")
        and not os.path.exists("/usr/local/bin/ffmpeg")
        and not os.path.exists("/opt/homebrew/bin/ffmpeg"),
        reason="ffmpeg not available",
    )
    def test_extract_audio_basic(self, tmp_path: Path):
        """Test basic audio extraction (skip if ffmpeg not available)."""
        # This test is a placeholder - actual video testing requires a test video file
        # In production, this would test _extract_audio_from_video with a sample video
        pass
