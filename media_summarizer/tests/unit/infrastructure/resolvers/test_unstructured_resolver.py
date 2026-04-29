"""
Unit tests for the Unstructured API resolver.
"""

import os
import tempfile
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from media_summarizer.core.ports.document_parser import (
    DocumentFormat,
    ParseError,
    ParseErrorCode,
    ParseResult,
)
from media_summarizer.infrastructure.resolvers.unstructured_resolver import (
    UnstructuredResolver,
)


@pytest.fixture
def resolver():
    """Create an Unstructured resolver with a test API key."""
    return UnstructuredResolver(api_key="test-unstructured-key", timeout=30)


@pytest.fixture
def temp_pdf():
    """Create a temporary file simulating a PDF."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 fake pdf content for testing")
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def sample_elements():
    """Sample Unstructured API response elements."""
    return [
        {
            "type": "Title",
            "text": "Introduction",
            "metadata": {"page_number": 1},
        },
        {
            "type": "NarrativeText",
            "text": "This is the first paragraph of the document.",
            "metadata": {"page_number": 1},
        },
        {
            "type": "ListItem",
            "text": "First bullet point",
            "metadata": {"page_number": 1},
        },
        {
            "type": "ListItem",
            "text": "Second bullet point",
            "metadata": {"page_number": 1},
        },
        {
            "type": "Title",
            "text": "Chapter 2",
            "metadata": {"page_number": 2},
        },
        {
            "type": "NarrativeText",
            "text": "Content on page two.",
            "metadata": {"page_number": 2},
        },
        {
            "type": "Table",
            "text": "| Col A | Col B |\n|-------|-------|\n| 1 | 2 |",
            "metadata": {"page_number": 2},
        },
    ]


class TestUnstructuredResolverMetadata:
    """Tests for resolver metadata and format support."""

    def test_provider_name(self, resolver):
        assert resolver.provider_name == "unstructured"

    def test_supports_all_formats(self, resolver):
        for fmt in DocumentFormat:
            assert resolver.supports_format(fmt) is True


class TestUnstructuredResolverAuth:
    """Tests for authentication handling."""

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_auth_error(self, temp_pdf):
        resolver = UnstructuredResolver(api_key="", timeout=30)
        result = await resolver.parse(temp_pdf, "test.pdf", DocumentFormat.PDF)

        assert isinstance(result, ParseError)
        assert result.code == ParseErrorCode.AUTHENTICATION_ERROR
        assert "not configured" in result.message


class TestUnstructuredResolverParse:
    """Tests for the parse method with mocked HTTP calls."""

    @pytest.mark.asyncio
    async def test_successful_parse(self, resolver, temp_pdf, sample_elements):
        """Test a complete successful parsing flow."""
        response = httpx.Response(
            200,
            json=sample_elements,
            request=httpx.Request("POST", "https://api.unstructuredapp.io/general/v0/general"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=response):
            result = await resolver.parse(temp_pdf, "test.pdf", DocumentFormat.PDF)

        assert isinstance(result, ParseResult)
        assert result.provider == "unstructured"
        assert result.page_count == 2  # Elements span pages 1 and 2
        assert "Introduction" in result.markdown_content
        assert "Chapter 2" in result.markdown_content
        assert "First bullet point" in result.markdown_content
        assert result.metadata["element_count"] == 7

    @pytest.mark.asyncio
    async def test_empty_elements_returns_error(self, resolver, temp_pdf):
        """Test that an empty elements response is flagged."""
        response = httpx.Response(
            200,
            json=[],
            request=httpx.Request("POST", "https://api.unstructuredapp.io/general/v0/general"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=response):
            result = await resolver.parse(temp_pdf, "test.pdf", DocumentFormat.PDF)

        assert isinstance(result, ParseError)
        assert result.code == ParseErrorCode.EMPTY_RESULT

    @pytest.mark.asyncio
    async def test_rate_limit(self, resolver, temp_pdf):
        """Test that 429 responses are retryable rate limit errors."""
        error_response = httpx.Response(
            429,
            text="Too many requests",
            request=httpx.Request("POST", "https://api.unstructuredapp.io/general/v0/general"),
        )

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "429", request=error_response.request, response=error_response
            ),
        ):
            result = await resolver.parse(temp_pdf, "test.pdf", DocumentFormat.PDF)

        assert isinstance(result, ParseError)
        assert result.code == ParseErrorCode.RATE_LIMITED
        assert result.retryable is True

    @pytest.mark.asyncio
    async def test_timeout(self, resolver, temp_pdf):
        """Test that timeouts are retryable."""
        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            result = await resolver.parse(temp_pdf, "test.pdf", DocumentFormat.PDF)

        assert isinstance(result, ParseError)
        assert result.code == ParseErrorCode.TIMEOUT
        assert result.retryable is True

    @pytest.mark.asyncio
    async def test_server_error_is_retryable(self, resolver, temp_pdf):
        """Test that 5xx errors are retryable."""
        error_response = httpx.Response(
            503,
            text="Service unavailable",
            request=httpx.Request("POST", "https://api.unstructuredapp.io/general/v0/general"),
        )

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "503", request=error_response.request, response=error_response
            ),
        ):
            result = await resolver.parse(temp_pdf, "test.pdf", DocumentFormat.PDF)

        assert isinstance(result, ParseError)
        assert result.code == ParseErrorCode.API_ERROR
        assert result.retryable is True


class TestElementsToMarkdown:
    """Tests for the elements-to-markdown conversion."""

    def test_title_formatting(self):
        elements = [{"type": "Title", "text": "My Title", "metadata": {}}]
        md = UnstructuredResolver._elements_to_markdown(elements)
        assert "## My Title" in md

    def test_header_formatting(self):
        elements = [{"type": "Header", "text": "Top Header", "metadata": {}}]
        md = UnstructuredResolver._elements_to_markdown(elements)
        assert "# Top Header" in md

    def test_list_items(self):
        elements = [
            {"type": "ListItem", "text": "Item 1", "metadata": {}},
            {"type": "ListItem", "text": "Item 2", "metadata": {}},
        ]
        md = UnstructuredResolver._elements_to_markdown(elements)
        assert "- Item 1" in md
        assert "- Item 2" in md

    def test_empty_text_skipped(self):
        elements = [
            {"type": "NarrativeText", "text": "", "metadata": {}},
            {"type": "Title", "text": "Real Title", "metadata": {}},
        ]
        md = UnstructuredResolver._elements_to_markdown(elements)
        assert "Real Title" in md
        # No empty paragraphs
        assert "\n\n\n\n" not in md

    def test_formula_wrapped_in_math(self):
        elements = [{"type": "Formula", "text": "E = mc^2", "metadata": {}}]
        md = UnstructuredResolver._elements_to_markdown(elements)
        assert "$$" in md
        assert "E = mc^2" in md

    def test_figure_caption_italic(self):
        elements = [{"type": "FigureCaption", "text": "Figure 1: Test", "metadata": {}}]
        md = UnstructuredResolver._elements_to_markdown(elements)
        assert "*Figure 1: Test*" in md
