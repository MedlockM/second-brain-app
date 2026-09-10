"""Submission orchestrator adapters for media ingestion."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, NamedTuple, Optional

from media_summarizer.core.media_ingestion.domain import (
    IngestionOutcome,
    IngestSharedContentCommand,
    IngestUrlCommand,
    MediaFamily,
    ProcessingLifecycleStatus,
    ResolvedMedia,
)
from media_summarizer.core.media_ingestion.errors import OrchestrationError
from media_summarizer.core.media_ingestion.media_metadata import (
    normalize_cover_url,
    select_creator,
)
from media_summarizer.core.media_ingestion.ports import SubmissionOrchestratorPort
from media_summarizer.core.media_ingestion.title_derivation import derive_media_title
from media_summarizer.core.models import (
    JobStatus,
    MediaFailureCode,
    ProcessingJob,
    UserMediaStatus,
)
from media_summarizer.core.services import audio_quota_gate, quota_enforcer
from media_summarizer.core.services.durable_media_service import (
    finalize_deduplicated_save,
    save_media_for_user,
    user_holds_media,
)
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
DEFAULT_X_INGESTION_QUEUE = required_env("X_INGESTION_QUEUE")
DEFAULT_YOUTUBE_INGESTION_QUEUE = required_env("YOUTUBE_INGESTION_QUEUE")
DEFAULT_TIKTOK_INGESTION_QUEUE = required_env("TIKTOK_INGESTION_QUEUE")
DEFAULT_INSTAGRAM_INGESTION_QUEUE = required_env("INSTAGRAM_INGESTION_QUEUE")
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


class _ContentJob(NamedTuple):
    """What the ledger's job id resolved to, and whether the read even worked.

    The distinction matters: a job that is *absent* is a reservation nothing will
    ever complete, while a read that *failed* says nothing at all and must not be
    turned into a verdict on the content.
    """

    job: Optional[ProcessingJob]
    read_failed: bool


# How a live job's pipeline state reads to the user who just saved the same
# content. There is no lifecycle stage for "summarizing", and none is needed: the
# library collapses every in-flight stage into "processing" anyway.
_JOB_STATUS_TO_LIFECYCLE = {
    JobStatus.PENDING: ProcessingLifecycleStatus.PENDING,
    JobStatus.EXTRACTING: ProcessingLifecycleStatus.EXTRACTING,
    JobStatus.TRANSCRIBING: ProcessingLifecycleStatus.TRANSCRIBING,
    JobStatus.SUMMARIZING: ProcessingLifecycleStatus.TRANSCRIBING,
    JobStatus.COMPLETED: ProcessingLifecycleStatus.READY_FOR_ARTIFACTS,
    JobStatus.FAILED: ProcessingLifecycleStatus.FAILED,
    JobStatus.CANCELLED: ProcessingLifecycleStatus.CANCELLED,
}


async def _load_content_job(job_id: str, *, media_key: str) -> _ContentJob:
    """Read the job the content ledger points at. Never raises."""
    try:
        job = await database_async.get_processing_job_by_id(job_id)
    except Exception as exc:  # noqa: BLE001 - a dead read must not fail a save
        log_event(
            logger,
            logging.WARNING,
            "media.ingest.duplicate_job_unreadable",
            f"Could not read the content job behind a deduplicated save: {exc}",
            job_id=job_id,
            media_key=media_key,
            error_type=type(exc).__name__,
        )
        return _ContentJob(job=None, read_failed=True)
    return _ContentJob(job=job, read_failed=False)


async def _resolve_duplicate_status(
    *,
    media_key: str,
    ledger_status: Optional[str],
    content_job_id: str,
    content: _ContentJob,
) -> ProcessingLifecycleStatus:
    """What a save of already-known content is worth, from the ledger and the job.

    ``reserved`` used to map straight to ``pending``, which was only ever correct
    if ``reserved`` meant "in flight". Nothing closed the ledger before task-390,
    so it meant "was submitted once, at some point", and every re-save of a
    finished media was persisted as pending, waiting on a job that had completed
    days earlier. The job itself is the authority: when it has reached a terminal
    state the save resolves from that state, and the stranded ledger row is
    repaired on the way through so the next save reads the truth directly.
    """
    value = (ledger_status or "").lower().strip()
    if value == "processed":
        return ProcessingLifecycleStatus.READY_FOR_ARTIFACTS
    if value == "failed":
        return ProcessingLifecycleStatus.FAILED
    if value != "reserved":
        # The ledger has no other state. An absent/unknown value must not leave a
        # freshly saved row polling forever for work no code has scheduled.
        return ProcessingLifecycleStatus.COMPLETED

    if content.read_failed:
        # No information. Treating the reservation as in flight is the only
        # honest answer, and the worker mirror refreshes the row either way.
        return ProcessingLifecycleStatus.PENDING

    if content.job is None:
        # A reservation pointing at a job that no longer exists: its transcript is
        # unreachable (the pointer to it lived on that row) and no worker is going
        # to publish anything. Saying "pending" here is what parked saves forever.
        log_event(
            logger,
            logging.WARNING,
            "media.ingest.duplicate_ledger_orphaned",
            "Content ledger points at a job that no longer exists",
            job_id=content_job_id,
            media_key=media_key,
        )
        return ProcessingLifecycleStatus.FAILED

    mapped = _JOB_STATUS_TO_LIFECYCLE.get(
        content.job.status, ProcessingLifecycleStatus.PENDING
    )
    if mapped == ProcessingLifecycleStatus.READY_FOR_ARTIFACTS:
        await _reconcile_stranded_ledger(
            media_key=media_key, job_id=content_job_id, processed=True
        )
    elif mapped in (
        ProcessingLifecycleStatus.FAILED,
        ProcessingLifecycleStatus.CANCELLED,
    ):
        await _reconcile_stranded_ledger(
            media_key=media_key, job_id=content_job_id, processed=False
        )
    return mapped


async def _reconcile_stranded_ledger(
    *, media_key: str, job_id: str, processed: bool
) -> None:
    """Close a ledger row whose job is already terminal. Best effort.

    The completion path closes the ledger itself, so this only ever fires for
    rows stranded before that path existed, or by a completion event that was
    lost. Never fails the save: the outcome has already been resolved from the
    job, and a ledger left stale only means the next save resolves it the same
    way again.
    """
    try:
        if processed:
            await episode_idempotence.mark_processed(
                media_key=media_key, job_id=job_id
            )
        else:
            await episode_idempotence.mark_failed(media_key=media_key, job_id=job_id)
    except Exception as exc:  # noqa: BLE001 - a repair never fails a save
        log_event(
            logger,
            logging.WARNING,
            "media_idempotence.reconcile_failed",
            f"Could not reconcile a stranded content ledger row: {exc}",
            media_key=media_key,
            job_id=job_id,
            target_status="processed" if processed else "failed",
            error_type=type(exc).__name__,
        )


def _library_status_from_duplicate(
    status: ProcessingLifecycleStatus,
) -> UserMediaStatus:
    if status in (
        ProcessingLifecycleStatus.READY_FOR_ARTIFACTS,
        ProcessingLifecycleStatus.COMPLETED,
    ):
        return UserMediaStatus.READY
    if status in (
        ProcessingLifecycleStatus.FAILED,
        ProcessingLifecycleStatus.CANCELLED,
    ):
        return UserMediaStatus.FAILED
    if status == ProcessingLifecycleStatus.PENDING:
        return UserMediaStatus.PENDING
    return UserMediaStatus.PROCESSING


# Transcription providers that are paid by the minute. Only Deepgram is metered by
# length: native subtitles, Apify transcripts and shared text produce a transcript
# without spending a single minute of anyone's allowance.
_AUDIO_BILLED_TRANSCRIPTION_PROVIDERS = frozenset({"deepgram"})


def _audio_seconds_billed_by(job: Any) -> Optional[int]:
    """Seconds of audio the content's transcription established, or None.

    None means "this content was not metered in audio minutes" -- an article, a
    document, a video with native subtitles, or a job that never reached a
    terminal transcription. 0 means it was, but its length is unknown.

    Reads `audio_duration_seconds` and never `duration_seconds`: in the Deepgram
    metadata the latter is how long the API call took, not how long the audio is.
    """
    transcription = getattr(job, "transcription_metadata", None) or {}
    provider = str(transcription.get("provider") or "").strip().lower()
    if provider not in _AUDIO_BILLED_TRANSCRIPTION_PROVIDERS:
        return None

    extraction = getattr(job, "extraction_metadata", None) or {}
    for source in (transcription, extraction):
        try:
            seconds = int(float(source.get("audio_duration_seconds") or 0))
        except (TypeError, ValueError):
            continue
        if seconds > 0:
            return seconds
    return 0


async def _debit_deduplicated_audio_save(
    *,
    user_id: str,
    media_key: str,
    media_item_id: str,
    content_job: Optional[ProcessingJob],
) -> None:
    """Charge a user's *first* save of content somebody else already processed.

    The pipeline being skipped is not the same statement as the save being free.
    Global deduplication is a provider-cost optimisation shared by everybody; the
    minute allowance measures how much audio and video *this user* takes in, so
    their first copy of a media is charged like any other -- and every copy after
    that is free, because they already hold it (task-281). The alternative, giving
    a media away to everyone but whoever saved it first, is arbitrary from the
    user's seat and trivially gamed.

    Debited outside the gate on purpose: there is no provider spend left to
    refuse here, so refusing the save would cost the user their library entry to
    protect a bill nobody is about to pay. Going past the allowance is the
    settlement's existing overrun policy -- the counter stays true and the *next*
    real import is the one that gets refused.

    The idempotency token is the save's own library id, so a retried or
    redelivered submission charges it at most once, and two different saves of
    the same content by the same user never share a token.

    ``content_job`` is ``None`` when the job behind the content is gone or could
    not be read: there is then no duration to charge and nothing is debited. A
    quota read never fails a save.
    """
    if await user_holds_media(
        user_id=user_id,
        media_key=media_key,
        exclude_media_item_id=media_item_id,
    ):
        log_event(
            logger,
            logging.INFO,
            "quota.audio_gate_already_held",
            "User already holds this deduplicated media; the save is free",
            user_id=user_id,
            media_key=media_key,
            media_item_id=media_item_id,
        )
        return

    if content_job is None:
        log_event(
            logger,
            logging.WARNING,
            "quota.duplicate_debit_skipped",
            "No content job behind a deduplicated save; nothing to debit",
            user_id=user_id,
            media_key=media_key,
            media_item_id=media_item_id,
        )
        return

    audio_seconds = _audio_seconds_billed_by(content_job)
    if audio_seconds is None:
        # Nothing was transcribed for this content, so there is nothing to charge:
        # articles, documents, captioned videos and shared text are unlimited.
        return

    debited = await quota_enforcer.record_transcription_minutes(
        user_id=user_id,
        # 0 seconds means "transcribed, length unknown": one provisional minute,
        # like the gate does when a duration probe comes back empty.
        minutes=quota_enforcer.minutes_for_seconds(audio_seconds) or 1,
        idempotency_token=quota_enforcer.gate_token(media_item_id),
    )
    log_event(
        logger,
        logging.INFO,
        "quota.duplicate_first_save_debited",
        "First save of globally deduplicated audio content debited",
        user_id=user_id,
        media_key=media_key,
        media_item_id=media_item_id,
        content_job_id=content_job.id,
        audio_duration_seconds=audio_seconds,
        debited_minutes=debited,
    )


async def _build_duplicate_outcome(
    *,
    user_id: str,
    resolved: ResolvedMedia,
    existing: Dict[str, Any],
    durable_media_item_id: str,
) -> IngestionOutcome:
    """Outcome for a media_key someone (maybe another user) already processed.

    The ids returned here are the caller's own library ids, never the id of the
    job that happens to hold the global idempotence reservation. Handing back a
    foreign job id is the §1.6.1 defect: the requesting user would poll and open
    an item that does not belong to them, while their own library row stayed
    invisible. Deduplication is a *pipeline* optimisation; the library entry is
    per user (task-218 §4.3).

    The content job is read once here and handed to everything below, because
    three of them need it and it is the authority on what the reused content is:
    the quota debit reads its audio length, the status resolution reads its
    pipeline state, and the finalisation copies its title, creator and cover onto
    the new row before submitting the transcript for indexing.
    """
    existing_job_id = existing.get("job_id")
    if not existing_job_id:
        raise OrchestrationError(
            "Duplicate media_key detected but idempotence row has no job_id."
        )
    content_job_id = str(existing_job_id)
    content = await _load_content_job(content_job_id, media_key=resolved.media_key)
    mapped_status = await _resolve_duplicate_status(
        media_key=resolved.media_key,
        ledger_status=existing.get("status"),
        content_job_id=content_job_id,
        content=content,
    )
    await _debit_deduplicated_audio_save(
        user_id=user_id,
        media_key=resolved.media_key,
        media_item_id=durable_media_item_id,
        content_job=content.job,
    )
    owned_job_id = await finalize_deduplicated_save(
        user_id=user_id,
        media_item_id=durable_media_item_id,
        processing_status=_library_status_from_duplicate(mapped_status),
        content_job=content.job,
    )
    caller_media_item_id = durable_media_item_id
    return IngestionOutcome(
        media_item_id=caller_media_item_id,
        job_id=owned_job_id or caller_media_item_id,
        status=mapped_status,
        media_key=resolved.media_key,
        normalized_url=resolved.normalized_url,
        deduplicated=True,
        duplicate_of_media_item_id=caller_media_item_id,
        metadata={
            "idempotence_status": existing.get("status"),
            "resolved_status": mapped_status.value,
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
        x_ingestion_queue: Optional[str] = None,
        youtube_ingestion_queue: Optional[str] = None,
        tiktok_ingestion_queue: Optional[str] = None,
        instagram_ingestion_queue: Optional[str] = None,
    ) -> None:
        self._deepgram_transcription_queue = (
            deepgram_transcription_queue
            or DEFAULT_DEEPGRAM_TRANSCRIPTION_QUEUE
        )
        self._podcastindex_resolution_queue = (
            podcastindex_resolution_queue or DEFAULT_PODCASTINDEX_RESOLUTION_QUEUE
        )
        self._x_ingestion_queue = x_ingestion_queue or DEFAULT_X_INGESTION_QUEUE
        self._youtube_ingestion_queue = (
            youtube_ingestion_queue or DEFAULT_YOUTUBE_INGESTION_QUEUE
        )
        self._tiktok_ingestion_queue = (
            tiktok_ingestion_queue or DEFAULT_TIKTOK_INGESTION_QUEUE
        )
        self._instagram_ingestion_queue = (
            instagram_ingestion_queue or DEFAULT_INSTAGRAM_INGESTION_QUEUE
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
        - Creates the durable library row, carrying the requested folder_id.
          Organization lives there and nowhere else (task-220).
        - Allocates a minute hold for quota enforcement.
        - Routes to appropriate worker queues based on media family and type.
        - Handles direct transcription for shared text and Apify social video transcripts.
        - Manages idempotence via media_key deduplication.
        """
        # Single derivation point for the title stored at submission (task-266).
        # Resolvers put whatever their provider already knows in `resolved.title`;
        # here it is validated against the deterministic distrust rules and, when
        # nothing survives, replaced by a readable "<label> — <date>" fallback.
        # A worker that later learns the real title (YouTube, TikTok, article,
        # document) overwrites this value through the durable mirror.
        title = derive_media_title(
            [resolved.title],
            media_type=resolved.media_type.value,
            source_platform=resolved.source_platform.value,
            file_name_candidates=[
                resolved.metadata.get("original_name") if resolved.metadata else None
            ],
        )

        # The durable library entry is created FIRST (task-218 §4.3): everything
        # below it -- the idempotence reservation, the processing job, the queue
        # sends -- is operational state that may fail without the user losing what
        # they saved. Placing it before the duplicate short-circuit is deliberate:
        # a media_key already processed *globally* is still a brand-new library
        # entry for THIS user, and that is the case §1.6.1 got wrong by handing
        # the requesting user another user's job id.
        # A cover known at submission is hotlinked as-is: the sources whose URL
        # is signed and expiring resolve inside their worker, not here, and
        # re-host there (task-302 §5). Nothing on this path downloads an image,
        # so the share request stays as fast as it is today.
        cover_url = normalize_cover_url(resolved.cover_url)
        creator_name = select_creator([resolved.creator_name], title=title)

        durable_media_item_id = await save_media_for_user(
            user_id=command.user.user_id,
            media_key=resolved.media_key,
            title=title,
            creator_name=creator_name,
            thumbnail_url=cover_url,
            source_url=resolved.normalized_url,
            source_platform=resolved.source_platform.value,
            media_type=resolved.media_type.value,
            folder_id=command.request.folder_id,
        )

        existing = await episode_idempotence.already_processed(media_key=resolved.media_key)
        if existing and existing.get("job_id"):
            log_event(
                logger,
                logging.INFO,
                "media.ingest.duplicate_reused",
                "Existing media submission reused through idempotence",
                job_id=existing.get("job_id"),
                media_item_id=durable_media_item_id,
                resolver_key=resolved.resolver_key,
                media_type=resolved.media_type.value,
                source_platform=resolved.source_platform.value,
            )
            return await _build_duplicate_outcome(
                user_id=command.user.user_id,
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
            creator_name=creator_name,
            media_image=cover_url,
            source_platform=resolved.source_platform.value,
            media_type=resolved.media_type.value,
            # Pointer from the operational row to the durable one: how the status
            # mirror finds the library row, and how the workers know which
            # media_item_id to publish (task-220).
            media_item_id=durable_media_item_id,
        )

        canonical_media_item_id = durable_media_item_id

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
                    return await _build_duplicate_outcome(
                        user_id=command.user.user_id,
                        resolved=resolved,
                        existing=duplicate,
                        durable_media_item_id=durable_media_item_id,
                    )
                raise OrchestrationError(
                    f"Unable to reserve media key '{resolved.media_key}'."
                )

            await database_async.create_processing_job(job)
            job_created = True

            # No folder write on the job: the requested organization was already
            # persisted on the durable row above, which is now the only place it
            # lives (task-220). The job used to carry a second copy that every
            # read had to prefer or reconcile.

            pipeline_enqueued = False
            podcastindex_resolution_enqueued = False
            x_ingestion_enqueued = False
            youtube_ingestion_enqueued = False
            tiktok_ingestion_enqueued = False
            instagram_ingestion_enqueued = False
            outcome_status = ProcessingLifecycleStatus.PENDING
            if resolved.raw_text is not None and resolved.media_family == MediaFamily.SOCIAL_VIDEO:
                # Apify transcript bypass: store transcript directly, skip Deepgram.
                transcript_s3_key = f"{job.id}.txt"
                transcript_text = normalize_transcript_text(
                    resolved.raw_text,
                    source=resolved.source_platform.value,
                )
                duration_seconds = resolved.metadata.get("duration_seconds", 0)
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
                            "quota_debit_skipped": gate.debit_skipped,
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
                            "quota_debit_skipped": gate.debit_skipped,
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
            elif resolved.resolver_key == "article.default":
                # The article's text is already in hand: `ArticleResolver` read the
                # page before this submission existed, because its fingerprint is
                # part of `media_key` (task-392). There is nothing left to queue --
                # the transcript is stored here, in the request.
                outcome_status = await self._settle_article_submission(
                    job=job,
                    resolved=resolved,
                    media_item_id=canonical_media_item_id,
                )
                pipeline_enqueued = (
                    outcome_status == ProcessingLifecycleStatus.COMPLETED
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
            elif resolved.resolver_key == "instagram.default":
                # Queue-first Instagram resolution (task-274). The resolver needs
                # yt-dlp and, on an IP block, an Apify run measured at 63-100 s --
                # neither fits the API's non-negotiable 30 s ceiling, so the
                # request only persists the job and hands the URL to the worker.
                job.mark_extracting()
                await database_async.update_processing_job(job)
                await sqs.send_message(
                    queue_name=self._instagram_ingestion_queue,
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
                instagram_ingestion_enqueued = True
                log_event(
                    logger,
                    logging.INFO,
                    "worker.enqueued",
                    "Instagram ingestion enqueued",
                    job_id=job.id,
                    media_item_id=canonical_media_item_id,
                    queue=self._instagram_ingestion_queue,
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
                    if tiktok_ingestion_enqueued or instagram_ingestion_enqueued
                    else ProcessingLifecycleStatus.PENDING
                ),
                media_key=resolved.media_key,
                normalized_url=resolved.normalized_url,
                deduplicated=False,
                metadata={
                    "resolver_key": resolved.resolver_key,
                    "pipeline_enqueued": pipeline_enqueued,
                    "podcastindex_resolution_enqueued": podcastindex_resolution_enqueued,
                    "x_ingestion_enqueued": x_ingestion_enqueued,
                    "youtube_ingestion_enqueued": youtube_ingestion_enqueued,
                    "tiktok_ingestion_enqueued": tiktok_ingestion_enqueued,
                    "instagram_ingestion_enqueued": instagram_ingestion_enqueued,
                    "media_family": resolved.media_family.value,
                    "media_type": resolved.media_type.value,
                    "source_platform": resolved.source_platform.value,
                },
            )

        except Exception as exc:
            if job_created:
                try:
                    job.mark_failed(
                        error_code=MediaFailureCode.SUBMISSION_FAILED,
                        error_step="ingestion_core",
                        error_metadata={
                            "reason": "ingestion_core_submission_failed",
                            "exception_type": type(exc).__name__,
                        },
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

    async def _settle_article_submission(
        self,
        *,
        job: ProcessingJob,
        resolved: ResolvedMedia,
        media_item_id: str,
    ) -> ProcessingLifecycleStatus:
        """Close out a web-article submission in the request that made it.

        `ArticleResolver` already read the page -- it had to, because the text's
        fingerprint is half of `media_key` (task-392) -- so there is nothing left
        for a queue to do: either the text is here and this stores it, or the page
        could not be read and this records why.

        The failed branch is where the reservation matters. A page that answered a
        503 or timed out must not leave `media_idempotence` holding a terminal
        `failed` row: the URL-derived key is the only identity a failure has, and a
        `failed` row under it would answer every later save of that URL with the
        same failure without ever re-reading the page. So a transient cause
        *releases* the reservation and a verdict on the page itself keeps it.
        """
        if resolved.raw_text is None:
            return await self._fail_unreadable_article(
                job=job,
                resolved=resolved,
                media_item_id=media_item_id,
            )

        transcript_s3_key = f"{job.id}.txt"
        # No re-normalization: `resolved.raw_text` is the exact string that was
        # fingerprinted into `media_key`, and the stored transcript has to be the
        # same bytes or the identity would describe something nobody can read.
        transcript_text = resolved.raw_text
        extraction_metadata: Dict[str, Any] = dict(
            resolved.metadata.get("extraction_metadata") or {}
        )
        source_url = (
            extraction_metadata.get("final_url")
            or extraction_metadata.get("requested_url")
            or resolved.normalized_url
        )
        transcription_metadata: Dict[str, Any] = {
            "provider": resolved.metadata.get("transcript_provider")
            or "article_extractor",
            "model_used": resolved.metadata.get("transcript_extractor")
            or "trafilatura",
            "language": extraction_metadata.get("language"),
            # Paragraph count, comparable across sources (task-231 §13.1).
            "segments_count": extraction_metadata.get("paragraph_count")
            or count_paragraphs(transcript_text),
            "duration_seconds": 0,
            "source_url": source_url,
            "transcribed_at": extraction_metadata.get("fetched_at") or _now_iso(),
        }

        await s3.upload_file_object(
            bucket=DEFAULT_TRANSCRIPT_BUCKET,
            key=transcript_s3_key,
            file_obj=BytesIO(transcript_text.encode("utf-8")),
            content_type="text/plain",
            metadata={
                "content-type": "text/plain",
                "job-type": "article-transcription",
                "provider": "article-extractor",
            },
        )
        job.set_transcription_location(transcript_s3_key)
        job.set_transcription_metadata(transcription_metadata)
        if extraction_metadata:
            job.extraction_metadata = extraction_metadata
        job.mark_completed()
        await database_async.update_processing_job(job)
        await sqs.send_message(
            queue_name=DEFAULT_EPISODE_COMPLETED_EVENTS_QUEUE,
            message_body={
                "event_type": "episode_completion_status",
                "status": "success",
                "media_key": resolved.media_key,
                "canonical_job_id": job.id,
                "transcription_s3_key": transcript_s3_key,
                "transcription_metadata": transcription_metadata,
            },
        )
        log_event(
            logger,
            logging.INFO,
            "transcription.completed",
            "Article transcript stored inline at submission",
            job_id=job.id,
            media_item_id=media_item_id,
            resolver_key=resolved.resolver_key,
            source_platform=resolved.source_platform.value,
            transcript_source="article_extractor",
            content_fingerprint=resolved.metadata.get("content_fingerprint"),
        )
        return ProcessingLifecycleStatus.COMPLETED

    async def _fail_unreadable_article(
        self,
        *,
        job: ProcessingJob,
        resolved: ResolvedMedia,
        media_item_id: str,
    ) -> ProcessingLifecycleStatus:
        """Record a page whose text could not be read, with the code the app renders."""
        failure_code = MediaFailureCode.UNEXPECTED_ERROR
        raw_failure_code = resolved.metadata.get("article_failure_code")
        if isinstance(raw_failure_code, str):
            try:
                failure_code = MediaFailureCode(raw_failure_code)
            except ValueError:
                failure_code = MediaFailureCode.UNEXPECTED_ERROR
        retryable = bool(resolved.metadata.get("article_fetch_retryable"))
        error_metadata: Dict[str, Any] = dict(
            resolved.metadata.get("article_fetch_error_metadata") or {}
        )

        job.mark_failed(
            error_code=failure_code,
            error_step="article_extraction",
            error_metadata=error_metadata,
        )
        # Mirrors the durable library row to FAILED, which is what turns the
        # spinner into the localized failed tile the reader already knows.
        await database_async.update_processing_job(job)

        if retryable:
            # Deletes the row while it is still `reserved`, so the next save of
            # this URL reads the page again instead of inheriting this outage.
            await episode_idempotence.release_reservation(
                media_key=resolved.media_key,
                job_id=job.id,
            )
        else:
            await sqs.send_message(
                queue_name=DEFAULT_EPISODE_COMPLETED_EVENTS_QUEUE,
                message_body={
                    "event_type": "episode_completion_status",
                    "status": "failure",
                    "media_key": resolved.media_key,
                    "canonical_job_id": job.id,
                    "reason": failure_code.value,
                },
            )

        log_event(
            logger,
            logging.ERROR,
            "transcription.failed",
            "Article could not be read at submission",
            job_id=job.id,
            media_item_id=media_item_id,
            resolver_key=resolved.resolver_key,
            source_platform=resolved.source_platform.value,
            transcript_source="article_extractor",
            error_code=failure_code.value,
            detail=resolved.metadata.get("article_fetch_error_code"),
            retryable=retryable,
        )
        return ProcessingLifecycleStatus.FAILED
