"""User-initiated rename of one library item's title.

A rename is a two-surface write, and that is the whole reason this is a service
rather than three lines in the endpoint:

1. ``user_media`` holds the title the library lists and the media screen shows.
   ``title`` is not immutable (``utils/user_media._IMMUTABLE_ATTRS``), so the
   attribute-level ``SET`` of ``update_attributes`` is all the storage layer
   needs — no new primitive, and a concurrent folder move is not clobbered.
2. Algolia holds a **denormalized copy** of the title on every transcript chunk
   (``search_indexing.index_transcript``), where it is both searchable and
   highlighted. A rename that stops at DynamoDB leaves the search results
   showing — and matching on — the old name, which is the bug this service
   exists to prevent.

Ownership is the ``(user_id, media_item_id)`` key itself, exactly as for the
folder move: another user's item simply does not exist here.

Scope is deliberately the user-facing title and nothing else. ``media_key``,
``saved_at``, the dedup identity and the artifacts are untouched: renaming what
you saved does not make it a different save.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from media_summarizer.core.media_ingestion.title_derivation import MAX_TITLE_LENGTH
from media_summarizer.core.services import search_indexing
from media_summarizer.utils import user_media as user_media_store
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

EVENT_RENAMED = "user_media.renamed"
EVENT_SEARCH_RETITLE_FAILED = "user_media.rename_search_failed"


class MediaNotFound(LookupError):
    """No library row of this user matches the requested id."""


def normalize_title(raw: Optional[str]) -> str:
    """Trim a submitted title and refuse what cannot become one.

    The ceiling is :data:`MAX_TITLE_LENGTH`, the same bound the ingestion
    pipeline derives titles under: a hand-typed name that no automatic title
    could ever reach would only be a row the lists have to truncate anyway.

    Raises:
        ValueError: the value is missing, blank once trimmed, or too long.
    """
    if raw is None:
        raise ValueError("A title is required")
    trimmed = " ".join(raw.split())
    if not trimmed:
        raise ValueError("A title cannot be blank")
    if len(trimmed) > MAX_TITLE_LENGTH:
        raise ValueError(f"A title cannot exceed {MAX_TITLE_LENGTH} characters")
    return trimmed


async def rename_media_for_user(
    *, user_id: str, media_item_id: str, title: str
) -> str:
    """Give one library item a new user-facing title.

    Returns:
        The stored title, trimmed.

    Raises:
        MediaNotFound: no visible row of this user matches the id.
        ValueError: the title is blank or too long.
    """
    normalized = normalize_title(title)

    record = await user_media_store.get_user_media(user_id, media_item_id)
    if record is None:
        raise MediaNotFound(media_item_id)

    updated = await user_media_store.update_attributes(
        user_id=user_id,
        media_item_id=media_item_id,
        attributes={"title": normalized},
    )
    if not updated:
        raise MediaNotFound(media_item_id)

    # Best-effort, and deliberately after the durable write: the library is the
    # source of truth, and a search index that lags by one title is a cosmetic
    # staleness. Failing the user's rename over it would be the worse trade.
    try:
        await asyncio.to_thread(
            search_indexing.update_media_title,
            user_id=user_id,
            media_item_id=media_item_id,
            title=normalized,
        )
    except Exception as exc:  # noqa: BLE001 - every failure mode must be logged
        log_event(
            logger,
            logging.ERROR,
            EVENT_SEARCH_RETITLE_FAILED,
            f"Search chunks keep the previous title: {exc}",
            user_id=user_id,
            media_item_id=media_item_id,
            error_type=type(exc).__name__,
            exc_info=True,
        )

    log_event(
        logger,
        logging.INFO,
        EVENT_RENAMED,
        "Library row renamed",
        user_id=user_id,
        media_item_id=media_item_id,
        title_length=len(normalized),
    )
    return normalized
