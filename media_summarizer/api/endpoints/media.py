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

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.api.models.media_contracts import (
    LEGACY_PROCESSING_JOB_STATUS_MAP,
)
from media_summarizer.api.models.media_contracts import (
    MediaArtifactContract as CanonicalMediaArtifactContract,
)
from media_summarizer.api.models.media_contracts import (
    MediaItemContract as CanonicalMediaItemContract,
)
from media_summarizer.api.models.media_contracts import (
    MediaItemStatus as CanonicalMediaItemStatus,
)
from media_summarizer.api.models.media_contracts import (
    MediaStatusResponse as CanonicalMediaStatusResponse,
)
from media_summarizer.api.models.media_contracts import (
    MediaType as CanonicalMediaType,
)
from media_summarizer.api.models.media_contracts import (
    ProcessingJobContract as CanonicalProcessingJobContract,
)
from media_summarizer.api.models.media_contracts import (
    ProcessingJobLifecycleStatus as CanonicalJobLifecycle,
)
from media_summarizer.api.models.media_contracts import (
    ProcessingProgress as CanonicalProcessingProgress,
)
from media_summarizer.api.models.media_contracts import (
    SourcePlatform as CanonicalSourcePlatform,
)
from media_summarizer.api.models.media_contracts import (
    TranscriptInfo as CanonicalTranscriptInfo,
)
from media_summarizer.api.models.media_contracts import (
    TranscriptStatus as CanonicalTranscriptStatus,
)
from media_summarizer.core.models import ProcessingJob
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.models.media_artifact import MediaArtifactRecord
from media_summarizer.core.ports.document_parser import DocumentFormat
from media_summarizer.core.services import folder_service, media_search_service, tag_service
from media_summarizer.core.services.media_search_service import SearchFilters
from media_summarizer.core.services.quota_enforcer import (
    check_submission_allowed,
    estimate_submission_cost,
    record_submission,
)
from media_summarizer.core.services.raw_content_service import (
    RawContentNotAvailableError,
    get_raw_content,
)
from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils.language_codes import normalize_language_code
from media_summarizer.utils.logging_config import bind_log_context, log_event, reset_log_context
from media_summarizer.utils.media_artifacts import safe_list_media_artifacts_by_media_item

router = APIRouter()
logger = logging.getLogger(__name__)

DEEPGRAM_TRANSCRIPTION_QUEUE = os.environ.get("DEEPGRAM_TRANSCRIPTION_QUEUE", "deepgram-transcription-queue")
DOCUMENT_PARSING_QUEUE = os.environ.get("DOCUMENT_PARSING_QUEUE", "document-parsing-queue")
DOCUMENT_BUCKET = os.environ.get("DOCUMENT_BUCKET", "media-summarizer-documents")
AUDIO_BUCKET = os.environ.get("AUDIO_BUCKET", "media-summarizer-audio")

# Pre-signed URL validity for audio uploads (10 minutes)
AUDIO_PRESIGNED_URL_EXPIRATION = int(os.environ.get("AUDIO_PRESIGNED_URL_EXPIRATION", "600"))

# Max upload size: 50MB
MAX_UPLOAD_SIZE_BYTES = int(os.environ.get("MAX_UPLOAD_SIZE_BYTES", str(50 * 1024 * 1024)))

# Shared content limits (aligned with mobile client constants)
MAX_SHARED_AUDIO_SIZE_BYTES = int(os.environ.get("MAX_SHARED_AUDIO_SIZE_BYTES", str(25 * 1024 * 1024)))
MAX_SHARED_TEXT_LENGTH = int(os.environ.get("MAX_SHARED_TEXT_LENGTH", "50000"))
SUPPORTED_SHARED_AUDIO_MIME_TYPES = frozenset([
    "audio/ogg",
    "audio/opus",
    "audio/mp4",
    "audio/mpeg",
    "audio/x-m4a",
    "audio/aac",
    "audio/wav",
    "audio/x-wav",
    "audio/flac",
    "audio/amr",
])

