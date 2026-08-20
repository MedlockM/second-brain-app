"""The engagement signal behind the Inbox "Continue learning" row (task-303).

Owner-validated recommendation of
``docs/research/task-303-engagement-recency-model/README.md`` — Option A: the
signal is **one attribute on the thing itself**, ``last_engaged_at``, plus one
sparse GSI on ``user_media``. No activity table, no event log, no device-local
store, and therefore nothing that can hold a pointer to destroyed content.

What counts as an engagement (§2.2), and nothing else:

    E1  a generation was launched -- ``POST /api/artifacts`` accepted a request for
        this scope, including the deduplicated ``200`` path. The user asked; that
        the answer already existed is an implementation detail they never see.
    E2  an artifact was opened and rendered -- the viewer reports it once per
        mount, through ``POST /api/engagements``.

Opening a media detail screen does **not** count: it would make the row a
*recently tapped* list, duplicate "Recently added", fire on accidental taps, and
admit items that have nothing to continue. Reading the transcript does not count
in v1 either, because the reader is the detail screen's default tab and the app
cannot tell the two events apart.

Both writes are best-effort in the ``quota_enforcer._debit`` sense: they swallow,
they log, and they never fail the action the user actually asked for. There is no
retry -- the event recurs the next time the user opens something, and a retry queue
for a decoration is disproportionate.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from media_summarizer.core.media_ingestion.media_metadata import parse_cover_locator
from media_summarizer.core.models.user_media import UserMediaRecord
from media_summarizer.core.services.media_search_service import COVER_URL_EXPIRATION_SECONDS
from media_summarizer.utils import database_async, s3
from media_summarizer.utils import user_media as user_media_store
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

# The two kinds of subject a user can engage with. "collection" is what the UI
# calls a folder; the artifact API's own word for the same thing is "folder".
KIND_MEDIA = "media"
KIND_COLLECTION = "collection"

# How many entries the row holds. A server-side default so the row can be
# re-tuned without shipping an app build.
DEFAULT_RECENT_LIMIT = 12
MAX_RECENT_LIMIT = 20

# Beyond this, an engagement is not something to continue. Enforced as a sort-key
# range condition on the media side, so stale entries cost nothing to exclude and
# the row empties itself -- which is what makes "hide the section when empty"
# implementable: no items means no section.
RECENT_WINDOW_DAYS = 90

# A collection tile draws a small mosaic of its newest items' covers.
MAX_PREVIEW_IMAGES = 4


class EngagementSubjectNotFoundError(Exception):
    """The subject does not exist, or is not this user's. Answered as a 404."""


@dataclass
class RecentEngagement:
    """One tile of the row, render-ready.

    Both kinds share ``kind`` / ``id`` / ``title`` / ``engaged_at``. Media entries
    carry ``creator_name``, ``image_url`` and ``media_type`` (the fallback icon
    needs the type); collection entries carry ``item_count`` and up to
    ``MAX_PREVIEW_IMAGES`` covers. A collection with no covered item returns an
    empty list, and the client draws its accent-surface fallback.
    """

    kind: str
    id: str
    engaged_at: datetime
    title: Optional[str] = None
    creator_name: Optional[str] = None
    image_url: Optional[str] = None
    media_type: Optional[str] = None
    item_count: Optional[int] = None
    preview_images: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------


async def stamp(*, user_id: str, kind: str, subject_id: str) -> bool:
    """Stamp one engagement. Best-effort: never raises, never retries.

    Callers that already know the subject is owned (``POST /api/artifacts``, which
    asserted it to accept the generation at all) come straight here.

    Returns:
        True when the stamp landed. False covers every refusal without
        distinguishing them, because no caller may act on the difference: the
        dampener rejected it, the row is gone, the item is soft-deleted, the folder
        belongs to somebody else, or the write itself failed.
    """
    subject_id = (subject_id or "").strip()
    if not subject_id:
        return False
    try:
        if kind == KIND_MEDIA:
            return await user_media_store.stamp_engagement(user_id, subject_id)
        if kind == KIND_COLLECTION:
            return await database_async.stamp_folder_engagement(
                subject_id,
                user_id=user_id,
                dampener_seconds=user_media_store.ENGAGEMENT_DAMPENER_SECONDS,
            )
        return False
    except Exception as exc:  # noqa: BLE001 - a recency decoration never fails a user action
        # Logged as a structured event so a systematic breakage is visible, and
        # deliberately without an alarm: the row degrades to empty, which the Inbox
        # already renders as "no section".
        log_event(
            logger,
            logging.WARNING,
            "engagement.stamp_failed",
            "Could not record an engagement",
            user_id=user_id,
            kind=kind,
            subject_id=subject_id,
            error_type=type(exc).__name__,
        )
        return False


async def record_engagement(*, user_id: str, kind: str, subject_id: str) -> bool:
    """Ownership-checked stamp, behind ``POST /api/engagements``.

    The subject is resolved before anything is written, so an unowned or unknown id
    is a 404 that writes nothing -- the same check the artifact routes make, for the
    same reason.

    Raises:
        EngagementSubjectNotFoundError: unknown subject, or another user's.
    """
    subject_id = (subject_id or "").strip()
    if not subject_id:
        raise EngagementSubjectNotFoundError("Unknown engagement subject")

    if kind == KIND_MEDIA:
        record = await user_media_store.get_user_media(user_id, subject_id)
        if record is None:
            raise EngagementSubjectNotFoundError("Media item not found")
    elif kind == KIND_COLLECTION:
        folder = await database_async.get_folder_by_id(subject_id)
        if folder is None or folder.user_id != user_id:
            raise EngagementSubjectNotFoundError("Collection not found")
    else:
        raise EngagementSubjectNotFoundError(f"Unknown engagement kind: {kind}")

    return await stamp(user_id=user_id, kind=kind, subject_id=subject_id)


