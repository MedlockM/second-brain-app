"""Engagement routes: what the user last worked on (task-303).

    POST /api/engagements          -> 204, records one engagement
    GET  /api/engagements/recent   -> 200, the "Continue learning" row

Two deliberate shapes, both settled by the benchmark:

* **An explicit ``POST``, never a ``GET`` side effect.** Stamping inside
  ``GET /api/artifacts/{id}/content`` would need no new endpoint and no client
  change, and it is rejected: ``GET`` is a safe method, the mobile client replays a
  ``GET`` once after refreshing a 401, and ``expo-router`` can *render* a screen the
  user never opened (``router.prefetch``), which would silently record engagements
  for artifacts nobody read. The two artifact ``GET`` routes stay side-effect-free.
* **One dedicated read endpoint, not an aggregate ``/api/home``.** Bundling the
  digest, "Recently added" and this row into one response couples three independent
  sections into one failure domain, behind the slowest of the three.
"""

from __future__ import annotations

import logging
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.services import engagement_service
from media_summarizer.core.services.engagement_service import (
    DEFAULT_RECENT_LIMIT,
    MAX_RECENT_LIMIT,
    EngagementSubjectNotFoundError,
)
from media_summarizer.utils.logging_config import bind_log_context, log_event, reset_log_context

router = APIRouter()
logger = logging.getLogger(__name__)


class EngagementCreateRequest(BaseModel):
    kind: Literal["media", "collection"] = Field(
        ..., description="What was engaged with: a media item or a collection"
    )
    id: str = Field(..., description="Media item id, or collection (folder) id")


class RecentEngagementResponse(BaseModel):
    """One tile of the row. The fields a media tile draws and the fields a
    collection tile draws are both optional, and which ones are populated follows
    from ``kind``."""

    kind: str
    id: str
    title: Optional[str] = None
    engaged_at: str
    creator_name: Optional[str] = None
    image_url: Optional[str] = None
    media_type: Optional[str] = None
    item_count: Optional[int] = None
    preview_images: List[str] = Field(default_factory=list)


class RecentEngagementListResponse(BaseModel):
    status: str = "success"
    items: List[RecentEngagementResponse]


@router.post("/engagements", status_code=status.HTTP_204_NO_CONTENT)
async def create_engagement(
    payload: EngagementCreateRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> Response:
    """Record that the user just opened and read one artifact.

    Answers ``204`` even when the underlying write is refused or fails: a 4xx here is
    reserved for a subject that is not the caller's. The client fires this without
    awaiting it, so nothing about the artifact it is reading can depend on the answer.
    """
    token = bind_log_context(user_id=current_user.id, kind=payload.kind, subject_id=payload.id)
    try:
        await engagement_service.record_engagement(
            user_id=current_user.id,
            kind=payload.kind,
            subject_id=payload.id,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except EngagementSubjectNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    finally:
        reset_log_context(token)


@router.get("/engagements/recent", response_model=RecentEngagementListResponse)
async def list_recent_engagements(
    limit: int = Query(DEFAULT_RECENT_LIMIT, ge=1, le=MAX_RECENT_LIMIT),
    current_user: AuthUser = Depends(get_current_user),
) -> RecentEngagementListResponse:
    """The "Continue learning" row: media and collections merged, newest first.

    An empty list is a normal answer, not a degraded one — a brand-new account has
    engaged with nothing, and a row whose entries all aged out of the freshness
    window empties itself. The client hides the section.
    """
    token = bind_log_context(user_id=current_user.id)
    try:
        entries = await engagement_service.list_recent(current_user.id, limit=limit)
        log_event(
            logger,
            logging.INFO,
            "engagement.recent.succeeded",
            "Recent engagements retrieved",
            item_count=len(entries),
        )
        return RecentEngagementListResponse(
            status="success",
            items=[
                RecentEngagementResponse(
                    kind=entry.kind,
                    id=entry.id,
                    title=entry.title,
                    engaged_at=entry.engaged_at.isoformat(),
                    creator_name=entry.creator_name,
                    image_url=entry.image_url,
                    media_type=entry.media_type,
                    item_count=entry.item_count,
                    preview_images=list(entry.preview_images),
                )
                for entry in entries
            ],
        )
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "engagement.recent.failed",
            "Failed to retrieve recent engagements",
            error_type=type(exc).__name__,
            error_code="ENGAGEMENT_RECENT_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve recent engagements",
        )
    finally:
        reset_log_context(token)
