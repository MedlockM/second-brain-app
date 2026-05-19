"""Distributed rate limiter for PodcastIndex outbound calls."""

from __future__ import annotations

import logging
import os
from media_summarizer.utils.distributed_rate_limiter import acquire_global_slot

logger = logging.getLogger(__name__)

_LIMIT_ENABLED = os.getenv("PODCASTINDEX_RATE_LIMIT_ENABLED", "true").lower() not in {
    "0",
    "false",
    "no",
}
_RPS = float(os.getenv("PODCASTINDEX_RATE_LIMIT_RPS", "1") or "1")
_INTERVAL_MS = max(1, int(1000 / max(_RPS, 0.001)))
_REDIS_URL = (os.getenv("PODCASTINDEX_LIMITER_REDIS_URL") or "").strip()
_REDIS_KEY = os.getenv(
    "PODCASTINDEX_LIMITER_KEY", "podcastindex:global:next_allowed_ms"
)
_REDIS_KEY_TTL_MS = int(os.getenv("PODCASTINDEX_LIMITER_TTL_MS", "60000"))


async def acquire_podcastindex_slot() -> float:
    """
    Reserve a global PodcastIndex call slot and wait until it is due.

    Returns:
        Wait time in seconds applied before the caller can perform outbound call.
    """
    return await acquire_global_slot(
        enabled=_LIMIT_ENABLED,
        interval_ms=_INTERVAL_MS,
        redis_url=_REDIS_URL,
        redis_key=_REDIS_KEY,
        redis_key_ttl_ms=_REDIS_KEY_TTL_MS,
        limiter_name="PodcastIndex",
        logger=logger,
    )
