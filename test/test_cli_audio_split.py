"""针对音频切分工具函数的测试。"""

from __future__ import annotations

import wave
from pathlib import Path
import sys
import struct

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from any2summary import cli

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


def _write_silent_wav(path: Path, duration_seconds: float, sample_rate: int = 8000) -> None:
    """生成指定时长的静音 WAV 文件。"""

    total_frames = int(duration_seconds * sample_rate)
    if total_frames <= 0:
        total_frames = sample_rate
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * total_frames)


def _write_wav_with_pattern(
    path: Path,
    pattern: list[tuple[float, int]],
    sample_rate: int = 8000
) -> None:
    """生成带有特定音量模式的 WAV 文件。

    Args:
        path: 输出文件路径
        pattern: (duration_seconds, amplitude) 元组列表
                 amplitude 范围 [0, 32767]，0表示静音
        sample_rate: 采样率
    """
    frames = []

    for duration, amplitude in pattern:
        num_frames = int(duration * sample_rate)
        if amplitude == 0:
            # 静音
            frames.extend([0] * num_frames)
        else:
            # 简单的正弦波
            for i in range(num_frames):
                value = int(amplitude * (i % 100) / 100.0)
                frames.append(value)

    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)  # 16-bit
        handle.setframerate(sample_rate)
        # 将整数列表转换为字节
        frame_bytes = b''.join(struct.pack('<h', frame) for frame in frames)
        handle.writeframes(frame_bytes)


