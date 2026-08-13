"""Submission orchestrator adapters for media ingestion."""

from __future__ import annotations

import logging
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
from media_summarizer.core.services import audio_quota_gate
from media_summarizer.core.services.durable_media_service import save_media_for_user
from media_summarizer.core.services.transcript_formatting import (
    count_paragraphs,
    normalize_transcript_text,
)
from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils import media_idempotence as episode_idempotence
from media_summarizer.utils.env import required_env
from media_summarizer.utils.language_codes import normalize_language_code
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

DEFAULT_DEEPGRAM_TRANSCRIPTION_QUEUE = required_env("DEEPGRAM_TRANSCRIPTION_QUEUE")
DEFAULT_PODCASTINDEX_RESOLUTION_QUEUE = required_env("PODCASTINDEX_RESOLUTION_QUEUE")
DEFAULT_ARTICLE_EXTRACTION_QUEUE = required_env("ARTICLE_EXTRACTION_QUEUE")
DEFAULT_X_INGESTION_QUEUE = required_env("X_INGESTION_QUEUE")
DEFAULT_YOUTUBE_INGESTION_QUEUE = required_env("YOUTUBE_INGESTION_QUEUE")
DEFAULT_TIKTOK_INGESTION_QUEUE = required_env("TIKTOK_INGESTION_QUEUE")
DEFAULT_EPISODE_COMPLETED_EVENTS_QUEUE = required_env("EPISODE_COMPLETED_EVENTS_QUEUE")
DEFAULT_TRANSCRIPT_BUCKET = required_env("TRANSCRIPT_BUCKET")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _shared_text_transcription_metadata(raw_text: str) -> Dict[str, Any]:
    return {
        "provider": "shared_text",
        "language": "unknown",
        # Paragraph count, comparable with the Deepgram path (task-231 §13.1).
        "segments_count": count_paragraphs(raw_text),
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
    durable_media_item_id: Optional[str],
) -> IngestionOutcome:
    """Outcome for a media_key someone (maybe another user) already processed.

    The ids returned here are the caller's own library ids, never the id of the
    job that happens to hold the global idempotence reservation. Handing back a
    foreign job id is the §1.6.1 defect: the requesting user would poll and open
    an item that does not belong to them, while their own library row stayed
    invisible. Deduplication is a *pipeline* optimisation; the library entry is
    per user (task-218 §4.3).
    """
    existing_job_id = existing.get("job_id")
    if not existing_job_id:
        raise OrchestrationError(
            "Duplicate media_key detected but idempotence row has no job_id."
        )
    mapped_status = _status_from_idempotence(existing.get("status"))
    caller_media_item_id = durable_media_item_id or existing_job_id
    return IngestionOutcome(
        media_item_id=caller_media_item_id,
        job_id=existing_job_id,
        status=mapped_status,
        media_key=resolved.media_key,
        normalized_url=resolved.normalized_url,
        deduplicated=True,
        duplicate_of_media_item_id=caller_media_item_id,
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
        self._tiktok_ingestion_queue = (
            tiktok_ingestion_queue or DEFAULT_TIKTOK_INGESTION_QUEUE
        )

    async def submit(
        self,
        *,
        command: IngestUrlCommand | IngestSharedContentCommand,
        resolved: ResolvedMedia,
    ) -> IngestionOutcome:
        """
        Submit resolved media for processing.

        For all commands (IngestUrlCommand and IngestSharedContentCommand):
        - Creates the durable library row, carrying the requested folder_id and
          tag_ids. Organization lives there and nowhere else (task-220).
        - Allocates a minute hold for quota enforcement.
        - Routes to appropriate worker queues based on media family and type.
        - Handles direct transcription for shared text and Apify social video transcripts.
        - Manages idempotence via media_key deduplication.
        """
        title = resolved.title or f"{resolved.source_platform.value}:{resolved.media_type.value}"

        # The durable library entry is created FIRST (task-218 §4.3): everything
        # below it -- the idempotence reservation, the processing job, the queue
        # sends -- is operational state that may fail without the user losing what
        # they saved. Placing it before the duplicate short-circuit is deliberate:
        # a media_key already processed *globally* is still a brand-new library
        # entry for THIS user, and that is the case §1.6.1 got wrong by handing
        # the requesting user another user's job id.
        durable_media_item_id = await save_media_for_user(
            user_id=command.user.user_id,
            media_key=resolved.media_key,
            title=title,
            source_url=resolved.normalized_url,
            source_platform=resolved.source_platform.value,
            media_type=resolved.media_type.value,
            folder_id=command.request.folder_id,
            tag_ids=list(dict.fromkeys(command.request.tag_ids or [])),
        )

        existing = await episode_idempotence.already_processed(media_key=resolved.media_key)
        if existing and existing.get("job_id"):
            log_event(
                logger,
                logging.INFO,
                "media.ingest.duplicate_reused",
                "Existing media submission reused through idempotence",
                job_id=existing.get("job_id"),
                media_item_id=durable_media_item_id or existing.get("job_id"),
                resolver_key=resolved.resolver_key,
                media_type=resolved.media_type.value,
                source_platform=resolved.source_platform.value,
            )
            return _build_duplicate_outcome(
                resolved=resolved,
                existing=existing,
                durable_media_item_id=durable_media_item_id,
            )

        job = ProcessingJob(
            user_id=command.user.user_id,
            user_email=command.user.user_email,
            source_url=resolved.normalized_url,
            media_url=resolved.audio_url,
            media_key=resolved.media_key,
            title=title,
            source_platform=resolved.source_platform.value,
            media_type=resolved.media_type.value,
            # Pointer from the operational row to the durable one: how the status
            # mirror finds the library row, and how the workers know which
            # media_item_id to publish (task-220).
            media_item_id=durable_media_item_id,
        )

        # The id the outside world uses. It is the durable one; ``job.id`` is only
        # the fallback for the flag-off path, where no library row was written.
        canonical_media_item_id = durable_media_item_id or job.id

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
                    return _build_duplicate_outcome(
                        resolved=resolved,
                        existing=duplicate,
                        durable_media_item_id=durable_media_item_id,
                    )
                raise OrchestrationError(
                    f"Unable to reserve media key '{resolved.media_key}'."
                )

            await database_async.create_processing_job(job)
            job_created = True

            # No folder/tag write on the job: the requested organization was
            # already persisted on the durable row above, which is now the only
            # place it lives (task-220). The job used to carry a second copy that
            # every read had to prefer or reconcile.

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
                transcript_text = normalize_transcript_text(
                    resolved.raw_text,
                    source=resolved.source_platform.value,
                )
                duration_seconds = resolved.metadata.get("duration_seconds", 0)
                minutes_used = max(1, int((duration_seconds or 0) / 60) + (1 if (duration_seconds or 0) % 60 > 0 else 0))
                transcription_metadata: Dict[str, Any] = {
                    "provider": "apify_native",
                    "language": "unknown",
                    # Paragraph count, comparable with the Deepgram path (task-231 §13.1).
                    "segments_count": count_paragraphs(transcript_text),
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
                    media_item_id=canonical_media_item_id,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                    transcript_source="apify_native",
                    minutes_used=minutes_used,
                )
            elif resolved.raw_text is not None and resolved.media_family == MediaFamily.TEXT:
                transcript_s3_key = f"{job.id}.txt"
                transcript_text = normalize_transcript_text(
                    resolved.raw_text,
                    source=resolved.source_platform.value,
                )
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
                    media_item_id=canonical_media_item_id,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                    transcript_source="shared_text",
                )
            elif resolved.audio_s3_key:
                # Staged audio (WhatsApp voice notes and friends). The endpoint
                # had the bytes in hand and probed the real duration, so this is
                # the single place where the audio quota gets debited for this
                # path (task-250 Layer 1).
                gate = await audio_quota_gate.gate_audio_transcription(
                    job_id=job.id,
                    user_id=command.user.user_id,
                    job=job,
                    media_key=resolved.media_key,
                    known_duration_seconds=int(
                        resolved.metadata.get("audio_duration_seconds") or 0
                    ),
                    error_step="ingestion_core",
                )
                if gate.allowed:
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
                            "content_mime_type": resolved.metadata.get(
                                "content_mime_type"
                            ),
                            "original_name": resolved.metadata.get("original_name"),
                            "content_size_bytes": resolved.metadata.get(
                                "content_size_bytes"
                            ),
                            "audio_duration_seconds": gate.duration_seconds,
                            "quota_debited_minutes": gate.debited_minutes,
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
                        media_item_id=canonical_media_item_id,
                        queue=self._deepgram_transcription_queue,
                        resolver_key=resolved.resolver_key,
                        source_platform=resolved.source_platform.value,
                        transcript_source="deepgram",
                        audio_s3_key=resolved.audio_s3_key,
                        quota_debited_minutes=gate.debited_minutes,
                    )
                else:
                    # The gate already marked the job failed with the stable
                    # quota error code; just stop the pipeline here.
                    await episode_idempotence.mark_failed(
                        media_key=resolved.media_key,
                        job_id=job.id,
                    )
                    outcome_status = ProcessingLifecycleStatus.FAILED
            elif resolved.media_type == MediaType.IMAGE_POST:
                # Instagram image posts (single + carousel). The OCR/vision
                # pipeline they need does not exist: this branch enqueued to
                # "instagram-image-queue", a queue Terraform has never created
                # and no worker has ever consumed, so every image post silently
                # stalled in EXTRACTING forever. Fail the job with a user-facing
                # reason instead of pretending it was queued.
                job.mark_failed(
                    error_message="unsupported_content: Instagram image posts are not supported yet.",
                    error_step="ingestion_core",
                )
                await database_async.update_processing_job(job)
                await episode_idempotence.mark_failed(
                    media_key=resolved.media_key,
                    job_id=job.id,
                )
                outcome_status = ProcessingLifecycleStatus.FAILED
                log_event(
                    logger,
                    logging.WARNING,
                    "media.ingest.unsupported",
                    "Instagram image post rejected: no OCR/vision pipeline exists",
                    job_id=job.id,
                    media_item_id=canonical_media_item_id,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                    post_type=resolved.metadata.get("post_type"),
                    image_count=resolved.metadata.get("image_count", 0),
                )
            elif resolved.media_family == MediaFamily.SOCIAL_VIDEO and resolved.audio_url:
                # Instagram reels/video posts and other social video with a remote audio URL.
                # Social video CDNs (Instagram, TikTok, X) block Deepgram IPs -> push mode.
                # `quota_source_platform` keeps this path metered as its own
                # category (article for instagram/x) instead of audio minutes:
                # the validated task-250 decision leaves social video where it is.
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
                        "quota_source_platform": resolved.source_platform.value,
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
                    media_item_id=canonical_media_item_id,
                    queue=self._deepgram_transcription_queue,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                    transcript_source="deepgram",
                )
            elif resolved.audio_url:
                # Direct audio URL: nobody told us how long it is, so the gate
                # runs an HTTP Range probe on the container before committing to
                # a transcription (task-250 Layer 1).
                gate = await audio_quota_gate.gate_audio_transcription(
                    job_id=job.id,
                    user_id=command.user.user_id,
                    job=job,
                    media_key=resolved.media_key,
                    audio_url=resolved.audio_url,
                    known_duration_seconds=int(
                        resolved.metadata.get("audio_duration_seconds") or 0
                    ),
                    error_step="ingestion_core",
                )
                if gate.allowed:
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
                            "audio_duration_seconds": gate.duration_seconds,
                            "quota_debited_minutes": gate.debited_minutes,
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
                        media_item_id=canonical_media_item_id,
                        queue=self._deepgram_transcription_queue,
                        resolver_key=resolved.resolver_key,
                        source_platform=resolved.source_platform.value,
                        transcript_source="deepgram",
                        audio_duration_seconds=gate.duration_seconds,
                        quota_debited_minutes=gate.debited_minutes,
                    )
                else:
                    await episode_idempotence.mark_failed(
                        media_key=resolved.media_key,
                        job_id=job.id,
                    )
                    outcome_status = ProcessingLifecycleStatus.FAILED
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
                    media_item_id=canonical_media_item_id,
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
                    media_item_id=canonical_media_item_id,
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
                    media_item_id=canonical_media_item_id,
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
                # task-216: the transcript language resolved by the API (explicit
                # request override, else the user's reading_language) travels to
                # the worker so the provider is asked for the right language.
                # ``IngestSharedContentRequest`` has no ``transcript_language``
                # field, so read it defensively: a shared YouTube URL resolves
                # into this same branch and would otherwise raise AttributeError.
                requested_transcript_language = normalize_language_code(
                    getattr(command.request, "transcript_language", None)
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
                    media_item_id=canonical_media_item_id,
                    queue=self._youtube_ingestion_queue,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                    transcript_language=requested_transcript_language,
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
                    media_item_id=canonical_media_item_id,
                    queue=self._podcastindex_resolution_queue,
                    resolver_key=resolved.resolver_key,
                    source_platform=resolved.source_platform.value,
                )

            return IngestionOutcome(
                media_item_id=canonical_media_item_id,
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
