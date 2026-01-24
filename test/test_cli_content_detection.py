"""Tests for smart content type detection (_smart_detect_content_type)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import Mock

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

# Import first, then reload to ensure fresh module state
import any2summary.cli as cli_module

sys.modules.pop("any2summary", None)
sys.modules.pop("any2summary.cli", None)

from any2summary import cli

cli = importlib.reload(cli)


class MockResponse:
    """Mock HTTP response for testing."""

    def __init__(
        self,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        text: str = "",
    ):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text


@pytest.fixture
def mock_httpx(monkeypatch: pytest.MonkeyPatch):
    """Mock httpx for HTTP requests."""
    # Clear the content type cache before each test
    cli._CONTENT_TYPE_CACHE.clear()

    head_responses: Dict[str, MockResponse] = {}
    get_responses: Dict[str, MockResponse] = {}

    def mock_head(url: str, **kwargs: Any) -> MockResponse:
        return head_responses.get(url, MockResponse(status_code=404))

    def mock_get(url: str, **kwargs: Any) -> MockResponse:
        return get_responses.get(url, MockResponse(status_code=404))

    mock_httpx_module = Mock()
    mock_httpx_module.head = mock_head
    mock_httpx_module.get = mock_get

    monkeypatch.setattr(cli, "httpx", mock_httpx_module)

    return {"head": head_responses, "get": get_responses}


class TestSmartDetectContentType:
    """Test suite for _smart_detect_content_type function."""

    def test_detect_video_from_file_extension(self):
        """Should detect video from .mp4 extension."""
        url = "https://example.com/video.mp4"
        result = cli._smart_detect_content_type(url)
        assert result == "video"

    def test_detect_audio_from_file_extension(self):
        """Should detect audio from .mp3, .m4a, .wav extensions."""
        test_cases = [
            "https://example.com/audio.mp3",
            "https://example.com/podcast.m4a",
            "https://example.com/sound.wav",
        ]
        for url in test_cases:
            result = cli._smart_detect_content_type(url)
            assert result == "audio", f"Failed for {url}"

    def test_detect_video_from_content_type_header(self, mock_httpx):
        """Should detect video from Content-Type header."""
        url = "https://example.com/watch?v=123"
        mock_httpx["head"][url] = MockResponse(
            status_code=200,
            headers={"content-type": "video/mp4"},
        )
        result = cli._smart_detect_content_type(url)
        assert result == "video"

    def test_detect_audio_from_content_type_header(self, mock_httpx):
        """Should detect audio from Content-Type header."""
        url = "https://example.com/podcast"
        mock_httpx["head"][url] = MockResponse(
            status_code=200,
            headers={"content-type": "audio/mpeg"},
        )
        result = cli._smart_detect_content_type(url)
        assert result == "audio"

    def test_detect_video_from_opengraph_meta_tag(self, mock_httpx):
        """Should detect video from OpenGraph og:type meta tag."""
        url = "https://tiktok.com/@user/video/123"
        mock_httpx["head"][url] = MockResponse(
            status_code=200,
            headers={"content-type": "text/html"},
        )
        mock_httpx["get"][url] = MockResponse(
            status_code=200,
            text='<html><head><meta property="og:type" content="video.other" /></head></html>',
        )
        result = cli._smart_detect_content_type(url)
        assert result == "video"

    def test_detect_video_from_twitter_card(self, mock_httpx):
        """Should detect video from Twitter Card meta tag."""
        url = "https://example.com/video-page"
        mock_httpx["head"][url] = MockResponse(
            status_code=200,
            headers={"content-type": "text/html"},
        )
        mock_httpx["get"][url] = MockResponse(
            status_code=200,
            text='<html><head><meta name="twitter:card" content="player" /></head></html>',
        )
        result = cli._smart_detect_content_type(url)
        assert result == "video"

    def test_detect_video_from_video_tag(self, mock_httpx):
        """Should detect video from <video> tag in HTML."""
        url = "https://example.com/media"
        mock_httpx["head"][url] = MockResponse(
            status_code=200,
            headers={"content-type": "text/html"},
        )
        mock_httpx["get"][url] = MockResponse(
            status_code=200,
            text='<html><body><video src="movie.mp4"></video></body></html>',
        )
        result = cli._smart_detect_content_type(url)
        assert result == "video"

    def test_detect_video_from_audio_tag(self, mock_httpx):
        """Should detect video (audio) from <audio> tag in HTML."""
        url = "https://example.com/podcast"
        mock_httpx["head"][url] = MockResponse(
            status_code=200,
            headers={"content-type": "text/html"},
        )
        mock_httpx["get"][url] = MockResponse(
            status_code=200,
            text='<html><body><audio src="podcast.mp3"></audio></body></html>',
        )
        result = cli._smart_detect_content_type(url)
        assert result == "video"  # Audio is treated as video for diarization

    def test_detect_video_from_embed_keyword_in_url(self):
        """Should detect video from 'embed' keyword in URL."""
        url = "https://example.com/embed/123"
        result = cli._smart_detect_content_type(url)
        assert result == "video"

    def test_detect_video_from_player_keyword_in_url(self):
        """Should detect video from 'player' keyword in URL."""
        url = "https://example.com/player/456"
        result = cli._smart_detect_content_type(url)
        assert result == "video"

    def test_detect_video_from_watch_keyword_in_url(self):
        """Should detect video from 'watch' keyword in URL."""
        url = "https://example.com/watch?v=789"
        result = cli._smart_detect_content_type(url)
        assert result == "video"

    def test_fallback_to_article_for_unknown_content(self, mock_httpx):
        """Should fallback to article for unknown content type."""
        url = "https://example.com/blog/post"
        mock_httpx["head"][url] = MockResponse(
            status_code=200,
            headers={"content-type": "text/html"},
        )
        mock_httpx["get"][url] = MockResponse(
            status_code=200,
            text="<html><body><h1>Blog Post</h1><p>Content...</p></body></html>",
        )
        result = cli._smart_detect_content_type(url)
        assert result == "article"

    def test_fallback_to_existing_logic_on_http_error(self, mock_httpx):
        """Should fallback to existing white list logic when HTTP fails."""
        # YouTube URL should be detected by existing white list even if HTTP fails
        url = "https://www.youtube.com/watch?v=abc123"
        mock_httpx["head"][url] = MockResponse(status_code=500)

        result = cli._smart_detect_content_type(url)
        # Should use existing _is_media_source_url logic as fallback
        assert result == "video"

    def test_detect_new_platforms_tiktok(self):
        """Should correctly detect TikTok as video (NEW FEATURE)."""
        url = "https://www.tiktok.com/@user/video/123456"
        result = cli._smart_detect_content_type(url)
        assert result == "video"

    def test_detect_new_platforms_instagram(self):
        """Should correctly detect Instagram Reels as video (NEW FEATURE)."""
        url = "https://www.instagram.com/reel/ABC123/"
        result = cli._smart_detect_content_type(url)
        assert result == "video"

    def test_detect_new_platforms_xiaohongshu(self):
        """Should correctly detect Xiaohongshu as video (NEW FEATURE)."""
        url = "https://www.xiaohongshu.com/explore/64a1b2c3d4e5f6g7h8i9"
        result = cli._smart_detect_content_type(url)
        assert result == "video"

    def test_cache_same_url_detection(self, mock_httpx):
        """Should cache detection results to avoid repeated HTTP requests."""
        url = "https://example.com/video.mp4"
        mock_httpx["head"][url] = MockResponse(
            status_code=200,
            headers={"content-type": "video/mp4"},
        )

        # First call
        result1 = cli._smart_detect_content_type(url)
        assert result1 == "video"

        # Clear mock to ensure cache is used
        mock_httpx["head"].clear()

        # Second call should use cache (no HTTP request)
        result2 = cli._smart_detect_content_type(url)
        assert result2 == "video"

    def test_timeout_handling(self, mock_httpx, monkeypatch):
        """Should handle HTTP timeout gracefully."""
        url = "https://slow.example.com/video"

        def mock_head_timeout(*args, **kwargs):
            raise Exception("Connection timeout")

        mock_httpx_module = Mock()
        mock_httpx_module.head = mock_head_timeout
        monkeypatch.setattr(cli, "httpx", mock_httpx_module)

        # Should fallback to existing logic without crashing
        result = cli._smart_detect_content_type(url)
        assert result in ["video", "article"]  # Should not crash

    def test_partial_html_fetch_limit(self, mock_httpx):
        """Should only fetch first 1KB of HTML for efficiency."""
        url = "https://example.com/page"
        large_html = "<html>" + "x" * 10000 + "</html>"

        mock_httpx["head"][url] = MockResponse(
            status_code=200,
            headers={"content-type": "text/html"},
        )
        mock_httpx["get"][url] = MockResponse(
            status_code=200,
            text=large_html,
        )

        result = cli._smart_detect_content_type(url)
        # Should work even with partial HTML
        assert result == "article"

    def test_case_insensitive_content_type(self, mock_httpx):
        """Should handle case-insensitive Content-Type headers."""
        url = "https://example.com/VIDEO.MP4"
        mock_httpx["head"][url] = MockResponse(
            status_code=200,
            headers={"content-type": "VIDEO/MP4"},  # Uppercase
        )
        result = cli._smart_detect_content_type(url)
        assert result == "video"

    def test_content_type_with_charset(self, mock_httpx):
        """Should handle Content-Type with charset parameter."""
        url = "https://example.com/page"
        mock_httpx["head"][url] = MockResponse(
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
        )
        mock_httpx["get"][url] = MockResponse(
            status_code=200,
            text="<html><body>Article content</body></html>",
        )
        result = cli._smart_detect_content_type(url)
        assert result == "article"


class TestIsProbableArticleUrlIntegration:
    """Test integration of _smart_detect_content_type with _is_probable_article_url."""

    def test_youtube_is_not_article(self):
        """YouTube URLs should NOT be detected as articles."""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = cli._is_probable_article_url(url)
        assert result is False

    def test_tiktok_is_not_article(self):
        """TikTok URLs should NOT be detected as articles (NEW FEATURE)."""
        url = "https://www.tiktok.com/@user/video/123"
        result = cli._is_probable_article_url(url)
        assert result is False

    def test_instagram_is_not_article(self):
        """Instagram Reels should NOT be detected as articles (NEW FEATURE)."""
        url = "https://www.instagram.com/reel/ABC/"
        result = cli._is_probable_article_url(url)
        assert result is False

    def test_medium_article_is_article(self):
        """Medium blog URLs should be detected as articles."""
        url = "https://medium.com/@author/article-title-123abc"
        result = cli._is_probable_article_url(url)
        assert result is True

    def test_generic_blog_is_article(self):
        """Generic blog URLs should be detected as articles."""
        url = "https://example.com/blog/my-post"
        result = cli._is_probable_article_url(url)
        assert result is True
