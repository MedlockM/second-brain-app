"""Domain models for the hexagonal media ingestion core."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MediaFamily(str, Enum):
    PODCAST = "podcast"
    ARTICLE = "article"
    YOUTUBE = "youtube"
    SOCIAL_VIDEO = "social_video"
    AUDIO = "audio"
    TEXT = "text"
    UNKNOWN = "unknown"


class MediaType(str, Enum):
    PODCAST_EPISODE = "podcast_episode"
    ARTICLE = "article"
    YOUTUBE_VIDEO = "youtube_video"
    SHORT_VIDEO = "short_video"
    IMAGE_POST = "image_post"
    AUDIO_FILE = "audio_file"
    SHARED_TEXT = "shared_text"
    UNKNOWN = "unknown"


class SourcePlatform(str, Enum):
    SPOTIFY = "spotify"
    APPLE_PODCASTS = "apple_podcasts"
    DEEZER = "deezer"
    RSS = "rss"
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


class ProcessingLifecycleStatus(str, Enum):
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


@dataclass(frozen=True)
class UserContext:
    user_id: str
    user_email: str


@dataclass(frozen=True)
class IngestUrlRequest:
    url: str
    source_app: Optional[str] = None
    locale: Optional[str] = None
    transcript_language: Optional[str] = None
    idempotency_key: Optional[str] = None
    folder_id: Optional[str] = None
    tag_ids: Optional[List[str]] = None


@dataclass(frozen=True)
class IngestUrlCommand:
    user: UserContext
    request: IngestUrlRequest


@dataclass(frozen=True)
class IngestSharedContentRequest:
    share_type: SharedContentType
    source_platform: SourcePlatform
    source_app: Optional[str] = None
    locale: Optional[str] = None
    idempotency_key: Optional[str] = None
    text: Optional[str] = None
    content_hash: Optional[str] = None
    content_mime_type: Optional[str] = None
    original_name: Optional[str] = None
    content_size_bytes: Optional[int] = None
    staged_audio_s3_key: Optional[str] = None
    folder_id: Optional[str] = None
    tag_ids: Optional[List[str]] = None


@dataclass(frozen=True)
class IngestSharedContentCommand:
    user: UserContext
    request: IngestSharedContentRequest


@dataclass(frozen=True)
class ClassifiedUrl:
    media_family: MediaFamily
    source_platform: SourcePlatform
    resolver_key: str


@dataclass(frozen=True)
class ResolveContext:
    command: IngestUrlCommand
    normalized_url: str
    media_key: str
    classification: ClassifiedUrl


@dataclass(frozen=True)
class ResolvedMedia:
    media_key: str
    normalized_url: str
    media_family: MediaFamily
    media_type: MediaType
    source_platform: SourcePlatform
    resolver_key: str
    title: Optional[str] = None
    audio_url: Optional[str] = None
    audio_s3_key: Optional[str] = None
    raw_text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IngestionOutcome:
    media_item_id: str
    job_id: str
    status: ProcessingLifecycleStatus
    media_key: str
    normalized_url: str
    deduplicated: bool = False
    duplicate_of_media_item_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
