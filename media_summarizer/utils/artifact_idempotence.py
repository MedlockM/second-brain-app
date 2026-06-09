"""
Generation lock helpers for artifact cache/idempotence.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from botocore.exceptions import ClientError

from media_summarizer.core.models.media_artifact import ArtifactGenerationLock
from media_summarizer.utils import database_async

logger = logging.getLogger(__name__)

ARTIFACT_IDEMPOTENCE_TABLE = os.environ.get(
    "ARTIFACT_IDEMPOTENCE_TABLE", "artifact_idempotence"
)


async def get_generation_lock(
    generation_fingerprint: str,
) -> Optional[ArtifactGenerationLock]:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(ARTIFACT_IDEMPOTENCE_TABLE)
        resp = await table.get_item(
            Key={"generation_fingerprint": generation_fingerprint},
            ConsistentRead=True,
        )
        item = resp.get("Item")
        if not item:
            return None
        return ArtifactGenerationLock.from_dynamodb_item(item)


async def reserve_generation(lock: ArtifactGenerationLock) -> bool:
    session = database_async.get_session()
    try:
        async with session.resource(
            "dynamodb",
            
            region_name=database_async.AWS_REGION,
        ) as dynamodb:
            table = await dynamodb.Table(ARTIFACT_IDEMPOTENCE_TABLE)
            await table.put_item(
                Item=lock.to_dynamodb_item(),
                ConditionExpression=(
                    "attribute_not_exists(generation_fingerprint) OR #st = :failed"
                ),
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={":failed": "failed"},
            )
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        raise


async def save_generation_lock(lock: ArtifactGenerationLock) -> ArtifactGenerationLock:
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(ARTIFACT_IDEMPOTENCE_TABLE)
        await table.put_item(Item=lock.to_dynamodb_item())
        return lock
