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

    What a plan *costs and includes* is deliberately not here: the paywall reads
    `GET /api/pricing`, which serves the pricing config itself. This endpoint
    only ever describes the caller's own state (task-299).

    There is one date, `resets_at`: it is the end of the period the gauge
    describes, so the period end and the reset are the same instant and sending it
    twice under two names would only invite the app to render two. On a
    subscription that instant is the renewal anniversary; during the free trial it
    is the moment the trial closes, after which nothing refills at all.

    `trial_raises_allowance_until` is the one exception, and it is a different date
    for a different fact: a subscriber whose free trial is still running is served
    the better of the two allowances, so on that instant the gauge *shrinks* to what
    their plan alone grants. It is null whenever the allowance is already the plan's
    own. The app should say so before the day comes rather than let the user watch
    their minutes disappear.
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
            "trial_raises_allowance_until": (
                snapshot.trial_raises_allowance_until.isoformat()
                if snapshot.trial_raises_allowance_until
                else None
            ),
            "warning_threshold_reached": snapshot.warning_threshold_reached,
        }

        return response
    except Exception as e:
        logger.error(f"Failed to retrieve entitlements for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve entitlements",
        )
