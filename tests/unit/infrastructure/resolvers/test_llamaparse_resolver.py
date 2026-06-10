"""Unit tests for LlamaParseResolver."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from media_summarizer.core.ports.document_parser import DocumentFormat, ParseErrorCode
from media_summarizer.infrastructure.resolvers.llamaparse_resolver import (
    LlamaParseResolver,
)


@pytest.fixture
def temp_pdf_file():
    """Create a temporary PDF file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        # Write minimal PDF content
        f.write(b"%PDF-1.4\n%EOF")
        temp_path = f.name
    yield temp_path
    # Cleanup
    Path(temp_path).unlink(missing_ok=True)


@pytest.fixture
def resolver():
    """Create a LlamaParseResolver instance with a fake API key."""
    return LlamaParseResolver(api_key="test-api-key-12345")


@pytest.mark.asyncio
async def test_sentinel_filename_triggers_failure(resolver, temp_pdf_file):
    """Sentinel filename should trigger a simulated ParseError without API calls."""
    result = await resolver.parse(
        file_path=temp_pdf_file,
        file_name="__e2e_force_llamaparse_failure__test.pdf",
        document_format=DocumentFormat.PDF,
    )

    # Should return a ParseError with RATE_LIMITED code
    assert hasattr(result, "code")
    assert result.code == ParseErrorCode.RATE_LIMITED
    assert result.retryable is True
    assert "E2E test sentinel" in result.message


@pytest.mark.asyncio
async def test_normal_filename_without_sentinel(resolver, temp_pdf_file):
    """Normal filename without sentinel should attempt actual API call."""
    # Mock the httpx.AsyncClient to avoid real API calls
    with patch("media_summarizer.infrastructure.resolvers.llamaparse_resolver.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock successful upload
        mock_upload_response = MagicMock()
        mock_upload_response.json.return_value = {"id": "job-123"}
        mock_client.post.return_value = mock_upload_response

        # Mock successful poll
        mock_poll_response = MagicMock()
        mock_poll_response.json.return_value = {"status": "SUCCESS"}
        
        # Mock successful result retrieval
        mock_result_response = MagicMock()
        mock_result_response.json.return_value = {
            "markdown": "# Test Document\n\nSome content",
            "pages": 1,
        }

        # Set up mock client to return different responses based on call order
        mock_client.post.return_value = mock_upload_response
        mock_client.get.side_effect = [mock_poll_response, mock_result_response]

        result = await resolver.parse(
            file_path=temp_pdf_file,
            file_name="normal_document.pdf",
            document_format=DocumentFormat.PDF,
        )

        # Should return a ParseResult (not a ParseError)
        assert hasattr(result, "markdown_content")
        assert result.markdown_content == "# Test Document\n\nSome content"
        assert result.provider_name == "llamaparse"

        # Verify API calls were made
        mock_client.post.assert_called_once()
        assert mock_client.get.call_count == 2


@pytest.mark.asyncio
async def test_sentinel_filename_prefix_variations(resolver, temp_pdf_file):
    """Test various sentinel filename prefixes."""
    sentinel_filenames = [
        "__e2e_force_llamaparse_failure__test.pdf",
        "__e2e_force_llamaparse_failure__",
        "__e2e_force_llamaparse_failure__sample.pdf",
        "__e2e_force_llamaparse_failure__document.txt",
    ]

    for filename in sentinel_filenames:
        result = await resolver.parse(
            file_path=temp_pdf_file,
            file_name=filename,
            document_format=DocumentFormat.PDF,
        )
        assert result.code == ParseErrorCode.RATE_LIMITED, (
            f"Sentinel not recognized for filename: {filename}"
        )


@pytest.mark.asyncio
async def test_non_sentinel_filenames_skip_short_circuit(resolver, temp_pdf_file):
    """Non-sentinel filenames should not trigger the short-circuit."""
    non_sentinel_filenames = [
        "test.pdf",
        "document.pdf",
        "e2e_force_llamaparse_failure__test.pdf",  # Missing leading underscore
        "e2e_force_llamaparse_failuretest.pdf",  # Missing double underscore
        "__e2e__test.pdf",  # Different prefix
    ]

    with patch("media_summarizer.infrastructure.resolvers.llamaparse_resolver.httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock successful responses
        mock_upload_response = MagicMock()
        mock_upload_response.json.return_value = {"id": "job-123"}
        mock_poll_response = MagicMock()
        mock_poll_response.json.return_value = {"status": "SUCCESS"}
        mock_result_response = MagicMock()
        mock_result_response.json.return_value = {
            "markdown": "# Content",
            "pages": 1,
        }

        for filename in non_sentinel_filenames:
            mock_client.reset_mock()
            mock_client.post.return_value = mock_upload_response
            mock_client.get.side_effect = [mock_poll_response, mock_result_response]

            result = await resolver.parse(
                file_path=temp_pdf_file,
                file_name=filename,
                document_format=DocumentFormat.PDF,
            )

            # Should attempt API call (not short-circuit to error)
            assert hasattr(result, "markdown_content"), (
                f"Expected ParseResult for non-sentinel filename: {filename}"
            )
            assert mock_client.post.called, (
                f"API call should be made for non-sentinel filename: {filename}"
            )