_AUDIO_EXTENSIONS = (".mp3", ".m4a", ".aac", ".ogg", ".wav", ".flac", ".opus")
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"}
_TIKTOK_HOSTS = {"tiktok.com", "www.tiktok.com", "vm.tiktok.com"}
_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com"}


def _detect_platform(url: str) -> tuple[str, str]:
    """Return (source_platform, resolver_key) for a given URL.

    Used only for early platform detection for quota checking.
    The actual platform resolution is done in the use case.
    """
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
    source_app: Optional[str] = Field(None, description="Source app that submitted the URL")
    locale: Optional[str] = Field(None, description="Client locale")
    transcript_language: Optional[str] = Field(
        None,
        description=(
            "Optional override of the preferred transcript language code, e.g. 'fr'. "
            "When omitted, the authenticated user's reading_language is used."
        ),
    )
    idempotency_key: Optional[str] = Field(None, description="Client idempotency key")
    folder_id: Optional[str] = Field(
        None, description="Optional folder ID to assign to the media item"
    )
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


class IngestSharedContentResponse(BaseModel):
    media_item_id: str
    status: str
    source_platform: str
    deduplicated: Optional[bool] = None
    duplicate_of_media_item_id: Optional[str] = None


class MediaItemResponse(BaseModel):
    media_item_id: str
    status: str
    source_platform: Optional[str] = None
    error_message: Optional[str] = None
    extraction_metadata: Optional[dict] = None
    transcription_metadata: Optional[dict] = None
    transcript_source: Optional[str] = Field(
        None,
        description=(
            "How the transcript was obtained "
            "(e.g. 'deepgram', 'apify_native', 'yt-dlp_native')"
        ),
    )
    provider: Optional[str] = None


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
    error_message: Optional[str] = None


class MediaSearchResponse(BaseModel):
    status: str = "success"
    items: List[MediaSearchItem]
    total: int = Field(..., description="Total number of items matching filters")
    next_cursor: Optional[str] = Field(None, description="Cursor for next page")
    has_more: bool = Field(..., description="Whether more items are available")


# ---------- Canonical contract mapping ----------

# Map ProcessingJob.media_type (DB-stored) to the canonical MediaType enum.
# ProcessingJob stores coarse values like "video"/"podcast"/"article"/"audio"/"document";
# the canonical contract distinguishes platform-specific subtypes.
_LEGACY_MEDIA_TYPE_MAP = {
    "podcast": CanonicalMediaType.PODCAST_EPISODE,
    "podcast_episode": CanonicalMediaType.PODCAST_EPISODE,
    "article": CanonicalMediaType.ARTICLE,
    "audio": CanonicalMediaType.AUDIO_FILE,
    "audio_file": CanonicalMediaType.AUDIO_FILE,
    "shared_text": CanonicalMediaType.SHARED_TEXT,
    "document": CanonicalMediaType.ARTICLE,
}


def _canonical_media_type(job: ProcessingJob) -> CanonicalMediaType:
    raw = (job.media_type or "").lower().strip()
    if raw in _LEGACY_MEDIA_TYPE_MAP:
        return _LEGACY_MEDIA_TYPE_MAP[raw]
    if raw == "video":
        platform = (job.source_platform or "").lower().strip()
        if platform in ("tiktok", "instagram", "x"):
            return CanonicalMediaType.SHORT_VIDEO
        if platform == "youtube":
            return CanonicalMediaType.YOUTUBE_VIDEO
        return CanonicalMediaType.YOUTUBE_VIDEO
    try:
        return CanonicalMediaType(raw)
    except ValueError:
        return CanonicalMediaType.UNKNOWN


def _canonical_source_platform(job: ProcessingJob) -> CanonicalSourcePlatform:
    raw = (job.source_platform or "").lower().strip()
    try:
        return CanonicalSourcePlatform(raw)
    except ValueError:
        return CanonicalSourcePlatform.UNKNOWN


def _canonical_job_status(job: ProcessingJob) -> CanonicalJobLifecycle:
    return LEGACY_PROCESSING_JOB_STATUS_MAP.get(
        job.status.value, CanonicalJobLifecycle.PENDING
    )


