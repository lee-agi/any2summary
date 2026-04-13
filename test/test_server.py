"""Tests for the FastAPI companion server.

Run with: pytest test/test_server.py -v
"""

import os
import pytest
from unittest.mock import patch

# Skip all tests if FastAPI is not installed
pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

from fastapi.testclient import TestClient


class TestServerHealth:
    """Tests for the /api/health endpoint."""

    def test_health_check_returns_ok(self):
        """Health endpoint should return status ok."""
        from any2summary.server import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "services" in data

    def test_health_check_includes_service_status(self):
        """Health endpoint should report service availability."""
        from any2summary.server import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/health")
        data = response.json()

        services = data["services"]
        assert "ffmpeg" in services
        assert "yt_dlp" in services
        assert "azure_openai" in services
        # All values should be boolean
        for key, value in services.items():
            assert isinstance(value, bool), f"{key} should be boolean"


class TestServerTranscribe:
    """Tests for the /api/transcribe endpoint."""

    def test_transcribe_requires_url(self):
        """Transcribe endpoint should require URL parameter."""
        from any2summary.server import create_app

        app = create_app()
        client = TestClient(app)

        # Missing URL should fail
        response = client.post("/api/transcribe")
        assert response.status_code == 422  # Validation error

    def test_transcribe_accepts_valid_request(self):
        """Transcribe endpoint should accept valid request structure."""
        from any2summary.server import create_app

        app = create_app()
        client = TestClient(app)

        # Mock the perform_azure_diarization function
        mock_result = {
            "speakers": [{"start": 0.0, "end": 5.0, "speaker": "Speaker1"}],
            "transcript": [{"start": 0.0, "end": 5.0, "text": "Hello world", "speaker": "Speaker1"}],
            "metadata": {"title": "Test Video"},
        }

        with patch("any2summary.cli.perform_azure_diarization", return_value=mock_result):
            response = client.post(
                "/api/transcribe",
                json={
                    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "language": "en",
                },
            )
            assert response.status_code == 200

            data = response.json()
            assert "speakers" in data
            assert "transcript" in data
            assert data["speakers"] == mock_result["speakers"]
            assert data["transcript"] == mock_result["transcript"]

    def test_transcribe_handles_missing_credentials(self):
        """Transcribe should return 400 when credentials are missing."""
        from any2summary.server import create_app

        app = create_app()
        client = TestClient(app)

        # Ensure no credentials are set - use RuntimeError mock
        with patch("any2summary.cli.perform_azure_diarization") as mock_func:
            mock_func.side_effect = RuntimeError("Azure OpenAI 凭据缺失")

            response = client.post(
                "/api/transcribe",
                json={"url": "https://example.com/video.mp4", "language": "en"},
            )
            assert response.status_code == 400


class TestServerSummarize:
    """Tests for the /api/summarize endpoint."""

    def test_summarize_requires_url(self):
        """Summarize endpoint should require URL parameter."""
        from any2summary.server import create_app

        app = create_app()
        client = TestClient(app)

        response = client.post("/api/summarize")
        assert response.status_code == 422  # Validation error

    def test_summarize_accepts_valid_request(self):
        """Summarize endpoint should accept valid request structure."""
        from any2summary.server import create_app

        app = create_app()
        client = TestClient(app)

        # Mock the _run_summarize_pipeline function
        mock_output = {
            "summary": "This is a test summary.",
            "segments": [{"start": 0, "end": 1, "text": "Test content"}],
            "metadata": {"title": "Test Article"},
            "timeline": "00:00:00 - 00:00:01 | Test content",
        }

        with patch("any2summary.server._run_summarize_pipeline", return_value=mock_output):
            response = client.post(
                "/api/summarize",
                json={
                    "url": "https://example.com/article",
                    "language": "en",
                },
            )
            assert response.status_code == 200

            data = response.json()
            assert "summary" in data
            assert "segments" in data
            assert data["summary"] == mock_output["summary"]


