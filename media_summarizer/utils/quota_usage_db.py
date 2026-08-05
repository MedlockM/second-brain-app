"""
DynamoDB access layer for quota usage counters.

Two tables:
- user_usage_monthly: monthly counters for hard cap enforcement
  PK: user_id (S), SK: period (S, format YYYY-MM)
  Attributes: audio_minutes_used, articles_count, documents_count,
              youtube_count, cost_eur_estimated, last_updated

- user_usage_daily: daily counters for rate limit enforcement
  PK: user_id (S), SK: date (S, format YYYY-MM-DD)
  Attributes: audio_imports, text_imports, document_imports,
              last_import_timestamps (list of recent timestamps for per-minute checks)
  TTL: ttl_epoch (auto-expire after 3 days)

All counter increments use atomic ADD operations to avoid race conditions.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from media_summarizer.utils import database_async

logger = logging.getLogger(__name__)

USER_USAGE_MONTHLY_TABLE = os.environ.get("USER_USAGE_MONTHLY_TABLE", "user_usage_monthly")
USER_USAGE_DAILY_TABLE = os.environ.get("USER_USAGE_DAILY_TABLE", "user_usage_daily")


def _current_period() -> str:
    """Return current month period string in YYYY-MM format."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _current_date() -> str:
    """Return current date string in YYYY-MM-DD format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _daily_ttl_epoch() -> int:
    """Return TTL epoch (3 days from now) for daily records auto-cleanup."""
    return int((datetime.now(timezone.utc) + timedelta(days=3)).timestamp())


async def get_monthly_usage(user_id: str, period: Optional[str] = None) -> Dict[str, Any]:
    """
    Get monthly usage counters for a user.
    Returns a dict with counter values (defaults to 0 if no record exists).
    """
    if period is None:
        period = _current_period()

    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(USER_USAGE_MONTHLY_TABLE)
        response = await table.get_item(
            Key={"user_id": user_id, "period": period}
        )
        item = response.get("Item")
        if not item:
            return {
                "audio_minutes_used": 0,
                "articles_count": 0,
                "documents_count": 0,
                "youtube_count": 0,
                "cost_eur_estimated": 0.0,
            }
        return {
            "audio_minutes_used": int(item.get("audio_minutes_used", 0)),
            "articles_count": int(item.get("articles_count", 0)),
            "documents_count": int(item.get("documents_count", 0)),
            "youtube_count": int(item.get("youtube_count", 0)),
            "cost_eur_estimated": float(item.get("cost_eur_estimated", 0)),
        }


async def increment_monthly_usage(
    user_id: str,
    *,
    audio_minutes: int = 0,
    articles: int = 0,
    documents: int = 0,
    youtube: int = 0,
    cost_eur: float = 0.0,
    period: Optional[str] = None,
) -> None:
    """
    Atomically increment monthly usage counters.
    Creates the record if it does not exist.
    """
    if period is None:
        period = _current_period()

    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(USER_USAGE_MONTHLY_TABLE)

        update_parts = []
        expr_names = {}
        expr_values = {}

        if audio_minutes:
            update_parts.append("#am :am")
            expr_names["#am"] = "audio_minutes_used"
            expr_values[":am"] = audio_minutes
        if articles:
            update_parts.append("#ac :ac")
            expr_names["#ac"] = "articles_count"
            expr_values[":ac"] = articles
        if documents:
            update_parts.append("#dc :dc")
            expr_names["#dc"] = "documents_count"
            expr_values[":dc"] = documents
        if youtube:
            update_parts.append("#yc :yc")
            expr_names["#yc"] = "youtube_count"
            expr_values[":yc"] = youtube
        if cost_eur:
            update_parts.append("#ce :ce")
            expr_names["#ce"] = "cost_eur_estimated"
            expr_values[":ce"] = Decimal(str(round(cost_eur, 4)))

        if not update_parts:
            return

        # Always update last_updated
        now_iso = datetime.now(timezone.utc).isoformat()

        update_expr = "ADD " + ", ".join(update_parts) + " SET #lu = :lu"
        expr_names["#lu"] = "last_updated"
        expr_values[":lu"] = now_iso

        await table.update_item(
            Key={"user_id": user_id, "period": period},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )


async def get_daily_usage(user_id: str, date: Optional[str] = None) -> Dict[str, Any]:
    """
    Get daily usage counters for a user.
    Returns a dict with counter values (defaults to 0 if no record exists).
    """
    if date is None:
        date = _current_date()

    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(USER_USAGE_DAILY_TABLE)
        response = await table.get_item(
            Key={"user_id": user_id, "date": date}
        )
        item = response.get("Item")
        if not item:
            return {
                "audio_imports": 0,
                "text_imports": 0,
                "document_imports": 0,
                "last_text_import_ts": [],
                "last_api_call_ts": [],
            }
        return {
            "audio_imports": int(item.get("audio_imports", 0)),
            "text_imports": int(item.get("text_imports", 0)),
            "document_imports": int(item.get("document_imports", 0)),
            "last_text_import_ts": item.get("last_text_import_ts", []),
            "last_api_call_ts": item.get("last_api_call_ts", []),
        }


async def increment_daily_usage(
    user_id: str,
    *,
    audio_imports: int = 0,
    text_imports: int = 0,
    document_imports: int = 0,
    date: Optional[str] = None,
) -> None:
    """
    Atomically increment daily usage counters.
    Creates the record if it does not exist. Sets TTL for auto-cleanup.
    """
    if date is None:
        date = _current_date()

    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(USER_USAGE_DAILY_TABLE)

        update_parts = []
        expr_names = {}
        expr_values = {}

        if audio_imports:
            update_parts.append("#ai :ai")
            expr_names["#ai"] = "audio_imports"
            expr_values[":ai"] = audio_imports
        if text_imports:
            update_parts.append("#ti :ti")
            expr_names["#ti"] = "text_imports"
            expr_values[":ti"] = text_imports
        if document_imports:
            update_parts.append("#di :di")
            expr_names["#di"] = "document_imports"
            expr_values[":di"] = document_imports

        if not update_parts:
            return

        # Set TTL on every write
        ttl_val = _daily_ttl_epoch()
        update_expr = "ADD " + ", ".join(update_parts) + " SET #ttl = :ttl"
        expr_names["#ttl"] = "ttl_epoch"
        expr_values[":ttl"] = ttl_val

        await table.update_item(
            Key={"user_id": user_id, "date": date},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )


async def record_import_timestamp(
    user_id: str,
    *,
    field: str,
    date: Optional[str] = None,
) -> None:
    """
    Append current timestamp to a list field (for per-minute rate tracking).
    Only keeps the last 120 entries (2 minutes of per-second imports max).

    field: one of 'last_text_import_ts' or 'last_api_call_ts'
    """
    if date is None:
        date = _current_date()

    now_ts = int(time.time())

    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(USER_USAGE_DAILY_TABLE)

        # Use list_append to add the timestamp, creating the list if absent
        await table.update_item(
            Key={"user_id": user_id, "date": date},
            UpdateExpression=(
                "SET #f = list_append(if_not_exists(#f, :empty), :ts), "
                "#ttl = :ttl"
            ),
            ExpressionAttributeNames={
                "#f": field,
                "#ttl": "ttl_epoch",
            },
            ExpressionAttributeValues={
                ":ts": [now_ts],
                ":empty": [],
                ":ttl": _daily_ttl_epoch(),
            },
        )
