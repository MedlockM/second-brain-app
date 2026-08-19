"""
Pricing configuration service with in-memory cache (TTL ~5 minutes).

Reads all pricing/quota parameters from DynamoDB pricing_config table.
On first load, seeds default values derived from the validated consumption model
(docs/research/task-287-consumption-model/README.md, owner_decision: ok).

The service is stateless-safe: multiple processes will each maintain their own
cache but share the same DynamoDB source of truth. Changes propagate within
the TTL window (300 seconds by default).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Cache TTL in seconds (5 minutes)
_CACHE_TTL_SECONDS = 300

# In-memory cache
_cache: Dict[str, Any] = {}
_cache_loaded_at: float = 0.0


# ---------------------------------------------------------------------------
# Default values from the validated consumption model of task-287
# (docs/research/task-287-consumption-model/README.md, owner_decision: ok).
#
# One unit is metered: the *minute*. A minute is a minute of media we pay a
# transcription provider to process, and everything that is not transcription is
# unlimited. Ingestion paths that trigger no per-item provider fee (articles, web
# pages, TikTok, Instagram photo posts, single-item AI generations) cost zero
# minutes by design — see §3.1 of the benchmark for the conversion table.
#
# These are seeded into DynamoDB if the table is empty on first read.
# ---------------------------------------------------------------------------

DEFAULT_PRICING_CONFIG: Dict[str, Any] = {
    # --- Tier definitions ---
    # `minutes_per_month` is the *only* allowance a tier carries, and it doubles as
    # safety-net layer 1: at 0.00664 EUR of provider budget per minute, the worst
    # case a subscriber can cost is minutes x 0.00664, which each tier's
    # `revenue_net_eur` covers several times over (0.40 / 1.99 / 4.78 EUR).
    "tiers": {
        "text_only": {
            "id": "text_only",
            "name": "Reader",
            "name_fr": "Lecteur",
            "price_ttc_eur": 3.00,
            "revenue_net_eur": 2.125,
            "minutes_per_month": 60,
            # A single import can never be allowed to swallow a whole allowance in
            # one go; above this the submission is refused as too long, which is
            # not something an upgrade fixes.
            "max_minutes_per_item": 60,
        },
        "mix": {
            "id": "mix",
            "name": "Mix",
            "name_fr": "Mix",
            "price_ttc_eur": 5.00,
            "revenue_net_eur": 3.542,
            "minutes_per_month": 300,
            "max_minutes_per_item": 180,
        },
        "audio_heavy": {
            "id": "audio_heavy",
            "name": "Audio-Heavy",
            "name_fr": "Audio-Heavy",
            "price_ttc_eur": 9.00,
            "revenue_net_eur": 6.375,
            # 720, not 900: at 900 minutes the worst case (0.006642 x 900 = 5.98 EUR)
            # eats 94% of the 6.375 EUR net, which leaves nothing for infrastructure.
            "minutes_per_month": 720,
            "max_minutes_per_item": 240,
        },
    },
    # --- Free trial ---
    "free_trial": {
        "enabled": True,
        "duration_days": 30,
        "tier": "mix",
        "minutes_per_month": 300,
        "max_minutes_per_item": 180,
    },
    # --- How each metered event converts into minutes (benchmark §3.1) ---
    "unit_conversion": {
        # Transcribed audio and video are charged their real length, rounded up.
        "min_minutes_per_transcription": 1,
        # A video whose captions we buy costs one flat provider fee, so it costs
        # one minute whatever its length.
        "captions_minutes": 1,
        # LlamaParse bills at least one credit per page: five pages of document are
        # worth about one minute of transcription budget.
        "document_pages_per_minute": 5,
        # A generation over a collection is the only AI action that scales with the
        # amount of content behind it. Single-item generations are free.
        "collection_sources_per_minute": 5,
    },
    # --- Usage gauge (what the app shows before the wall) ---
    "usage_gauge": {
        "warning_threshold_pct": 80,
    },
    # --- Safety-net layer 2: invisible burst guards (benchmark §3.3) ---
    # Not a user-visible allowance and never a refusal reason: these bound how fast
    # a single account can burn through infrastructure in one day. Every size sits
    # far above the heaviest measured usage, so a normal user cannot reach them, and
    # crossing one only emits `quota.burst_guard_tripped` for the owner to look at.
    "burst_guards": {
        "minutes_per_day": 150,
        "items_per_day": 60,
        "documents_per_day": 40,
        "document_pages_per_day": 400,
        "generations_per_day": 50,
    },
    # --- Safety-net layer 3: shared provider pools (benchmark §3.3) ---
    # Apify credit and LlamaParse credits are *fixed monthly pools shared by every
    # user*, so no per-user cap can protect them. Capacities are expressed in the
    # unit each provider bills, counted across all users, and the percentages are
    # where the owner is warned and where new spend on that provider stops.
    "provider_pools": {
        "apify": {
            "plan": "free",
            "monthly_capacity": 1160,
            "capacity_unit": "results",
            "alarm_pct": 60,
            "stop_pct": 90,
        },
        "llamaparse": {
            "plan": "free",
            "monthly_capacity": 10000,
            "capacity_unit": "pages",
            "alarm_pct": 60,
            "stop_pct": 90,
        },
    },
    # --- Provider configuration ---
    "providers": {
        "transcription": {
            "provider": "deepgram",
            "model": "nova-3",
            # Single source of truth for what a minute costs us: Deepgram Nova-3
            # pay-as-you-go at $0.0077/min, converted at 0.86 EUR/USD
            # (https://deepgram.com/pricing, 2026-08-18). Nothing else in the
            # codebase is allowed to hardcode a per-minute price.
            "cost_per_minute_eur": 0.00664,
        },
        "llm": {
            "summary_short_model": "gpt-5-nano",
            "summary_detailed_model": "gpt-5.4-nano",
            "flashcards_model": "gpt-5.4-nano",
            "notes_model": "gpt-5.4-nano",
        },
        "document_parsing": {
            "primary": "llamaparse",
            "fallback": "unstructured",
        },
        "search": {
            "provider": "algolia",
            "plan": "build_free",
        },
    },
    # --- Revenue model ---
    "revenue_model": {
        "store_commission_pct": 15.0,
        "tva_pct": 20.0,
        "distribution_channel": "app_store_play_store",
    },
    # --- Infrastructure cost baseline (informational) ---
    "infra_cost_baseline": {
        "total_monthly_eur_at_100u": 14.6,
        "per_user_eur_at_100u": 0.145,
        "components": {
            "ec2_t4g_small": 10.55,
            "algolia_build_free": 0.0,
            "aws_misc": 4.0,
        },
    },
}


def _is_cache_valid() -> bool:
    """Check if the in-memory cache is still within TTL."""
    if not _cache:
        return False
    return (time.time() - _cache_loaded_at) < _CACHE_TTL_SECONDS


def _merge_defaults(defaults: Any, stored: Any) -> Any:
    """Overlay the stored config on the defaults, leaf by leaf.

    Seeding only happens when the table is *empty*, so a key added to the
    defaults after the first seed would otherwise never reach an environment
    whose table is already populated — and a quota whose key is missing reads as
    0, i.e. no limit at all. That is how `minutes_per_month` and `burst_guards`
    would have been silently inert on dev.

    A stored value always wins, including a stored 0: the point is to fill gaps,
    never to override what the owner has set in DynamoDB.

    The reverse does not happen on its own: a top-level key *removed* from the
    defaults stays in the table until it is deleted there. That is why dropping a
    section here comes with a matching delete on `pricing_config-<env>`.
    """
    if isinstance(defaults, dict) and isinstance(stored, dict):
        merged = dict(defaults)
        for key, value in stored.items():
            merged[key] = (
                _merge_defaults(defaults[key], value) if key in defaults else value
            )
        return merged
    return stored


async def _load_from_db() -> Dict[str, Any]:
    """Load config from DynamoDB. Seed defaults if table is empty."""
    from media_summarizer.utils import pricing_config_db

    try:
        config = await pricing_config_db.get_all_config()
    except Exception as e:
        logger.warning(
            "Failed to read pricing config from DynamoDB, using defaults: %s", e
        )
        return dict(DEFAULT_PRICING_CONFIG)

    if not config:
        # Seed defaults
        logger.info("Pricing config table is empty, seeding default values.")
        try:
            await pricing_config_db.put_config_batch(DEFAULT_PRICING_CONFIG)
        except Exception as e:
            logger.error("Failed to seed pricing config defaults: %s", e)
        return dict(DEFAULT_PRICING_CONFIG)

    return _merge_defaults(DEFAULT_PRICING_CONFIG, config)


async def get_pricing_config() -> Dict[str, Any]:
    """
    Return the full pricing config dict from cache or DynamoDB.
    Cache is refreshed every 5 minutes.
    """
    global _cache, _cache_loaded_at

    if _is_cache_valid():
        return _cache

    config = await _load_from_db()
    _cache = config
    _cache_loaded_at = time.time()
    return _cache


async def get_config_value(key: str, default: Any = None) -> Any:
    """Get a single pricing config value by key."""
    config = await get_pricing_config()
    return config.get(key, default)


async def update_config_values(updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update one or more pricing config values.
    Writes to DynamoDB and invalidates cache immediately.
    Returns the full updated config.
    """
    global _cache, _cache_loaded_at
    from media_summarizer.utils import pricing_config_db

    await pricing_config_db.put_config_batch(updates)

    # Invalidate cache to force reload on next access
    _cache_loaded_at = 0.0

    # Reload and return
    return await get_pricing_config()


def invalidate_cache() -> None:
    """Force cache invalidation (useful for testing)."""
    global _cache, _cache_loaded_at
    _cache = {}
    _cache_loaded_at = 0.0
