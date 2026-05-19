"""
Canonical API/domain contracts for media ingestion and artifacts.

This module freezes the shared request/response and domain schemas used by:
- backend implementation tasks
- mobile/web client integration tasks

It is intentionally endpoint-agnostic so contracts can be reused before
runtime endpoints are fully implemented.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MediaType(str, Enum):
    PODCAST_EPISODE = "podcast_episode"
    ARTICLE = "article"
    YOUTUBE_VIDEO = "youtube_video"
    SHORT_VIDEO = "short_video"
    AUDIO_FILE = "audio_file"
    SHARED_TEXT = "shared_text"
    UNKNOWN = "unknown"


class SourcePlatform(str, Enum):
    SPOTIFY = "spotify"
    APPLE_PODCASTS = "apple_podcasts"
    DEEZER = "deezer"
    RSS = "rss"
    PODCAST_INDEX = "podcast_index"
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    X = "x"
    WHATSAPP = "whatsapp"
    WEB = "web"
    DIRECT_URL = "direct_url"
    UNKNOWN = "unknown"


class SharedContentType(str, Enum):
    TEXT = "text"
    AUDIO = "audio"


class MediaItemStatus(str, Enum):
    INGESTED = "ingested"
    RESOLVING = "resolving"
    PROCESSING = "processing"
    READY_FOR_ARTIFACTS = "ready_for_artifacts"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TranscriptStatus(str, Enum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    TRANSCRIBING = "transcribing"
    READY = "ready"
    FAILED = "failed"


class ProcessingJobLifecycleStatus(str, Enum):
    PENDING = "pending"
    CLASSIFYING = "classifying"
    RESOLVING = "resolving"
    DOWNLOADING = "downloading"
    EXTRACTING = "extracting"
    TRANSCRIBING = "transcribing"
    READY_FOR_ARTIFACTS = "ready_for_artifacts"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Transitional helper for current ProcessingJob values still present in runtime.
LEGACY_PROCESSING_JOB_STATUS_MAP: Dict[str, ProcessingJobLifecycleStatus] = {
    "pending": ProcessingJobLifecycleStatus.PENDING,
    "rss_resolving": ProcessingJobLifecycleStatus.RESOLVING,
    "downloading": ProcessingJobLifecycleStatus.DOWNLOADING,
    "transcribing": ProcessingJobLifecycleStatus.TRANSCRIBING,
    # Legacy automatic summarization stage maps to transcript-ready in canonical flow.
    "summarizing": ProcessingJobLifecycleStatus.READY_FOR_ARTIFACTS,
    # Legacy email-coupled terminal stage is treated as completed in canonical flow.
    "notifying": ProcessingJobLifecycleStatus.COMPLETED,
    "completed": ProcessingJobLifecycleStatus.COMPLETED,
    "failed": ProcessingJobLifecycleStatus.FAILED,
    "cancelled": ProcessingJobLifecycleStatus.CANCELLED,
}


class ArtifactType(str, Enum):
    SUMMARY = "summary"
    QUIZ = "quiz"
    NOTES = "notes"


class ArtifactStatus(str, Enum):
    QUEUED = "queued"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class CanonicalErrorCode(str, Enum):
    BAD_REQUEST = "BAD_REQUEST"
    INVALID_URL = "INVALID_URL"
    UNSUPPORTED_URL = "UNSUPPORTED_URL"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"
    NOT_FOUND = "NOT_FOUND"
    MEDIA_NOT_FOUND = "MEDIA_NOT_FOUND"
    ARTIFACT_NOT_FOUND = "ARTIFACT_NOT_FOUND"
    CONFLICT = "CONFLICT"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    INSUFFICIENT_MINUTES = "INSUFFICIENT_MINUTES"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class CanonicalErrorPayload(BaseModel):
    code: CanonicalErrorCode
    message: str
    request_id: Optional[str] = None


class CanonicalErrorResponse(BaseModel):
    error: CanonicalErrorPayload
    detail: Optional[str] = None


class ProcessingProgress(BaseModel):
    percentage: int = Field(..., ge=0, le=100)
    stage: ProcessingJobLifecycleStatus


class ProcessingJobContract(BaseModel):
    job_id: str
    status: ProcessingJobLifecycleStatus
    progress: ProcessingProgress
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_code: Optional[CanonicalErrorCode] = None
    error_message: Optional[str] = None


class ArtifactStatusSnapshot(BaseModel):
    status: ArtifactStatus
    updated_at: str
    artifact_id: Optional[str] = None


class TranscriptInfo(BaseModel):
    status: TranscriptStatus
    transcription_s3_key: Optional[str] = None
    source: Optional[str] = Field(
        default=None,
        description="native_transcript | deepgram | article_extractor | x_api_lookup | shared_text",
    )
    language: Optional[str] = None
    segments_count: Optional[int] = Field(default=None, ge=0)
    duration_seconds: Optional[float] = Field(default=None, ge=0)


class MediaItemContract(BaseModel):
    media_item_id: str
    media_key: str
    original_url: str
    normalized_url: str
    media_type: MediaType
    source_platform: SourcePlatform
    status: MediaItemStatus
    transcript: TranscriptInfo
    artifact_statuses: Dict[ArtifactType, ArtifactStatusSnapshot] = Field(
        default_factory=dict
    )
    created_at: str
    updated_at: str


class MediaArtifactContract(BaseModel):
    artifact_id: str
    media_item_id: str
    artifact_type: ArtifactType
    status: ArtifactStatus
    parameters: Dict[str, Any] = Field(default_factory=dict)
    content: Optional[Dict[str, Any]] = None
    error_code: Optional[CanonicalErrorCode] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str
    completed_at: Optional[str] = None


class IngestUrlRequest(BaseModel):
    url: str = Field(..., min_length=1)
    source_app: Optional[str] = None
    locale: Optional[str] = None
    idempotency_key: Optional[str] = None


class IngestSharedContentRequest(BaseModel):
    share_type: SharedContentType
    source_platform: SourcePlatform
    source_app: Optional[str] = None
    locale: Optional[str] = None
    idempotency_key: Optional[str] = None
    text: Optional[str] = None
    content_mime_type: Optional[str] = None
    original_name: Optional[str] = None
    content_size_bytes: Optional[int] = Field(default=None, ge=0)


class IngestUrlResponse(BaseModel):
    media_item: MediaItemContract
    processing_job: ProcessingJobContract
    deduplicated: bool = False
    duplicate_of_media_item_id: Optional[str] = None


class MediaStatusResponse(BaseModel):
    media_item: MediaItemContract
    processing_job: ProcessingJobContract
    artifacts: List[MediaArtifactContract] = Field(default_factory=list)


class ArtifactCreateRequest(BaseModel):
    artifact_type: ArtifactType
    parameters: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None


class ArtifactCreateResponse(BaseModel):
    artifact: MediaArtifactContract
    reused_existing: bool = False


class ArtifactListResponse(BaseModel):
    media_item_id: str
    items: List[MediaArtifactContract] = Field(default_factory=list)
    count: int = Field(default=0, ge=0)


class ArtifactDetailResponse(BaseModel):
    artifact: MediaArtifactContract


__all__ = [
    "ArtifactCreateRequest",
    "ArtifactCreateResponse",
    "ArtifactDetailResponse",
    "ArtifactListResponse",
    "ArtifactStatus",
    "ArtifactStatusSnapshot",
    "ArtifactType",
    "CanonicalErrorCode",
    "CanonicalErrorPayload",
    "CanonicalErrorResponse",
    "IngestSharedContentRequest",
    "IngestUrlRequest",
    "IngestUrlResponse",
    "LEGACY_PROCESSING_JOB_STATUS_MAP",
    "MediaArtifactContract",
    "MediaItemContract",
    "MediaItemStatus",
    "MediaStatusResponse",
    "MediaType",
    "ProcessingJobContract",
    "ProcessingJobLifecycleStatus",
    "ProcessingProgress",
    "SharedContentType",
    "SourcePlatform",
    "TranscriptInfo",
    "TranscriptStatus",
]
