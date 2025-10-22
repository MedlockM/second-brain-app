"""
Jobs API endpoints for tracking processing job status.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from media_summarizer.utils import database_async
from media_summarizer.api.dependencies.auth import get_current_user, AuthUser
from media_summarizer.core.models import ProcessingJob

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobStatusResponse(BaseModel):
    """Response model for job status."""

    job_id: str
    status: str
    progress_percentage: int
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    error_step: Optional[str] = None
    podcast_title: Optional[str] = None
    episode_title: Optional[str] = None
    processing_durations: Optional[dict] = None


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str, current_user: AuthUser = Depends(get_current_user)
) -> JobStatusResponse:
    """
    Get the status of a processing job.

    Args:
        job_id: The ID of the processing job
        current_user: The authenticated user

    Returns:
        JobStatusResponse: The current status of the job

    Raises:
        HTTPException: If job not found or user doesn't have access
    """
    try:
        # Get the job from database
        job = await database_async.get_processing_job_by_id(job_id)

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Check if the user owns this job
        if job.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Access denied to this job")

        # Prepare processing durations
        processing_durations = {}
        if job.download_duration:
            processing_durations["download"] = job.download_duration
        if job.transcription_duration:
            processing_durations["transcription"] = job.transcription_duration
        if job.summarization_duration:
            processing_durations["summarization"] = job.summarization_duration
        if job.total_duration:
            processing_durations["total"] = job.total_duration

        # Create response
        response = JobStatusResponse(
            job_id=job.id,
            status=job.status.value,
            progress_percentage=job.get_progress_percentage(),
            created_at=job.created_at.isoformat(),
            updated_at=job.updated_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            error_message=job.error_message,
            error_step=job.error_step,
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


@router.get("/user/{user_id}", response_model=list[JobStatusResponse])
async def get_user_jobs(
    user_id: str, current_user: AuthUser = Depends(get_current_user)
) -> list[JobStatusResponse]:
    """
    Get all jobs for a specific user.

    Args:
        user_id: The ID of the user
        current_user: The authenticated user

    Returns:
        List[JobStatusResponse]: List of jobs for the user

    Raises:
        HTTPException: If user doesn't have access
    """
    try:
        # Check if the user is requesting their own jobs
        if user_id != current_user.id:
            raise HTTPException(
                status_code=403, detail="Access denied to other user's jobs"
            )

        # Get all jobs for the user
        jobs = await database_async.get_processing_jobs_by_user_id(user_id)

        # Convert to response format
        job_responses = []
        for job in jobs:
            # Prepare processing durations
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
                progress_percentage=job.get_progress_percentage(),
                created_at=job.created_at.isoformat(),
                updated_at=job.updated_at.isoformat(),
                started_at=job.started_at.isoformat() if job.started_at else None,
                completed_at=job.completed_at.isoformat() if job.completed_at else None,
                error_message=job.error_message,
                error_step=job.error_step,
                processing_durations=processing_durations
                if processing_durations
                else None,
            )
            job_responses.append(response)

        logger.info(f"Retrieved {len(job_responses)} jobs for user {user_id}")
        return job_responses

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving jobs for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
