"""
Ownership gate for every media-scoped endpoint (task-220).

One helper, used by ``/api/media/*`` and ``/api/artifacts/*`` alike, so the
question "does this item belong to the caller" has exactly one answer in the
codebase. It resolves against the durable ``user_media`` table, never against
``processing_jobs``: the operational row is allowed to expire, and access to a
library item must not expire with it (§4.4 of the task-218 benchmark).

Two properties are deliberate:

- **Ownership is the key, not a comparison.** The lookup is
  ``GetItem(user_id, media_item_id)``, so another user's item is not "denied",
  it simply does not exist for this caller. There is no ``job.user_id !=
  current_user.id`` branch left to forget.
- **404, not 403.** Since the read is already scoped to the caller, a missing row
  and a foreign row are the same event, and answering 403 for the second would
  leak the existence of another user's item.
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, status

from media_summarizer.core.models.user_media import UserMediaRecord
from media_summarizer.utils import user_media as user_media_store


async def get_media_for_user(media_item_id: str, user_id: str) -> UserMediaRecord:
    """Return the caller's library row, or raise 404.

    Raises:
        HTTPException: 404 when the item does not exist, does not belong to the
            caller, or has been soft-deleted.
    """
    record: Optional[UserMediaRecord] = await user_media_store.get_user_media(
        user_id, media_item_id
    )
    if record is None or record.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media item not found",
        )
    return record
