"""
Folder service: business logic for hierarchical folder management.

Handles creation, listing (tree), renaming, moving, deletion with cascade,
and media-to-folder assignment.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from media_summarizer.core.models.folder import (
    MAX_FOLDER_DEPTH,
    Folder,
)
from media_summarizer.utils import database_async

logger = logging.getLogger(__name__)


# ---- Helper: ensure the default folder exists ----

async def ensure_default_folder(user_id: str) -> Folder:
    """Return the user's default 'Uncategorized' folder, creating it if absent."""
    folders = await database_async.get_folders_by_user_id(user_id)
    for f in folders:
        if f.is_default:
            return f

    # Create the default folder
    default = Folder.create_default(user_id)
    await database_async.create_folder(default)
    logger.info(f"Created default folder {default.id} for user {user_id}")
    return default


# ---- Depth calculation ----

def _compute_depth(folder_id: Optional[str], folders_by_id: Dict[str, Folder]) -> int:
    """Compute the depth of a folder (0 for root, 1 for child of root, etc.)."""
    depth = 0
    current_id = folder_id
    visited = set()
    while current_id is not None:
        if current_id in visited:
            # Cycle detected -- treat as root to avoid infinite loop
            break
        visited.add(current_id)
        folder = folders_by_id.get(current_id)
        if folder is None:
            break
        depth += 1
        current_id = folder.parent_folder_id
    return depth


def _get_descendant_ids(
    folder_id: str, folders: List[Folder]
) -> List[str]:
    """Return all descendant folder IDs (children, grandchildren, etc.) recursively."""
    children_map: Dict[str, List[str]] = {}
    for f in folders:
        parent = f.parent_folder_id
        if parent:
            children_map.setdefault(parent, []).append(f.id)

    result: List[str] = []
    stack = [folder_id]
    while stack:
        current = stack.pop()
        for child_id in children_map.get(current, []):
            result.append(child_id)
            stack.append(child_id)
    return result


# ---- Use cases ----

async def create_folder(
    user_id: str, name: str, parent_folder_id: Optional[str] = None
) -> Folder:
    """Create a new folder for a user.

    Validates:
    - parent exists and belongs to user (if specified)
    - depth does not exceed MAX_FOLDER_DEPTH
    """
    # Ensure default folder exists first
    await ensure_default_folder(user_id)

    all_folders = await database_async.get_folders_by_user_id(user_id)
    folders_by_id = {f.id: f for f in all_folders}

    # Validate parent
    if parent_folder_id is not None:
        parent = folders_by_id.get(parent_folder_id)
        if parent is None:
            raise ValueError(f"Parent folder {parent_folder_id} not found")
        if parent.user_id != user_id:
            raise ValueError("Parent folder does not belong to this user")

    # Check depth
    parent_depth = _compute_depth(parent_folder_id, folders_by_id)
    if parent_depth >= MAX_FOLDER_DEPTH:
        raise ValueError(
            f"Maximum folder depth ({MAX_FOLDER_DEPTH}) exceeded"
        )

    folder = Folder(
        user_id=user_id,
        name=name,
        parent_folder_id=parent_folder_id,
    )
    await database_async.create_folder(folder)
    logger.info(f"Created folder '{name}' ({folder.id}) for user {user_id}")
    return folder


async def list_folders(user_id: str) -> List[Dict[str, Any]]:
    """List all folders for a user as a flat list with parent references.

    Also ensures the default folder exists. Returns a list of folder dicts
    that can be reconstructed into a tree on the client side.
    """
    _default = await ensure_default_folder(user_id)  # Side-effect: creates if missing
    all_folders = await database_async.get_folders_by_user_id(user_id)

    result = []
    for f in all_folders:
        result.append({
            "id": f.id,
            "name": f.name,
            "parent_folder_id": f.parent_folder_id,
            "is_default": f.is_default,
            "created_at": f.created_at.isoformat(),
            "updated_at": f.updated_at.isoformat(),
        })

    # Sort: default first, then alphabetical
    result.sort(key=lambda x: (not x["is_default"], x["name"].lower()))
    return result


