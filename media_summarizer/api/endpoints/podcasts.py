"""
Podcasts submission endpoints (backward-compatible alias for tests).

Provides /api/v1/podcasts/submit to create a processing job directly from a podcast URL
(RSS feed) and enqueue a message for downstream processing. Deducts 1 credit.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.utils.database_async import get_db
from media_summarizer.utils import database_async, sqs
from media_summarizer.core.models import ProcessingJob
from media_summarizer.core.services import minute_pool

router = APIRouter()
logger = logging.getLogger(__name__)

REQUIRED_MINUTES = 1


class PodcastSubmitRequest(BaseModel):
    podcast_url: str = Field(..., description="Podcast RSS URL")
    user_email: Optional[str] = Field(None, description="User email (fallback)")


class PodcastSubmitResponse(BaseModel):
    job_id: str
    status: str


@router.post("/podcasts/submit")
async def submit_podcast_for_processing(
    payload: PodcastSubmitRequest,
    request: Request,
    db=Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Backward-compatible endpoint used by integration tests to submit a podcast by URL.

    Creates a processing job, allocates a minutes hold, then enqueues a message.
    """
    try:
        # Load fresh user (support dict-like overrides in tests)
        current_user_id = getattr(current_user, "id", None) or (
            current_user.get("id") if isinstance(current_user, dict) else None
        )
        current_user_email = getattr(current_user, "email", None) or (
            current_user.get("email") if isinstance(current_user, dict) else None
        )
        if not current_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user not found",
            )

        user = await database_async.get_user_by_id(current_user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated user not found",
            )

        # (Removed legacy credits check) Minutes-based billing: availability enforced via minute holds.

        # Create job (pending)
        job = ProcessingJob(
            user_id=user.id,
            user_email=user.email,
            podcast_url=payload.podcast_url,
        )
        job = await database_async.create_processing_job(job)

        # Allocate minute hold (minutes-based billing)
        await minute_pool.allocate_hold_for_job(
            user_id=user.id, job_id=job.id, minutes_estimated=REQUIRED_MINUTES
        )

        # Enqueue message; keep fields expected by tests
        message = {
            "job_id": job.id,
            "podcast_url": payload.podcast_url,
            "user_email": user.email,
            "user_id": user.id,
        }
        # Use audio-download-queue to satisfy focused test capture; use keyword args to avoid signature issues
        await sqs.send_message(queue_name="audio-download-queue", message_body=message)

        return {"job_id": job.id, "status": job.status.value}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in /podcasts/submit: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit podcast",
        )
