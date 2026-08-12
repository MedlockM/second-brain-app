"""
Durable library persistence — the use-case layer of task-240 (Phase 1).

Every user save goes through :func:`save_media_for_user`, which creates or reuses
exactly one ``user_media`` row. This is the write half of Option A
(``docs/research/task-218-durable-media-library-persistence/README.md`` §4.3).

Reads still resolve through ``processing_jobs`` in Phase 1: switching them is
task-220. Until then this table is written but not read by the API, which is what
makes the phase safe to roll back — flip ``DURABLE_MEDIA_ENABLED`` off and the
orphan rows left behind are inert.

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
    build_media_item_id,
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
EVENT_REUSED = "durable_media.reused"
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
) -> Optional[str]:
    """Persist the durable library row for a save. Returns its ``media_item_id``.

    Idempotent by construction: the id is derived from ``(user_id, media_key)``
    and the write is conditional, so re-saving the same content converges on the
    same single row instead of creating a duplicate.

    Returns None when the feature flag is off, which lets every call site stay a
    plain unconditional call.

    Raises:
        DurableMediaWriteError: the row could not be written. Callers on the save
            path must decide whether to fail the request; the failure is already
            logged and alarmed by the time this is raised.
    """
    if not user_media_store.durable_media_enabled():
        return None

    try:
        media_item_id = build_media_item_id(user_id, media_key)
    except ValueError as exc:
        log_event(
            logger,
            logging.ERROR,
            EVENT_WRITE_FAILED,
            f"Cannot derive a durable media_item_id: {exc}",
            user_id=user_id,
            media_key=media_key,
            job_id=job_id,
            reason="invalid_identity",
        )
        raise DurableMediaWriteError(str(exc)) from exc

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
        stored, created = await user_media_store.create_if_absent(record)
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

    if created:
        log_event(
            logger,
            logging.INFO,
            EVENT_CREATED,
            "Durable user_media row created",
            user_id=user_id,
            media_item_id=media_item_id,
            media_key=media_key,
            job_id=job_id,
            folder_id=resolved_folder_id,
        )
        return stored.media_item_id

    # Row already existed: a re-save, or the loser of a concurrent race. Refresh
    # the operational pointer only. The user's folder and tags are deliberately
    # left alone -- the stored row may carry a later organization than this call.
    log_event(
        logger,
        logging.INFO,
        EVENT_REUSED,
        "Durable user_media row already existed, reused",
        user_id=user_id,
        media_item_id=media_item_id,
        media_key=media_key,
        job_id=job_id,
    )
    if job_id:
        await mirror_attributes(
            user_id=user_id,
            media_item_id=media_item_id,
            attributes={"last_job_id": job_id},
        )
    return stored.media_item_id


async def try_save_media_for_user(**kwargs: Any) -> Optional[str]:
    """Phase-1 call-site wrapper: never fails the user's save.

    ``save_media_for_user`` raises, and in the end state (once task-220 makes
    ``user_media`` the read path) that is exactly right: a save whose library row
    is missing is a save that did not happen, and the request must fail.

    In Phase 1 reads still resolve through ``processing_jobs``, so a row that
    fails to land costs the user nothing today. Failing the whole ingestion over
    a table nothing reads yet would trade a real, user-visible regression for a
    bookkeeping one. The failure is already logged at ERROR and alarmed by the
    time it gets here — it is reported, not silenced — and task-241's backfill
    reconciles any row that was missed.

    TASK-220: when reads flip to ``user_media``, delete this wrapper and call
    ``save_media_for_user`` directly at every call site. Leaving it in place
    afterwards would let a user believe an item is in their library when it is
    not.
    """
    try:
        return await save_media_for_user(**kwargs)
    except DurableMediaWriteError:
        # Already logged as durable_media.write_failed (ERROR + alarm).
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
    if not user_media_store.durable_media_enabled():
        return False
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
    """Push a job's current status and resolved metadata onto its library row.

    Without this, ``processing_status`` would freeze at ``pending`` forever and
    metadata the pipeline discovers late (a YouTube title, an audio duration)
    would never reach the durable record — hollowing out AC #5 while technically
    satisfying it at creation time.

    No-op unless ``job.media_item_id`` points at a durable row, so a job created
    while the flag was off is never mirrored onto a row that does not exist.
    """
    if not user_media_store.durable_media_enabled():
        return False
    if not job or not job.media_item_id or not job.user_id:
        return False

    attributes: Dict[str, Any] = {"last_job_id": job.id}

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

    return await mirror_attributes(
        user_id=job.user_id,
        media_item_id=job.media_item_id,
        attributes=attributes,
    )
