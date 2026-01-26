"""Tests for fileSaver.js generateFilename function.

Uses Node.js to execute the actual JavaScript code and verify filename generation.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


CHROME_EXT_SRC = Path("chrome_extension/src")


def run_generate_filename(
    url: str, title: str, metadata: dict | None = None
) -> str:
    """Run generateFilename through Node.js and return the result.

    Args:
        url: Page URL
        title: Page title
        metadata: Optional metadata dict with publishDate, uploadDate, etc.

    Returns:
        Generated filename matching cli.py format:
        【{domain}】{title}-{year}-M{month}_summary.md
    """
    metadata_json = json.dumps(metadata or {})
    js_code = f"""
    {(CHROME_EXT_SRC / "fileSaver.js").read_text(encoding="utf-8")}

    // Override Date for predictable fallback
    const originalDate = Date;
    global.Date = class extends originalDate {{
        constructor(...args) {{
            if (args.length === 0) {{
                super(2025, 0, 23, 10, 30, 45);  // Jan 23, 2025
            }} else {{
                super(...args);
            }}
        }}
        static now() {{
            return new originalDate(2025, 0, 23, 10, 30, 45).getTime();
        }}
    }};

    const metadata = {metadata_json};
    const result = generateFilename({json.dumps(url)}, {json.dumps(title)}, metadata);
    console.log(result);
    """

    # Remove export statement for Node.js compatibility
    js_code = js_code.replace("export async function saveSummaryAsMarkdown",
                              "async function saveSummaryAsMarkdown")

    result = subprocess.run(
        ["node", "-e", js_code],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class TestGenerateFilenameWithSpecialChars:
    """Test filename generation with special characters.

    New format: 【{domain}】{title}-{year}-M{month}_summary.md
    Uses blacklist cleaning (removes illegal chars and spaces).
    """

    def test_emoji_in_title(self) -> None:
        """Test that emoji characters are removed."""
        filename = run_generate_filename(
            "https://youtube.com/watch?v=abc123",
            "🎬 视频标题 #1",
            {"publishDate": "2024-01-15"}
        )
        # Should not contain emoji, # symbol, or spaces
        assert "🎬" not in filename
        assert "#" not in filename
        assert " " not in filename
        # Should contain Chinese characters and domain
        assert "视频标题" in filename
        assert "【YouTube】" in filename
        assert "2024-M01" in filename
        assert filename.endswith("_summary.md")

    def test_programming_symbols_in_title(self) -> None:
        """Test that programming-related symbols are handled."""
        filename = run_generate_filename(
            "https://example.com",
            "C++ & Java: 100% Guide",
            {"publishDate": "2024-03-20"}
        )
        # Special chars should be removed (blacklist: \/:*?"<>|`)
        assert ":" not in filename
        # Spaces should be removed
        assert " " not in filename
        # Core text should remain (concatenated without spaces)
        assert "CJava100Guide" in filename or "C++&Java" in filename
        assert filename.endswith("_summary.md")

    def test_zero_width_and_control_chars(self) -> None:
        """Test that zero-width and control characters are removed."""
        filename = run_generate_filename(
            "https://example.com",
            "Title\u200b\u200cwith\x00hidden\x1fchars"
        )
        # Zero-width chars should be removed
        assert "\u200b" not in filename
        assert "\u200c" not in filename
        # Control chars should be removed
        assert "\x00" not in filename
        assert "\x1f" not in filename
        # Valid parts should remain (no spaces)
        assert "Titlewithhiddenchars" in filename
        assert filename.endswith("_summary.md")

    def test_spaces_removed_not_replaced(self) -> None:
        """Test that spaces are removed entirely (cli.py behavior)."""
        filename = run_generate_filename(
            "https://example.com",
            "A B C"
        )
        # Spaces should be removed, not replaced with underscores
        assert " " not in filename
        assert "ABC" in filename


class TestGenerateFilenameEdgeCases:
    """Test edge cases in filename generation."""

    def test_empty_title_uses_summary_fallback(self) -> None:
        """Test that empty title uses 'summary' as fallback."""
        filename = run_generate_filename(
            "https://example.com/page/article",
            ""
        )
        # Should use "summary" as fallback for title
        assert "summary" in filename
        assert filename.endswith("_summary.md")

    def test_whitespace_only_title(self) -> None:
        """Test that whitespace-only title falls back to 'summary'."""
        filename = run_generate_filename(
            "https://test.com/path",
            "   \t\n  "
        )
        # Should fall back to "summary"
        assert "summary" in filename

    def test_all_special_chars_title(self) -> None:
        """Test that title with only special chars falls back to 'summary'."""
        filename = run_generate_filename(
            "https://fallback.org/page",
            "!@#$%^&*()"
        )
        # Should fall back to "summary"
        assert "summary" in filename

    def test_long_title_truncated(self) -> None:
        """Test that very long titles are truncated."""
        long_title = "A" * 200
        filename = run_generate_filename(
            "https://example.com",
            long_title
        )
        # Title part should be truncated to ~100 chars
        # Full format: 【domain】title-year-Mmonth_summary.md
        assert len(filename) < 200


class TestGenerateFilenameInternational:
    """Test international character support."""

    def test_chinese_title(self) -> None:
        """Test that Chinese characters are preserved."""
        filename = run_generate_filename(
            "https://bilibili.com/video/BV123",
            "这是一个中文标题",
            {"publishDate": "2024-06-15"}
        )
        assert "这是一个中文标题" in filename
        assert "【Bilibili】" in filename
        assert "2024-M06" in filename
        assert filename.endswith("_summary.md")

    def test_japanese_title(self) -> None:
        """Test that Japanese characters are preserved."""
        filename = run_generate_filename(
            "https://example.com",
            "日本語のタイトル"
        )
        # Japanese characters should be preserved
        assert "日本語のタイトル" in filename
        assert filename.endswith("_summary.md")

    def test_korean_title(self) -> None:
        """Test that Korean characters are preserved (spaces removed)."""
        filename = run_generate_filename(
            "https://example.com",
            "한국어 제목입니다"
        )
        # Spaces should be removed
        assert "한국어제목입니다" in filename
        assert filename.endswith("_summary.md")

    def test_mixed_language_title(self) -> None:
        """Test mixed language title (spaces removed)."""
        filename = run_generate_filename(
            "https://example.com",
            "Hello 世界 こんにちは"
        )
        # Spaces should be removed
        assert "Hello世界こんにちは" in filename
        assert filename.endswith("_summary.md")


class TestGenerateFilenameFormat:
    """Test filename format and structure.

    New format: 【{domain}】{title}-{year}-M{month}_summary.md
    """

    def test_format_with_publish_date(self) -> None:
        """Test filename format with publish date from metadata."""
        filename = run_generate_filename(
            "https://youtube.com/watch?v=test123",
            "Test Video Title",
            {"publishDate": "2024-05-20"}
        )
        # Should match: 【YouTube】TestVideoTitle-2024-M05_summary.md
        assert "【YouTube】" in filename
        assert "TestVideoTitle" in filename
        assert "2024-M05" in filename
        assert filename.endswith("_summary.md")

    def test_format_with_upload_date_fallback(self) -> None:
        """Test that uploadDate is used when publishDate is absent."""
        filename = run_generate_filename(
            "https://youtube.com/watch?v=test",
            "Video",
            {"uploadDate": "2023-12-25"}
        )
        assert "2023-M12" in filename

    def test_format_without_date_uses_current(self) -> None:
        """Test that current date is used when no date in metadata."""
        filename = run_generate_filename(
            "https://example.com",
            "Test"
        )
        # Mock date is 2025-01-23, so should be 2025-M01
        assert "2025-M01" in filename

    def test_ends_with_summary_md(self) -> None:
        """Test that filename ends with _summary.md."""
        filename = run_generate_filename(
            "https://example.com",
            "Test"
        )
        assert filename.endswith("_summary.md")

    def test_no_timestamp_in_filename(self) -> None:
        """Test that there's no ISO timestamp in filename (differs from old behavior)."""
        filename = run_generate_filename(
            "https://example.com",
            "Test Title"
        )
        # Should NOT have ISO-like timestamp format
        assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}", filename)


