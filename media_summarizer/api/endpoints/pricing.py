"""
Pricing endpoints:
- GET  /api/pricing       — Public: returns current tier/pricing info for mobile app
- PUT  /api/pricing/admin — Protected: update pricing config at runtime (admin only)
- GET  /api/pricing/admin — Protected: returns full config including internal params
"""

import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from media_summarizer.core.services import pricing_config_service

router = APIRouter()
logger = logging.getLogger(__name__)

# Admin secret for pricing config management.
# In production this is set via environment variable; never hardcoded.
ADMIN_SECRET_ENV = "PRICING_ADMIN_SECRET"


def _verify_admin_secret(request: Request) -> None:
    """
    Verify that the request contains a valid admin secret.
    Uses a simple Bearer token approach with a shared secret.
    """
    admin_secret = os.environ.get(ADMIN_SECRET_ENV, "")
    if not admin_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin endpoint not configured",
        )

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = auth_header[len("Bearer "):]
    if token != admin_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin credentials",
        )


class PricingUpdateRequest(BaseModel):
    """Request body for updating pricing config values."""

    updates: Dict[str, Any]


@router.get("/pricing")
async def get_public_pricing():
    """
    Public endpoint for the mobile app to fetch current pricing/tier information.

    This is the *only* runtime source of plan figures the app reads (task-299):
    the paywall renders its cards from `tiers`, its trial line from `free_trial`
    and its minutes legend from `unit_conversion`, so a figure changed through
    `PUT /api/pricing/admin` moves the screen with no build. Nothing on the
    client re-states these numbers.

    Never exposes internal cost monitoring or provider config.
    """
    try:
        config = await pricing_config_service.get_pricing_config()

        # Build public-facing response (exclude internal/sensitive data)
        tiers = config.get("tiers", {})
        free_trial = config.get("free_trial", {})

        # Format tiers for mobile consumption. One metered unit means one number
        # per tier: the minutes it includes, plus the longest single import it
        # accepts. There are no per-category caps to publish any more, and no
        # prose `description` either — it only ever re-worded `minutes_per_month`,
        # which is how the paywall drifted from the config in the first place.
        # The client turns the figures into sentences.
        public_tiers = []
        tier_order = ["text_only", "mix", "audio_heavy"]
        for tier_id in tier_order:
            tier_data = tiers.get(tier_id)
            if tier_data:
                public_tiers.append({
                    "id": tier_data.get("id", tier_id),
                    "name": tier_data.get("name", tier_id),
                    "name_fr": tier_data.get("name_fr", ""),
                    "price_ttc_eur": tier_data.get("price_ttc_eur"),
                    "minutes_per_month": tier_data.get("minutes_per_month"),
                    "max_minutes_per_item": tier_data.get("max_minutes_per_item"),
                })

        # Free trial info (public-safe subset)
        public_free_trial = None
        if free_trial.get("enabled"):
            public_free_trial = {
                "enabled": True,
                "duration_days": free_trial.get("duration_days", 30),
                "tier": free_trial.get("tier", "mix"),
                "minutes_per_month": free_trial.get("minutes_per_month"),
                "max_minutes_per_item": free_trial.get("max_minutes_per_item"),
            }

        # How a metered event converts into minutes. Public on purpose: it is
        # what the user is told a minute buys, so it must come from the same
        # config the enforcer converts with, not from a sentence written twice.
        unit_conversion = config.get("unit_conversion", {})

        return {
            "tiers": public_tiers,
            "free_trial": public_free_trial,
            "unit_conversion": {
                # `min_minutes_per_transcription` stays internal: transcribed
                # media is billed its own length, and the rounding floor is not
                # a claim the paywall makes.
                "captions_minutes": unit_conversion.get("captions_minutes"),
                "document_pages_per_minute": unit_conversion.get(
                    "document_pages_per_minute"
                ),
                "collection_sources_per_minute": unit_conversion.get(
                    "collection_sources_per_minute"
                ),
            },
            "currency": "EUR",
            "billing_period": "monthly",
        }
    except Exception as e:
        logger.error("Failed to retrieve public pricing config: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pricing information",
        )


@router.get("/pricing/admin")
async def get_admin_pricing(request: Request):
    """
    Admin endpoint: returns the full pricing config including internal params
    (unit conversions, burst guards, provider pools, provider config).
    Protected by admin secret.
    """
    _verify_admin_secret(request)

    try:
        config = await pricing_config_service.get_pricing_config()
        return {"config": config}
    except Exception as e:
        logger.error("Failed to retrieve admin pricing config: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pricing configuration",
        )


@router.put("/pricing/admin")
async def update_admin_pricing(
    request: Request,
    body: PricingUpdateRequest,
):
    """
    Admin endpoint: update one or more pricing config values at runtime.
    Protected by admin secret. Changes take effect within 5 minutes (cache TTL).

    Body example:
    {
        "updates": {
            "tiers": { ... updated tier definitions ... },
            "burst_guards": { ... }
        }
    }

    Each key in 'updates' corresponds to a top-level config key.
    The value completely replaces the existing value for that key.
    """
    _verify_admin_secret(request)

    if not body.updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No updates provided",
        )

    try:
        updated_config = await pricing_config_service.update_config_values(body.updates)
        logger.info(
            "Pricing config updated by admin. Keys: %s",
            list(body.updates.keys()),
        )
        return {"status": "ok", "updated_keys": list(body.updates.keys()), "config": updated_config}
    except Exception as e:
        logger.error("Failed to update pricing config: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update pricing configuration",
        )
