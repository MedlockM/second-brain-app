"""
Utilities to manage media watchers for pending media items (event fan-out).

NOTE: The underlying DynamoDB table still uses legacy column name "episode_guid"
as the partition key. The Python API uses "media_key" as the media-agnostic name.

Schema (DynamoDB): episode_watchers (legacy table name)
- PK: episode_guid (S) [legacy column name, maps to media_key]
- SK: user_id (S)
- Attributes: job_id (S), email (S), status (pending|emailed|failed), minutes_estimated (N), source (manual|spotify), created_at (ISO)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from botocore.exceptions import ClientError

from media_summarizer.utils import database_async

MEDIA_WATCHERS_TABLE = os.environ.get(
    "MEDIA_WATCHERS_TABLE",
    os.environ.get("EPISODE_WATCHERS_TABLE", "episode_watchers"),
)

# Legacy DynamoDB column name for the partition key
_PK_COLUMN = "episode_guid"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def add_watcher(
    *,
    media_key: str,
    user_id: str,
    email: str,
    job_id: str,
    minutes_estimated: int,
    source: str,
) -> bool:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        endpoint_url=database_async.AWS_ENDPOINT_URL,
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(MEDIA_WATCHERS_TABLE)
        try:
            await table.put_item(
                Item={
                    _PK_COLUMN: media_key,
                    "user_id": user_id,
                    "email": email,
                    "job_id": job_id,
                    "status": "pending",
                    "minutes_estimated": int(minutes_estimated or 0),
                    "source": source,
                    "created_at": _now_iso(),
                },
                ConditionExpression=f"attribute_not_exists({_PK_COLUMN}) AND attribute_not_exists(user_id)",
            )
            return True
        except ClientError as e:
            # Already exists
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise


async def list_watchers(media_key: str) -> List[Dict[str, Any]]:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        endpoint_url=database_async.AWS_ENDPOINT_URL,
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(MEDIA_WATCHERS_TABLE)
        # Partition key query
        resp = await table.query(
            KeyConditionExpression=database_async.Key(_PK_COLUMN).eq(media_key)
        )
        return resp.get("Items", [])


async def mark_watcher_emailed(media_key: str, user_id: str) -> None:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        endpoint_url=database_async.AWS_ENDPOINT_URL,
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(MEDIA_WATCHERS_TABLE)
        await table.update_item(
            Key={_PK_COLUMN: media_key, "user_id": user_id},
            UpdateExpression="SET #st = :s, updated_at = :u",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":s": "emailed", ":u": _now_iso()},
        )


async def mark_watcher_failed(media_key: str, user_id: str, reason: Optional[str] = None) -> None:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        endpoint_url=database_async.AWS_ENDPOINT_URL,
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(MEDIA_WATCHERS_TABLE)
        update = "SET #st = :s, updated_at = :u"
        expr_names = {"#st": "status"}
        expr_vals = {":s": "failed", ":u": _now_iso()}
        if reason:
            update += ", failure_reason = :r"
            expr_vals[":r"] = reason
        await table.update_item(
            Key={_PK_COLUMN: media_key, "user_id": user_id},
            UpdateExpression=update,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_vals,
        )