def _canonical_media_item_status(job: ProcessingJob) -> CanonicalMediaItemStatus:
    job_status = _canonical_job_status(job)
    if job_status == CanonicalJobLifecycle.PENDING:
        return CanonicalMediaItemStatus.INGESTED
    if job_status == CanonicalJobLifecycle.RESOLVING:
        return CanonicalMediaItemStatus.RESOLVING
    if job_status == CanonicalJobLifecycle.READY_FOR_ARTIFACTS:
        return CanonicalMediaItemStatus.READY_FOR_ARTIFACTS
    if job_status == CanonicalJobLifecycle.FAILED:
        return CanonicalMediaItemStatus.FAILED
    if job_status == CanonicalJobLifecycle.CANCELLED:
        return CanonicalMediaItemStatus.CANCELLED
    if job_status == CanonicalJobLifecycle.COMPLETED:
        return CanonicalMediaItemStatus.READY_FOR_ARTIFACTS
    return CanonicalMediaItemStatus.PROCESSING


def _canonical_progress(job_status: CanonicalJobLifecycle) -> CanonicalProcessingProgress:
    # Coarse percentages keyed off the lifecycle stage; the worker pipeline doesn't
    # publish a finer-grained value yet.
    stage_pct = {
        CanonicalJobLifecycle.PENDING: 0,
        CanonicalJobLifecycle.CLASSIFYING: 5,
        CanonicalJobLifecycle.RESOLVING: 15,
        CanonicalJobLifecycle.EXTRACTING: 35,
        CanonicalJobLifecycle.TRANSCRIBING: 65,
        CanonicalJobLifecycle.READY_FOR_ARTIFACTS: 90,
        CanonicalJobLifecycle.COMPLETED: 100,
        CanonicalJobLifecycle.FAILED: 0,
        CanonicalJobLifecycle.CANCELLED: 0,
    }
    return CanonicalProcessingProgress(
        percentage=stage_pct.get(job_status, 0),
        stage=job_status,
    )


def _canonical_transcript(job: ProcessingJob) -> CanonicalTranscriptInfo:
    job_status = _canonical_job_status(job)
    if job_status in (
        CanonicalJobLifecycle.READY_FOR_ARTIFACTS,
        CanonicalJobLifecycle.COMPLETED,
    ):
        status = CanonicalTranscriptStatus.READY
    elif job_status == CanonicalJobLifecycle.FAILED:
        status = CanonicalTranscriptStatus.FAILED
    elif job_status == CanonicalJobLifecycle.TRANSCRIBING:
        status = CanonicalTranscriptStatus.TRANSCRIBING
    elif job_status == CanonicalJobLifecycle.EXTRACTING:
        status = CanonicalTranscriptStatus.EXTRACTING
    else:
        status = CanonicalTranscriptStatus.PENDING

    tx_meta = job.transcription_metadata if isinstance(job.transcription_metadata, dict) else {}
    ext_meta = job.extraction_metadata if isinstance(job.extraction_metadata, dict) else {}

    source = tx_meta.get("provider") or ext_meta.get("transcript_source")
    if isinstance(source, str):
        source = source.strip().removesuffix("_pending").removesuffix("_pending_cdn_fallback") or None
    else:
        source = None

    duration = tx_meta.get("duration_seconds") or ext_meta.get("duration_seconds")
    try:
        duration = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None

    segments = tx_meta.get("segments_count")
    try:
        segments = int(segments) if segments is not None else None
    except (TypeError, ValueError):
        segments = None

    language = tx_meta.get("language") or ext_meta.get("language")
    if not isinstance(language, str):
        language = None

    return CanonicalTranscriptInfo(
        status=status,
        transcription_s3_key=job.transcription_s3_key,
        source=source,
        language=language,
        segments_count=segments,
        duration_seconds=duration,
    )


