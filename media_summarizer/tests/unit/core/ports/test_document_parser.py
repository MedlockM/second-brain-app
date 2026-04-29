"""
Unit tests for the document parser port (core interface).
"""

import pytest

from media_summarizer.core.ports.document_parser import (
    DocumentFormat,
    ParseError,
    ParseErrorCode,
    ParseResult,
)


class TestDocumentFormat:
    """Tests for the DocumentFormat enum and helpers."""

    def test_from_extension_pdf(self):
        assert DocumentFormat.from_extension("pdf") == DocumentFormat.PDF
        assert DocumentFormat.from_extension("PDF") == DocumentFormat.PDF
        assert DocumentFormat.from_extension(".pdf") == DocumentFormat.PDF

    def test_from_extension_docx(self):
        assert DocumentFormat.from_extension("docx") == DocumentFormat.DOCX

    def test_from_extension_images(self):
        assert DocumentFormat.from_extension("jpg") == DocumentFormat.IMAGE_JPG
        assert DocumentFormat.from_extension("jpeg") == DocumentFormat.IMAGE_JPEG
        assert DocumentFormat.from_extension("png") == DocumentFormat.IMAGE_PNG
        assert DocumentFormat.from_extension("tiff") == DocumentFormat.IMAGE_TIFF
        assert DocumentFormat.from_extension("tif") == DocumentFormat.IMAGE_TIFF
        assert DocumentFormat.from_extension("heic") == DocumentFormat.IMAGE_HEIF

    def test_from_extension_unknown_returns_none(self):
        assert DocumentFormat.from_extension("mp4") is None
        assert DocumentFormat.from_extension("zip") is None
        assert DocumentFormat.from_extension("") is None

    def test_supported_extensions_contains_all(self):
        exts = DocumentFormat.supported_extensions()
        assert "pdf" in exts
        assert "docx" in exts
        assert "pptx" in exts
        assert "xlsx" in exts
        assert "jpg" in exts
        assert "jpeg" in exts
        assert "png" in exts
        assert "tiff" in exts
        assert "tif" in exts
        assert "bmp" in exts
        assert "heif" in exts
        assert "heic" in exts

    def test_supported_extensions_does_not_contain_unsupported(self):
        exts = DocumentFormat.supported_extensions()
        assert "mp4" not in exts
        assert "zip" not in exts
        assert "exe" not in exts


class TestParseErrorCode:
    """Tests for the error code enum stability."""

    def test_all_codes_are_strings(self):
        for code in ParseErrorCode:
            assert isinstance(code.value, str)

    def test_expected_codes_exist(self):
        codes = {c.value for c in ParseErrorCode}
        assert "unsupported_format" in codes
        assert "rate_limited" in codes
        assert "api_error" in codes
        assert "timeout" in codes
        assert "empty_result" in codes
        assert "file_too_large" in codes
        assert "authentication_error" in codes
        assert "network_error" in codes
        assert "invalid_file" in codes


class TestParseResult:
    """Tests for the ParseResult dataclass."""

    def test_creation(self):
        result = ParseResult(
            markdown_content="# Hello",
            page_count=3,
            metadata={"key": "value"},
            provider="test",
        )
        assert result.markdown_content == "# Hello"
        assert result.page_count == 3
        assert result.metadata == {"key": "value"}
        assert result.provider == "test"

    def test_defaults(self):
        result = ParseResult(markdown_content="content")
        assert result.page_count == 0
        assert result.metadata == {}
        assert result.provider == ""


class TestParseError:
    """Tests for the ParseError dataclass."""

    def test_creation(self):
        error = ParseError(
            code=ParseErrorCode.RATE_LIMITED,
            message="Too many requests",
            provider="llamaparse",
            retryable=True,
        )
        assert error.code == ParseErrorCode.RATE_LIMITED
        assert error.message == "Too many requests"
        assert error.provider == "llamaparse"
        assert error.retryable is True

    def test_defaults(self):
        error = ParseError(code=ParseErrorCode.API_ERROR, message="oops")
        assert error.provider == ""
        assert error.retryable is False
