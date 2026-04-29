"""
Media search service: metadata-based search and filtering for user media items.

Provides text search on title (case-insensitive substring match), filtering by
tags, folder (including sub-folders), source platform, and media type.
Results are sorted by created_at DESC with cursor-based pagination.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from media_summarizer.core.models import ProcessingJob, Folder
from media_summarizer.core.services.folder_service import _get_descendant_ids
from media_summarizer.utils import database_async

logger = logging.getLogger(__name__)

# Default page size
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass
class SearchFilters:
    """Container for search/filter parameters."""

    q: Optional[str] = None  # Title text search (case-insensitive substring)
    tags: Optional[List[str]] = None  # Tag IDs to filter by (ANY match)
    folder_id: Optional[str] = None  # Folder ID (includes sub-folders)
    source: Optional[str] = None  # Source platform filter
    media_type: Optional[str] = None  # Media type filter
    status: Optional[str] = None  # Job status filter


@dataclass
class PaginationCursor:
    """Cursor for pagination based on (created_at_iso, id)."""

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
) -> SearchResult:
    """Search user's media items with metadata filters and pagination.

    Args:
        user_id: The authenticated user's ID.
        filters: Search and filter parameters.
        cursor: Pagination cursor (opaque string from previous response).
        limit: Maximum number of items to return per page.

    Returns:
        SearchResult with filtered, sorted, paginated items.
    """
    # Clamp limit
    limit = max(1, min(limit, MAX_PAGE_SIZE))

    # Fetch all user's processing jobs
    all_jobs = await database_async.get_processing_jobs_by_user_id(user_id)

    # Resolve folder IDs for sub-folder inclusion
    folder_ids_to_match: Optional[set] = None
    if filters.folder_id is not None:
        all_folders = await database_async.get_folders_by_user_id(user_id)
        descendant_ids = _get_descendant_ids(filters.folder_id, all_folders)
        folder_ids_to_match = {filters.folder_id} | set(descendant_ids)

    # Apply filters
    filtered_jobs = _apply_filters(all_jobs, filters, folder_ids_to_match)

    # Sort by created_at DESC, then by id DESC for stable ordering
    filtered_jobs.sort(
        key=lambda j: (j.created_at.isoformat(), j.id),
        reverse=True,
    )

    total_filtered = len(filtered_jobs)

    # Apply cursor-based pagination
    if cursor:
        try:
            parsed_cursor = PaginationCursor.from_string(cursor)
            filtered_jobs = _apply_cursor(filtered_jobs, parsed_cursor)
        except ValueError:
            # Invalid cursor, start from beginning
            pass

    # Take limit + 1 to determine if there are more items
    page_items = filtered_jobs[: limit + 1]
    has_more = len(page_items) > limit
    page_items = page_items[:limit]

    # Build next cursor
    next_cursor: Optional[str] = None
    if has_more and page_items:
        last_item = page_items[-1]
        next_cursor = PaginationCursor(
            created_at_iso=last_item.created_at.isoformat(),
            item_id=last_item.id,
        ).to_string()

    # Serialize items to response dicts
    items = [_job_to_search_result(job) for job in page_items]

    return SearchResult(
        items=items,
        total_filtered=total_filtered,
        next_cursor=next_cursor,
        has_more=has_more,
    )


def _apply_filters(
    jobs: List[ProcessingJob],
    filters: SearchFilters,
    folder_ids_to_match: Optional[set],
) -> List[ProcessingJob]:
    """Apply all search filters to the list of jobs."""
    result = []

    # Pre-compute lowercase query for title search
    query_lower = filters.q.lower().strip() if filters.q else None
    source_lower = filters.source.lower().strip() if filters.source else None
    media_type_lower = filters.media_type.lower().strip() if filters.media_type else None
    status_lower = filters.status.lower().strip() if filters.status else None

    for job in jobs:
        # Title search (case-insensitive substring match)
        if query_lower:
            job_title = (job.title or "").lower()
            if query_lower not in job_title:
                continue

        # Tag filter (any of the specified tags must be present)
        if filters.tags:
            job_tag_set = set(job.tag_ids) if job.tag_ids else set()
            if not job_tag_set.intersection(filters.tags):
                continue

        # Folder filter (including sub-folders)
        if folder_ids_to_match is not None:
            if (job.folder_id or "") not in folder_ids_to_match:
                continue

        # Source platform filter
        if source_lower:
            job_source = (job.source_platform or "").lower()
            if job_source != source_lower:
                continue

        # Media type filter
        if media_type_lower:
            job_media_type = (job.media_type or "").lower()
            if job_media_type != media_type_lower:
                continue

        # Status filter
        if status_lower:
            if job.status.value.lower() != status_lower:
                continue

        result.append(job)

    return result


def _apply_cursor(
    jobs: List[ProcessingJob], cursor: PaginationCursor
) -> List[ProcessingJob]:
    """Skip items up to and including the cursor position.

    Since items are sorted DESC by (created_at, id), we skip all items
    that come before or at the cursor position.
    """
    cursor_key = (cursor.created_at_iso, cursor.item_id)

    for i, job in enumerate(jobs):
        job_key = (job.created_at.isoformat(), job.id)
        if job_key < cursor_key:
            # This item comes after the cursor in DESC order
            return jobs[i:]

    # Cursor is past all items
    return []


def _job_to_search_result(job: ProcessingJob) -> Dict[str, Any]:
    """Convert a ProcessingJob to a search result dict."""
    return {
        "media_item_id": job.id,
        "title": job.title,
        "source_platform": job.source_platform,
        "media_type": job.media_type,
        "status": job.status.value,
        "folder_id": job.folder_id,
        "tag_ids": job.tag_ids or [],
        "source_url": job.source_url,
        "media_image": job.media_image,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "progress": job.get_progress_percentage(),
        "error_message": job.error_message,
    }
