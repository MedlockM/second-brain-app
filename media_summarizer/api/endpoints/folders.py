"""
Folder API endpoints for hierarchical media organization.

Provides CRUD operations on user folders and media-to-folder assignment.
"""

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.services import folder_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- Request / Response models ----------

class CreateFolderRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Folder name")
    parent_folder_id: Optional[str] = Field(
        None, description="Parent folder ID (null for root-level)"
    )


class UpdateFolderRequest(BaseModel):
    name: Optional[str] = Field(
        None, min_length=1, max_length=255, description="New folder name"
    )
    parent_folder_id: Optional[str] = Field(
        None, description="New parent folder ID (null to move to root)"
    )

    class Config:
        # Allow explicit null to distinguish "move to root" from "no change"
        # We handle this via the _move_to_root flag below
        pass


class AssignFolderRequest(BaseModel):
    folder_id: Optional[str] = Field(
        None,
        description="Folder ID to assign the media to (null for Uncategorized)",
    )


class FolderResponse(BaseModel):
    id: str
    name: str
    parent_folder_id: Optional[str] = None
    is_default: bool = False
    # Items stored directly in this folder, counted from the durable library
    # (task-220). A freshly created folder is necessarily empty, so the create
    # endpoint returns 0 without querying.
    media_count: int = 0
    created_at: str
    updated_at: str


class FolderListResponse(BaseModel):
    status: str = "success"
    folders: List[FolderResponse]
    count: int


class FolderDeleteResponse(BaseModel):
    status: str = "success"
    deleted_folders: int
    moved_media_count: int
    default_folder_id: str


class AssignFolderResponse(BaseModel):
    status: str = "success"
    media_id: str
    folder_id: str
    previous_folder_id: Optional[str] = None


# ---------- Endpoints ----------

@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    payload: CreateFolderRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> FolderResponse:
    """Create a new folder."""
    try:
        folder = await folder_service.create_folder(
            user_id=current_user.id,
            name=payload.name,
            parent_folder_id=payload.parent_folder_id,
        )
        return FolderResponse(
            id=folder.id,
            name=folder.name,
            parent_folder_id=folder.parent_folder_id,
            is_default=folder.is_default,
            created_at=folder.created_at.isoformat(),
            updated_at=folder.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating folder: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create folder",
        )


@router.get("", response_model=FolderListResponse)
async def list_folders(
    current_user: AuthUser = Depends(get_current_user),
) -> FolderListResponse:
    """List all folders for the authenticated user (flat list with parent references)."""
    try:
        folders = await folder_service.list_folders(user_id=current_user.id)
        items = [FolderResponse(**f) for f in folders]
        return FolderListResponse(
            status="success",
            folders=items,
            count=len(items),
        )
    except Exception as e:
        logger.error(f"Error listing folders: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list folders",
        )


@router.put("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: str,
    payload: UpdateFolderRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> FolderResponse:
    """Update a folder (rename and/or move).

    To move a folder to root, send `{"parent_folder_id": null}` explicitly.
    If parent_folder_id is not included in the body, the parent is unchanged.
    """
    try:
        # Determine whether parent_folder_id was explicitly provided in the body.
        # When the key is absent from JSON, Pydantic sets it to None by default,
        # so we inspect the raw body via __fields_set__.
        parent_arg: Any = ...  # sentinel = no change
        if "parent_folder_id" in payload.model_fields_set:
            parent_arg = payload.parent_folder_id  # could be None (move to root) or a string

        folder = await folder_service.update_folder(
            user_id=current_user.id,
            folder_id=folder_id,
            name=payload.name,
            parent_folder_id=parent_arg,
        )
        return FolderResponse(
            id=folder.id,
            name=folder.name,
            parent_folder_id=folder.parent_folder_id,
            is_default=folder.is_default,
            media_count=await folder_service.count_media_in_folder(
                current_user.id, folder.id
            ),
            created_at=folder.created_at.isoformat(),
            updated_at=folder.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating folder {folder_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update folder",
        )


@router.delete("/{folder_id}", response_model=FolderDeleteResponse)
async def delete_folder(
    folder_id: str,
    current_user: AuthUser = Depends(get_current_user),
) -> FolderDeleteResponse:
    """Delete a folder. Sub-folders and media are moved to 'Uncategorized'."""
    try:
        result = await folder_service.delete_folder(
            user_id=current_user.id,
            folder_id=folder_id,
        )
        return FolderDeleteResponse(
            status="success",
            deleted_folders=result["deleted_folders"],
            moved_media_count=result["moved_media_count"],
            default_folder_id=result["default_folder_id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting folder {folder_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete folder",
        )
