"""针对 Azure 说话人分离回退逻辑的测试。"""

from __future__ import annotations

import sys
import types
import wave
from pathlib import Path

import pytest
import json
from httpx import RemoteProtocolError
import httpx
import httpcore

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from any2summary import cli


def test_consume_transcription_response_collects_stream_data() -> None:
    """流式响应应累积所有 chunk 便于后续解析。"""

    chunks = [
        {"type": "transcript.segment", "segments": [{"start": 0, "end": 1}]},
        {"type": "transcript.text.done", "text": "Final"},
    ]

    result = cli._consume_transcription_response(iter(chunks))

    assert "data" in result
    assert result["data"] == chunks


def test_consume_transcription_response_handles_remote_protocol_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """流式响应中途断开时也应返回已收集的数据。"""

    chunks = [
        {"type": "transcript.segment", "segments": [{"start": 0, "end": 1}]},
        {"type": "transcript.text.done", "text": "Partial"},
    ]

    def _broken_stream():
        for chunk in chunks:
            yield chunk
        raise RemoteProtocolError("peer closed connection without sending complete message body")

    caplog.set_level("WARNING")

    result = cli._consume_transcription_response(_broken_stream())

    assert result["data"] == chunks
    assert (
        "RemoteProtocolError" in caplog.text
        or "流式响应中断" in caplog.text
        or "Azure streaming response interrupted" in caplog.text
    )


def test_consume_transcription_response_handles_read_timeout(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """读超时也应视为传输中断并返回已收集的数据。"""

    chunks = [
        {"type": "transcript.segment", "segments": [{"start": 0, "end": 1}]},
        {"type": "transcript.text.done", "text": "Partial"},
    ]

    def _timeout_stream():
        for chunk in chunks:
            yield chunk
        raise httpx.ReadTimeout("timeout")

    caplog.set_level("WARNING")

    result = cli._consume_transcription_response(_timeout_stream())

    assert result["data"] == chunks
    assert (
        "timeout" in caplog.text
        or "流式响应中断" in caplog.text
        or "Azure streaming response interrupted" in caplog.text
    )


def test_consume_transcription_response_handles_httpcore_remote_protocol_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """httpcore RemoteProtocolError 也应视为传输中断。"""

    chunks = [
        {"type": "transcript.segment", "segments": [{"start": 0, "end": 1}]},
        {"type": "transcript.text.done", "text": "Partial"},
    ]

    def _broken_stream():
        for chunk in chunks:
            yield chunk
        raise httpcore.RemoteProtocolError(
            "peer closed connection without sending complete message body"
    )

    caplog.set_level("WARNING")

    result = cli._consume_transcription_response(_broken_stream())

    assert result["data"] == chunks
    assert (
        "RemoteProtocolError" in caplog.text
        or "流式响应中断" in caplog.text
        or "Azure streaming response interrupted" in caplog.text
    )


def test_perform_azure_diarization_supports_checkpoint_resume(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """分段级 checkpoint 可在连接失败后断点续跑。"""

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.com")

    first_segment = tmp_path / "part1.wav"
    second_segment = tmp_path / "part2.wav"
    _write_silent_wav(first_segment, duration_seconds=1.0)
    _write_silent_wav(second_segment, duration_seconds=1.0)

    monkeypatch.setattr(cli, "_prepare_audio_cache", lambda _url: str(tmp_path / "audio.wav"))
    monkeypatch.setattr(
        cli, "_ensure_audio_segments", lambda _wav: [str(first_segment), str(second_segment)]
    )
    monkeypatch.setattr(cli, "_resolve_video_cache_dir", lambda _url: str(tmp_path))

    cache_path = tmp_path / "diarization.json"
    checkpoint_path = tmp_path / "diarization.partial.json"

    def _payload(offset: float) -> MutableMapping[str, Any]:
        return {
            "speakers": [
                {"start": 0.0 + offset, "end": 1.0 + offset, "speaker": "S1"}
            ],
            "transcript": [
                {
                    "start": 0.0 + offset,
                    "end": 1.0 + offset,
                    "speaker": "S1",
                    "text": f"chunk-{offset}",
                }
            ],
        }

    class _FlakyTranscriptions:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **_: object):
            self.calls += 1
            if self.calls == 1:
                return _payload(0.0)
            raise httpx.ConnectError("reset", request=None)

    class _StableTranscriptions:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **_: object):
            self.calls += 1
            return _payload(1.0)

    class _DummyAudio:
        def __init__(self, transcriptions):
            self.transcriptions = transcriptions

    class _DummyAzureOpenAI:
        def __init__(self, transcriptions):
            self.audio = _DummyAudio(transcriptions)

    flaky_module = types.SimpleNamespace(
        AzureOpenAI=lambda **_: _DummyAzureOpenAI(_FlakyTranscriptions()),
        BadRequestError=RuntimeError,
        APIConnectionError=httpx.ConnectError,
    )

    caplog.set_level("WARNING")
    monkeypatch.setitem(sys.modules, "openai", flaky_module)

    with pytest.raises(httpx.ConnectError):
        cli.perform_azure_diarization("https://example.com/podcast", "en", streaming=False)

    assert not cache_path.exists()
    assert checkpoint_path.exists()

    stable_module = types.SimpleNamespace(
        AzureOpenAI=lambda **_: _DummyAzureOpenAI(_StableTranscriptions()),
        BadRequestError=RuntimeError,
        APIConnectionError=httpx.ConnectError,
    )
    monkeypatch.setitem(sys.modules, "openai", stable_module)

    result = cli.perform_azure_diarization("https://example.com/podcast", "en", streaming=False)

    assert checkpoint_path.exists() is False
    assert cache_path.exists()
    assert len(result["transcript"]) == 2
    assert len(result["speakers"]) == 2


