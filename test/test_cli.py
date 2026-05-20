"""Test suite for any2summary CLI tool."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, List

import pytest


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PACKAGE_ROOT = os.path.dirname(PROJECT_ROOT)
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)

import any2summary.cli as cli


def test_cli_outputs_transcript_with_speaker_annotations(monkeypatch, capsys):
    """CLI should merge transcript and speaker data into JSON output."""

    def fake_fetch_transcript(video_url: str, language: str, fallback_languages: List[str]):
        assert video_url == "https://youtu.be/example"
        assert language == "en"
        assert fallback_languages == ["en"]
        return [
            {"start": 0.0, "end": 2.5, "text": "Hello world."},
            {"start": 2.5, "end": 5.2, "text": "Second sentence."},
        ]

    def fake_perform_diarization(
        video_url: str,
        language: str,
        max_speakers: int | None = None,
        known_speakers=None,
        known_speaker_names=None,
        streaming: bool = True,
    ):
        assert video_url == "https://youtu.be/example"
        assert language == "en"
        assert max_speakers is None
        assert known_speakers is None
        assert known_speaker_names is None
        assert streaming is True
        return {
            "speakers": [
                {"start": 0.0, "end": 3.0, "speaker": "Speaker A"},
                {"start": 3.0, "end": 6.0, "speaker": "Speaker B"},
            ],
            "transcript": None,
        }

    monkeypatch.setattr(cli, "fetch_transcript_with_metadata", fake_fetch_transcript)
    monkeypatch.setattr(cli, "perform_azure_diarization", fake_perform_diarization)

    exit_code = cli.run([
        "--url",
        "https://youtu.be/example",
        "--language",
        "en",
        "--force-azure-diarization",
    ])

    assert exit_code == 0

    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    assert payload[0]["speaker"] == "Speaker A"
    assert payload[1]["speaker"] == "Speaker B"
    assert payload[0]["start"] == 0.0
    assert payload[1]["end"] == 5.2


def test_cli_fallbacks_to_azure_transcription(monkeypatch, capsys):
    """When YouTube transcript is unavailable, Azure fallback should be used."""

    def fake_fetch_transcript(video_url: str, language: str, fallback_languages: List[str]):
        raise RuntimeError("No subtitles available")

    def fake_perform_diarization(
        video_url: str,
        language: str,
        max_speakers: int | None = None,
        known_speakers=None,
        known_speaker_names=None,
        streaming: bool = True,
    ):
        return {
            "speakers": [
                {"start": 0.0, "end": 3.0, "speaker": "Speaker A"},
                {"start": 3.0, "end": 6.0, "speaker": "Speaker B"},
            ],
            "transcript": [
                {"start": 0.0, "end": 3.0, "text": "Hello world."},
                {"start": 3.0, "end": 6.0, "text": "Second sentence."},
            ],
        }

    monkeypatch.setattr(
        cli, "fetch_transcript_with_metadata", fake_fetch_transcript
    )
    monkeypatch.setattr(cli, "perform_azure_diarization", fake_perform_diarization)

    exit_code = cli.run([
        "--url",
        "https://youtu.be/example",
        "--language",
        "en",
    ])

    assert exit_code == 0

    stdout = capsys.readouterr().out
    payload = json.loads(stdout)

    assert payload[0]["text"] == "Hello world."
    assert payload[1]["speaker"] == "Speaker B"


def test_run_retries_single_url_success(monkeypatch, capsys):
    """_run_single 返回非 0 时应自动重试一次。"""

    attempts = {"count": 0}

    def fake_run_single(args):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return 1
        print("[]")
        return 0

    monkeypatch.setattr(cli, "_run_single", fake_run_single)

    exit_code = cli.run([
        "--url",
        "https://youtu.be/retry",
        "--language",
        "en",
    ])

    assert exit_code == 0
    assert attempts["count"] == 2
    assert capsys.readouterr().out.strip() == "[]"


def test_run_retries_single_url_failure(monkeypatch, capsys):
    """连续失败两次应返回非 0 且仅重试一次。"""

    attempts = {"count": 0}

    def fake_run_single(args):
        attempts["count"] += 1
        return 1

    monkeypatch.setattr(cli, "_run_single", fake_run_single)

    exit_code = cli.run([
        "--url",
        "https://youtu.be/retry",
        "--language",
        "en",
    ])

    assert exit_code == 1
    assert attempts["count"] == 2
    assert capsys.readouterr().out == ""


def test_cli_skips_azure_when_captions_available(monkeypatch, capsys):
    """有字幕时应短路 Azure 调用以避免下载音频。"""

    segments = [
        {"start": 0.0, "end": 2.0, "text": "Hello world."},
        {"start": 2.0, "end": 4.0, "text": "Second."},
    ]

    monkeypatch.setattr(
        cli,
        "fetch_transcript_with_metadata",
        lambda *args, **kwargs: [dict(segment) for segment in segments],
    )

    def fake_perform(*_args, **_kwargs):  # pragma: no cover - should not run
        raise AssertionError("Azure diarization should be skipped when captions exist")

    monkeypatch.setattr(cli, "perform_azure_diarization", fake_perform)

    exit_code = cli.run([
        "--url",
        "https://youtu.be/example",
        "--language",
        "en",
    ])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["text"] == "Hello world."
    assert "speaker" not in payload[0]


def test_cli_force_azure_diarization_invokes_azure(monkeypatch, capsys):
    """强制模式下即使有字幕也应调用 Azure。"""

    segments = [
        {"start": 0.0, "end": 3.0, "text": "Hello."},
    ]

    monkeypatch.setattr(
        cli,
        "fetch_transcript_with_metadata",
        lambda *args, **kwargs: [dict(segment) for segment in segments],
    )

    azure_called = {"value": False}

    def fake_perform(*_args, **_kwargs):
        azure_called["value"] = True
        return {
            "speakers": [{"start": 0.0, "end": 3.0, "speaker": "Speaker A"}],
            "transcript": None,
        }

    monkeypatch.setattr(cli, "perform_azure_diarization", fake_perform)

    exit_code = cli.run(
        [
            "--url",
            "https://youtu.be/example",
            "--language",
            "en",
            "--force-azure-diarization",
        ]
    )

    assert exit_code == 0
    assert azure_called["value"] is True
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["speaker"] == "Speaker A"


def test_run_multiple_retries_each_url(monkeypatch, capsys):
    """_run_multiple 中的每个 URL 都应支持一次重试。"""

    attempts: dict[str, int] = {}

    def fake_run_single(args):
        attempts[args.url] = attempts.get(args.url, 0) + 1
        count = attempts[args.url]
        if count == 1:
            return 1
        print(json.dumps({"url": args.url, "attempt": count}))
        return 0

    monkeypatch.setattr(cli, "_run_single", fake_run_single)

    exit_code = cli.run([
        "--url",
        "https://youtu.be/a,https://youtu.be/b",
        "--language",
        "en",
    ])

    assert exit_code == 0
    assert attempts == {
        "https://youtu.be/a": 2,
        "https://youtu.be/b": 2,
    }

    output_lines = [line for line in capsys.readouterr().out.splitlines() if line]
    assert len(output_lines) == 2
    for line in output_lines:
        data = json.loads(line)
        assert data["attempt"] == 2


def test_run_multiple_reports_failure_after_retries(monkeypatch, capsys):
    """多链接模式下若两次都失败，应输出错误并返回 1。"""

    attempts: dict[str, int] = {}

    def fake_run_single(args):
        attempts[args.url] = attempts.get(args.url, 0) + 1
        if args.url.endswith("ok") and attempts[args.url] == 2:
            print("{}")
            return 0
        return 1

    monkeypatch.setattr(cli, "_run_single", fake_run_single)

    exit_code = cli.run([
        "--url",
        "https://youtu.be/fail,https://youtu.be/ok",
        "--language",
        "en",
    ])

    assert exit_code == 1
    assert attempts["https://youtu.be/fail"] == 2
    assert attempts["https://youtu.be/ok"] == 2

    captured = capsys.readouterr()
    stderr_lines = [line for line in captured.err.splitlines() if line]
    assert any("https://youtu.be/fail" in line for line in stderr_lines)


def test_prepare_audio_uses_cache(monkeypatch, tmp_path):
    """Cached WAV file should bypass re-download and reconversion."""

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    monkeypatch.setenv("ANY2SUMMARY_CACHE_DIR", str(cache_dir))

    video_url = "https://youtu.be/example"
    video_id = cli.extract_video_id(video_url)
    assert video_id is not None

    video_dir = cache_dir / "youtube" / video_id
    video_dir.mkdir(parents=True)
    wav_path = video_dir / "audio.wav"
    wav_path.write_bytes(b"fake-audio")

    download_called = False
    convert_called = False

    def fake_download(url: str, directory: str) -> str:
        nonlocal download_called
        download_called = True
        return str(video_dir / "audio.m4a")

    def fake_convert(src: str, dst: str) -> None:
        nonlocal convert_called
        convert_called = True

    monkeypatch.setattr(cli, "download_audio_stream", fake_download)
    monkeypatch.setattr(cli, "convert_audio_to_wav", fake_convert)

    cached_path = cli._prepare_audio_cache(video_url)

    assert cached_path == str(wav_path)
    assert not download_called
    assert not convert_called


def test_resolve_video_cache_dir_non_youtube(monkeypatch, tmp_path):
    """非 YouTube URL 应使用稳定哈希目录。"""

    monkeypatch.setenv("ANY2SUMMARY_CACHE_DIR", str(tmp_path))

    url = "https://www.bilibili.com/video/BV1xx411c7mD?p=2"
    cache_dir = cli._resolve_video_cache_dir(url)

    assert cache_dir.startswith(str(tmp_path))
    assert "bilibili" in cache_dir
    assert os.path.isdir(cache_dir)


def test_build_extra_body(tmp_path):
    audio_file = tmp_path / "speaker.wav"
    audio_file.write_bytes(b"fake-audio")

    payload = cli._build_extra_body([("Agent", str(audio_file))])

    assert payload["known_speaker_names"] == ["Agent"]
    assert payload["known_speaker_references"][0].startswith("data:audio/wav;base64,")


def test_parse_known_speakers_invalid():
    with pytest.raises(RuntimeError):
        cli._parse_known_speakers(["invalid-format"])


def test_cli_clean_cache_removes_cached_directory(monkeypatch, tmp_path, capsys):
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    monkeypatch.setenv("ANY2SUMMARY_CACHE_DIR", str(cache_root))

    url = "https://www.youtube.com/watch?v=exampleid"
    video_dir = cache_root / "exampleid"
    video_dir.mkdir()
    (video_dir / "audio.wav").write_bytes(b"fake-audio")

    removed: dict[str, str] = {}

    def fake_rmtree(path: str, **kwargs):
        removed["path"] = path

    def fake_fetch_transcript(*_args, **_kwargs):
        return [{"start": 0.0, "end": 1.0, "text": "Hi"}]

    monkeypatch.setattr(cli.shutil, "rmtree", fake_rmtree)
    monkeypatch.setattr(cli, "fetch_transcript_with_metadata", fake_fetch_transcript)

    exit_code = cli.run([
        "--url",
        url,
        "--clean-cache",
    ])

    assert exit_code == 0
    expected = cli._resolve_video_cache_dir(url)
    assert removed["path"] == expected
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload[0]["text"] == "Hi"


def test_cli_loads_env_file(monkeypatch, tmp_path):
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "AZURE_OPENAI_API_KEY=dotenv-key\nAZURE_OPENAI_ENDPOINT=https://example.invalid\n"
    )

    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.setenv("ANY2SUMMARY_DOTENV", str(dotenv_path))

    def fake_fetch_transcript(*_args, **_kwargs):
        raise RuntimeError("transcript unavailable")

    def fake_perform_diarization(*_args, **_kwargs):
        assert os.getenv("AZURE_OPENAI_API_KEY") == "dotenv-key"
        assert os.getenv("AZURE_OPENAI_ENDPOINT") == "https://example.invalid"
        return {
            "speakers": [{"start": 0.0, "end": 1.0, "speaker": "Speaker"}],
            "transcript": [{"start": 0.0, "end": 1.0, "text": "Azure"}],
        }

    monkeypatch.setattr(cli, "fetch_transcript_with_metadata", fake_fetch_transcript)
    monkeypatch.setattr(cli, "perform_azure_diarization", fake_perform_diarization)

    exit_code = cli.run(["--url", "https://youtu.be/env"])

    assert exit_code == 0


def test_cli_can_disable_azure_streaming(monkeypatch, tmp_path):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.com")

    segments = [{"start": 0.0, "end": 1.0, "text": "Hi"}]

    monkeypatch.setattr(
        cli,
        "fetch_transcript_with_metadata",
        lambda *_args, **_kwargs: [dict(segment) for segment in segments],
    )

    captured: dict[str, bool] = {}

    def fake_perform_diarization(
        *_args,
        **kwargs,
    ):
        captured["streaming"] = kwargs.get("streaming")
        return {
            "speakers": [{"start": 0.0, "end": 1.0, "speaker": "Speaker"}],
            "transcript": None,
        }

    monkeypatch.setattr(cli, "perform_azure_diarization", fake_perform_diarization)

    exit_code = cli.run(
        [
            "--url",
            "https://youtu.be/disable",
            "--force-azure-diarization",
            "--no-azure-streaming",
        ]
    )

    assert exit_code == 0
    assert captured["streaming"] is False


def test_should_try_android_fallback_with_cookies():
    exc = RuntimeError("HTTP Error 403: Forbidden")
    assert cli._should_try_android_fallback(exc, cookiefile="/tmp/cookies.txt")


def test_direct_audio_url_skips_youtube_transcript(monkeypatch, capsys):
    """Direct .m4a URLs must go straight to Azure, not youtube-transcript-api."""

    target_url = "https://media.xyzcdn.net/626b46ea9cbbf0451cf5a962/ll7qIcIWWGFSsORHr4yY-UuqAe8h.m4a"

    def fail_fetch_transcript(*_args, **_kwargs):  # pragma: no cover - defensive
        raise AssertionError("direct audio must not import/fetch YouTube transcripts")

    def fake_perform_diarization(video_url: str, *_args, **_kwargs):
        assert video_url == target_url
        return {
            "speakers": [{"start": 0.0, "end": 2.0, "speaker": "Speaker A"}],
            "transcript": [{"start": 0.0, "end": 2.0, "text": "完整音频转写片段"}],
        }

    monkeypatch.setattr(cli, "fetch_transcript_with_metadata", fail_fetch_transcript)
    monkeypatch.setattr(cli, "perform_azure_diarization", fake_perform_diarization)

    exit_code = cli.run(["--url", target_url, "--language", "zh"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["text"] == "完整音频转写片段"


def test_xiaoyuzhou_page_resolves_og_audio_before_summary(monkeypatch, capsys):
    """小宇宙页面必须先解析 og:audio，并基于音频 URL 转写。"""

    page_url = "https://www.xiaoyuzhoufm.com/episode/6a00aa051b7bd50295dfe41d"
    audio_url = "https://media.xyzcdn.net/626b46ea9cbbf0451cf5a962/ll7qIcIWWGFSsORHr4yY-UuqAe8h.m4a"

    class _Response:
        text = (
            "<html><head>"
            f"<meta property='og:audio' content='{audio_url}'>"
            "</head><body><p>show notes should not be used as summary basis</p></body></html>"
        )

        def raise_for_status(self) -> None:
            return None

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *_args: Any) -> bool:
            return False

        def get(self, url: str, **_kwargs: Any) -> _Response:
            assert url == page_url
            return _Response()

    def fail_fetch_article_assets(*_args, **_kwargs):  # pragma: no cover - defensive
        raise AssertionError("podcast pages must not fall back to article/show notes")

    def fake_perform_diarization(video_url: str, *_args, **_kwargs):
        assert video_url == audio_url
        return {
            "speakers": [{"start": 0.0, "end": 2.0, "speaker": "姚顺宇"}],
            "transcript": [{"start": 0.0, "end": 2.0, "text": "基于音频的转写"}],
        }

    monkeypatch.setattr(cli, "_create_http_client", lambda: _Client())
    monkeypatch.setattr(cli, "fetch_article_assets", fail_fetch_article_assets)
    monkeypatch.setattr(cli, "perform_azure_diarization", fake_perform_diarization)

    exit_code = cli.run(["--url", page_url, "--language", "zh"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["text"] == "基于音频的转写"


def test_podcast_page_without_audio_fails_fast(monkeypatch):
    """未解析到音频时，禁止输出基于 metadata/show notes 的完整总结。"""

    page_url = "https://www.xiaoyuzhoufm.com/episode/no-audio"

    class _Response:
        text = "<html><body><p>only show notes</p></body></html>"

        def raise_for_status(self) -> None:
            return None

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *_args: Any) -> bool:
            return False

        def get(self, url: str, **_kwargs: Any) -> _Response:
            assert url == page_url
            return _Response()

    monkeypatch.setattr(cli, "_create_http_client", lambda: _Client())

    with pytest.raises(RuntimeError, match="禁止基于页面元数据"):
        cli._resolve_podcast_audio_url(page_url)
