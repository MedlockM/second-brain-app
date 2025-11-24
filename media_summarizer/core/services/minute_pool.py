"""
Minute pool service — allocate holds for jobs, finalize on success, release on failure.

This service uses minute_db to operate on DynamoDB tables:
- minute_usage: create holds (held), finalize (finalized), release (released)
- minute_buckets: decrement minutes_remaining on finalize, in order:
  rollover -> subscription -> packs (by earliest expiration)
"""
from __future__ import annotations
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta

from media_summarizer.core.models.billing import MinuteUsage, MinuteUsageStatus, MinuteBucketSource
from media_summarizer.utils import minute_db


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

    # Load buckets
    buckets = await minute_db.get_minute_buckets_by_user_id(usage.user_id)

    # Ordering: rollover -> subscription -> packs (by earliest expiry)
    rollover = [b for b in buckets if b.source_type == MinuteBucketSource.rollover]
    subs = [b for b in buckets if b.source_type == MinuteBucketSource.subscription]
    packs = [b for b in buckets if b.source_type == MinuteBucketSource.pack]

    # Sort rollover by earliest expiration (as per PAYMENT_SYSTEM_V2.md line 24)
    rollover.sort(key=lambda b: b.expires_at or datetime.max.replace(tzinfo=timezone.utc))
    
    # Sort subscriptions by period_end (consume oldest period first)
    subs.sort(key=lambda b: b.period_end or datetime.max.replace(tzinfo=timezone.utc))
    
    # Sort packs by earliest expiration
    packs.sort(key=lambda b: b.expires_at or datetime.max.replace(tzinfo=timezone.utc))

    ordered = rollover + subs + packs

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

