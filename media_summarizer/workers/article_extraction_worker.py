"""
Article extraction worker.

Serves the RSS path: `rss_feed_poll_worker` publishes one message per new article
item, with its processing job already created. A URL a user saves themselves is
*not* routed here -- it is read inside the request, because an article's text is
part of its content identity and has to be known before anything is written
(task-392, `ArticleResolver`).

Pipeline:
- Consumes messages from ARTICLE_EXTRACTION_QUEUE
- Reads the page through `ArticleContentFetcherPort` (the same reader the API path
  uses, so both agree on what a page says)
- Uploads transcript to TRANSCRIPT_BUCKET as {job_id}.txt
- Updates processing job metadata/status
- Publishes success/failure completion events
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, Optional

from media_summarizer.core.models.failure_codes import MediaFailureCode
from media_summarizer.core.ports.article_content import (
    ArticleContent,
    ArticleContentFetcherPort,
    ArticleFetchError,
)
from media_summarizer.infrastructure.resolvers.trafilatura_article_resolver import (
    TrafilaturaArticleResolver,
)
from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils.env import required_env
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
from media_summarizer.workers.ingestion_failures import IngestionFailure

logger = logging.getLogger(__name__)

TRANSCRIPT_BUCKET = required_env("TRANSCRIPT_BUCKET")
ARTICLE_EXTRACTION_QUEUE = required_env("ARTICLE_EXTRACTION_QUEUE")
EPISODE_COMPLETED_EVENTS_QUEUE = required_env("EPISODE_COMPLETED_EVENTS_QUEUE")

ARTICLE_WORKER_MAX_RETRIES = max(
    1, int(os.environ.get("ARTICLE_WORKER_MAX_RETRIES", "3"))
)

_content_fetcher: Optional[ArticleContentFetcherPort] = None


class ArticleExtractionError(IngestionFailure):
    """An article extraction failure. See `IngestionFailure` for the shape."""


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fetcher() -> ArticleContentFetcherPort:
    """The shared page reader, built once per container.

    The fetch policy -- redirects, the content-type gate, the size cap, the
    encoding fallback -- lives in the adapter, not here. It used to live in this
    file, where the API path could not reach it; two copies of it would be how the
    two paths come to disagree about what a page says (task-392).
    """
    global _content_fetcher
    if _content_fetcher is None:
        _content_fetcher = TrafilaturaArticleResolver()
    return _content_fetcher


def _failure_from_fetch_error(error: ArticleFetchError) -> ArticleExtractionError:
    """Translate a provider-level fetch error into this worker's retry vocabulary."""
    return ArticleExtractionError(
        error.media_failure_code,
        details=error.details,
        retryable=error.retryable,
        fetch_error_code=error.code.value,
        **error.context,
    )


def _error_extraction_metadata(
    *, requested_url: str, error: ArticleExtractionError
) -> Dict[str, Any]:
    """The `extraction_metadata` shape for a page that could not be read."""
    return {
        "extractor": "trafilatura",
        "extractor_version": "v1",
        "requested_url": requested_url,
        "final_url": None,
        "http_status": None,
        "content_type": None,
        "fetched_at": _now_iso_utc(),
        "char_count": None,
        "word_count": None,
        "paragraph_count": None,
        "language": None,
        "title": None,
        "last_error_code": error.code.value,
    }


async def _upload_transcript(job_id: str, text: str) -> str:
    """Upload the already-normalized extracted text as plain text."""
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
            "transcription_s3_key": transcript_s3_key,
            "transcription_metadata": {
                "provider": "article_extractor",
                "model_used": "trafilatura",
                "language": metadata.get("language"),
                "segments_count": metadata.get("paragraph_count"),
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
    job.extraction_metadata = _error_extraction_metadata(
        requested_url=requested_url,
        error=error,
    )
    job.extraction_metadata["failure_details"] = error.details
    job.mark_failed(
        error_code=error.code,
        error_step="article_extraction",
        error_metadata=error.error_metadata(step="article_extraction"),
    )
    await database_async.update_processing_job(job)


async def process_article_message(message_body: Dict[str, Any]) -> Dict[str, Any]:
    job_id = message_body.get("job_id")
    normalized_url = (message_body.get("normalized_url") or "").strip()

    if not isinstance(job_id, str) or not job_id.strip():
        raise ArticleExtractionError(
            MediaFailureCode.INVALID_JOB_MESSAGE,
            details="missing_job_id",
            retryable=False,
        )
    if not normalized_url:
        raise ArticleExtractionError(
            MediaFailureCode.INVALID_JOB_MESSAGE,
            details="missing_normalized_url",
            retryable=False,
        )

    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        raise ArticleExtractionError(
            MediaFailureCode.INVALID_JOB_MESSAGE,
            details="processing_job_not_found",
            retryable=False,
        )

    job.mark_extracting()
    await database_async.update_processing_job(job)

    try:
        article: ArticleContent = await _fetcher().fetch(normalized_url)
    except ArticleFetchError as exc:
        raise _failure_from_fetch_error(exc) from exc

    transcript_s3_key = await _upload_transcript(job_id, article.text)

    extraction_metadata = article.extraction_metadata()
    transcription_metadata = {
        "provider": article.provider or "article_extractor",
        "model_used": article.extractor or "trafilatura",
        "language": article.language,
        # Paragraph count, comparable across sources (task-231 s13.1).
        "segments_count": article.paragraph_count,
        "duration_seconds": 0,
        "source_url": article.final_url or article.requested_url,
        "transcribed_at": article.fetched_at,
    }

    job.set_transcription_location(transcript_s3_key)
    job.set_transcription_metadata(transcription_metadata)
    job.extraction_metadata = extraction_metadata
    # Before `mark_completed`, so the completion event carries the headline and
    # the creator, and the Algolia record is right on the first indexing pass
    # (task-266, task-304). The `og:image` is hotlinked: a publisher's image URL
    # is unsigned and stable, and re-hosting the highest-volume source would put
    # a second-host fetch on the one path that makes no external call today
    # (task-302 §5.3).
    if article.title:
        job.title = article.title
    if article.creator_name:
        job.creator_name = article.creator_name
    if article.cover_url:
        job.media_image = article.cover_url
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
        await _publish_failure_event(
            job_id=body.get("job_id"),
            media_key=body.get("media_key"),
            reason=exc.reason,
        )
        log_event(
            logger,
            logging.ERROR,
            "transcription.failed",
            "Article extraction failed",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            transcript_source="article_extractor",
            error_code=exc.code.value,
            detail=exc.details,
            # The site's own wording — English, unversioned — stays here rather
            # than on the job: CloudWatch is where we read it.
            exc_info=exc,
        )
    except Exception as exc:
        if receive_count < ARTICLE_WORKER_MAX_RETRIES:
            raise

        final_error = ArticleExtractionError(
            MediaFailureCode.UNEXPECTED_ERROR,
            details="unexpected_exception",
            retryable=False,
            exception_type=type(exc).__name__,
        )
        await _mark_job_failed(
            job_id=body.get("job_id"),
            requested_url=(body.get("normalized_url") or "").strip(),
            error=final_error,
        )
        await _publish_failure_event(
            job_id=body.get("job_id"),
            media_key=body.get("media_key"),
            reason=final_error.reason,
        )
        log_event(
            logger,
            logging.ERROR,
            "transcription.failed",
            "Article extraction failed after retries",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            transcript_source="article_extractor",
            error_code=final_error.code.value,
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
