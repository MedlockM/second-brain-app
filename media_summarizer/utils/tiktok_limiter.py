"""Global rate limiter helpers for TikTok outbound extraction calls."""

from __future__ import annotations

import logging
import os
import time

from media_summarizer.utils.distributed_rate_limiter import (
    acquire_global_slot,
    increment_fixed_window_counter,
)

logger = logging.getLogger(__name__)

_LIMIT_ENABLED = os.getenv("TIKTOK_RATE_LIMIT_ENABLED", "true").lower() not in {
    "0",
    "false",
    "no",
}
_PER_HOUR = max(1, int(os.getenv("TIKTOK_RATE_LIMIT_PER_HOUR", "100") or "100"))
_MIN_INTERVAL_SECONDS = float(
    os.getenv("TIKTOK_MIN_INTERVAL_SECONDS", "3") or "3"
)
_INTERVAL_MS = max(1, int(_MIN_INTERVAL_SECONDS * 1000))
_REDIS_URL = (os.getenv("TIKTOK_LIMITER_REDIS_URL") or "").strip()
_SLOT_KEY = os.getenv("TIKTOK_LIMITER_KEY", "tiktok:global:next_allowed_ms")
_SLOT_KEY_TTL_MS = int(os.getenv("TIKTOK_LIMITER_TTL_MS", "60000"))
_HOURLY_KEY_PREFIX = os.getenv(
    "TIKTOK_LIMITER_HOURLY_KEY_PREFIX", "tiktok:global:hour_bucket"
).strip() or "tiktok:global:hour_bucket"


class TikTokRateLimitExceeded(Exception):
    def __init__(self, *, limit_type: str, count: int, retry_after_seconds: int) -> None:
        super().__init__(limit_type)
        self.limit_type = limit_type
        self.count = count
        self.retry_after_seconds = retry_after_seconds


async def acquire_tiktok_slot() -> float:
    """
    Apply TikTok pacing and hourly quota protection.

    Returns:
        Seconds waited to satisfy the pacing limiter.
    """
    waited_seconds = await acquire_global_slot(
        enabled=_LIMIT_ENABLED,
        interval_ms=_INTERVAL_MS,
        redis_url=_REDIS_URL,
        redis_key=_SLOT_KEY,
        redis_key_ttl_ms=_SLOT_KEY_TTL_MS,
        limiter_name="TikTok",
        logger=logger,
    )
    if not _LIMIT_ENABLED:
        return waited_seconds

    hour_bucket = int(time.time() // 3600)
    hourly_key = f"{_HOURLY_KEY_PREFIX}:{hour_bucket}"
    count = await increment_fixed_window_counter(
        enabled=True,
        redis_url=_REDIS_URL,
        redis_key=hourly_key,
        window_seconds=3700,
        limiter_name="TikTok",
        logger=logger,
    )
    if count > _PER_HOUR:
        retry_after_seconds = max(
            1,
            int((((hour_bucket + 1) * 3600) - time.time())),
        )
        raise TikTokRateLimitExceeded(
            limit_type="hourly_quota_exceeded",
            count=count,
            retry_after_seconds=retry_after_seconds,
        )

    return waited_seconds
