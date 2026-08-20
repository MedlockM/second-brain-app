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
from media_summarizer.core.services import audio_quota_gate, cover_capture
from media_summarizer.infrastructure import apify_adapter
from media_summarizer.infrastructure.apify_adapter import ApifyActorKind
from media_summarizer.infrastructure.resolvers.instagram_apify_resolver import (
    InstagramApifyRequired,
    InstagramApifyResolver,
    InstagramContentType,
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
from media_summarizer.workers import apify_orchestration
from media_summarizer.workers.base_worker import (
    get_sqs_receive_params,
    process_message_with_retry,
)

logger = logging.getLogger(__name__)

INSTAGRAM_INGESTION_QUEUE = required_env("INSTAGRAM_INGESTION_QUEUE")
EPISODE_COMPLETED_EVENTS_QUEUE = required_env("EPISODE_COMPLETED_EVENTS_QUEUE")
INSTAGRAM_WORKER_MAX_RETRIES = max(1, int(os.environ.get("INSTAGRAM_WORKER_MAX_RETRIES", "3")))

_DEFAULT_TEMPORARY_MESSAGE = "Instagram media extraction is temporarily unavailable. Please retry."
_DEFAULT_UNSUPPORTED_MESSAGE = "Unable to extract transcribable media from this Instagram URL."
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
    if job.apify_state == "processing":
        job.apify_state = "processed"
        job.apify_completed_at = datetime.now(timezone.utc)
    job.mark_failed(
        error_message=error.user_message,
        error_step="instagram_ingestion",
    )
    await database_async.update_processing_job(job)


async def process_instagram_message(message_body: Dict[str, Any]) -> Dict[str, Any]:
    """Process an initial, callback, or deadline Instagram queue message."""
    message_type = str(message_body.get("message_type") or "ingest")
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

    resolver = InstagramApifyResolver()

    if message_type == "apify_backstop":
        expired = await apify_orchestration.expire_backstop(
            job_id=job_id,
            run_id=str(message_body.get("apify_run_id") or ""),
            source_platform="instagram",
        )
        if expired:
            await _publish_failure_event(
                job_id=job_id,
                media_key=media_key or expired.media_key,
                reason="apify_callback_deadline_exceeded",
            )
        return {"job_id": job_id, "routed_to": "backstop"}

    if message_type == "apify_callback":
        run_id = str(message_body.get("apify_run_id") or "").strip()
        job = await apify_orchestration.claim_callback(job_id, run_id)
        if not job:
            return {"job_id": job_id, "routed_to": "duplicate_callback"}
        if str(message_body.get("apify_status") or "") != "SUCCEEDED":
            raise InstagramIngestionError(
                "provider_error",
                details=f"apify_terminal_{message_body.get('apify_status')}",
                retryable=False,
                user_message=_DEFAULT_TEMPORARY_MESSAGE,
            )
        stored_context = dict(job.apify_context or {})
        normalized_url = str(stored_context.get("normalized_url") or "").strip()
        media_key = str(stored_context.get("media_key") or job.media_key or "").strip()
        user_id = str(stored_context.get("user_id") or job.user_id).strip()
        try:
            content_type = InstagramContentType(str(stored_context.get("instagram_content_type") or ""))
            items = await apify_adapter.fetch_dataset_items(
                source_platform="instagram",
                dataset_id=job.apify_dataset_id or "",
            )
            context = _build_resolve_context(
                normalized_url=normalized_url,
                media_key=media_key or job_id,
                user_id=user_id or "unknown",
            )
            resolved = resolver.resolve_apify_dataset(
                context=context,
                content_type=content_type,
                actor_id=job.apify_actor_id or "",
                items=items,
            )
        except apify_adapter.ApifyAdapterError as exc:
            raise InstagramIngestionError(
                "provider_error",
                details=exc.code,
                retryable=exc.retryable,
                user_message=_DEFAULT_TEMPORARY_MESSAGE,
            ) from exc
        except (ValueError, NonRetryableProviderResolutionError) as exc:
            raise InstagramIngestionError(
                "unsupported_content",
                details=f"apify_result_invalid:{exc}",
                retryable=False,
                user_message=_DEFAULT_UNSUPPORTED_MESSAGE,
            ) from exc
        message_body = stored_context
    else:
        job.mark_extracting()
        await database_async.update_processing_job(job)
        context = _build_resolve_context(
            normalized_url=normalized_url,
            media_key=media_key or job_id,
            user_id=user_id or "unknown",
        )
        try:
            # Always raises `InstagramApifyRequired` since task-310: Apify is
            # the only Instagram path, so the resolver classifies and hands
            # over. The assignment satisfies the `ContentResolverPort`
            # signature; only the callback continuation below produces a
            # terminal `ResolvedMedia`.
            resolved = await resolver.resolve(context)
        except InstagramApifyRequired as exc:
            kind = ApifyActorKind.INSTAGRAM_POST if exc.content_type == InstagramContentType.POST else ApifyActorKind.INSTAGRAM_REEL
            stored_context = {
                **message_body,
                "normalized_url": exc.normalized_url,
                "instagram_content_type": exc.content_type.value,
            }
            try:
                run = await apify_orchestration.start_run_for_job(
                    job=job,
                    kind=kind,
                    source_platform="instagram",
                    input_data=resolver.build_apify_input(
                        normalized_url=exc.normalized_url,
                        content_type=exc.content_type,
                    ),
                    queue_name=INSTAGRAM_INGESTION_QUEUE,
                    context=stored_context,
                )
            except apify_adapter.ApifyAdapterError as adapter_exc:
                raise InstagramIngestionError(
                    "provider_error",
                    details=adapter_exc.code,
                    retryable=adapter_exc.retryable,
                    user_message=_DEFAULT_TEMPORARY_MESSAGE,
                ) from adapter_exc
            return {
                "job_id": job_id,
                "media_key": media_key,
                "content_type": exc.content_type.value,
                "routed_to": "apify_webhook",
                "apify_run_id": run.run_id,
            }
        except RetryableProviderResolutionError as exc:
            raise InstagramIngestionError(
                "provider_error",
                details=f"resolver_retryable:{exc}",
                retryable=True,
                user_message=_DEFAULT_TEMPORARY_MESSAGE,
            ) from exc
        except NonRetryableProviderResolutionError as exc:
            raise InstagramIngestionError(
                "unsupported_content",
                details=f"resolver_non_retryable:{exc}",
                retryable=False,
                user_message=_DEFAULT_UNSUPPORTED_MESSAGE,
            ) from exc

    # Extract metadata from resolver result
    resolver_metadata = resolved.metadata or {}
    resolved_content_type = resolver_metadata.get("instagram_content_type")
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
            instagram_content_type=resolved_content_type,
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
            content_type=resolved_content_type,
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
        # The account name and the cover exist for the same reason and at the
        # same moment as the caption: the resolver just ran. Instagram serves
        # signed `scontent.*.cdninstagram.com` URLs that 403 within days, so the
        # cover is re-hosted rather than stored as-is (task-302 §5.1). A failure
        # returns None and the tile falls back to its media-type icon.
        if resolved.creator_name:
            job.creator_name = resolved.creator_name
        cover_locator = await cover_capture.capture_from_url(
            source_url=resolved.cover_url,
            media_item_id=job.media_item_id,
        )
        if cover_locator:
            job.media_image = cover_locator
        job.mark_transcribing()
        if message_type == "apify_callback":
            if not await apify_orchestration.complete_callback(job):
                return {"job_id": job_id, "routed_to": "duplicate_callback"}
        else:
            await database_async.update_processing_job(job)

        # A reel is about to be transcribed by the minute like any other audio:
        # the meter follows the provider call, not the URL (task-287). This gate
        # is the last point where that Deepgram spend can still be refused, and
        # the only place it is charged -- without it a reel was transcribed for
        # free whatever the user's remaining allowance.
        gate = await audio_quota_gate.gate_audio_transcription(
            job_id=job_id,
            user_id=user_id,
            job=job,
            media_key=media_key,
            known_duration_seconds=audio_duration_seconds,
            error_step="instagram_ingestion",
        )
        if not gate.allowed:
            return {
                "job_id": job_id,
                "media_key": media_key,
                "content_type": resolved_content_type,
                "routed_to": "quota_refused",
                "error_code": gate.error_code,
            }

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
            audio_duration_seconds=gate.duration_seconds or audio_duration_seconds,
            quota_debited_minutes=gate.debited_minutes,
            quota_debit_skipped=gate.debit_skipped,
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
            instagram_content_type=resolved_content_type,
            transcript_source="deepgram_pending",
            audio_url_kind=resolver_metadata.get("audio_url_kind"),
        )

        return {
            "job_id": job_id,
            "media_key": media_key,
            "content_type": resolved_content_type,
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

    receive_count = int((message.get("Attributes") or {}).get("ApproximateReceiveCount", "1"))

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
            receive_params = get_sqs_receive_params(visibility_timeout=360)
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
