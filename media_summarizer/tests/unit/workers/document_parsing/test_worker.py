"""
Unit tests for the document parsing worker.
"""

import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from media_summarizer.core.ports.document_parser import (
    DocumentFormat,
    ParseError,
    ParseErrorCode,
    ParseResult,
)
from media_summarizer.workers.document_parsing.worker import (
    _detect_format,
    parse_document_with_fallback,
    process_document_parsing_message,
    process_message,
)


class TestDetectFormat:
    """Tests for file extension detection."""

    def test_pdf(self):
        assert _detect_format("report.pdf") == DocumentFormat.PDF

    def test_docx(self):
        assert _detect_format("essay.docx") == DocumentFormat.DOCX

    def test_pptx(self):
        assert _detect_format("slides.pptx") == DocumentFormat.PPTX

    def test_xlsx(self):
        assert _detect_format("data.xlsx") == DocumentFormat.XLSX

    def test_jpg(self):
        assert _detect_format("scan.jpg") == DocumentFormat.IMAGE_JPG

    def test_jpeg(self):
        assert _detect_format("photo.jpeg") == DocumentFormat.IMAGE_JPEG

    def test_png(self):
        assert _detect_format("screenshot.png") == DocumentFormat.IMAGE_PNG

    def test_tiff(self):
        assert _detect_format("document.tiff") == DocumentFormat.IMAGE_TIFF

    def test_tif_alias(self):
        assert _detect_format("document.tif") == DocumentFormat.IMAGE_TIFF

    def test_unsupported(self):
        assert _detect_format("video.mp4") is None

    def test_no_extension(self):
        assert _detect_format("noext") is None

    def test_case_insensitive(self):
        assert _detect_format("Report.PDF") == DocumentFormat.PDF

    def test_path_with_dirs(self):
        assert _detect_format("/tmp/uploads/my-file.docx") == DocumentFormat.DOCX


class TestParseDocumentWithFallback:
    """Tests for the fallback orchestration logic."""

    @pytest.mark.asyncio
    async def test_primary_success_no_fallback(self):
        """When LlamaParse succeeds, Unstructured is not called."""
        primary_result = ParseResult(
            markdown_content="# Success",
            page_count=1,
            metadata={},
            provider="llamaparse",
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"fake pdf")
            f.flush()
            temp_path = f.name

        try:
            with patch(
                "media_summarizer.workers.document_parsing.worker._llamaparse"
            ) as mock_llama:
                mock_llama.parse = AsyncMock(return_value=primary_result)

                with patch(
                    "media_summarizer.workers.document_parsing.worker._unstructured"
                ) as mock_unstructured:
                    mock_unstructured.parse = AsyncMock()

                    result = await parse_document_with_fallback(
                        temp_path, "test.pdf", DocumentFormat.PDF
                    )

                    assert isinstance(result, ParseResult)
                    assert result.provider == "llamaparse"
                    mock_unstructured.parse.assert_not_called()
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_primary_fails_fallback_succeeds(self):
        """When LlamaParse fails, Unstructured is used as fallback."""
        primary_error = ParseError(
            code=ParseErrorCode.RATE_LIMITED,
            message="Rate limit exceeded",
            provider="llamaparse",
            retryable=True,
        )
        fallback_result = ParseResult(
            markdown_content="# Fallback Success",
            page_count=2,
            metadata={},
            provider="unstructured",
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"fake pdf")
            f.flush()
            temp_path = f.name

        try:
            with patch(
                "media_summarizer.workers.document_parsing.worker._llamaparse"
            ) as mock_llama:
                mock_llama.parse = AsyncMock(return_value=primary_error)

                with patch(
                    "media_summarizer.workers.document_parsing.worker._unstructured"
                ) as mock_unstructured:
                    mock_unstructured.parse = AsyncMock(return_value=fallback_result)

                    result = await parse_document_with_fallback(
                        temp_path, "test.pdf", DocumentFormat.PDF
                    )

                    assert isinstance(result, ParseResult)
                    assert result.provider == "unstructured"
                    mock_unstructured.parse.assert_called_once()
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_both_fail_returns_combined_error(self):
        """When both parsers fail, a combined error is returned."""
        primary_error = ParseError(
            code=ParseErrorCode.RATE_LIMITED,
            message="LlamaParse rate limit",
            provider="llamaparse",
            retryable=True,
        )
        fallback_error = ParseError(
            code=ParseErrorCode.API_ERROR,
            message="Unstructured server error",
            provider="unstructured",
            retryable=True,
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"fake pdf")
            f.flush()
            temp_path = f.name

        try:
            with patch(
                "media_summarizer.workers.document_parsing.worker._llamaparse"
            ) as mock_llama:
                mock_llama.parse = AsyncMock(return_value=primary_error)

                with patch(
                    "media_summarizer.workers.document_parsing.worker._unstructured"
                ) as mock_unstructured:
                    mock_unstructured.parse = AsyncMock(return_value=fallback_error)

                    result = await parse_document_with_fallback(
                        temp_path, "test.pdf", DocumentFormat.PDF
                    )

                    assert isinstance(result, ParseError)
                    assert "All parsers failed" in result.message
                    assert "LlamaParse" in result.message
                    assert "Unstructured" in result.message
                    assert result.retryable is True
        finally:
            os.unlink(temp_path)


