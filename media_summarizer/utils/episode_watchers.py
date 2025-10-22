"""
Utilities to manage episode watchers for pending episodes (Approach 2: event fan-out).

Schema (DynamoDB): episode_watchers
- PK: episode_guid (S)
- SK: user_id (S)
- Attributes: job_id (S), email (S), status (pending|emailed|failed), minutes_estimated (N), source (manual|spotify), created_at (ISO)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from botocore.exceptions import ClientError

from media_summarizer.utils import database_async

EPISODE_WATCHERS_TABLE = os.environ.get("EPISODE_WATCHERS_TABLE", "episode_watchers")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def add_watcher(
    *,
    episode_guid: str,
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
        table = await dynamodb.Table(EPISODE_WATCHERS_TABLE)
        try:
            await table.put_item(
                Item={
                    "episode_guid": episode_guid,
                    "user_id": user_id,
                    "email": email,
                    "job_id": job_id,
                    "status": "pending",
                    "minutes_estimated": int(minutes_estimated or 0),
                    "source": source,
                    "created_at": _now_iso(),
                },
                ConditionExpression="attribute_not_exists(episode_guid) AND attribute_not_exists(user_id)",
            )
            return True
        except ClientError as e:
            # Already exists
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise


async def list_watchers(episode_guid: str) -> List[Dict[str, Any]]:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        endpoint_url=database_async.AWS_ENDPOINT_URL,
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(EPISODE_WATCHERS_TABLE)
        # Partition key query
        resp = await table.query(
            KeyConditionExpression=database_async.Key("episode_guid").eq(episode_guid)
        )
        return resp.get("Items", [])


async def mark_watcher_emailed(episode_guid: str, user_id: str) -> None:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        endpoint_url=database_async.AWS_ENDPOINT_URL,
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(EPISODE_WATCHERS_TABLE)
        await table.update_item(
            Key={"episode_guid": episode_guid, "user_id": user_id},
            UpdateExpression="SET #st = :s, updated_at = :u",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":s": "emailed", ":u": _now_iso()},
        )


async def mark_watcher_failed(episode_guid: str, user_id: str, reason: Optional[str] = None) -> None:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        endpoint_url=database_async.AWS_ENDPOINT_URL,
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(EPISODE_WATCHERS_TABLE)
        update = "SET #st = :s, updated_at = :u"
        expr_names = {"#st": "status"}
        expr_vals = {":s": "failed", ":u": _now_iso()}
        if reason:
            update += ", failure_reason = :r"
            expr_vals[":r"] = reason
        await table.update_item(
            Key={"episode_guid": episode_guid, "user_id": user_id},
            UpdateExpression=update,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_vals,
        )
