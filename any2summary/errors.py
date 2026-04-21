"""Error codes and diagnostic utilities for any2summary.

This module provides a structured error code system with:
- Categorized error codes (config, dependency, network)
- Detailed error information with suggestions
- Auto-fix capabilities for recoverable issues
"""

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Callable, Optional
import subprocess
import sys


class ErrorCode(IntEnum):
    """Error codes organized by category.

    Ranges:
    - 1000-1099: Configuration errors
    - 1100-1199: Dependency errors
    - 1200-1299: Network/connectivity errors
    """

    # Configuration errors (1000-1099)
    ENV_FILE_MISSING = 1001
    AZURE_ENDPOINT_MISSING = 1002
    AZURE_KEY_MISSING = 1003
    AZURE_KEY_INVALID = 1004  # HTTP 401/403
    AZURE_DEPLOYMENT_MISSING = 1005

    # Dependency errors (1100-1199)
    PYTHON_VERSION_TOO_OLD = 1100
    FFMPEG_NOT_INSTALLED = 1101
    YTDLP_NOT_INSTALLED = 1102
    PACKAGE_MISSING = 1103
    OPTIONAL_PACKAGE_MISSING = 1104

    # Network/connectivity errors (1200-1299)
    AZURE_UNREACHABLE = 1201
    AZURE_TIMEOUT = 1202
    AZURE_RATE_LIMITED = 1203  # HTTP 429
    AZURE_SERVER_ERROR = 1204  # HTTP 500+
    AZURE_BAD_REQUEST = 1205  # HTTP 400


@dataclass
class ErrorInfo:
    """Detailed information about an error.

    Attributes:
        code: The error code enum value.
        message: Human-readable error message.
        suggestion: Suggested fix or next step.
        auto_fix: Optional callable that attempts to fix the issue.
                  Returns True if fix was successful, False otherwise.
    """

    code: ErrorCode
    message: str
    suggestion: str
    auto_fix: Optional[Callable[[], bool]] = None


def _fix_env_file() -> bool:
    """Create a template .env file."""
    env_path = Path(".env")
    if env_path.exists():
        return False

    template = """# any2summary Azure OpenAI Configuration
# Created by `any2summary doctor --fix`

# Required: Your Azure OpenAI endpoint
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com

# Required: Your Azure OpenAI API key
AZURE_OPENAI_API_KEY=your-api-key-here

# Optional: Deployment names (defaults will be used if not set)
# AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT=whisper
# AZURE_OPENAI_SUMMARY_DEPLOYMENT=gpt-4o
"""
    try:
        env_path.write_text(template, encoding="utf-8")
        return True
    except Exception:
        return False


def _run_command(command: list[str], timeout: int) -> bool:
    """Run a command and return whether it succeeded.

    This centralizes subprocess invocation so auto-fix handlers share
    consistent behaviour and are easier to maintain/test.
    """
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            timeout=timeout,
        )
        return True
    except Exception:
        return False


def _fix_ffmpeg() -> bool:
    """Attempt to install ffmpeg via common package managers."""
    if sys.platform == "darwin":
        return _run_command(["brew", "install", "ffmpeg"], timeout=300)
    if sys.platform == "linux":
        return _run_command(["sudo", "apt-get", "install", "-y", "ffmpeg"], timeout=300)
    return False


def _fix_ytdlp() -> bool:
    """Install yt-dlp via pip."""
    return _run_command([sys.executable, "-m", "pip", "install", "yt-dlp"], timeout=120)


def _make_package_fixer(package_name: str) -> Callable[[], bool]:
    """Create a fixer function for a specific pip package."""

    def fixer() -> bool:
        return _run_command([sys.executable, "-m", "pip", "install", package_name], timeout=120)

    return fixer


