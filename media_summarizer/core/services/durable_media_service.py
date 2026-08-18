"""
Durable library persistence — the use-case layer of task-240/220.

Every user save goes through :func:`save_media_for_user`, which creates or reuses
exactly one ``user_media`` row. This is the write half of Option A
(``docs/research/task-218-durable-media-library-persistence/README.md`` §4.3).

Since task-220 (Phase 3) the API *reads* this table too, which changed the
failure contract of the save path: a save whose durable row is missing is a save
the user cannot see, so it now fails the request instead of being swallowed. The
Phase-1 ``try_save_media_for_user`` wrapper that absorbed those failures is gone.

Failure policy, straight from §6.5 and from the incident that motivated the whole
benchmark:

- The **save path** (:func:`save_media_for_user`) logs ``durable_media.write_failed``
  at ERROR and re-raises. That event is alarmed
  (``infrastructure/terraform/modules/platform/durable_media_alerts.tf``). A
  durable write that fails silently is precisely how a library loses rows for two
  months without anyone noticing, so it is never swallowed here.
- The **mirror path** (:func:`mirror_job`) logs the same alarmed event but does
  not raise. It only refreshes a denormalised snapshot; failing the pipeline over
  a status hint would trade a cosmetic staleness for a real processing failure.
  The caller decides which contract applies.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from media_summarizer.core.models.processing_job import JobStatus, ProcessingJob
from media_summarizer.core.models.user_media import (
    UserMediaRecord,
    UserMediaStatus,
    new_media_item_id,
)
from media_summarizer.core.services.folder_service import ensure_default_folder
from media_summarizer.utils import user_media as user_media_store
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

# The single alarmed event name. Both the API save path and the worker mirror
# emit it, and durable_media_alerts.tf filters it on every log group, so a
# failure is visible wherever it happens.
EVENT_WRITE_FAILED = "durable_media.write_failed"
EVENT_CREATED = "durable_media.created"
EVENT_SKIPPED = "durable_media.skipped"


class DurableMediaWriteError(RuntimeError):
    """The durable library row could not be written."""


# Pipeline status -> library status. Deliberately lossy: the three in-flight
# pipeline stages collapse into one "processing", because the library only needs
# to know whether the entry is usable. The fine-grained stages stay in the
# expirable processing_jobs row, which is the only place they belong.
_JOB_STATUS_TO_LIBRARY_STATUS = {
    JobStatus.PENDING: UserMediaStatus.PENDING,
    JobStatus.EXTRACTING: UserMediaStatus.PROCESSING,
    JobStatus.TRANSCRIBING: UserMediaStatus.PROCESSING,
    JobStatus.SUMMARIZING: UserMediaStatus.PROCESSING,
    JobStatus.COMPLETED: UserMediaStatus.READY,
    JobStatus.FAILED: UserMediaStatus.FAILED,
    # A cancelled job will never produce artifacts, so from the library's point of
    # view the entry is as unusable as a failed one. The reason why lives in the
    # job row for as long as it exists.
    JobStatus.CANCELLED: UserMediaStatus.FAILED,
}


def map_job_status(status: Optional[JobStatus]) -> Optional[UserMediaStatus]:
    """Project a pipeline status onto the library status, or None if unknown.

    Returning None rather than guessing keeps ``processing_status`` honest: an
    unmapped pipeline state is *no information*, and AC #7 requires the attribute
    to be genuinely nullable.
    """
    if status is None:
        return None
    return _JOB_STATUS_TO_LIBRARY_STATUS.get(status)


async def _resolve_folder_id(user_id: str, folder_id: Optional[str]) -> Optional[str]:
    """Fall back to the user's default folder so a row is always navigable.

    Best-effort: if the folder lookup fails, the row is still saved without a
    folder rather than the save being lost. An unfiled item is a small annoyance;
    a dropped save is the bug this table exists to prevent.
    """
    if folder_id:
        return folder_id
    try:
        default_folder = await ensure_default_folder(user_id)
        return default_folder.id
    except Exception as exc:  # noqa: BLE001 - never fail a save over a folder
        logger.warning(
            "Could not resolve default folder for user %s: %s", user_id, exc
        )
        return None


async def save_media_for_user(
    *,
    user_id: str,
    media_key: str,
    title: Optional[str] = None,
    source_url: Optional[str] = None,
    source_platform: Optional[str] = None,
    media_type: Optional[str] = None,
    duration_seconds: Optional[int] = None,
    thumbnail_url: Optional[str] = None,
    language: Optional[str] = None,
    folder_id: Optional[str] = None,
    tag_ids: Optional[List[str]] = None,
    job_id: Optional[str] = None,
    processing_status: Optional[UserMediaStatus] = UserMediaStatus.PENDING,
) -> str:
    """Persist the durable library row for a save. Returns its ``media_item_id``.

    Every call represents a distinct user save and therefore creates a fresh
    opaque id. Pipeline idempotence remains separate and keyed by ``media_key``.

    Raises:
        DurableMediaWriteError: the row could not be written. Callers on the save
            path must decide whether to fail the request; the failure is already
            logged and alarmed by the time this is raised.
    """
    if not (user_id or "").strip() or not (media_key or "").strip():
        exc = ValueError("user_id and media_key are required to save media")
        log_event(
            logger,
            logging.ERROR,
            EVENT_WRITE_FAILED,
            f"Cannot create a durable media row: {exc}",
            user_id=user_id,
            media_key=media_key,
            job_id=job_id,
            reason="invalid_identity",
        )
        raise DurableMediaWriteError(str(exc))

    media_item_id = new_media_item_id()

    resolved_folder_id = await _resolve_folder_id(user_id, folder_id)
    now = datetime.now(timezone.utc)
    record = UserMediaRecord(
        user_id=user_id,
        media_item_id=media_item_id,
        media_key=media_key,
        title=title,
        source_url=source_url,
        source_platform=source_platform,
        media_type=media_type,
        duration_seconds=duration_seconds,
        thumbnail_url=thumbnail_url,
        language=language,
        folder_id=resolved_folder_id,
        tag_ids=list(tag_ids or []),
        saved_at=now,
        updated_at=now,
        processing_status=processing_status,
        last_job_id=job_id,
    )

    try:
        stored = await user_media_store.create(record)
    except Exception as exc:  # noqa: BLE001 - every failure mode must be alarmed
        log_event(
            logger,
            logging.ERROR,
            EVENT_WRITE_FAILED,
            f"Durable user_media write failed: {exc}",
            user_id=user_id,
            media_key=media_key,
            media_item_id=media_item_id,
            job_id=job_id,
            error_type=type(exc).__name__,
            exc_info=True,
        )
        raise DurableMediaWriteError(
            f"Durable user_media write failed for {media_item_id}"
        ) from exc

    log_event(
        logger,
        logging.INFO,
        EVENT_CREATED,
        "Durable user_media save created",
        user_id=user_id,
        media_item_id=media_item_id,
        media_key=media_key,
        job_id=job_id,
        folder_id=resolved_folder_id,
    )
    return stored.media_item_id


async def user_holds_media(
    *,
    user_id: str,
    media_key: str,
    exclude_media_item_id: Optional[str] = None,
) -> bool:
    """Does this user already have this content in their library?

    The question the audio quota asks before debiting (task-281). It is *not* the
    question the global idempotence ledger answers: that one says whether the
    pipeline still has work to do, for everybody at once, while this one is
    scoped to a single owner and ignores processing entirely. A media the user
    already holds costs them nothing to file again, whether or not a job runs.

    Scoped to the user and to nothing else: every folder, every collection and
    every processing status counts as held, because the rule is about owning the
    content, not about where it was filed. Soft-deleted rows do not count -- a
    user who deleted an item no longer holds it, so re-saving it debits again.

    ``exclude_media_item_id`` is the save currently being made. The durable row
    is written before the quota gate runs (task-218 §4.3), so without excluding
    it every save would find itself and never debit anything. The underlying read
    is strongly consistent, so the row a save wrote a moment earlier is visible
    to the save that follows it.

    Fails *open* (returns False, so the caller debits): the lookup hits the table
    the save path just wrote to successfully, so an error here is close to
    impossible, and the failure mode that must not exist is a quota anyone can
    open by making a read fail.
    """
    media_key = (media_key or "").strip()
    if not (user_id or "").strip() or not media_key:
        return False

    try:
        records = await user_media_store.list_for_user_by_media_key(user_id, media_key)
    except Exception as exc:  # noqa: BLE001 - never fail a save over a quota read
        log_event(
            logger,
            logging.WARNING,
            "durable_media.holds_lookup_failed",
            f"Could not establish whether the user already holds the media: {exc}",
            user_id=user_id,
            media_key=media_key,
            error_type=type(exc).__name__,
        )
        return False

    return any(
        record.media_item_id != exclude_media_item_id for record in records
    )


async def finalize_deduplicated_save(
    *,
    user_id: str,
    media_item_id: str,
    processing_status: UserMediaStatus,
    existing_job_id: str,
) -> Optional[str]:
    """Persist the outcome of a save for content already in the global ledger.

    A duplicate does not run a job for the newly created library row, so the
    normal worker mirror will never update it. This write is therefore part of
    the save path and is strict, unlike :func:`mirror_attributes`: returning a
    successful response while the row still says ``pending`` would leave the
    client polling work that will never happen.

    The global idempotence job can belong to another user. Its id is returned
    only when ownership can be proved from the operational row; a foreign or
    expired job still lets the terminal status be persisted, but never becomes
    a pointer on the caller's library row.
    """
    from media_summarizer.utils import database_async

    owned_job_id: Optional[str] = None
    try:
        existing_job = await database_async.get_processing_job_by_id(existing_job_id)
    except Exception as exc:  # noqa: BLE001 - expiry must not break deduplication
        logger.warning(
            "Could not resolve duplicate job %s while finalizing %s: %s",
            existing_job_id,
            media_item_id,
            exc,
        )
    else:
        if existing_job is not None and existing_job.user_id == user_id:
            owned_job_id = existing_job.id

    attributes: Dict[str, Any] = {"processing_status": processing_status}
    if owned_job_id:
        attributes["last_job_id"] = owned_job_id

    try:
        updated = await user_media_store.update_attributes(
            user_id=user_id,
            media_item_id=media_item_id,
            attributes=attributes,
        )
    except Exception as exc:  # noqa: BLE001 - save-path failures are alarmed
        log_event(
            logger,
            logging.ERROR,
            EVENT_WRITE_FAILED,
            f"Durable duplicate finalization failed: {exc}",
            user_id=user_id,
            media_item_id=media_item_id,
            error_type=type(exc).__name__,
            exc_info=True,
        )
        raise DurableMediaWriteError(
            f"Durable duplicate finalization failed for {media_item_id}"
        ) from exc

    if not updated:
        log_event(
            logger,
            logging.ERROR,
            EVENT_WRITE_FAILED,
            "Durable row disappeared before duplicate finalization",
            user_id=user_id,
            media_item_id=media_item_id,
            reason="missing_row",
        )
        raise DurableMediaWriteError(
            f"Durable row missing during duplicate finalization for {media_item_id}"
        )

    return owned_job_id


async def resolve_job_for_record(
    record: UserMediaRecord,
) -> Optional[ProcessingJob]:
    """Find the global content job behind a library row, if it still exists.

    Reserved for the few callers that genuinely need *pipeline* data the library
    row does not carry — today only the transcript location (raw content,
    artifact generation, digests). Library reads must never call this: that is
    invariant I3, and the whole point of task-220 is that a missing job is a
    non-event for the library.

    The authoritative pointer is the global ``media_idempotence`` row keyed by
    ``record.media_key``. The content job may belong to another user: ownership
    was already established by loading this caller-owned library row, and global
    pipeline deduplication deliberately makes every save of the content read the
    same transcript. ``last_job_id`` remains only for direct document/audio
    uploads that do not enter the global ledger, and is ownership-checked.
    """
    if record is None:
        return None

    from media_summarizer.utils import database_async, media_idempotence

    content_job_id: Optional[str] = None
    try:
        ledger = await media_idempotence.already_processed(record.media_key)
        if ledger and ledger.get("job_id"):
            content_job_id = str(ledger["job_id"])
    except Exception as exc:  # noqa: BLE001 - direct uploads can lack a ledger
        logger.warning("Could not load content ledger for %s: %s", record.media_key, exc)

    if content_job_id:
        try:
            job = await database_async.get_processing_job_by_id(content_job_id)
        except Exception as exc:  # noqa: BLE001 - a dead job is not an error here
            logger.warning("Could not load content job %s: %s", content_job_id, exc)
        else:
            if job is not None:
                return job

    if record.last_job_id and record.last_job_id != content_job_id:
        try:
            job = await database_async.get_processing_job_by_id(record.last_job_id)
        except Exception as exc:  # noqa: BLE001 - a dead job is not an error here
            logger.warning("Could not load direct job %s: %s", record.last_job_id, exc)
        else:
            if job is not None and job.user_id == record.user_id:
                return job
    return None


async def mirror_attributes(
    *,
    user_id: str,
    media_item_id: str,
    attributes: Dict[str, Any],
) -> bool:
    """Best-effort refresh of denormalised attributes on an existing row.

    Never raises: a stale snapshot is a display detail, and the pipeline must not
    fail because a hint could not be refreshed. Failures still emit the alarmed
    event so "best-effort" does not mean "invisible".
    """
    if not media_item_id or not attributes:
        return False

    try:
        return await user_media_store.update_attributes(
            user_id=user_id,
            media_item_id=media_item_id,
            attributes=attributes,
        )
    except Exception as exc:  # noqa: BLE001 - best-effort by contract
        log_event(
            logger,
            logging.ERROR,
            EVENT_WRITE_FAILED,
            f"Durable user_media attribute mirror failed: {exc}",
            user_id=user_id,
            media_item_id=media_item_id,
            attributes=sorted(attributes.keys()),
            error_type=type(exc).__name__,
            exc_info=True,
        )
        return False


async def mirror_job(job: ProcessingJob) -> bool:
    """Push a content job's state onto every save that shares its media key.

    Without this, ``processing_status`` would freeze at ``pending`` forever and
    metadata the pipeline discovers late (a YouTube title, an audio duration)
    would never reach the durable record — hollowing out AC #5 while technically
    satisfying it at creation time.

    The job id is copied only to rows owned by the job's user. Other users still
    receive the content status and metadata, while resolving the transcript via
    ``media_key``; this keeps the global processing identity from becoming a
    cross-account pointer on their rows.
    """
    if not job or not job.user_id:
        return False

    attributes: Dict[str, Any] = {}

    library_status = map_job_status(job.status)
    if library_status is not None:
        attributes["processing_status"] = library_status

    # Metadata the pipeline resolves after the save (a YouTube title, the real
    # media type, the artwork). Only non-empty values are mirrored, so a worker
    # that does not know a field cannot blank out what another worker resolved.
    for source_attr, target_attr in (
        ("title", "title"),
        ("source_url", "source_url"),
        ("source_platform", "source_platform"),
        ("media_type", "media_type"),
        ("media_image", "thumbnail_url"),
    ):
        value = getattr(job, source_attr, None)
        if value:
            attributes[target_attr] = value

    # The media's own length, not any of the job's *processing* durations. The
    # extraction workers publish it under this key; job.total_duration is how long
    # the pipeline took and must never end up here.
    metadata = job.extraction_metadata or {}
    raw_duration = metadata.get("audio_duration_seconds")
    if raw_duration:
        try:
            attributes["duration_seconds"] = int(raw_duration)
        except (TypeError, ValueError):
            pass

    updated = False
    seen: set[tuple[str, str]] = set()

    # Update the initiating save first. This remains reliable during rollout
    # even before the new GSI has finished backfilling.
    if job.media_item_id:
        direct_attributes = {**attributes, "last_job_id": job.id}
        updated = await mirror_attributes(
            user_id=job.user_id,
            media_item_id=job.media_item_id,
            attributes=direct_attributes,
        )
        seen.add((job.user_id, job.media_item_id))

    if not job.media_key:
        return updated

    try:
        records = await user_media_store.list_by_media_key(job.media_key)
    except Exception as exc:  # noqa: BLE001 - direct mirror already succeeded
        logger.warning("Could not fan out media_key %s: %s", job.media_key, exc)
        return updated

    for record in records:
        target = (record.user_id, record.media_item_id)
        if target in seen:
            continue
        target_attributes = dict(attributes)
        if record.user_id == job.user_id:
            target_attributes["last_job_id"] = job.id
        refreshed = await mirror_attributes(
            user_id=record.user_id,
            media_item_id=record.media_item_id,
            attributes=target_attributes,
        )
        updated = refreshed or updated
        seen.add(target)

    return updated
