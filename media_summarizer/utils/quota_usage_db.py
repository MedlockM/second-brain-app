"""
DynamoDB access layer for consumption counters.

Only one thing is metered, the minute (see the validated consumption model in
docs/research/task-287-consumption-model/README.md): a minute of media we pay a
transcription provider to process, plus the flat conversions of §3.1 (a bought
caption set, five document pages, five collection sources).

Two tables:
- user_usage_monthly: the allowance counter, one row per user per billing period
  PK: user_id (S), SK: period (S)
  Attributes: minutes_used, cost_eur_estimated (observability only), last_updated,
              settled_jobs (SS, idempotency tokens of already-applied debits)

  The period is *not* a calendar month: it is the billing window the user's
  subscription is in, so the counter empties on the subscription anniversary the
  app already shows as `period_end`. `quota_enforcer.resolve_quota_period` owns
  the key format; this layer only stores what it is given.

  The same table carries one shared row keyed on PROVIDER_POOL_USER_ID, which
  counts provider spend across *all* users for safety-net layer 3. That row is
  keyed on the calendar month, because it tracks provider billing cycles rather
  than any user's subscription.

- user_usage_daily: the invisible burst guards of safety-net layer 2
  PK: user_id (S), SK: date (S, format YYYY-MM-DD)
  Attributes: minutes, items, documents, document_pages, generations
  TTL: ttl_epoch (auto-expire after 3 days)

All counter increments use atomic ADD operations to avoid race conditions.

`settled_jobs` grows by at most two tokens per transcription (the submission debit
and the Deepgram settlement). At the highest allowance a full period stays around
55 kB — well inside the 400 kB DynamoDB item limit — and the item is scoped to a
single period, so the set resets every billing window.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, Mapping, Optional

from botocore.exceptions import ClientError

from media_summarizer.utils import database_async
from media_summarizer.utils.env import required_env

logger = logging.getLogger(__name__)

USER_USAGE_MONTHLY_TABLE = required_env("USER_USAGE_MONTHLY_TABLE")
USER_USAGE_DAILY_TABLE = required_env("USER_USAGE_DAILY_TABLE")

# Reserved partition of the monthly table holding platform-wide provider spend.
# Not a user id, and it can never collide with one: user ids are UUIDs.
PROVIDER_POOL_USER_ID = "__provider_pools__"

# Daily burst-guard counters (layer 2). Keys are the keyword arguments callers
# pass, values are the DynamoDB attribute names.
_DAILY_COUNTERS: Mapping[str, str] = {
    "minutes": "minutes",
    "items": "items",
    "documents": "documents",
    "document_pages": "document_pages",
    "generations": "generations",
}

# Platform-wide provider pool counters (layer 3).
_POOL_COUNTERS: Mapping[str, str] = {
    "apify_results": "apify_results",
    "llamaparse_pages": "llamaparse_pages",
}


def _current_month() -> str:
    """Return the current calendar month in YYYY-MM format."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _current_date() -> str:
    """Return current date string in YYYY-MM-DD format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _daily_ttl_epoch() -> int:
    """Return TTL epoch (3 days from now) for daily records auto-cleanup."""
    return int((datetime.now(timezone.utc) + timedelta(days=3)).timestamp())


async def _atomic_add(
    *,
    table_name: str,
    key: Dict[str, str],
    additions: Dict[str, Any],
    set_fields: Dict[str, Any],
    idempotency_token: Optional[str],
    log_name: str,
) -> bool:
    """Apply an atomic ADD, optionally guarded by an idempotency token.

    When `idempotency_token` is provided the token is added to the item's
    `settled_jobs` string set in the same update, under a condition that rejects
    the write if the token is already there. That makes a redelivered SQS message
    (or a retried worker run) debit the counters exactly once.

    Returns True when the counters moved, False when the write was skipped
    because the token had already been applied (or there was nothing to add).
    """
    additions = {name: value for name, value in additions.items() if value}
    if not additions:
        return False

    expr_names: Dict[str, str] = {}
    expr_values: Dict[str, Any] = {}
    add_parts = []
    for index, (attribute, value) in enumerate(additions.items()):
        placeholder = f"#a{index}"
        value_ref = f":a{index}"
        expr_names[placeholder] = attribute
        expr_values[value_ref] = value
        add_parts.append(f"{placeholder} {value_ref}")

    condition_expr: Optional[str] = None
    if idempotency_token:
        expr_names["#sj"] = "settled_jobs"
        expr_values[":sj"] = {idempotency_token}
        expr_values[":token"] = idempotency_token
        add_parts.append("#sj :sj")
        condition_expr = "attribute_not_exists(#sj) OR NOT contains(#sj, :token)"

    set_parts = []
    for index, (attribute, value) in enumerate(set_fields.items()):
        placeholder = f"#s{index}"
        value_ref = f":s{index}"
        expr_names[placeholder] = attribute
        expr_values[value_ref] = value
        set_parts.append(f"{placeholder} = {value_ref}")

    update_expr = "ADD " + ", ".join(add_parts)
    if set_parts:
        update_expr += " SET " + ", ".join(set_parts)

    request: Dict[str, Any] = {
        "Key": key,
        "UpdateExpression": update_expr,
        "ExpressionAttributeNames": expr_names,
        "ExpressionAttributeValues": expr_values,
    }
    if condition_expr:
        request["ConditionExpression"] = condition_expr

    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        try:
            await table.update_item(**request)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                logger.info(
                    log_name,
                    extra={"key": key, "idempotency_token": idempotency_token},
                )
                return False
            raise

    return True


async def _get_item(table_name: str, key: Dict[str, str]) -> Optional[Dict[str, Any]]:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(table_name)
        response = await table.get_item(Key=key)
        item = response.get("Item")
        return item if item else None


# ---------------------------------------------------------------------------
# Monthly allowance counter
# ---------------------------------------------------------------------------


async def get_monthly_usage(user_id: str, period: str) -> Dict[str, Any]:
    """Return the consumption counters of one billing period.

    `cost_eur_estimated` is observability only: it is the measured provider spend
    of that period and nothing reads it to allow or refuse anything.
    """
    item = await _get_item(
        USER_USAGE_MONTHLY_TABLE, {"user_id": user_id, "period": period}
    )
    if item is None:
        return {"minutes_used": 0, "cost_eur_estimated": 0.0}
    return {
        "minutes_used": int(item.get("minutes_used", 0)),
        "cost_eur_estimated": float(item.get("cost_eur_estimated", 0)),
    }


async def increment_monthly_usage(
    user_id: str,
    period: str,
    *,
    minutes: int = 0,
    cost_eur: float = 0.0,
    idempotency_token: Optional[str] = None,
) -> bool:
    """Atomically debit minutes (and record measured cost) for one period.

    Creates the row if it does not exist. Returns True when the counters moved,
    False when the write was skipped as a duplicate.
    """
    additions: Dict[str, Any] = {}
    if minutes:
        additions["minutes_used"] = minutes
    if cost_eur:
        additions["cost_eur_estimated"] = Decimal(str(round(cost_eur, 4)))

    return await _atomic_add(
        table_name=USER_USAGE_MONTHLY_TABLE,
        key={"user_id": user_id, "period": period},
        additions=additions,
        set_fields={"last_updated": datetime.now(timezone.utc).isoformat()},
        idempotency_token=idempotency_token,
        log_name="quota.monthly_increment_skipped_duplicate",
    )


# ---------------------------------------------------------------------------
# Daily burst guards (safety-net layer 2)
# ---------------------------------------------------------------------------


async def get_daily_usage(user_id: str, date: Optional[str] = None) -> Dict[str, int]:
    """Return today's burst-guard counters (0 when nothing was recorded)."""
    if date is None:
        date = _current_date()

    item = await _get_item(USER_USAGE_DAILY_TABLE, {"user_id": user_id, "date": date})
    if item is None:
        return {name: 0 for name in _DAILY_COUNTERS}
    return {
        name: int(item.get(attribute, 0))
        for name, attribute in _DAILY_COUNTERS.items()
    }


async def increment_daily_usage(
    user_id: str,
    *,
    minutes: int = 0,
    items: int = 0,
    documents: int = 0,
    document_pages: int = 0,
    generations: int = 0,
    date: Optional[str] = None,
    idempotency_token: Optional[str] = None,
) -> bool:
    """Atomically increment today's burst-guard counters.

    Creates the row if it does not exist and sets its TTL. These counters never
    refuse anything on their own — `quota_enforcer` only reads them to decide
    whether an account is worth the owner's attention.
    """
    if date is None:
        date = _current_date()

    provided = {
        "minutes": minutes,
        "items": items,
        "documents": documents,
        "document_pages": document_pages,
        "generations": generations,
    }
    additions = {
        _DAILY_COUNTERS[name]: value for name, value in provided.items() if value
    }

    return await _atomic_add(
        table_name=USER_USAGE_DAILY_TABLE,
        key={"user_id": user_id, "date": date},
        additions=additions,
        set_fields={"ttl_epoch": _daily_ttl_epoch()},
        idempotency_token=idempotency_token,
        log_name="quota.daily_increment_skipped_duplicate",
    )


# ---------------------------------------------------------------------------
# Shared provider pools (safety-net layer 3)
# ---------------------------------------------------------------------------


async def get_provider_pool_usage(month: Optional[str] = None) -> Dict[str, int]:
    """Return this calendar month's provider spend across every user."""
    if month is None:
        month = _current_month()

    item = await _get_item(
        USER_USAGE_MONTHLY_TABLE,
        {"user_id": PROVIDER_POOL_USER_ID, "period": month},
    )
    if item is None:
        return {name: 0 for name in _POOL_COUNTERS}
    return {
        name: int(item.get(attribute, 0))
        for name, attribute in _POOL_COUNTERS.items()
    }


async def increment_provider_pool_usage(
    *,
    apify_results: int = 0,
    llamaparse_pages: int = 0,
    month: Optional[str] = None,
    idempotency_token: Optional[str] = None,
) -> bool:
    """Record provider spend against the shared monthly pool.

    Apify credit and LlamaParse credits are fixed monthly pools shared by every
    user, so no per-user allowance can protect them. This is the counter behind
    the alarm and the stop threshold of `provider_pools` in the pricing config.
    """
    if month is None:
        month = _current_month()

    provided = {
        "apify_results": apify_results,
        "llamaparse_pages": llamaparse_pages,
    }
    additions = {
        _POOL_COUNTERS[name]: value for name, value in provided.items() if value
    }

    return await _atomic_add(
        table_name=USER_USAGE_MONTHLY_TABLE,
        key={"user_id": PROVIDER_POOL_USER_ID, "period": month},
        additions=additions,
        set_fields={"last_updated": datetime.now(timezone.utc).isoformat()},
        idempotency_token=idempotency_token,
        log_name="quota.provider_pool_increment_skipped_duplicate",
    )
