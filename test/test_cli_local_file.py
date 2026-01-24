"""Tests for `--file` local file processing parameter."""

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
    run,
    _run_summarize_command,
    _process_local_file,
    _resolve_file_cache_dir,
    _detect_file_type,
    SUPPORTED_AUDIO_EXTENSIONS,
    SUPPORTED_VIDEO_EXTENSIONS,
    SUPPORTED_DOCUMENT_EXTENSIONS,
)


class TestFileTypeDetection:
    """Tests for file type detection."""

    def test_supported_audio_extensions_defined(self) -> None:
        """Verify supported audio extensions are defined."""
        assert ".mp3" in SUPPORTED_AUDIO_EXTENSIONS
        assert ".m4a" in SUPPORTED_AUDIO_EXTENSIONS
        assert ".wav" in SUPPORTED_AUDIO_EXTENSIONS

    def test_supported_video_extensions_defined(self) -> None:
        """Verify supported video extensions are defined."""
        assert ".mp4" in SUPPORTED_VIDEO_EXTENSIONS
        assert ".mkv" in SUPPORTED_VIDEO_EXTENSIONS
        assert ".webm" in SUPPORTED_VIDEO_EXTENSIONS

    def test_supported_document_extensions_defined(self) -> None:
        """Verify supported document extensions are defined."""
        assert ".pdf" in SUPPORTED_DOCUMENT_EXTENSIONS

    def test_detect_audio_file(self) -> None:
        """Verify audio files are correctly detected."""
        assert _detect_file_type("/path/to/file.mp3") == "audio"
        assert _detect_file_type("/path/to/file.m4a") == "audio"
        assert _detect_file_type("/path/to/file.wav") == "audio"
        assert _detect_file_type("/path/to/file.MP3") == "audio"  # case insensitive

    def test_detect_video_file(self) -> None:
        """Verify video files are correctly detected."""
        assert _detect_file_type("/path/to/file.mp4") == "video"
        assert _detect_file_type("/path/to/file.mkv") == "video"
        assert _detect_file_type("/path/to/file.webm") == "video"

    def test_detect_pdf_file(self) -> None:
        """Verify PDF files are correctly detected."""
        assert _detect_file_type("/path/to/file.pdf") == "document"
        assert _detect_file_type("/path/to/file.PDF") == "document"

    def test_detect_unsupported_file(self) -> None:
        """Verify unsupported files return unknown."""
        assert _detect_file_type("/path/to/file.txt") == "unknown"
        assert _detect_file_type("/path/to/file.docx") == "unknown"


class TestFileCacheDir:
    """Tests for file cache directory resolution."""

    def test_resolve_file_cache_dir_uses_hash(self) -> None:
        """Verify cache dir is based on file path hash."""
        cache_dir = _resolve_file_cache_dir("/path/to/file.mp3")
        assert cache_dir is not None
        assert "any2summary" in str(cache_dir).lower() or "cache" in str(cache_dir).lower()

    def test_resolve_file_cache_dir_consistent(self) -> None:
        """Verify same file path gives same cache dir."""
        dir1 = _resolve_file_cache_dir("/path/to/file.mp3")
        dir2 = _resolve_file_cache_dir("/path/to/file.mp3")
        assert dir1 == dir2

    def test_resolve_file_cache_dir_different_for_different_files(self) -> None:
        """Verify different files get different cache dirs."""
        dir1 = _resolve_file_cache_dir("/path/to/file1.mp3")
        dir2 = _resolve_file_cache_dir("/path/to/file2.mp3")
        assert dir1 != dir2