class TestProcessDocumentParsingMessage:
    """Tests for the main message processing function."""

    @pytest.mark.asyncio
    async def test_missing_fields_raises(self):
        """Missing required fields should raise ValueError."""
        with pytest.raises(ValueError, match="Missing required fields"):
            await process_document_parsing_message({"job_id": "123"})

    @pytest.mark.asyncio
    async def test_unsupported_format_raises(self):
        """Unsupported file extension should raise ValueError."""
        message = {
            "job_id": "job-123",
            "user_id": "user-456",
            "document_s3_key": "job-123/video.mp4",
            "file_name": "video.mp4",
            "media_key": "doc:user-456:video.mp4:1024",
        }

        with patch(
            "media_summarizer.workers.document_parsing.worker.database_async"
        ) as mock_db:
            mock_db.get_processing_job_by_id = AsyncMock(return_value=None)

            with pytest.raises(ValueError, match="Unsupported document format"):
                await process_document_parsing_message(message)

    @pytest.mark.asyncio
    async def test_successful_parse_uploads_and_emits(self):
        """Successful parsing uploads markdown and emits completion event."""
        message = {
            "job_id": "job-123",
            "user_id": "user-456",
            "document_s3_key": "job-123/report.pdf",
            "file_name": "report.pdf",
            "media_key": "doc:user-456:report.pdf:2048",
            "media_title": "My Report",
        }

        mock_job = MagicMock()
        mock_job.mark_transcribing = MagicMock()
        mock_job.set_transcription_location = MagicMock()
        mock_job.set_processing_duration = MagicMock()

        parse_result = ParseResult(
            markdown_content="# Parsed Report\n\nContent here.",
            page_count=5,
            metadata={},
            provider="llamaparse",
        )

        with patch(
            "media_summarizer.workers.document_parsing.worker.database_async"
        ) as mock_db:
            mock_db.get_processing_job_by_id = AsyncMock(return_value=mock_job)
            mock_db.update_processing_job = AsyncMock()

            with patch(
                "media_summarizer.workers.document_parsing.worker.s3"
            ) as mock_s3:
                mock_s3.download_file = AsyncMock(side_effect=self._create_temp_file)
                mock_s3.upload_file_object = AsyncMock()

                with patch(
                    "media_summarizer.workers.document_parsing.worker.sqs"
                ) as mock_sqs:
                    mock_sqs.send_message = AsyncMock()

                    with patch(
                        "media_summarizer.workers.document_parsing.worker.parse_document_with_fallback",
                        new_callable=AsyncMock,
                        return_value=parse_result,
                    ):
                        await process_document_parsing_message(message)

                # Verify S3 upload was called for the markdown output
                mock_s3.upload_file_object.assert_called_once()
                call_kwargs = mock_s3.upload_file_object.call_args[1]
                assert call_kwargs["key"] == "job-123.md"
                assert call_kwargs["content_type"] == "text/markdown"

                # Verify completion event was emitted
                assert mock_sqs.send_message.call_count >= 1
                completion_call = mock_sqs.send_message.call_args_list[0]
                assert completion_call[1]["queue_name"] == "episode-completion-events"
                body = completion_call[1]["message_body"]
                assert body["status"] == "success"
                assert body["canonical_job_id"] == "job-123"

    @staticmethod
    async def _create_temp_file(bucket, key, file_path):
        """Helper to create a fake downloaded file."""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(b"%PDF-1.4 fake content")


class TestProcessMessage:
    """Tests for the SQS message wrapper."""

    @pytest.mark.asyncio
    async def test_none_message_raises(self):
        with pytest.raises(ValueError, match="Message is None"):
            await process_message(None)

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            await process_message({"Body": "not-json{{"})

    @pytest.mark.asyncio
    async def test_sqs_format_parsed_correctly(self):
        """SQS message with Body field should be parsed."""
        message = {
            "Body": json.dumps({
                "job_id": "j1",
                "user_id": "u1",
                "document_s3_key": "j1/f.pdf",
                "file_name": "f.pdf",
                "media_key": "k1",
            }),
            "ReceiptHandle": "rh-1",
        }

        with patch(
            "media_summarizer.workers.document_parsing.worker.process_document_parsing_message",
            new_callable=AsyncMock,
        ) as mock_process:
            await process_message(message)
            mock_process.assert_called_once()
            args = mock_process.call_args[0][0]
            assert args["job_id"] == "j1"
