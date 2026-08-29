"""
Media API endpoints.

Provides operations on media items (processing jobs from the user's perspective).
Supports URL ingestion, file upload (document parsing), status retrieval, and folder assignment via PATCH.
"""

from __future__ import annotations

import json
import logging
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.api.dependencies.media_access import get_media_for_user
from media_summarizer.api.models.media_contracts import (
    LEGACY_PROCESSING_JOB_STATUS_MAP,
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
from media_summarizer.core.constants import MAX_TAGS_PER_MEDIA
from media_summarizer.core.media_ingestion.title_derivation import (
    derive_media_title,
    label_for_file_name,
)
from media_summarizer.core.models import ProcessingJob
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.models.user_media import (
    ReviewBlurb,
    UserMediaRecord,
    UserMediaStatus,
)
from media_summarizer.core.ports.document_parser import DocumentFormat
from media_summarizer.core.services import (
    audio_duration_probe,
    cover_capture,
    folder_service,
    media_deletion_service,
    media_search_service,
    quota_enforcer,
    tag_service,
)
from media_summarizer.core.services.durable_media_service import (
    resolve_job_for_record,
    save_media_for_user,
    user_holds_media,
)
from media_summarizer.core.services.media_search_service import (
    DEFAULT_SORT_DIRECTION,
    SearchFilters,
    SortDirection,
)
from media_summarizer.core.services.quota_enforcer import check_submission_allowed
from media_summarizer.core.services.raw_content_service import (
    RawContentNotAvailableError,
    get_raw_content,
)
from media_summarizer.core.services.short_url_resolver import resolve_tiktok_short_link
from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils.env import required_env
from media_summarizer.utils.language_codes import normalize_language_code
from media_summarizer.utils.logging_config import bind_log_context, log_event, reset_log_context

router = APIRouter()
logger = logging.getLogger(__name__)

DEEPGRAM_TRANSCRIPTION_QUEUE = required_env("DEEPGRAM_TRANSCRIPTION_QUEUE")
DOCUMENT_PARSING_QUEUE = required_env("DOCUMENT_PARSING_QUEUE")
DOCUMENT_BUCKET = required_env("DOCUMENT_BUCKET")
AUDIO_BUCKET = required_env("AUDIO_BUCKET")

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


def _parse_form_tag_ids(raw: Optional[str]) -> Optional[List[str]]:
    """Decode the multipart `tag_ids` field, which travels as a JSON array.

    Multipart form fields are strings, so every upload/share endpoint carries the
    tag list as `["tag_a","tag_b"]`. This is the only place that knows it, so the
    validation below works on real lists whatever the transport was.
    """
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tag_ids must be a valid JSON array of strings",
        )
    if not isinstance(parsed, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tag_ids must be a JSON array",
        )
    return [str(tag_id) for tag_id in parsed]


async def _resolve_media_organization(
    *,
    user_id: str,
    folder_id: Optional[str],
    tag_ids: Optional[List[str]],
) -> tuple[Optional[str], Optional[List[str]]]:
    """Validate the folder/tags a submission asks for and return them resolved.

    Single dialect of "where does this save go", shared by every ingestion
    entrypoint (URL, shared content, document upload, audio upload) so a mobile
    gesture cannot end up with a weaker check than another. Enforces:

    - the folder exists and belongs to the caller
    - the tags exist and belong to the caller
    - at most ``MAX_TAGS_PER_MEDIA`` distinct tags

    Returns ``(resolved_folder_id, unique_tag_ids)``, both ``None`` when nothing
    was asked for — ``save_media_for_user`` then falls back to the user's default
    folder. Raises ``HTTPException`` 400 on any violation.
    """
    resolved_folder_id: Optional[str] = None
    requested_folder_id = folder_id.strip() if folder_id else None
    if requested_folder_id:
        folder = await database_async.get_folder_by_id(requested_folder_id)
        if folder is None or folder.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Folder not found: {requested_folder_id}",
            )
        resolved_folder_id = folder.id

    if not tag_ids:
        return resolved_folder_id, None

    unique_tag_ids = list(dict.fromkeys(tag_ids))
    if len(unique_tag_ids) > MAX_TAGS_PER_MEDIA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot assign more than {MAX_TAGS_PER_MEDIA} tags",
        )
    user_tags = await database_async.get_tags_by_user_id(user_id)
    user_tag_ids = {t.id for t in user_tags}
    invalid_ids = [tid for tid in unique_tag_ids if tid not in user_tag_ids]
    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tag(s) not found: {', '.join(invalid_ids)}",
        )
    return resolved_folder_id, unique_tag_ids


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