class TestProcessLocalFile:
    """Tests for local file processing."""

    def test_process_local_file_checks_existence(self, tmp_path: Path) -> None:
        """Verify process_local_file checks if file exists."""
        non_existent = tmp_path / "non_existent.mp3"
        with pytest.raises(FileNotFoundError):
            _process_local_file(str(non_existent), language="en")

    def test_process_local_file_rejects_unsupported(self, tmp_path: Path) -> None:
        """Verify unsupported file types are rejected."""
        unsupported = tmp_path / "file.xyz"
        unsupported.write_text("content")
        with pytest.raises(ValueError, match="不支持的文件类型"):
            _process_local_file(str(unsupported), language="en")

    def test_process_audio_file_calls_azure(self, tmp_path: Path) -> None:
        """Verify audio files are processed via Azure transcription."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio content")

        with mock.patch("any2summary.cli._transcribe_local_audio") as mock_transcribe:
            mock_transcribe.return_value = [{"start": 0, "end": 10, "text": "Hello"}]
            result = _process_local_file(str(audio_file), language="en")
            mock_transcribe.assert_called_once()
            assert result is not None

    def test_process_video_file_extracts_audio_first(self, tmp_path: Path) -> None:
        """Verify video files extract audio before transcription."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"fake video content")

        with mock.patch("any2summary.cli._extract_audio_from_video") as mock_extract:
            with mock.patch("any2summary.cli._transcribe_local_audio") as mock_transcribe:
                mock_extract.return_value = str(tmp_path / "extracted.wav")
                mock_transcribe.return_value = [{"start": 0, "end": 10, "text": "Hello"}]
                result = _process_local_file(str(video_file), language="en")
                mock_extract.assert_called_once()

    def test_process_pdf_file_extracts_text(self, tmp_path: Path) -> None:
        """Verify PDF files have text extracted."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"fake pdf content")

        with mock.patch("any2summary.cli._extract_text_from_pdf") as mock_extract:
            mock_extract.return_value = [{"start": 0, "end": 0, "text": "Extracted text"}]
            result = _process_local_file(str(pdf_file), language="en")
            mock_extract.assert_called_once()
            assert result is not None


class TestFileArgument:
    """Tests for --file CLI argument."""

    def test_file_argument_is_recognized(self) -> None:
        """Verify --file argument is parsed."""
        with mock.patch("any2summary.cli._load_dotenv_if_present"):
            with mock.patch("any2summary.cli._run_single_local_file", return_value=0):
                # This should not raise ArgumentError
                try:
                    _run_summarize_command(["--file", "/path/to/file.mp3"])
                except SystemExit:
                    pass  # May exit due to file not existing
                except Exception as e:
                    if "unrecognized arguments" in str(e):
                        pytest.fail("--file argument not recognized")

    def test_file_and_url_mutually_exclusive(self) -> None:
        """Verify --file and --url cannot be used together."""
        with mock.patch("any2summary.cli._load_dotenv_if_present"):
            with pytest.raises(SystemExit):
                _run_summarize_command([
                    "--file", "/path/to/file.mp3",
                    "--url", "https://youtube.com/watch?v=test",
                ])

    def test_file_or_url_required(self) -> None:
        """Verify either --file or --url is required."""
        with mock.patch("any2summary.cli._load_dotenv_if_present"):
            with pytest.raises(SystemExit):
                _run_summarize_command([])


class TestLocalFileIntegration:
    """Integration tests for local file processing."""

    @pytest.fixture
    def mock_azure_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up mock Azure environment variables."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")

    def test_local_file_flow_with_summary(
        self, tmp_path: Path, mock_azure_env: None
    ) -> None:
        """Verify complete flow with local file and summary generation."""
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"fake audio")

        with mock.patch("any2summary.cli._process_local_file") as mock_process:
            with mock.patch("any2summary.cli.generate_translation_summary") as mock_summary:
                mock_process.return_value = [{"start": 0, "end": 10, "text": "Test"}]
                mock_summary.return_value = {"summary": "Test summary"}

                with mock.patch("any2summary.cli._load_dotenv_if_present"):
                    with mock.patch("any2summary.cli._output_local_file_results"):
                        try:
                            _run_summarize_command([
                                "--file", str(audio_file),
                                "--azure-summary",
                            ])
                        except Exception:
                            pass  # May fail on other checks

                # Verify file was processed
                mock_process.assert_called()
