"""
Service: Spotify Playlist Sync (Generic)

Fetch listened episodes from any Spotify playlist, resolve via PodcastIndex,
then submit for processing. Based on tosum_sync.py but generalized.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from media_summarizer.core.services.episode_submission import (
    submit_episode_for_user,
)
from media_summarizer.utils import podcast_index
from media_summarizer.utils.spotify import (
    compute_listen_percent,
    ensure_access_token,
    extract_spotify_episode_metadata,
    get_episodes_details_map,
    list_playlist_episode_items,
)
from media_summarizer.utils.user_episode_submissions import (
    has_user_already_submitted,
    mark_user_submission,
)

logger = logging.getLogger(__name__)

SPOTIFY_SYNC_MAX = int(os.environ.get("SPOTIFY_SYNC_MAX", "5"))
SPOTIFY_LISTEN_THRESHOLD_PERCENT = float(
    os.environ.get("SPOTIFY_LISTEN_THRESHOLD_PERCENT", "80")
)


def _normalize(s: str) -> str:
    import re
    import unicodedata

    s = (s or "").lower()
    # Normalize Unicode characters (NFD = decompose accents)
    s = unicodedata.normalize("NFD", s)
    # Remove combining characters (accents)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    # Normalize back to NFC
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"[\W_]+", " ", s)  # remove punctuation
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _best_match_episode(
    episodes: List[Dict[str, Any]],
    target_title: str,
) -> Dict[str, Any] | None:
    """
    Naive matching, in order:
    - strict equals on normalized title
    - substring match (either way)
    - token overlap (Jaccard)
    """
    t_norm = _normalize(target_title)
    # Strict equality
    for e in episodes:
        if _normalize(e.get("title", "")) == t_norm:
            return e
    # Substring either way
    for e in episodes:
        e_norm = _normalize(e.get("title", ""))
        if t_norm in e_norm or e_norm in t_norm:
            return e
    # Token overlap (Jaccard)
    t_tokens = set(t_norm.split())
    best = None
    best_score = 0.0
    top_candidates = []  # Track top 3 candidates for debugging
    for e in episodes:
        e_tokens = set(_normalize(e.get("title", "")).split())
        if not e_tokens or not t_tokens:
            continue
        inter = len(t_tokens & e_tokens)
        union = len(t_tokens | e_tokens)
        score = inter / union if union else 0.0
        if score > best_score:
            best_score = score
            best = e
        # Track top candidates
        if len(top_candidates) < 3:
            top_candidates.append((score, e.get("title", "Unknown")))
            top_candidates.sort(reverse=True, key=lambda x: x[0])
        elif score > top_candidates[-1][0]:
            top_candidates[-1] = (score, e.get("title", "Unknown"))
            top_candidates.sort(reverse=True, key=lambda x: x[0])

    if best_score >= 0.6:
        return best

    # Log debug info when no match found
    logger.debug(
        f"No match found for '{target_title}' (normalized: '{t_norm}'). "
        f"Best score: {best_score:.3f}. Top candidates: "
        f"{', '.join([f'{title} ({score:.3f})' for score, title in top_candidates[:3]])}"
    )
    return None


async def run_playlist_sync_for_user(user, playlist_id: str) -> Dict[str, Any]:
    """
    Sync a specific Spotify playlist for a user.
    
    Args:
        user: User object with Spotify tokens
        playlist_id: Spotify playlist ID to sync
    
    Returns:
        Dict with status, counts, and results
    """
    # Ensure Spotify linked
    if not getattr(user, "spotify_refresh_token", None):
        return {"status": "error", "reason": "spotify_not_linked"}

    # Ensure fresh token
    access_token = await ensure_access_token(user)

    # Collect episode items from playlist
    items = await list_playlist_episode_items(access_token, playlist_id)

    # Enrich with user-specific resume_point via /episodes?ids=...
    ids = [ep.get("id") for ep in items if ep.get("id")]
    details_map = await get_episodes_details_map(access_token, ids)

    scanned = 0
    eligible = 0
    submitted = 0
    results: List[Dict[str, Any]] = []
    skipped_below = 0
    skipped_missing = 0
    skipped_not_matched = 0
    skipped_already_submitted = 0
    skipped_insufficient_credits = 0
    
    for ep in items:
        if submitted >= SPOTIFY_SYNC_MAX:
            break
        scanned += 1
        # Merge resume_point from /episodes if missing/null on playlist item
        ep_id = ep.get("id")
        if (not ep.get("resume_point")) and ep_id and ep_id in details_map:
            det = details_map[ep_id]
            # det may contain 'resume_point' with fully_played/resume_position_ms
            rp = det.get("resume_point") or {}
            if rp:
                # If fully_played and no resume_position_ms given, treat as 100%
                if (
                    rp.get("fully_played")
                    and not rp.get("resume_position_ms")
                    and ep.get("duration_ms")
                ):
                    rp = dict(rp)
                    rp["resume_position_ms"] = ep.get("duration_ms")
                ep = dict(ep)
                ep["resume_point"] = rp

        percent = compute_listen_percent(ep)
        if percent is None:
            skipped_missing += 1
            continue
        if percent < SPOTIFY_LISTEN_THRESHOLD_PERCENT:
            skipped_below += 1
            continue

        eligible += 1
        ep_title, show_title, duration_sec = extract_spotify_episode_metadata(ep)
        # Fallback show title from /episodes details if missing
        if (not show_title) and ep_id and ep_id in details_map:
            show_title = (details_map[ep_id].get("show") or {}).get(
                "name"
            ) or show_title
        # Resolve show -> feed via search
        try:
            search = await podcast_index.search_podcasts(
                query=show_title or ep_title,
                max_results=5,
            )
            feeds = search.get("feeds", [])
            if not feeds:
                logger.warning(
                    f"No feeds found for query: '{show_title or ep_title}' (episode: {ep_title})"
                )
                skipped_not_matched += 1
                continue
            feed = feeds[0]
            feed_id = feed.get("id")
            if not feed_id:
                logger.warning(f"Feed has no ID for query: '{show_title or ep_title}'")
                skipped_not_matched += 1
                continue
            eps = await podcast_index.get_episodes_by_feed_id(
                feed_id=feed_id,
                max_results=250,
            )
            ep_items = eps.get("items", [])
            match = _best_match_episode(ep_items, ep_title)
            if not match:
                logger.warning(
                    f"No match found for episode '{ep_title}' in {len(ep_items)} episodes "
                    f"from feed '{feed.get('title', 'Unknown')}' (feed_id={feed_id}). "
                    f"Check DEBUG logs for matching details."
                )
                skipped_not_matched += 1
                continue

            guid = match.get("guid")
            audio_url = match.get("enclosureUrl")
            feed_title = match.get("feedTitle") or show_title
            if not guid or not audio_url:
                skipped_missing += 1
                continue

            # User-level deduplication: skip if this user already submitted this episode
            if await has_user_already_submitted(user.id, guid):
                skipped_already_submitted += 1
                continue

            # Submit using shared service (idempotence + watchers inside)
            # Use episode image if available, otherwise fallback to feed image
            episode_image_url = (
                match.get("image") or match.get("feedImage") or feed.get("image", "")
            )
            logger.info(f"Submitting episode {guid} with image: {episode_image_url}")
            res = await submit_episode_for_user(
                user=user,
                episode_guid=guid,
                episode_title=match.get("title") or ep_title,
                feed_title=feed_title,
                audio_url=audio_url,
                duration_seconds=duration_sec or (match.get("duration") or 0),
                episode_image=episode_image_url,
                source="spotify",
            )
            
            if res.get("status") == "skipped":
                reason = res.get("reason", "unknown")
                if reason == "insufficient_credits":
                    logger.warning(f"Skipping episode {guid} due to insufficient credits.")
                    skipped_insufficient_credits += 1
                else:
                    logger.info(f"Skipping episode {guid}: {reason}")
                    skipped_already_submitted += 1
                continue
                
            submitted += 1
            results.append(res)

            # Mark user submission to avoid future duplicates from playlist scans
            try:
                await mark_user_submission(
                    user_id=user.id,
                    episode_guid=guid,
                    job_id=res.get("job_id", ""),
                    source="spotify",
                )
            except Exception:
                # Non-fatal; future scans may retry; global GUID idempotence protects
                pass
        except Exception as e:
            logger.warning(f"Failed syncing episode '{ep_title}' from show '{show_title}': {e}", exc_info=True)
            # Treat as not matched/missing without raising
            skipped_not_matched += 1

    out = {
        "status": "success",
        "playlist_id": playlist_id,
        "scanned": scanned,
        "eligible": eligible,
        "submitted": submitted,
        "skipped": {
            "below_threshold": skipped_below,
            "missing_data": skipped_missing,
            "not_matched": skipped_not_matched,
            "already_submitted": skipped_already_submitted,
            "insufficient_credits": skipped_insufficient_credits,
        },
        "results": results,
    }
    return out
