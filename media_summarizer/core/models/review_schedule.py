"""
Review schedule model for FSRS spaced repetition on flashcards.

Each record represents a single flashcard scheduled for review using the
FSRS algorithm. The DynamoDB table uses user_id as PK and card_id as SK.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _new_card_id() -> str:
    return f"card_{uuid.uuid4().hex}"


class CardState(int, Enum):
    """FSRS card states matching the fsrs library (v6+)."""
    LEARNING = 1
    REVIEW = 2
    RELEARNING = 3


class ReviewScheduleRecord(BaseModel):
    """A single flashcard review schedule entry."""

    user_id: str
    card_id: str = Field(default_factory=_new_card_id)
    # Scope, not media: a collection's flashcards must enter the review queue
    # like any other deck, and a collection has no media item (task-270).
    scope: str
    scope_id: str
    artifact_id: str
    question: str
    answer: str

    # FSRS algorithm fields
    stability: float = 0.0
    difficulty: float = 0.0
    elapsed_days: int = 0
    scheduled_days: int = 0
    reps: int = 0
    lapses: int = 0
    state: int = Field(default=CardState.LEARNING.value)
    last_review: Optional[str] = None
    due: str = Field(default_factory=lambda: _now_utc().isoformat())

    # Metadata
    spaced_repetition_enabled: bool = True
    created_at: str = Field(default_factory=lambda: _now_utc().isoformat())
    updated_at: str = Field(default_factory=lambda: _now_utc().isoformat())

    def to_dynamodb_item(self) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "user_id": self.user_id,
            "card_id": self.card_id,
            "scope": self.scope,
            "scope_id": self.scope_id,
            "artifact_id": self.artifact_id,
            "question": self.question,
            "answer": self.answer,
            "stability": str(self.stability),
            "difficulty": str(self.difficulty),
            "elapsed_days": self.elapsed_days,
            "scheduled_days": self.scheduled_days,
            "reps": self.reps,
            "lapses": self.lapses,
            "state": self.state,
            "last_review": self.last_review or "",
            "due": self.due,
            "spaced_repetition_enabled": self.spaced_repetition_enabled,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "ReviewScheduleRecord":
        return cls(
            user_id=item["user_id"],
            card_id=item["card_id"],
            scope=item["scope"],
            scope_id=item["scope_id"],
            artifact_id=item["artifact_id"],
            question=item["question"],
            answer=item["answer"],
            stability=float(item.get("stability", 0)),
            difficulty=float(item.get("difficulty", 0)),
            elapsed_days=int(item.get("elapsed_days", 0)),
            scheduled_days=int(item.get("scheduled_days", 0)),
            reps=int(item.get("reps", 0)),
            lapses=int(item.get("lapses", 0)),
            state=int(item.get("state", CardState.NEW.value)),
            last_review=item.get("last_review") or None,
            due=item.get("due", _now_utc().isoformat()),
            spaced_repetition_enabled=item.get("spaced_repetition_enabled", True),
            created_at=item.get("created_at", _now_utc().isoformat()),
            updated_at=item.get("updated_at", _now_utc().isoformat()),
        )


class UserReviewSettings(BaseModel):
    """User-level spaced repetition settings."""

    user_id: str
    spaced_rep_enabled: bool = True
    review_hour: int = Field(default=9, ge=0, le=23)
    review_frequency: str = "daily"  # daily, every_other_day, weekly
    max_items_per_session: int = Field(default=20, ge=1, le=100)
    updated_at: str = Field(default_factory=lambda: _now_utc().isoformat())

    def to_dynamodb_item(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "spaced_rep_enabled": self.spaced_rep_enabled,
            "review_hour": self.review_hour,
            "review_frequency": self.review_frequency,
            "max_items_per_session": self.max_items_per_session,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "UserReviewSettings":
        return cls(
            user_id=item["user_id"],
            spaced_rep_enabled=item.get("spaced_rep_enabled", True),
            review_hour=int(item.get("review_hour", 9)),
            review_frequency=item.get("review_frequency", "daily"),
            max_items_per_session=int(item.get("max_items_per_session", 20)),
            updated_at=item.get("updated_at", _now_utc().isoformat()),
        )
