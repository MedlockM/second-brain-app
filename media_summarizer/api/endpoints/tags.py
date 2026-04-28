"""
Tag API endpoints for user-created media labels.

Provides CRUD operations on user tags and media-to-tag assignment.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.services import tag_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- Request / Response models ----------

class CreateTagRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Tag name")
    color: Optional[str] = Field(
        None, description="Hex color (e.g. #FF5733). Defaults to gray if omitted."
    )


class UpdateTagRequest(BaseModel):
    name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="New tag name"
    )
    color: Optional[str] = Field(
        None, description="New hex color (e.g. #FF5733)"
    )


class SetMediaTagsRequest(BaseModel):
    tag_ids: List[str] = Field(
        ..., description="List of tag IDs to assign to the media item"
    )


class TagResponse(BaseModel):
    id: str
    name: str
    color: Optional[str] = None
    created_at: str
    updated_at: str


class TagListResponse(BaseModel):
    status: str = "success"
    tags: List[TagResponse]
    count: int


class TagDeleteResponse(BaseModel):
    status: str = "success"
    deleted_tag_id: str
    dissociated_media_count: int


class SetMediaTagsResponse(BaseModel):
    status: str = "success"
    media_id: str
    tag_ids: List[str]
    previous_tag_ids: List[str]


# ---------- Endpoints ----------

@router.post("", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    payload: CreateTagRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> TagResponse:
    """Create a new tag."""
    try:
        tag = await tag_service.create_tag(
            user_id=current_user.id,
            name=payload.name,
            color=payload.color,
        )
        return TagResponse(
            id=tag.id,
            name=tag.name,
            color=tag.color,
            created_at=tag.created_at.isoformat(),
            updated_at=tag.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating tag: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create tag",
        )


@router.get("", response_model=TagListResponse)
async def list_tags(
    current_user: AuthUser = Depends(get_current_user),
) -> TagListResponse:
    """List all tags for the authenticated user."""
    try:
        tags = await tag_service.list_tags(user_id=current_user.id)
        items = [TagResponse(**t) for t in tags]
        return TagListResponse(
            status="success",
            tags=items,
            count=len(items),
        )
    except Exception as e:
        logger.error(f"Error listing tags: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tags",
        )


@router.put("/{tag_id}", response_model=TagResponse)
async def update_tag(
    tag_id: str,
    payload: UpdateTagRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> TagResponse:
    """Update a tag (rename and/or change color)."""
    try:
        # Determine whether color was explicitly provided in the body
        color_arg = ...  # sentinel = no change
        if "color" in payload.model_fields_set:
            color_arg = payload.color

        tag = await tag_service.update_tag(
            user_id=current_user.id,
            tag_id=tag_id,
            name=payload.name,
            color=color_arg,
        )
        return TagResponse(
            id=tag.id,
            name=tag.name,
            color=tag.color,
            created_at=tag.created_at.isoformat(),
            updated_at=tag.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating tag {tag_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tag",
        )


@router.delete("/{tag_id}", response_model=TagDeleteResponse)
async def delete_tag(
    tag_id: str,
    current_user: AuthUser = Depends(get_current_user),
) -> TagDeleteResponse:
    """Delete a tag. Dissociates it from all media items."""
    try:
        result = await tag_service.delete_tag(
            user_id=current_user.id,
            tag_id=tag_id,
        )
        return TagDeleteResponse(
            status="success",
            deleted_tag_id=result["deleted_tag_id"],
            dissociated_media_count=result["dissociated_media_count"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting tag {tag_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete tag",
        )
