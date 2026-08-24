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
from typing import List, Optional

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
    """A single search result."""

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
    created_at: int = Field(..., description="Creation timestamp (Unix)")
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

            hits.append(
                SearchHit(
                    media_item_id=hit_data.get("media_item_id", ""),
                    title=detail.get("title") or hit_data.get("title") or None,
                    creator_name=detail.get("creator_name") or None,
                    source_platform=hit_data.get("source_platform") or None,
                    media_type=detail.get("media_type") or None,
                    media_image=detail.get("media_image") or None,
                    created_at=hit_data.get("created_at", 0),
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
