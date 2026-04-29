"""
RSS Feed subscription API endpoints.

Provides operations on user RSS feed subscriptions:
- Subscribe to a new feed
- List subscribed feeds
- Pause/resume a feed
- Unsubscribe from a feed
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.services.rss_feed_service import (
    FeedServiceError,
    FeedServiceException,
    list_feeds,
    parse_feed,
    pause_feed,
    resume_feed,
    subscribe,
    unsubscribe,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- Request / Response models ----------


class SubscribeFeedRequest(BaseModel):
    url: str = Field(..., min_length=1, description="URL of the RSS/Atom feed")


class FeedItemPreview(BaseModel):
    guid: str
    title: str
    link: Optional[str] = None
    item_type: str  # "audio" or "article"
    published: Optional[str] = None


class SubscribeFeedResponse(BaseModel):
    id: str
    feed_url: str
    feed_title: Optional[str] = None
    status: str
    items_detected: int
    items: List[FeedItemPreview] = Field(
        default_factory=list,
        description="Preview of the detected feed items (up to 20 most recent)",
    )


class FeedResponse(BaseModel):
    id: str
    feed_url: str
    feed_title: Optional[str] = None
    status: str
    last_polled_at: Optional[str] = None
    last_error: Optional[str] = None
    items_ingested: int
    created_at: str
    updated_at: str


class FeedListResponse(BaseModel):
    status: str = "success"
    feeds: List[FeedResponse]
    count: int


class FeedDeleteResponse(BaseModel):
    status: str = "success"
    feed_id: str


class FeedPatchRequest(BaseModel):
    action: str = Field(
        ..., description="Action to perform: 'pause' or 'resume'"
    )


class FeedPatchResponse(BaseModel):
    status: str = "success"
    feed_id: str
    feed_status: str


# ---------- Error mapping ----------


_ERROR_STATUS_MAP = {
    FeedServiceError.FEED_NOT_FOUND: status.HTTP_404_NOT_FOUND,
    FeedServiceError.FEED_ACCESS_DENIED: status.HTTP_403_FORBIDDEN,
    FeedServiceError.FEED_PARSE_ERROR: status.HTTP_422_UNPROCESSABLE_ENTITY,
    FeedServiceError.FEED_ALREADY_SUBSCRIBED: status.HTTP_409_CONFLICT,
    FeedServiceError.FEED_INVALID_URL: status.HTTP_400_BAD_REQUEST,
}


def _raise_service_error(exc: FeedServiceException) -> None:
    """Convert a FeedServiceException to an HTTPException."""
    http_status = _ERROR_STATUS_MAP.get(exc.code, status.HTTP_500_INTERNAL_SERVER_ERROR)
    raise HTTPException(status_code=http_status, detail=exc.message)


# ---------- Endpoints ----------


@router.post("", response_model=SubscribeFeedResponse, status_code=status.HTTP_201_CREATED)
async def subscribe_to_feed(
    payload: SubscribeFeedRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> SubscribeFeedResponse:
    """Subscribe to an RSS/Atom feed.

    Validates the URL, parses the feed, and creates the subscription.
    Returns a preview of detected items.
    """
    try:
        feed = await subscribe(
            user_id=current_user.id,
            feed_url=payload.url,
        )

        # Parse the feed again to get items preview
        try:
            feed_data = parse_feed(payload.url)
            items_preview = [
                FeedItemPreview(
                    guid=item["guid"],
                    title=item["title"],
                    link=item.get("link"),
                    item_type=item["item_type"],
                    published=item.get("published"),
                )
                for item in feed_data["items"][:20]
            ]
            items_count = len(feed_data["items"])
        except Exception:
            items_preview = []
            items_count = 0

        return SubscribeFeedResponse(
            id=feed.id,
            feed_url=feed.feed_url,
            feed_title=feed.feed_title,
            status=feed.status.value,
            items_detected=items_count,
            items=items_preview,
        )
    except FeedServiceException as e:
        _raise_service_error(e)
    except Exception as e:
        logger.error("Error subscribing to feed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to subscribe to feed",
        )


@router.get("", response_model=FeedListResponse)
async def list_user_feeds(
    current_user: AuthUser = Depends(get_current_user),
) -> FeedListResponse:
    """List all RSS feed subscriptions for the authenticated user."""
    try:
        feeds = await list_feeds(user_id=current_user.id)
        items = [FeedResponse(**f) for f in feeds]
        return FeedListResponse(
            status="success",
            feeds=items,
            count=len(items),
        )
    except Exception as e:
        logger.error("Error listing feeds: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list feeds",
        )


@router.patch("/{feed_id}", response_model=FeedPatchResponse)
async def patch_feed(
    feed_id: str,
    payload: FeedPatchRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> FeedPatchResponse:
    """Pause or resume an RSS feed subscription."""
    try:
        if payload.action == "pause":
            feed = await pause_feed(user_id=current_user.id, feed_id=feed_id)
        elif payload.action == "resume":
            feed = await resume_feed(user_id=current_user.id, feed_id=feed_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid action: {payload.action}. Must be 'pause' or 'resume'.",
            )
        return FeedPatchResponse(
            status="success",
            feed_id=feed.id,
            feed_status=feed.status.value,
        )
    except FeedServiceException as e:
        _raise_service_error(e)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error patching feed %s: %s", feed_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update feed",
        )


@router.delete("/{feed_id}", response_model=FeedDeleteResponse)
async def delete_feed(
    feed_id: str,
    current_user: AuthUser = Depends(get_current_user),
) -> FeedDeleteResponse:
    """Unsubscribe from an RSS feed."""
    try:
        await unsubscribe(user_id=current_user.id, feed_id=feed_id)
        return FeedDeleteResponse(
            status="success",
            feed_id=feed_id,
        )
    except FeedServiceException as e:
        _raise_service_error(e)
    except Exception as e:
        logger.error("Error deleting feed %s: %s", feed_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete feed",
        )
