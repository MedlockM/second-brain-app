"""
Media API endpoints.

Provides operations on media items (processing jobs from the user's perspective).
Supports URL ingestion, file upload (document parsing), status retrieval, and folder assignment via PATCH.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File, status
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.models import ProcessingJob
from media_summarizer.core.ports.document_parser import DocumentFormat
from media_summarizer.core.services import minute_pool
from media_summarizer.core.services import folder_service
from media_summarizer.core.services import tag_service
from media_summarizer.core.services import media_search_service
from media_summarizer.core.services.media_search_service import SearchFilters
from media_summarizer.core.services.quota_enforcer import (
    check_submission_allowed,
    record_submission,
    estimate_submission_cost,
)
from media_summarizer.core.services.raw_content_service import (
    get_raw_content,
    RawContentNotAvailableError,
)
from media_summarizer.utils import database_async, s3, sqs
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
DOCUMENT_PARSING_QUEUE = os.environ.get("DOCUMENT_PARSING_QUEUE", "document-parsing-queue")
DOCUMENT_BUCKET = os.environ.get("DOCUMENT_BUCKET", "media-summarizer-documents")
AUDIO_BUCKET = os.environ.get("AUDIO_BUCKET", "media-summarizer-audio")

# Pre-signed URL validity for audio uploads (10 minutes)
AUDIO_PRESIGNED_URL_EXPIRATION = int(os.environ.get("AUDIO_PRESIGNED_URL_EXPIRATION", "600"))

# Max upload size: 50MB
MAX_UPLOAD_SIZE_BYTES = int(os.environ.get("MAX_UPLOAD_SIZE_BYTES", str(50 * 1024 * 1024)))

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
        return "instagram", "apify"
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


class UploadDocumentResponse(BaseModel):
    media_item_id: str
    status: str
    source_platform: str = "document"
    file_name: str


class UploadAudioResponse(BaseModel):
    media_item_id: str
    status: str
    source_platform: str = "audio"


class MediaItemResponse(BaseModel):
    media_item_id: str
    status: str
    source_platform: Optional[str] = None
    error_message: Optional[str] = None
    progress: int
    extraction_metadata: Optional[dict] = None
    transcription_metadata: Optional[dict] = None
    transcript_source: Optional[str] = Field(
        None,
        description=(
            "How the transcript was obtained "
            "(e.g. 'deepgram', 'apify_native', 'yt-dlp_native')"
        ),
    )


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


# ---------- Search / List models ----------

class MediaSearchItem(BaseModel):
    media_item_id: str
    title: Optional[str] = None
    source_platform: Optional[str] = None
    media_type: Optional[str] = None
    status: str
    folder_id: Optional[str] = None
    tag_ids: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    media_image: Optional[str] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None
    progress: int
    error_message: Optional[str] = None


class MediaSearchResponse(BaseModel):
    status: str = "success"
    items: List[MediaSearchItem]
    total: int = Field(..., description="Total number of items matching filters")
    next_cursor: Optional[str] = Field(None, description="Cursor for next page")
    has_more: bool = Field(..., description="Whether more items are available")


# ---------- Endpoints ----------

@router.get("", response_model=MediaSearchResponse)
async def search_media(
    q: Optional[str] = None,
    tags: Optional[str] = None,
    folder_id: Optional[str] = None,
    source: Optional[str] = None,
    type: Optional[str] = None,
    status_filter: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = 20,
    current_user: AuthUser = Depends(get_current_user),
) -> MediaSearchResponse:
    """Search and list user's media items with metadata filters.

    Query Parameters:
        q: Text search on title (case-insensitive substring match)
        tags: Comma-separated tag IDs to filter by (any match)
        folder_id: Filter by folder (includes sub-folders)
        source: Filter by source platform (youtube, tiktok, web, audio, etc.)
        type: Filter by media type (video, article, podcast, audio)
        status_filter: Filter by job status (pending, completed, failed, etc.)
        cursor: Pagination cursor from previous response
        limit: Page size (1-100, default 20)
    """
    try:
        # Parse comma-separated tags
        tag_list: Optional[List[str]] = None
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]

        filters = SearchFilters(
            q=q,
            tags=tag_list,
            folder_id=folder_id,
            source=source,
            media_type=type,
            status=status_filter,
        )

        result = await media_search_service.search_media(
            user_id=current_user.id,
            filters=filters,
            cursor=cursor,
            limit=limit,
        )

        items = [MediaSearchItem(**item) for item in result.items]

        return MediaSearchResponse(
            status="success",
            items=items,
            total=result.total_filtered,
            next_cursor=result.next_cursor,
            has_more=result.has_more,
        )

    except Exception as e:
        logger.error(f"Error searching media for user {current_user.id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search media items",
        )


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

        # Quota enforcement check before processing
        quota_result = await check_submission_allowed(
            user_id=user.id,
            source_platform=source_platform,
            duration_seconds=0,  # duration unknown at URL ingestion time
        )
        if not quota_result.allowed:
            raise HTTPException(
                status_code=quota_result.http_status,
                detail=quota_result.message,
                headers={"X-Quota-Error-Code": quota_result.error_code},
            )

        # Derive media_type from source_platform
        _platform_to_media_type = {
            "youtube": "video",
            "tiktok": "video",
            "instagram": "video",
            "audio": "audio",
            "web": "article",
        }
        detected_media_type = _platform_to_media_type.get(source_platform, "podcast")

        job = ProcessingJob(
            user_id=user.id,
            user_email=user.email,
            source_url=url,
            source_platform=source_platform,
            media_type=detected_media_type,
        )

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

        # Record quota usage after successful enqueue
        estimated_cost = estimate_submission_cost(source_platform, duration_seconds=0)
        await record_submission(
            user_id=user.id,
            source_platform=source_platform,
            duration_seconds=0,
            estimated_cost_eur=estimated_cost,
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


@router.post("/upload", response_model=UploadDocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Upload a document file for parsing and ingestion.

    Supported formats: PDF, DOCX, PPTX, XLSX, JPG, JPEG, PNG, TIFF, BMP, HEIF.
    The document will be parsed using LlamaParse (primary) with fallback to
    Unstructured API, then fed into the downstream LLM pipeline.

    Returns 202 Accepted with the media_item_id to poll for status.
    """
    file_name = file.filename or "document"
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

    token = bind_log_context(user_id=current_user.id, source_platform="document")
    try:
        # Validate file extension
        if not ext or ext not in DocumentFormat.supported_extensions():
            supported = ", ".join(sorted(DocumentFormat.supported_extensions()))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format: '.{ext}'. Supported formats: {supported}",
            )

        # Read file content (with size check)
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty",
            )
        if len(content) > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB",
            )

        user = await database_async.get_user_by_id(current_user.id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # Quota enforcement check before processing
        quota_result = await check_submission_allowed(
            user_id=user.id,
            source_platform="document",
            duration_seconds=0,
        )
        if not quota_result.allowed:
            raise HTTPException(
                status_code=quota_result.http_status,
                detail=quota_result.message,
                headers={"X-Quota-Error-Code": quota_result.error_code},
            )

        # Create processing job
        job = ProcessingJob(
            user_id=user.id,
            user_email=user.email,
            source_url="",
            source_platform="document",
            media_type="document",
            title=file_name,
        )
        job = await database_async.create_processing_job(job)

        # Allocate 1 minute credit for document parsing
        await minute_pool.allocate_hold_for_job(
            user_id=user.id,
            job_id=job.id,
            minutes_estimated=REQUIRED_MINUTES,
        )

        # Upload document to S3
        document_s3_key = f"{job.id}/{file_name}"
        from io import BytesIO

        await s3.upload_file_object(
            bucket=DOCUMENT_BUCKET,
            key=document_s3_key,
            file_obj=BytesIO(content),
            content_type=file.content_type or "application/octet-stream",
            metadata={"original-filename": file_name},
        )

        # Generate a media_key for idempotence (based on user + filename + size)
        media_key = f"doc:{user.id}:{file_name}:{len(content)}"

        # Enqueue document parsing message
        await sqs.send_message(
            queue_name=DOCUMENT_PARSING_QUEUE,
            message_body={
                "job_id": job.id,
                "user_id": user.id,
                "document_s3_key": document_s3_key,
                "file_name": file_name,
                "media_key": media_key,
                "media_title": file_name,
            },
        )

        # Record quota usage after successful enqueue
        estimated_cost = estimate_submission_cost("document", duration_seconds=0)
        await record_submission(
            user_id=user.id,
            source_platform="document",
            duration_seconds=0,
            estimated_cost_eur=estimated_cost,
        )

        log_event(
            logger,
            logging.INFO,
            "media.upload.created",
            "Document uploaded and queued for parsing",
            media_item_id=job.id,
            source_platform="document",
            file_name=file_name,
            file_size_bytes=len(content),
        )

        return UploadDocumentResponse(
            media_item_id=job.id,
            status=job.status.value,
            source_platform="document",
            file_name=file_name,
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "media.upload.failed",
            "Document upload failed",
            error_type=type(exc).__name__,
            error_code="UPLOAD_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload document",
        )
    finally:
        reset_log_context(token)


@router.post("/upload-audio", response_model=UploadAudioResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_audio(
    file: UploadFile = File(...),
    tag_ids: Optional[str] = Form(None),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Upload an audio file for transcription via Deepgram.

    Supported formats: MP3, M4A, AAC, OGG, WAV, FLAC, OPUS.
    The audio file is uploaded to S3, then a pre-signed URL is generated
    and sent to the Deepgram transcription worker.

    Returns 202 Accepted with the media_item_id to poll for status.
    """
    file_name = file.filename or "audio"
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

    token = bind_log_context(user_id=current_user.id, source_platform="audio")
    try:
        # Validate file extension
        if not ext or f".{ext}" not in _AUDIO_EXTENSIONS:
            supported = ", ".join(_AUDIO_EXTENSIONS)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported audio format: '.{ext}'. Supported formats: {supported}",
            )

        # Read file content (with size check)
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty",
            )
        if len(content) > MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size: {MAX_UPLOAD_SIZE_BYTES // (1024*1024)}MB",
            )

        user = await database_async.get_user_by_id(current_user.id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # Create processing job
        job = ProcessingJob(
            user_id=user.id,
            user_email=user.email,
            source_url="",
            source_platform="audio",
            media_type="audio",
            title=file_name,
        )

        # Parse and validate tag_ids if provided
        parsed_tag_ids: Optional[List[str]] = None
        if tag_ids:
            import json as _json

            try:
                parsed_tag_ids = _json.loads(tag_ids)
            except (ValueError, TypeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="tag_ids must be a valid JSON array of strings",
                )
            if not isinstance(parsed_tag_ids, list):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="tag_ids must be a JSON array",
                )

        if parsed_tag_ids:
            from media_summarizer.core.constants import MAX_TAGS_PER_MEDIA

            unique_tag_ids = list(dict.fromkeys(parsed_tag_ids))
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

        # Allocate minute pool hold
        await minute_pool.allocate_hold_for_job(
            user_id=user.id,
            job_id=job.id,
            minutes_estimated=REQUIRED_MINUTES,
        )

        # Upload audio file to S3
        audio_s3_key = f"{job.id}.{ext}"
        from io import BytesIO

        await s3.upload_file_object(
            bucket=AUDIO_BUCKET,
            key=audio_s3_key,
            file_obj=BytesIO(content),
            content_type=file.content_type or "application/octet-stream",
            metadata={"original-filename": file_name},
        )

        # Generate pre-signed S3 GET URL (10 min validity)
        presigned_url = await s3.generate_presigned_url(
            bucket=AUDIO_BUCKET,
            key=audio_s3_key,
            expiration=AUDIO_PRESIGNED_URL_EXPIRATION,
            http_method="GET",
        )

        # Enqueue transcription message with the pre-signed URL
        await sqs.send_message(
            queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
            message_body={
                "job_id": job.id,
                "user_id": user.id,
                "source_platform": "audio",
                "audio_url": presigned_url,
                "audio_s3_key": audio_s3_key,
                "original_name": file_name,
            },
        )

        log_event(
            logger,
            logging.INFO,
            "media.upload_audio.created",
            "Audio file uploaded and queued for transcription",
            media_item_id=job.id,
            source_platform="audio",
            file_name=file_name,
            file_size_bytes=len(content),
            audio_s3_key=audio_s3_key,
        )

        return UploadAudioResponse(
            media_item_id=job.id,
            status=job.status.value,
            source_platform="audio",
        )

    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "media.upload_audio.failed",
            "Audio upload failed",
            error_type=type(exc).__name__,
            error_code="AUDIO_UPLOAD_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload audio file",
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

        # Derive transcript_source from extraction or transcription metadata
        transcript_source: Optional[str] = None
        ext_meta = job.extraction_metadata
        if ext_meta and isinstance(ext_meta, dict):
            ts = ext_meta.get("transcript_source")
            if isinstance(ts, str) and ts.strip():
                # Normalize pending states to the final provider name
                transcript_source = (
                    ts.strip()
                    .removesuffix("_pending")
                    .removesuffix("_pending_cdn_fallback")
                )
        tx_meta = job.transcription_metadata
        if not transcript_source and tx_meta and isinstance(tx_meta, dict):
            provider = tx_meta.get("provider")
            if isinstance(provider, str) and provider.strip():
                transcript_source = provider.strip()

        return MediaItemResponse(
            media_item_id=job.id,
            status=job.status.value,
            source_platform=job.source_platform,
            error_message=job.error_message,
            progress=job.get_progress_percentage(),
            extraction_metadata=job.extraction_metadata,
            transcription_metadata=job.transcription_metadata,
            transcript_source=transcript_source,
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


# ---------- Raw Content models ----------

class RawContentResponse(BaseModel):
    status: str = "success"
    media_item_id: str
    content: str = Field(..., description="Formatted raw content (transcript, extracted text, OCR)")
    content_type: str = Field(..., description="MIME type of the content (text/plain)")
    media_type: Optional[str] = Field(None, description="Type of media (podcast, article, video, audio)")
    source_format: Optional[str] = Field(
        None,
        description="Detected source format (deepgram_json, plain_text, article_text, social_post, ocr)",
    )


# ---------- Raw Content endpoint ----------

@router.get("/{media_item_id}/raw-content", response_model=RawContentResponse)
async def get_media_raw_content(
    media_item_id: str,
    request: Request,
    current_user: AuthUser = Depends(get_current_user),
):
    """Retrieve the raw content (transcript, extracted text, or OCR result) for a media item.

    Returns the formatted source content regardless of media type:
    - Audio/Video/Podcast: formatted transcript (Deepgram or Whisper)
    - Articles: extracted text (trafilatura)
    - Social posts: raw text of the post
    - Images/PDFs: OCR result

    The response format is consistent: plain text with paragraphs.
    """
    token = bind_log_context(user_id=current_user.id, media_item_id=media_item_id)
    try:
        job = await database_async.get_processing_job_by_id(media_item_id)

        if job is None:
            log_event(
                logger,
                logging.WARNING,
                "media.raw_content.not_found",
                "Media item not found",
                media_item_id=media_item_id,
                error_code="MEDIA_NOT_FOUND",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Media item not found",
            )

        if job.user_id != current_user.id:
            log_event(
                logger,
                logging.WARNING,
                "media.raw_content.forbidden",
                "Access denied to media item raw content",
                media_item_id=media_item_id,
                error_code="ACCESS_DENIED",
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )

        raw = await get_raw_content(job)

        log_event(
            logger,
            logging.INFO,
            "media.raw_content.succeeded",
            "Raw content retrieved",
            media_item_id=media_item_id,
            source_format=raw.source_format,
            content_length=len(raw.content),
        )

        return RawContentResponse(
            status="success",
            media_item_id=media_item_id,
            content=raw.content,
            content_type=raw.content_type,
            media_type=raw.media_type,
            source_format=raw.source_format,
        )

    except RawContentNotAvailableError as exc:
        log_event(
            logger,
            logging.INFO,
            "media.raw_content.not_available",
            "Raw content not yet available",
            media_item_id=media_item_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except HTTPException:
        raise
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "media.raw_content.failed",
            "Failed to retrieve raw content",
            media_item_id=media_item_id,
            error_type=type(exc).__name__,
            error_code="RAW_CONTENT_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve raw content",
        )
    finally:
        reset_log_context(token)
