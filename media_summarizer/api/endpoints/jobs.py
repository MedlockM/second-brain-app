"""Operational probe on a single processing job.

**This router is operational-only and deliberately not part of the library.**
Since task-220 the user library, Search, folder contents and counts are all read
from the durable `user_media` table; `processing_jobs` is expirable operational
state (its TTL is re-enabled in Phase 4). Anything that lists a user's media
must therefore never come from here.

The per-user listings this module used to expose (`GET /jobs/me`, `GET /jobs/`,
`GET /jobs/user/{user_id}`) were exactly such job-backed library reads, with no
consumer in the mobile app nor in the E2E suite, so task-220 deleted them. What
remains is a single lookup by job id, kept for debugging a specific pipeline run;
the canonical, durable view of a media item is `GET /api/media/{id}/status`.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from media_summarizer.api.dependencies.auth import AuthUser, get_current_user
from media_summarizer.utils import database_async

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobStatusResponse(BaseModel):
    """Response model for job status."""

    job_id: str
    status: str
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    error_step: Optional[str] = None
    podcast_title: Optional[str] = None
    episode_title: Optional[str] = None
    episode_image: Optional[str] = None
    episode_date_published: Optional[int] = None
    summary_url: Optional[str] = None
    quiz_s3_key: Optional[str] = None
    processing_durations: Optional[dict] = None


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str, current_user: AuthUser = Depends(get_current_user)
) -> JobStatusResponse:
    """Return the operational state of one processing job owned by the caller.

    A 404 here means the job row is gone (expired or never existed); it says
    nothing about the media item, which lives in `user_media`.
    """
    try:
        job = await database_async.get_processing_job_by_id(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied to this job")

        processing_durations = {}
        if job.download_duration:
            processing_durations["download"] = job.download_duration
        if job.transcription_duration:
            processing_durations["transcription"] = job.transcription_duration
        if job.summarization_duration:
            processing_durations["summarization"] = job.summarization_duration
        if job.total_duration:
            processing_durations["total"] = job.total_duration

        response = JobStatusResponse(
            job_id=job.id,
            status=job.status.value,
            created_at=job.created_at.isoformat(),
            updated_at=job.updated_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            error_message=job.error_message,
            error_step=job.error_step,
            podcast_title=job.source_platform,
            episode_title=job.title,
            episode_image=job.media_image,
            episode_date_published=job.media_date_published,
            summary_url=None,
            quiz_s3_key=job.quiz_s3_key,
            processing_durations=processing_durations if processing_durations else None,
        )

        logger.info(
            f"Retrieved job status for job {job_id}, status: {job.status.value}"
        )
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving job status for {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
