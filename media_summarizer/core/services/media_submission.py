"""
Shared media submission service with global idempotence (media key),
job creation, and minutes billing.

Designed to be called by API endpoints and future sync integrations.
In V1, notifications are delivered via mobile app polling, not email.
"""

from __future__ import annotations

import os
import json
from math import ceil
from typing import Dict, Any

from media_summarizer.utils import (
    database_async,
    sqs,
    s3,
    media_idempotence,
    media_watchers,
)
from media_summarizer.core.models import ProcessingJob
from media_summarizer.core.services.minute_pool import (
    allocate_hold_for_job,
    finalize_usage,
    get_total_available_minutes,
)
from media_summarizer.core.services.quota_enforcer import (
    check_submission_allowed,
    record_submission,
    estimate_submission_cost,
)


async def submit_media_for_user(
    *,
    user: Any,
    media_key: str,
    media_title: str,
    source_title: str,
    audio_url: str,
    duration_seconds: int,
    media_image: str = "",
    media_date_published: int = 0,  # Unix timestamp - when content was published
    source: str = "manual",
    folder_id: str | None = None,  # Optional folder to assign the media to
    feed_url: str = "",  # RSS feed URL for Podcasting 2.0 transcript lookup
) -> Dict[str, Any]:
    """
    Submit a media item for a user with global idempotence.

    - If key is new: create a canonical job, reserve key, allocate minutes, enqueue download.
    - If key already processed: create a billing job, charge minutes (summary in app via polling).
    - If key reserved/in progress: return "pending" status (watchers fan-out).

    Returns a dict compatible with MediaItemSelectionResponse.
    """
    # 0. Credit Check (Pre-flight)
    # Estimate required minutes (min 1)
    minutes_required = max(1, ceil((duration_seconds or 0) / 60))
    available = await get_total_available_minutes(user.id)

    if available < minutes_required:
        return {
            "status": "skipped",
            "reason": "insufficient_credits",
            "message": f"Insufficient credits (Required: {minutes_required}, Available: {available})",
            "minutes_required": minutes_required,
            "minutes_available": available,
        }

    # 0b. Quota enforcement check (hard caps, rate limits, cost monitoring)
    quota_result = await check_submission_allowed(
        user_id=user.id,
        source_platform=source or "audio",
        duration_seconds=duration_seconds or 0,
    )
    if not quota_result.allowed:
        return {
            "status": "skipped",
            "reason": quota_result.error_code,
            "message": quota_result.message,
        }

    # Resolve folder_id: if provided, use it; otherwise leave None (assigned later or via default)
    resolved_folder_id = folder_id
    if resolved_folder_id is None:
        # Auto-assign to default "Uncategorized" folder
        from media_summarizer.core.services.folder_service import ensure_default_folder
        default_folder = await ensure_default_folder(user.id)
        resolved_folder_id = default_folder.id

    # Create a tentative job to accompany the reservation
    job = ProcessingJob(
        user_id=user.id,
        user_email=user.email,
        source_url="",
        media_url=audio_url,
        media_key=media_key,
        media_image=media_image,
        media_date_published=media_date_published,
        folder_id=resolved_folder_id,
    )

    # Try to reserve globally
    reserved = await media_idempotence.reserve_or_skip(media_key, job.id)
    if not reserved:
        # Already known globally
        existing = await media_idempotence.already_processed(media_key)
        if (
            existing
            and existing.get("status") == "processed"
            and existing.get("job_id")
        ):
            existing_job_id = existing.get("job_id")
            existing_job = await database_async.get_processing_job_by_id(
                existing_job_id
            )

            # Load existing summary if available
            summary_content = None
            if existing_job and getattr(existing_job, "summary_s3_key", None):
                try:
                    summary_bucket = os.environ.get(
                        "SUMMARY_BUCKET", "media-summarizer-summaries"
                    )
                    raw = await s3.download_file_to_memory(
                        summary_bucket, existing_job.summary_s3_key
                    )
                    try:
                        parsed = json.loads(raw.decode("utf-8"))
                        summary_content = parsed.get("summary", parsed)
                    except Exception:
                        summary_content = raw.decode("utf-8", errors="ignore")
                except Exception:
                    summary_content = None

            # Create a billing/notification job for this user
            billing_job = ProcessingJob(
                user_id=user.id,
                user_email=user.email,
                source_url=getattr(existing_job, "source_url", ""),
                media_url=audio_url,
                media_key=media_key,
                media_date_published=media_date_published,
                folder_id=resolved_folder_id,
            )
            billing_job = await database_async.create_processing_job(billing_job)

            # Billing: allocate then finalize with known duration (fallback min 1)
            minutes_used = max(1, ceil((duration_seconds or 0) / 60))
            await allocate_hold_for_job(
                user_id=user.id, job_id=billing_job.id, minutes_estimated=minutes_used
            )
            await finalize_usage(billing_job.id, minutes_used)

            return {
                "job_id": billing_job.id,
                "status": "completed",
                "message": "Existing summary detected -- available in app (minutes charged)",
                "minutes_hold_estimated": minutes_used,
                "estimated_processing_time": "0",
                "media_title": media_title,
                "source_title": source_title,
                # Deprecated aliases
                "episode_title": media_title,
                "podcast_title": source_title,
            }

        # Not yet processed (reserved / in progress by another job)
        # Create a "watcher" job for this user, allocate an estimated hold, and register the watcher.
        minutes_estimated = (
            ceil(duration_seconds / 60)
            if duration_seconds and duration_seconds > 0
            else 0
        )
        watcher_job = await database_async.create_processing_job(job)
        try:
            await allocate_hold_for_job(
                user_id=user.id,
                job_id=watcher_job.id,
                minutes_estimated=minutes_estimated,
            )
        except Exception:
            # Allocation best-effort
            pass
        try:
            await media_watchers.add_watcher(
                media_key=media_key,
                user_id=user.id,
                email=user.email,
                job_id=watcher_job.id,
                minutes_estimated=minutes_estimated,
                source=source,
            )
        except Exception:
            # If the add fails (conditional), continue anyway
            pass

        return {
            "job_id": watcher_job.id,
            "status": "pending",
            "message": "Media already submitted -- processing in progress or reserved (you will be notified)",
            "minutes_hold_estimated": minutes_estimated,
            "estimated_processing_time": "a few minutes",
            "media_title": media_title,
            "source_title": source_title,
            # Deprecated aliases
            "episode_title": media_title,
            "podcast_title": source_title,
        }

    # New canonical processing: persist the job and orchestrate
    created_job = await database_async.create_processing_job(job)

    # Allocate minutes (estimate if duration known)
    minutes_estimated = (
        ceil(duration_seconds / 60) if duration_seconds and duration_seconds > 0 else 0
    )
    try:
        await allocate_hold_for_job(
            user_id=user.id, job_id=created_job.id, minutes_estimated=minutes_estimated
        )
    except Exception:
        # Allocation best-effort
        pass

    # Persist update
    await database_async.update_processing_job(created_job)

    # Enqueue to deepgram transcription queue (direct path, no download worker needed)
    await sqs.send_message(
        queue_name="deepgram-transcription-queue",
        message_body={
            "job_id": created_job.id,
            "user_id": user.id,
            "user_email": user.email,
            "audio_url": audio_url,
            "media_title": media_title,
            "source_title": source_title,
            "audio_duration_seconds": duration_seconds,
            "media_key": media_key,
            "media_image": media_image,
            # RSS feed URL for Podcasting 2.0 transcript lookup
            "feed_url": feed_url,
            "episode_guid": media_key,
            # Podcast audio from known open CDNs -> pull mode
            "deepgram_mode": "pull",
            # Deprecated aliases for downstream workers that may still read old keys
            "episode_title": media_title,
            "podcast_title": source_title,
            "episode_image": media_image,
        },
    )

    # Record submission in quota usage counters
    estimated_cost = estimate_submission_cost(source or "audio", duration_seconds or 0)
    await record_submission(
        user_id=user.id,
        source_platform=source or "audio",
        duration_seconds=duration_seconds or 0,
        estimated_cost_eur=estimated_cost,
    )

    return {
        "job_id": created_job.id,
        "status": created_job.status.value,
        "message": "Media submitted successfully for processing",
        "minutes_hold_estimated": minutes_estimated,
        "estimated_processing_time": "5-10 minutes",
        "media_title": media_title,
        "source_title": source_title,
        # Deprecated aliases
        "episode_title": media_title,
        "podcast_title": source_title,
    }
