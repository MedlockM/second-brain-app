"""
Pricing configuration service with in-memory cache (TTL ~5 minutes).

Reads all pricing/quota parameters from DynamoDB pricing_config table.
On first load, seeds default values derived from the validated benchmark
(docs/research/task-65-pricing-v1-benchmark/README.md, owner_decision: ok).

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
# Default pricing values from validated task-65 benchmark (owner_decision: ok)
# These are seeded into DynamoDB if the table is empty on first read.
# ---------------------------------------------------------------------------

DEFAULT_PRICING_CONFIG: Dict[str, Any] = {
    # --- Tier definitions ---
    "tiers": {
        "text_only": {
            "id": "text_only",
            "name": "Reader",
            "name_fr": "Lecteur",
            "price_ttc_eur": 3.00,
            "revenue_net_eur": 2.125,
            "audio_minutes_per_month": 0,
            "description": "Articles, documents, YouTube captions. No audio transcription.",
            "description_fr": "Articles, documents, sous-titres YouTube. Aucune transcription audio.",
        },
        "mix": {
            "id": "mix",
            "name": "Mix",
            "name_fr": "Mix",
            "price_ttc_eur": 5.00,
            "revenue_net_eur": 3.542,
            "audio_minutes_per_month": 300,
            "description": "Everything in Reader plus 5h/month of podcast and audio transcription.",
            "description_fr": "Tout le tier Lecteur + 5h/mois de transcription audio (podcasts).",
        },
        "audio_heavy": {
            "id": "audio_heavy",
            "name": "Audio-Heavy",
            "name_fr": "Audio-Heavy",
            "price_ttc_eur": 9.00,
            "revenue_net_eur": 6.375,
            "audio_minutes_per_month": 900,
            "description": "Everything in Mix with 15h/month of podcast and audio transcription.",
            "description_fr": "Tout le tier Mix + 15h/mois de transcription audio (podcasts).",
        },
    },
    # --- Free trial ---
    "free_trial": {
        "enabled": True,
        "duration_days": 30,
        "tier": "mix",
        "hard_caps": {
            "audio_minutes": 300,
            "articles": 300,
            "documents": 50,
        },
        "cost_monitoring": {
            "warning_eur": 3.0,
            "hard_block_eur": 5.0,
        },
    },
    # --- Hard caps (monthly, per tier) ---
    "hard_caps": {
        "text_only": {
            "audio_minutes": 0,
            "articles": 500,
            "documents": 100,
            "youtube": 100,
            "max_audio_duration_minutes": 0,
        },
        "mix": {
            "audio_minutes": 300,
            "articles": 500,
            "documents": 100,
            "youtube": 100,
            "max_audio_duration_minutes": 180,
        },
        "audio_heavy": {
            "audio_minutes": 900,
            "articles": 1500,
            "documents": 300,
            "youtube": 200,
            "max_audio_duration_minutes": 180,
        },
    },
    # --- Rate limits (daily, per tier) ---
    "rate_limits": {
        "text_only": {
            "audio_imports_per_day": 0,
            "text_imports_per_day": 30,
            "document_imports_per_day": 10,
            "text_imports_per_minute": 5,
            "api_calls_per_minute": 15,
        },
        "mix": {
            "audio_imports_per_day": 10,
            "max_audio_per_import_minutes": 60,
            "text_imports_per_day": 30,
            "document_imports_per_day": 10,
            "text_imports_per_minute": 5,
            "api_calls_per_minute": 30,
        },
        "audio_heavy": {
            "audio_imports_per_day": 20,
            "max_audio_per_import_minutes": 90,
            "text_imports_per_day": 100,
            "document_imports_per_day": 30,
            "text_imports_per_minute": 10,
            "api_calls_per_minute": 60,
        },
    },
    # --- Cost monitoring thresholds (per user, per tier) ---
    "cost_monitoring": {
        "text_only": {
            "warning_eur": 2.5,
            "hard_block_eur": 3.5,
            "action": "throttle_5_imports_per_day",
        },
        "mix": {
            "warning_eur": 4.0,
            "hard_block_eur": 6.0,
            "action": "throttle_1_audio_per_hour",
        },
        "audio_heavy": {
            "warning_eur": 7.0,
            "hard_block_eur": 10.0,
            "action": "throttle_and_contact_owner",
        },
    },
    # --- Provider configuration ---
    "providers": {
        "transcription": {
            "provider": "deepgram",
            "model": "nova-3",
            "cost_per_minute_eur": 0.003,
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

    return config


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