def _build_media_item_contract(job: ProcessingJob) -> CanonicalMediaItemContract:
    return CanonicalMediaItemContract(
        media_item_id=job.id,
        media_key=job.media_key or job.id,
        original_url=job.source_url or "",
        normalized_url=job.source_url or "",
        media_type=_canonical_media_type(job),
        source_platform=_canonical_source_platform(job),
        status=_canonical_media_item_status(job),
        transcript=_canonical_transcript(job),
        artifact_statuses={},
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
    )


def _build_processing_job_contract(job: ProcessingJob) -> CanonicalProcessingJobContract:
    job_status = _canonical_job_status(job)
    return CanonicalProcessingJobContract(
        job_id=job.id,
        status=job_status,
        progress=_canonical_progress(job_status),
        created_at=job.created_at.isoformat(),
        updated_at=job.updated_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error_code=None,
        error_message=job.error_message,
    )


# Internal MediaArtifactType values that are surfaced via the public contract.
# Anything outside this set is filtered out of the response (e.g. legacy types
# the contract enum hasn't been extended for yet).
_PUBLIC_ARTIFACT_TYPES = {
    "summary",
    "summary_short",
    "summary_detailed",
    "quiz",
    "notes",
    "flashcards",
}


def _build_artifact_contract(
    record: MediaArtifactRecord,
) -> Optional[CanonicalMediaArtifactContract]:
    raw_type = record.artifact_type.value
    if raw_type not in _PUBLIC_ARTIFACT_TYPES:
        return None
    return CanonicalMediaArtifactContract(
        artifact_id=record.artifact_id,
        media_item_id=record.media_item_id,
        artifact_type=raw_type,
        status=record.status.value,
        parameters=record.parameters or {},
        content=None,
        error_code=None,
        error_message=record.error_message,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
        completed_at=record.completed_at.isoformat() if record.completed_at else None,
    )


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
    from media_summarizer.core.constants import MAX_TAGS_PER_MEDIA
    from media_summarizer.core.media_ingestion.domain import (
        IngestUrlCommand,
        UserContext,
    )
    from media_summarizer.core.media_ingestion.domain import (
        IngestUrlRequest as DomainIngestUrlRequest,
    )
    from media_summarizer.core.media_ingestion.errors import (
        InvalidUrlError,
        MediaIngestionError,
    )
    from media_summarizer.core.media_ingestion.wiring import (
        build_default_ingest_url_use_case,
    )

    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url is required")

    token = bind_log_context(user_id=current_user.id)
    try:
        log_event(
            logger,
            logging.INFO,
            "media.ingest.started",
            "Media ingest URL received",
        )

        user = await database_async.get_user_by_id(current_user.id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # Validate folder ownership if provided
        resolved_folder_id: Optional[str] = None
        requested_folder_id = payload.folder_id.strip() if payload.folder_id else None
        if requested_folder_id:
            folder = await database_async.get_folder_by_id(requested_folder_id)
            if folder is None or folder.user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Folder not found: {requested_folder_id}",
                )
            resolved_folder_id = folder.id

        # Validate tags ownership and count if provided
        if payload.tag_ids:
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
        else:
            unique_tag_ids = None

        # Quota enforcement check before processing
        # Detect source platform for quota checking
        source_platform_for_quota, _ = _detect_platform(url)
        quota_result = await check_submission_allowed(
            user_id=user.id,
            source_platform=source_platform_for_quota,
            duration_seconds=0,  # duration unknown at URL ingestion time
        )
        if not quota_result.allowed:
            raise HTTPException(
                status_code=quota_result.http_status,
                detail=quota_result.message,
                headers={"X-Quota-Error-Code": quota_result.error_code},
            )

        # Transcript language (task-216): the user's reading_language preference
        # (task-190) is the default; an explicit payload value overrides it for
        # this single submission (e.g. keep an EN video's original transcript).
        transcript_language = normalize_language_code(
            payload.transcript_language
        ) or normalize_language_code(user.reading_language)

        # Build the domain command
        domain_request = DomainIngestUrlRequest(
            url=url,
            source_app=payload.source_app,
            locale=payload.locale,
            transcript_language=transcript_language,
            idempotency_key=payload.idempotency_key,
            folder_id=resolved_folder_id,
            tag_ids=unique_tag_ids,
        )
        command = IngestUrlCommand(
            user=UserContext(user_id=current_user.id, user_email=user.email),
            request=domain_request,
        )

        # Execute the use case
        use_case = build_default_ingest_url_use_case()
        outcome = await use_case.execute(command)

        # Record quota usage after successful submission
        estimated_cost = estimate_submission_cost(
            outcome.metadata.get("source_platform", source_platform_for_quota),
            duration_seconds=0
        )
        await record_submission(
            user_id=user.id,
            source_platform=outcome.metadata.get("source_platform", source_platform_for_quota),
            duration_seconds=0,
            estimated_cost_eur=estimated_cost,
        )

        log_event(
            logger,
            logging.INFO,
            "media.ingest.created",
            "Media item created and queued",
            media_item_id=outcome.media_item_id,
            source_platform=outcome.metadata.get("source_platform"),
            transcript_language=transcript_language,
            transcript_language_source=(
                "request_override" if payload.transcript_language else "reading_language"
            ),
        )

        return IngestUrlResponse(
            media_item_id=outcome.media_item_id,
            status=outcome.status.value,
            source_platform=outcome.metadata.get("source_platform", "unknown"),
        )

    except HTTPException:
        raise
    except InvalidUrlError as exc:
        log_event(
            logger,
            logging.WARNING,
            "media.ingest.invalid_url",
            "Invalid URL provided for ingestion",
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except MediaIngestionError as exc:
        log_event(
            logger,
            logging.ERROR,
            "media.ingest.failed",
            "Media ingestion failed in use case",
            error_type=type(exc).__name__,
            error_code="INGEST_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest URL",
        )
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "media.ingest.failed",
            "Media ingest failed unexpectedly",
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
                "deepgram_mode": "pull",
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


@router.post("/ingest-shared-content", response_model=IngestSharedContentResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_shared_content(
    share_type: str = Form(...),
    source_platform: str = Form(...),
    source_app: Optional[str] = Form(None),
    idempotency_key: Optional[str] = Form(None),
    locale: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    content_mime_type: Optional[str] = Form(None),
    original_name: Optional[str] = Form(None),
    folder_id: Optional[str] = Form(None),
    tag_ids: Optional[str] = Form(None),
    audio_file: Optional[UploadFile] = File(None),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Ingest shared content (text or audio) from mobile share intents (e.g. WhatsApp).

    Accepts multipart/form-data. The `share_type` field determines which path is taken:
    - "text": requires the `text` field with the shared message content.
    - "audio": requires `audio_file` (the binary), `content_mime_type`, and `original_name`.

    Returns 202 Accepted with the media_item_id to poll for status.
    """
    import hashlib
    from io import BytesIO

    from media_summarizer.core.media_ingestion.domain import (
        IngestSharedContentCommand,
        SharedContentType,
        SourcePlatform,
        UserContext,
    )
    from media_summarizer.core.media_ingestion.domain import (
        IngestSharedContentRequest as DomainIngestSharedContentRequest,
    )
    from media_summarizer.core.media_ingestion.errors import (
        MediaIngestionError,
        ResolutionError,
    )
    from media_summarizer.core.media_ingestion.wiring import (
        build_default_ingest_shared_content_use_case,
    )

    token = bind_log_context(user_id=current_user.id, source_platform="shared_content")
    try:
        # Validate share_type
        share_type_clean = (share_type or "").strip().lower()
        if share_type_clean not in ("text", "audio"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid share_type: '{share_type}'. Must be 'text' or 'audio'.",
            )

        # Validate source_platform
        source_platform_clean = (source_platform or "").strip().lower()
        try:
            domain_source_platform = SourcePlatform(source_platform_clean)
        except ValueError:
            valid_platforms = ', '.join(sp.value for sp in SourcePlatform)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source_platform: '{source_platform}'. Must be one of: {valid_platforms}.",
            )

        domain_share_type = SharedContentType(share_type_clean)

        # Verify user exists
        user = await database_async.get_user_by_id(current_user.id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        # Validate folder ownership if provided
        from media_summarizer.core.constants import MAX_TAGS_PER_MEDIA

        resolved_folder_id: Optional[str] = None
        requested_folder_id = folder_id.strip() if folder_id else None
        if requested_folder_id:
            folder = await database_async.get_folder_by_id(requested_folder_id)
            if folder is None or folder.user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Folder not found: {requested_folder_id}",
                )
            resolved_folder_id = folder.id

        # Validate tags ownership and count if provided
        unique_tag_ids: Optional[List[str]] = None
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
            unique_tag_ids = list(dict.fromkeys(parsed_tag_ids))
            if len(unique_tag_ids) > MAX_TAGS_PER_MEDIA:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot assign more than {MAX_TAGS_PER_MEDIA} tags",
                )
            # Validate tags belong to user
            user_tags = await database_async.get_tags_by_user_id(user.id)
            user_tag_ids_set = {t.id for t in user_tags}
            invalid_ids = [tid for tid in unique_tag_ids if tid not in user_tag_ids_set]
            if invalid_ids:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Tag(s) not found: {', '.join(invalid_ids)}",
                )

        # Branch based on share_type
        staged_audio_s3_key: Optional[str] = None
        content_hash: Optional[str] = None
        content_size_bytes: Optional[int] = None

        if domain_share_type == SharedContentType.TEXT:
            # Validate text field
            text_content = (text or "").strip()
            if not text_content:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Field 'text' is required and must not be empty for share_type=text.",
                )
            if len(text_content) > MAX_SHARED_TEXT_LENGTH:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Text is too long ({len(text_content)} characters). Maximum is {MAX_SHARED_TEXT_LENGTH}.",
                )

        elif domain_share_type == SharedContentType.AUDIO:
            # Validate audio-specific fields
            if audio_file is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Field 'audio_file' is required for share_type=audio.",
                )

            mime = (content_mime_type or audio_file.content_type or "").strip().lower()
            if not mime or mime not in SUPPORTED_SHARED_AUDIO_MIME_TYPES:
                supported_list = ", ".join(sorted(SUPPORTED_SHARED_AUDIO_MIME_TYPES))
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported audio MIME type: '{mime}'. Supported: {supported_list}.",
                )

            # Read file content
            audio_content = await audio_file.read()
            if len(audio_content) == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Audio file is empty.",
                )
            if len(audio_content) > MAX_SHARED_AUDIO_SIZE_BYTES:
                max_mb = MAX_SHARED_AUDIO_SIZE_BYTES // (1024 * 1024)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Audio file too large. Maximum size: {max_mb}MB.",
                )

            content_size_bytes = len(audio_content)

            # Compute content hash for deduplication
            content_hash = hashlib.sha256(audio_content).hexdigest()

            # Determine file extension from MIME
            _mime_to_ext = {
                "audio/ogg": "ogg",
                "audio/opus": "opus",
                "audio/mp4": "m4a",
                "audio/mpeg": "mp3",
                "audio/x-m4a": "m4a",
                "audio/aac": "aac",
                "audio/wav": "wav",
                "audio/x-wav": "wav",
                "audio/flac": "flac",
                "audio/amr": "amr",
            }
            ext = _mime_to_ext.get(mime, "audio")
            file_name_for_s3 = original_name or audio_file.filename or f"shared-audio.{ext}"

            # Stage audio to S3
            staged_audio_s3_key = f"shared-audio/{current_user.id}/{content_hash}.{ext}"
            await s3.upload_file_object(
                bucket=AUDIO_BUCKET,
                key=staged_audio_s3_key,
                file_obj=BytesIO(audio_content),
                content_type=mime,
                metadata={
                    "original-filename": file_name_for_s3,
                    "source-platform": source_platform_clean,
                    "share-type": "audio",
                },
            )

            log_event(
                logger,
                logging.INFO,
                "media.ingest_shared_content.audio_staged",
                "Shared audio file staged to S3",
                audio_s3_key=staged_audio_s3_key,
                content_hash=content_hash,
                file_size_bytes=content_size_bytes,
            )

        # Build the domain command
        domain_request = DomainIngestSharedContentRequest(
            share_type=domain_share_type,
            source_platform=domain_source_platform,
            source_app=source_app,
            locale=locale,
            idempotency_key=idempotency_key,
            text=text if domain_share_type == SharedContentType.TEXT else None,
            content_hash=content_hash,
            content_mime_type=content_mime_type,
            original_name=original_name,
            content_size_bytes=content_size_bytes,
            staged_audio_s3_key=staged_audio_s3_key,
            folder_id=resolved_folder_id,
            tag_ids=unique_tag_ids,
        )
        command = IngestSharedContentCommand(
            user=UserContext(user_id=current_user.id, user_email=user.email),
            request=domain_request,
        )

        # Execute the use case
        use_case = build_default_ingest_shared_content_use_case()
        outcome = await use_case.execute(command)

        log_event(
            logger,
            logging.INFO,
            "media.ingest_shared_content.created",
            "Shared content ingested successfully",
            media_item_id=outcome.media_item_id,
            share_type=share_type_clean,
            source_platform=source_platform_clean,
            deduplicated=outcome.deduplicated,
        )

        return IngestSharedContentResponse(
            media_item_id=outcome.media_item_id,
            status=outcome.status.value,
            source_platform=source_platform_clean,
            deduplicated=outcome.deduplicated if outcome.deduplicated else None,
            duplicate_of_media_item_id=outcome.duplicate_of_media_item_id,
        )

    except HTTPException:
        raise
    except ResolutionError as exc:
        log_event(
            logger,
            logging.WARNING,
            "media.ingest_shared_content.validation_failed",
            "Shared content validation failed in use case",
            error_message=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except MediaIngestionError as exc:
        log_event(
            logger,
            logging.ERROR,
            "media.ingest_shared_content.failed",
            "Shared content ingestion failed",
            error_type=type(exc).__name__,
            error_code="INGEST_SHARED_CONTENT_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest shared content",
        )
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "media.ingest_shared_content.failed",
            "Shared content ingestion failed unexpectedly",
            error_type=type(exc).__name__,
            error_code="INGEST_SHARED_CONTENT_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest shared content",
        )
    finally:
        reset_log_context(token)


@router.get("/{media_item_id}", response_model=CanonicalMediaStatusResponse)
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

        artifact_records = await safe_list_media_artifacts_by_media_item(media_item_id)
        artifacts: List[CanonicalMediaArtifactContract] = []
        for record in artifact_records:
            mapped = _build_artifact_contract(record)
            if mapped is not None:
                artifacts.append(mapped)

        return CanonicalMediaStatusResponse(
            media_item=_build_media_item_contract(job),
            processing_job=_build_processing_job_contract(job),
            artifacts=artifacts,
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
    translation: Optional[dict] = Field(
        None,
        description=(
            "Translation provenance when the content was translated to the "
            "user's reading_language (task-192/task-200/task-203): is_translated, "
            "translated_from, target_language, detected_language, "
            "detection_method, translation_pending, translation_status. "
            "translation_status is one of: queued, in_progress, done, failed, null. "
            "When translation_pending is true (status queued/in_progress), "
            "the client should poll again. On status=failed, do not poll."
        ),
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

        raw = await get_raw_content(job, reading_language=current_user.reading_language)

        log_event(
            logger,
            logging.INFO,
            "media.raw_content.succeeded",
            "Raw content retrieved",
            media_item_id=media_item_id,
            source_format=raw.source_format,
            content_length=len(raw.content),
            is_translated=(raw.translation or {}).get("is_translated", False),
        )

        return RawContentResponse(
            status="success",
            media_item_id=media_item_id,
            content=raw.content,
            content_type=raw.content_type,
            media_type=raw.media_type,
            source_format=raw.source_format,
            translation=raw.translation,
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
