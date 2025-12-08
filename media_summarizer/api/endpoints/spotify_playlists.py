"""
Spotify Playlists Manager API endpoints
"""
from __future__ import annotations

import logging
from typing import List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from media_summarizer.api.dependencies.auth import RequireAuth
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.models.spotify import SpotifyPlaylistFollow
from media_summarizer.utils import database_async, spotify_follows_db
from media_summarizer.utils.spotify import ensure_access_token, list_user_playlists
from media_summarizer.core.services.playlist_sync import run_playlist_sync_for_user

router = APIRouter()
logger = logging.getLogger(__name__)


class PlaylistResponse(BaseModel):
    """Playlist info merged with follow state"""
    id: str
    name: str
    images: List[dict]
    tracks_total: int
    owner_name: str
    collaborative: bool
    public: Optional[bool]
    enabled: bool = False  # Follow/tracking state


class SubscriptionRequest(BaseModel):
    """Request to update playlist follow state"""
    enabled: bool


class SubscriptionResponse(BaseModel):
    """Follow state"""
    playlist_id: str
    enabled: bool
    last_synced_at: Optional[str] = None


class SyncResponse(BaseModel):
    """Sync operation result"""
    status: str
    playlist_id: str
    scanned: int
    eligible: int
    submitted: int
    skipped: dict


@router.get("/spotify/playlists", response_model=List[PlaylistResponse])
async def list_playlists(current_user: AuthUser = RequireAuth):
    """
    List user's Spotify playlists (owner only) merged with follow state.
    """
    try:
        user = await database_async.get_user_by_id(current_user.id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        # Ensure Spotify token is fresh
        access_token = await ensure_access_token(user)
        
        # Fetch all playlists
        playlists = await list_user_playlists(access_token, limit=50, max_pages=5)
        
        # Filter: owner only
        owner_playlists = [
            pl for pl in playlists
            if pl.get("owner", {}).get("id") == getattr(user, "spotify_user_id", None)
        ]
        
        logger.info(f"Returning {len(owner_playlists)} owner playlists for user {current_user.id}")
        
        # Get follows
        follows = await spotify_follows_db.get_follows_by_user(current_user.id)
        follows_map = {f.playlist_id: f for f in follows}
        
        # Merge
        result = []
        for pl in owner_playlists:
            pl_id = pl.get("id", "")
            follow = follows_map.get(pl_id)
            result.append(PlaylistResponse(
                id=pl_id,
                name=pl.get("name", ""),
                images=pl.get("images", []),
                tracks_total=pl.get("tracks", {}).get("total", 0),
                owner_name=pl.get("owner", {}).get("display_name", ""),
                collaborative=pl.get("collaborative", False),
                public=pl.get("public"),
                enabled=follow.enabled if follow else False,
            ))
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list playlists for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list playlists"
        )


@router.get("/spotify/subscriptions", response_model=List[SubscriptionResponse])
async def get_subscriptions(current_user: AuthUser = RequireAuth):
    """
    Get all playlist follows/subscriptions for current user.
    """
    try:
        follows = await spotify_follows_db.get_follows_by_user(current_user.id)
        return [
            SubscriptionResponse(
                playlist_id=f.playlist_id,
                enabled=f.enabled,
                last_synced_at=f.last_synced_at.isoformat() if f.last_synced_at else None,
            )
            for f in follows
        ]
    except Exception as e:
        logger.error(f"Failed to get subscriptions for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get subscriptions"
        )


@router.put("/spotify/playlists/{playlist_id}/subscription", response_model=SubscriptionResponse)
async def update_subscription(
    playlist_id: str,
    payload: SubscriptionRequest,
    current_user: AuthUser = RequireAuth
):
    """
    Toggle playlist follow/tracking state.
    When enabled=True, the playlist will be synced on the next scheduled cron run.
    """
    try:
        user = await database_async.get_user_by_id(current_user.id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        # Get or create follow
        follow = await spotify_follows_db.get_follow(current_user.id, playlist_id)
        if not follow:
            follow = SpotifyPlaylistFollow(
                user_id=current_user.id,
                playlist_id=playlist_id,
                enabled=payload.enabled,
            )
        else:
            follow.enabled = payload.enabled
            follow.updated_at = datetime.now(timezone.utc)
        
        # Save follow state (will be picked up by next cron run)
        follow = await spotify_follows_db.upsert_follow(follow)
        
        logger.info(
            f"Playlist {playlist_id} tracking {'enabled' if payload.enabled else 'disabled'} "
            f"for user {current_user.id}. Will be synced on next scheduled run."
        )
        
        return SubscriptionResponse(
            playlist_id=follow.playlist_id,
            enabled=follow.enabled,
            last_synced_at=follow.last_synced_at.isoformat() if follow.last_synced_at else None,
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update subscription for playlist {playlist_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update subscription"
        )


@router.post("/spotify/playlists/{playlist_id}/sync", response_model=SyncResponse)
async def sync_playlist(playlist_id: str, current_user: AuthUser = RequireAuth):
    """
    Manually trigger sync for a specific playlist.
    """
    try:
        user = await database_async.get_user_by_id(current_user.id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        
        logger.info(f"Manual sync triggered for playlist {playlist_id} (user {current_user.id})")
        result = await run_playlist_sync_for_user(user, playlist_id)
        
        if result.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("reason", "Sync failed")
            )
        
        # Update last_synced_at if follow exists
        follow = await spotify_follows_db.get_follow(current_user.id, playlist_id)
        if follow:
            follow.last_synced_at = datetime.now(timezone.utc)
            await spotify_follows_db.upsert_follow(follow)
        
        return SyncResponse(
            status=result["status"],
            playlist_id=result["playlist_id"],
            scanned=result["scanned"],
            eligible=result["eligible"],
            submitted=result["submitted"],
            skipped=result["skipped"],
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to sync playlist {playlist_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync playlist"
        )