def test_ensure_audio_segments_splits_large_wav(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """超出阈值的音频应被自动切分成多个片段。"""

    original = tmp_path / "audio.wav"
    _write_silent_wav(original, duration_seconds=1.5, sample_rate=8000)

    monkeypatch.setattr(cli, "MAX_WAV_DURATION_SECONDS", 1.0)
    monkeypatch.setattr(cli, "MAX_WAV_SIZE_BYTES", 1024 * 1024)
    monkeypatch.setattr(cli, "AUDIO_SEGMENT_SECONDS", 0.6)

    segments = cli._ensure_audio_segments(str(original))

    assert len(segments) == 3
    for index, segment in enumerate(segments, start=1):
        path = Path(segment)
        assert path.exists()
        assert path.name == f"audio_part{index:03d}.wav"


def test_ensure_audio_segments_respects_azure_limit(tmp_path: Path) -> None:
    """超过 Azure 限制的音频应当按默认阈值切分。"""

    azure_safe_duration = cli.AUDIO_SEGMENT_SECONDS + 200.0
    wav_path = tmp_path / "long_audio.wav"
    _write_silent_wav(wav_path, duration_seconds=azure_safe_duration, sample_rate=10)

    segments = cli._ensure_audio_segments(str(wav_path))

    assert len(segments) >= 2
    for segment in segments:
        duration = cli._get_wav_duration(segment)
        assert duration <= cli.AUDIO_SEGMENT_SECONDS + 1.0


# ===== 智能边界检测测试 =====


@pytest.mark.skipif(not NUMPY_AVAILABLE, reason="numpy not installed")
def test_find_silence_boundary_detects_silence(tmp_path: Path) -> None:
    """Should find silence boundary near target point."""

    # Create audio with pattern: 10s audio, 2s silence, 10s audio
    pattern = [
        (10.0, 5000),   # 10 seconds of audio
        (2.0, 0),       # 2 seconds of silence
        (10.0, 5000),   # 10 seconds of audio
    ]

    wav_path = tmp_path / "test_audio.wav"
    _write_wav_with_pattern(wav_path, pattern, sample_rate=8000)

    # Target at 11 seconds (middle of silence), window ±5 seconds
    boundary = cli._find_silence_boundary(str(wav_path), target_seconds=11.0, window_seconds=5.0)

    # Should find silence around 10-12 seconds
    assert 10.0 <= boundary <= 12.0


@pytest.mark.skipif(not NUMPY_AVAILABLE, reason="numpy not installed")
def test_find_silence_boundary_prefers_longest_silence(tmp_path: Path) -> None:
    """Should prefer longest silence in window."""

    # Pattern: 5s audio, 0.5s silence, 5s audio, 2s silence, 5s audio
    pattern = [
        (5.0, 5000),    # 5s audio
        (0.5, 0),       # 0.5s short silence
        (5.0, 5000),    # 5s audio
        (2.0, 0),       # 2s long silence (should be selected)
        (5.0, 5000),    # 5s audio
    ]

    wav_path = tmp_path / "test_audio.wav"
    _write_wav_with_pattern(wav_path, pattern, sample_rate=8000)

    # Target at 11 seconds (near both silences), window ±5 seconds
    boundary = cli._find_silence_boundary(str(wav_path), target_seconds=11.0, window_seconds=5.0)

    # Should prefer the longer silence (around 10.5-12.5 seconds)
    assert 10.0 <= boundary <= 13.0


@pytest.mark.skipif(not NUMPY_AVAILABLE, reason="numpy not installed")
def test_find_silence_boundary_fallback_when_no_silence(tmp_path: Path) -> None:
    """Should return target when no silence found."""

    # Continuous audio with no silence
    pattern = [
        (20.0, 5000),   # 20 seconds of continuous audio
    ]

    wav_path = tmp_path / "test_audio.wav"
    _write_wav_with_pattern(wav_path, pattern, sample_rate=8000)

    target = 10.0
    boundary = cli._find_silence_boundary(str(wav_path), target_seconds=target, window_seconds=5.0)

    # Should return close to target (fallback behavior)
    assert abs(boundary - target) < 1.0


@pytest.mark.skipif(not NUMPY_AVAILABLE, reason="numpy not installed")
def test_split_wav_file_smart_uses_silence_detection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Smart split should cut at silence boundaries, not fixed intervals."""

    # Create audio with clear silence markers every ~700 seconds
    # Pattern: 700s audio, 2s silence, repeat
    pattern = [
        (700.0, 5000),
        (2.0, 0),
        (700.0, 5000),
        (2.0, 0),
        (200.0, 5000),  # Final partial segment
    ]

    wav_path = tmp_path / "long_audio.wav"
    _write_wav_with_pattern(wav_path, pattern, sample_rate=100)  # Low sample rate for speed

    monkeypatch.setattr(cli, "AUDIO_SEGMENT_SECONDS", 700.0)

    output_dir = str(tmp_path / "output")
    segments = cli._split_wav_file_smart(str(wav_path), output_dir, "audio")

    # Should create 3 segments, splitting at silence boundaries
    assert len(segments) == 3

    # Verify splits occurred near silence (around 700s and 1400s)
    # First segment should be around 700-702 seconds (includes silence)
    duration_1 = cli._get_wav_duration(segments[0])
    assert 698.0 <= duration_1 <= 705.0, f"First segment duration {duration_1} not near silence"

    # Second segment should also be around 700-702 seconds
    duration_2 = cli._get_wav_duration(segments[1])
    assert 698.0 <= duration_2 <= 705.0, f"Second segment duration {duration_2} not near silence"


@pytest.mark.skipif(not NUMPY_AVAILABLE, reason="numpy not installed")
def test_split_wav_file_smart_respects_max_duration(tmp_path: Path) -> None:
    """Smart split should not exceed maximum segment duration."""

    # Create very long audio without silence
    pattern = [
        (2000.0, 5000),  # 2000 seconds of continuous audio
    ]

    wav_path = tmp_path / "very_long_audio.wav"
    _write_wav_with_pattern(wav_path, pattern, sample_rate=100)

    output_dir = str(tmp_path / "output")
    segments = cli._split_wav_file_smart(str(wav_path), output_dir, "audio")

    # Should split into multiple segments despite no silence
    assert len(segments) >= 2

    # No segment should exceed AUDIO_SEGMENT_SECONDS
    for segment in segments:
        duration = cli._get_wav_duration(segment)
        assert duration <= cli.AUDIO_SEGMENT_SECONDS + 5.0  # Allow small margin
