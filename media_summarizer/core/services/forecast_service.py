"""
Forecast service — compute per-podcast monthly minutes forecast using Podcast Index.

Rules implemented:
- If ≥ 4 months of history: average of last 4 calendar months
- If = 3 months: average of last 3 months
- If 1–2 months: average of last 2 months
- If < 1 month: sum of current month only

Notes:
- Episodes are grouped by calendar month (UTC) using datePublished.
- Per-episode minutes = ceil(duration_seconds / 60). If duration is missing, impute using
  the median minutes of the month; if unavailable, the global median across the 4-month window;
  else fallback to DEFAULT_FORECAST_DURATION_MINUTES (env, default 30).
- Caching: in-memory cache per (feed_id, month_key) until the first day of next month (UTC).
  This is a simple optimization for dev/local; multi-instance deployments should back this with
  a shared store (e.g., DynamoDB) if necessary.
"""
from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from statistics import median
from typing import Any, Dict, List, Optional

from media_summarizer.utils import podcast_index

DEFAULT_FORECAST_DURATION_MINUTES = int(os.environ.get("DEFAULT_FORECAST_DURATION_MINUTES", "30"))
FORECAST_FETCH_LIMIT = int(os.environ.get("FORECAST_FETCH_LIMIT", "1000"))

# Primary cache is DynamoDB (feed_forecasts table). No in-process cache retained to keep behavior consistent across instances.


def _first_day_of_month_utc(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, 1, tzinfo=timezone.utc)


def _add_months(dt: datetime, months: int) -> datetime:
    # naive month arithmetic: adjust year and month; keep day=1 for stability
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    return datetime(year, month, 1, tzinfo=timezone.utc)


def _month_key(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def _months_between(start: datetime, end: datetime) -> int:
    """Return number of calendar month boundaries from start (inclusive) to end (exclusive).
    Example: 2025-07-01 to 2025-10-01 -> 3.
    """
    return (end.year - start.year) * 12 + (end.month - start.month)


async def compute_monthly_minutes_forecast(feed_id: int, *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Compute minutes per month forecast for a podcast feed.

    Returns dict with keys: minutes_per_month, basis, coverage_months, last_computed_at.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    first_day_cur = _first_day_of_month_utc(now)
    first_day_m3 = _add_months(first_day_cur, -3)
    since_ts = int(first_day_m3.timestamp())

    # Fetch episodes (up to 4 months back)
    data = await podcast_index.get_episodes_by_feed_id(
        feed_id=feed_id, max_results=min(FORECAST_FETCH_LIMIT, 1000), since=since_ts
    )

    items: List[Dict[str, Any]] = data.get("items", []) if isinstance(data, dict) else []

    # Prepare calendar months: M0 (current) to M-3
    months = [first_day_cur, _add_months(first_day_cur, -1), _add_months(first_day_cur, -2), _add_months(first_day_cur, -3)]
    month_keys = [_month_key(m) for m in months]

    # Map month_key -> list of per-episode minutes (None for unknowns)
    per_month: Dict[str, List[Optional[int]]] = {mk: [] for mk in month_keys}

    seen_guids = set()
    earliest_dt: Optional[datetime] = None

    for ep in items:
        guid = ep.get("guid")
        if guid:
            if guid in seen_guids:
                continue
            seen_guids.add(guid)

        ts = ep.get("datePublished")
        if not isinstance(ts, int):
            continue
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        if earliest_dt is None or dt < earliest_dt:
            earliest_dt = dt

        mk = _month_key(datetime(dt.year, dt.month, 1, tzinfo=timezone.utc))
        if mk not in per_month:
            # ignore outside the 4-month window
            continue

        # minutes per episode
        dur = ep.get("duration")
        minutes = math.ceil(int(dur) / 60) if dur is not None and int(dur) > 0 else None
        per_month[mk].append(minutes)

    # Imputation for missing durations
    all_known = [m for arr in per_month.values() for m in arr if m is not None]
    global_median = int(median(all_known)) if all_known else DEFAULT_FORECAST_DURATION_MINUTES

    totals: Dict[str, int] = {}
    for mk in month_keys:
        arr = per_month.get(mk, [])
        known = [m for m in arr if m is not None]
        unknown_count = len(arr) - len(known)
        month_median = int(median(known)) if known else global_median
        totals[mk] = int(sum(known) + unknown_count * month_median)

    # Determine basis 4/3/2/<1 using calendar months (including zero months)
    if earliest_dt and earliest_dt >= first_day_cur:
        basis = "sum_current_month"
        value = totals[month_keys[0]]
        coverage = 1
    else:
        # Align with spec semantics using inclusive month buckets:
        # earliest in:
        #   - current month          -> sum current month (handled above)
        #   - previous month         -> avg last 2 months
        #   - two months ago         -> avg last 3 months
        #   - three months ago (or earlier) -> avg last 4 months
        first_day_m1 = _add_months(first_day_cur, -1)
        first_day_m2 = _add_months(first_day_cur, -2)
        first_day_m3 = _add_months(first_day_cur, -3)
        if earliest_dt and earliest_dt >= first_day_m1:
            sel = month_keys[:2]
            basis = "avg_last_2_months"
            coverage = 2
        elif earliest_dt and earliest_dt >= first_day_m2:
            sel = month_keys[:3]
            basis = "avg_last_3_months"
            coverage = 3
        else:
            sel = month_keys[:4]
            basis = "avg_last_4_months"
            coverage = 4
        value = math.ceil(sum(totals[k] for k in sel) / len(sel)) if sel else 0

    result = {
        "minutes_per_month": int(value),
        "basis": basis,
        "coverage_months": coverage,
        "last_computed_at": now.isoformat(),
    }
    return result


async def get_forecast_with_cache(feed_id: int, *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Return forecast for the given feed_id using an in-memory cache that expires at the
    first day of next month (UTC). Useful to avoid repeated PodcastIndex calls when users
    open the same podcast frequently within the same month.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    first_day_cur = _first_day_of_month_utc(now)
    first_day_next = _add_months(first_day_cur, 1)
    month_key = _month_key(first_day_cur)
    cache_key = (feed_id, month_key)

    # 1) DynamoDB cache (shared)
    from media_summarizer.utils import minute_db
    mk = month_key
    db_item = await minute_db.get_feed_forecast(str(feed_id), mk)
    if db_item:
        # Validate expiry if available
        exp_iso = db_item.get("expires_at")
        try:
            if exp_iso:
                exp_dt = datetime.fromisoformat(exp_iso)
                if exp_dt > now:
                    return {
                        "minutes_per_month": int(db_item.get("minutes_per_month", 0)),
                        "basis": db_item.get("basis", ""),
                        "coverage_months": int(db_item.get("coverage_months", 0)),
                        "last_computed_at": db_item.get("computed_at", now.isoformat()),
                    }
        except Exception:
            # If parsing fails, ignore and recompute below
            pass

    # 2) Compute and persist to DynamoDB
    result = await compute_monthly_minutes_forecast(feed_id=feed_id, now=now)
    # set expires_at to first day of next month
    to_store = {**result, "expires_at": first_day_next.isoformat()}
    try:
        await minute_db.upsert_feed_forecast(str(feed_id), mk, to_store)
    except Exception:
        pass
    return result


