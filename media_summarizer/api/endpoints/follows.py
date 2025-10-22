"""
Endpoints to manage follows and per-feed forecast persistence.

Routes:
- POST   /api/v1/follows         { feed_id: int }  -> creates/updates follow with forecast
- GET    /api/v1/follows                              -> list follows for current user
- DELETE /api/v1/follows         { feed_id: int }  -> delete follow
"""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import require_verified_email
from media_summarizer.core.models.billing import Follow
from media_summarizer.utils import minute_db
from media_summarizer.core.services.forecast_service import get_forecast_with_cache

router = APIRouter()
logger = logging.getLogger(__name__)


class FollowCreateRequest(BaseModel):
    feed_id: int = Field(..., description="Podcast Index feed ID")


class FollowDeleteRequest(BaseModel):
    feed_id: int = Field(..., description="Podcast Index feed ID")


class FollowResponse(BaseModel):
    user_id: str
    feed_id: str
    forecast_minutes: int
    reserved_minutes: int


@router.get("/follows", response_model=List[FollowResponse])
async def list_follows(current_user=Depends(require_verified_email)):
    try:
        follows = await minute_db.get_follows_by_user_id(current_user.id)
        return [
            FollowResponse(
                user_id=f.user_id,
                feed_id=f.feed_id,
                forecast_minutes=int(f.forecast_minutes or 0),
                reserved_minutes=int(f.reserved_minutes or 0),
            )
            for f in follows
        ]
    except Exception as e:
        logger.error(f"Failed to list follows for user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list follows")


@router.post("/follows", response_model=FollowResponse)
async def create_or_update_follow(payload: FollowCreateRequest, current_user=Depends(require_verified_email)):
    try:
        # Retrieve forecast via shared cache (compute if ever missing; in practice profile page computed it already)
        fc = await get_forecast_with_cache(feed_id=payload.feed_id)
        minutes = int(fc.get("minutes_per_month", 0))

        follow = Follow(
            user_id=current_user.id,
            feed_id=str(payload.feed_id),  # stored as string in DynamoDB model
            forecast_minutes=minutes,
            reserved_minutes=minutes,  # soft reservation equals latest known forecast
        )
        await minute_db.upsert_follow(follow)
        return FollowResponse(
            user_id=follow.user_id,
            feed_id=follow.feed_id,
            forecast_minutes=follow.forecast_minutes,
            reserved_minutes=follow.reserved_minutes,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create/update follow for user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to follow podcast")


@router.delete("/follows")
async def delete_follow(payload: FollowDeleteRequest, current_user=Depends(require_verified_email)):
    try:
        ok = await minute_db.delete_follow(user_id=current_user.id, feed_id=str(payload.feed_id))
        if not ok:
            # still return 200 to keep idempotent behavior
            return {"status": "ok"}
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Failed to delete follow for user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete follow")
