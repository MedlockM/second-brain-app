"""
DynamoDB access layer for the pricing_config table.

The table stores all dynamic pricing/quota parameters as key-value pairs.
Each item has:
  - config_key (S): unique identifier for the parameter (partition key)
  - config_value (S): JSON-encoded value
  - updated_at (S): ISO8601 timestamp of last update

This allows runtime modification of all pricing parameters without redeployment.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from media_summarizer.utils import database_async
from media_summarizer.utils.env import required_env

logger = logging.getLogger(__name__)

PRICING_CONFIG_TABLE = required_env("PRICING_CONFIG_TABLE")


async def get_all_config() -> Dict[str, Any]:
    """Read all pricing config items and return as a dict of key -> parsed value."""
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(PRICING_CONFIG_TABLE)
        response = await table.scan()
        items = response.get("Items", [])
        result: Dict[str, Any] = {}
        for item in items:
            key = item["config_key"]
            raw_value = item.get("config_value", "null")
            try:
                result[key] = json.loads(raw_value)
            except (json.JSONDecodeError, TypeError):
                result[key] = raw_value
        return result


async def get_config_value(config_key: str) -> Optional[Any]:
    """Read a single config value by key."""
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(PRICING_CONFIG_TABLE)
        response = await table.get_item(Key={"config_key": config_key})
        item = response.get("Item")
        if not item:
            return None
        raw_value = item.get("config_value", "null")
        try:
            return json.loads(raw_value)
        except (json.JSONDecodeError, TypeError):
            return raw_value


async def put_config_value(config_key: str, value: Any) -> None:
    """Write (create or update) a single config value."""
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(PRICING_CONFIG_TABLE)
        await table.put_item(
            Item={
                "config_key": config_key,
                "config_value": json.dumps(value),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )


async def put_config_batch(items: Dict[str, Any]) -> None:
    """Write multiple config key-value pairs in batch."""
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(PRICING_CONFIG_TABLE)
        now = datetime.now(timezone.utc).isoformat()
        async with table.batch_writer() as batch:
            for key, value in items.items():
                await batch.put_item(
                    Item={
                        "config_key": key,
                        "config_value": json.dumps(value),
                        "updated_at": now,
                    }
                )


async def delete_config_value(config_key: str) -> None:
    """Delete a single config value by key."""
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(PRICING_CONFIG_TABLE)
        await table.delete_item(Key={"config_key": config_key})
