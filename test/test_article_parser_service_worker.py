"""Test that articleParser.js doesn't use APIs unavailable in Service Worker.

Service Worker environment does NOT have:
- DOMParser
- document
- window

This test ensures the code doesn't directly use these APIs in Service Worker context.
Note: parseArticleInPageContext() runs in PAGE context (not Service Worker),
so it IS allowed to use these APIs.
"""

import re
from pathlib import Path

import pytest


ARTICLE_PARSER_PATH = Path(__file__).parent.parent / "chrome_extension" / "src" / "articleParser.js"


def remove_page_context_function(code: str) -> str:
    """Remove parseArticleInPageContext function from code.

    This function runs in page context (via chrome.scripting.executeScript),
    not in Service Worker, so it's allowed to use DOM APIs.
    """
    # Remove content between markers
    pattern = r'// PAGE_CONTEXT_FUNCTION_START[\s\S]*?// PAGE_CONTEXT_FUNCTION_END'
    return re.sub(pattern, '// [PAGE_CONTEXT_FUNCTION_REMOVED]', code)


class TestArticleParserServiceWorkerCompatibility:
    """Test articleParser.js for Service Worker compatibility."""

    @pytest.fixture
    def article_parser_code(self) -> str:
        """Read the articleParser.js source code."""
        return ARTICLE_PARSER_PATH.read_text(encoding="utf-8")

    @pytest.fixture
    def service_worker_code(self, article_parser_code: str) -> str:
        """Get code that runs in Service Worker context (excluding page context functions)."""
        return remove_page_context_function(article_parser_code)

    def test_no_direct_domparser_usage(self, service_worker_code: str):
        """DOMParser should not be used directly in Service Worker context.

        Service Workers don't have access to DOMParser.
        The parsing should be done via Content Script or alternative methods.
        """
        # Check for direct DOMParser instantiation
        domparser_pattern = r'\bnew\s+DOMParser\s*\('
        matches = re.findall(domparser_pattern, service_worker_code)

        assert len(matches) == 0, (
            f"Found {len(matches)} direct DOMParser usage(s) in Service Worker context. "
            "DOMParser is not available in Service Worker environment. "
            "Use Content Script for DOM parsing instead."
        )

    def test_no_direct_document_usage(self, service_worker_code: str):
        """document object should not be used directly in Service Worker context.

        Service Workers don't have access to document object.
        """
        # Remove comments first
        code_without_comments = re.sub(r'//.*$', '', service_worker_code, flags=re.MULTILINE)
        code_without_comments = re.sub(r'/\*.*?\*/', '', code_without_comments, flags=re.DOTALL)

        # Check for document usage
        document_pattern = r'\bdocument\s*\.'
        matches = re.findall(document_pattern, code_without_comments)

        assert len(matches) == 0, (
            f"Found {len(matches)} direct document usage(s) in Service Worker context. "
            "document is not available in Service Worker environment. "
            "Use Content Script for DOM operations instead."
        )

    def test_no_direct_window_usage(self, service_worker_code: str):
        """window object should not be used directly in Service Worker context.

        Service Workers don't have access to window object.
        """
        # Remove comments first
        code_without_comments = re.sub(r'//.*$', '', service_worker_code, flags=re.MULTILINE)
        code_without_comments = re.sub(r'/\*.*?\*/', '', code_without_comments, flags=re.DOTALL)

        # Check for window usage
        window_pattern = r'\bwindow\s*\.'
        matches = re.findall(window_pattern, code_without_comments)

        assert len(matches) == 0, (
            f"Found {len(matches)} direct window usage(s) in Service Worker context. "
            "window is not available in Service Worker environment."
        )

    def test_page_context_function_exists(self, article_parser_code: str):
        """Verify that parseArticleInPageContext function exists with proper markers."""
        assert "PAGE_CONTEXT_FUNCTION_START" in article_parser_code, (
            "parseArticleInPageContext should have PAGE_CONTEXT_FUNCTION_START marker"
        )
        assert "PAGE_CONTEXT_FUNCTION_END" in article_parser_code, (
            "parseArticleInPageContext should have PAGE_CONTEXT_FUNCTION_END marker"
        )
        assert "parseArticleInPageContext" in article_parser_code, (
            "parseArticleInPageContext function should exist"
        )

    def test_page_context_function_uses_dom_apis(self, article_parser_code: str):
        """Verify that parseArticleInPageContext properly uses DOM APIs for page context."""
        # Extract the page context function
        pattern = r'// PAGE_CONTEXT_FUNCTION_START([\s\S]*?)// PAGE_CONTEXT_FUNCTION_END'
        match = re.search(pattern, article_parser_code)

        assert match is not None, "Could not find PAGE_CONTEXT_FUNCTION content"

        page_context_code = match.group(1)

        # This function SHOULD use document and window since it runs in page context
        assert "document" in page_context_code, (
            "parseArticleInPageContext should use document (it runs in page context)"
        )
