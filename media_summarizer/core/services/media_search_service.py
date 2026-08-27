"""
Media search service: metadata-based search and filtering for user media items.

Provides text search on title (case-insensitive substring match), filtering by
tags, folder (including sub-folders), source platform, and media type.
Results are sorted by saved_at, newest first by default, with cursor-based
pagination. A caller can ask for oldest first instead (``sort_direction="asc"``,
task-323): a triage pass works through the backlog in the order it accumulated,
so it needs the tail of the library, and reversing a page client-side would only
reverse *that page* — the oldest item would still be on the last page.

Source of truth is the durable ``user_media`` table, never ``processing_jobs``
(task-220, §4.4 of the task-218 benchmark). This is what makes the library and
Search survive the expiry of a processing job: nothing on this path dereferences
an operational row, so there is nothing to lose when one disappears.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

from media_summarizer.core.media_ingestion.media_metadata import parse_cover_locator
from media_summarizer.core.models.user_media import UserMediaRecord
from media_summarizer.core.services.folder_service import _get_descendant_ids
from media_summarizer.utils import database_async, s3
from media_summarizer.utils import user_media as user_media_store

logger = logging.getLogger(__name__)

# Default page size
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# How long a signed cover URL stays usable. Generous on purpose: the Inbox
# refetches on focus, and a shorter window would expire under an app left open
# across a session. The client caches across rotations through `expo-image`'s
# `cacheKey` (task-302 §6.2), so a changing signature costs no re-download.
COVER_URL_EXPIRATION_SECONDS = 86400

#: Chronological direction of the page. Declared here rather than in the endpoint
#: so the query parameter that produces the 422 and the sort that honours it are
#: the same two values.
SortDirection = Literal["asc", "desc"]
DEFAULT_SORT_DIRECTION: SortDirection = "desc"


@dataclass
class SearchFilters:
    """Container for search/filter parameters."""

    q: Optional[str] = None  # Title text search (case-insensitive substring)
    tags: Optional[List[str]] = None  # Tag IDs to filter by (ANY match)
    folder_id: Optional[str] = None  # Folder ID (includes sub-folders)
    source: Optional[str] = None  # Source platform filter
    media_type: Optional[str] = None  # Media type filter
    status: Optional[str] = None  # Library processing status filter


@dataclass
class PaginationCursor:
    """Cursor for pagination based on (saved_at_iso, media_item_id)."""

    created_at_iso: str
    item_id: str

    @classmethod
    def from_string(cls, cursor_str: str) -> "PaginationCursor":
        """Parse a cursor string in the format 'created_at_iso|id'."""
        parts = cursor_str.split("|", 1)
        if len(parts) != 2:
            raise ValueError("Invalid cursor format")
        return cls(created_at_iso=parts[0], item_id=parts[1])

    def to_string(self) -> str:
        """Serialize cursor to string."""
        return f"{self.created_at_iso}|{self.item_id}"


@dataclass
class SearchResult:
    """Result of a media search operation."""

    items: List[Dict[str, Any]]
    total_filtered: int  # Total count of items matching filters (before pagination)
    next_cursor: Optional[str]  # Cursor for next page (None if last page)
    has_more: bool


async def search_media(
    user_id: str,
    filters: SearchFilters,
    cursor: Optional[str] = None,
    limit: int = DEFAULT_PAGE_SIZE,
    sort_direction: SortDirection = DEFAULT_SORT_DIRECTION,
) -> SearchResult:
    """Search user's media items with metadata filters and pagination.

    Args:
        user_id: The authenticated user's ID.
        filters: Search and filter parameters.
        cursor: Pagination cursor (opaque string from previous response).
        limit: Maximum number of items to return per page.
        sort_direction: ``"desc"`` (default, newest first) or ``"asc"`` (oldest
            first). The cursor is applied in the same direction, so paginating an
            ascending list walks forward through time instead of skipping the
            whole library on the second page.

    Returns:
        SearchResult with filtered, sorted, paginated items.
    """
    # Clamp limit
    limit = max(1, min(limit, MAX_PAGE_SIZE))

    # Fetch the user's durable library rows
    all_records = await user_media_store.list_library_for_user(user_id)

    # Resolve folder IDs for sub-folder inclusion
    folder_ids_to_match: Optional[set] = None
    if filters.folder_id is not None:
        all_folders = await database_async.get_folders_by_user_id(user_id)
        descendant_ids = _get_descendant_ids(filters.folder_id, all_folders)
        folder_ids_to_match = {filters.folder_id} | set(descendant_ids)

    # Apply filters
    filtered = _apply_filters(all_records, filters, folder_ids_to_match)

    # Sort by (saved_at, id) in the requested direction. The id is part of the key
    # so two items saved in the same millisecond keep a stable relative order --
    # without it the cursor could skip or repeat one of them.
    ascending = sort_direction == "asc"
    filtered.sort(key=_sort_key, reverse=not ascending)

    total_filtered = len(filtered)

    # Apply cursor-based pagination
    if cursor:
        try:
            parsed_cursor = PaginationCursor.from_string(cursor)
            filtered = _apply_cursor(filtered, parsed_cursor, ascending=ascending)
        except ValueError:
            # Invalid cursor, start from beginning
            pass

    # Take limit + 1 to determine if there are more items
    page_items = filtered[: limit + 1]
    has_more = len(page_items) > limit
    page_items = page_items[:limit]

    # Build next cursor
    next_cursor: Optional[str] = None
    if has_more and page_items:
        last_item = page_items[-1]
        next_cursor = PaginationCursor(
            created_at_iso=last_item.saved_at.isoformat(),
            item_id=last_item.media_item_id,
        ).to_string()

    # Serialize items to response dicts
    items = [_record_to_search_result(record) for record in page_items]
    await resolve_cover_urls(items)

    return SearchResult(
        items=items,
        total_filtered=total_filtered,
        next_cursor=next_cursor,
        has_more=has_more,
    )


def _sort_key(record: UserMediaRecord) -> tuple:
    return (record.saved_at.isoformat(), record.media_item_id)


def _apply_filters(
    records: List[UserMediaRecord],
    filters: SearchFilters,
    folder_ids_to_match: Optional[set],
) -> List[UserMediaRecord]:
    """Apply all search filters to the list of library rows."""
    result = []

    # Pre-compute lowercase query for title search
    query_lower = filters.q.lower().strip() if filters.q else None
    source_lower = filters.source.lower().strip() if filters.source else None
    media_type_lower = filters.media_type.lower().strip() if filters.media_type else None
    status_lower = filters.status.lower().strip() if filters.status else None

    for record in records:
        # Title search (case-insensitive substring match)
        if query_lower:
            if query_lower not in (record.title or "").lower():
                continue

        # Tag filter (any of the specified tags must be present)
        if filters.tags:
            if not set(record.tag_ids).intersection(filters.tags):
                continue

        # Folder filter (including sub-folders)
        if folder_ids_to_match is not None:
            if (record.folder_id or "") not in folder_ids_to_match:
                continue

        # Source platform filter
        if source_lower:
            if (record.source_platform or "").lower() != source_lower:
                continue

        # Media type filter
        if media_type_lower:
            if (record.media_type or "").lower() != media_type_lower:
                continue

        # Status filter. An item with no known processing status is never a match:
        # the attribute is nullable by contract, and "unknown" is not a status.
        if status_lower:
            current = record.processing_status.value if record.processing_status else None
            if current is None or current.lower() != status_lower:
                continue

        result.append(record)

    return result


def _apply_cursor(
    records: List[UserMediaRecord],
    cursor: PaginationCursor,
    *,
    ascending: bool = False,
) -> List[UserMediaRecord]:
    """Skip items up to and including the cursor position.

    "After the cursor" is direction-dependent, which is the whole reason this
    takes ``ascending``: comparing with ``<`` on an ascending page would treat the
    first item past the cursor as already consumed and return the empty list, so
    an ascending listing would stop after one page.
    """
    cursor_key = (cursor.created_at_iso, cursor.item_id)

    for i, record in enumerate(records):
        record_key = _sort_key(record)
        past_cursor = record_key > cursor_key if ascending else record_key < cursor_key
        if past_cursor:
            return records[i:]

    # Cursor is past all items
    return []


async def load_display_details(
    user_id: str,
    media_item_ids: List[str],
) -> Dict[str, Dict[str, Any]]:
    """What a media item *looks* like, read from the library row itself.

    The transcript index is a search index: it answers which items match, and
    where in their text. It is a poor place to also keep what those items look
    like — a cover denormalised into it would be written once, at indexing time,
    and would then be wrong for every item indexed before covers existed, stale
    for every cover replaced afterwards, and impossible to reconcile without a
    reindex. The library row is the single source of truth for all of that, and
    reading it here is what makes a search result and a library row show the
    same picture *by construction*.

    One `get_item` per hit, by primary key, capped by the page size the endpoint
    already enforces. Covers are signed by the same resolver the library list
    uses, so a signing failure blanks one cover rather than failing the search.

    A missing id maps to nothing: the row is gone (deleted, or never mirrored)
    and the caller falls back to what the index knows.
    """
    if not media_item_ids:
        return {}

    records = await asyncio.gather(
        *(
            user_media_store.get_user_media(user_id, media_item_id)
            for media_item_id in media_item_ids
        )
    )

    details: Dict[str, Dict[str, Any]] = {}
    for media_item_id, record in zip(media_item_ids, records):
        if record is None:
            continue
        details[media_item_id] = {
            "title": record.title,
            "creator_name": record.creator_name,
            "media_type": record.media_type,
            "media_image": record.thumbnail_url,
        }

    await resolve_cover_urls(list(details.values()))
    return details


async def resolve_cover_urls(items: List[Dict[str, Any]]) -> None:
    """Turn stored cover values into something the client can fetch, in place.

    Public because the search endpoint needs the same treatment: a cover is
    stored once and read from two places, and signing it twice in two ways is
    how the two surfaces would end up disagreeing about which covers load.

    ``thumbnail_url`` holds one of two shapes (task-302 §5): an absolute
    third-party URL, hotlinked as-is, or an ``s3://bucket/key`` locator for a
    re-hosted cover, which is signed here. Every locator on the page goes
    through a single client, and a signing failure blanks that one cover rather
    than failing the read -- the tile then falls back to its media-type icon.
    """
    pending: List[tuple[int, tuple[str, str]]] = []
    for index, item in enumerate(items):
        located = parse_cover_locator(item.get("media_image"))
        if located:
            pending.append((index, located))
    if not pending:
        return

    signed = await s3.generate_presigned_urls(
        [located for _, located in pending],
        expiration=COVER_URL_EXPIRATION_SECONDS,
    )
    for (index, _), url in zip(pending, signed):
        items[index]["media_image"] = url


def _record_to_search_result(record: UserMediaRecord) -> Dict[str, Any]:
    """Convert a durable library row to a search result dict.

    ``status`` mirrors ``processing_status`` and is nullable: the library entry
    exists whether or not anything is known about its processing. ``completed_at``
    and ``error_message`` are gone from this payload -- they were job attributes,
    and a list read no longer touches jobs.

    ``review_blurb`` is the mirrored prose (task-323). It has to be listed here
    *and* declared on the endpoint's response model: this dict is validated into
    that model, and Pydantic drops an undeclared key without a word.
    """
    return {
        "media_item_id": record.media_item_id,
        "title": record.title,
        "review_blurb": record.review_blurb,
        "creator_name": record.creator_name,
        "source_platform": record.source_platform,
        "media_type": record.media_type,
        "status": record.processing_status.value if record.processing_status else None,
        "folder_id": record.folder_id,
        "tag_ids": list(record.tag_ids),
        "source_url": record.source_url,
        "media_image": record.thumbnail_url,
        "created_at": record.saved_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }
