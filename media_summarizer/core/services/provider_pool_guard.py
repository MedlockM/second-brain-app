"""
Safety-net layer 3: the shared provider pools.

Apify credit and LlamaParse credits are **fixed monthly pools shared by every
user**: they are bought per month, they do not roll over, and once the pool is
empty every user's imports on that provider fail at once. No per-user allowance
can protect them — a hundred users each staying politely inside their minutes can
still empty a 5 USD Apify credit between them.

So this module counts what the platform spends on each provider, month by month,
and does two things with the figure:

- at `alarm_pct` of the plan capacity it logs `provider_pool.threshold_reached`,
  which is what a CloudWatch alarm watches so the owner can upgrade the plan
  *before* anything breaks;
- at `stop_pct` it stops new spend on that provider, so the last slice of credit
  stays available and imports fail with a retryable error (the content is kept and
  the message is retried) instead of the provider returning an opaque 402.

Capacities and thresholds live in the `provider_pools` section of the pricing
config, so the owner raises them from DynamoDB when they upgrade a plan.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from media_summarizer.core.services import pricing_config_service
from media_summarizer.utils import quota_usage_db

logger = logging.getLogger(__name__)

POOL_APIFY = "apify"
POOL_LLAMAPARSE = "llamaparse"

# Pool name -> the counter `quota_usage_db` keeps for it.
_POOL_COUNTER: Dict[str, str] = {
    POOL_APIFY: "apify_results",
    POOL_LLAMAPARSE: "llamaparse_pages",
}


@dataclass
class PoolStatus:
    """Where one provider pool stands this month."""

    pool: str
    used: int
    capacity: int
    alarm_pct: int
    stop_pct: int

    @property
    def utilisation_pct(self) -> float:
        if self.capacity <= 0:
            return 0.0
        return (self.used / self.capacity) * 100

    @property
    def alarm_reached(self) -> bool:
        return self.capacity > 0 and self.utilisation_pct >= self.alarm_pct

    @property
    def spend_allowed(self) -> bool:
        """A capacity of 0 means "not configured", which never blocks anything."""
        return self.capacity <= 0 or self.utilisation_pct < self.stop_pct


async def _pool_config(pool: str) -> Dict[str, int]:
    config = await pricing_config_service.get_pricing_config()
    pool_config = (config.get("provider_pools", {}) or {}).get(pool, {}) or {}
    return {
        "capacity": int(pool_config.get("monthly_capacity", 0) or 0),
        "alarm_pct": int(pool_config.get("alarm_pct", 60) or 60),
        "stop_pct": int(pool_config.get("stop_pct", 90) or 90),
    }


async def get_pool_status(pool: str, *, month: Optional[str] = None) -> PoolStatus:
    """Read one pool's month-to-date spend against its configured capacity."""
    settings = await _pool_config(pool)
    usage = await quota_usage_db.get_provider_pool_usage(month)
    return PoolStatus(
        pool=pool,
        used=int(usage.get(_POOL_COUNTER.get(pool, ""), 0) or 0),
        capacity=settings["capacity"],
        alarm_pct=settings["alarm_pct"],
        stop_pct=settings["stop_pct"],
    )


async def spend_allowed(pool: str) -> bool:
    """Whether new spend on this provider may go ahead.

    Fails open: an unreadable counter must not stop the whole product. The pool is
    a protection against a slow drift, not a correctness invariant.
    """
    try:
        status = await get_pool_status(pool)
    except Exception as exc:
        logger.warning(
            "provider_pool.check_failed_open",
            extra={"pool": pool, "error": str(exc), "error_type": type(exc).__name__},
        )
        return True

    if status.spend_allowed:
        return True

    logger.error(
        "provider_pool.spend_stopped",
        extra={
            "pool": pool,
            "used": status.used,
            "capacity": status.capacity,
            "utilisation_pct": round(status.utilisation_pct, 1),
            "stop_pct": status.stop_pct,
        },
    )
    return False


async def record_spend(
    pool: str,
    *,
    units: int,
    idempotency_token: str,
) -> None:
    """Count `units` of provider spend that actually happened.

    Best-effort: the provider has already billed us, so a counter failure must not
    fail the work. Under-counting the pool for one run only delays the alarm.
    """
    if units <= 0 or pool not in _POOL_COUNTER:
        return

    try:
        if pool == POOL_APIFY:
            await quota_usage_db.increment_provider_pool_usage(
                apify_results=units,
                idempotency_token=idempotency_token,
            )
        else:
            await quota_usage_db.increment_provider_pool_usage(
                llamaparse_pages=units,
                idempotency_token=idempotency_token,
            )
        status = await get_pool_status(pool)
    except Exception as exc:
        logger.warning(
            "provider_pool.record_failed",
            extra={
                "pool": pool,
                "units": units,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )
        return

    if status.alarm_reached:
        # The line a CloudWatch metric filter watches: past this point the owner
        # has to upgrade the plan or watch the pool run out.
        logger.error(
            "provider_pool.threshold_reached",
            extra={
                "pool": pool,
                "used": status.used,
                "capacity": status.capacity,
                "utilisation_pct": round(status.utilisation_pct, 1),
                "alarm_pct": status.alarm_pct,
                "stop_pct": status.stop_pct,
            },
        )
