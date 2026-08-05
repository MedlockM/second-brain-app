"""
Entitlements API endpoints for subscription and quota tracking.

This endpoint is consumed by the mobile app to check user access
and remaining audio minutes for the current month after RevenueCat
webhook updates.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from media_summarizer.api.dependencies.auth import require_verified_email

router = APIRouter()
logger = logging.getLogger(__name__)

# Tier configuration for paywall offerings display
OFFERINGS_CONFIG = [
    {
        "tier": "S",
        "name": "Text-Only",
        "display_name": "Reader",
        "price_eur": 3.00,
        "minutes_per_month": 0,
        "description": "Articles, newsletters, PDFs, YouTube with captions. No audio transcription.",
        "features": [
            "Unlimited articles and web content",
            "PDF and document processing",
            "YouTube with captions (95% coverage)",
            "Flashcards, notes, and summaries",
        ],
    },
    {
        "tier": "M",
        "name": "Mix",
        "display_name": "Mix",
        "price_eur": 5.00,
        "minutes_per_month": 300,
        "description": "Everything in Reader plus 5 hours of podcast transcription per month.",
        "features": [
            "Everything in Reader",
            "300 minutes (5h) audio transcription/month",
            "Podcast import and processing",
            "Audio file uploads",
        ],
    },
    {
        "tier": "L",
        "name": "Audio-Heavy",
        "display_name": "Audio-Heavy",
        "price_eur": 9.00,
        "minutes_per_month": 900,
        "description": "For podcast enthusiasts: 15 hours of transcription per month.",
        "features": [
            "Everything in Mix",
            "900 minutes (15h) audio transcription/month",
            "Priority processing",
            "Higher daily import limits",
        ],
    },
]


@router.get("/entitlements/status")
async def get_entitlements_status(
    request: Request,
    current_user=Depends(require_verified_email),
):
    """
    Get the current user's subscription tier, remaining audio minutes for the
    current month, and period info.

    Returns:
    - subscription tier (S/M/L) if active, else None
    - is_active boolean for paywall gate
    - period_end date for subscription expiry tracking
    - auto_renew_status for renewal display
    - remaining audio minutes for the current month (tier hard cap minus usage)
    - offerings_config if user has no active subscription (for paywall display)
    """
    try:
        from media_summarizer.core.services.quota_enforcer import (
            _SUBSCRIPTION_TIER_TO_CONFIG,
            _get_effective_caps,
        )
        from media_summarizer.utils import minute_db, quota_usage_db

        # Get active subscription
        subs = await minute_db.get_subscriptions_by_user_id(current_user.id)
        active_sub = None
        if subs:
            for s in subs:
                if s.status.value in ("active", "grace_period"):
                    active_sub = s
                    break
            # If no active sub, check for a canceled sub that hasn't expired yet
            if not active_sub:
                now = datetime.now(timezone.utc)
                for s in subs:
                    if s.status.value == "canceled" and s.current_period_end and s.current_period_end > now:
                        active_sub = s
                        break

        is_active = active_sub is not None and active_sub.status.value in (
            "active", "grace_period", "canceled"
        )

        # Remaining audio minutes for the current month: tier hard cap
        # (with free-trial override, same logic as the enforcement gate)
        # minus usage recorded in user_usage_monthly.
        minutes_remaining = 0
        if active_sub:
            config_tier = _SUBSCRIPTION_TIER_TO_CONFIG.get(active_sub.tier.value, "mix")
            effective_caps = await _get_effective_caps(config_tier, current_user.id)
            audio_minutes_cap = int(effective_caps.get("audio_minutes", 0))
            usage = await quota_usage_db.get_monthly_usage(current_user.id)
            minutes_remaining = max(0, audio_minutes_cap - int(usage.get("audio_minutes_used", 0)))

        response = {
            "user_id": current_user.id,
            "subscription_tier": active_sub.tier.value if active_sub else None,
            "subscription_status": active_sub.status.value if active_sub else None,
            "is_active": is_active,
            "period_end": active_sub.current_period_end.isoformat() if active_sub and active_sub.current_period_end else None,
            "auto_renew_status": active_sub.auto_renew_status if active_sub else None,
            "minutes_remaining": minutes_remaining,
        }

        # Include offerings config if user has no active subscription
        if not is_active:
            response["offerings_config"] = OFFERINGS_CONFIG

        return response
    except Exception as e:
        logger.error(f"Failed to retrieve entitlements for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve entitlements",
        )