def test_perform_azure_diarization_skips_completed_segments_from_checkpoint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """已有 checkpoint 时应跳过已完成的分段。"""

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.com")

    first_segment = tmp_path / "part1.wav"
    second_segment = tmp_path / "part2.wav"
    _write_silent_wav(first_segment, duration_seconds=1.0)
    _write_silent_wav(second_segment, duration_seconds=1.0)

    monkeypatch.setattr(cli, "_prepare_audio_cache", lambda _url: str(tmp_path / "audio.wav"))
    monkeypatch.setattr(
        cli, "_ensure_audio_segments", lambda _wav: [str(first_segment), str(second_segment)]
    )
    monkeypatch.setattr(cli, "_resolve_video_cache_dir", lambda _url: str(tmp_path))

    checkpoint_path = tmp_path / "diarization.partial.json"
    cache_path = tmp_path / "diarization.json"

    checkpoint_payload = {
        "speakers": [
            {"start": 0.0, "end": 1.0, "speaker": "S1"},
        ],
        "transcript": [
            {"start": 0.0, "end": 1.0, "speaker": "S1", "text": "cached"}
        ],
        "segment_offset": 1.0,
        "processed_duration": 1.0,
        "produced_tokens": 10.0,
        "segments_done": 1,
    }
    checkpoint_path.write_text(json.dumps(checkpoint_payload), encoding="utf-8")

    class _CountingTranscriptions:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **_: object):
            self.calls += 1
            return {
                "speakers": [
                    {"start": 0.0, "end": 1.0, "speaker": "S2"},
                ],
                "transcript": [
                    {
                        "start": 0.0,
                        "end": 1.0,
                        "speaker": "S2",
                        "text": "new",
                    }
                ],
            }

    class _DummyAudio:
        def __init__(self, transcriptions: _CountingTranscriptions) -> None:
            self.transcriptions = transcriptions

    class _DummyAzureOpenAI:
        def __init__(self, transcriptions: _CountingTranscriptions) -> None:
            self.audio = _DummyAudio(transcriptions)

    transcriptions = _CountingTranscriptions()
    module = types.SimpleNamespace(
        AzureOpenAI=lambda **_: _DummyAzureOpenAI(transcriptions),
        BadRequestError=RuntimeError,
    )
    monkeypatch.setitem(sys.modules, "openai", module)

    result = cli.perform_azure_diarization("https://example.com/podcast", "en", streaming=False)

    assert transcriptions.calls == 1, "应只处理未完成的分段"
    assert cache_path.exists()
    assert not checkpoint_path.exists()
    assert result["transcript"][0]["text"] == "cached"
    assert result["transcript"][1]["text"] == "new"


def test_perform_azure_diarization_retries_stream_transport_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """流式传输错误应在内部自动重试。"""

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.com")

    wav_path = tmp_path / "audio.wav"
    _write_silent_wav(wav_path, duration_seconds=1.0)

    monkeypatch.setattr(cli, "_prepare_audio_cache", lambda *_: str(wav_path))
    monkeypatch.setattr(cli, "_ensure_audio_segments", lambda *_: [str(wav_path)])
    monkeypatch.setattr(cli, "_resolve_video_cache_dir", lambda *_: str(tmp_path))

    cache_path = tmp_path / "diarization.json"
    checkpoint_path = tmp_path / "diarization.partial.json"

    class _FlakyTranscriptions:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **_: object):
            self.calls += 1
            if self.calls == 1:
                raise httpx.ConnectError("reset", request=None)
            return {
                "speakers": [
                    {"start": 0.0, "end": 1.0, "speaker": "S1"},
                ],
                "transcript": [
                    {"start": 0.0, "end": 1.0, "speaker": "S1", "text": "ok"}
                ],
            }

    class _DummyAudio:
        def __init__(self, transcriptions: _FlakyTranscriptions) -> None:
            self.transcriptions = transcriptions

    class _DummyAzureOpenAI:
        def __init__(self, transcriptions: _FlakyTranscriptions) -> None:
            self.audio = _DummyAudio(transcriptions)

    transcriptions = _FlakyTranscriptions()
    module = types.SimpleNamespace(
        AzureOpenAI=lambda **_: _DummyAzureOpenAI(transcriptions),
        BadRequestError=RuntimeError,
    )
    monkeypatch.setitem(sys.modules, "openai", module)

    result = cli.perform_azure_diarization("https://example.com/podcast", "en", streaming=False)

    assert transcriptions.calls == 2, "应在传输错误后重试一次"
    assert cache_path.exists()
    assert not checkpoint_path.exists()
    assert result["transcript"][0]["text"] == "ok"


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


