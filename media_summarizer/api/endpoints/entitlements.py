"""
Entitlements API endpoints for subscription and minute tracking.

This endpoint is consumed by the mobile app (via RevenueCat webhook handler in task-99)
to check user access and remaining minutes.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status

from media_summarizer.api.dependencies.auth import require_verified_email

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/entitlements/status")
async def get_entitlements_status(
    request: Request,
    current_user=Depends(require_verified_email),
):
    """
    Get the current user's subscription tier and remaining minutes.

    Returns:
    - subscription tier (S/M/L) if active, else None
    - total remaining minutes across all sources (subscription, packs, rollover)
    - breakdown by source type

    TODO: Wire to RevenueCat webhook handler in task-99.
    When RevenueCat sends purchase events, the webhook handler will update the
    subscriptions and minute_buckets tables, and this endpoint will reflect the latest state.
    """
    try:
        from media_summarizer.utils import minute_db
        from media_summarizer.core.models.billing import MinuteBucketSource
        from datetime import datetime, timezone

        # Get active subscription
        subs = await minute_db.get_subscriptions_by_user_id(current_user.id)
        active_sub = None
        if subs:
            for s in subs:
                if str(s.status) == "active" or s.status.value == "active":
                    active_sub = s
                    break

        # Get all minute buckets
        buckets = await minute_db.get_minute_buckets_by_user_id(current_user.id)
        now = datetime.now(timezone.utc)
        
        total_remaining = 0
        breakdown = {"subscription": 0, "pack": 0, "rollover": 0, "migration": 0}
        
        for b in buckets:
            # Skip expired buckets
            if b.expires_at and b.expires_at < now:
                continue
            
            mr = int(b.minutes_remaining or 0)
            total_remaining += mr
            if b.source_type == MinuteBucketSource.subscription:
                breakdown["subscription"] += mr
            elif b.source_type == MinuteBucketSource.pack:
                breakdown["pack"] += mr
            elif b.source_type == MinuteBucketSource.rollover:
                breakdown["rollover"] += mr
            elif b.source_type == MinuteBucketSource.migration:
                breakdown["migration"] += mr

        return {
            "user_id": current_user.id,
            "subscription_tier": active_sub.tier.value if active_sub else None,
            "subscription_status": active_sub.status.value if active_sub else None,
            "minutes_remaining": total_remaining,
            "breakdown": breakdown,
        }
    except Exception as e:
        logger.error(f"Failed to retrieve entitlements for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve entitlements",
        )
