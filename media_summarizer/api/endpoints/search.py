"""
Search API endpoints for transcript search.

Provides full-text search over indexed media transcripts, proxied through the
backend to Algolia.

Multi-tenant isolation: the shared index stores all users' records with a
``user_id`` attribute, and isolation is enforced by an explicit user_id filter
applied server-side in the query.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.services import search_indexing
from media_summarizer.core.services.media_search_service import load_display_details

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------- Response Models ----------


class SearchHitHighlight(BaseModel):
    """Highlight snippet from a search hit."""

    field: str = Field(..., description="Field name containing the match")
    snippet: str = Field(..., description="Highlighted snippet with match context")


class SearchHit(BaseModel):
    """A single search result.

    Everything about how the hit *looks*, and everything the client's actions
    menu writes to, is read from the durable library row (task-375). The index
    answers which items match and where in their text; it is not asked what they
    are called, where they are filed or when they were saved. That is what makes
    one media show the same cover, the same subtitle and the same date whether it
    is reached through the library list or through a search.

    ``in_library`` is the one field that says which source answered. A deletion
    does not unindex a transcript, so a hit can come back with no row behind it:
    it then carries only what the index knows, and there is nothing left to
    rename, move or delete.
    """

    media_item_id: str = Field(..., description="ID of the matching media item")
    title: Optional[str] = Field(None, description="Media title")
    creator_name: Optional[str] = Field(None, description="Publisher of the media")
    source_platform: Optional[str] = Field(None, description="Source platform")
    media_type: Optional[str] = Field(
        None, description="Media kind, drawn as a glyph when there is no cover"
    )
    media_image: Optional[str] = Field(
        None,
        description=(
            "Fetchable cover URL, signed on read for a re-hosted cover. Read "
            "from the library row, so it is the same picture the library list "
            "shows. Null when the item has none."
        ),
    )
    source_url: Optional[str] = Field(
        None,
        description=(
            "Where the media came from, read from the library row. The vignette "
            "shows its domain as the subtitle when the media has no creator."
        ),
    )
    folder_id: Optional[str] = Field(
        None,
        description=(
            "Folder the media is filed in, read from the library row. Null means "
            "unsorted -- which is also what the folder picker preselects."
        ),
    )
    created_at: str = Field(
        ...,
        description=(
            "When the media was saved (ISO 8601), read from the library row so "
            "it is the very date the library list renders. Falls back to the "
            "index's own timestamp for a hit with no row left."
        ),
    )
    updated_at: str = Field(
        ...,
        description=(
            "Last write on the library row (ISO 8601). The client builds its "
            "cover cache key from it, so a replaced cover is refetched."
        ),
    )
    in_library: bool = Field(
        ...,
        description=(
            "Whether the media still has a library row. False on a hit the index "
            "kept after a deletion: no action can be offered on it."
        ),
    )
    text_match_score: int = Field(
        ..., description="Text match relevance score"
    )
    highlights: List[SearchHitHighlight] = Field(
        default_factory=list, description="Highlighted snippets"
    )


class SearchResponse(BaseModel):
    """Response model for transcript search."""

    query: str = Field(..., description="Original search query")
    found: int = Field(..., description="Total number of matching documents")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Results per page")
    hits: List[SearchHit] = Field(default_factory=list, description="Search results")


# ---------- Helpers ----------


def _iso_from_index_timestamp(value: Any) -> str:
    """Render the index's own Unix creation timestamp as an ISO 8601 instant.

    Only ever reached for a hit whose library row is gone: the row is the source
    of truth for the date, and this keeps the field one type for every hit rather
    than making the client parse two. UTC and explicitly offset, like every date
    the API sends -- an offset-less string is read as local time by the client's
    ``Date`` and would drift the age it prints.
    """
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        seconds = 0
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()


# ---------- Endpoints ----------


@router.get("/transcripts", response_model=SearchResponse)
async def search_transcripts(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    page: int = Query(1, ge=1, le=100, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Results per page"),
    source_platform: Optional[str] = Query(
        None, description="Filter by source platform (e.g. youtube, audio, web)"
    ),
    current_user: AuthUser = Depends(get_current_user),
) -> SearchResponse:
    """
    Search through the authenticated user's indexed transcripts.

    Performs a full-text lexical search with typo tolerance and relevance ranking.
    Results are filtered to only include the current user's content (tenant
    isolation via user_id filter on the shared index).
    Results are deduplicated by media item (one hit per document even if multiple
    chunks match).

    Returns ranked results with highlighted matching snippets.
    """
    try:
        result = search_indexing.search_transcripts(
            user_id=current_user.id,
            query=q,
            page=page,
            per_page=per_page,
            filter_by_platform=source_platform,
        )

        # What each hit *looks* like comes from the library row, not from the
        # index: the index is a search index, and a cover denormalised into it
        # would be missing on everything indexed earlier and stale on every
        # cover replaced later. Reading the row is what makes a search result
        # and a library row show the same picture by construction.
        raw_hits = result.get("hits", [])
        details = await load_display_details(
            current_user.id,
            [hit["media_item_id"] for hit in raw_hits if hit.get("media_item_id")],
        )

        # Transform Algolia response into our API response model
        hits = []
        for hit_data in raw_hits:
            # Build highlight snippets
            highlights = []
            for hl in hit_data.get("highlights", []):
                snippet = hl.get("snippet", "")
                if snippet:
                    highlights.append(
                        SearchHitHighlight(
                            field=hl.get("field", ""),
                            snippet=snippet,
                        )
                    )

            # The row wins on everything it carries; the index is the fallback
            # for an item whose library row is gone, which stays findable today
            # because deleting a media does not unindex it.
            detail = details.get(hit_data.get("media_item_id", ""), {})
            created_at = detail.get("created_at") or _iso_from_index_timestamp(
                hit_data.get("created_at")
            )

            hits.append(
                SearchHit(
                    media_item_id=hit_data.get("media_item_id", ""),
                    title=detail.get("title") or hit_data.get("title") or None,
                    creator_name=detail.get("creator_name") or None,
                    source_platform=hit_data.get("source_platform") or None,
                    media_type=detail.get("media_type") or None,
                    media_image=detail.get("media_image") or None,
                    source_url=detail.get("source_url") or None,
                    folder_id=detail.get("folder_id") or None,
                    created_at=created_at,
                    # An orphan hit has no write history to expose; its cover is
                    # null anyway, so there is no cache key to keep fresh.
                    updated_at=detail.get("updated_at") or created_at,
                    in_library=bool(detail),
                    text_match_score=hit_data.get("text_match_score", 0),
                    highlights=highlights,
                )
            )

        return SearchResponse(
            query=q,
            found=result.get("found", 0),
            page=page,
            per_page=per_page,
            hits=hits,
        )

    except RuntimeError as e:
        # Algolia not configured
        logger.error(f"Search service unavailable: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )
    except Exception as e:
        logger.error(
            f"Search failed for user {current_user.id}, query='{q}': {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed",
        )
