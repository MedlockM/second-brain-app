"""
User-initiated deletion of one library item — the only writer of ``purge_at``.

§6.2 of ``docs/research/task-218-durable-media-library-persistence/README.md``
defines the model this file implements:

1. The user deletes an item. The row is **soft-deleted**: ``deleted_at`` is
   stamped and ``purge_at`` is set to now + :data:`PURGE_GRACE_DAYS` days.
2. The item leaves every read surface immediately — the DynamoDB read helpers
   filter ``deleted_at`` out, and the search index chunks are removed here and
   now, because Algolia is a live read surface and a "deleted" item that still
   answers a search is still visible.
3. ``PURGE_GRACE_DAYS`` later, the DynamoDB TTL sweeps the row and the stream
   ``REMOVE`` event drives the cascade in
   ``workers/cleanup/media_lifecycle.py``, which deletes the artifacts, the S3
   objects and the index entries for good.

Why a grace period at all, when the user asked for a deletion: 30 days of "the
row is invisible but still there" is the window in which an accidental deletion
or a bug in this service remains recoverable. It also makes the cascade safely
eventually-consistent. Shared content is purged only after its final visible
library reference disappears.

Account deletion is a different use case and does not come through here: an
erasure request removes the rows outright (``user_media.delete_all_for_user``,
task-224) instead of scheduling them 30 days out.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from media_summarizer.core.models.user_media import UserMediaRecord
from media_summarizer.core.services import search_indexing
from media_summarizer.utils import user_media as user_media_store
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

# The grace window between the user's deletion and the irreversible cascade.
# Matches the 30 days §6.2 fixes, and is the number the runbook and
# docs/DATA_RETENTION.md quote to users.
PURGE_GRACE_DAYS = 30

EVENT_SOFT_DELETED = "user_media.soft_deleted"
EVENT_ALREADY_DELETED = "user_media.delete_noop"
EVENT_DELETE_FAILED = "user_media.delete_failed"
EVENT_SEARCH_DELETE_FAILED = "user_media.delete_search_failed"


class MediaNotFound(LookupError):
    """No library row of this user matches the requested id."""


@dataclass(frozen=True)
class DeletionResult:
    """What happened, for the API layer to shape a response from."""

    media_item_id: str
    purge_at: int
    deleted_at: Optional[str]
    already_deleted: bool


async def _resolve_row(user_id: str, media_item_id: str) -> UserMediaRecord:
    """Find the library row a client's id refers to, or raise :class:`MediaNotFound`.

    Only durable save ids are accepted. The app has never shipped, so the old
    job-id fallback is deleted rather than carried into the per-save identity
    model.
    """
    record = await user_media_store.get_user_media(
        user_id, media_item_id, include_deleted=True
    )
    if record is None:
        raise MediaNotFound(media_item_id)
    return record


async def delete_media_for_user(*, user_id: str, media_item_id: str) -> DeletionResult:
    """Soft-delete one library item and take it off the read surfaces.

    Idempotent: deleting an item twice returns the *first* deletion's
    ``purge_at`` rather than pushing it 30 more days out, so a retrying client
    cannot keep an item alive indefinitely.

    Raises:
        MediaNotFound: no row of this user matches the id.
    """
    record = await _resolve_row(user_id, media_item_id)
    resolved_id = record.media_item_id

    try:
        deleted = await user_media_store.mark_deleted(
            user_id=user_id,
            media_item_id=resolved_id,
            grace_days=PURGE_GRACE_DAYS,
        )
    except Exception as exc:  # noqa: BLE001 - every failure mode must be alarmed
        log_event(
            logger,
            logging.ERROR,
            EVENT_DELETE_FAILED,
            f"Could not soft-delete library row: {exc}",
            user_id=user_id,
            media_item_id=resolved_id,
            error_type=type(exc).__name__,
            exc_info=True,
        )
        raise

    already_deleted = deleted is None
    if deleted is None:
        # The conditional write refused: the row was already soft-deleted. Re-read
        # it so the caller still learns the purge date, and fall through to the
        # search cleanup, which is idempotent and may have failed the first time.
        current = await user_media_store.get_user_media(
            user_id, resolved_id, include_deleted=True
        )
        if current is None:
            raise MediaNotFound(media_item_id)
        deleted = current

    # Algolia is a live read surface, so "invisible immediately" has to include
    # it. Best-effort: the purge cascade calls the same delete again in 30 days,
    # so a failure here is a temporary leak of searchable text, not a permanent
    # one, and it must not turn the user's deletion into an error.
    try:
        await asyncio.to_thread(search_indexing.delete_document, user_id, resolved_id)
    except Exception as exc:  # noqa: BLE001 - see above
        log_event(
            logger,
            logging.ERROR,
            EVENT_SEARCH_DELETE_FAILED,
            f"Search chunks survive a deleted media item: {exc}",
            user_id=user_id,
            media_item_id=resolved_id,
            error_type=type(exc).__name__,
            exc_info=True,
        )

    log_event(
        logger,
        logging.INFO,
        EVENT_ALREADY_DELETED if already_deleted else EVENT_SOFT_DELETED,
        (
            "Library row was already scheduled for purge"
            if already_deleted
            else "Library row soft-deleted and scheduled for purge"
        ),
        user_id=user_id,
        media_item_id=resolved_id,
        requested_media_item_id=media_item_id,
        purge_at=deleted.purge_at,
        grace_days=PURGE_GRACE_DAYS,
    )

    return DeletionResult(
        media_item_id=resolved_id,
        purge_at=int(deleted.purge_at or 0),
        deleted_at=deleted.deleted_at.isoformat() if deleted.deleted_at else None,
        already_deleted=already_deleted,
    )