class _DummyTranscriptions:
    def create(self, **kwargs):
        return {}


class _DummyAudio:
    def __init__(self) -> None:
        self.transcriptions = _DummyTranscriptions()


class _DummyAzureOpenAI:
    def __init__(self, **_: object) -> None:
        self.audio = _DummyAudio()


def test_perform_azure_diarization_handles_empty_response(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Azure 返回空响应时应当返回空结果而非抛错。"""

    wav_path = tmp_path / "audio.wav"
    _write_silent_wav(wav_path, duration_seconds=1.0)

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.com")

    module = types.SimpleNamespace(
        AzureOpenAI=_DummyAzureOpenAI,
        BadRequestError=RuntimeError,
    )
    monkeypatch.setitem(sys.modules, "openai", module)

    monkeypatch.setattr(cli, "_prepare_audio_cache", lambda _: str(wav_path))
    monkeypatch.setattr(cli, "_ensure_audio_segments", lambda __: [str(wav_path)])
    monkeypatch.setattr(cli, "_resolve_video_cache_dir", lambda _: str(tmp_path))

    result = cli.perform_azure_diarization("https://youtu.be/example", "en")

    assert result == {"speakers": [], "transcript": []}


def test_cli_azure_diarization_handles_nested_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """当 Azure 响应嵌套在 response.output 时也应提取字幕。"""

    wav_path = tmp_path / "audio.wav"
    _write_silent_wav(wav_path, duration_seconds=1.0)

    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.com")

    stream_events = [
        {
            "diarization": {
                "segments": [
                    {
                        "timestamps": {
                            "start": {"seconds": 0},
                            "end": {"seconds": 1},
                        },
                        "speaker": {"label": "Speaker 1"},
                    },
                    {
                        "timestamps": {
                            "start": {"offset_seconds": 1},
                            "end": {"offsetMillis": 2000},
                        },
                        "speaker": {"info": {"name": "Speaker 2"}},
                    },
                ]
            }
        },
        {
            "transcript": {
                "chunks": [
                    {
                        "content": [{"type": "text", "value": "Hello"}],
                        "timestamps": {"start_time_ms": 0, "end_time_ms": 1000},
                        "speaker": {"label": "Speaker 1"},
                    },
                    {
                        "content": [{"type": "text", "value": "World"}],
                        "timing": {"from": "PT1S", "to": "PT2S"},
                        "speaker": {"details": {"label": "Speaker 2"}},
                    },
                ]
            }
        },
        {"type": "transcript.text.done", "text": "Hello World"},
    ]

    captured: dict[str, object] = {}

    class _StreamingTranscriptions:
        def __init__(self) -> None:
            self.events = stream_events

        def create(self, **kwargs):
            captured["stream"] = kwargs.get("stream")
            captured["chunking_strategy"] = kwargs.get("chunking_strategy")
            if kwargs.get("stream"):
                return iter(self.events)
            return self.events[-1]

    class _Client(_DummyAzureOpenAI):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.audio.transcriptions = _StreamingTranscriptions()

    module = types.SimpleNamespace(
        AzureOpenAI=_Client,
        BadRequestError=RuntimeError,
    )
    monkeypatch.setitem(sys.modules, "openai", module)

    def fake_fetch_transcript(*_args, **_kwargs):
        raise RuntimeError(
            "No transcript available in requested languages: ['en']"
        )

    progress_updates: list[float] = []

    def record_progress(ratio: float, _detail: str | None = None) -> None:
        progress_updates.append(ratio)

    monkeypatch.setattr(cli, "fetch_transcript_with_metadata", fake_fetch_transcript)
    monkeypatch.setattr(cli, "_prepare_audio_cache", lambda *_: str(wav_path))
    monkeypatch.setattr(cli, "_ensure_audio_segments", lambda *_: [str(wav_path)])
    monkeypatch.setattr(cli, "_resolve_video_cache_dir", lambda *_: str(tmp_path))
    monkeypatch.setattr(cli, "_update_progress_bar", record_progress)

    exit_code = cli.run([
        "--url",
        "https://youtu.be/nested",
    ])

    assert exit_code == 0

    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload[0]["text"] == "Hello"
    assert payload[0]["speaker"] == "Speaker 1"
    assert payload[1]["text"] == "World"
    assert payload[1]["speaker"] == "Speaker 2"
    assert progress_updates, "Streaming 模式下应当触发进度更新"
    assert captured["stream"] is True