class TestInvalidFilenameEdgeCases:
    """Test edge cases that may cause Chrome 'Invalid filename' error.

    Chrome downloads API rejects filenames that:
    - Start with a dot (e.g., '.hidden')
    - Consist only of dots (e.g., '...')
    - Consist only of dots and dashes (e.g., '.-.-')
    - Are empty

    New format uses 【domain】 prefix which helps avoid these issues.
    """

    def test_title_only_dots(self) -> None:
        """Test that title with only dots doesn't produce invalid filename."""
        filename = run_generate_filename(
            "https://example.com/page",
            "..."
        )
        # Should have domain prefix, so won't start with dot
        assert filename.startswith("【")
        assert filename.endswith("_summary.md")

    def test_title_dots_and_dashes_only(self) -> None:
        """Test that title with only dots and dashes uses fallback."""
        filename = run_generate_filename(
            "https://example.com/article",
            ".-.-.-"
        )
        # Title should fall back to "summary"
        assert "summary" in filename
        assert filename.startswith("【")

    def test_title_starts_with_dot(self) -> None:
        """Test that title starting with dot is handled."""
        filename = run_generate_filename(
            "https://example.com",
            ".hidden_file_name"
        )
        # Filename starts with domain prefix, not dot
        assert filename.startswith("【")
        # Dot should be removed from title
        assert "hiddenfilename" in filename.lower() or "summary" in filename.lower()

    def test_title_only_dashes(self) -> None:
        """Test that title with only dashes falls back properly."""
        filename = run_generate_filename(
            "https://fallback.org/path",
            "---"
        )
        # Should fall back to "summary" for title part
        assert "summary" in filename

    def test_url_fallback_also_invalid(self) -> None:
        """Test when title is invalid, fallback to 'summary'."""
        filename = run_generate_filename(
            "https://example.com/",
            "..."
        )
        # Title should fall back to "summary"
        assert "summary" in filename
        assert filename.startswith("【")


