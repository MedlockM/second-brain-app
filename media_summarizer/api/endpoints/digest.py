"""
In-app digest API endpoints.

Provides:
- GET /api/digest/daily - get daily digest for the authenticated user
- GET /api/digest/weekly - get weekly digest for the authenticated user
- GET /api/digest/settings - get user digest settings
- PATCH /api/digest/settings - update user digest settings (toggle on/off)
"""

from __future__ import annotations

import logging
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.services import digest_service
from media_summarizer.utils.logging_config import bind_log_context, log_event, reset_log_context

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------- Request/Response Models ----------


class DigestMediaItemResponse(BaseModel):
    media_item_id: str
    title: Optional[str] = None
    media_type: Optional[str] = None
    source_platform: Optional[str] = None
    summary_short_artifact_id: Optional[str] = None
    summary_short_status: str = "pending"
    added_at: str


class DigestResponse(BaseModel):
    user_id: str
    digest_type: str
    period_key: str
    status: str
    media_items: List[DigestMediaItemResponse]
    item_count: int
    created_at: str
    updated_at: str
    published_at: Optional[str] = None


class DigestSettingsResponse(BaseModel):
    user_id: str
    digest_enabled: bool
    daily_digest_enabled: bool
    weekly_digest_enabled: bool


class DigestSettingsUpdateRequest(BaseModel):
    digest_enabled: Optional[bool] = None
    daily_digest_enabled: Optional[bool] = None
    weekly_digest_enabled: Optional[bool] = None


# ---------- Endpoints ----------


@router.get("/digest/daily", response_model=DigestResponse)
async def get_daily_digest(
    target_date: Optional[str] = Query(
        None,
        description="Target date in YYYY-MM-DD format. Defaults to today.",
        alias="date",
    ),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Get the daily digest for the authenticated user.
    Contains Summary Short for each media item added that day.
    """
    token = bind_log_context(user_id=current_user.id)
    try:
        # Check if digest is enabled for this user
        settings = await digest_service.get_user_digest_settings(current_user.id)
        if not settings.digest_enabled or not settings.daily_digest_enabled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Daily digest is disabled for this user",
            )

        # Parse target date
        parsed_date: Optional[date] = None
        if target_date:
            try:
                parsed_date = date.fromisoformat(target_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date format. Use YYYY-MM-DD.",
                )

        digest = await digest_service.get_or_assemble_daily_digest(
            current_user.id, parsed_date
        )

        log_event(
            logger,
            logging.INFO,
            "digest.daily.retrieved",
            "Daily digest retrieved",
            user_id=current_user.id,
            period_key=digest.period_key,
            item_count=len(digest.media_items),
        )

        return DigestResponse(
            user_id=digest.user_id,
            digest_type=digest.digest_type.value,
            period_key=digest.period_key,
            status=digest.status.value,
            media_items=[
                DigestMediaItemResponse(
                    media_item_id=mi.media_item_id,
                    title=mi.title,
                    media_type=mi.media_type,
                    source_platform=mi.source_platform,
                    summary_short_artifact_id=mi.summary_short_artifact_id,
                    summary_short_status=mi.summary_short_status,
                    added_at=mi.added_at,
                )
                for mi in digest.media_items
            ],
            item_count=len(digest.media_items),
            created_at=digest.created_at,
            updated_at=digest.updated_at,
            published_at=digest.published_at,
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "digest.daily.failed",
            "Failed to retrieve daily digest",
            user_id=current_user.id,
            error_type=type(exc).__name__,
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve daily digest",
        )
    finally:
        reset_log_context(token)


@router.get("/digest/weekly", response_model=DigestResponse)
async def get_weekly_digest(
    week: Optional[str] = Query(
        None,
        description="Target week in YYYY-Wnn format (e.g. 2026-W18). Defaults to current week.",
    ),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Get the weekly digest for the authenticated user.
    Contains Summary Short for each media item added that week.
    """
    token = bind_log_context(user_id=current_user.id)
    try:
        # Check if digest is enabled for this user
        settings = await digest_service.get_user_digest_settings(current_user.id)
        if not settings.digest_enabled or not settings.weekly_digest_enabled:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Weekly digest is disabled for this user",
            )

        # Validate week format if provided
        if week:
            try:
                parts = week.split("-W")
                if len(parts) != 2:
                    raise ValueError()
                int(parts[0])
                w = int(parts[1])
                if w < 1 or w > 53:
                    raise ValueError()
            except (ValueError, IndexError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid week format. Use YYYY-Wnn (e.g. 2026-W18).",
                )

        digest = await digest_service.get_or_assemble_weekly_digest(
            current_user.id, week
        )

        log_event(
            logger,
            logging.INFO,
            "digest.weekly.retrieved",
            "Weekly digest retrieved",
            user_id=current_user.id,
            period_key=digest.period_key,
            item_count=len(digest.media_items),
        )

        return DigestResponse(
            user_id=digest.user_id,
            digest_type=digest.digest_type.value,
            period_key=digest.period_key,
            status=digest.status.value,
            media_items=[
                DigestMediaItemResponse(
                    media_item_id=mi.media_item_id,
                    title=mi.title,
                    media_type=mi.media_type,
                    source_platform=mi.source_platform,
                    summary_short_artifact_id=mi.summary_short_artifact_id,
                    summary_short_status=mi.summary_short_status,
                    added_at=mi.added_at,
                )
                for mi in digest.media_items
            ],
            item_count=len(digest.media_items),
            created_at=digest.created_at,
            updated_at=digest.updated_at,
            published_at=digest.published_at,
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "digest.weekly.failed",
            "Failed to retrieve weekly digest",
            user_id=current_user.id,
            error_type=type(exc).__name__,
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve weekly digest",
        )
    finally:
        reset_log_context(token)


