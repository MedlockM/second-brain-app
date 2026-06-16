"""
Search API endpoints for transcript search and Algolia credentials.

Provides:
- Full-text search over indexed media transcripts (backend-proxied via Algolia)
- Secured API key generation for direct client-side Algolia search

Multi-tenant isolation: the shared index stores all users' records with a
``user_id`` attribute. Isolation is enforced via:
- Backend-proxied search: explicit user_id filter in the query
- Direct client search: secured API key with embedded user_id filter
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.services import search_indexing
from media_summarizer.utils.algolia_client import generate_secured_search_key

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
    source_platform: Optional[str] = Field(None, description="Source platform")
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


class SearchCredentialsResponse(BaseModel):
    """Response model for Algolia search credentials (secured API key)."""

    app_id: str = Field(..., description="Algolia Application ID")
    secured_key: str = Field(
        ..., description="Secured API key (embeds user_id filter, short-lived)"
    )
    index_name: str = Field(..., description="Shared index name to search")
    valid_until: int = Field(
        ..., description="Unix timestamp when the secured key expires"
    )


# ---------- Endpoints ----------


@router.get("/credentials", response_model=SearchCredentialsResponse)
async def get_search_credentials(
    current_user: AuthUser = Depends(get_current_user),
) -> SearchCredentialsResponse:
    """
    Generate a secured Algolia API key for direct client-side search.

    The returned key embeds a tamper-proof ``user_id`` filter, restricting
    search results to only the authenticated user's records. The key is
    short-lived (1 hour) and must be refreshed by the client before expiry
    or on 403 from Algolia.

    The parent search-only key never leaves the backend.
    """
    try:
        credentials = generate_secured_search_key(user_id=current_user.id)
        return SearchCredentialsResponse(
            app_id=credentials["app_id"],
            secured_key=credentials["secured_key"],
            index_name=credentials["index_name"],
            valid_until=credentials["valid_until"],
        )
    except RuntimeError as e:
        logger.error(f"Search credentials unavailable: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search service is not configured",
        )
    except ValueError as e:
        logger.error(f"Invalid request for search credentials: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


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

        # Transform Algolia response into our API response model
        hits = []
        for hit_data in result.get("hits", []):
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

            hits.append(
                SearchHit(
                    media_item_id=hit_data.get("media_item_id", ""),
                    title=hit_data.get("title") or None,
                    source_platform=hit_data.get("source_platform") or None,
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
