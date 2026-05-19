"""Reusable distributed rate limiting primitives with Redis and local fallback."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

try:
    from redis import asyncio as redis_asyncio
except Exception:  # pragma: no cover - optional dependency at import-time
    redis_asyncio = None


_REDIS_CLIENTS: dict[str, Any] = {}
_LOCAL_SLOT_LOCKS: dict[str, asyncio.Lock] = {}
_LOCAL_SLOT_STATE: dict[str, int] = {}
_LOCAL_COUNTER_LOCKS: dict[str, asyncio.Lock] = {}
_LOCAL_COUNTER_STATE: dict[str, tuple[int, float]] = {}

_RESERVE_SLOT_LUA = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local interval_ms = tonumber(ARGV[2])
local ttl_ms = tonumber(ARGV[3])

local next_allowed = tonumber(redis.call("GET", key) or "0")
local scheduled = now_ms
if next_allowed > now_ms then
  scheduled = next_allowed
end

local new_next = scheduled + interval_ms
redis.call("SET", key, new_next, "PX", ttl_ms)
return scheduled
"""


def _now_ms() -> int:
    return int(time.time() * 1000)


async def _get_redis_client(redis_url: str):
    client = _REDIS_CLIENTS.get(redis_url)
    if client is not None:
        return client
    if not redis_url or redis_asyncio is None:
        return None

    client = redis_asyncio.from_url(
        redis_url,
        decode_responses=True,
    )
    _REDIS_CLIENTS[redis_url] = client
    return client


def _slot_lock(key: str) -> asyncio.Lock:
    lock = _LOCAL_SLOT_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _LOCAL_SLOT_LOCKS[key] = lock
    return lock


def _counter_lock(key: str) -> asyncio.Lock:
    lock = _LOCAL_COUNTER_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _LOCAL_COUNTER_LOCKS[key] = lock
    return lock


async def acquire_global_slot(
    *,
    enabled: bool,
    interval_ms: int,
    redis_url: str,
    redis_key: str,
    redis_key_ttl_ms: int,
    limiter_name: str,
    logger: Optional[logging.Logger] = None,
) -> float:
    """Reserve a globally paced slot, waiting until it becomes due."""
    if not enabled:
        return 0.0

    active_logger = logger or logging.getLogger(__name__)
    now_ms = _now_ms()
    scheduled_ms: Optional[int] = None

    if redis_url:
        try:
            client = await _get_redis_client(redis_url)
            if client is None:
                raise RuntimeError("Redis limiter unavailable")
            scheduled_ms = int(
                float(
                    await client.eval(
                        _RESERVE_SLOT_LUA,
                        1,
                        redis_key,
                        now_ms,
                        interval_ms,
                        redis_key_ttl_ms,
                    )
                )
            )
        except Exception as exc:
            active_logger.warning(
                "%s Redis limiter unavailable, falling back to local limiter: %s",
                limiter_name,
                exc,
            )

    if scheduled_ms is None:
        async with _slot_lock(redis_key):
            scheduled_ms = max(now_ms, _LOCAL_SLOT_STATE.get(redis_key, 0))
            _LOCAL_SLOT_STATE[redis_key] = scheduled_ms + interval_ms

    wait_ms = max(0, scheduled_ms - now_ms)
    if wait_ms > 0:
        await asyncio.sleep(wait_ms / 1000.0)
    return wait_ms / 1000.0


async def increment_fixed_window_counter(
    *,
    enabled: bool,
    redis_url: str,
    redis_key: str,
    window_seconds: int,
    limiter_name: str,
    logger: Optional[logging.Logger] = None,
) -> int:
    """Increment a fixed-window counter and return the new count."""
    if not enabled:
        return 0

    active_logger = logger or logging.getLogger(__name__)

    if redis_url:
        try:
            client = await _get_redis_client(redis_url)
            if client is None:
                raise RuntimeError("Redis limiter unavailable")
            count = int(await client.incr(redis_key))
            if count == 1:
                await client.expire(redis_key, window_seconds)
            return count
        except Exception as exc:
            active_logger.warning(
                "%s Redis counter unavailable, falling back to local counter: %s",
                limiter_name,
                exc,
            )

    now = time.time()
    expires_at = now + window_seconds
    async with _counter_lock(redis_key):
        previous = _LOCAL_COUNTER_STATE.get(redis_key)
        if previous is None or previous[1] <= now:
            count = 1
        else:
            count = previous[0] + 1
            expires_at = previous[1]
        _LOCAL_COUNTER_STATE[redis_key] = (count, expires_at)
        return count