# ---------------------------------------------------------------------------
# Read path
# ---------------------------------------------------------------------------


async def list_recent(user_id: str, *, limit: int = DEFAULT_RECENT_LIMIT) -> List[RecentEngagement]:
    """The row itself: one merged, sorted, capped list of media *and* collections.

    Two DynamoDB calls, issued concurrently — the sparse ``engaged-index`` query on
    ``user_media``, and the ``user-index`` query that already returns every folder of
    the user with every attribute (so the folder side needs no index of its own, and
    is windowed and ordered in Python). A third, conditional call hydrates the
    collections that made the cut.
    """
    limit = max(1, min(limit, MAX_RECENT_LIMIT))
    window_start = datetime.now(timezone.utc) - timedelta(days=RECENT_WINDOW_DAYS)

    engaged_media, folders = await asyncio.gather(
        user_media_store.list_recently_engaged(user_id, limit=limit, since=window_start),
        database_async.get_folders_by_user_id(user_id),
    )

    entries: List[RecentEngagement] = []

    for item in engaged_media:
        engaged_at = _parse_instant(item.get("last_engaged_at"))
        media_item_id = str(item.get("media_item_id") or "")
        if engaged_at is None or not media_item_id:
            continue
        entries.append(
            RecentEngagement(
                kind=KIND_MEDIA,
                id=media_item_id,
                engaged_at=engaged_at,
                title=_as_optional_str(item.get("title")),
                creator_name=_as_optional_str(item.get("creator_name")),
                image_url=_as_optional_str(item.get("thumbnail_url")),
                media_type=_as_optional_str(item.get("media_type")),
            )
        )

    for folder in folders:
        engaged_at = _as_aware(folder.last_engaged_at)
        if engaged_at is None or engaged_at <= window_start:
            continue
        entries.append(
            RecentEngagement(
                kind=KIND_COLLECTION,
                id=folder.id,
                engaged_at=engaged_at,
                title=folder.name,
            )
        )

    # Newest first, id as the tie-breaker so two engagements stamped in the same
    # millisecond keep a stable order between two reads.
    entries.sort(key=lambda entry: (entry.engaged_at, entry.id), reverse=True)
    entries = entries[:limit]

    await _hydrate_collections(user_id, entries)
    await _sign_covers(entries)
    return entries


async def _hydrate_collections(user_id: str, entries: List[RecentEngagement]) -> None:
    """Fill ``item_count`` and ``preview_images`` for the collections in the row.

    One partition read for the whole row rather than one ``folder-index`` query per
    collection: up to twelve queries returning full items is more payload for less
    information, and this is the same read ``GET /api/folders`` already performs on
    every Inbox open. Skipped entirely when the capped row holds no collection.
    """
    collection_ids = {entry.id for entry in entries if entry.kind == KIND_COLLECTION}
    if not collection_ids:
        return

    per_folder: Dict[str, List[UserMediaRecord]] = {fid: [] for fid in collection_ids}
    for record in await user_media_store.list_library_for_user(user_id):
        bucket = per_folder.get(record.folder_id or "")
        if bucket is not None:
            bucket.append(record)

    for entry in entries:
        if entry.kind != KIND_COLLECTION:
            continue
        records = sorted(
            per_folder.get(entry.id, []),
            key=lambda record: record.saved_at,
            reverse=True,
        )
        entry.item_count = len(records)
        entry.preview_images = [
            record.thumbnail_url for record in records if record.thumbnail_url
        ][:MAX_PREVIEW_IMAGES]


async def _sign_covers(entries: List[RecentEngagement]) -> None:
    """Turn stored cover values into something the client can fetch, in place.

    A cover is stored either as an absolute third-party URL, hotlinked as-is, or as
    an ``s3://bucket/key`` locator for a re-hosted one, which is signed here — the
    client must never have to know which. Every locator in the row goes through a
    single signing client, and a signature that cannot be produced blanks that one
    cover instead of failing the read.
    """
    pending: List[Tuple[RecentEngagement, Optional[int], Tuple[str, str]]] = []
    for entry in entries:
        located = parse_cover_locator(entry.image_url)
        if located:
            pending.append((entry, None, located))
        for index, value in enumerate(entry.preview_images):
            located = parse_cover_locator(value)
            if located:
                pending.append((entry, index, located))
    if not pending:
        return

    signed = await s3.generate_presigned_urls(
        [located for _, _, located in pending],
        expiration=COVER_URL_EXPIRATION_SECONDS,
    )
    for (entry, slot, _), url in zip(pending, signed):
        if slot is None:
            entry.image_url = url
        elif url:
            entry.preview_images[slot] = url

    # A preview whose signature failed is dropped rather than sent as an empty
    # string: the tile draws fewer covers, which it already handles.
    for entry in entries:
        if entry.preview_images:
            entry.preview_images = [
                value for value in entry.preview_images if not parse_cover_locator(value)
            ]


def _parse_instant(raw: Any) -> Optional[datetime]:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return _as_aware(datetime.fromisoformat(raw))
    except ValueError:
        return None


def _as_aware(value: Optional[datetime]) -> Optional[datetime]:
    """UTC-normalise an instant so window comparisons can never raise."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _as_optional_str(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None