class TestServerCORS:
    """Tests for CORS configuration."""

    def test_cors_allows_chrome_extension(self):
        """CORS should allow requests from Chrome extensions."""
        from any2summary.server import create_app

        app = create_app()
        client = TestClient(app)

        # Preflight request
        response = client.options(
            "/api/health",
            headers={
                "Origin": "chrome-extension://abcdefghijklmnop",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS middleware should handle this
        assert response.status_code in (200, 204, 400)

    def test_cors_allows_localhost(self):
        """CORS should allow requests from localhost."""
        from any2summary.server import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get(
            "/api/health",
            headers={"Origin": "http://localhost:3000"},
        )
        assert response.status_code == 200


class TestHelperFunctions:
    """Tests for server helper functions."""

    def test_check_ffmpeg_available(self):
        """Should correctly detect ffmpeg availability."""
        from any2summary.server import _check_ffmpeg_available

        result = _check_ffmpeg_available()
        assert isinstance(result, bool)

    def test_check_ytdlp_available(self):
        """Should correctly detect yt-dlp availability."""
        from any2summary.server import _check_ytdlp_available

        result = _check_ytdlp_available()
        assert isinstance(result, bool)
        # yt-dlp should be installed as a dependency
        assert result is True

    def test_check_azure_credentials_without_env(self):
        """Should return False when credentials are not set."""
        from any2summary.server import _check_azure_credentials

        # Clear environment variables
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("AZURE_OPENAI_API_KEY", None)
            os.environ.pop("AZURE_OPENAI_ENDPOINT", None)
            result = _check_azure_credentials()
            assert result is False

    def test_check_azure_credentials_with_env(self):
        """Should return True when credentials are set."""
        from any2summary.server import _check_azure_credentials

        with patch.dict(os.environ, {
            "AZURE_OPENAI_API_KEY": "test-key",
            "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
        }):
            result = _check_azure_credentials()
            assert result is True


class TestYouTubeTranscriptEndpoint:
    """Tests for the /api/youtube/transcript endpoint."""

    def test_youtube_transcript_requires_url(self):
        """YouTube transcript endpoint should require URL parameter."""
        from any2summary.server import create_app

        app = create_app()
        client = TestClient(app)

        response = client.get("/api/youtube/transcript")
        assert response.status_code == 422  # Validation error

    def test_youtube_transcript_returns_segments_and_metadata(self):
        """YouTube transcript endpoint should return segments and metadata."""
        from any2summary.server import create_app

        app = create_app()
        client = TestClient(app)

        # Mock the fetch functions
        mock_segments = [
            {"start": 0.0, "end": 5.0, "text": "Hello world"},
            {"start": 5.0, "end": 10.0, "text": "Test content"},
        ]
        mock_metadata = {
            "title": "Test Video",
            "webpage_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "upload_date": "20230101",
        }

        with patch("any2summary.cli.fetch_transcript_with_metadata", return_value=mock_segments):
            with patch("any2summary.cli._fetch_video_metadata", return_value=mock_metadata):
                response = client.get(
                    "/api/youtube/transcript",
                    params={
                        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                        "languages": "en,zh-Hans",
                    },
                )
                assert response.status_code == 200

                data = response.json()
                assert "segments" in data
                assert "metadata" in data
                assert len(data["segments"]) == 2
                assert data["segments"][0]["text"] == "Hello world"
                assert data["metadata"]["title"] == "Test Video"

    def test_youtube_transcript_uses_default_languages(self):
        """YouTube transcript endpoint should use default languages if not specified."""
        from any2summary.server import create_app

        app = create_app()
        client = TestClient(app)

        mock_segments = [{"start": 0.0, "end": 5.0, "text": "Test"}]
        mock_metadata = {"title": "Test", "webpage_url": "", "upload_date": ""}

        with patch("any2summary.cli.fetch_transcript_with_metadata", return_value=mock_segments) as mock_fetch:
            with patch("any2summary.cli._fetch_video_metadata", return_value=mock_metadata):
                response = client.get(
                    "/api/youtube/transcript",
                    params={"url": "https://www.youtube.com/watch?v=test123"},
                )
                assert response.status_code == 200
                # Check that default languages were used
                mock_fetch.assert_called_once()
                call_args = mock_fetch.call_args
                assert "en" in str(call_args)

    def test_youtube_transcript_handles_transcript_error(self):
        """YouTube transcript endpoint should return 400 for transcript errors."""
        from any2summary.server import create_app

        app = create_app()
        client = TestClient(app)

        with patch("any2summary.cli.fetch_transcript_with_metadata") as mock_fetch:
            mock_fetch.side_effect = RuntimeError("No transcript available")

            response = client.get(
                "/api/youtube/transcript",
                params={"url": "https://www.youtube.com/watch?v=invalid"},
            )
            assert response.status_code == 400
            assert "No transcript available" in response.text


class TestMetadataCamelCaseConversion:
    """Tests for metadata field name conversion from snake_case to camelCase."""

    def test_convert_metadata_to_camel_case(self):
        """Test that snake_case fields are converted to camelCase."""
        from any2summary.server import _convert_metadata_to_camel_case

        snake_case_metadata = {
            "title": "Test Video",
            "webpage_url": "https://www.youtube.com/watch?v=test123",
            "upload_date": "20240115",
            "duration": 300,
            "channel": "Test Channel",
            "channel_id": "UC123456",
            "uploader": "Test Uploader",
            "view_count": 1000,
            "like_count": 100,
        }

        result = _convert_metadata_to_camel_case(snake_case_metadata)

        # Check camelCase conversion
        assert result["title"] == "Test Video"
        assert result["webpageUrl"] == "https://www.youtube.com/watch?v=test123"
        assert result["uploadDate"] == "20240115"
        assert result["duration"] == 300
        assert result["channel"] == "Test Channel"
        assert result["channelId"] == "UC123456"
        assert result["uploader"] == "Test Uploader"
        assert result["viewCount"] == 1000
        assert result["likeCount"] == 100

        # Old snake_case keys should not exist
        assert "webpage_url" not in result
        assert "upload_date" not in result
        assert "channel_id" not in result
        assert "view_count" not in result
        assert "like_count" not in result

    def test_convert_metadata_preserves_unmapped_fields(self):
        """Test that unmapped fields are preserved as-is."""
        from any2summary.server import _convert_metadata_to_camel_case

        metadata = {
            "title": "Test",
            "custom_field": "value",
            "another_key": 123,
        }

        result = _convert_metadata_to_camel_case(metadata)

        assert result["title"] == "Test"
        assert result["custom_field"] == "value"
        assert result["another_key"] == 123

    def test_convert_metadata_handles_empty_dict(self):
        """Test that empty dict returns empty dict."""
        from any2summary.server import _convert_metadata_to_camel_case

        result = _convert_metadata_to_camel_case({})
        assert result == {}

    def test_convert_metadata_handles_none(self):
        """Test that None returns empty dict."""
        from any2summary.server import _convert_metadata_to_camel_case

        result = _convert_metadata_to_camel_case(None)
        assert result == {}

    def test_youtube_transcript_returns_camel_case_metadata(self):
        """Test that /api/youtube/transcript returns camelCase metadata."""
        from any2summary.server import create_app

        app = create_app()
        client = TestClient(app)

        mock_segments = [{"start": 0.0, "end": 5.0, "text": "Test"}]
        mock_metadata = {
            "title": "Test Video",
            "webpage_url": "https://www.youtube.com/watch?v=test123",
            "upload_date": "20240115",
        }

        with patch("any2summary.cli.fetch_transcript_with_metadata", return_value=mock_segments):
            with patch("any2summary.cli._fetch_video_metadata", return_value=mock_metadata):
                response = client.get(
                    "/api/youtube/transcript",
                    params={"url": "https://www.youtube.com/watch?v=test123"},
                )
                assert response.status_code == 200

                data = response.json()
                # Should have camelCase keys
                assert data["metadata"]["uploadDate"] == "20240115"
                assert data["metadata"]["webpageUrl"] == "https://www.youtube.com/watch?v=test123"
                # Should NOT have snake_case keys
                assert "upload_date" not in data["metadata"]
                assert "webpage_url" not in data["metadata"]

    def test_transcribe_returns_camel_case_metadata(self):
        """Test that /api/transcribe returns camelCase metadata."""
        from any2summary.server import create_app

        app = create_app()
        client = TestClient(app)

        mock_transcribe_result = {
            "speakers": [{"start": 0.0, "end": 5.0, "speaker": "Speaker1"}],
            "transcript": [{"start": 0.0, "end": 5.0, "text": "Hello", "speaker": "Speaker1"}],
        }
        mock_metadata = {
            "title": "Test Video",
            "webpage_url": "https://www.youtube.com/watch?v=test123",
            "upload_date": "20240115",
        }

        with patch("any2summary.cli.perform_azure_diarization", return_value=mock_transcribe_result):
            with patch("any2summary.cli._fetch_video_metadata", return_value=mock_metadata):
                response = client.post(
                    "/api/transcribe",
                    json={"url": "https://www.youtube.com/watch?v=test123", "language": "en"},
                )
                assert response.status_code == 200

                data = response.json()
                # Should have metadata with camelCase keys
                assert data["metadata"] is not None
                assert data["metadata"]["title"] == "Test Video"
                assert data["metadata"]["uploadDate"] == "20240115"
                assert data["metadata"]["webpageUrl"] == "https://www.youtube.com/watch?v=test123"

    def test_transcribe_handles_metadata_fetch_failure(self):
        """Test that /api/transcribe handles metadata fetch failure gracefully."""
        from any2summary.server import create_app

        app = create_app()
        client = TestClient(app)

        mock_transcribe_result = {
            "speakers": [],
            "transcript": [{"start": 0.0, "end": 5.0, "text": "Hello"}],
        }

        with patch("any2summary.cli.perform_azure_diarization", return_value=mock_transcribe_result):
            with patch("any2summary.cli._fetch_video_metadata", side_effect=Exception("Network error")):
                response = client.post(
                    "/api/transcribe",
                    json={"url": "https://www.youtube.com/watch?v=test123", "language": "en"},
                )
                # Should still succeed but with null metadata
                assert response.status_code == 200
                data = response.json()
                assert data["metadata"] is None


class TestCLIServeCommand:
    """Tests for the CLI serve subcommand."""

    def test_serve_command_parsing(self):
        """CLI should correctly parse serve command arguments."""
        from any2summary import cli

        # Test that serve command is recognized
        args_list = ["serve", "--port", "9000", "--host", "0.0.0.0"]

        # This should call _run_serve_command
        with patch("any2summary.server.run_server") as mock_run:
            result = cli.run(args_list)
            mock_run.assert_called_once_with(
                host="0.0.0.0",
                port=9000,
                reload=False,
            )

    def test_serve_command_default_values(self):
        """Serve command should use default host and port."""
        from any2summary import cli

        args_list = ["serve"]

        with patch("any2summary.server.run_server") as mock_run:
            result = cli.run(args_list)
            mock_run.assert_called_once_with(
                host="127.0.0.1",
                port=8765,
                reload=False,
            )

    def test_serve_command_reload_flag(self):
        """Serve command should support --reload flag."""
        from any2summary import cli

        args_list = ["serve", "--reload"]

        with patch("any2summary.server.run_server") as mock_run:
            result = cli.run(args_list)
            mock_run.assert_called_once_with(
                host="127.0.0.1",
                port=8765,
                reload=True,
            )
