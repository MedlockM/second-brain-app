"""
DynamoDB operations for the FSRS review schedule and user review settings.

Tables:
- review_schedule: PK=user_id, SK=card_id
- user_review_settings: PK=user_id
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from media_summarizer.core.models.review_schedule import (
    ReviewScheduleRecord,
    UserReviewSettings,
)
from media_summarizer.utils.database_async import (
    _dynamodb_client_kwargs,
    _log_dynamodb_error,
    _log_dynamodb_success,
    get_session,
)
from media_summarizer.utils.env import required_env

logger = logging.getLogger(__name__)

REVIEW_SCHEDULE_TABLE = required_env("REVIEW_SCHEDULE_TABLE")
USER_REVIEW_SETTINGS_TABLE = required_env("USER_REVIEW_SETTINGS_TABLE")


# ---------- Review Schedule CRUD ----------


async def create_review_card(record: ReviewScheduleRecord) -> ReviewScheduleRecord:
    """Create a new review schedule card entry."""
    session = get_session()
    async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
        table = await dynamodb.Table(REVIEW_SCHEDULE_TABLE)
        try:
            await table.put_item(
                Item=record.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(card_id)",
            )
            _log_dynamodb_success(
                "create_review_card",
                table=REVIEW_SCHEDULE_TABLE,
                card_id=record.card_id,
                user_id=record.user_id,
            )
            return record
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ValueError(
                    f"Review card with ID {record.card_id} already exists"
                )
            _log_dynamodb_error(
                "create_review_card",
                e,
                table=REVIEW_SCHEDULE_TABLE,
                card_id=record.card_id,
            )
            raise


async def get_review_card(user_id: str, card_id: str) -> Optional[ReviewScheduleRecord]:
    """Get a single review card by user_id and card_id."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(REVIEW_SCHEDULE_TABLE)
            response = await table.get_item(
                Key={"user_id": user_id, "card_id": card_id}
            )
            if "Item" in response:
                return ReviewScheduleRecord.from_dynamodb_item(response["Item"])
            return None
    except ClientError as e:
        _log_dynamodb_error(
            "get_review_card",
            e,
            table=REVIEW_SCHEDULE_TABLE,
            card_id=card_id,
            user_id=user_id,
        )
        raise


async def update_review_card(record: ReviewScheduleRecord) -> ReviewScheduleRecord:
    """Update a review card (e.g. after a review)."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(REVIEW_SCHEDULE_TABLE)
            await table.put_item(Item=record.to_dynamodb_item())
            _log_dynamodb_success(
                "update_review_card",
                table=REVIEW_SCHEDULE_TABLE,
                card_id=record.card_id,
                user_id=record.user_id,
            )
            return record
    except ClientError as e:
        _log_dynamodb_error(
            "update_review_card",
            e,
            table=REVIEW_SCHEDULE_TABLE,
            card_id=record.card_id,
        )
        raise


async def get_due_cards(
    user_id: str, now: Optional[datetime] = None, limit: int = 50
) -> List[ReviewScheduleRecord]:
    """Get all cards due for review for a user (due <= now)."""
    if now is None:
        now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(REVIEW_SCHEDULE_TABLE)
            response = await table.query(
                KeyConditionExpression=Key("user_id").eq(user_id),
                FilterExpression=Attr("due").lte(now_iso)
                & Attr("spaced_repetition_enabled").eq(True),
            )
            items = response.get("Items", [])
            cards = [ReviewScheduleRecord.from_dynamodb_item(item) for item in items]
            # Sort by due date ascending (oldest first)
            cards.sort(key=lambda c: c.due)
            return cards[:limit]
    except ClientError as e:
        _log_dynamodb_error(
            "get_due_cards",
            e,
            table=REVIEW_SCHEDULE_TABLE,
            user_id=user_id,
        )
        raise


async def get_cards_by_media_item(
    user_id: str, media_item_id: str
) -> List[ReviewScheduleRecord]:
    """Get all review cards for a specific media item."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(REVIEW_SCHEDULE_TABLE)
            response = await table.query(
                KeyConditionExpression=Key("user_id").eq(user_id),
                FilterExpression=Attr("media_item_id").eq(media_item_id),
            )
            items = response.get("Items", [])
            return [ReviewScheduleRecord.from_dynamodb_item(item) for item in items]
    except ClientError as e:
        _log_dynamodb_error(
            "get_cards_by_media_item",
            e,
            table=REVIEW_SCHEDULE_TABLE,
            user_id=user_id,
            media_item_id=media_item_id,
        )
        raise


async def bulk_create_review_cards(
    records: List[ReviewScheduleRecord],
) -> List[ReviewScheduleRecord]:
    """Batch write multiple review cards."""
    if not records:
        return []
    session = get_session()
    async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
        table = await dynamodb.Table(REVIEW_SCHEDULE_TABLE)
        async with table.batch_writer() as batch:
            for record in records:
                await batch.put_item(Item=record.to_dynamodb_item())
        _log_dynamodb_success(
            "bulk_create_review_cards",
            table=REVIEW_SCHEDULE_TABLE,
            count=len(records),
            user_id=records[0].user_id if records else "unknown",
        )
    return records


# ---------- User Review Settings CRUD ----------


async def get_user_review_settings(user_id: str) -> Optional[UserReviewSettings]:
    """Get review settings for a user."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_REVIEW_SETTINGS_TABLE)
            response = await table.get_item(Key={"user_id": user_id})
            if "Item" in response:
                return UserReviewSettings.from_dynamodb_item(response["Item"])
            return None
    except ClientError as e:
        _log_dynamodb_error(
            "get_user_review_settings",
            e,
            table=USER_REVIEW_SETTINGS_TABLE,
            user_id=user_id,
        )
        raise


async def save_user_review_settings(
    settings: UserReviewSettings,
) -> UserReviewSettings:
    """Create or update user review settings."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_REVIEW_SETTINGS_TABLE)
            await table.put_item(Item=settings.to_dynamodb_item())
            _log_dynamodb_success(
                "save_user_review_settings",
                table=USER_REVIEW_SETTINGS_TABLE,
                user_id=settings.user_id,
            )
            return settings
    except ClientError as e:
        _log_dynamodb_error(
            "save_user_review_settings",
            e,
            table=USER_REVIEW_SETTINGS_TABLE,
            user_id=settings.user_id,
        )
        raise
