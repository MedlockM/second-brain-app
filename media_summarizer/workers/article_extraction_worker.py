"""
Article extraction worker.

Pipeline:
- Consumes messages from ARTICLE_EXTRACTION_QUEUE
- Fetches article HTML from normalized URL
- Extracts clean text with trafilatura
- Uploads transcript to TRANSCRIPT_BUCKET as {job_id}.txt
- Updates processing job metadata/status
- Publishes success/failure completion events
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from io import BytesIO
import os
from typing import Any, Dict, Optional

import httpx
import trafilatura

from media_summarizer.core.services.transcript_translation import (
    prewarm_translated_transcript,
)
from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
    setup_logging,
)
from media_summarizer.workers.base_worker import (
    get_sqs_receive_params,
    process_message_with_retry,
)

logger = logging.getLogger(__name__)

TRANSCRIPT_BUCKET = os.environ.get("TRANSCRIPT_BUCKET", "media-summarizer-transcripts")
ARTICLE_EXTRACTION_QUEUE = os.environ.get(
    "ARTICLE_EXTRACTION_QUEUE", "article-extraction-queue"
)
EPISODE_COMPLETED_EVENTS_QUEUE = os.environ.get(
    "EPISODE_COMPLETED_EVENTS_QUEUE", "episode-completed-events"
)

ARTICLE_WORKER_MAX_RETRIES = max(
    1, int(os.environ.get("ARTICLE_WORKER_MAX_RETRIES", "3"))
)
ARTICLE_EXTRACT_TIMEOUT_SECONDS = float(
    os.environ.get("ARTICLE_EXTRACT_TIMEOUT_SECONDS", "20")
)
ARTICLE_EXTRACT_MAX_HTML_BYTES = max(
    1024, int(os.environ.get("ARTICLE_EXTRACT_MAX_HTML_BYTES", "2000000"))
)
ARTICLE_EXTRACT_USER_AGENT = os.environ.get(
    "ARTICLE_EXTRACT_USER_AGENT",
    "media-summarizer/article-extractor (+https://media-summarizer.local)",
)

_SUPPORTED_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
_DEFAULT_USER_MESSAGE = "Unable to process this article URL."

_ERROR_MESSAGES: Dict[str, str] = {
    "article_fetch_timeout": "Article fetch timed out. Please retry.",
    "article_http_error": "Article URL returned an error and could not be processed.",
    "article_unsupported_content_type": (
        "The URL does not point to a supported article page."
    ),
    "article_extraction_empty": "Could not extract readable text from this article.",
    "article_extraction_failed": "Article extraction failed. Please retry.",
}


class ArticleExtractionError(Exception):
    def __init__(
        self,
        code: str,
        *,
        details: Optional[str] = None,
        retryable: bool = False,
        user_message: Optional[str] = None,
    ) -> None:
        super().__init__(details or code)
        self.code = code
        self.details = (details or "").strip()
        self.retryable = retryable
        self.user_message = user_message or _ERROR_MESSAGES.get(code, _DEFAULT_USER_MESSAGE)


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_supported_content_type(content_type: str) -> bool:
    value = (content_type or "").lower()
    return any(token in value for token in _SUPPORTED_CONTENT_TYPES)


def _word_count(text: str) -> int:
    return len([token for token in text.split() if token.strip()])


def _build_extraction_metadata(
    *,
    requested_url: str,
    final_url: Optional[str] = None,
    http_status: Optional[int] = None,
    content_type: Optional[str] = None,
    fetched_at: Optional[str] = None,
    char_count: Optional[int] = None,
    word_count: Optional[int] = None,
    language: Optional[str] = None,
    title: Optional[str] = None,
    last_error_code: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "extractor": "trafilatura",
        "extractor_version": "v1",
        "requested_url": requested_url,
        "final_url": final_url,
        "http_status": http_status,
        "content_type": content_type,
        "fetched_at": fetched_at or _now_iso_utc(),
        "char_count": char_count,
        "word_count": word_count,
        "language": language,
        "title": title,
        "last_error_code": last_error_code,
    }


async def _fetch_article_html(url: str) -> Dict[str, Any]:
    headers = {
        "User-Agent": ARTICLE_EXTRACT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
    }

    try:
        async with httpx.AsyncClient(
            timeout=ARTICLE_EXTRACT_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers=headers,
        ) as client:
            async with client.stream("GET", url) as response:
                status_code = response.status_code
                content_type = (response.headers.get("content-type") or "").strip()
                final_url = str(response.url)

                if status_code >= 400:
                    retryable = status_code >= 500
                    raise ArticleExtractionError(
                        "article_http_error",
                        details=f"status={status_code}",
                        retryable=retryable,
                    )

                if not _is_supported_content_type(content_type):
                    raise ArticleExtractionError(
                        "article_unsupported_content_type",
                        details=f"content_type={content_type or 'missing'}",
                        retryable=False,
                    )

                total = 0
                chunks: list[bytes] = []
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > ARTICLE_EXTRACT_MAX_HTML_BYTES:
                        raise ArticleExtractionError(
                            "article_extraction_failed",
                            details="html_too_large",
                            retryable=False,
                        )
                    chunks.append(chunk)

                encoding = response.encoding or "utf-8"
                raw_html = b"".join(chunks)
                try:
                    html = raw_html.decode(encoding, errors="replace")
                except LookupError:
                    html = raw_html.decode("utf-8", errors="replace")

                return {
                    "html": html,
                    "http_status": status_code,
                    "content_type": content_type,
                    "final_url": final_url,
                }
    except ArticleExtractionError:
        raise
    except httpx.TimeoutException as exc:
        raise ArticleExtractionError(
            "article_fetch_timeout",
            details=type(exc).__name__,
            retryable=True,
        ) from exc
    except httpx.HTTPError as exc:
        raise ArticleExtractionError(
            "article_http_error",
            details=type(exc).__name__,
            retryable=True,
        ) from exc
    except Exception as exc:
        raise ArticleExtractionError(
            "article_extraction_failed",
            details=type(exc).__name__,
            retryable=False,
        ) from exc


def _extract_clean_text(html: str) -> str:
    try:
        extracted = trafilatura.extract(
            html,
            output_format="txt",
            include_comments=False,
            include_tables=False,
            include_links=False,
        )
    except Exception as exc:
        raise ArticleExtractionError(
            "article_extraction_failed",
            details=f"trafilatura_error={type(exc).__name__}",
            retryable=False,
        ) from exc

    text = (extracted or "").strip()
    if not text:
        raise ArticleExtractionError(
            "article_extraction_empty",
            details="empty_text_after_extraction",
            retryable=False,
        )
    return text


async def _upload_transcript(job_id: str, text: str) -> str:
    transcript_s3_key = f"{job_id}.txt"
    await s3.upload_file_object(
        bucket=TRANSCRIPT_BUCKET,
        key=transcript_s3_key,
        file_obj=BytesIO(text.encode("utf-8")),
        content_type="text/plain",
        metadata={
            "content-type": "text/plain",
            "job-type": "article-transcription",
            "provider": "article-extractor",
        },
    )
    return transcript_s3_key


async def _publish_success_event(
    *,
    job_id: str,
    media_key: Optional[str],
    transcript_s3_key: str,
    metadata: Dict[str, Any],
) -> None:
    await sqs.send_message(
        queue_name=EPISODE_COMPLETED_EVENTS_QUEUE,
        message_body={
            "event_type": "episode_completion_status",
            "status": "success",
            "media_key": media_key,
            "canonical_job_id": job_id,
            "minutes_used": 1,
            "transcription_s3_key": transcript_s3_key,
            "transcription_metadata": {
                "provider": "article_extractor",
                "model_used": "trafilatura",
                "language": metadata.get("language"),
                "segments_count": metadata.get("word_count"),
                "duration_seconds": 0,
                "source_url": metadata.get("final_url") or metadata.get("requested_url"),
                "extracted_at": metadata.get("fetched_at"),
            },
        },
    )


async def _publish_failure_event(
    *,
    job_id: Optional[str],
    media_key: Optional[str],
    reason: str,
) -> None:
    if not job_id:
        return
    await sqs.send_message(
        queue_name=EPISODE_COMPLETED_EVENTS_QUEUE,
        message_body={
            "event_type": "episode_completion_status",
            "status": "failure",
            "media_key": media_key,
            "canonical_job_id": job_id,
            "reason": reason,
        },
    )


async def _mark_job_failed(
    *,
    job_id: Optional[str],
    requested_url: str,
    error: ArticleExtractionError,
) -> None:
    if not job_id:
        return
    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        return
    job.extraction_metadata = _build_extraction_metadata(
        requested_url=requested_url,
        last_error_code=error.code,
    )
    if error.details:
        job.extraction_metadata["failure_details"] = error.details
    job.mark_failed(
        error_message=error.user_message,
        error_step="article_extraction",
    )
    await database_async.update_processing_job(job)


async def process_article_message(message_body: Dict[str, Any]) -> Dict[str, Any]:
    job_id = message_body.get("job_id")
    normalized_url = (message_body.get("normalized_url") or "").strip()

    if not isinstance(job_id, str) or not job_id.strip():
        raise ArticleExtractionError(
            "article_extraction_failed",
            details="missing_job_id",
            retryable=False,
        )
    if not normalized_url:
        raise ArticleExtractionError(
            "article_extraction_failed",
            details="missing_normalized_url",
            retryable=False,
        )

    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        raise ArticleExtractionError(
            "article_extraction_failed",
            details=f"processing_job_not_found:{job_id}",
            retryable=False,
        )

    job.mark_extracting()
    await database_async.update_processing_job(job)

    fetch_result = await _fetch_article_html(normalized_url)
    clean_text = _extract_clean_text(fetch_result["html"])
    transcript_s3_key = await _upload_transcript(job_id, clean_text)

    extraction_metadata = _build_extraction_metadata(
        requested_url=normalized_url,
        final_url=fetch_result.get("final_url"),
        http_status=fetch_result.get("http_status"),
        content_type=fetch_result.get("content_type"),
        char_count=len(clean_text),
        word_count=_word_count(clean_text),
        language=None,
        title=None,
        last_error_code=None,
    )
    transcription_metadata = {
        "provider": "article_extractor",
        "model_used": "trafilatura",
        "language": extraction_metadata.get("language"),
        "segments_count": extraction_metadata.get("word_count"),
        "duration_seconds": 0,
        "source_url": (
            extraction_metadata.get("final_url")
            or extraction_metadata.get("requested_url")
        ),
        "transcribed_at": extraction_metadata.get("fetched_at"),
    }

    job.set_transcription_location(transcript_s3_key)
    job.set_transcription_metadata(transcription_metadata)
    job.extraction_metadata = extraction_metadata
    await prewarm_translated_transcript(job, transcript_s3_key, clean_text)
    job.mark_completed()
    await database_async.update_processing_job(job)

    return {
        "job_id": job_id,
        "media_key": message_body.get("media_key"),
        "transcript_s3_key": transcript_s3_key,
        "extraction_metadata": extraction_metadata,
    }


async def process_message(message: Dict[str, Any]) -> None:
    body: Dict[str, Any] = {}
    try:
        body = json.loads(message.get("Body", "{}"))
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "worker.invalid_message",
            "Invalid JSON in article extraction message",
            queue=ARTICLE_EXTRACTION_QUEUE,
            exc_info=exc,
        )
        return

    context_token = bind_log_context(
        job_id=body.get("job_id"),
        media_item_id=body.get("job_id"),
        queue=ARTICLE_EXTRACTION_QUEUE,
        provider="article_extractor",
        transcript_source="article_extractor",
    )

    receive_count = int(
        (message.get("Attributes") or {}).get("ApproximateReceiveCount", "1")
    )

    try:
        result = await process_article_message(body)
        await _publish_success_event(
            job_id=result["job_id"],
            media_key=result.get("media_key"),
            transcript_s3_key=result["transcript_s3_key"],
            metadata=result["extraction_metadata"],
        )
        log_event(
            logger,
            logging.INFO,
            "transcription.completed",
            "Article extraction completed",
            transcript_source="article_extractor",
            job_id=result["job_id"],
            media_item_id=result["job_id"],
        )
    except ArticleExtractionError as exc:
        should_retry = exc.retryable and receive_count < ARTICLE_WORKER_MAX_RETRIES
        if should_retry:
            raise

        await _mark_job_failed(
            job_id=body.get("job_id"),
            requested_url=(body.get("normalized_url") or "").strip(),
            error=exc,
        )
        reason = exc.code if not exc.details else f"{exc.code}:{exc.details}"
        await _publish_failure_event(
            job_id=body.get("job_id"),
            media_key=body.get("media_key"),
            reason=reason,
        )
        log_event(
            logger,
            logging.ERROR,
            "transcription.failed",
            "Article extraction failed",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            transcript_source="article_extractor",
            error_code=exc.code,
            detail=exc.details,
        )
    except Exception as exc:
        if receive_count < ARTICLE_WORKER_MAX_RETRIES:
            raise

        final_error = ArticleExtractionError(
            "article_extraction_failed",
            details=f"unexpected:{type(exc).__name__}",
            retryable=False,
        )
        await _mark_job_failed(
            job_id=body.get("job_id"),
            requested_url=(body.get("normalized_url") or "").strip(),
            error=final_error,
        )
        await _publish_failure_event(
            job_id=body.get("job_id"),
            media_key=body.get("media_key"),
            reason=f"{final_error.code}:{final_error.details}",
        )
        log_event(
            logger,
            logging.ERROR,
            "transcription.failed",
            "Article extraction failed after retries",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            transcript_source="article_extractor",
            error_code=final_error.code,
            exc_info=exc,
        )
    finally:
        reset_log_context(context_token)


async def process_messages_batch(messages: list[Dict[str, Any]]) -> None:
    async def process_one(message: Dict[str, Any]) -> bool:
        return await process_message_with_retry(
            message=message,
            processor=process_message,
            queue_name=ARTICLE_EXTRACTION_QUEUE,
            max_retries=ARTICLE_WORKER_MAX_RETRIES,
            worker_name="article-extraction",
        )

    tasks = [asyncio.create_task(process_one(message)) for message in messages]
    await asyncio.gather(*tasks, return_exceptions=True)


async def poll_queue() -> None:
    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting article extraction worker",
        queue=ARTICLE_EXTRACTION_QUEUE,
    )
    while True:
        try:
            receive_params = get_sqs_receive_params(visibility_timeout=300)
            messages = await sqs.receive_messages(
                queue_name=ARTICLE_EXTRACTION_QUEUE,
                max_messages=receive_params["MaxNumberOfMessages"],
                wait_time_seconds=receive_params["WaitTimeSeconds"],
                visibility_timeout=receive_params["VisibilityTimeout"],
            )
            if messages:
                await process_messages_batch(messages)
            else:
                await asyncio.sleep(1)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "Article extraction polling failed",
                queue=ARTICLE_EXTRACTION_QUEUE,
                exc_info=exc,
            )
            await asyncio.sleep(5)


async def main() -> None:
    setup_logging("article-extraction-worker")
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
