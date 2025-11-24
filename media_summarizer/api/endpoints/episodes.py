"""
Episodes API endpoints for retrieving user's completed episodes with summaries and quizzes.
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from media_summarizer.utils import database_async, s3
from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.models import JobStatus
import json
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/episodes", tags=["episodes"])


class EpisodeResponse(BaseModel):
    """Response model for a single episode with summary and quiz."""

    job_id: str = Field(..., description="Job ID")
    podcast_title: str = Field(..., description="Podcast title")
    podcast_id: str = Field(default="", description="Podcast ID")
    episode_title: str = Field(..., description="Episode title")
    episode_image: str = Field(default="", description="Episode image URL")
    episode_date_published: int = Field(default=0, description="Episode publication date (Unix timestamp)")
    created_at: int = Field(..., description="Job submission timestamp (Unix timestamp) - for sorting")
    completed_at: Optional[int] = Field(None, description="Job completion timestamp (Unix timestamp)")
    summary: Dict[str, Any] = Field(..., description="Summary content")
    quiz: Dict[str, Any] = Field(..., description="Quiz content")


class MyEpisodesResponse(BaseModel):
    """Response model for my episodes list."""

    status: str = Field(..., description="Response status")
    episodes: List[EpisodeResponse] = Field(..., description="List of episodes")
    count: int = Field(..., description="Number of episodes")


@router.get("/my-episodes", response_model=MyEpisodesResponse)
async def get_my_episodes(
    current_user: AuthUser = Depends(get_current_user),
) -> MyEpisodesResponse:
    """
    Get all completed episodes (with summaries and quizzes) for the authenticated user.

    Args:
        current_user: The authenticated user

    Returns:
        MyEpisodesResponse: List of all completed episodes with their summaries and quizzes

    Raises:
        HTTPException: If there's an error retrieving episodes
    """
    try:
        logger.info(f"Retrieving episodes for user {current_user.id}")

        # Get all jobs for the user
        jobs = await database_async.get_processing_jobs_by_user_id(current_user.id)

        # Filter only jobs that have BOTH summary AND quiz in S3
        jobs_with_content = [
            job for job in jobs 
            if job.summary_s3_key and job.quiz_s3_key
        ]

        logger.info(
            f"Found {len(jobs_with_content)} jobs with summaries and quizzes for user {current_user.id}"
        )

        episodes = []
        summary_bucket = os.environ.get("SUMMARY_BUCKET", "media-summarizer-summaries")
        quiz_bucket = os.environ.get("QUIZ_BUCKET", "media-summarizer-quizzes")

        for job in jobs_with_content:
            try:
                # Download summary and quiz in parallel
                summary_task = s3.download_file_to_memory(
                    bucket=summary_bucket, key=job.summary_s3_key
                )
                quiz_task = s3.download_file_to_memory(
                    bucket=quiz_bucket, key=job.quiz_s3_key
                )
                
                summary_content, quiz_content = await asyncio.gather(
                    summary_task, quiz_task, return_exceptions=True
                )
                
                # Handle potential errors from gather
                if isinstance(summary_content, Exception):
                    logger.error(f"Error downloading summary for job {job.id}: {summary_content}")
                    continue
                if isinstance(quiz_content, Exception):
                    logger.error(f"Error downloading quiz for job {job.id}: {quiz_content}")
                    continue

                # Parse JSON
                summary_data = json.loads(summary_content.decode("utf-8"))
                quiz_data = json.loads(quiz_content.decode("utf-8"))

                # Extract relevant fields
                # created_at: when user submitted the job (for sorting)
                # episode_date_published: when the episode was published (for display)
                episode_response = EpisodeResponse(
                    job_id=job.id,
                    podcast_title=summary_data.get("podcast_title", "Unknown Podcast"),
                    podcast_id=job.podcast_id or "",
                    episode_title=summary_data.get("episode_title", "Unknown Episode"),
                    episode_image=summary_data.get("episode_image", ""),
                    episode_date_published=job.episode_date_published or 0,
                    created_at=int(job.created_at.timestamp()),
                    completed_at=int(job.completed_at.timestamp()) if job.completed_at else None,
                    summary=summary_data.get("summary", {}),
                    quiz=quiz_data,
                )

                episodes.append(episode_response)

            except Exception as e:
                logger.error(
                    f"Error retrieving episode data for job {job.id}: {str(e)}",
                    exc_info=True,
                )
                # Continue with other jobs even if one fails
                continue

        # Sort by created_at DESC (most recently submitted jobs first)
        episodes.sort(
            key=lambda x: x.created_at,
            reverse=True,
        )

        logger.info(
            f"Successfully retrieved {len(episodes)} episodes for user {current_user.id}"
        )

        return MyEpisodesResponse(
            status="success", episodes=episodes, count=len(episodes)
        )

    except Exception as e:
        logger.error(f"Error retrieving episodes for user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve episodes: {str(e)}",
        )
