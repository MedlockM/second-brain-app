"""Submission orchestrator adapters for media ingestion."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, Optional

from media_summarizer.core.media_ingestion.domain import (
    IngestionOutcome,
    IngestSharedContentCommand,
    IngestUrlCommand,
    MediaFamily,
    MediaType,
    ProcessingLifecycleStatus,
    ResolvedMedia,
)
from media_summarizer.core.media_ingestion.errors import OrchestrationError
from media_summarizer.core.media_ingestion.ports import SubmissionOrchestratorPort
from media_summarizer.core.models import ProcessingJob
from media_summarizer.core.services.transcript_translation import (
    prewarm_translated_transcript,
)
from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils import media_idempotence as episode_idempotence
from media_summarizer.utils.logging_config import log_event
from media_summarizer.utils.user_media_submissions import mark_user_submission as mark_user_media_submission

logger = logging.getLogger(__name__)

DEFAULT_DEEPGRAM_TRANSCRIPTION_QUEUE = os.environ.get(
    "DEEPGRAM_TRANSCRIPTION_QUEUE", "deepgram-transcription-queue"
)
DEFAULT_PODCASTINDEX_RESOLUTION_QUEUE = os.environ.get(
    "PODCASTINDEX_RESOLUTION_QUEUE", "podcastindex-resolution-queue"
)
DEFAULT_ARTICLE_EXTRACTION_QUEUE = os.environ.get(
    "ARTICLE_EXTRACTION_QUEUE", "article-extraction-queue"
)
DEFAULT_X_INGESTION_QUEUE = os.environ.get(
    "X_INGESTION_QUEUE", "x-ingestion-queue"
)
DEFAULT_YOUTUBE_INGESTION_QUEUE = os.environ.get(
    "YOUTUBE_INGESTION_QUEUE", "youtube-ingestion-queue"
)
DEFAULT_TIKTOK_INGESTION_QUEUE = os.environ.get(
    "TIKTOK_INGESTION_QUEUE", "tiktok-ingestion-queue"
)
DEFAULT_INSTAGRAM_IMAGE_QUEUE = os.environ.get(
    "INSTAGRAM_IMAGE_QUEUE", "instagram-image-queue"
)
DEFAULT_EPISODE_COMPLETED_EVENTS_QUEUE = os.environ.get(
    "EPISODE_COMPLETED_EVENTS_QUEUE", "episode-completed-events"
)
DEFAULT_TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcripts"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _shared_text_transcription_metadata(raw_text: str) -> Dict[str, Any]:
    return {
        "provider": "shared_text",
        "language": "unknown",
        "segments_count": len((raw_text or "").split()),
        "duration_seconds": 0,
        "transcribed_at": _now_iso(),
    }


def _status_from_idempotence(status: Optional[str]) -> ProcessingLifecycleStatus:
    value = (status or "").lower().strip()
    if value == "processed":
        return ProcessingLifecycleStatus.READY_FOR_ARTIFACTS
    if value == "failed":
        return ProcessingLifecycleStatus.FAILED
    return ProcessingLifecycleStatus.PENDING


def _build_duplicate_outcome(
    *,
    resolved: ResolvedMedia,
    existing: Dict[str, Any],
) -> IngestionOutcome:
    existing_job_id = existing.get("job_id")
    if not existing_job_id:
        raise OrchestrationError(
            "Duplicate media_key detected but idempotence row has no job_id."
        )
    mapped_status = _status_from_idempotence(existing.get("status"))
    return IngestionOutcome(
        media_item_id=existing_job_id,
        job_id=existing_job_id,
        status=mapped_status,
        media_key=resolved.media_key,
        normalized_url=resolved.normalized_url,
        deduplicated=True,
        duplicate_of_media_item_id=existing_job_id,
        metadata={
            "idempotence_status": existing.get("status"),
            "resolver_key": resolved.resolver_key,
            "media_family": resolved.media_family.value,
            "media_type": resolved.media_type.value,
            "source_platform": resolved.source_platform.value,
        },
    )


class ProcessingJobSubmissionOrchestrator(SubmissionOrchestratorPort):
    """
    Transitional orchestrator adapter.

    Uses existing `ProcessingJob` persistence and queue infrastructure while
    keeping orchestration behind a dedicated port.
    """

    def __init__(
        self,
        *,
        deepgram_transcription_queue: Optional[str] = None,
        podcastindex_resolution_queue: Optional[str] = None,
        article_extraction_queue: Optional[str] = None,
        x_ingestion_queue: Optional[str] = None,
        youtube_ingestion_queue: Optional[str] = None,
        tiktok_ingestion_queue: Optional[str] = None,
        instagram_image_queue: Optional[str] = None,
    ) -> None:
        self._deepgram_transcription_queue = (
            deepgram_transcription_queue
            or DEFAULT_DEEPGRAM_TRANSCRIPTION_QUEUE
        )
        self._podcastindex_resolution_queue = (
            podcastindex_resolution_queue or DEFAULT_PODCASTINDEX_RESOLUTION_QUEUE
        )
        self._article_extraction_queue = (
            article_extraction_queue or DEFAULT_ARTICLE_EXTRACTION_QUEUE
        )
        self._x_ingestion_queue = x_ingestion_queue or DEFAULT_X_INGESTION_QUEUE
        self._youtube_ingestion_queue = (
            youtube_ingestion_queue or DEFAULT_YOUTUBE_INGESTION_QUEUE
        )
        self._instagram_image_queue = (
            instagram_image_queue or DEFAULT_INSTAGRAM_IMAGE_QUEUE
        )
        self._tiktok_ingestion_queue = (
            tiktok_ingestion_queue or DEFAULT_TIKTOK_INGESTION_QUEUE
        )

    async def submit(
        self,
        *,
        command: IngestUrlCommand | IngestSharedContentCommand,
        resolved: ResolvedMedia,
    ) -> IngestionOutcome:
        existing = await episode_idempotence.already_processed(media_key=resolved.media_key)
        if existing and existing.get("job_id"):
            log_event(
                logger,
                logging.INFO,
                "media.ingest.duplicate_reused",
                "Existing media submission reused through idempotence",
                job_id=existing.get("job_id"),
                media_item_id=existing.get("job_id"),
                resolver_key=resolved.resolver_key,
                media_type=resolved.media_type.value,
                source_platform=resolved.source_platform.value,
            )
            return _build_duplicate_outcome(resolved=resolved, existing=existing)

        title = resolved.title or f"{resolved.source_platform.value}:{resolved.media_type.value}"

        job = ProcessingJob(
            user_id=command.user.user_id,
            user_email=command.user.user_email,
            source_url=resolved.normalized_url,
            media_url=resolved.audio_url,
            media_key=resolved.media_key,
            title=title,
            source_platform=resolved.source_platform.value,
            media_type=resolved.media_type.value,
        )

        reservation_created = False
        job_created = False
        try:
            reservation_created = await episode_idempotence.reserve_or_skip(
                media_key=resolved.media_key,
                job_id=job.id,
            )
            if not reservation_created:
                duplicate = await episode_idempotence.already_processed(
                    media_key=resolved.media_key
                )
                if duplicate:
                    return _build_duplicate_outcome(resolved=resolved, existing=duplicate)
                raise OrchestrationError(
                    f"Unable to reserve media key '{resolved.media_key}'."
                )

            await database_async.create_processing_job(job)
            job_created = True

            try:
                await mark_user_media_submission(
                    user_id=command.user.user_id,
                    media_key=resolved.media_key,
                    job_id=job.id,
                    source=command.request.source_app
                    or (
                        "ingest-shared-content"
                        if isinstance(command, IngestSharedContentCommand)
                        else "ingest-url"
                    ),
                )
            except Exception as exc:
                log_event(
                    logger,
                    logging.WARNING,
                    "external_call.failed",
                    "Failed to record user media submission",
                    provider="dynamodb",
                    user_id=command.user.user_id,
                    job_id=job.id,
                    resolver_key=resolved.resolver_key,
                    exc_info=exc,
                )

            pipeline_enqueued = False
            podcastindex_resolution_enqueued = False
            article_extraction_enqueued = False
            x_ingestion_enqueued = False
            youtube_ingestion_enqueued = False
            tiktok_ingestion_enqueued = False
            social_video_transcription_enqueued = False
            outcome_status = ProcessingLifecycleStatus.PENDING
            if resolved.raw_text is not None and resolved.media_family == MediaFamily.SOCIAL_VIDEO:
                # Apify transcript bypass: store transcript directly, skip Deepgram.
                transcript_s3_key = f"{job.id}.txt"
                transcript_text = resolved.raw_text.strip()
                duration_seconds = resolved.metadata.get("duration_seconds", 0)
                minutes_used = max(1, int((duration_seconds or 0) / 60) + (1 if (duration_seconds or 0) % 60 > 0 else 0))
                transcription_metadata: Dict[str, Any] = {
                    "provider": "apify_native",
                    "language": "unknown",
                    "segments_count": len(transcript_text.split()),
                    "duration_seconds": duration_seconds or 0,
                    "transcribed_at": _now_iso(),
                    "transcript_source": resolved.metadata.get("transcript_source", "apify_native"),
                }
                await s3.upload_file_object(
                    bucket=DEFAULT_TRANSCRIPT_BUCKET,
                    key=transcript_s3_key,
                    file_obj=BytesIO(transcript_text.encode("utf-8")),
                    content_type="text/plain",
                    metadata={
                        "content-type": "text/plain",
                        "provider": "apify_native",
                        "source-platform": resolved.source_platform.value,
                    },
                )
                job.set_transcription_location(transcript_s3_key)
                job.set_transcription_metadata(transcription_metadata)
                await prewarm_translated_transcript(
                    job, transcript_s3_key, transcript_text
                )
                job.mark_completed()
                await database_async.update_processing_job(job)
                await sqs.send_message(
                    queue_name=DEFAULT_EPISODE_COMPLETED_EVENTS_QUEUE,
                    message_body={
                        "event_type": "episode_completion_status",
                        "status": "success",
                        "media_key": resolved.media_key,
                        "canonical_job_id": job.id,
                        "minutes_used": minutes_used,
                        "transcription_s3_key": transcript_s3_key,
                        "transcription_metadata": transcription_metadata,
                    },
                )
                pipeline_enqueued = True
                outcome_status = ProcessingLifecycleStatus.COMPLETED
                log_event(
                    logger,
                    logging.INFO,
                    "transcription.completed",
                    "Social video transcript stored from Apify native transcript",
                    job_id=job.id,
                    media_item_id=job.id,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                    transcript_source="apify_native",
                    minutes_used=minutes_used,
                )
            elif resolved.raw_text is not None and resolved.media_family == MediaFamily.TEXT:
                transcript_s3_key = f"{job.id}.txt"
                transcript_text = resolved.raw_text.strip()
                transcription_metadata = _shared_text_transcription_metadata(
                    transcript_text
                )
                await s3.upload_file_object(
                    bucket=DEFAULT_TRANSCRIPT_BUCKET,
                    key=transcript_s3_key,
                    file_obj=BytesIO(transcript_text.encode("utf-8")),
                    content_type="text/plain",
                    metadata={
                        "content-type": "text/plain",
                        "provider": "shared_text",
                        "source-platform": resolved.source_platform.value,
                    },
                )
                job.set_transcription_location(transcript_s3_key)
                job.set_transcription_metadata(transcription_metadata)
                await prewarm_translated_transcript(
                    job, transcript_s3_key, transcript_text
                )
                job.mark_completed()
                await database_async.update_processing_job(job)
                await sqs.send_message(
                    queue_name=DEFAULT_EPISODE_COMPLETED_EVENTS_QUEUE,
                    message_body={
                        "event_type": "episode_completion_status",
                        "status": "success",
                        "media_key": resolved.media_key,
                        "canonical_job_id": job.id,
                        "minutes_used": 1,
                        "transcription_s3_key": transcript_s3_key,
                        "transcription_metadata": transcription_metadata,
                    },
                )
                pipeline_enqueued = True
                outcome_status = ProcessingLifecycleStatus.COMPLETED
                log_event(
                    logger,
                    logging.INFO,
                    "transcription.completed",
                    "Shared text transcript stored without queued transcription",
                    job_id=job.id,
                    media_item_id=job.id,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                    transcript_source="shared_text",
                )
            elif resolved.audio_s3_key:
                job.set_audio_location(resolved.audio_s3_key)
                await database_async.update_processing_job(job)
                await sqs.send_message(
                    queue_name=self._deepgram_transcription_queue,
                    message_body={
                        "job_id": job.id,
                        "user_id": command.user.user_id,
                        "user_email": command.user.user_email,
                        "audio_s3_key": resolved.audio_s3_key,
                        "audio_url": resolved.audio_url,
                        "media_key": resolved.media_key,
                        "normalized_url": resolved.normalized_url,
                        "episode_title": title,
                        "podcast_title": title,
                        "content_mime_type": resolved.metadata.get("content_mime_type"),
                        "original_name": resolved.metadata.get("original_name"),
                        "content_size_bytes": resolved.metadata.get("content_size_bytes"),
                        "deepgram_mode": "pull",
                    },
                )
                pipeline_enqueued = True
                log_event(
                    logger,
                    logging.INFO,
                    "transcription.enqueued",
                    "Staged audio transcription enqueued",
                    job_id=job.id,
                    media_item_id=job.id,
                    queue=self._deepgram_transcription_queue,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                    transcript_source="deepgram",
                    audio_s3_key=resolved.audio_s3_key,
                )
            elif resolved.media_type == MediaType.IMAGE_POST:
                # Instagram image posts (single + carousel) — dispatch to image/OCR queue
                # Caption is persisted in metadata; images sent for visual processing
                job.mark_extracting()
                await database_async.update_processing_job(job)
                await sqs.send_message(
                    queue_name=self._instagram_image_queue,
                    message_body={
                        "job_id": job.id,
                        "user_id": command.user.user_id,
                        "user_email": command.user.user_email,
                        "media_key": resolved.media_key,
                        "normalized_url": resolved.normalized_url,
                        "source_platform": resolved.source_platform.value,
                        "resolver_key": resolved.resolver_key,
                        "image_urls": resolved.metadata.get("image_urls", []),
                        "image_count": resolved.metadata.get("image_count", 0),
                        "post_type": resolved.metadata.get("post_type"),
                        "caption": resolved.metadata.get("caption"),
                        "comments": resolved.metadata.get("comments", []),
                        "comments_count": resolved.metadata.get("comments_count", 0),
                        "episode_title": title,
                        "podcast_title": title,
                    },
                )
                pipeline_enqueued = True
                outcome_status = ProcessingLifecycleStatus.EXTRACTING
                log_event(
                    logger,
                    logging.INFO,
                    "worker.enqueued",
                    "Instagram image post enqueued for OCR/vision processing",
                    job_id=job.id,
                    media_item_id=job.id,
                    queue=self._instagram_image_queue,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                    post_type=resolved.metadata.get("post_type"),
                    image_count=resolved.metadata.get("image_count", 0),
                )
            elif resolved.media_family == MediaFamily.SOCIAL_VIDEO and resolved.audio_url:
                # Instagram reels/video posts and other social video with a remote audio URL.
                # Social video CDNs (Instagram, TikTok, X) block Deepgram IPs -> push mode.
                job.mark_transcribing()
                await database_async.update_processing_job(job)
                await sqs.send_message(
                    queue_name=self._deepgram_transcription_queue,
                    message_body={
                        "job_id": job.id,
                        "user_id": command.user.user_id,
                        "user_email": command.user.user_email,
                        "audio_url": resolved.audio_url,
                        "media_key": resolved.media_key,
                        "normalized_url": resolved.normalized_url,
                        "source_platform": resolved.source_platform.value,
                        "resolver_key": resolved.resolver_key,
                        "episode_title": title,
                        "podcast_title": title,
                        "caption": resolved.metadata.get("caption"),
                        "comments": resolved.metadata.get("comments", []),
                        "comments_count": resolved.metadata.get("comments_count", 0),
                        "deepgram_mode": "push",
                    },
                )
                pipeline_enqueued = True
                social_video_transcription_enqueued = True
                outcome_status = ProcessingLifecycleStatus.TRANSCRIBING
                log_event(
                    logger,
                    logging.INFO,
                    "transcription.enqueued",
                    "Social video transcription enqueued",
                    job_id=job.id,
                    media_item_id=job.id,
                    queue=self._deepgram_transcription_queue,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                    transcript_source="deepgram",
                )
            elif resolved.audio_url:
                await sqs.send_message(
                    queue_name=self._deepgram_transcription_queue,
                    message_body={
                        "job_id": job.id,
                        "user_id": command.user.user_id,
                        "user_email": command.user.user_email,
                        "audio_url": resolved.audio_url,
                        "media_key": resolved.media_key,
                        "normalized_url": resolved.normalized_url,
                        "episode_title": title,
                        "podcast_title": title,
                        "deepgram_mode": "pull_with_push_fallback",
                    },
                )
                pipeline_enqueued = True
                log_event(
                    logger,
                    logging.INFO,
                    "transcription.enqueued",
                    "Direct audio transcription enqueued",
                    job_id=job.id,
                    media_item_id=job.id,
                    queue=self._deepgram_transcription_queue,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                    transcript_source="deepgram",
                )
            elif resolved.resolver_key == "x.default":
                await sqs.send_message(
                    queue_name=self._x_ingestion_queue,
                    message_body={
                        "job_id": job.id,
                        "user_id": command.user.user_id,
                        "user_email": command.user.user_email,
                        "media_key": resolved.media_key,
                        "normalized_url": resolved.normalized_url,
                        "resolver_key": resolved.resolver_key,
                        "source_platform": resolved.source_platform.value,
                        "tweet_id": str(resolved.metadata.get("tweet_id") or "").strip(),
                    },
                )
                pipeline_enqueued = True
                x_ingestion_enqueued = True
                log_event(
                    logger,
                    logging.INFO,
                    "worker.enqueued",
                    "X ingestion enqueued",
                    job_id=job.id,
                    media_item_id=job.id,
                    queue=self._x_ingestion_queue,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                )
            elif resolved.media_family == MediaFamily.ARTICLE:
                await sqs.send_message(
                    queue_name=self._article_extraction_queue,
                    message_body={
                        "job_id": job.id,
                        "user_id": command.user.user_id,
                        "user_email": command.user.user_email,
                        "media_key": resolved.media_key,
                        "normalized_url": resolved.normalized_url,
                        "resolver_key": resolved.resolver_key,
                    },
                )
                pipeline_enqueued = True
                article_extraction_enqueued = True
                log_event(
                    logger,
                    logging.INFO,
                    "worker.enqueued",
                    "Article extraction enqueued",
                    job_id=job.id,
                    media_item_id=job.id,
                    queue=self._article_extraction_queue,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                )
            elif resolved.resolver_key == "tiktok.default":
                job.mark_extracting()
                await database_async.update_processing_job(job)
                await sqs.send_message(
                    queue_name=self._tiktok_ingestion_queue,
                    message_body={
                        "job_id": job.id,
                        "user_id": command.user.user_id,
                        "user_email": command.user.user_email,
                        "media_key": resolved.media_key,
                        "normalized_url": resolved.normalized_url,
                        "resolver_key": resolved.resolver_key,
                        "episode_title": title,
                        "podcast_title": title,
                    },
                )
                pipeline_enqueued = True
                tiktok_ingestion_enqueued = True
                log_event(
                    logger,
                    logging.INFO,
                    "worker.enqueued",
                    "TikTok ingestion enqueued",
                    job_id=job.id,
                    media_item_id=job.id,
                    queue=self._tiktok_ingestion_queue,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                )
            elif resolved.media_family == MediaFamily.YOUTUBE:
                job.mark_extracting()
                await database_async.update_processing_job(job)
                message_body: Dict[str, Any] = {
                    "job_id": job.id,
                    "user_id": command.user.user_id,
                    "user_email": command.user.user_email,
                    "media_key": resolved.media_key,
                    "normalized_url": resolved.normalized_url,
                    "resolver_key": resolved.resolver_key,
                    "episode_title": title,
                    "podcast_title": title,
                }
                requested_transcript_language = getattr(
                    command.request,
                    "transcript_language",
                    None,
                )
                if command.request.locale:
                    message_body["locale"] = command.request.locale
                if requested_transcript_language:
                    message_body["transcript_language"] = (
                        requested_transcript_language
                    )
                await sqs.send_message(
                    queue_name=self._youtube_ingestion_queue,
                    message_body=message_body,
                )
                pipeline_enqueued = True
                youtube_ingestion_enqueued = True
                log_event(
                    logger,
                    logging.INFO,
                    "worker.enqueued",
                    "YouTube ingestion enqueued",
                    job_id=job.id,
                    media_item_id=job.id,
                    queue=self._youtube_ingestion_queue,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                )
            elif resolved.media_family == MediaFamily.PODCAST:
                # Queue-first PodcastIndex resolution to absorb bursts off API path.
                job.mark_extracting()
                await database_async.update_processing_job(job)
                await sqs.send_message(
                    queue_name=self._podcastindex_resolution_queue,
                    message_body={
                        "job_id": job.id,
                        "user_id": command.user.user_id,
                        "user_email": command.user.user_email,
                        "media_key": resolved.media_key,
                        "normalized_url": resolved.normalized_url,
                        "source_platform": resolved.source_platform.value,
                        "resolver_key": resolved.resolver_key,
                        "episode_title": title,
                        "podcast_title": title,
                    },
                )
                pipeline_enqueued = True
                podcastindex_resolution_enqueued = True
                log_event(
                    logger,
                    logging.INFO,
                    "worker.enqueued",
                    "Podcast resolution enqueued",
                    job_id=job.id,
                    media_item_id=job.id,
                    queue=self._podcastindex_resolution_queue,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                )

            return IngestionOutcome(
                media_item_id=job.id,
                job_id=job.id,
                status=(
                    outcome_status
                    if outcome_status != ProcessingLifecycleStatus.PENDING
                    else ProcessingLifecycleStatus.EXTRACTING
                    if tiktok_ingestion_enqueued
                    else ProcessingLifecycleStatus.PENDING
                ),
                media_key=resolved.media_key,
                normalized_url=resolved.normalized_url,
                deduplicated=False,
                metadata={
                    "resolver_key": resolved.resolver_key,
                    "pipeline_enqueued": pipeline_enqueued,
                    "podcastindex_resolution_enqueued": podcastindex_resolution_enqueued,
                    "article_extraction_enqueued": article_extraction_enqueued,
                    "x_ingestion_enqueued": x_ingestion_enqueued,
                    "youtube_ingestion_enqueued": youtube_ingestion_enqueued,
                    "tiktok_ingestion_enqueued": tiktok_ingestion_enqueued,
                    "social_video_transcription_enqueued": social_video_transcription_enqueued,
                    "media_family": resolved.media_family.value,
                    "media_type": resolved.media_type.value,
                    "source_platform": resolved.source_platform.value,
                },
            )

        except Exception as exc:
            if job_created:
                try:
                    job.mark_failed(
                        error_message=f"ingestion_core_submission_failed: {exc}",
                        error_step="ingestion_core",
                    )
                    await database_async.update_processing_job(job)
                    await episode_idempotence.mark_failed(
                        media_key=resolved.media_key,
                        job_id=job.id,
                    )
                except Exception as update_exc:
                    log_event(
                        logger,
                        logging.WARNING,
                        "external_call.failed",
                        "Failed to persist orchestrator job failure state",
                        job_id=job.id,
                        resolver_key=resolved.resolver_key,
                        provider="dynamodb",
                        exc_info=update_exc,
                    )
            elif reservation_created:
                try:
                    await episode_idempotence.release_reservation(
                        media_key=resolved.media_key,
                        job_id=job.id,
                    )
                except Exception as release_exc:
                    log_event(
                        logger,
                        logging.WARNING,
                        "external_call.failed",
                        "Failed to release media key reservation",
                        job_id=job.id,
                        resolver_key=resolved.resolver_key,
                        provider="dynamodb",
                        exc_info=release_exc,
                    )

            if isinstance(exc, OrchestrationError):
                raise
            raise OrchestrationError(
                f"Failed to orchestrate media submission for key '{resolved.media_key}': {exc}"
            ) from exc