@router.get("/digest/settings", response_model=DigestSettingsResponse)
async def get_digest_settings(
    current_user: AuthUser = Depends(get_current_user),
):
    """Get digest settings for the authenticated user."""
    token = bind_log_context(user_id=current_user.id)
    try:
        settings = await digest_service.get_user_digest_settings(current_user.id)
        return DigestSettingsResponse(
            user_id=settings.user_id,
            digest_enabled=settings.digest_enabled,
            daily_digest_enabled=settings.daily_digest_enabled,
            weekly_digest_enabled=settings.weekly_digest_enabled,
        )
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "digest.settings.get.failed",
            "Failed to get digest settings",
            user_id=current_user.id,
            error_type=type(exc).__name__,
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get digest settings",
        )
    finally:
        reset_log_context(token)


@router.patch("/digest/settings", response_model=DigestSettingsResponse)
async def update_digest_settings(
    payload: DigestSettingsUpdateRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    """Update digest settings for the authenticated user (toggle digest on/off)."""
    token = bind_log_context(user_id=current_user.id)
    try:
        settings = await digest_service.update_user_digest_settings(
            current_user.id,
            digest_enabled=payload.digest_enabled,
            daily_digest_enabled=payload.daily_digest_enabled,
            weekly_digest_enabled=payload.weekly_digest_enabled,
        )

        log_event(
            logger,
            logging.INFO,
            "digest.settings.updated",
            "Digest settings updated",
            user_id=current_user.id,
            digest_enabled=settings.digest_enabled,
            daily_digest_enabled=settings.daily_digest_enabled,
            weekly_digest_enabled=settings.weekly_digest_enabled,
        )

        return DigestSettingsResponse(
            user_id=settings.user_id,
            digest_enabled=settings.digest_enabled,
            daily_digest_enabled=settings.daily_digest_enabled,
            weekly_digest_enabled=settings.weekly_digest_enabled,
        )

    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "digest.settings.update.failed",
            "Failed to update digest settings",
            user_id=current_user.id,
            error_type=type(exc).__name__,
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update digest settings",
        )
    finally:
        reset_log_context(token)