# ---------- Deletion models ----------

class DeleteMediaResponse(BaseModel):
    status: str = "success"
    media_item_id: str = Field(
        ...,
        description=(
            "The durable library id that was deleted. May differ from the id in the "
            "path while reads still resolve through processing_jobs (task-220)."
        ),
    )
    deleted_at: Optional[str] = Field(
        None, description="When the item left the user's library (ISO-8601 UTC)"
    )
    purge_at: int = Field(
        ...,
        description=(
            "Epoch seconds after which the item and everything it owns are "
            "irreversibly destroyed. Until then the deletion is recoverable by support."
        ),
    )
    grace_days: int = Field(
        ..., description="Days between the deletion and the irreversible purge"
    )


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
    """One row of the library list, projected from the durable ``user_media`` record.

    ``status`` is the *library* processing status (pending/processing/ready/failed)
    and is nullable by contract: the entry exists in the library whether or not
    anything is known about its processing (task-220, invariant I3). The former
    ``completed_at`` / ``error_message`` fields are gone -- they were processing-job
    attributes, and a list read no longer reads jobs.
    """

    media_item_id: str
    title: Optional[str] = None
    # The triage card mirrored from the ``review_blurb`` artifact (task-323): the
    # hook, its bullets and who it is for. Null until that artifact completes, and
    # null forever on an item whose generation failed -- a row without a blurb is a
    # normal row.
    review_blurb: Optional[ReviewBlurb] = None
    # Publisher of the media -- channel, show, site, account (task-304). Nullable
    # by contract: shared text, documents and audio files have none, and the tile
    # simply omits its second line.
    creator_name: Optional[str] = None
    source_platform: Optional[str] = None
    media_type: Optional[str] = None
    status: Optional[str] = None
    folder_id: Optional[str] = None
    tag_ids: List[str] = Field(default_factory=list)
    source_url: Optional[str] = None
    media_image: Optional[str] = None
    created_at: str
    updated_at: str


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


def _canonical_media_type(
    media_type: Optional[str], source_platform: Optional[str]
) -> CanonicalMediaType:
    raw = (media_type or "").lower().strip()
    if raw in _LEGACY_MEDIA_TYPE_MAP:
        return _LEGACY_MEDIA_TYPE_MAP[raw]
    if raw == "video":
        platform = (source_platform or "").lower().strip()
        if platform in ("tiktok", "instagram", "x"):
            return CanonicalMediaType.SHORT_VIDEO
        if platform == "youtube":
            return CanonicalMediaType.YOUTUBE_VIDEO
        return CanonicalMediaType.YOUTUBE_VIDEO
    try:
        return CanonicalMediaType(raw)
    except ValueError:
        return CanonicalMediaType.UNKNOWN


def _canonical_source_platform(source_platform: Optional[str]) -> CanonicalSourcePlatform:
    raw = (source_platform or "").lower().strip()
    try:
        return CanonicalSourcePlatform(raw)
    except ValueError:
        return CanonicalSourcePlatform.UNKNOWN


# Library status -> job lifecycle, used when the operational job is gone.
#
# ``READY -> COMPLETED`` is the load-bearing entry: the mobile detail screen polls
# until it sees ``completed``, so an item whose job expired must still report a
# terminal status or the client spins forever on data that will never change.
_LIBRARY_STATUS_TO_JOB_LIFECYCLE = {
    UserMediaStatus.PENDING: CanonicalJobLifecycle.PENDING,
    UserMediaStatus.PROCESSING: CanonicalJobLifecycle.EXTRACTING,
    UserMediaStatus.READY: CanonicalJobLifecycle.COMPLETED,
    UserMediaStatus.FAILED: CanonicalJobLifecycle.FAILED,
}