class TestFileSaverModuleStructure:
    """Test fileSaver.js module structure."""

    def test_file_exists(self) -> None:
        """Verify fileSaver.js exists."""
        module_path = CHROME_EXT_SRC / "fileSaver.js"
        assert module_path.is_file(), "fileSaver.js should exist"

    def test_exports_save_function(self) -> None:
        """Verify fileSaver.js exports saveSummaryAsMarkdown."""
        module_path = CHROME_EXT_SRC / "fileSaver.js"
        content = module_path.read_text(encoding="utf-8")
        assert "export async function saveSummaryAsMarkdown" in content

    def test_has_extract_domain_function(self) -> None:
        """Verify generateFilename uses extractDomain helper."""
        module_path = CHROME_EXT_SRC / "fileSaver.js"
        content = module_path.read_text(encoding="utf-8")
        assert "extractDomain" in content, "Should have extractDomain function"

    def test_has_derive_year_month_function(self) -> None:
        """Verify generateFilename uses deriveYearMonth helper."""
        module_path = CHROME_EXT_SRC / "fileSaver.js"
        content = module_path.read_text(encoding="utf-8")
        assert "deriveYearMonth" in content, "Should have deriveYearMonth function"

    def test_uses_blacklist_regex(self) -> None:
        """Verify sanitizeFilenameBase uses blacklist regex (cli.py style)."""
        module_path = CHROME_EXT_SRC / "fileSaver.js"
        content = module_path.read_text(encoding="utf-8")
        # Should use blacklist pattern for illegal chars
        assert "sanitizeFilenameBase" in content, "Should have sanitizeFilenameBase function"

    def test_has_fallback_logic(self) -> None:
        """Verify generateFilename has fallback for empty results."""
        module_path = CHROME_EXT_SRC / "fileSaver.js"
        content = module_path.read_text(encoding="utf-8")
        # Should have fallback to "summary"
        assert '"summary"' in content, "Should have fallback to 'summary'"


