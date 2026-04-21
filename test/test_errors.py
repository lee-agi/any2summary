"""Tests for error code module."""

import subprocess
import pytest
from any2summary.errors import (
    ErrorCode,
    ErrorInfo,
    get_error_info,
    map_http_status_to_error,
    create_package_error,
    ERROR_CATALOG,
)


class TestErrorCode:
    """Test ErrorCode enum."""

    def test_error_code_ranges(self):
        """Test error codes are in expected ranges."""
        # Configuration errors: 1000-1099
        assert 1000 <= ErrorCode.ENV_FILE_MISSING < 1100
        assert 1000 <= ErrorCode.AZURE_ENDPOINT_MISSING < 1100
        assert 1000 <= ErrorCode.AZURE_KEY_MISSING < 1100
        assert 1000 <= ErrorCode.AZURE_KEY_INVALID < 1100

        # Dependency errors: 1100-1199
        assert 1100 <= ErrorCode.PYTHON_VERSION_TOO_OLD < 1200
        assert 1100 <= ErrorCode.FFMPEG_NOT_INSTALLED < 1200
        assert 1100 <= ErrorCode.YTDLP_NOT_INSTALLED < 1200
        assert 1100 <= ErrorCode.PACKAGE_MISSING < 1200

        # Network errors: 1200-1299
        assert 1200 <= ErrorCode.AZURE_UNREACHABLE < 1300
        assert 1200 <= ErrorCode.AZURE_RATE_LIMITED < 1300
        assert 1200 <= ErrorCode.AZURE_SERVER_ERROR < 1300

    def test_error_codes_are_unique(self):
        """Test all error codes have unique values."""
        values = [code.value for code in ErrorCode]
        assert len(values) == len(set(values)), "Duplicate error code values found"


class TestErrorCatalog:
    """Test ERROR_CATALOG mappings."""

    def test_all_error_codes_have_catalog_entry(self):
        """Test that all error codes have an entry in ERROR_CATALOG."""
        for code in ErrorCode:
            # Skip PACKAGE_MISSING and OPTIONAL_PACKAGE_MISSING as they are dynamic
            if code in (ErrorCode.PACKAGE_MISSING, ErrorCode.OPTIONAL_PACKAGE_MISSING):
                continue
            assert code in ERROR_CATALOG, f"ErrorCode.{code.name} missing from ERROR_CATALOG"

    def test_catalog_entries_have_required_fields(self):
        """Test all catalog entries have required fields."""
        for code, info in ERROR_CATALOG.items():
            assert isinstance(info, ErrorInfo)
            assert info.code == code
            assert info.message, f"ErrorCode.{code.name} missing message"
            assert info.suggestion, f"ErrorCode.{code.name} missing suggestion"

    def test_auto_fix_functions_exist_for_fixable_errors(self):
        """Test fixable errors have auto_fix functions."""
        fixable_codes = [
            ErrorCode.ENV_FILE_MISSING,
            ErrorCode.FFMPEG_NOT_INSTALLED,
            ErrorCode.YTDLP_NOT_INSTALLED,
        ]
        for code in fixable_codes:
            info = ERROR_CATALOG.get(code)
            assert info is not None, f"ErrorCode.{code.name} not in catalog"
            assert info.auto_fix is not None, f"ErrorCode.{code.name} should have auto_fix"
            assert callable(info.auto_fix), f"ErrorCode.{code.name} auto_fix should be callable"


class TestGetErrorInfo:
    """Test get_error_info function."""

    def test_get_known_error(self):
        """Test getting a known error code."""
        info = get_error_info(ErrorCode.AZURE_ENDPOINT_MISSING)
        assert info.code == ErrorCode.AZURE_ENDPOINT_MISSING
        assert "AZURE_OPENAI_ENDPOINT" in info.message
        assert info.suggestion

    def test_get_unknown_error(self):
        """Test getting an unknown error code returns generic info."""
        # Create a fake error code value
        fake_code = 9999
        info = get_error_info(fake_code)  # type: ignore
        assert "未知错误" in info.message
        assert str(fake_code) in info.message


class TestMapHttpStatusToError:
    """Test HTTP status code mapping."""

    def test_auth_errors(self):
        """Test 401 and 403 map to AZURE_KEY_INVALID."""
        assert map_http_status_to_error(401) == ErrorCode.AZURE_KEY_INVALID
        assert map_http_status_to_error(403) == ErrorCode.AZURE_KEY_INVALID

    def test_bad_request(self):
        """Test 400 maps to AZURE_BAD_REQUEST."""
        assert map_http_status_to_error(400) == ErrorCode.AZURE_BAD_REQUEST

    def test_rate_limited(self):
        """Test 429 maps to AZURE_RATE_LIMITED."""
        assert map_http_status_to_error(429) == ErrorCode.AZURE_RATE_LIMITED

    def test_server_errors(self):
        """Test 5xx errors map to AZURE_SERVER_ERROR."""
        assert map_http_status_to_error(500) == ErrorCode.AZURE_SERVER_ERROR
        assert map_http_status_to_error(502) == ErrorCode.AZURE_SERVER_ERROR
        assert map_http_status_to_error(503) == ErrorCode.AZURE_SERVER_ERROR

    def test_unknown_status(self):
        """Test unknown status codes map to AZURE_UNREACHABLE."""
        assert map_http_status_to_error(404) == ErrorCode.AZURE_UNREACHABLE
        assert map_http_status_to_error(418) == ErrorCode.AZURE_UNREACHABLE


class TestCreatePackageError:
    """Test create_package_error function."""

    def test_create_package_error_basic(self):
        """Test creating a package error with same import and pip name."""
        error = create_package_error("requests")
        assert error.code == ErrorCode.PACKAGE_MISSING
        assert "requests" in error.message
        assert "pip install requests" in error.suggestion
        assert error.auto_fix is not None

    def test_create_package_error_different_names(self):
        """Test creating a package error with different import and pip names."""
        error = create_package_error("youtube_transcript_api", "youtube-transcript-api")
        assert "youtube_transcript_api" in error.message
        assert "pip install youtube-transcript-api" in error.suggestion

    def test_auto_fix_is_callable(self):
        """Test auto_fix function is callable."""
        error = create_package_error("some_package")
        assert callable(error.auto_fix)

    def test_auto_fix_runs_expected_pip_command(self, monkeypatch):
        """Test auto_fix executes pip install command for chosen package."""
        executed = {}

        def fake_run(cmd, **kwargs):
            executed["cmd"] = cmd
            executed["kwargs"] = kwargs

        monkeypatch.setattr(subprocess, "run", fake_run)
        error = create_package_error("youtube_transcript_api", "youtube-transcript-api")

        assert error.auto_fix is not None
        assert error.auto_fix() is True
        assert executed["cmd"][-1] == "youtube-transcript-api"
        assert executed["kwargs"]["check"] is True
        assert executed["kwargs"]["capture_output"] is True
        assert executed["kwargs"]["timeout"] == 120

    def test_auto_fix_returns_false_on_subprocess_error(self, monkeypatch):
        """Test auto_fix handles installer command failures gracefully."""

        def fake_run(*args, **kwargs):
            raise subprocess.CalledProcessError(1, ["pip", "install", "missing-pkg"])

        monkeypatch.setattr(subprocess, "run", fake_run)
        error = create_package_error("missing_pkg", "missing-pkg")

        assert error.auto_fix is not None
        assert error.auto_fix() is False
