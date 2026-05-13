"""
Pricing endpoints:
- GET  /api/pricing       — Public: returns current tier/pricing info for mobile app
- PUT  /api/pricing/admin — Protected: update pricing config at runtime (admin only)
- GET  /api/pricing/admin — Protected: returns full config including internal params
"""

import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
    Returns tier definitions, free trial info, and feature descriptions.
    Never exposes internal cost monitoring or provider config.
    """
    try:
        config = await pricing_config_service.get_pricing_config()

        # Build public-facing response (exclude internal/sensitive data)
        tiers = config.get("tiers", {})
        free_trial = config.get("free_trial", {})
        hard_caps = config.get("hard_caps", {})

        # Format tiers for mobile consumption
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
                    "audio_minutes_per_month": tier_data.get("audio_minutes_per_month"),
                    "description": tier_data.get("description", ""),
                    "description_fr": tier_data.get("description_fr", ""),
                    "hard_caps": hard_caps.get(tier_id, {}),
                })

        # Free trial info (public-safe subset)
        public_free_trial = None
        if free_trial.get("enabled"):
            public_free_trial = {
                "enabled": True,
                "duration_days": free_trial.get("duration_days", 30),
                "tier": free_trial.get("tier", "mix"),
                "hard_caps": free_trial.get("hard_caps", {}),
            }

        return {
            "tiers": public_tiers,
            "free_trial": public_free_trial,
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
    (cost monitoring, provider config, infra baseline, rate limits).
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
            "hard_caps": { ... }
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
