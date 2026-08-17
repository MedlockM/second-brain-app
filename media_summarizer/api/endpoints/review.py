"""
Spaced repetition review API endpoints.

Provides:
- GET /api/review/due - get flashcards due for review
- POST /api/review/{card_id}/result - submit review result
- PATCH /api/user/settings - update spaced repetition settings
- POST /api/review/scopes/{scope}/{scope_id}/toggle - toggle spaced rep per scope
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.models.media_artifact import ArtifactScope
from media_summarizer.core.models.review_schedule import UserReviewSettings
from media_summarizer.core.services import fsrs_service
from media_summarizer.utils import review_db
from media_summarizer.utils.logging_config import bind_log_context, log_event, reset_log_context

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------- Request/Response Models ----------


class DueCardResponse(BaseModel):
    card_id: str
    scope: str
    scope_id: str
    artifact_id: str
    question: str
    answer: str
    state: int
    reps: int
    lapses: int
    due: str
    stability: float
    difficulty: float


class DueCardsListResponse(BaseModel):
    cards: List[DueCardResponse]
    total_due: int


class ReviewResultRequest(BaseModel):
    rating: str = Field(
        ...,
        description="Review rating: again, hard, good, or easy",
        pattern="^(again|hard|good|easy)$",
    )


class ReviewResultResponse(BaseModel):
    card_id: str
    rating: str
    new_state: int
    new_due: str
    stability: float
    difficulty: float
    reps: int
    lapses: int


class UserSettingsRequest(BaseModel):
    spaced_rep_enabled: Optional[bool] = None
    review_hour: Optional[int] = Field(None, ge=0, le=23)
    review_frequency: Optional[str] = Field(
        None, pattern="^(daily|every_other_day|weekly)$"
    )
    max_items_per_session: Optional[int] = Field(None, ge=1, le=100)


class UserSettingsResponse(BaseModel):
    user_id: str
    spaced_rep_enabled: bool
    review_hour: int
    review_frequency: str
    max_items_per_session: int


class ScopeToggleRequest(BaseModel):
    enabled: bool = Field(..., description="Whether spaced repetition is enabled for this scope")


class ScopeToggleResponse(BaseModel):
    scope: str
    scope_id: str
    enabled: bool
    cards_updated: int


# ---------- Endpoints ----------


@router.get("/review/due", response_model=DueCardsListResponse)
async def get_due_cards(
    current_user: AuthUser = Depends(get_current_user),
):
    """Get flashcards that are due for review today."""
    token = bind_log_context(user_id=current_user.id)
    try:
        cards = await fsrs_service.get_due_cards_for_user(current_user.id)

        response_cards = [
            DueCardResponse(
                card_id=card.card_id,
                scope=card.scope,
                scope_id=card.scope_id,
                artifact_id=card.artifact_id,
                question=card.question,
                answer=card.answer,
                state=card.state,
                reps=card.reps,
                lapses=card.lapses,
                due=card.due,
                stability=card.stability,
                difficulty=card.difficulty,
            )
            for card in cards
        ]

        log_event(
            logger,
            logging.INFO,
            "review.due.retrieved",
            "Due cards retrieved",
            user_id=current_user.id,
            card_count=len(response_cards),
        )

        return DueCardsListResponse(
            cards=response_cards,
            total_due=len(response_cards),
        )

    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "review.due.failed",
            "Failed to retrieve due cards",
            user_id=current_user.id,
            error_type=type(exc).__name__,
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve due cards",
        )
    finally:
        reset_log_context(token)


@router.post("/review/{card_id}/result", response_model=ReviewResultResponse)
async def submit_review_result(
    card_id: str,
    payload: ReviewResultRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    """Submit a review result for a flashcard (Again/Hard/Good/Easy)."""
    token = bind_log_context(user_id=current_user.id, card_id=card_id)
    try:
        updated_card = await fsrs_service.review_card(
            user_id=current_user.id,
            card_id=card_id,
            rating_str=payload.rating,
        )

        return ReviewResultResponse(
            card_id=updated_card.card_id,
            rating=payload.rating,
            new_state=updated_card.state,
            new_due=updated_card.due,
            stability=updated_card.stability,
            difficulty=updated_card.difficulty,
            reps=updated_card.reps,
            lapses=updated_card.lapses,
        )

    except ValueError as exc:
        log_event(
            logger,
            logging.WARNING,
            "review.result.invalid",
            str(exc),
            user_id=current_user.id,
            card_id=card_id,
            rating=payload.rating,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "review.result.failed",
            "Failed to submit review result",
            user_id=current_user.id,
            card_id=card_id,
            error_type=type(exc).__name__,
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit review result",
        )
    finally:
        reset_log_context(token)


@router.patch("/user/settings", response_model=UserSettingsResponse)
async def update_user_settings(
    payload: UserSettingsRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    """Update spaced repetition settings for the authenticated user."""
    token = bind_log_context(user_id=current_user.id)
    try:
        # Get existing settings or create defaults
        settings = await review_db.get_user_review_settings(current_user.id)
        if settings is None:
            settings = UserReviewSettings(user_id=current_user.id)

        # Apply updates
        if payload.spaced_rep_enabled is not None:
            settings.spaced_rep_enabled = payload.spaced_rep_enabled
        if payload.review_hour is not None:
            settings.review_hour = payload.review_hour
        if payload.review_frequency is not None:
            settings.review_frequency = payload.review_frequency
        if payload.max_items_per_session is not None:
            settings.max_items_per_session = payload.max_items_per_session

        settings.updated_at = datetime.now(timezone.utc).isoformat()
        saved = await review_db.save_user_review_settings(settings)

        log_event(
            logger,
            logging.INFO,
            "review.settings.updated",
            "User review settings updated",
            user_id=current_user.id,
            spaced_rep_enabled=saved.spaced_rep_enabled,
            review_hour=saved.review_hour,
            review_frequency=saved.review_frequency,
            max_items_per_session=saved.max_items_per_session,
        )

        return UserSettingsResponse(
            user_id=saved.user_id,
            spaced_rep_enabled=saved.spaced_rep_enabled,
            review_hour=saved.review_hour,
            review_frequency=saved.review_frequency,
            max_items_per_session=saved.max_items_per_session,
        )

    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "review.settings.failed",
            "Failed to update user settings",
            user_id=current_user.id,
            error_type=type(exc).__name__,
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update settings",
        )
    finally:
        reset_log_context(token)


@router.get("/user/settings", response_model=UserSettingsResponse)
async def get_user_settings(
    current_user: AuthUser = Depends(get_current_user),
):
    """Get spaced repetition settings for the authenticated user."""
    token = bind_log_context(user_id=current_user.id)
    try:
        settings = await review_db.get_user_review_settings(current_user.id)
        if settings is None:
            # Return defaults
            settings = UserReviewSettings(user_id=current_user.id)

        return UserSettingsResponse(
            user_id=settings.user_id,
            spaced_rep_enabled=settings.spaced_rep_enabled,
            review_hour=settings.review_hour,
            review_frequency=settings.review_frequency,
            max_items_per_session=settings.max_items_per_session,
        )

    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "review.settings.get.failed",
            "Failed to get user settings",
            user_id=current_user.id,
            error_type=type(exc).__name__,
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get settings",
        )
    finally:
        reset_log_context(token)


@router.post(
    "/review/scopes/{scope}/{scope_id}/toggle",
    response_model=ScopeToggleResponse,
)
async def toggle_scope_spaced_rep(
    scope: str,
    scope_id: str,
    payload: ScopeToggleRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    """Enable or disable spaced repetition for one scope (a media, or a collection)."""
    token = bind_log_context(user_id=current_user.id, scope=scope, scope_id=scope_id)
    try:
        if scope not in {ArtifactScope.MEDIA.value, ArtifactScope.FOLDER.value}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="scope must be 'media' or 'folder'",
            )
        cards_updated = await fsrs_service.toggle_spaced_rep_for_scope(
            user_id=current_user.id,
            scope=scope,
            scope_id=scope_id,
            enabled=payload.enabled,
        )

        return ScopeToggleResponse(
            scope=scope,
            scope_id=scope_id,
            enabled=payload.enabled,
            cards_updated=cards_updated,
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "review.scope_toggle.failed",
            "Failed to toggle spaced rep for scope",
            user_id=current_user.id,
            scope=scope,
            scope_id=scope_id,
            error_type=type(exc).__name__,
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to toggle spaced repetition",
        )
    finally:
        reset_log_context(token)
