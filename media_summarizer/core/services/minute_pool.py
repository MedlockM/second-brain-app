"""
Minute pool service — allocate holds for jobs, finalize on success, release on failure.

This service uses minute_db to operate on DynamoDB tables:
- minute_usage: create holds (held), finalize (finalized), release (released)
- minute_buckets: decrement minutes_remaining on finalize, sorted by period_end (oldest first)
"""
from __future__ import annotations
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta

from media_summarizer.core.models.billing import MinuteUsage, MinuteUsageStatus
from media_summarizer.utils import minute_db


async def get_total_available_minutes(user_id: str) -> int:
    """
    Calculate total available minutes for a user across all buckets.
    """
    buckets = await minute_db.get_minute_buckets_by_user_id(user_id)
    total = 0
    now = datetime.now(timezone.utc)
    
    for b in buckets:
        # Skip expired buckets
        if b.expires_at:
            try:
                # Handle both datetime objects and ISO strings
                if isinstance(b.expires_at, str):
                    exp = datetime.fromisoformat(b.expires_at)
                elif isinstance(b.expires_at, datetime):
                    exp = b.expires_at
                else:
                    # Unknown type, skip expiry check
                    exp = None
                
                if exp and exp <= now:
                    continue
            except (ValueError, TypeError):
                # If parsing fails, include the bucket (safer to include than exclude)
                pass
        
        total += int(b.minutes_remaining or 0)
        
    return total



async def allocate_hold_for_job(user_id: str, job_id: str, minutes_estimated: int = 0) -> MinuteUsage:
    usage = MinuteUsage(
        id=f"mu_{job_id}",
        user_id=user_id,
        job_id=job_id,
        minutes_estimated=max(0, int(minutes_estimated or 0)),
        status=MinuteUsageStatus.held,
        hold_expires_at=datetime.now(timezone.utc) + timedelta(days=2),
    )
    return await minute_db.create_minute_usage(usage)


async def release_hold(job_id: str) -> bool:
    usage = await minute_db.get_minute_usage_by_job_id(job_id)
    if not usage:
        return False
    if usage.status != MinuteUsageStatus.held:
        return False
    usage.status = MinuteUsageStatus.released
    await minute_db.update_minute_usage(usage)
    return True


async def finalize_usage(job_id: str, minutes_used: int) -> bool:
    minutes_used = max(0, int(minutes_used or 0))
    usage = await minute_db.get_minute_usage_by_job_id(job_id)
    if not usage:
        return False

    # Idempotency check: if already finalized, do not deduct again
    if usage.status == MinuteUsageStatus.finalized:
        return True

    # Load buckets
    buckets = await minute_db.get_minute_buckets_by_user_id(usage.user_id)

    # Sort subscription buckets by period_end (consume oldest period first)
    # All buckets are now subscription type per pricing V1 model
    ordered = sorted(buckets, key=lambda b: b.period_end or datetime.max.replace(tzinfo=timezone.utc))

    remaining = minutes_used
    breakdown: List[Dict[str, Any]] = []

    for b in ordered:
        if remaining <= 0:
            break
        avail = int(b.minutes_remaining or 0)
        if avail <= 0:
            continue
        take = min(avail, remaining)
        b.minutes_remaining = avail - take
        await minute_db.update_minute_bucket(b)
        breakdown.append({"bucket_id": b.id, "minutes": take})
        remaining -= take

    # Persist usage
    usage.minutes_used = minutes_used
    usage.bucket_breakdown = breakdown
    usage.status = MinuteUsageStatus.finalized if remaining == 0 else MinuteUsageStatus.failed
    if remaining != 0:
        # Could not cover full usage; caller may choose to handle deficit later
        pass
    await minute_db.update_minute_usage(usage)

    return remaining == 0

