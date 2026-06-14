from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.services.artifact_service import (
    ArtifactGenerationDisabledError,
    ArtifactTranscriptNotReadyError,
    ArtifactTypeNotEnabledError,
    get_media_artifact_record,
    list_media_artifact_records,
    request_artifact_generation,
)
from media_summarizer.utils import database_async, s3
from media_summarizer.utils.logging_config import bind_log_context, log_event, reset_log_context

router = APIRouter()
logger = logging.getLogger(__name__)


class ArtifactCreateRequest(BaseModel):
    artifact_type: str = Field(..., description="Type of artifact: summary, summary_short, summary_detailed, notes, quiz, flashcards")
    parameters: Optional[dict] = Field(default=None, description="Optional parameters for artifact generation")


class ArtifactResponse(BaseModel):
    artifact_id: str
    artifact_type: str
    media_item_id: str
    status: str
    s3_key: Optional[str] = None


class ArtifactListResponse(BaseModel):
    artifacts: List[ArtifactResponse]
    media_item_id: str


class ArtifactContentResponse(BaseModel):
    artifact_id: str
    artifact_type: str
    media_item_id: str
    status: str
    content: Dict[str, Any] = Field(
        ..., description="Parsed JSON content of the artifact (summary, notes, quiz, flashcards)"
    )


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
        job = await _get_job_for_user(media_item_id, current_user.id)

        record, reused = await request_artifact_generation(
            media_item_id=media_item_id,
            job=job,
            artifact_type=artifact_type,
            parameters=payload.parameters,
            reading_language=current_user.reading_language,
        )

        log_event(
            logger,
            logging.INFO,
            "artifact.create.requested",
            "Artifact generation queued" if not reused else "Artifact reused from cache",
            media_item_id=media_item_id,
            artifact_id=record.artifact_id,
            artifact_type=artifact_type,
            reused=reused,
        )

        s3_key: Optional[str] = None
        if record.storage is not None:
            s3_key = record.storage.key

        return ArtifactResponse(
            artifact_id=record.artifact_id,
            artifact_type=record.artifact_type.value,
            media_item_id=media_item_id,
            status=record.status.value,
            s3_key=s3_key,
        )

    except ArtifactTypeNotEnabledError as exc:
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
            detail=str(exc),
        )
    except ArtifactGenerationDisabledError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Artifact generation is currently disabled",
        )
    except ArtifactTranscriptNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
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
        await _get_job_for_user(media_item_id, current_user.id)

        records = await list_media_artifact_records(media_item_id)
        artifacts = []
        for record in records:
            # Skip request pointers (they start with "request#")
            if record.artifact_id.startswith("request#"):
                continue
            s3_key: Optional[str] = None
            if record.storage is not None:
                s3_key = record.storage.key
            artifacts.append(
                ArtifactResponse(
                    artifact_id=record.artifact_id,
                    artifact_type=record.artifact_type.value,
                    media_item_id=media_item_id,
                    status=record.status.value,
                    s3_key=s3_key,
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
        record = await get_media_artifact_record(artifact_id)
        if record is None:
            log_event(
                logger,
                logging.WARNING,
                "artifact.get.not_found",
                "Artifact not found",
                artifact_id=artifact_id,
                error_code="ARTIFACT_NOT_FOUND",
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

        # Verify ownership
        await _get_job_for_user(record.media_item_id, current_user.id)

        s3_key: Optional[str] = None
        if record.storage is not None:
            s3_key = record.storage.key

        log_event(
            logger,
            logging.INFO,
            "artifact.get.succeeded",
            "Artifact retrieved",
            artifact_id=artifact_id,
            artifact_type=record.artifact_type.value,
            media_item_id=record.media_item_id,
            status=record.status.value,
        )

        return ArtifactResponse(
            artifact_id=record.artifact_id,
            artifact_type=record.artifact_type.value,
            media_item_id=record.media_item_id,
            status=record.status.value,
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


@router.get("/artifacts/{artifact_id}/content", response_model=ArtifactContentResponse)
async def get_artifact_content(
    artifact_id: str,
    request: Request,
    current_user: AuthUser = Depends(get_current_user),
):
    """Return the JSON payload an artifact resolved to.

    The worker pipeline writes each artifact as a JSON blob in its dedicated
    S3 bucket (one bucket per artifact type). This endpoint resolves the
    record, verifies ownership, downloads the blob and inlines the parsed
    content in the response so the mobile client doesn't need to deal with
    presigned URLs.
    """
    token = bind_log_context(user_id=current_user.id, artifact_id=artifact_id)
    try:
        record = await get_media_artifact_record(artifact_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Artifact not found",
            )

        # Verify ownership
        await _get_job_for_user(record.media_item_id, current_user.id)

        if record.storage is None:
            # Artifact exists but isn't ready yet (queued / generating / failed).
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Artifact is not ready (status: {record.status.value}). "
                    "Try again once generation completes."
                ),
            )

        try:
            payload_bytes = await s3.download_file_to_memory(
                bucket=record.storage.bucket,
                key=record.storage.key,
            )
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "artifact.content.download_failed",
                "Failed to download artifact payload from S3",
                artifact_id=artifact_id,
                bucket=record.storage.bucket,
                key=record.storage.key,
                error_type=type(exc).__name__,
                error_code="ARTIFACT_CONTENT_DOWNLOAD_FAILED",
                exc_info=exc,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Artifact storage is currently unreachable",
            )

        try:
            content = json.loads(payload_bytes.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            log_event(
                logger,
                logging.ERROR,
                "artifact.content.parse_failed",
                "Failed to parse artifact payload as JSON",
                artifact_id=artifact_id,
                error_type=type(exc).__name__,
                error_code="ARTIFACT_CONTENT_PARSE_FAILED",
                exc_info=exc,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Artifact payload is malformed",
            )

        if not isinstance(content, dict):
            content = {"value": content}

        log_event(
            logger,
            logging.INFO,
            "artifact.content.succeeded",
            "Artifact content retrieved",
            artifact_id=artifact_id,
            artifact_type=record.artifact_type.value,
            media_item_id=record.media_item_id,
            content_size=len(payload_bytes),
        )

        return ArtifactContentResponse(
            artifact_id=record.artifact_id,
            artifact_type=record.artifact_type.value,
            media_item_id=record.media_item_id,
            status=record.status.value,
            content=content,
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "artifact.content.failed",
            "Failed to retrieve artifact content",
            artifact_id=artifact_id,
            error_type=type(exc).__name__,
            error_code="ARTIFACT_CONTENT_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve artifact content",
        )
    finally:
        reset_log_context(token)
