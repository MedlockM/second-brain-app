import math
from datetime import datetime, timezone, timedelta

import pytest

# Mark entire module as forecast-only
pytestmark = pytest.mark.forecast

from media_summarizer.core.services import forecast_service as fs


def _ts(y, m, d):
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())


def _mk_item(guid: str, dt: datetime, duration_s: int | None):
    return {
        "guid": guid,
        "datePublished": int(dt.replace(tzinfo=timezone.utc).timestamp()),
        "duration": duration_s,
    }


@pytest.mark.asyncio
async def test_forecast_less_than_one_month(monkeypatch):
    now = datetime(2025, 10, 6, tzinfo=timezone.utc)
    m0_first = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    # Episodes only in current month
    items = [
        _mk_item("a", m0_first + timedelta(days=1), 600),   # 10 min
        _mk_item("b", m0_first + timedelta(days=2), 61),    # 2 min (ceil)
        _mk_item("c", m0_first + timedelta(days=3), None),  # imputed
    ]

    async def fake_get_episodes_by_feed_id(feed_id: int, max_results: int = 10, since=None, http_client=None):
        return {"items": items, "status": "true", "count": len(items)}

    monkeypatch.setattr(
        fs.podcast_index, "get_episodes_by_feed_id", fake_get_episodes_by_feed_id
    )

    res = await fs.compute_monthly_minutes_forecast(feed_id=123, now=now)
    assert res["basis"] == "sum_current_month"
    # Known minutes: 10 + ceil(61/60)=2 -> 12; unknown imputed by median of known = median(10,2)=6 -> total 18
    assert res["minutes_per_month"] == 18
    assert res["coverage_months"] == 1


@pytest.mark.asyncio
async def test_forecast_two_months_average(monkeypatch):
    now = datetime(2025, 10, 6, tzinfo=timezone.utc)
    m0_first = datetime(2025, 10, 1, tzinfo=timezone.utc)
    m1_first = datetime(2025, 9, 1, tzinfo=timezone.utc)

    items = [
        _mk_item("a", m0_first + timedelta(days=1), 600),  # 10 min
        _mk_item("b", m1_first + timedelta(days=1), 300),  # 5 min
    ]

    async def fake_get_episodes_by_feed_id(feed_id: int, max_results: int = 10, since=None, http_client=None):
        return {"items": items, "status": "true", "count": len(items)}

    monkeypatch.setattr(
        fs.podcast_index, "get_episodes_by_feed_id", fake_get_episodes_by_feed_id
    )

    res = await fs.compute_monthly_minutes_forecast(feed_id=123, now=now)
    assert res["basis"] == "avg_last_2_months"
    assert res["coverage_months"] == 2
    # average of (10,5) = 7.5 -> ceil = 8
    assert res["minutes_per_month"] == 8


@pytest.mark.asyncio
async def test_forecast_four_months_average(monkeypatch):
    now = datetime(2025, 10, 6, tzinfo=timezone.utc)
    m0_first = datetime(2025, 10, 1, tzinfo=timezone.utc)
    m1_first = datetime(2025, 9, 1, tzinfo=timezone.utc)
    m2_first = datetime(2025, 8, 1, tzinfo=timezone.utc)
    m3_first = datetime(2025, 7, 1, tzinfo=timezone.utc)

    items = [
        _mk_item("a", m0_first + timedelta(days=1), 600),  # 10
        _mk_item("b", m1_first + timedelta(days=1), 300),  # 5
        _mk_item("c", m2_first + timedelta(days=1), 60),   # 1
        _mk_item("d", m3_first + timedelta(days=1), 120),  # 2
    ]

    async def fake_get_episodes_by_feed_id(feed_id: int, max_results: int = 10, since=None, http_client=None):
        return {"items": items, "status": "true", "count": len(items)}

    monkeypatch.setattr(
        fs.podcast_index, "get_episodes_by_feed_id", fake_get_episodes_by_feed_id
    )

    res = await fs.compute_monthly_minutes_forecast(feed_id=123, now=now)
    assert res["basis"] == "avg_last_4_months"
    assert res["coverage_months"] == 4
    # average of (10,5,1,2) = 4.5 -> ceil = 5
    assert res["minutes_per_month"] == 5