async def update_folder(
    user_id: str,
    folder_id: str,
    name: Optional[str] = None,
    parent_folder_id: Optional[str] = ...,  # type: ignore[assignment]  # sentinel
) -> Folder:
    """Update a folder (rename and/or move).

    Args:
        user_id: owner user ID
        folder_id: folder to update
        name: new name (if provided)
        parent_folder_id: new parent (None = move to root, ... = no change)
    """
    folder = await database_async.get_folder_by_id(folder_id)
    if folder is None:
        raise ValueError(f"Folder {folder_id} not found")
    if folder.user_id != user_id:
        raise ValueError("Folder does not belong to this user")
    if folder.is_default:
        raise ValueError("Cannot modify the default folder")

    all_folders = await database_async.get_folders_by_user_id(user_id)
    folders_by_id = {f.id: f for f in all_folders}

    if name is not None:
        folder.name = name.strip()

    # Handle parent change (sentinel ... means "no change")
    if parent_folder_id is not ...:
        if parent_folder_id is not None:
            # Validate parent exists and belongs to user
            parent = folders_by_id.get(parent_folder_id)
            if parent is None:
                raise ValueError(f"Parent folder {parent_folder_id} not found")
            if parent.user_id != user_id:
                raise ValueError("Parent folder does not belong to this user")

            # Prevent moving a folder into its own subtree
            descendant_ids = _get_descendant_ids(folder_id, all_folders)
            if parent_folder_id in descendant_ids or parent_folder_id == folder_id:
                raise ValueError("Cannot move a folder into its own subtree")

            # Check depth
            parent_depth = _compute_depth(parent_folder_id, folders_by_id)
            # Also account for the depth of the deepest descendant of the folder being moved
            max_descendant_depth = 0
            if descendant_ids:
                for desc_id in descendant_ids:
                    d = _compute_depth(desc_id, folders_by_id) - _compute_depth(
                        folder_id, folders_by_id
                    )
                    if d > max_descendant_depth:
                        max_descendant_depth = d

            if parent_depth + 1 + max_descendant_depth > MAX_FOLDER_DEPTH:
                raise ValueError(
                    f"Moving folder would exceed maximum depth ({MAX_FOLDER_DEPTH})"
                )

        folder.parent_folder_id = parent_folder_id

    folder.touch()
    await database_async.update_folder(folder)
    logger.info(f"Updated folder {folder_id} for user {user_id}")
    return folder


async def delete_folder(user_id: str, folder_id: str) -> Dict[str, Any]:
    """Delete a folder. Moves all sub-folders and media to 'Uncategorized'.

    Returns a summary of what was moved.
    """
    folder = await database_async.get_folder_by_id(folder_id)
    if folder is None:
        raise ValueError(f"Folder {folder_id} not found")
    if folder.user_id != user_id:
        raise ValueError("Folder does not belong to this user")
    if folder.is_default:
        raise ValueError("Cannot delete the default folder")

    default = await ensure_default_folder(user_id)
    all_folders = await database_async.get_folders_by_user_id(user_id)

    # Collect all descendant folder IDs (including the folder itself)
    descendant_ids = _get_descendant_ids(folder_id, all_folders)
    all_folder_ids_to_delete = [folder_id] + descendant_ids

    # Move media items from all deleted folders to "Uncategorized"
    moved_media_count = 0
    for fid in all_folder_ids_to_delete:
        jobs = await database_async.get_processing_jobs_by_folder_id(user_id, fid)
        for job in jobs:
            job.folder_id = default.id
            job.touch()
            await database_async.update_processing_job(job)
            moved_media_count += 1

    # Move direct children of deleted folders whose parent is being deleted
    # to "Uncategorized" -- but since we delete ALL descendants, this is only
    # relevant for sub-folders that have children outside the deleted subtree.
    # Actually, all descendants are deleted, so no orphan sub-folders remain.

    # Delete all folders (descendants first, then the target)
    deleted_folder_count = 0
    for fid in reversed(all_folder_ids_to_delete):
        await database_async.delete_folder(fid)
        deleted_folder_count += 1

    logger.info(
        f"Deleted folder {folder_id} and {len(descendant_ids)} sub-folders, "
        f"moved {moved_media_count} media items to Uncategorized"
    )
    return {
        "deleted_folders": deleted_folder_count,
        "moved_media_count": moved_media_count,
        "default_folder_id": default.id,
    }


async def assign_folder_to_media(
    user_id: str, media_id: str, folder_id: Optional[str]
) -> Dict[str, Any]:
    """Assign a media item (processing job) to a folder.

    If folder_id is None, assigns to the default 'Uncategorized' folder.
    """
    # Get the job
    job = await database_async.get_processing_job_by_id(media_id)
    if job is None:
        raise ValueError(f"Media item {media_id} not found")
    if job.user_id != user_id:
        raise ValueError("Media item does not belong to this user")

    # Resolve target folder
    if folder_id is None:
        target = await ensure_default_folder(user_id)
        folder_id = target.id
    else:
        target = await database_async.get_folder_by_id(folder_id)
        if target is None:
            raise ValueError(f"Folder {folder_id} not found")
        if target.user_id != user_id:
            raise ValueError("Folder does not belong to this user")

    old_folder_id = job.folder_id
    job.folder_id = folder_id
    job.touch()
    await database_async.update_processing_job(job)

    logger.info(
        f"Assigned media {media_id} to folder {folder_id} "
        f"(was {old_folder_id}) for user {user_id}"
    )
    return {
        "media_id": media_id,
        "folder_id": folder_id,
        "previous_folder_id": old_folder_id,
    }
