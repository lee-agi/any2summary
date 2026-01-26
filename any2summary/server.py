"""FastAPI companion server for Chrome extension audio transcription.

This module provides HTTP endpoints that wrap the CLI functions, allowing
the Chrome extension to call audio transcription and summarization APIs
via a local server.

Usage:
    any2summary serve --port 8765
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, MutableMapping, Optional

_LOGGER = logging.getLogger(__name__)

# Default port for the companion server
DEFAULT_SERVER_PORT = 8765


# ----- Pydantic Request Models -----
# These ensure the server accepts JSON request body (not query params),
# matching the Chrome extension's fetch call format in summarize.js.
# Models are defined at module level so FastAPI can properly recognize them.

try:
    from pydantic import BaseModel

    class TranscribeRequest(BaseModel):
        """Request body for /api/transcribe endpoint."""

        url: str
        language: str = "en"
        max_speakers: Optional[int] = None
        known_speaker_names: Optional[List[str]] = None
        streaming: bool = True

    class SummarizeRequest(BaseModel):
        """Request body for /api/summarize endpoint."""

        url: str
        language: str = "en"
        azure_summary: bool = True
        azure_streaming: bool = True
        force_azure_diarization: bool = False
        summary_prompt: Optional[str] = None
        article_summary_prompt: Optional[str] = None

except ImportError:
    # Pydantic will be imported when FastAPI is available
    TranscribeRequest = None  # type: ignore
    SummarizeRequest = None  # type: ignore


def _convert_metadata_to_camel_case(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """将 metadata 字段名从 snake_case 转换为 camelCase。

    这是为了与 Chrome 扩展 fileSaver.js 保持一致，后者期望 camelCase 字段名。

    Args:
        metadata: 原始 metadata 字典（yt-dlp 返回的 snake_case 格式）

    Returns:
        转换后的 camelCase 格式 metadata
    """
    if not metadata:
        return {}

    # 字段名映射表：snake_case -> camelCase
    field_mapping = {
        "title": "title",
        "webpage_url": "webpageUrl",
        "upload_date": "uploadDate",
        "duration": "duration",
        "channel": "channel",
        "channel_id": "channelId",
        "uploader": "uploader",
        "description": "description",
        "view_count": "viewCount",
        "like_count": "likeCount",
        "comment_count": "commentCount",
    }

    camel_metadata = {}
    for snake_key, camel_key in field_mapping.items():
        if snake_key in metadata:
            camel_metadata[camel_key] = metadata[snake_key]

    # 保留未映射的字段（原样复制）
    for key, value in metadata.items():
        if key not in field_mapping and key not in camel_metadata:
            camel_metadata[key] = value

    return camel_metadata


def create_app() -> Any:
    """Create and configure the FastAPI application."""
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
    except ImportError as exc:
        raise RuntimeError(
            "FastAPI 未安装。请执行 `pip install fastapi uvicorn`。"
        ) from exc

    app = FastAPI(
        title="any2summary Companion Server",
        description="Local server for Chrome extension audio transcription support",
        version="1.0.0",
    )

    # Configure CORS for Chrome extension
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allow all origins for local development
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    async def health_check():
        """Health check endpoint to verify server availability."""
        from any2summary import cli

        # Check available services
        services = {
            "ffmpeg": _check_ffmpeg_available(),
            "yt_dlp": _check_ytdlp_available(),
            "azure_openai": _check_azure_credentials(),
        }

        return {
            "status": "ok",
            "version": cli.__CLI_VERSION,
            "services": services,
        }

    @app.post("/api/transcribe")
    async def transcribe(body: TranscribeRequest):
        """Transcribe audio from URL with speaker diarization.

        This endpoint wraps the CLI's perform_azure_diarization function.
        Accepts JSON request body (not query params) to match Chrome extension.
        """
        from any2summary import cli

        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: cli.perform_azure_diarization(
                    video_url=body.url,
                    language=body.language,
                    max_speakers=body.max_speakers,
                    known_speaker_names=body.known_speaker_names,
                    streaming=body.streaming,
                ),
            )

            # 获取 video metadata（perform_azure_diarization 不返回 metadata）
            # 这是为了确保 Chrome 扩展能获取正确的 title、domain 和 uploadDate
            video_metadata = None
            try:
                video_metadata = cli._fetch_video_metadata(body.url)
            except Exception as meta_exc:
                _LOGGER.warning("Failed to fetch video metadata: %s", meta_exc)

            camel_metadata = _convert_metadata_to_camel_case(video_metadata) if video_metadata else None

            return {
                "speakers": result.get("speakers", []),
                "transcript": result.get("transcript", []),
                "metadata": camel_metadata,
            }

        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            _LOGGER.exception("Transcription failed")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.post("/api/summarize")
    async def summarize(body: SummarizeRequest):
        """Summarize content from URL.

        This endpoint wraps the CLI's full processing pipeline.
        Accepts JSON request body (not query params) to match Chrome extension.
        """
        import argparse
        from any2summary import cli

        try:
            # Build args namespace to mimic CLI
            args = argparse.Namespace(
                url=body.url,
                language=body.language,
                fallback_languages=None,
                azure_streaming=body.azure_streaming,
                force_azure_diarization=body.force_azure_diarization,
                azure_summary=body.azure_summary,
                summary_prompt_file=None,
                article_summary_prompt_file=None,
                max_speakers=None,
                known_speakers=None,
                known_speaker_names=None,
                clean_cache=False,
            )

            # Override prompts if provided
            if body.summary_prompt:
                import tempfile
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False
                ) as f:
                    f.write(body.summary_prompt)
                    args.summary_prompt_file = f.name

            if body.article_summary_prompt:
                import tempfile
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False
                ) as f:
                    f.write(body.article_summary_prompt)
                    args.article_summary_prompt_file = f.name

            # Run in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: _run_summarize_pipeline(args),
            )

            return {
                "summary": result.get("summary", ""),
                "segments": result.get("segments", []),
                "metadata": result.get("metadata"),
                "timeline": result.get("timeline"),
            }

        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            _LOGGER.exception("Summarization failed")
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/youtube/transcript")
    async def get_youtube_transcript(
        url: str,
        languages: str = "en,zh-Hans,zh-Hant",
    ):
        """获取 YouTube 视频字幕。

        本地服务会使用系统代理（通过 HTTP_PROXY/HTTPS_PROXY 环境变量）。

        Args:
            url: YouTube 视频 URL
            languages: 逗号分隔的语言代码列表，按优先级排序

        Returns:
            包含 segments 和 metadata 的 JSON 响应
        """
        from any2summary import cli

        try:
            # Parse language preferences
            preferred_languages = [
                lang.strip() for lang in languages.split(",") if lang.strip()
            ]
            if not preferred_languages:
                preferred_languages = ["en", "zh-Hans", "zh-Hant"]

            primary_language = preferred_languages[0]
            fallback_languages = preferred_languages[1:]

            # Fetch transcript segments (uses system proxy via youtube_transcript_api)
            loop = asyncio.get_event_loop()
            segments = await loop.run_in_executor(
                None,
                lambda: cli.fetch_transcript_with_metadata(
                    url, primary_language, fallback_languages
                ),
            )

            # Fetch video metadata (uses system proxy via yt-dlp)
            metadata = await loop.run_in_executor(
                None,
                lambda: cli._fetch_video_metadata(url),
            )

            # 将 metadata 字段名转换为 camelCase（与 Chrome 扩展 fileSaver.js 保持一致）
            camel_metadata = _convert_metadata_to_camel_case(metadata) if metadata else None
            return {
                "segments": segments,
                "metadata": camel_metadata,
            }

        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            _LOGGER.exception("YouTube transcript fetch failed")
            raise HTTPException(status_code=500, detail=str(exc))

    return app


def _check_ffmpeg_available() -> bool:
    """Check if ffmpeg is available in PATH."""
    import shutil
    return shutil.which("ffmpeg") is not None


def _check_ytdlp_available() -> bool:
    """Check if yt-dlp is available."""
    try:
        import yt_dlp
        return True
    except ImportError:
        return False


def _check_azure_credentials() -> bool:
    """Check if Azure OpenAI credentials are configured."""
    return bool(
        os.getenv("AZURE_OPENAI_API_KEY") and os.getenv("AZURE_OPENAI_ENDPOINT")
    )


def _run_summarize_pipeline(args) -> MutableMapping[str, Any]:
    """Run the summarization pipeline and capture output.

    This wraps _run_single to capture JSON output instead of printing.
    """
    import io
    import json
    import sys
    from any2summary import cli

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured = io.StringIO()

    try:
        exit_code = cli._run_single(args)
        output = captured.getvalue()

        if exit_code != 0:
            raise RuntimeError(f"Pipeline failed with exit code {exit_code}")

        # Parse JSON output
        if output.strip():
            return json.loads(output)
        return {}

    finally:
        sys.stdout = old_stdout


def run_server(
    host: str = "127.0.0.1",
    port: int = DEFAULT_SERVER_PORT,
    reload: bool = False,
) -> None:
    """Run the FastAPI server.

    Args:
        host: Host to bind to (default: 127.0.0.1 for security)
        port: Port to bind to (default: 8765)
        reload: Enable auto-reload for development
    """
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(
            "uvicorn 未安装。请执行 `pip install uvicorn`。"
        ) from exc

    _LOGGER.info("Starting any2summary server on %s:%d", host, port)

    uvicorn.run(
        "any2summary.server:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )
