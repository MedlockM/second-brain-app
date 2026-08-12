"""
Subscriptions, Follows, and Feed Forecasts data access on DynamoDB (async, aioboto3),
using the same session config as database_async.

CRUD operations for:
- Subscriptions
- Follows (forecast/reservations)
- Feed Forecasts (shared cache)

GSIs expected:
- user-index on user_id (subscriptions, follows)

Note: Table creation and index management are handled outside this module (infra scripts/terraform).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from media_summarizer.core.models.billing import Follow, Subscription
from media_summarizer.utils import database_async
from media_summarizer.utils.env import required_env

# Table names (overridable via env)
SUBSCRIPTIONS_TABLE = required_env("SUBSCRIPTIONS_TABLE")
FOLLOWS_TABLE = required_env("FOLLOWS_TABLE")
FEED_FORECASTS_TABLE = required_env("FEED_FORECASTS_TABLE")


# ---------- Subscriptions ----------


async def create_subscription(subscription: Subscription) -> Subscription:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(SUBSCRIPTIONS_TABLE)
        await table.put_item(
            Item=subscription.to_dynamodb_item(),
            ConditionExpression="attribute_not_exists(id)",
        )
        return subscription


async def get_subscriptions_by_user_id(user_id: str) -> List[Subscription]:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(SUBSCRIPTIONS_TABLE)
        response = await table.query(
            IndexName="user-index", KeyConditionExpression=Key("user_id").eq(user_id)
        )
        items = response.get("Items", [])
        return [Subscription.from_dynamodb_item(it) for it in items]


async def update_subscription(subscription: Subscription) -> Subscription:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(SUBSCRIPTIONS_TABLE)
        await table.put_item(Item=subscription.to_dynamodb_item())
        return subscription


# ---------- Follows ----------


async def upsert_follow(follow: Follow) -> Follow:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(FOLLOWS_TABLE)
        await table.put_item(Item=follow.to_dynamodb_item())
        return follow


async def get_follows_by_user_id(user_id: str) -> List[Follow]:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(FOLLOWS_TABLE)
        # Table is modeled with partition key user_id (and range feed_id)
        response = await table.query(KeyConditionExpression=Key("user_id").eq(user_id))
        items = response.get("Items", [])
        return [Follow.from_dynamodb_item(it) for it in items]


# ---------- Feed Forecasts (shared cache) ----------


async def get_feed_forecast(feed_id: str, month_key: str) -> Optional[Dict[str, Any]]:
    """Return forecast cache row for (feed_id, month_key) or None."""
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(FEED_FORECASTS_TABLE)
        try:
            resp = await table.get_item(
                Key={"feed_id": str(feed_id), "month_key": month_key}
            )
            item = resp.get("Item")
            return item or None
        except ClientError:
            return None


async def upsert_feed_forecast(
    feed_id: str, month_key: str, forecast: Dict[str, Any]
) -> bool:
    """Upsert forecast cache for (feed_id, month_key).

    'forecast' should contain keys: minutes_per_month, basis, coverage_months,
    computed_at, expires_at. Returns True on success, False if table missing.
    """
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(FEED_FORECASTS_TABLE)
        try:
            from datetime import datetime, timezone

            now_iso = datetime.now(timezone.utc).isoformat()
            exp_iso = forecast.get("expires_at")
            ttl_value = None
            try:
                if exp_iso:
                    from datetime import datetime

                    ttl_value = int(datetime.fromisoformat(exp_iso).timestamp())
            except Exception:
                ttl_value = None
            item = {
                "feed_id": str(feed_id),
                "month_key": month_key,
                "minutes_per_month": int(forecast.get("minutes_per_month", 0)),
                "basis": str(forecast.get("basis", "")),
                "coverage_months": int(forecast.get("coverage_months", 0)),
                "computed_at": forecast.get("last_computed_at") or now_iso,
                "expires_at": exp_iso or "",
                "created_at": now_iso,
                "updated_at": now_iso,
            }
            if ttl_value is not None:
                item["ttl"] = ttl_value
            await table.put_item(Item=item)
            return True
        except ClientError:
            return False


async def delete_follow(user_id: str, feed_id: str) -> bool:
    """Delete a follow item by (user_id, feed_id)."""
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(FOLLOWS_TABLE)
        try:
            await table.delete_item(Key={"user_id": user_id, "feed_id": feed_id})
            return True
        except ClientError:
            return False
