"""
Episode submission service -- thin wrapper around media_submission.submit_media_for_user
that maps episode-specific parameters (episode_guid, feed_title, etc.) to the
generic media submission interface.

Also responsible for passing the RSS feed URL so the download worker can
attempt Podcasting 2.0 transcript retrieval before audio download.
"""

from __future__ import annotations

from typing import Any, Dict

from media_summarizer.core.services.media_submission import submit_media_for_user


async def submit_episode_for_user(
    *,
    user: Any,
    episode_guid: str,
    episode_title: str,
    feed_title: str,
    audio_url: str,
    duration_seconds: int,
    episode_image: str = "",
    episode_date_published: int = 0,
    feed_url: str = "",
    source: str = "manual",
    folder_id: str | None = None,
) -> Dict[str, Any]:
    """
    Submit a podcast episode for processing.

    Delegates to the generic submit_media_for_user service with episode-specific
    field mapping. The media_key is set to the episode GUID for global idempotence.

    Args:
        user: Authenticated user object (must have .id and .email).
        episode_guid: Unique episode GUID (used as media_key).
        episode_title: Human-readable episode title.
        feed_title: Podcast/feed title.
        audio_url: Direct URL to the audio enclosure.
        duration_seconds: Episode duration in seconds (0 if unknown).
        episode_image: Episode artwork URL.
        episode_date_published: Unix timestamp of episode publication date.
        feed_url: RSS feed URL for Podcasting 2.0 transcript lookup.
        source: Submission source identifier.
        folder_id: Optional folder to assign the media to.

    Returns:
        Dict compatible with EpisodeSelectionResponse.
    """
    result = await submit_media_for_user(
        user=user,
        media_key=episode_guid,
        media_title=episode_title,
        source_title=feed_title,
        audio_url=audio_url,
        duration_seconds=duration_seconds,
        media_image=episode_image,
        media_date_published=episode_date_published,
        source=source,
        folder_id=folder_id,
        feed_url=feed_url,
    )

    # Ensure backward-compatible keys expected by EpisodeSelectionResponse
    if "episode_title" not in result:
        result["episode_title"] = episode_title
    if "podcast_title" not in result:
        result["podcast_title"] = feed_title

    return result
