"""
Media API endpoints.

Provides operations on media items (processing jobs from the user's perspective).
Supports URL ingestion, status retrieval, and folder assignment via PATCH.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.models import ProcessingJob
from media_summarizer.core.services import minute_pool
from media_summarizer.core.services import folder_service
from media_summarizer.core.services import tag_service
from media_summarizer.utils import database_async, sqs
from media_summarizer.utils.logging_config import bind_log_context, log_event, reset_log_context

router = APIRouter()
logger = logging.getLogger(__name__)

_AUDIO_EXTENSIONS = (".mp3", ".m4a", ".aac", ".ogg", ".wav", ".flac", ".opus")
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"}
_TIKTOK_HOSTS = {"tiktok.com", "www.tiktok.com", "vm.tiktok.com"}
_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com"}

DEEPGRAM_TRANSCRIPTION_QUEUE = os.environ.get("DEEPGRAM_TRANSCRIPTION_QUEUE", "deepgram-transcription-queue")
YOUTUBE_INGESTION_QUEUE = os.environ.get("YOUTUBE_INGESTION_QUEUE", "youtube-ingestion-queue")
TIKTOK_INGESTION_QUEUE = os.environ.get("TIKTOK_INGESTION_QUEUE", "tiktok-ingestion-queue")
INSTAGRAM_INGESTION_QUEUE = os.environ.get("INSTAGRAM_INGESTION_QUEUE", "instagram-ingestion-queue")
PODCASTINDEX_RESOLUTION_QUEUE = os.environ.get("PODCASTINDEX_RESOLUTION_QUEUE", "podcastindex-resolution-queue")
ARTICLE_EXTRACTION_QUEUE = os.environ.get("ARTICLE_EXTRACTION_QUEUE", "article-extraction-queue")

REQUIRED_MINUTES = 1


def _detect_platform(url: str) -> tuple[str, str]:
    """Return (source_platform, resolver_key) for a given URL."""
    try:
        split = urlsplit(url)
        host = (split.netloc or "").lower().removeprefix("www.")
        path = (split.path or "").lower()
    except ValueError:
        return "unknown", "unknown"

    if host in _YOUTUBE_HOSTS:
        return "youtube", "youtube"
    if host in _TIKTOK_HOSTS:
        return "tiktok", "tiktok"
    if host in _INSTAGRAM_HOSTS:
        return "instagram", "getinsaver"
    if path.endswith(_AUDIO_EXTENSIONS):
        return "audio", "deepgram"
    return "web", "article"


class IngestUrlRequest(BaseModel):
    url: str = Field(..., description="URL to ingest (podcast RSS, YouTube, TikTok, Instagram, article, or direct audio)")
    tag_ids: Optional[List[str]] = Field(
        None, description="Optional list of tag IDs to associate with the media item at ingestion time"
    )


class IngestUrlResponse(BaseModel):
    media_item_id: str
    status: str
    source_platform: str


class MediaItemResponse(BaseModel):
    media_item_id: str
    status: str
    source_platform: Optional[str] = None
    error_message: Optional[str] = None
    progress: int


# ---------- Folder assignment models ----------

class PatchMediaRequest(BaseModel):
    folder_id: Optional[str] = Field(
        None,
        description="Folder ID to assign the media to (null for Uncategorized)",
    )


class PatchMediaResponse(BaseModel):
    status: str = "success"
    media_id: str
    folder_id: str
    previous_folder_id: Optional[str] = None


# ---------- Tag assignment models ----------

class PatchMediaTagsRequest(BaseModel):
    tag_ids: List[str] = Field(
        ..., description="List of tag IDs to assign to the media item (replaces existing)"
    )


class PatchMediaTagsResponse(BaseModel):
    status: str = "success"
    media_id: str
    tag_ids: List[str]
    previous_tag_ids: List[str]


# ---------- Endpoints ----------

@router.post("/ingest-url", response_model=IngestUrlResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_url(
    payload: IngestUrlRequest,
    request: Request,
    current_user: AuthUser = Depends(get_current_user),
):
    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url is required")

    source_platform, resolver_key = _detect_platform(url)
    token = bind_log_context(
        user_id=current_user.id,
        source_platform=source_platform,
        resolver_key=resolver_key,
    )
    try:
        log_event(
            logger,
            logging.INFO,
            "media.ingest.started",
            "Media ingest URL received",
            source_platform=source_platform,
            resolver_key=resolver_key,
        )

        user = await database_async.get_user_by_id(current_user.id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        job = ProcessingJob(user_id=user.id, user_email=user.email, source_url=url)

        # Associate tags at ingestion time if provided
        if payload.tag_ids:
            from media_summarizer.core.constants import MAX_TAGS_PER_MEDIA

            unique_tag_ids = list(dict.fromkeys(payload.tag_ids))
            if len(unique_tag_ids) > MAX_TAGS_PER_MEDIA:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot assign more than {MAX_TAGS_PER_MEDIA} tags",
                )
            # Validate tags belong to user
            user_tags = await database_async.get_tags_by_user_id(user.id)
            user_tag_ids = {t.id for t in user_tags}
            invalid_ids = [tid for tid in unique_tag_ids if tid not in user_tag_ids]
            if invalid_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Tag(s) not found: {', '.join(invalid_ids)}",
                )
            job.tag_ids = unique_tag_ids

        job = await database_async.create_processing_job(job)

        await minute_pool.allocate_hold_for_job(
            user_id=user.id,
            job_id=job.id,
            minutes_estimated=REQUIRED_MINUTES,
        )

        base_payload = {
            "job_id": job.id,
            "user_id": user.id,
            "source_platform": source_platform,
            "normalized_url": url,
        }

        if source_platform == "youtube":
            await sqs.send_message(queue_name=YOUTUBE_INGESTION_QUEUE, message_body=base_payload)
        elif source_platform == "tiktok":
            await sqs.send_message(queue_name=TIKTOK_INGESTION_QUEUE, message_body=base_payload)
        elif source_platform == "instagram":
            await sqs.send_message(queue_name=INSTAGRAM_INGESTION_QUEUE, message_body=base_payload)
        elif source_platform == "audio":
            await sqs.send_message(
                queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
                message_body={**base_payload, "audio_url": url},
            )
        elif source_platform == "web":
            await sqs.send_message(queue_name=ARTICLE_EXTRACTION_QUEUE, message_body=base_payload)
        else:
            await sqs.send_message(
                queue_name=PODCASTINDEX_RESOLUTION_QUEUE,
                message_body={**base_payload, "feed_url": url},
            )

        log_event(
            logger,
            logging.INFO,
            "media.ingest.created",
            "Media item created and queued",
            media_item_id=job.id,
            source_platform=source_platform,
            resolver_key=resolver_key,
            queue=(
                YOUTUBE_INGESTION_QUEUE if source_platform == "youtube"
                else TIKTOK_INGESTION_QUEUE if source_platform == "tiktok"
                else INSTAGRAM_INGESTION_QUEUE if source_platform == "instagram"
                else DEEPGRAM_TRANSCRIPTION_QUEUE if source_platform == "audio"
                else ARTICLE_EXTRACTION_QUEUE if source_platform == "web"
                else PODCASTINDEX_RESOLUTION_QUEUE
            ),
        )

        return IngestUrlResponse(
            media_item_id=job.id,
            status=job.status.value,
            source_platform=source_platform,
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "media.ingest.failed",
            "Media ingest failed",
            source_platform=source_platform,
            resolver_key=resolver_key,
            error_type=type(exc).__name__,
            error_code="INGEST_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest URL",
        )
    finally:
        reset_log_context(token)


@router.get("/{media_item_id}", response_model=MediaItemResponse)
async def get_media_item(
    media_item_id: str,
    request: Request,
    current_user: AuthUser = Depends(get_current_user),
):
    token = bind_log_context(user_id=current_user.id, media_item_id=media_item_id)
    try:
        job = await database_async.get_processing_job_by_id(media_item_id)

        if job is None:
            log_event(
                logger,
                logging.WARNING,
                "media.get.not_found",
                "Media item not found",
                media_item_id=media_item_id,
                error_code="MEDIA_NOT_FOUND",
            )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media item not found")

        if job.user_id != current_user.id:
            log_event(
                logger,
                logging.WARNING,
                "media.get.forbidden",
                "Access denied to media item",
                media_item_id=media_item_id,
                error_code="ACCESS_DENIED",
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        log_event(
            logger,
            logging.INFO,
            "media.get.succeeded",
            "Media item retrieved",
            media_item_id=media_item_id,
            status=job.status.value,
        )

        return MediaItemResponse(
            media_item_id=job.id,
            status=job.status.value,
            source_platform=None,
            error_message=job.error_message,
            progress=job.get_progress_percentage(),
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "media.get.failed",
            "Failed to retrieve media item",
            media_item_id=media_item_id,
            error_type=type(exc).__name__,
            error_code="GET_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve media item",
        )
    finally:
        reset_log_context(token)


@router.patch("/{media_id}", response_model=PatchMediaResponse)
async def patch_media(
    media_id: str,
    payload: PatchMediaRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> PatchMediaResponse:
    """Update a media item. Currently supports changing the folder assignment."""
    try:
        result = await folder_service.assign_folder_to_media(
            user_id=current_user.id,
            media_id=media_id,
            folder_id=payload.folder_id,
        )
        return PatchMediaResponse(
            status="success",
            media_id=result["media_id"],
            folder_id=result["folder_id"],
            previous_folder_id=result["previous_folder_id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error patching media {media_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update media item",
        )


@router.patch("/{media_id}/tags", response_model=PatchMediaTagsResponse)
async def patch_media_tags(
    media_id: str,
    payload: PatchMediaTagsRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> PatchMediaTagsResponse:
    """Associate or dissociate tags on a media item (replaces existing tag list)."""
    try:
        result = await tag_service.set_media_tags(
            user_id=current_user.id,
            media_id=media_id,
            tag_ids=payload.tag_ids,
        )
        return PatchMediaTagsResponse(
            status="success",
            media_id=result["media_id"],
            tag_ids=result["tag_ids"],
            previous_tag_ids=result["previous_tag_ids"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error setting tags on media {media_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update media tags",
        )