def run_sanitize_subdirectory(subdirectory: str) -> str:
    """Run sanitizeSubdirectory through Node.js and return the result.

    Args:
        subdirectory: The subdirectory path to sanitize

    Returns:
        Sanitized subdirectory path
    """
    js_code = f"""
    {(CHROME_EXT_SRC / "fileSaver.js").read_text(encoding="utf-8")}

    const result = sanitizeSubdirectory({json.dumps(subdirectory)});
    console.log(result);
    """

    # Remove export statement for Node.js compatibility
    js_code = js_code.replace("export async function saveSummaryAsMarkdown",
                              "async function saveSummaryAsMarkdown")

    result = subprocess.run(
        ["node", "-e", js_code],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


class TestSubdirectoryValidation:
    """Test subdirectory path sanitization for Chrome downloads API compatibility.

    Chrome downloads API restrictions:
    - Only accepts relative paths (relative to Downloads folder)
    - Path cannot start with / (absolute path)
    - Path/filename cannot start with . (hidden files/directories)
    - Path cannot contain .. (directory traversal)
    """

    def test_absolute_path_converted_to_relative(self) -> None:
        """Test that absolute paths are converted to relative paths."""
        result = run_sanitize_subdirectory("/Users/clzhang/cache/any2summary")
        assert not result.startswith("/"), f"Result should not start with /: {result}"
        assert "Users" in result and "clzhang" in result

    def test_hidden_directory_sanitized(self) -> None:
        """Test that directories starting with . are removed."""
        result = run_sanitize_subdirectory("/Users/clzhang/.cache/any2summary")
        assert ".cache" not in result, f"Hidden directory should be removed: {result}"
        # Should still have valid parts or fallback
        assert result, "Result should not be empty"

    def test_path_traversal_removed(self) -> None:
        """Test that .. directory traversal is removed."""
        result = run_sanitize_subdirectory("any2summary/../../../etc/passwd")
        assert ".." not in result, f"Directory traversal should be removed: {result}"
        # After removing .., the result should be a safe relative path
        # "any2summary/etc/passwd" is safe - it's relative to Downloads folder
        assert result == "any2summary/etc/passwd"

    def test_valid_relative_path_unchanged(self) -> None:
        """Test that valid relative paths are preserved."""
        result = run_sanitize_subdirectory("any2summary")
        assert result == "any2summary"

    def test_valid_nested_relative_path(self) -> None:
        """Test that valid nested relative paths are preserved."""
        result = run_sanitize_subdirectory("summaries/2025/january")
        assert result == "summaries/2025/january"

    def test_empty_path_uses_default(self) -> None:
        """Test that empty path returns default value."""
        result = run_sanitize_subdirectory("")
        assert result == "any2summary", f"Empty path should use default: {result}"

    def test_all_hidden_directories_uses_default(self) -> None:
        """Test that path with only hidden directories uses default."""
        result = run_sanitize_subdirectory("/.hidden/.another")
        assert result == "any2summary", f"All-hidden path should use default: {result}"

    def test_multiple_leading_slashes(self) -> None:
        """Test that multiple leading slashes are handled."""
        result = run_sanitize_subdirectory("///path/to/dir")
        assert not result.startswith("/"), f"Should remove leading slashes: {result}"
        assert "path" in result

    def test_real_user_case_absolute_with_hidden(self) -> None:
        """Test the actual user case: absolute path with .cache directory."""
        result = run_sanitize_subdirectory("/Users/clzhang/.cache/any2summary")
        assert not result.startswith("/"), "Should not start with /"
        assert ".cache" not in result, "Should not contain .cache"
        # The path should be sanitized to either keep valid parts or fallback
        # Valid parts would be: Users/clzhang/any2summary (without .cache)
        # Or fallback to: any2summary
        assert result, "Should have a non-empty result"


class TestDomainMapping:
    """Test domain extraction and mapping to friendly names."""

    def test_youtube_domain_mapping(self) -> None:
        """Test YouTube domain is mapped to 'YouTube'."""
        filename = run_generate_filename(
            "https://www.youtube.com/watch?v=abc123",
            "Test Video",
            {"publishDate": "2024-01-15"}
        )
        assert "【YouTube】" in filename

    def test_youtube_without_www(self) -> None:
        """Test YouTube without www prefix."""
        filename = run_generate_filename(
            "https://youtube.com/watch?v=abc123",
            "Test Video"
        )
        assert "【YouTube】" in filename

    def test_bilibili_domain_mapping(self) -> None:
        """Test Bilibili domain is mapped to 'Bilibili'."""
        filename = run_generate_filename(
            "https://www.bilibili.com/video/BV123",
            "测试视频",
            {"publishDate": "2024-02-20"}
        )
        assert "【Bilibili】" in filename

    def test_unknown_domain_uses_hostname(self) -> None:
        """Test unknown domains use hostname with www stripped."""
        filename = run_generate_filename(
            "https://www.example.com/article",
            "Test Article"
        )
        # Should use "example.com" (www stripped)
        assert "【example.com】" in filename

    def test_domain_without_www(self) -> None:
        """Test domain without www prefix."""
        filename = run_generate_filename(
            "https://blog.example.org/post",
            "Blog Post"
        )
        assert "【blog.example.org】" in filename


class TestSnakeCaseCompatibility:
    """Test snake_case field name compatibility for server metadata.

    The local server (server.py) now returns camelCase metadata,
    but fileSaver.js should also handle snake_case as a fallback
    for backward compatibility.
    """

    def test_snake_case_upload_date(self) -> None:
        """Test that snake_case upload_date is recognized."""
        filename = run_generate_filename(
            "https://youtube.com/watch?v=test123",
            "Test Video",
            {"upload_date": "20240115"}  # snake_case
        )
        assert "2024-M01" in filename

    def test_snake_case_publish_date(self) -> None:
        """Test that snake_case publish_date is recognized."""
        filename = run_generate_filename(
            "https://youtube.com/watch?v=test123",
            "Test Video",
            {"publish_date": "20240315"}  # snake_case
        )
        assert "2024-M03" in filename

    def test_camel_case_takes_priority(self) -> None:
        """Test that camelCase takes priority over snake_case."""
        filename = run_generate_filename(
            "https://youtube.com/watch?v=test123",
            "Test Video",
            {
                "publishDate": "20240515",  # camelCase (priority)
                "publish_date": "20240115",  # snake_case (fallback)
            }
        )
        # camelCase should take priority
        assert "2024-M05" in filename

    def test_upload_date_fallback_to_snake_case(self) -> None:
        """Test uploadDate fallback to upload_date when camelCase is missing."""
        filename = run_generate_filename(
            "https://youtube.com/watch?v=test123",
            "Test Video",
            {
                # No camelCase publishDate or uploadDate
                "upload_date": "20240815",  # snake_case fallback
            }
        )
        assert "2024-M08" in filename

    def test_mixed_case_metadata_from_server(self) -> None:
        """Test metadata that might come from different sources."""
        filename = run_generate_filename(
            "https://youtube.com/watch?v=test123",
            "测试视频标题",
            {
                "title": "测试视频标题",
                "uploadDate": "20241225",  # From local server (camelCase)
            }
        )
        assert "【YouTube】" in filename
        assert "2024-M12" in filename
        assert "测试视频标题" in filename


class TestCliCompatibility:
    """Test compatibility with cli.py naming conventions.

    cli.py format: 【{domain}】{title}-{year}-M{month}_summary.md
    Example: 【科技】iPhone新品发布-2024-M01_summary.md
    """

    def test_full_format_match(self) -> None:
        """Test full filename format matches cli.py style."""
        filename = run_generate_filename(
            "https://youtube.com/watch?v=test",
            "iPhone新品发布",
            {"publishDate": "2024-01-20"}
        )
        # Expected: 【YouTube】iPhone新品发布-2024-M01_summary.md
        assert filename == "【YouTube】iPhone新品发布-2024-M01_summary.md"

    def test_spaces_removed_like_cli(self) -> None:
        """Test that spaces are removed (cli.py behavior)."""
        filename = run_generate_filename(
            "https://example.com",
            "Hello World Test",
            {"publishDate": "2024-03-15"}
        )
        # Spaces should be removed, not replaced with underscores
        assert "HelloWorldTest" in filename
        assert " " not in filename

    def test_month_zero_padded(self) -> None:
        """Test that month is zero-padded to 2 digits."""
        filename = run_generate_filename(
            "https://example.com",
            "Test",
            {"publishDate": "2024-03-01"}
        )
        assert "M03" in filename

        filename2 = run_generate_filename(
            "https://example.com",
            "Test",
            {"publishDate": "2024-11-15"}
        )
        assert "M11" in filename2