# Error catalog mapping error codes to detailed information
ERROR_CATALOG: dict[ErrorCode, ErrorInfo] = {
    ErrorCode.ENV_FILE_MISSING: ErrorInfo(
        code=ErrorCode.ENV_FILE_MISSING,
        message=".env 配置文件不存在",
        suggestion="运行 `any2summary init` 或 `any2summary doctor --fix` 创建配置文件",
        auto_fix=_fix_env_file,
    ),
    ErrorCode.AZURE_ENDPOINT_MISSING: ErrorInfo(
        code=ErrorCode.AZURE_ENDPOINT_MISSING,
        message="AZURE_OPENAI_ENDPOINT 环境变量未设置",
        suggestion="在 .env 文件中设置 AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com",
        auto_fix=None,
    ),
    ErrorCode.AZURE_KEY_MISSING: ErrorInfo(
        code=ErrorCode.AZURE_KEY_MISSING,
        message="AZURE_OPENAI_API_KEY 环境变量未设置",
        suggestion="在 .env 文件中设置 AZURE_OPENAI_API_KEY=your-api-key",
        auto_fix=None,
    ),
    ErrorCode.AZURE_KEY_INVALID: ErrorInfo(
        code=ErrorCode.AZURE_KEY_INVALID,
        message="Azure API 密钥无效或已过期",
        suggestion="检查 API 密钥是否正确，或在 Azure Portal 重新生成",
        auto_fix=None,
    ),
    ErrorCode.AZURE_DEPLOYMENT_MISSING: ErrorInfo(
        code=ErrorCode.AZURE_DEPLOYMENT_MISSING,
        message="Azure 部署名称未设置",
        suggestion="在 .env 文件中设置 AZURE_OPENAI_SUMMARY_DEPLOYMENT 或 AZURE_OPENAI_TRANSCRIPTION_DEPLOYMENT",
        auto_fix=None,
    ),
    ErrorCode.PYTHON_VERSION_TOO_OLD: ErrorInfo(
        code=ErrorCode.PYTHON_VERSION_TOO_OLD,
        message="Python 版本过低",
        suggestion="请升级到 Python 3.10 或更高版本",
        auto_fix=None,
    ),
    ErrorCode.FFMPEG_NOT_INSTALLED: ErrorInfo(
        code=ErrorCode.FFMPEG_NOT_INSTALLED,
        message="ffmpeg 未安装",
        suggestion="macOS: brew install ffmpeg | Linux: sudo apt install ffmpeg | Windows: 下载安装包",
        auto_fix=_fix_ffmpeg,
    ),
    ErrorCode.YTDLP_NOT_INSTALLED: ErrorInfo(
        code=ErrorCode.YTDLP_NOT_INSTALLED,
        message="yt-dlp 未安装",
        suggestion="运行 pip install yt-dlp",
        auto_fix=_fix_ytdlp,
    ),
    ErrorCode.AZURE_UNREACHABLE: ErrorInfo(
        code=ErrorCode.AZURE_UNREACHABLE,
        message="无法连接到 Azure OpenAI 端点",
        suggestion="检查网络连接和 AZURE_OPENAI_ENDPOINT 配置",
        auto_fix=None,
    ),
    ErrorCode.AZURE_TIMEOUT: ErrorInfo(
        code=ErrorCode.AZURE_TIMEOUT,
        message="连接 Azure OpenAI 超时",
        suggestion="检查网络连接，或稍后重试",
        auto_fix=None,
    ),
    ErrorCode.AZURE_RATE_LIMITED: ErrorInfo(
        code=ErrorCode.AZURE_RATE_LIMITED,
        message="Azure OpenAI 请求速率限制 (HTTP 429)",
        suggestion="等待一段时间后重试，或提升 Azure 配额",
        auto_fix=None,
    ),
    ErrorCode.AZURE_SERVER_ERROR: ErrorInfo(
        code=ErrorCode.AZURE_SERVER_ERROR,
        message="Azure OpenAI 服务器错误 (HTTP 5xx)",
        suggestion="Azure 服务可能暂时不可用，请稍后重试",
        auto_fix=None,
    ),
    ErrorCode.AZURE_BAD_REQUEST: ErrorInfo(
        code=ErrorCode.AZURE_BAD_REQUEST,
        message="Azure OpenAI 请求格式错误 (HTTP 400)",
        suggestion="检查 API 版本和部署名称配置",
        auto_fix=None,
    ),
}


def get_error_info(code: ErrorCode) -> ErrorInfo:
    """Get detailed information for an error code.

    Args:
        code: The error code to look up.

    Returns:
        ErrorInfo with details, or a generic error if code not found.
    """
    return ERROR_CATALOG.get(
        code,
        ErrorInfo(
            code=code,
            message=f"未知错误 (代码: {code})",
            suggestion="请检查日志获取更多信息",
            auto_fix=None,
        ),
    )


def map_http_status_to_error(status_code: int) -> ErrorCode:
    """Map HTTP status code to appropriate error code.

    Args:
        status_code: HTTP response status code.

    Returns:
        Corresponding ErrorCode for the HTTP status.
    """
    if status_code in {401, 403}:
        return ErrorCode.AZURE_KEY_INVALID
    if status_code == 400:
        return ErrorCode.AZURE_BAD_REQUEST
    if status_code == 429:
        return ErrorCode.AZURE_RATE_LIMITED
    if status_code >= 500:
        return ErrorCode.AZURE_SERVER_ERROR
    return ErrorCode.AZURE_UNREACHABLE


def create_package_error(package_name: str, pip_name: str | None = None) -> ErrorInfo:
    """Create an ErrorInfo for a missing package.

    Args:
        package_name: The import name of the package.
        pip_name: The pip install name (defaults to package_name).

    Returns:
        ErrorInfo with auto-fix capability.
    """
    install_name = pip_name or package_name
    return ErrorInfo(
        code=ErrorCode.PACKAGE_MISSING,
        message=f"Python 包 {package_name} 未安装",
        suggestion=f"运行 pip install {install_name}",
        auto_fix=_make_package_fixer(install_name),
    )
