"""
Spotify utilities: token refresh and simple data access for Tosum sync.
"""
from __future__ import annotations

import os
import base64
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx

from media_summarizer.utils import database_async

logger = logging.getLogger(__name__)

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")

SPOTIFY_API_BASE = "https://api.spotify.com/v1"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"

HTTP_TIMEOUT = httpx.Timeout(20.0)


def _basic_auth_header() -> Dict[str, str]:
    if not (SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET):
        raise RuntimeError("Spotify OAuth not configured")
    basic = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode("utf-8")
    ).decode("utf-8")
    return {"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"}


async def ensure_access_token(user) -> str:
    """
    Ensure a valid Spotify access token for the given user, refreshing if needed.
    Updates the user in DB on refresh.
    """
    if not getattr(user, "spotify_refresh_token", None):
        raise RuntimeError("User is not linked with Spotify")

    # Renew if missing or expiring within 60s
    now = datetime.now(timezone.utc)
    if getattr(user, "spotify_access_token", None) and getattr(user, "spotify_token_expires_at", None):
        if user.spotify_token_expires_at > now + timedelta(seconds=60):
            return user.spotify_access_token

    # Refresh
    headers = _basic_auth_header()
    data = {
        "grant_type": "refresh_token",
        "refresh_token": user.spotify_refresh_token,
    }
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        resp = await client.post(SPOTIFY_TOKEN_URL, headers=headers, data=data)
        resp.raise_for_status()
        td = resp.json()
        access_token = td.get("access_token")
        expires_in = int(td.get("expires_in") or 3600)
        if not access_token:
            raise RuntimeError("Failed to refresh Spotify access token")
        user.spotify_access_token = access_token
        user.spotify_token_expires_at = now + timedelta(seconds=expires_in)
        # Some refresh flows return a new refresh_token; persist if present
        if td.get("refresh_token"):
            user.spotify_refresh_token = td["refresh_token"]
        await database_async.update_user(user)
        return access_token


async def list_user_playlists(access_token: str, *, limit: int = 50, max_pages: int = 5) -> List[Dict[str, Any]]:
    playlists: List[Dict[str, Any]] = []
    url = f"{SPOTIFY_API_BASE}/me/playlists"
    params = {"limit": min(limit, 50)}
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        pages = 0
        while url and pages < max_pages:
            r = await client.get(url, headers=headers, params=params)
            r.raise_for_status()
            data = r.json()
            items = data.get("items", [])
            playlists.extend(items)
            url = data.get("next")  # absolute URL or None
            params = None  # next already includes params
            pages += 1
    return playlists


async def find_playlist_by_name(access_token: str, name: str) -> Optional[Dict[str, Any]]:
    name_norm = name.strip().lower()
    pls = await list_user_playlists(access_token)
    for p in pls:
        if p.get("name", "").strip().lower() == name_norm:
            return p
    return None


async def list_playlist_episode_items(access_token: str, playlist_id: str, *, limit: int = 100, max_pages: int = 10) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    url = f"{SPOTIFY_API_BASE}/playlists/{playlist_id}/tracks"
    params = {"limit": min(limit, 100)}
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        pages = 0
        while url and pages < max_pages:
            r = await client.get(url, headers=headers, params=params)
            r.raise_for_status()
            data = r.json()
            for it in data.get("items", []):
                track = it.get("track") or {}
                if track and track.get("type") == "episode":
                    items.append(track)
            url = data.get("next")
            params = None
            pages += 1
    return items


def compute_listen_percent(episode_track: Dict[str, Any]) -> Optional[float]:
    rp = episode_track.get("resume_point") or {}
    duration_ms = episode_track.get("duration_ms")
    pos_ms = rp.get("resume_position_ms")
    if isinstance(duration_ms, (int, float)) and isinstance(pos_ms, (int, float)) and duration_ms > 0:
        return (pos_ms / duration_ms) * 100.0
    return None


def extract_spotify_episode_metadata(episode_track: Dict[str, Any]) -> Tuple[str, str, Optional[int]]:
    """
    Returns (episode_title, show_title, duration_seconds)
    """
    ep_title = episode_track.get("name", "")
    show = episode_track.get("show") or {}
    show_title = show.get("name", "")
    dur_ms = episode_track.get("duration_ms")
    dur_sec = int(dur_ms / 1000) if isinstance(dur_ms, (int, float)) else None
    return ep_title, show_title, dur_sec


async def get_episodes_details_map(access_token: str, episode_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Fetch episode details (including resume_point) for given IDs in chunks.
    Returns mapping id -> episode dict (or subset with resume_point).
    """
    result: Dict[str, Dict[str, Any]] = {}
    if not episode_ids:
        return result
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        # Spotify allows up to 50 ids per request
        chunk: List[str] = []
        for eid in episode_ids:
            if eid and eid not in result:
                chunk.append(eid)
            if len(chunk) == 50:
                r = await client.get(f"{SPOTIFY_API_BASE}/episodes", headers=headers, params={"ids": ",".join(chunk)})
                r.raise_for_status()
                for e in r.json().get("episodes", []) or []:
                    if e and e.get("id"):
                        result[e["id"]] = e
                chunk = []
        if chunk:
            r = await client.get(f"{SPOTIFY_API_BASE}/episodes", headers=headers, params={"ids": ",".join(chunk)})
            r.raise_for_status()
            for e in r.json().get("episodes", []) or []:
                if e and e.get("id"):
                    result[e["id"]] = e
    return result
