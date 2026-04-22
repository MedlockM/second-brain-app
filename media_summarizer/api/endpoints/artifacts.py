from __future__ import annotations

import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.utils import database_async, sqs
from media_summarizer.utils.logging_config import bind_log_context, log_event, reset_log_context

router = APIRouter()
logger = logging.getLogger(__name__)

SUMMARIZATION_QUEUE = os.environ.get("SUMMARIZATION_QUEUE", "summarization-queue")
NOTES_QUEUE = os.environ.get("NOTES_QUEUE", "notes-queue")
QUIZ_QUEUE = os.environ.get("QUIZ_QUEUE", "quiz-queue")
FLASHCARDS_QUEUE = os.environ.get("FLASHCARDS_QUEUE", "flashcards-queue")

_ARTIFACT_TYPE_TO_QUEUE = {
    "summary": SUMMARIZATION_QUEUE,
    "notes": NOTES_QUEUE,
    "quiz": QUIZ_QUEUE,
    "flashcards": FLASHCARDS_QUEUE,
}
_ARTIFACT_TYPE_TO_S3_KEY_ATTR = {
    "summary": "summary_s3_key",
    "notes": None,
    "quiz": None,
    "flashcards": None,
}

_ALLOWED_ARTIFACT_TYPES = frozenset(
    t.strip() for t in os.environ.get("ARTIFACT_TYPES_ALLOWED", "summary,notes,quiz,flashcards").split(",")
)


class ArtifactCreateRequest(BaseModel):
    artifact_type: str = Field(..., description="Type of artifact: summary, notes, quiz, flashcards")


class ArtifactResponse(BaseModel):
    artifact_id: str
    artifact_type: str
    media_item_id: str
    status: str
    s3_key: Optional[str] = None


class ArtifactListResponse(BaseModel):
    artifacts: List[ArtifactResponse]
    media_item_id: str


async def _get_job_for_user(media_item_id: str, user_id: str):
    job = await database_async.get_processing_job_by_id(media_item_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media item not found")
    if job.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return job


@router.post("/media/{media_item_id}/artifacts", response_model=ArtifactResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_artifact(
    media_item_id: str,
    payload: ArtifactCreateRequest,
    request: Request,
    current_user: AuthUser = Depends(get_current_user),
):
    artifact_type = (payload.artifact_type or "").strip().lower()
    token = bind_log_context(
        user_id=current_user.id,
        media_item_id=media_item_id,
        artifact_type=artifact_type,
    )
    try:
        if artifact_type not in _ALLOWED_ARTIFACT_TYPES:
            log_event(
                logger,
                logging.WARNING,
                "artifact.create.invalid_type",
                "Invalid artifact type requested",
                artifact_type=artifact_type,
                error_code="INVALID_ARTIFACT_TYPE",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid artifact_type '{artifact_type}'. Allowed: {sorted(_ALLOWED_ARTIFACT_TYPES)}",
            )

        job = await _get_job_for_user(media_item_id, current_user.id)

        queue = _ARTIFACT_TYPE_TO_QUEUE.get(artifact_type, SUMMARIZATION_QUEUE)
        await sqs.send_message(
            queue_name=queue,
            message_body={
                "job_id": job.id,
                "media_item_id": job.id,
                "artifact_type": artifact_type,
                "user_id": current_user.id,
                "transcript_s3_key": job.transcription_s3_key,
            },
        )

        log_event(
            logger,
            logging.INFO,
            "artifact.create.requested",
            "Artifact generation queued",
            media_item_id=media_item_id,
            artifact_id=job.id,
            artifact_type=artifact_type,
            queue=queue,
        )

        return ArtifactResponse(
            artifact_id=job.id,
            artifact_type=artifact_type,
            media_item_id=media_item_id,
            status="queued",
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "artifact.create.failed",
            "Failed to queue artifact generation",
            media_item_id=media_item_id,
            artifact_type=artifact_type,
            error_type=type(exc).__name__,
            error_code="ARTIFACT_CREATE_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to queue artifact generation",
        )
    finally:
        reset_log_context(token)


@router.get("/media/{media_item_id}/artifacts", response_model=ArtifactListResponse)
async def list_artifacts(
    media_item_id: str,
    request: Request,
    current_user: AuthUser = Depends(get_current_user),
):
    token = bind_log_context(user_id=current_user.id, media_item_id=media_item_id)
    try:
        job = await _get_job_for_user(media_item_id, current_user.id)

        artifacts = []
        if job.summary_s3_key:
            artifacts.append(
                ArtifactResponse(
                    artifact_id=f"{job.id}:summary",
                    artifact_type="summary",
                    media_item_id=media_item_id,
                    status="completed",
                    s3_key=job.summary_s3_key,
                )
            )

        log_event(
            logger,
            logging.INFO,
            "artifact.list.succeeded",
            "Artifact list retrieved",
            media_item_id=media_item_id,
            artifact_count=len(artifacts),
        )

        return ArtifactListResponse(artifacts=artifacts, media_item_id=media_item_id)

    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "artifact.list.failed",
            "Failed to list artifacts",
            media_item_id=media_item_id,
            error_type=type(exc).__name__,
            error_code="ARTIFACT_LIST_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list artifacts",
        )
    finally:
        reset_log_context(token)


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    artifact_id: str,
    request: Request,
    current_user: AuthUser = Depends(get_current_user),
):
    token = bind_log_context(user_id=current_user.id, artifact_id=artifact_id)
    try:
        # artifact_id uses the format "{media_item_id}:{artifact_type}" or plain job id for summary
        if ":" in artifact_id:
            media_item_id, artifact_type = artifact_id.split(":", 1)
        else:
            media_item_id = artifact_id
            artifact_type = "summary"

        job = await _get_job_for_user(media_item_id, current_user.id)

        s3_key: Optional[str] = None
        artifact_status = "not_found"

        if artifact_type == "summary" and job.summary_s3_key:
            s3_key = job.summary_s3_key
            artifact_status = "completed"
        elif artifact_type == "summary":
            artifact_status = "pending"

        if artifact_status == "not_found":
            log_event(
                logger,
                logging.WARNING,
                "artifact.get.not_found",
                "Artifact not found",
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                media_item_id=media_item_id,
                error_code="ARTIFACT_NOT_FOUND",
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

        log_event(
            logger,
            logging.INFO,
            "artifact.get.succeeded",
            "Artifact retrieved",
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            media_item_id=media_item_id,
            status=artifact_status,
        )

        return ArtifactResponse(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            media_item_id=media_item_id,
            status=artifact_status,
            s3_key=s3_key,
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "artifact.get.failed",
            "Failed to retrieve artifact",
            artifact_id=artifact_id,
            error_type=type(exc).__name__,
            error_code="ARTIFACT_GET_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve artifact",
        )
    finally:
        reset_log_context(token)
