"""
Queue-first Instagram ingestion worker.

Pipeline:
- Consumes messages from INSTAGRAM_INGESTION_QUEUE
- Resolves content via InstagramApifyResolver (Apify Reel/Post Scrapers)
- If the resolver returns raw_text (Apify native transcript for Reels):
    uploads transcript to S3 and publishes a completion event directly
- Fails with NonRetryableProviderResolutionError if neither raw_text nor
    image-post payload is present (no audio_url fallback to Deepgram)
- Marks the processing job as extracting/transcribing along the way
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from io import BytesIO
import os
from typing import Any, Dict, Optional

from media_summarizer.core.media_ingestion.domain import (
    ClassifiedUrl,
    IngestUrlCommand,
    IngestUrlRequest,
    MediaFamily,
    ResolveContext,
    SourcePlatform,
    UserContext,
)
from media_summarizer.core.media_ingestion.errors import (
    NonRetryableProviderResolutionError,
    RetryableProviderResolutionError,
)
from media_summarizer.infrastructure.resolvers.instagram_apify_resolver import (
    InstagramApifyResolver,
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

INSTAGRAM_INGESTION_QUEUE = os.environ.get(
    "INSTAGRAM_INGESTION_QUEUE", "instagram-ingestion-queue"
)
EPISODE_COMPLETED_EVENTS_QUEUE = os.environ.get(
    "EPISODE_COMPLETED_EVENTS_QUEUE", "episode-completed-events"
)
TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcripts"
)
INSTAGRAM_WORKER_MAX_RETRIES = max(
    1, int(os.environ.get("INSTAGRAM_WORKER_MAX_RETRIES", "3"))
)

_DEFAULT_TEMPORARY_MESSAGE = (
    "Instagram media extraction is temporarily unavailable. Please retry."
)
_DEFAULT_UNAVAILABLE_MESSAGE = (
    "This Instagram post is unavailable or cannot be processed."
)
_DEFAULT_UNSUPPORTED_MESSAGE = (
    "Unable to extract transcribable media from this Instagram URL."
)


class InstagramIngestionError(Exception):
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
        self.user_message = user_message or _DEFAULT_TEMPORARY_MESSAGE


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _build_resolve_context(
    *,
    normalized_url: str,
    media_key: str,
    user_id: str,
) -> ResolveContext:
    """Build a minimal ResolveContext for the InstagramApifyResolver."""
    return ResolveContext(
        command=IngestUrlCommand(
            user=UserContext(user_id=user_id, user_email=""),
            request=IngestUrlRequest(url=normalized_url),
        ),
        normalized_url=normalized_url,
        media_key=media_key,
        classification=ClassifiedUrl(
            media_family=MediaFamily.SOCIAL_VIDEO,
            source_platform=SourcePlatform.INSTAGRAM,
            resolver_key="instagram.default",
        ),
    )


def _build_extraction_metadata(
    *,
    source_url: str,
    download_url: Optional[str] = None,
    content_type: Optional[str] = None,
    transcript_source: Optional[str] = None,
    resolver_metadata: Optional[Dict[str, Any]] = None,
    last_error_code: Optional[str] = None,
    failure_details: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "source_platform": "instagram",
        "extractor": "instagram_ingestion_worker",
        "extractor_version": "v2",
        "provider": "apify",
        "source_url": source_url,
        "resolved_url": download_url,
        "instagram_content_type": content_type,
        "transcript_source": transcript_source,
        "resolver_metadata": resolver_metadata,
        "last_error_code": last_error_code,
        "failure_details": failure_details,
        "resolved_at": _now_iso_utc(),
    }


async def _upload_transcript(job_id: str, text: str) -> str:
    """Upload transcript text to S3 and return the S3 key."""
    transcript_s3_key = f"{job_id}.txt"
    await s3.upload_file_object(
        bucket=TRANSCRIPT_BUCKET,
        key=transcript_s3_key,
        file_obj=BytesIO(text.encode("utf-8")),
        content_type="text/plain",
        metadata={
            "content-type": "text/plain",
            "job-type": "instagram-transcript",
            "provider": "apify_native",
        },
    )
    return transcript_s3_key


async def _publish_success_event(
    *,
    job_id: str,
    media_key: Optional[str],
    transcript_s3_key: str,
    transcription_metadata: Dict[str, Any],
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
            "transcription_metadata": transcription_metadata,
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
    normalized_url: str,
    error: InstagramIngestionError,
) -> None:
    if not job_id:
        return

    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        return

    job.extraction_metadata = _build_extraction_metadata(
        source_url=normalized_url,
        last_error_code=error.code,
        failure_details=error.details or error.code,
    )
    job.extraction_metadata["failed_at"] = _now_iso_utc()
    job.mark_failed(
        error_message=error.user_message,
        error_step="instagram_ingestion",
    )
    await database_async.update_processing_job(job)


async def process_instagram_message(message_body: Dict[str, Any]) -> Dict[str, Any]:
    """Process an Instagram ingestion message: resolve via Apify and route accordingly."""
    job_id = (message_body.get("job_id") or "").strip()
    normalized_url = (message_body.get("normalized_url") or "").strip()
    media_key = (message_body.get("media_key") or "").strip()
    user_id = (message_body.get("user_id") or "").strip()

    if not job_id:
        raise InstagramIngestionError(
            "invalid_message",
            details="missing_job_id",
            retryable=False,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )
    if not normalized_url:
        raise InstagramIngestionError(
            "invalid_message",
            details="missing_normalized_url",
            retryable=False,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )

    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        raise InstagramIngestionError(
            "invalid_message",
            details=f"processing_job_not_found:{job_id}",
            retryable=False,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )

    job.mark_downloading()
    await database_async.update_processing_job(job)

    # Resolve via InstagramApifyResolver
    resolver = InstagramApifyResolver()
    context = _build_resolve_context(
        normalized_url=normalized_url,
        media_key=media_key or job_id,
        user_id=user_id or "unknown",
    )

    try:
        resolved = await resolver.resolve(context)
    except RetryableProviderResolutionError as exc:
        raise InstagramIngestionError(
            "provider_error",
            details=f"apify_retryable:{exc}",
            retryable=True,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        ) from exc
    except NonRetryableProviderResolutionError as exc:
        raise InstagramIngestionError(
            "unsupported_content",
            details=f"apify_non_retryable:{exc}",
            retryable=False,
            user_message=_DEFAULT_UNSUPPORTED_MESSAGE,
        ) from exc

    # Extract metadata from resolver result
    resolver_metadata = resolved.metadata or {}
    content_type = resolver_metadata.get("instagram_content_type")
    transcript_source = resolver_metadata.get("transcript_source")

    # Path A: Apify returned raw_text (native transcript available)
    if resolved.raw_text:
        transcript_s3_key = await _upload_transcript(job_id, resolved.raw_text)

        extraction_metadata = _build_extraction_metadata(
            source_url=normalized_url,
            content_type=content_type,
            transcript_source=transcript_source or "apify_native",
            resolver_metadata=resolver_metadata,
        )
        job.extraction_metadata = extraction_metadata
        job.media_url = normalized_url
        job.mark_transcribing()
        await database_async.update_processing_job(job)

        transcription_metadata = {
            "provider": "apify_native",
            "model_used": "apify_instagram_reel_scraper",
            "language": None,
            "segments_count": len(
                [line for line in resolved.raw_text.splitlines() if line.strip()]
            ),
            "duration_seconds": resolver_metadata.get("duration_seconds", 0),
            "transcript_char_count": len(resolved.raw_text),
            "source_url": normalized_url,
        }

        await _publish_success_event(
            job_id=job_id,
            media_key=media_key,
            transcript_s3_key=transcript_s3_key,
            transcription_metadata=transcription_metadata,
        )

        log_event(
            logger,
            logging.INFO,
            "transcription.completed_inline",
            "Instagram video resolved with Apify native transcript",
            job_id=job_id,
            media_item_id=job_id,
            transcript_source="apify_native",
            instagram_content_type=content_type,
            transcript_char_count=len(resolved.raw_text),
        )

        return {
            "job_id": job_id,
            "media_key": media_key,
            "content_type": content_type,
            "transcript_source": "apify_native",
            "routed_to": "completion_event",
        }

    # If we reach here, the resolver returned neither raw_text nor an
    # image-post payload. This is unsupported — fail hard.
    raise InstagramIngestionError(
        "unsupported_content",
        details="no_transcript_or_image_payload",
        retryable=False,
        user_message=_DEFAULT_UNSUPPORTED_MESSAGE,
    )


async def process_message(message: Dict[str, Any]) -> None:
    body: Dict[str, Any] = {}

    try:
        body = json.loads(message.get("Body", "{}"))
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "worker.invalid_message",
            "Invalid JSON in Instagram ingestion message",
            queue=INSTAGRAM_INGESTION_QUEUE,
            exc_info=exc,
        )
        return

    context_token = bind_log_context(
        job_id=body.get("job_id"),
        media_item_id=body.get("job_id"),
        queue=INSTAGRAM_INGESTION_QUEUE,
        resolver_key="instagram.default",
        source_platform="instagram",
        provider="apify",
    )

    receive_count = int(
        (message.get("Attributes") or {}).get("ApproximateReceiveCount", "1")
    )

    try:
        await process_instagram_message(body)
    except InstagramIngestionError as exc:
        should_retry = exc.retryable and receive_count < INSTAGRAM_WORKER_MAX_RETRIES
        if should_retry:
            raise

        await _mark_job_failed(
            job_id=body.get("job_id"),
            normalized_url=(body.get("normalized_url") or "").strip(),
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
            "Instagram ingestion failed",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            error_code=exc.code,
            detail=exc.details,
        )
    except Exception as exc:
        if receive_count < INSTAGRAM_WORKER_MAX_RETRIES:
            raise

        final_error = InstagramIngestionError(
            "provider_error",
            details=f"unexpected:{type(exc).__name__}",
            retryable=False,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )
        await _mark_job_failed(
            job_id=body.get("job_id"),
            normalized_url=(body.get("normalized_url") or "").strip(),
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
            "Instagram ingestion failed after retries",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            error_code=final_error.code,
            exc_info=exc,
        )
    finally:
        reset_log_context(context_token)


async def poll_queue() -> None:
    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting Instagram ingestion worker",
        queue=INSTAGRAM_INGESTION_QUEUE,
    )
    while True:
        try:
            receive_params = get_sqs_receive_params(visibility_timeout=300)
            messages = await sqs.receive_messages(
                queue_name=INSTAGRAM_INGESTION_QUEUE,
                max_messages=receive_params["MaxNumberOfMessages"],
                wait_time_seconds=receive_params["WaitTimeSeconds"],
                visibility_timeout=receive_params["VisibilityTimeout"],
            )
            if messages:
                for message in messages:
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=INSTAGRAM_INGESTION_QUEUE,
                        max_retries=INSTAGRAM_WORKER_MAX_RETRIES,
                        worker_name="instagram_ingestion",
                    )
            else:
                await asyncio.sleep(1)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "Instagram ingestion polling failed",
                queue=INSTAGRAM_INGESTION_QUEUE,
                exc_info=exc,
            )
            await asyncio.sleep(5)


async def main() -> None:
    setup_logging("instagram-ingestion-worker")
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
