"""
Queue-first Instagram ingestion worker.

This is the only place Instagram resolution runs (task-274). The API used to
resolve inline, which could not work: yt-dlp plus, on an IP block, an Apify run
measured at 63-100 s never fit the 30 s ceiling API Gateway imposes on the
request, so every save timed out with nothing persisted while the actor run was
billed and discarded.

Pipeline:
- Consumes messages from INSTAGRAM_INGESTION_QUEUE
- Resolves content via InstagramApifyResolver (yt-dlp first, Apify Reel/Post
  Scrapers on an IP block)
- For reels: enqueues a Deepgram transcription job pointing at the resolved
  audio URL (or video URL fallback) with deepgram_mode="push" -- Instagram CDNs
  block Deepgram's pull, so the Deepgram worker downloads the bytes and posts
  them itself. Carries the caption, the comments, the derived title (task-266)
  and the Instagram quota category.
- Image posts (single and carousel) fail with unsupported_content: no OCR/vision
  pipeline exists.
- Fails terminally when no audio URL is available.
- Marks the processing job as extracting/transcribing along the way.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from media_summarizer.core.media_ingestion.domain import (
    ClassifiedUrl,
    IngestUrlCommand,
    IngestUrlRequest,
    MediaFamily,
    MediaType,
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
from media_summarizer.utils import database_async, sqs
from media_summarizer.utils.deepgram_dispatch import enqueue_deepgram_transcription
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

logger = logging.getLogger(__name__)

INSTAGRAM_INGESTION_QUEUE = required_env("INSTAGRAM_INGESTION_QUEUE")
EPISODE_COMPLETED_EVENTS_QUEUE = required_env("EPISODE_COMPLETED_EVENTS_QUEUE")
INSTAGRAM_WORKER_MAX_RETRIES = max(
    1, int(os.environ.get("INSTAGRAM_WORKER_MAX_RETRIES", "3"))
)

_DEFAULT_TEMPORARY_MESSAGE = (
    "Instagram media extraction is temporarily unavailable. Please retry."
)
_DEFAULT_UNSUPPORTED_MESSAGE = (
    "Unable to extract transcribable media from this Instagram URL."
)
_IMAGE_POST_MESSAGE = "Instagram image posts are not supported yet."


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

    job.mark_extracting()
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

    if resolved.media_type == MediaType.IMAGE_POST:
        # Single images and carousels resolve fine; there is simply nothing to
        # transcribe and no OCR/vision pipeline to send them to. Failing here
        # with a reason the user can read is the whole handling.
        log_event(
            logger,
            logging.WARNING,
            "media.ingest.unsupported",
            "Instagram image post rejected: no OCR/vision pipeline exists",
            job_id=job_id,
            media_item_id=job_id,
            instagram_content_type=content_type,
            post_type=resolver_metadata.get("post_type"),
            image_count=resolver_metadata.get("image_count", 0),
        )
        raise InstagramIngestionError(
            "unsupported_content",
            details="instagram_image_post",
            retryable=False,
            user_message=_IMAGE_POST_MESSAGE,
        )

    # The resolver returns audio_url for reels -> hand off to Deepgram in push
    # mode: Instagram CDNs block Deepgram's own fetch, so the Deepgram worker
    # downloads the bytes and posts them itself.
    if resolved.audio_url:
        duration_value = resolver_metadata.get("duration_seconds") or 0
        try:
            audio_duration_seconds = int(float(duration_value))
        except (TypeError, ValueError):
            audio_duration_seconds = 0

        extraction_metadata = _build_extraction_metadata(
            source_url=normalized_url,
            download_url=resolved.audio_url,
            content_type=content_type,
            transcript_source=transcript_source or "deepgram_pending",
            resolver_metadata=resolver_metadata,
        )
        job.extraction_metadata = extraction_metadata
        job.media_url = resolved.audio_url
        # The caption only exists once the resolver has run, and the resolver
        # runs here rather than at submission time -- so this is where the title
        # reaches the job, and through the mirror the library row (task-266).
        # Before this, the caption was resolved, logged, and dropped.
        if resolved.title:
            job.title = resolved.title
        job.mark_transcribing()
        await database_async.update_processing_job(job)

        await enqueue_deepgram_transcription(
            job_id=job_id,
            audio_url=resolved.audio_url,
            deepgram_mode="push",
            source_platform="instagram",
            media_key=media_key,
            user_id=user_id,
            user_email=message_body.get("user_email"),
            normalized_url=normalized_url,
            # The title the resolver derived from the caption, falling back to
            # what the API stored at submission (task-266).
            episode_title=job.title or message_body.get("episode_title"),
            podcast_title=job.title or message_body.get("podcast_title"),
            audio_duration_seconds=audio_duration_seconds,
            # Instagram is metered in its own quota category, not in audio
            # minutes (validated task-250 decision).
            quota_source_platform="instagram",
            resolver_key=resolved.resolver_key,
            caption=resolver_metadata.get("caption"),
            comments=resolver_metadata.get("comments", []),
            comments_count=resolver_metadata.get("comments_count", 0),
        )

        log_event(
            logger,
            logging.INFO,
            "transcription.enqueued",
            "Instagram reel queued for Deepgram (push mode)",
            job_id=job_id,
            media_item_id=job_id,
            instagram_content_type=content_type,
            transcript_source="deepgram_pending",
            audio_url_kind=resolver_metadata.get("audio_url_kind"),
        )

        return {
            "job_id": job_id,
            "media_key": media_key,
            "content_type": content_type,
            "transcript_source": "deepgram_pending",
            "routed_to": "deepgram_queue",
        }

    # If we reach here, the resolver returned no audio URL for a video post.
    # There is nothing to transcribe — fail hard.
    raise InstagramIngestionError(
        "unsupported_content",
        details="no_transcript_or_audio_url",
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
