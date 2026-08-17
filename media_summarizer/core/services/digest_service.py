"""
Digest service: assembles daily/weekly digests and triggers summary_short pre-generation.

Key design decisions:
- Summary Short artifacts are pre-generated in a staggered manner (not burst)
- Existing summary_short artifacts are reused via the artifact idempotence system
- Digests are assembled from the user's media items added in the target period
- No email is sent; everything is in-app
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import List, Optional, Tuple

from media_summarizer.core.models.digest import (
    DigestMediaItem,
    DigestRecord,
    DigestStatus,
    DigestType,
    UserDigestSettings,
)
from media_summarizer.core.models.media_artifact import (
    ArtifactScope,
    MediaArtifactStatus,
    MediaArtifactType,
    build_scope_key,
)
from media_summarizer.core.services.durable_media_service import resolve_job_for_record
from media_summarizer.utils import database_async, digest_db, media_artifacts
from media_summarizer.utils import user_media as user_media_store

logger = logging.getLogger(__name__)


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _current_week_key(d: Optional[date] = None) -> str:
    """Return ISO week key like '2026-W18'."""
    target = d or _today_utc()
    iso_year, iso_week, _ = target.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _daily_period_key(d: Optional[date] = None) -> str:
    """Return daily period key like '2026-04-29'."""
    target = d or _today_utc()
    return target.isoformat()


def _week_date_range(week_key: str) -> Tuple[date, date]:
    """Convert a week key like '2026-W18' to (monday, sunday) date range."""
    year_str, week_str = week_key.split("-W")
    year = int(year_str)
    week = int(week_str)
    # ISO week: Monday is day 1
    monday = date.fromisocalendar(year, week, 1)
    sunday = date.fromisocalendar(year, week, 7)
    return monday, sunday


async def _get_media_items_for_period(
    user_id: str, start_date: date, end_date: date
) -> List[DigestMediaItem]:
    """
    Retrieve library items saved by the user in the given date range.

    Reads the durable ``user_media`` library and keys the digest on
    ``media_item_id`` (task-220). That id is the same one the artifact table uses,
    so ``_check_summary_short_status`` and the mobile deep link both resolve. The
    job is still consulted, but only to answer "is there a transcript to summarize":
    an item whose job has expired cannot produce a new summary_short and therefore
    has no place in a digest that exists to serve one.
    """
    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(
        end_date, datetime.max.time().replace(microsecond=0), tzinfo=timezone.utc
    )

    media_items: List[DigestMediaItem] = []
    for record in await user_media_store.list_library_for_user(user_id):
        if not (start_dt <= record.saved_at <= end_dt):
            continue
        job = await resolve_job_for_record(record)
        if job is None or not getattr(job, "transcription_s3_key", None):
            continue

        media_items.append(
            DigestMediaItem(
                media_item_id=record.media_item_id,
                title=record.title,
                media_type=record.media_type,
                source_platform=record.source_platform,
                added_at=record.saved_at.isoformat(),
            )
        )

    return media_items


async def _check_summary_short_status(
    user_id: str, media_item_id: str
) -> Tuple[str, Optional[str]]:
    """
    Check whether the digest's summary_short for this media item is available.
    Returns (status, artifact_id) where status is 'ready', 'pending', or 'none'.

    Reads the scope history newest-first and takes the first summary_short it
    finds, which is the latest one. The digest is a snapshot of a day, so "the
    most recent short summary" is the right answer even though several may exist
    now that the model is append-only (task-270).
    """
    records, _ = await media_artifacts.list_artifacts_by_scope(
        scope_key=build_scope_key(
            user_id=user_id,
            scope=ArtifactScope.MEDIA,
            scope_id=media_item_id,
        )
    )
    for record in records:
        if record.artifact_type == MediaArtifactType.SUMMARY_SHORT:
            if record.status == MediaArtifactStatus.READY:
                return "ready", record.artifact_id
            if record.status in (
                MediaArtifactStatus.QUEUED,
                MediaArtifactStatus.GENERATING,
            ):
                return "pending", record.artifact_id
    return "none", None


async def get_or_assemble_daily_digest(
    user_id: str, target_date: Optional[date] = None
) -> DigestRecord:
    """
    Get or assemble the daily digest for a user.
    If the digest already exists, return it (with updated summary_short statuses).
    If not, create it from the user's media items for the day.
    """
    target = target_date or _today_utc()
    period_key = _daily_period_key(target)

    # Check if digest already exists
    existing = await digest_db.get_digest(user_id, DigestType.DAILY, period_key)
    if existing:
        # Refresh summary_short statuses if digest is not yet ready
        if existing.status != DigestStatus.PUBLISHED:
            existing = await _refresh_digest_statuses(existing)
        return existing

    # Assemble new digest
    media_items = await _get_media_items_for_period(user_id, target, target)

    # Check summary_short status for each item
    for item in media_items:
        status, artifact_id = await _check_summary_short_status(
            user_id, item.media_item_id
        )
        item.summary_short_status = status
        item.summary_short_artifact_id = artifact_id

    # Determine overall status
    all_ready = all(mi.summary_short_status == "ready" for mi in media_items)
    digest_status = DigestStatus.READY if (all_ready or not media_items) else DigestStatus.PENDING

    record = DigestRecord(
        user_id=user_id,
        digest_type=DigestType.DAILY,
        period_key=period_key,
        media_items=media_items,
        status=digest_status,
    )
    await digest_db.save_digest(record)
    return record


async def get_or_assemble_weekly_digest(
    user_id: str, week_key: Optional[str] = None
) -> DigestRecord:
    """
    Get or assemble the weekly digest for a user.
    If the digest already exists, return it (with updated summary_short statuses).
    If not, create it from the user's media items for the week.
    """
    target_week = week_key or _current_week_key()
    period_key = target_week

    # Check if digest already exists
    existing = await digest_db.get_digest(user_id, DigestType.WEEKLY, period_key)
    if existing:
        if existing.status != DigestStatus.PUBLISHED:
            existing = await _refresh_digest_statuses(existing)
        return existing

    # Assemble new digest
    monday, sunday = _week_date_range(target_week)
    media_items = await _get_media_items_for_period(user_id, monday, sunday)

    # Check summary_short status for each item
    for item in media_items:
        status, artifact_id = await _check_summary_short_status(
            user_id, item.media_item_id
        )
        item.summary_short_status = status
        item.summary_short_artifact_id = artifact_id

    # Determine overall status
    all_ready = all(mi.summary_short_status == "ready" for mi in media_items)
    digest_status = DigestStatus.READY if (all_ready or not media_items) else DigestStatus.PENDING

    record = DigestRecord(
        user_id=user_id,
        digest_type=DigestType.WEEKLY,
        period_key=period_key,
        media_items=media_items,
        status=digest_status,
    )
    await digest_db.save_digest(record)
    return record


async def _refresh_digest_statuses(record: DigestRecord) -> DigestRecord:
    """Refresh summary_short statuses for all media items in a digest."""
    changed = False
    for item in record.media_items:
        status, artifact_id = await _check_summary_short_status(
            record.user_id, item.media_item_id
        )
        if status != item.summary_short_status or artifact_id != item.summary_short_artifact_id:
            item.summary_short_status = status
            item.summary_short_artifact_id = artifact_id
            changed = True

    if changed:
        all_ready = all(mi.summary_short_status == "ready" for mi in record.media_items)
        if all_ready and record.media_items:
            record.status = DigestStatus.READY
        await digest_db.save_digest(record)

    return record


async def trigger_summary_short_generation(
    user_id: str, media_item_id: str
) -> Optional[str]:
    """
    Trigger summary_short generation for a library item if not already generated.
    Uses the artifact service's idempotence system to avoid duplicates.

    ``user_id`` is now required: ``media_item_id`` is a durable library id, so the
    owner comes from the library key rather than from a processing job that may no
    longer exist.

    Returns the artifact_id if generation was triggered or already exists, None on error.
    """
    from media_summarizer.core.services.artifact_service import (
        ArtifactScopeEmptyError,
        ArtifactServiceError,
        ArtifactTranscriptNotReadyError,
        commit_artifact_generation,
        enforce_scope_ceilings,
        plan_artifact_generation,
        resolve_scope_sources,
    )

    media = await user_media_store.get_user_media(user_id, media_item_id)
    if media is None or media.is_deleted:
        logger.warning(
            "Cannot trigger summary_short for %s: no library row", media_item_id
        )
        return None

    job = await resolve_job_for_record(media)
    if job is None or not getattr(job, "transcription_s3_key", None):
        logger.debug(
            "Cannot trigger summary_short for %s: no transcript", media_item_id
        )
        return None

    # Resolve the owner's reading language so the digest summary is produced in
    # the user's language (common detect+translate step, task-192).
    reading_language: Optional[str] = None
    try:
        user = await database_async.get_user_by_id(user_id)
        if user is not None:
            reading_language = user.reading_language
    except Exception:  # pragma: no cover - non-fatal lookup
        reading_language = None

    try:
        resolution = await resolve_scope_sources(
            user_id=user_id,
            scope=ArtifactScope.MEDIA,
            scope_id=media_item_id,
            reading_language=reading_language,
        )
        enforce_scope_ceilings(resolution)
        plan = await plan_artifact_generation(
            user_id=user_id,
            scope=ArtifactScope.MEDIA,
            scope_id=media_item_id,
            artifact_type=MediaArtifactType.SUMMARY_SHORT,
            resolution=resolution,
        )
        record, _deduplicated = await commit_artifact_generation(plan)
        return record.artifact_id
    except (
        ArtifactScopeEmptyError,
        ArtifactTranscriptNotReadyError,
        ArtifactServiceError,
    ) as exc:
        logger.warning(
            "Failed to trigger summary_short for %s: %s", media_item_id, exc
        )
        return None


async def get_user_digest_settings(user_id: str) -> UserDigestSettings:
    """Get digest settings for a user, returning defaults if none exist."""
    settings = await digest_db.get_user_digest_settings(user_id)
    if settings is None:
        return UserDigestSettings(user_id=user_id)
    return settings


async def update_user_digest_settings(
    user_id: str,
    *,
    digest_enabled: Optional[bool] = None,
    daily_digest_enabled: Optional[bool] = None,
    weekly_digest_enabled: Optional[bool] = None,
) -> UserDigestSettings:
    """Update digest settings for a user."""
    settings = await get_user_digest_settings(user_id)

    if digest_enabled is not None:
        settings.digest_enabled = digest_enabled
    if daily_digest_enabled is not None:
        settings.daily_digest_enabled = daily_digest_enabled
    if weekly_digest_enabled is not None:
        settings.weekly_digest_enabled = weekly_digest_enabled

    return await digest_db.save_user_digest_settings(settings)
