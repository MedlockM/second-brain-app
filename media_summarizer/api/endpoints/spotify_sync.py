"""
Spotify Tosum Sync API endpoint
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from media_summarizer.api.dependencies.auth import require_verified_email
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.utils import database_async
from media_summarizer.core.services.tosum_sync import run_tosum_sync_for_user

router = APIRouter()


@router.post("/spotify/sync-tosum")
async def spotify_sync_tosum(current_user: AuthUser = Depends(require_verified_email)):
    user = await database_async.get_user_by_id(current_user.id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    result = await run_tosum_sync_for_user(user)
    if result.get("status") == "error":
        # Return 200 with error payload since this is an internal trigger endpoint per plan
        return result
    return result
