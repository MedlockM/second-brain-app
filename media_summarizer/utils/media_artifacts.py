"""
Persistence helpers for canonical media artifacts.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from media_summarizer.core.models.media_artifact import MediaArtifactRecord
from media_summarizer.utils import database_async
from media_summarizer.utils.env import required_env

logger = logging.getLogger(__name__)

MEDIA_ARTIFACTS_TABLE = required_env("MEDIA_ARTIFACTS_TABLE")
MEDIA_ITEM_INDEX = os.environ.get(
    "MEDIA_ARTIFACTS_MEDIA_ITEM_INDEX", "media-item-index"
)
REQUEST_FINGERPRINT_INDEX = os.environ.get(
    "MEDIA_ARTIFACTS_REQUEST_FINGERPRINT_INDEX", "request-fingerprint-index"
)
GENERATION_FINGERPRINT_INDEX = os.environ.get(
    "MEDIA_ARTIFACTS_GENERATION_FINGERPRINT_INDEX",
    "generation-fingerprint-index",
)
REQUEST_POINTER_PREFIX = "request#"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_request_pointer_id(request_fingerprint: str) -> str:
    return f"{REQUEST_POINTER_PREFIX}{request_fingerprint}"


async def create_media_artifact(record: MediaArtifactRecord) -> MediaArtifactRecord:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(MEDIA_ARTIFACTS_TABLE)
        await table.put_item(
            Item=record.to_dynamodb_item(),
            ConditionExpression="attribute_not_exists(artifact_id)",
        )
        return record


async def update_media_artifact(record: MediaArtifactRecord) -> MediaArtifactRecord:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(MEDIA_ARTIFACTS_TABLE)
        await table.put_item(Item=record.to_dynamodb_item())
        return record


async def get_media_artifact_by_id(artifact_id: str) -> Optional[MediaArtifactRecord]:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(MEDIA_ARTIFACTS_TABLE)
        resp = await table.get_item(
            Key={"artifact_id": artifact_id},
            ConsistentRead=True,
        )
        item = resp.get("Item")
        if not item:
            return None
        return MediaArtifactRecord.from_dynamodb_item(item)


async def get_request_pointer(request_fingerprint: str) -> Optional[Dict[str, Any]]:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(MEDIA_ARTIFACTS_TABLE)
        resp = await table.get_item(
            Key={"artifact_id": build_request_pointer_id(request_fingerprint)},
            ConsistentRead=True,
        )
        return resp.get("Item")


async def reserve_request_pointer(
    *,
    request_fingerprint: str,
    artifact_id: str,
) -> bool:
    session = database_async.get_session()
    item = {
        "artifact_id": build_request_pointer_id(request_fingerprint),
        "item_type": "request_pointer",
        "request_fingerprint": request_fingerprint,
        "active_artifact_id": artifact_id,
        "status": "reserved",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    try:
        async with session.resource(
            "dynamodb",
            
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(MEDIA_ARTIFACTS_TABLE)
            await table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(artifact_id) OR #st = :failed",
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={":failed": "failed"},
            )
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise


async def save_request_pointer(
    *,
    request_fingerprint: str,
    artifact_id: str,
    status: str,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    session = database_async.get_session()
    pointer = {
        "artifact_id": build_request_pointer_id(request_fingerprint),
        "item_type": "request_pointer",
        "request_fingerprint": request_fingerprint,
        "active_artifact_id": artifact_id,
        "status": status,
        "created_at": created_at or _now_iso(),
        "updated_at": _now_iso(),
    }
    async with session.resource(
        "dynamodb",
        
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(MEDIA_ARTIFACTS_TABLE)
        await table.put_item(Item=pointer)
        return pointer


async def _query_all(
    *,
    index_name: str,
    key_name: str,
    key_value: str,
    scan_forward: bool = False,
    limit: Optional[int] = None,
) -> List[MediaArtifactRecord]:
    session = database_async.get_session()
    items = []
    async with session.resource(
        "dynamodb",
        
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(MEDIA_ARTIFACTS_TABLE)
        kwargs = {
            "IndexName": index_name,
            "KeyConditionExpression": Key(key_name).eq(key_value),
            "ScanIndexForward": scan_forward,
        }
        if limit is not None:
            kwargs["Limit"] = limit
        while True:
            resp = await table.query(**kwargs)
            items.extend(resp.get("Items", []))
            if limit is not None or "LastEvaluatedKey" not in resp:
                break
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
    return [MediaArtifactRecord.from_dynamodb_item(item) for item in items]


async def list_media_artifacts_by_media_item(media_item_id: str) -> List[MediaArtifactRecord]:
    return await _query_all(
        index_name=MEDIA_ITEM_INDEX,
        key_name="media_item_id",
        key_value=media_item_id,
        scan_forward=False,
    )


async def list_media_artifacts_by_generation_fingerprint(
    generation_fingerprint: str,
) -> List[MediaArtifactRecord]:
    return await _query_all(
        index_name=GENERATION_FINGERPRINT_INDEX,
        key_name="generation_fingerprint",
        key_value=generation_fingerprint,
        scan_forward=False,
    )


async def get_latest_media_artifact_by_request_fingerprint(
    request_fingerprint: str,
) -> Optional[MediaArtifactRecord]:
    rows = await _query_all(
        index_name=REQUEST_FINGERPRINT_INDEX,
        key_name="request_fingerprint",
        key_value=request_fingerprint,
        scan_forward=False,
        limit=1,
    )
    return rows[0] if rows else None


async def safe_list_media_artifacts_by_media_item(
    media_item_id: str,
) -> List[MediaArtifactRecord]:
    try:
        return await list_media_artifacts_by_media_item(media_item_id)
    except ClientError as exc:
        logger.warning("Failed to list media artifacts for %s: %s", media_item_id, exc)
        return []
