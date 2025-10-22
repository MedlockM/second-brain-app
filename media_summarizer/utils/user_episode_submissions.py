"""
User episode submissions tracking utilities using DynamoDB.

Purpose: prevent re-submitting the same episode for the same user when
scanning external sources (e.g., Spotify Tosum playlist).

Table schema:
- Env var: USER_EPISODE_SUBMISSIONS_TABLE (default "user_episode_submissions")
- PK: user_id (S)
- SK: episode_guid (S)
- Attributes: submitted_at (ISO), job_id (S), source (S)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from botocore.exceptions import ClientError

from media_summarizer.utils import database_async

USER_EPISODE_SUBMISSIONS_TABLE = os.environ.get(
    "USER_EPISODE_SUBMISSIONS_TABLE", "user_episode_submissions"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def has_user_already_submitted(user_id: str, episode_guid: str) -> bool:
    """Return True if this user has already submitted this episode GUID."""
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        endpoint_url=database_async.AWS_ENDPOINT_URL,
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(USER_EPISODE_SUBMISSIONS_TABLE)
        resp = await table.get_item(
            Key={
                "user_id": user_id,
                "episode_guid": episode_guid,
            }
        )
        return "Item" in resp


async def mark_user_submission(
    *, user_id: str, episode_guid: str, job_id: str, source: str
) -> bool:
    """
    Record that a user submitted an episode.

    Returns True if new record, False if it already exists.
    """
    item = {
        "user_id": user_id,
        "episode_guid": episode_guid,
        "submitted_at": _now_iso(),
        "job_id": job_id,
        "source": source,
    }
    session = database_async.get_session()
    try:
        async with session.resource(
            "dynamodb",
            endpoint_url=database_async.AWS_ENDPOINT_URL,
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(USER_EPISODE_SUBMISSIONS_TABLE)
            await table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(user_id)",
            )
        return True
    except ClientError as e:
        # If already exists, treat as no-op
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise
