"""
CLI script to recompute forecast_minutes for all follows.

Usage:
  uv run python -m media_summarizer.scripts.recompute_forecasts

Options (env):
  - DEFAULT_FORECAST_DURATION_MINUTES (int, default 30)
  - FORECAST_FETCH_LIMIT (int, default 1000)

This walks the follows table and updates forecast_minutes and reserved_minutes for each item,
using the same forecast service and cache rules (cache is bypassed to force recomputation).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from media_summarizer.utils import minute_db
from media_summarizer.core.services.forecast_service import compute_monthly_minutes_forecast


async def _run():
    follows = []

    # Full table scan (dev/local). For production, replace with paginated/user-index strategies as needed.
    from media_summarizer.utils import database_async
    session = database_async.get_session()
    async with session.resource('dynamodb', region_name=database_async.AWS_REGION) as dynamodb:
        table = await dynamodb.Table(minute_db.FOLLOWS_TABLE)
        scan_kwargs = {}
        while True:
            resp = await table.scan(**scan_kwargs)
            items = resp.get('Items', [])
            for it in items:
                follows.append(it)
            last_key = resp.get('LastEvaluatedKey')
            if not last_key:
                break
            scan_kwargs['ExclusiveStartKey'] = last_key

    updated = 0
    now = datetime.now(timezone.utc)
    for it in follows:
        try:
            user_id = it.get('user_id')
            feed_id_str = it.get('feed_id')
            feed_id = int(feed_id_str) if isinstance(feed_id_str, str) and feed_id_str.isdigit() else None
            if not user_id or feed_id is None:
                continue
            forecast = await compute_monthly_minutes_forecast(feed_id=feed_id, now=now)
            minutes = int(forecast.get('minutes_per_month', 0))
            follow_obj = minute_db.Follow.from_dynamodb_item(it)
            follow_obj.forecast_minutes = minutes
            follow_obj.reserved_minutes = minutes
            await minute_db.upsert_follow(follow_obj)
            updated += 1
        except Exception:
            continue

    print(f"Recomputed forecasts for {updated} follow(s)")


def main():
    asyncio.run(_run())


if __name__ == "__main__":
    main()
