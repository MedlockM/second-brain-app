"""
Entitlements API endpoints for subscription and consumption tracking.

This is the single place the mobile app reads a user's plan and how much of this
period's minutes are left. Everything it returns comes from one
`EntitlementSnapshot`, so the gauge the user reads on the account screen and the
gate that refuses their next import can never disagree.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status

from media_summarizer.api.dependencies.auth import require_verified_email
from media_summarizer.core.services import quota_enforcer

router = APIRouter()
logger = logging.getLogger(__name__)

# What the paywall shows when the user has no plan. Minutes are the only metered
# unit, so each tier is one number; everything that is not transcription is
# unlimited on every tier and is said as such rather than listed per tier.
OFFERINGS_CONFIG = [
    {
        "tier": "S",
        "name": "Reader",
        "display_name": "Reader",
        "price_eur": 3.00,
        "minutes_per_month": 60,
        "description": "One hour of listening a month. Everything you read is unlimited.",
        "features": [
            "60 minutes of audio and video a month",
            "Unlimited articles, web pages and documents",
            "Unlimited flashcards, notes and summaries",
        ],
    },
    {
        "tier": "M",
        "name": "Mix",
        "display_name": "Mix",
        "price_eur": 5.00,
        "minutes_per_month": 300,
        "description": "About five hours of listening a month. Everything you read is unlimited.",
        "features": [
            "300 minutes of audio and video a month",
            "Unlimited articles, web pages and documents",
            "Unlimited flashcards, notes and summaries",
        ],
    },
    {
        "tier": "L",
        "name": "Audio-Heavy",
        "display_name": "Audio-Heavy",
        "price_eur": 9.00,
        "minutes_per_month": 720,
        "description": "Twelve hours of listening a month. Everything you read is unlimited.",
        "features": [
            "720 minutes of audio and video a month",
            "Unlimited articles, web pages and documents",
            "Unlimited flashcards, notes and summaries",
        ],
    },
]

# The one sentence that explains what a minute is. Shown under the plan list and
# next to the account gauge, so the user never has to guess why a two-hour video
# with subtitles cost them one minute.
MINUTES_LEGEND = (
    "Minutes cover audio and video we transcribe. A video with subtitles counts as "
    "one minute whatever its length, a PDF counts a minute per five pages, and "
    "articles, web pages and short clips are free."
)


@router.get("/entitlements/status")
async def get_entitlements_status(
    request: Request,
    current_user=Depends(require_verified_email),
):
    """Return the caller's plan and this period's minute consumption.

    - `subscription_tier` / `subscription_status` / `auto_renew_status` describe the plan.
    - `minutes_included` / `minutes_used` / `minutes_remaining` / `resets_at` are the
      gauge, and `warning_threshold_reached` says when to show the banner.
    - `max_minutes_per_item` is what makes "too long for one import" explainable.
    - `offerings_config` and `minutes_legend` are only sent when there is no plan.

    There is one date, `resets_at`: the allowance empties on the subscription
    anniversary, so the period end and the reset are the same instant, and sending
    it twice under two names would only invite the app to render two.
    """
    try:
        snapshot = await quota_enforcer.get_entitlement_snapshot(current_user.id)

        response = {
            "user_id": current_user.id,
            "subscription_tier": snapshot.subscription_tier,
            "subscription_status": snapshot.subscription_status,
            "is_active": snapshot.is_entitled,
            "is_free_trial": snapshot.is_free_trial,
            "auto_renew_status": snapshot.auto_renew,
            "minutes_included": snapshot.minutes_included,
            "minutes_used": snapshot.minutes_used,
            "minutes_remaining": snapshot.minutes_remaining,
            "max_minutes_per_item": snapshot.max_minutes_per_item,
            "resets_at": (
                snapshot.period_end.isoformat() if snapshot.period_end else None
            ),
            "warning_threshold_reached": snapshot.warning_threshold_reached,
        }

        if not snapshot.is_entitled:
            response["offerings_config"] = OFFERINGS_CONFIG
            response["minutes_legend"] = MINUTES_LEGEND

        return response
    except Exception as e:
        logger.error(f"Failed to retrieve entitlements for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve entitlements",
        )
