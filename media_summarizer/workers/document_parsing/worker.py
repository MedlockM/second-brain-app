"""
Document parsing ingestion worker.

Polls the document-parsing-queue, downloads the uploaded file from S3,
parses it via LlamaParse (primary) with fallback to Unstructured API,
uploads the resulting markdown to the transcript bucket, and emits a
completion event to continue the downstream LLM pipeline.

Owner decision (task-90): LlamaParse free tier API cloud -> fallback Unstructured API.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional

from media_summarizer.core.media_ingestion.title_derivation import (
    first_markdown_heading,
    select_title,
)
from media_summarizer.core.ports.document_parser import (
    DocumentFormat,
    DocumentParserPort,
    ParseError,
    ParseResult,
)
from media_summarizer.core.services import provider_pool_guard, quota_enforcer
from media_summarizer.infrastructure.resolvers.llamaparse_resolver import (
    LlamaParseResolver,
)
from media_summarizer.infrastructure.resolvers.unstructured_resolver import (
    UnstructuredResolver,
)
from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
    setup_logging,
)
from media_summarizer.workers.base_worker import process_message_with_retry

logger = logging.getLogger(__name__)

# Configuration
DOCUMENT_BUCKET = required_env("DOCUMENT_BUCKET")
TRANSCRIPT_BUCKET = required_env("TRANSCRIPT_BUCKET")
DOCUMENT_PARSING_QUEUE = required_env("DOCUMENT_PARSING_QUEUE")
EPISODE_COMPLETED_EVENTS_QUEUE = required_env("EPISODE_COMPLETED_EVENTS_QUEUE")

# Visibility timeout: document parsing can take up to 2-3 minutes
DOCUMENT_PARSING_VISIBILITY_TIMEOUT = int(
    os.environ.get("DOCUMENT_PARSING_VISIBILITY_TIMEOUT", "600")
)

# Resolvers (instantiated at module level for reuse across messages)
_llamaparse: DocumentParserPort = LlamaParseResolver()
_unstructured: DocumentParserPort = UnstructuredResolver()

# Formats whose parsed output is OCR of a picture rather than a structured
# document: their leading heading is body text, not a title (task-266).
_IMAGE_FORMATS = frozenset(
    {
        DocumentFormat.IMAGE_JPG,
        DocumentFormat.IMAGE_JPEG,
        DocumentFormat.IMAGE_PNG,
        DocumentFormat.IMAGE_TIFF,
        DocumentFormat.IMAGE_BMP,
        DocumentFormat.IMAGE_HEIF,
    }
)


def _detect_format(file_name: str) -> DocumentFormat | None:
    """Detect the document format from the file name extension."""
    ext = Path(file_name).suffix.lstrip(".")
    return DocumentFormat.from_extension(ext)


async def parse_document_with_fallback(
    file_path: str,
    file_name: str,
    document_format: DocumentFormat,
) -> ParseResult | ParseError:
    """
    Attempt parsing with LlamaParse, falling back to Unstructured on failure.

    Fallback triggers:
    - LlamaParse returns a retryable error (rate limit, timeout, network)
    - LlamaParse returns an API error

    Does NOT fallback if:
    - The format itself is unsupported (both services support all our formats)
    - LlamaParse returns a non-retryable auth error and Unstructured also has
      no key configured (both would fail)
    """
    # Primary: LlamaParse
    primary_result = await _llamaparse.parse(file_path, file_name, document_format)

    if isinstance(primary_result, ParseResult):
        log_event(
            logger,
            logging.INFO,
            "document_parsing.primary_success",
            "Document parsed successfully with LlamaParse",
            provider="llamaparse",
            page_count=primary_result.page_count,
        )
        return primary_result

    # Primary failed -- log and attempt fallback
    assert isinstance(primary_result, ParseError)
    log_event(
        logger,
        logging.WARNING,
        "document_parsing.primary_failed",
        "LlamaParse failed, attempting Unstructured fallback",
        provider="llamaparse",
        error_code=primary_result.code.value,
        error_message=primary_result.message,
    )

    # Fallback: Unstructured API
    fallback_result = await _unstructured.parse(file_path, file_name, document_format)

    if isinstance(fallback_result, ParseResult):
        log_event(
            logger,
            logging.INFO,
            "document_parsing.fallback_success",
            "Document parsed successfully with Unstructured (fallback)",
            provider="unstructured",
            page_count=fallback_result.page_count,
        )
        return fallback_result

    # Both failed
    assert isinstance(fallback_result, ParseError)
    log_event(
        logger,
        logging.ERROR,
        "document_parsing.all_failed",
        "Both LlamaParse and Unstructured failed to parse document",
        primary_error=primary_result.message,
        fallback_error=fallback_result.message,
    )

    # Return the fallback error (most recent) with context about both failures
    return ParseError(
        code=fallback_result.code,
        message=(
            f"All parsers failed. "
            f"LlamaParse: {primary_result.message}. "
            f"Unstructured: {fallback_result.message}"
        ),
        provider="llamaparse+unstructured",
        retryable=primary_result.retryable or fallback_result.retryable,
    )


async def _record_document_consumption(
    *,
    user_id: Optional[str],
    job_id: str,
    page_count: int,
    provider: str,
) -> None:
    """Charge a parsed document and count its pages against the LlamaParse pool.

    Best-effort: the parse is done and paid for, so a counter failure must not
    fail an import that succeeded.
    """
    pages = max(1, int(page_count or 1))

    if provider.strip().lower() == "llamaparse":
        await provider_pool_guard.record_spend(
            provider_pool_guard.POOL_LLAMAPARSE,
            units=pages,
            idempotency_token=f"llamaparse:{job_id}",
        )

    if not user_id:
        log_event(
            logger,
            logging.WARNING,
            "quota.document_debit_skipped_no_user",
            "No user_id on the document parsing message; nothing to charge",
            job_id=job_id,
        )
        return

    minutes = await quota_enforcer.record_document_parse(
        user_id,
        page_count=pages,
        idempotency_token=quota_enforcer.gate_token(job_id),
    )
    log_event(
        logger,
        logging.INFO,
        "quota.document_debited",
        "Document parse charged to the user's minutes",
        job_id=job_id,
        page_count=pages,
        provider=provider,
        debited_minutes=minutes,
    )


async def process_document_parsing_message(message_body: Dict[str, Any]) -> None:
    """
    Process a single document parsing message.

    Expected message schema:
    {
        "job_id": str,
        "user_id": str,
        "document_s3_key": str,
        "file_name": str,
        "media_key": str,
    }
    """
    job_id = message_body.get("job_id")
    document_s3_key = message_body.get("document_s3_key")
    file_name = message_body.get("file_name", "")
    media_key = message_body.get("media_key")

    if not all([job_id, document_s3_key, file_name]):
        raise ValueError(
            f"Missing required fields in document parsing message: "
            f"job_id={job_id}, document_s3_key={document_s3_key}, file_name={file_name}"
        )

    context_token = bind_log_context(job_id=job_id, source_platform="document")
    try:
        log_event(
            logger,
            logging.INFO,
            "worker.document_parsing.started",
            "Document parsing started",
            job_id=job_id,
            file_name=file_name,
        )

        # Detect format
        document_format = _detect_format(file_name)
        if document_format is None:
            ext = Path(file_name).suffix
            raise ValueError(
                f"Unsupported document format: '{ext}'. "
                f"Supported: {', '.join(sorted(DocumentFormat.supported_extensions()))}"
            )

        # Update job status to extracting (document parsing extracts content)
        job = await database_async.get_processing_job_by_id(job_id)
        if job:
            job.mark_extracting()
            await database_async.update_processing_job(job)

        # Download document from S3
        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = os.path.join(temp_dir, file_name)
            await s3.download_file(
                bucket=DOCUMENT_BUCKET,
                key=document_s3_key,
                file_path=local_path,
            )

            if not os.path.exists(local_path) or os.path.getsize(local_path) == 0:
                raise ValueError("Downloaded document file is empty or missing")

            # Parse with fallback
            start_time = time.time()
            result = await parse_document_with_fallback(
                file_path=local_path,
                file_name=file_name,
                document_format=document_format,
            )
            parse_duration = time.time() - start_time

        # Handle result
        if isinstance(result, ParseError):
            error_msg = f"Document parsing failed: {result.message}"
            if job:
                job.mark_failed(error_message=error_msg, error_step="document_parsing")
                await database_async.update_processing_job(job)
            raise RuntimeError(error_msg)

        # Success: upload markdown to transcript bucket
        assert isinstance(result, ParseResult)
        transcript_s3_key = f"{job_id}.md"
        markdown_bytes = result.markdown_content.encode("utf-8")

        # The parse is what costs money, and its price is the page count, which
        # only exists here: this is the single place a document is charged. One
        # minute per five pages, keyed on the job so a redelivery cannot debit
        # twice. LlamaParse pages also feed the shared pool of layer 3.
        await _record_document_consumption(
            user_id=message_body.get("user_id"),
            job_id=str(job_id),
            page_count=result.page_count,
            provider=result.provider,
        )

        await s3.upload_file_object(
            bucket=TRANSCRIPT_BUCKET,
            key=transcript_s3_key,
            file_obj=BytesIO(markdown_bytes),
            content_type="text/markdown",
            metadata={
                "content-type": "text/markdown",
                "job-type": "document-parsing",
                "parser-provider": result.provider,
                "page-count": str(result.page_count),
            },
        )

        # Update job metadata and mark completed
        if job:
            job.set_transcription_location(transcript_s3_key)
            job.set_processing_duration("transcription", int(parse_duration))
            job.set_transcription_metadata({
                "provider": result.provider,
                "source": "document_upload",
                "page_count": result.page_count,
                "parse_duration_seconds": int(parse_duration),
            })
            # Imported files take their title from the document metadata
            # (task-266): what the parser surfaces of it is the leading heading
            # of the markdown -- LlamaParse renders the document title as `#`,
            # Unstructured maps its `Title` elements to `##`. Nothing survives
            # -> the title derived at upload time from the filename, or the
            # "Document — <date>" / "Photo — <date>" label, stays in place.
            #
            # Images are excluded on purpose: their first heading is OCR'd body
            # text, not a title the file carries, and there is no EXIF/XMP
            # reader in the runtime to read a real one. A camera photo therefore
            # keeps the "Photo — <date>" label, which is precisely the owner's
            # rule for that source.
            if document_format not in _IMAGE_FORMATS:
                parsed_title = select_title(
                    [first_markdown_heading(result.markdown_content)]
                )
                if parsed_title:
                    job.title = parsed_title
            job.source_platform = "document"
            job.media_type = "document"
            job.mark_completed()
            await database_async.update_processing_job(job)

        # Emit completion event for downstream pipeline
        await sqs.send_message(
            queue_name=EPISODE_COMPLETED_EVENTS_QUEUE,
            message_body={
                "event_type": "episode_completion_status",
                "status": "success",
                "media_key": media_key,
                "canonical_job_id": job_id,
                "transcription_s3_key": transcript_s3_key,
                "transcription_metadata": {
                    "provider": result.provider,
                    "source": "document_upload",
                    "page_count": result.page_count,
                    "parse_duration_seconds": int(parse_duration),
                    "parsed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            },
        )

        # Search indexing (Algolia) is enqueued centrally by the media-completed
        # events consumer once it receives this episode_completion_status event.

        log_event(
            logger,
            logging.INFO,
            "worker.document_parsing.completed",
            "Document parsing completed",
            job_id=job_id,
            provider=result.provider,
            page_count=result.page_count,
            duration_seconds=int(parse_duration),
        )

    finally:
        reset_log_context(context_token)


async def process_message(message: Dict[str, Any]) -> None:
    """
    Process an SQS message for document parsing.

    Handles both direct message body (testing) and SQS format (production).
    """
    if message is None:
        raise ValueError("Message is None")

    if "Body" in message:
        try:
            body = json.loads(message["Body"])
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in message body: {str(e)}")
    else:
        body = message

    await process_document_parsing_message(body)


async def poll_queue() -> None:
    """Poll the SQS queue for document parsing messages."""
    logger.info("Starting document parsing worker - polling queue")

    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=DOCUMENT_PARSING_QUEUE,
                max_messages=1,
                wait_time_seconds=20,
                visibility_timeout=DOCUMENT_PARSING_VISIBILITY_TIMEOUT,
            )

            if messages:
                for message in messages:
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=DOCUMENT_PARSING_QUEUE,
                        max_retries=3,
                        worker_name="document_parsing",
                    )

            await asyncio.sleep(1)

        except Exception as e:
            logger.error("Error polling document parsing queue: %s", str(e))
            await asyncio.sleep(5)


async def main() -> None:
    """Main entry point for the document parsing worker."""
    logger.info("Starting document parsing worker")
    logger.info("Document bucket: %s", DOCUMENT_BUCKET)
    logger.info("Transcript bucket: %s", TRANSCRIPT_BUCKET)
    logger.info("Queue: %s", DOCUMENT_PARSING_QUEUE)
    await poll_queue()


if __name__ == "__main__":
    setup_logging("worker-document-parsing")
    asyncio.run(main())
