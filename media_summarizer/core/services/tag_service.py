"""
Tag service: business logic for user tag management.

Handles creation, listing, renaming, deletion, and media-to-tag association.
Tags are private per user and manually created.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from media_summarizer.core.constants import DEFAULT_TAG_COLOR, MAX_TAGS_PER_MEDIA
from media_summarizer.core.models.tag import Tag
from media_summarizer.utils import database_async

logger = logging.getLogger(__name__)


async def create_tag(
    user_id: str, name: str, color: Optional[str] = None
) -> Tag:
    """Create a new tag for a user.

    Args:
        user_id: owner user ID
        name: tag display name
        color: optional hex color (defaults to DEFAULT_TAG_COLOR)
    """
    resolved_color = color if color is not None else DEFAULT_TAG_COLOR

    tag = Tag(
        user_id=user_id,
        name=name,
        color=resolved_color,
    )
    await database_async.create_tag(tag)
    logger.info(f"Created tag '{name}' ({tag.id}) for user {user_id}")
    return tag


async def list_tags(user_id: str) -> List[Dict[str, Any]]:
    """List all tags for a user, sorted alphabetically by name."""
    tags = await database_async.get_tags_by_user_id(user_id)

    result = []
    for t in tags:
        result.append({
            "id": t.id,
            "name": t.name,
            "color": t.color,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
        })

    result.sort(key=lambda x: x["name"].lower())
    return result


async def update_tag(
    user_id: str,
    tag_id: str,
    name: Optional[str] = None,
    color: Optional[str] = ...,  # type: ignore[assignment]  # sentinel
) -> Tag:
    """Update a tag (rename and/or recolor).

    Args:
        user_id: owner user ID
        tag_id: tag to update
        name: new name (if provided)
        color: new color (None = remove color, ... = no change)
    """
    tag = await database_async.get_tag_by_id(tag_id)
    if tag is None:
        raise ValueError(f"Tag {tag_id} not found")
    if tag.user_id != user_id:
        raise ValueError("Tag does not belong to this user")

    if name is not None:
        tag.name = name.strip()
    if color is not ...:
        tag.color = color

    tag.touch()
    await database_async.update_tag(tag)
    logger.info(f"Updated tag {tag_id} for user {user_id}")
    return tag


async def delete_tag(user_id: str, tag_id: str) -> Dict[str, Any]:
    """Delete a tag and dissociate it from all media items.

    Returns a summary of the operation.
    """
    tag = await database_async.get_tag_by_id(tag_id)
    if tag is None:
        raise ValueError(f"Tag {tag_id} not found")
    if tag.user_id != user_id:
        raise ValueError("Tag does not belong to this user")

    # Dissociate from all media items that have this tag
    jobs = await database_async.get_processing_jobs_by_user_id(user_id)
    dissociated_count = 0
    for job in jobs:
        if tag_id in getattr(job, "tag_ids", []):
            job.tag_ids = [tid for tid in job.tag_ids if tid != tag_id]
            job.touch()
            await database_async.update_processing_job(job)
            dissociated_count += 1

    # Delete the tag itself
    await database_async.delete_tag(tag_id)
    logger.info(
        f"Deleted tag {tag_id} for user {user_id}, "
        f"dissociated from {dissociated_count} media items"
    )
    return {
        "deleted_tag_id": tag_id,
        "dissociated_media_count": dissociated_count,
    }


async def set_media_tags(
    user_id: str, media_id: str, tag_ids: List[str]
) -> Dict[str, Any]:
    """Set the tags for a media item (replaces existing tags).

    Validates that:
    - The media item exists and belongs to the user
    - All tag IDs exist and belong to the user
    - The number of tags does not exceed MAX_TAGS_PER_MEDIA
    """
    # Validate media item
    job = await database_async.get_processing_job_by_id(media_id)
    if job is None:
        raise ValueError(f"Media item {media_id} not found")
    if job.user_id != user_id:
        raise ValueError("Media item does not belong to this user")

    # Deduplicate
    unique_tag_ids = list(dict.fromkeys(tag_ids))

    # Validate count
    if len(unique_tag_ids) > MAX_TAGS_PER_MEDIA:
        raise ValueError(
            f"Cannot assign more than {MAX_TAGS_PER_MEDIA} tags to a media item"
        )

    # Validate all tags exist and belong to user
    if unique_tag_ids:
        user_tags = await database_async.get_tags_by_user_id(user_id)
        user_tag_ids = {t.id for t in user_tags}
        invalid_ids = [tid for tid in unique_tag_ids if tid not in user_tag_ids]
        if invalid_ids:
            raise ValueError(f"Tag(s) not found: {', '.join(invalid_ids)}")

    previous_tag_ids = list(job.tag_ids)
    job.tag_ids = unique_tag_ids
    job.touch()
    await database_async.update_processing_job(job)

    logger.info(
        f"Set tags on media {media_id} for user {user_id}: "
        f"{unique_tag_ids} (was {previous_tag_ids})"
    )
    return {
        "media_id": media_id,
        "tag_ids": unique_tag_ids,
        "previous_tag_ids": previous_tag_ids,
    }
