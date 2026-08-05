"""
FSRS spaced repetition service.

Wraps the `fsrs` library to provide card scheduling for flashcards.
Handles conversion between our DynamoDB model and the fsrs Card dataclass.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

import fsrs

from media_summarizer.core.models.review_schedule import (
    CardState,
    ReviewScheduleRecord,
)
from media_summarizer.utils import review_db
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

# Map our Rating strings to fsrs.Rating enum
RATING_MAP = {
    "again": fsrs.Rating.Again,
    "hard": fsrs.Rating.Hard,
    "good": fsrs.Rating.Good,
    "easy": fsrs.Rating.Easy,
}


def _record_to_fsrs_card(record: ReviewScheduleRecord) -> fsrs.Card:
    """Convert a ReviewScheduleRecord to an fsrs Card."""
    card_dict = {
        "card_id": hash(record.card_id) % (2**53),
        "state": record.state,
        "step": 0,
        "stability": record.stability if record.stability else None,
        "difficulty": record.difficulty if record.difficulty else None,
        "due": record.due,
        "last_review": record.last_review if record.last_review else None,
    }
    return fsrs.Card.from_dict(card_dict)


def _fsrs_card_to_record_fields(card: fsrs.Card) -> dict:
    """Extract FSRS fields from an fsrs Card to update a ReviewScheduleRecord."""
    return {
        "stability": card.stability or 0.0,
        "difficulty": card.difficulty or 0.0,
        "state": card.state.value if hasattr(card.state, "value") else int(card.state),
        "due": card.due.isoformat() if isinstance(card.due, datetime) else str(card.due),
        "last_review": (
            card.last_review.isoformat()
            if isinstance(card.last_review, datetime)
            else card.last_review
        ),
    }


def create_scheduler() -> fsrs.Scheduler:
    """Create a configured FSRS scheduler."""
    return fsrs.Scheduler(
        desired_retention=0.9,
        enable_fuzzing=True,
    )


async def initialize_cards_for_flashcards(
    user_id: str,
    media_item_id: str,
    artifact_id: str,
    flashcards: List[dict],
) -> List[ReviewScheduleRecord]:
    """
    Create ReviewScheduleRecords for newly generated flashcards.

    Args:
        user_id: The user who owns these cards
        media_item_id: The media item the flashcards belong to
        artifact_id: The artifact ID that generated these flashcards
        flashcards: List of dicts with 'question' and 'answer' keys

    Returns:
        List of created ReviewScheduleRecord entries
    """
    now = datetime.now(timezone.utc)
    records = []
    for card_data in flashcards:
        record = ReviewScheduleRecord(
            user_id=user_id,
            media_item_id=media_item_id,
            artifact_id=artifact_id,
            question=card_data["question"],
            answer=card_data["answer"],
            stability=0.0,
            difficulty=0.0,
            elapsed_days=0,
            scheduled_days=0,
            reps=0,
            lapses=0,
            state=CardState.LEARNING.value,
            last_review=None,
            due=now.isoformat(),
            spaced_repetition_enabled=True,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
        )
        records.append(record)

    if records:
        await review_db.bulk_create_review_cards(records)
        log_event(
            logger,
            logging.INFO,
            "fsrs.cards_initialized",
            "FSRS cards created for flashcards",
            user_id=user_id,
            media_item_id=media_item_id,
            artifact_id=artifact_id,
            card_count=len(records),
        )

    return records


async def review_card(
    user_id: str,
    card_id: str,
    rating_str: str,
    review_time: Optional[datetime] = None,
) -> ReviewScheduleRecord:
    """
    Process a review for a card using the FSRS algorithm.

    Args:
        user_id: User who reviewed the card
        card_id: The card being reviewed
        rating_str: One of 'again', 'hard', 'good', 'easy'
        review_time: When the review happened (defaults to now)

    Returns:
        The updated ReviewScheduleRecord

    Raises:
        ValueError: If the card is not found or rating is invalid
    """
    if rating_str.lower() not in RATING_MAP:
        raise ValueError(
            f"Invalid rating '{rating_str}'. Must be one of: again, hard, good, easy"
        )

    rating = RATING_MAP[rating_str.lower()]
    if review_time is None:
        review_time = datetime.now(timezone.utc)

    record = await review_db.get_review_card(user_id, card_id)
    if record is None:
        raise ValueError(f"Card {card_id} not found for user {user_id}")

    # Convert to fsrs Card
    fsrs_card = _record_to_fsrs_card(record)

    # Run FSRS scheduling
    scheduler = create_scheduler()
    updated_card, review_log = scheduler.review_card(fsrs_card, rating, review_time)

    # Update our record with FSRS output
    fsrs_fields = _fsrs_card_to_record_fields(updated_card)
    record.stability = fsrs_fields["stability"]
    record.difficulty = fsrs_fields["difficulty"]
    record.state = fsrs_fields["state"]
    record.due = fsrs_fields["due"]
    record.last_review = fsrs_fields["last_review"]
    record.reps = record.reps + 1
    if rating == fsrs.Rating.Again:
        record.lapses = record.lapses + 1
    record.updated_at = datetime.now(timezone.utc).isoformat()

    # Calculate elapsed and scheduled days
    if record.last_review:
        last_dt = datetime.fromisoformat(record.last_review)
        due_dt = datetime.fromisoformat(record.due)
        record.scheduled_days = max(0, (due_dt - last_dt).days)

    await review_db.update_review_card(record)

    log_event(
        logger,
        logging.INFO,
        "fsrs.card_reviewed",
        "Card reviewed and rescheduled",
        user_id=user_id,
        card_id=card_id,
        rating=rating_str,
        new_state=record.state,
        new_due=record.due,
        stability=record.stability,
        reps=record.reps,
    )

    return record


async def get_due_cards_for_user(
    user_id: str,
    now: Optional[datetime] = None,
) -> List[ReviewScheduleRecord]:
    """
    Get all due cards for a user, respecting their settings.

    Args:
        user_id: The user to get due cards for
        now: Current time (defaults to utcnow)

    Returns:
        List of due ReviewScheduleRecords, limited by user settings
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Check user settings
    settings = await review_db.get_user_review_settings(user_id)
    if settings and not settings.spaced_rep_enabled:
        return []

    max_items = settings.max_items_per_session if settings else 20
    cards = await review_db.get_due_cards(user_id, now=now, limit=max_items)
    return cards


async def toggle_spaced_rep_for_media(
    user_id: str,
    media_item_id: str,
    enabled: bool,
) -> int:
    """
    Enable or disable spaced repetition for all cards of a specific media item.

    Returns:
        Number of cards updated
    """
    cards = await review_db.get_cards_by_media_item(user_id, media_item_id)
    count = 0
    for card in cards:
        if card.spaced_repetition_enabled != enabled:
            card.spaced_repetition_enabled = enabled
            card.updated_at = datetime.now(timezone.utc).isoformat()
            await review_db.update_review_card(card)
            count += 1

    log_event(
        logger,
        logging.INFO,
        "fsrs.media_toggle",
        f"Spaced repetition {'enabled' if enabled else 'disabled'} for media",
        user_id=user_id,
        media_item_id=media_item_id,
        cards_updated=count,
    )
    return count
