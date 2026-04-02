"""
Legacy adapter for GUID-based callers.

Canonical runtime is media-key only. This adapter remains as a thin
deterministic GUID -> media_key mapper for any residual imports.
"""
from __future__ import annotations

from media_summarizer.utils.user_media_submissions import (
    has_user_already_submitted_media,
    mark_user_media_submission,
)

LEGACY_EPISODE_MEDIA_KEY_PREFIX = "episode_guid:"


def media_key_from_episode_guid(episode_guid: str) -> str:
    return f"{LEGACY_EPISODE_MEDIA_KEY_PREFIX}{episode_guid}"


async def has_user_already_submitted(user_id: str, episode_guid: str) -> bool:
    """
    Legacy compatibility API.

    Uses deterministic media_key derivation from episode_guid.
    """
    return await has_user_already_submitted_media(
        user_id=user_id,
        media_key=media_key_from_episode_guid(episode_guid),
    )


async def mark_user_submission(
    *, user_id: str, episode_guid: str, job_id: str, source: str
) -> bool:
    """
    Legacy compatibility API.

    Records submissions in canonical media-keyed table only.
    """
    return await mark_user_media_submission(
        user_id=user_id,
        media_key=media_key_from_episode_guid(episode_guid),
        job_id=job_id,
        source=source,
    )