def _canonical_job_status(
    record: UserMediaRecord, job: Optional[ProcessingJob]
) -> CanonicalJobLifecycle:
    """Lifecycle status of the item, job-first and library-second.

    A live job is the finest-grained answer, so it wins when it exists. When it
    does not, the library's own coarse status answers instead -- and an unknown
    library status resolves to ``COMPLETED`` rather than ``PENDING`` on purpose:
    with no job in existence nothing is in flight, and claiming otherwise would
    tell the client to keep waiting for a pipeline that is not running.
    """
    if job is not None:
        return LEGACY_PROCESSING_JOB_STATUS_MAP.get(
            job.status.value, CanonicalJobLifecycle.PENDING
        )
    if record.processing_status is None:
        return CanonicalJobLifecycle.COMPLETED
    return _LIBRARY_STATUS_TO_JOB_LIFECYCLE.get(
        record.processing_status, CanonicalJobLifecycle.COMPLETED
    )


def _canonical_media_item_status(job_status: CanonicalJobLifecycle) -> CanonicalMediaItemStatus:
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


def _canonical_transcript(
    job_status: CanonicalJobLifecycle,
    record: UserMediaRecord,
    job: Optional[ProcessingJob],
) -> CanonicalTranscriptInfo:
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

    # Everything below is pipeline detail that only ever lived on the job. With no
    # job left, the transcript block degrades to its status alone -- which is why
    # the status is derived from the library row and not from this metadata.
    tx_meta = (
        job.transcription_metadata
        if job is not None and isinstance(job.transcription_metadata, dict)
        else {}
    )
    ext_meta = (
        job.extraction_metadata
        if job is not None and isinstance(job.extraction_metadata, dict)
        else {}
    )

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

    language = (
        tx_meta.get("language") or ext_meta.get("language") or record.language
    )
    if not isinstance(language, str):
        language = None

    if duration is None and record.duration_seconds is not None:
        duration = float(record.duration_seconds)

    return CanonicalTranscriptInfo(
        status=status,
        transcription_s3_key=job.transcription_s3_key if job is not None else None,
        source=source,
        language=language,
        segments_count=segments,
        duration_seconds=duration,
    )


def _build_media_item_contract(
    record: UserMediaRecord,
    job: Optional[ProcessingJob],
    job_status: CanonicalJobLifecycle,
    cover_url: Optional[str] = None,
) -> CanonicalMediaItemContract:
    """Project the durable library row onto the canonical media item contract.

    The record is the authority for identity, metadata and organization; the job
    is only an enrichment, and every field it used to provide has a durable
    counterpart. ``media_item_id`` is the opaque id of this save. ``title`` is
    the row's own display title -- the same field the list endpoint projects, so
    the detail header and the inbox vignette cannot disagree.
    """
    return CanonicalMediaItemContract(
        media_item_id=record.media_item_id,
        media_key=record.media_key or record.media_item_id,
        title=record.title,
        media_image=cover_url,
        creator_name=record.creator_name,
        original_url=record.source_url or "",
        normalized_url=record.source_url or "",
        media_type=_canonical_media_type(record.media_type, record.source_platform),
        source_platform=_canonical_source_platform(record.source_platform),
        status=_canonical_media_item_status(job_status),
        transcript=_canonical_transcript(job_status, record, job),
        created_at=record.saved_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )


def _build_processing_job_contract(
    record: UserMediaRecord,
    job: Optional[ProcessingJob],
    job_status: CanonicalJobLifecycle,
) -> CanonicalProcessingJobContract:
    """Processing state as an *enrichment* of the library row.

    Deliberately still a required, non-null block of the response: the mobile
    client dereferences ``processing_job.status`` unconditionally, and the point of
    task-220 is that an expired job stops being visible to users -- not that it
    starts returning null and crashing the app. When no job survives, the block is
    synthesized from the durable row: the timestamps become the library's own, the
    dangling ``last_job_id`` is reported as the job id (correlation only, it may no
    longer resolve), and pipeline-only fields are simply absent.
    """
    if job is not None:
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

    is_terminal = job_status in (
        CanonicalJobLifecycle.COMPLETED,
        CanonicalJobLifecycle.FAILED,
        CanonicalJobLifecycle.CANCELLED,
    )
    return CanonicalProcessingJobContract(
        job_id=record.last_job_id or record.media_item_id,
        status=job_status,
        progress=_canonical_progress(job_status),
        created_at=record.saved_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
        started_at=None,
        completed_at=record.updated_at.isoformat() if is_terminal else None,
        error_code=None,
        error_message=None,
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
    sort: SortDirection = DEFAULT_SORT_DIRECTION,
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
        sort: Chronological direction -- "desc" (default, newest first) or "asc"
            (oldest first, for a triage pass through the backlog). Typed as a
            Literal, so any other value is a 422 rather than a silent fallback to
            the default.
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
            sort_direction=sort,
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
        UnsupportedUrlError,
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

        # Where the save goes: folder and tags must belong to the caller.
        resolved_folder_id, unique_tag_ids = await _resolve_media_organization(
            user_id=user.id,
            folder_id=payload.folder_id,
            tag_ids=payload.tag_ids,
        )

        # A share link carries an opaque redirect code, not a media id, so
        # expand it before anything reads it: the classifier cannot tell what it
        # points at, and `media_key` -- derived from the canonical URL right
        # after this -- would differ for two shares of the same media, which is
        # what deduplication and the "already held" quota exemption rest on.
        # Best effort: an unresolvable link is submitted as-is.
        url = await resolve_tiktok_short_link(url)

        # Consumption check before processing. Submitting a URL costs nothing by
        # itself: what a link costs is decided by the provider call it ends up
        # making, and only the worker that resolves it knows whether there is
        # anything to transcribe and how long it is. So this check only answers
        # "is this user entitled at all" -- the debit happens downstream.
        quota_result = await check_submission_allowed(user.id)
        if not quota_result.allowed:
            raise HTTPException(
                status_code=quota_result.http_status,
                detail=quota_result.error_body(),
                headers={"X-Quota-Error-Code": quota_result.error_code or ""},
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

        # No minutes are charged here whatever the platform: this submission has
        # not made a provider call yet. All that is recorded is the item itself,
        # for the invisible daily burst guard.
        await quota_enforcer.record_submitted_item(
            user.id,
            idempotency_token=quota_enforcer.item_token(outcome.media_item_id),
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
    except UnsupportedUrlError as exc:
        # The URL is valid, we just do not ingest that kind of media. That is a
        # client-side fact with a message worth reading ("TikTok photo posts are
        # not supported yet"), so it must not fall through to the generic 500
        # below, which replaced it with "Failed to ingest URL".
        log_event(
            logger,
            logging.WARNING,
            "media.ingest.unsupported_url",
            "Unsupported URL provided for ingestion",
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
    folder_id: Optional[str] = Form(None),
    tag_ids: Optional[str] = Form(None),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Upload a document file for parsing and ingestion.

    Supported formats: PDF, DOCX, PPTX, XLSX, JPG, JPEG, PNG, TIFF, BMP, HEIF.
    The document will be parsed using LlamaParse (primary) with fallback to
    Unstructured API, then fed into the downstream LLM pipeline.

    `folder_id` and `tag_ids` (JSON array of strings) are optional and place the
    resulting library row exactly like every other ingestion entrypoint does.

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

        # Where the save goes (task-264). Validated before the quota check so an
        # unusable folder or tag costs nothing to the user's allowance.
        resolved_folder_id, resolved_tag_ids = await _resolve_media_organization(
            user_id=user.id,
            folder_id=folder_id,
            tag_ids=_parse_form_tag_ids(tag_ids),
        )

        # Consumption check before processing. A document costs a minute per five
        # pages and the page count only exists after the parse, so the cheapest
        # honest figure here is the minimum any document costs: one minute. The
        # parsing worker charges the real page count.
        quota_result = await check_submission_allowed(user.id, minutes_needed=1)
        if not quota_result.allowed:
            raise HTTPException(
                status_code=quota_result.http_status,
                detail=quota_result.error_body(),
                headers={"X-Quota-Error-Code": quota_result.error_code or ""},
            )

        # Media key for idempotence (user + filename + size). Computed before the
        # job so it can seed the durable library id.
        media_key = f"doc:{user.id}:{file_name}:{len(content)}"

        # Title stored right away (task-266): the cleaned filename when it says
        # something -- "Grant Deed_Security.pdf" reads "Grant Deed Security" --
        # otherwise the media type plus the upload date, which is the owner's
        # rule for a camera capture or a library pick whose name is `IMG_4821`.
        # The parsing worker upgrades it later if the document carries a title.
        media_title = derive_media_title(
            [],
            label=label_for_file_name(file_name),
            file_name_candidates=[file_name],
        )
        # No cover here even for a photo: the bytes are not in S3 yet. The
        # parsing worker builds the thumbnail once the object exists, from the
        # object itself, and mirrors it back (task-302 §4, rows 9-10). A PDF or
        # a DOCX never gets one -- `ParseResult` carries no image and there is no
        # page rasteriser in the runtime. No creator either: an uploaded file has
        # no publisher we can read.

        # Durable library entry first (task-240, task-218 §4.3): the job, the S3
        # object and the queue message are operational and may be retried; what
        # the user saved must not depend on any of them surviving. Since task-220
        # the library is read from this row, so a failure here fails the upload:
        # returning 202 for a save the user will never see is worse than an error.
        durable_media_item_id = await save_media_for_user(
            user_id=user.id,
            media_key=media_key,
            title=media_title,
            source_platform="document",
            media_type="document",
            folder_id=resolved_folder_id,
            tag_ids=resolved_tag_ids,
        )

        # Create processing job
        job = ProcessingJob(
            user_id=user.id,
            user_email=user.email,
            source_url="",
            source_platform="document",
            media_type="document",
            title=media_title,
            # Pointer to the durable library row this job is working for. The job
            # deliberately stays free of `media_key`: the completion events and the
            # watcher fan-out key off it, and this upload path has no entry in the
            # global idempotence ledger to point at.
            media_item_id=durable_media_item_id,
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

        # Enqueue document parsing message
        await sqs.send_message(
            queue_name=DOCUMENT_PARSING_QUEUE,
            message_body={
                "job_id": job.id,
                "user_id": user.id,
                "document_s3_key": document_s3_key,
                "file_name": file_name,
                "media_key": media_key,
            },
        )

        # The minutes this document costs are charged by the parsing worker, which
        # is the only place the page count exists. Here we only count the item for
        # the invisible daily burst guard.
        await quota_enforcer.record_submitted_item(
            user.id,
            idempotency_token=quota_enforcer.item_token(job.id),
        )

        log_event(
            logger,
            logging.INFO,
            "media.upload.created",
            "Document uploaded and queued for parsing",
            media_item_id=durable_media_item_id,
            job_id=job.id,
            source_platform="document",
            file_name=file_name,
            file_size_bytes=len(content),
        )

        return UploadDocumentResponse(
            media_item_id=durable_media_item_id,
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
    folder_id: Optional[str] = Form(None),
    tag_ids: Optional[str] = Form(None),
    current_user: AuthUser = Depends(get_current_user),
):
    """
    Upload an audio file for transcription via Deepgram.

    Supported formats: MP3, M4A, AAC, OGG, WAV, FLAC, OPUS.
    The audio file is uploaded to S3, then a pre-signed URL is generated
    and sent to the Deepgram transcription worker.

    `folder_id` and `tag_ids` (JSON array of strings) are optional and place the
    resulting library row exactly like every other ingestion entrypoint does.

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

        # Where the save goes (task-264). Validated before the quota check so an
        # unusable folder or tag costs nothing to the user's allowance.
        resolved_folder_id, resolved_tag_ids = await _resolve_media_organization(
            user_id=user.id,
            folder_id=folder_id,
            tag_ids=_parse_form_tag_ids(tag_ids),
        )

        # Consumption check. The whole file is in memory, so the real duration is
        # read from the container here and the check is exact — this is the one
        # path that knows the length up front, which is also what makes the
        # "too long for one import" refusal possible before anything is stored. A
        # container we cannot parse yields 0, which means "accept, debit one
        # provisional minute, settle after transcription".
        upload_duration_seconds = (
            audio_duration_probe.probe_duration_seconds_from_bytes(content) or 0
        )
        upload_minutes = quota_enforcer.minutes_for_seconds(upload_duration_seconds)
        quota_result = await check_submission_allowed(
            user.id,
            minutes_needed=upload_minutes or 1,
        )
        if not quota_result.allowed:
            raise HTTPException(
                status_code=quota_result.http_status,
                detail=quota_result.error_body(),
                headers={"X-Quota-Error-Code": quota_result.error_code or ""},
            )

        # Same content-key convention as the document upload. The library id is
        # independent and random, so re-uploading creates another save even when
        # the content key is identical.
        media_key = f"audio:{user.id}:{file_name}:{len(content)}"

        # Cleaned filename when it carries a name of its own, otherwise
        # "Audio note — <date>" (task-266). A voice memo exported as
        # `AUD-20260817-WA0002.opus` has no title to read, and the raw filename
        # was never one.
        media_title = derive_media_title(
            [],
            media_type="audio",
            source_platform="audio",
            file_name_candidates=[file_name],
        )
        # No cover and no creator for an audio upload, by construction: the file
        # goes straight to Deepgram, and reading an ID3 `APIC`/`artist` tag would
        # need `mutagen` in the runtime for a payoff limited to ripped podcast
        # episodes, which already get real artwork through the podcast path
        # (task-302 §4, row 11). The tile keeps its media-type icon.

        # Create processing job
        job = ProcessingJob(
            user_id=user.id,
            user_email=user.email,
            source_url="",
            source_platform="audio",
            media_type="audio",
            title=media_title,
        )

        # Durable library entry first (task-240, task-218 §4.3). The folder and
        # tags are organization, so they land on the library row -- never on the
        # job -- and the row is written before the job so nothing user-owned
        # depends on the pipeline.
        durable_media_item_id = await save_media_for_user(
            user_id=user.id,
            media_key=media_key,
            title=media_title,
            source_platform="audio",
            media_type="audio",
            folder_id=resolved_folder_id,
            tag_ids=resolved_tag_ids,
        )
        job.media_item_id = durable_media_item_id

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

        # Re-uploading a file already in the library is the same save twice: the
        # content key is per user and per file, so an identical upload costs the
        # user nothing again (task-281). The row created just above is excluded,
        # otherwise every upload would find itself and never be debited.
        already_held = await user_holds_media(
            user_id=user.id,
            media_key=media_key,
            exclude_media_item_id=durable_media_item_id,
        )

        # Debit the minutes now that the job exists, exactly once for this job id.
        # The transcription worker will settle the difference with the duration
        # Deepgram bills, so an unparsable container still ends up counted
        # correctly and a parsable one is not counted twice.
        debited_minutes = 0
        if already_held:
            log_event(
                logger,
                logging.INFO,
                "quota.audio_gate_already_held",
                "User already holds this audio file; the upload is free",
                user_id=user.id,
                media_item_id=durable_media_item_id,
                job_id=job.id,
            )
        else:
            debited_minutes = await quota_enforcer.record_transcription_minutes(
                user.id,
                minutes=upload_minutes or 1,
                idempotency_token=quota_enforcer.gate_token(job.id),
            )

        await quota_enforcer.record_submitted_item(
            user.id,
            idempotency_token=quota_enforcer.item_token(job.id),
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
                "audio_duration_seconds": upload_duration_seconds,
                "quota_debited_minutes": debited_minutes,
                "quota_debit_skipped": already_held,
                "deepgram_mode": "pull",
            },
        )

        log_event(
            logger,
            logging.INFO,
            "media.upload_audio.created",
            "Audio file uploaded and queued for transcription",
            media_item_id=durable_media_item_id,
            job_id=job.id,
            source_platform="audio",
            file_name=file_name,
            file_size_bytes=len(content),
            audio_s3_key=audio_s3_key,
        )

        return UploadAudioResponse(
            media_item_id=durable_media_item_id,
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

        # Where the save goes: folder and tags must belong to the caller.
        resolved_folder_id, unique_tag_ids = await _resolve_media_organization(
            user_id=user.id,
            folder_id=folder_id,
            tag_ids=_parse_form_tag_ids(tag_ids),
        )

        # Branch based on share_type
        staged_audio_s3_key: Optional[str] = None
        content_hash: Optional[str] = None
        content_size_bytes: Optional[int] = None
        shared_audio_duration_seconds: int = 0

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

            # Consumption check. The bytes are in memory, so the container gives
            # the real duration for free and the refusal below is exact. The debit
            # itself happens once in the ingestion orchestrator, where the job id
            # exists; this check is only here to answer the share sheet with a
            # real HTTP error instead of a job that fails a second later.
            shared_audio_duration_seconds = (
                audio_duration_probe.probe_duration_seconds_from_bytes(audio_content)
                or 0
            )
            quota_result = await check_submission_allowed(
                current_user.id,
                minutes_needed=(
                    quota_enforcer.minutes_for_seconds(shared_audio_duration_seconds)
                    or 1
                ),
            )
            if not quota_result.allowed:
                raise HTTPException(
                    status_code=quota_result.http_status,
                    detail=quota_result.error_body(),
                    headers={"X-Quota-Error-Code": quota_result.error_code or ""},
                )

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
            audio_duration_seconds=shared_audio_duration_seconds,
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
        # Ownership is the key: the durable row is looked up under
        # (user_id, media_item_id), so another user's item is indistinguishable
        # from a non-existent one and no separate 403 branch is needed.
        record = await get_media_for_user(media_item_id, current_user.id)

        # Processing state is an optional enrichment. A missing job is a normal,
        # expected outcome once the operational row has expired.
        job = await resolve_job_for_record(record)
        job_status = _canonical_job_status(record, job)

        log_event(
            logger,
            logging.INFO,
            "media.get.succeeded",
            "Media item retrieved",
            media_item_id=media_item_id,
            status=job_status.value,
            has_job=job is not None,
        )

        # No artifact list here any more (task-270): a scope holds a timestamped
        # history, several entries per type, and the AI tab reads it from
        # GET /api/artifacts?scope=media&scope_id=... in one call. Embedding a
        # "current artifact per type" projection here is the assumption the
        # append-only model removes.
        # A re-hosted cover is stored as an `s3://` locator; the client must
        # never see one, so it is signed here exactly as the list endpoint does
        # (task-302 §5.5). A hotlinked URL passes straight through.
        cover_url = await cover_capture.resolve_cover_url(record.thumbnail_url)

        return CanonicalMediaStatusResponse(
            media_item=_build_media_item_contract(
                record, job, job_status, cover_url=cover_url
            ),
            processing_job=_build_processing_job_contract(record, job, job_status),
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


@router.delete("/{media_item_id}", response_model=DeleteMediaResponse)
async def delete_media_item(
    media_item_id: str,
    current_user: AuthUser = Depends(get_current_user),
) -> DeleteMediaResponse:
    """Delete one media item from the user's library.

    The item disappears from every read surface immediately and is destroyed for
    good after the grace window (see ``core/services/media_deletion_service.py``
    and ``docs/DATA_RETENTION.md``). This is the only path in the system allowed
    to schedule a library row for purge.

    Idempotent: deleting an already-deleted item returns 200 with the original
    ``purge_at`` rather than 404, so a client retrying on a flaky network cannot
    turn a successful deletion into an error — nor push the purge date out.
    """
    token = bind_log_context(user_id=current_user.id, media_item_id=media_item_id)
    try:
        result = await media_deletion_service.delete_media_for_user(
            user_id=current_user.id,
            media_item_id=media_item_id,
        )
        return DeleteMediaResponse(
            media_item_id=result.media_item_id,
            deleted_at=result.deleted_at,
            purge_at=result.purge_at,
            grace_days=media_deletion_service.PURGE_GRACE_DAYS,
        )
    except media_deletion_service.MediaNotFound:
        log_event(
            logger,
            logging.WARNING,
            "media.delete.not_found",
            "Media item not found",
            media_item_id=media_item_id,
            error_code="MEDIA_NOT_FOUND",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Media item not found"
        )
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "media.delete.failed",
            "Failed to delete media item",
            media_item_id=media_item_id,
            error_type=type(exc).__name__,
            error_code="DELETE_FAILED",
            exc_info=exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete media item",
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
        description="Content family of the source material (plain_text, article_text, social_post, ocr, markdown)",
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
    - Audio/Video/Podcast: formatted transcript (Deepgram, captions, RSS)
    - Articles: extracted text (trafilatura)
    - Social posts: raw text of the post
    - Images/PDFs: OCR result

    The response format is consistent: plain text whose paragraphs are separated
    by a blank line. Clients split on blank lines to render paragraphs.
    """
    token = bind_log_context(user_id=current_user.id, media_item_id=media_item_id)
    try:
        record = await get_media_for_user(media_item_id, current_user.id)

        # Unlike the library reads, this one genuinely needs the job: the
        # transcript location lives nowhere else. A library item whose job is gone
        # therefore has no retrievable raw content -- which is a 404 on the
        # content, not on the item.
        job = await resolve_job_for_record(record)
        if job is None:
            log_event(
                logger,
                logging.INFO,
                "media.raw_content.not_available",
                "Raw content unavailable: no processing job survives for this item",
                media_item_id=media_item_id,
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Raw content is no longer available for this media item",
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
