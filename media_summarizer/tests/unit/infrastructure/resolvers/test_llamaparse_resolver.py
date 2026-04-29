"""
Unit tests for the LlamaParse resolver.
"""

import json
import os
import tempfile
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

from media_summarizer.core.ports.document_parser import (
    DocumentFormat,
    ParseError,
    ParseErrorCode,
    ParseResult,
)
from media_summarizer.infrastructure.resolvers.llamaparse_resolver import (
    LlamaParseResolver,
)


@pytest.fixture
def resolver():
    """Create a LlamaParse resolver with a test API key."""
    return LlamaParseResolver(api_key="test-api-key", timeout=30)


@pytest.fixture
def temp_pdf():
    """Create a temporary file simulating a PDF."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 fake pdf content for testing")
        f.flush()
        yield f.name
    os.unlink(f.name)


class TestLlamaParseResolverMetadata:
    """Tests for resolver metadata and format support."""

    def test_provider_name(self, resolver):
        assert resolver.provider_name == "llamaparse"

    def test_supports_all_formats(self, resolver):
        for fmt in DocumentFormat:
            assert resolver.supports_format(fmt) is True


class TestLlamaParseResolverAuth:
    """Tests for authentication handling."""

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_auth_error(self, temp_pdf):
        resolver = LlamaParseResolver(api_key="", timeout=30)
        result = await resolver.parse(temp_pdf, "test.pdf", DocumentFormat.PDF)

        assert isinstance(result, ParseError)
        assert result.code == ParseErrorCode.AUTHENTICATION_ERROR
        assert "not configured" in result.message
        assert result.retryable is False


class TestLlamaParseResolverParse:
    """Tests for the parse method with mocked HTTP calls."""

    @pytest.mark.asyncio
    async def test_successful_parse(self, resolver, temp_pdf):
        """Test a complete successful parsing flow."""
        upload_response = httpx.Response(
            200,
            json={"id": "job-123"},
            request=httpx.Request("POST", "https://api.cloud.llamaindex.ai/api/parsing/upload"),
        )
        status_response = httpx.Response(
            200,
            json={"status": "SUCCESS"},
            request=httpx.Request("GET", "https://api.cloud.llamaindex.ai/api/parsing/job/job-123"),
        )
        result_response = httpx.Response(
            200,
            json={"markdown": "# Document Title\n\nSome content here.", "pages": 3},
            request=httpx.Request("GET", "https://api.cloud.llamaindex.ai/api/parsing/job/job-123/result/markdown"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=upload_response):
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=[status_response, result_response]):
                result = await resolver.parse(temp_pdf, "test.pdf", DocumentFormat.PDF)

        assert isinstance(result, ParseResult)
        assert result.markdown_content == "# Document Title\n\nSome content here."
        assert result.page_count == 3
        assert result.provider == "llamaparse"
        assert result.metadata["job_id"] == "job-123"

    @pytest.mark.asyncio
    async def test_rate_limit_returns_retryable_error(self, resolver, temp_pdf):
        """Test that 429 responses produce a retryable rate limit error."""
        rate_limit_response = httpx.Response(
            429,
            text="Rate limit exceeded",
            request=httpx.Request("POST", "https://api.cloud.llamaindex.ai/api/parsing/upload"),
        )

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "429", request=rate_limit_response.request, response=rate_limit_response
            ),
        ):
            result = await resolver.parse(temp_pdf, "test.pdf", DocumentFormat.PDF)

        assert isinstance(result, ParseError)
        assert result.code == ParseErrorCode.RATE_LIMITED
        assert result.retryable is True

    @pytest.mark.asyncio
    async def test_timeout_returns_retryable_error(self, resolver, temp_pdf):
        """Test that timeouts produce a retryable error."""
        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("Connection timed out"),
        ):
            result = await resolver.parse(temp_pdf, "test.pdf", DocumentFormat.PDF)

        assert isinstance(result, ParseError)
        assert result.code == ParseErrorCode.TIMEOUT
        assert result.retryable is True

    @pytest.mark.asyncio
    async def test_network_error_returns_retryable(self, resolver, temp_pdf):
        """Test that network connectivity errors are retryable."""
        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await resolver.parse(temp_pdf, "test.pdf", DocumentFormat.PDF)

        assert isinstance(result, ParseError)
        assert result.code == ParseErrorCode.NETWORK_ERROR
        assert result.retryable is True

    @pytest.mark.asyncio
    async def test_auth_failure_returns_non_retryable(self, resolver, temp_pdf):
        """Test that 401/403 responses are non-retryable."""
        auth_response = httpx.Response(
            401,
            text="Unauthorized",
            request=httpx.Request("POST", "https://api.cloud.llamaindex.ai/api/parsing/upload"),
        )

        with patch(
            "httpx.AsyncClient.post",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "401", request=auth_response.request, response=auth_response
            ),
        ):
            result = await resolver.parse(temp_pdf, "test.pdf", DocumentFormat.PDF)

        assert isinstance(result, ParseError)
        assert result.code == ParseErrorCode.AUTHENTICATION_ERROR
        assert result.retryable is False

    @pytest.mark.asyncio
    async def test_empty_result_returns_error(self, resolver, temp_pdf):
        """Test that empty markdown response is flagged as error."""
        upload_response = httpx.Response(
            200,
            json={"id": "job-456"},
            request=httpx.Request("POST", "https://api.cloud.llamaindex.ai/api/parsing/upload"),
        )
        status_response = httpx.Response(
            200,
            json={"status": "SUCCESS"},
            request=httpx.Request("GET", "https://api.cloud.llamaindex.ai/api/parsing/job/job-456"),
        )
        result_response = httpx.Response(
            200,
            json={"markdown": "", "pages": 0},
            request=httpx.Request("GET", "https://api.cloud.llamaindex.ai/api/parsing/job/job-456/result/markdown"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=upload_response):
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=[status_response, result_response]):
                result = await resolver.parse(temp_pdf, "test.pdf", DocumentFormat.PDF)

        assert isinstance(result, ParseError)
        assert result.code == ParseErrorCode.EMPTY_RESULT

    @pytest.mark.asyncio
    async def test_job_failure_returns_error(self, resolver, temp_pdf):
        """Test that a job that fails on the server side returns an API error."""
        upload_response = httpx.Response(
            200,
            json={"id": "job-789"},
            request=httpx.Request("POST", "https://api.cloud.llamaindex.ai/api/parsing/upload"),
        )
        status_response = httpx.Response(
            200,
            json={"status": "ERROR", "error": "Corrupt file"},
            request=httpx.Request("GET", "https://api.cloud.llamaindex.ai/api/parsing/job/job-789"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=upload_response):
            with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=status_response):
                result = await resolver.parse(temp_pdf, "test.pdf", DocumentFormat.PDF)

        assert isinstance(result, ParseError)
        assert result.code == ParseErrorCode.API_ERROR
        assert "Corrupt file" in result.message
