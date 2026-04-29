"""
Processing job model for tracking media processing jobs using DynamoDB.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, model_validator
import uuid
from enum import Enum


class JobStatus(str, Enum):
    """Enumeration of possible job statuses."""

    PENDING = "pending"
    RSS_RESOLVING = "rss_resolving"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    SUMMARIZING = "summarizing"
    NOTIFYING = "notifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingJob(BaseModel):
    """Processing job model for tracking media processing workflows in DynamoDB."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., min_length=1)
    media_item_id: Optional[str] = None
    source_id: Optional[str] = None
    status: JobStatus = Field(default=JobStatus.PENDING)

    # Input data
    source_url: Optional[str] = None  # e.g. podcast RSS feed URL
    media_url: Optional[str] = None  # direct audio/video URL
    media_key: Optional[str] = None  # globally unique key (e.g. episode GUID)
    media_image: Optional[str] = None
    user_email: str = Field(..., min_length=1)

    # Searchable metadata
    title: Optional[str] = None  # Display title of the media item
    source_platform: Optional[str] = None  # e.g. youtube, spotify, tiktok, web, audio
    media_type: Optional[str] = None  # e.g. podcast, article, video, audio

    # Processing metadata

    # File locations
    audio_s3_key: Optional[str] = None
    transcription_s3_key: Optional[str] = None
    summary_s3_key: Optional[str] = None
    quiz_s3_key: Optional[str] = None  # S3 key for generated quiz

    # Organization
    folder_id: Optional[str] = None  # Folder this media belongs to (user_folders table)
    tag_ids: List[str] = Field(default_factory=list)  # User tag IDs associated with this media

    # Media metadata
    media_date_published: Optional[int] = None  # Unix timestamp - when content was published

    # Error handling
    error_message: Optional[str] = None
    error_step: Optional[str] = None
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=3, ge=0)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expire_at: Optional[int] = None  # TTL timestamp for DynamoDB auto-deletion

    # Processing durations (in seconds)
    download_duration: Optional[int] = None
    transcription_duration: Optional[int] = None
    summarization_duration: Optional[int] = None
    total_duration: Optional[int] = None

    @field_validator("user_id")
    @classmethod
    def user_id_must_not_be_empty(cls, v):
        """Validate that user_id is not empty."""
        if not v.strip():
            raise ValueError("User ID must not be empty")
        return v.strip()

    @field_validator("user_email")
    @classmethod
    def email_must_be_valid(cls, v):
        """Validate that the email is not empty and has basic format."""
        if not v.strip():
            raise ValueError("Email must not be empty")
        if "@" not in v:
            raise ValueError("Email must contain @ symbol")
        return v.lower().strip()

    @model_validator(mode="after")
    def retry_count_validation(self):
        """Validate retry count against max retries."""
        if self.retry_count > self.max_retries:
            raise ValueError(
                f"Retry count ({self.retry_count}) cannot exceed max retries ({self.max_retries})"
            )
        return self

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now(timezone.utc)

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert the model to a DynamoDB item."""
        item = {
            "id": self.id,
            "user_id": self.user_id,
            "job_status": self.status.value,
            "user_email": self.user_email,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        
        # Add TTL if set
        if self.expire_at:
            item["expire_at"] = self.expire_at

        # Add optional fields if they exist
        optional_fields = [
            "media_item_id",
            "source_id",
            "source_url",
            "media_url",
            "media_key",
            "media_image",
            "title",
            "source_platform",
            "media_type",
            "audio_s3_key",
            "transcription_s3_key",
            "summary_s3_key",
            "quiz_s3_key",
            "folder_id",
            "media_date_published",
            "error_message",
            "error_step",
            "download_duration",
            "transcription_duration",
            "summarization_duration",
            "total_duration",
        ]

        for field in optional_fields:
            value = getattr(self, field)
            if value is not None:
                item[field] = value

        # Handle list fields (store only when non-empty)
        if self.tag_ids:
            item["tag_ids"] = self.tag_ids

        # Handle datetime fields
        datetime_fields = ["started_at", "completed_at"]
        for field in datetime_fields:
            value = getattr(self, field)
            if value is not None:
                item[field] = value.isoformat()

        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "ProcessingJob":
        """Create a ProcessingJob instance from a DynamoDB item."""
        # Convert datetime strings back to datetime objects
        datetime_fields = ["created_at", "updated_at", "started_at", "completed_at"]
        for field in datetime_fields:
            if field in item and item[field]:
                item[field] = datetime.fromisoformat(item[field])

        # Convert status string to enum
        if "job_status" in item:
            item["status"] = JobStatus(item["job_status"])
            # Remove the DynamoDB field name so it doesn't interfere with model creation
            del item["job_status"]
            
        # Handle expire_at (TTL) - convert Decimal to int if coming from boto3
        if "expire_at" in item:
            item["expire_at"] = int(item["expire_at"])

        return cls(**item)

    def update_status(
        self,
        new_status: JobStatus,
        error_message: Optional[str] = None,
        error_step: Optional[str] = None,
    ) -> None:
        """Update job status and timestamp."""
        old_status = self.status
        self.status = new_status

        # Set started_at when moving from PENDING
        if old_status == JobStatus.PENDING and new_status != JobStatus.PENDING:
            self.started_at = datetime.now(timezone.utc)

        # Set completed_at for terminal states
        if new_status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            self.completed_at = datetime.now(timezone.utc)
            if self.started_at:
                self.total_duration = int(
                    (self.completed_at - self.started_at).total_seconds()
                )

        # Handle error information
        if new_status == JobStatus.FAILED:
            self.error_message = error_message
            self.error_step = error_step
            
        # Update TTL on status change (extend life)
        # Keep jobs for 30 days after last update
        self.expire_at = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        self.updated_at = datetime.now(timezone.utc)

    def increment_retry(self) -> bool:
        """Increment retry count. Returns True if more retries are allowed."""
        self.retry_count += 1
        self.updated_at = datetime.now(timezone.utc)
        return self.retry_count <= self.max_retries

    def can_retry(self) -> bool:
        """Check if the job can be retried."""
        return self.retry_count < self.max_retries and self.status == JobStatus.FAILED

    def mark_started(self) -> None:
        """Mark the job as started."""
        if self.status == JobStatus.PENDING:
            self.update_status(JobStatus.RSS_RESOLVING)

    def mark_downloading(self) -> None:
        """Mark the job as downloading."""
        self.update_status(JobStatus.DOWNLOADING)

    def mark_transcribing(self) -> None:
        """Mark the job as transcribing."""
        self.update_status(JobStatus.TRANSCRIBING)

    def mark_summarizing(self) -> None:
        """Mark the job as summarizing."""
        self.update_status(JobStatus.SUMMARIZING)

    def mark_notifying(self) -> None:
        """Mark the job as sending notifications."""
        self.update_status(JobStatus.NOTIFYING)

    def mark_completed(self) -> None:
        """Mark the job as completed."""
        self.update_status(JobStatus.COMPLETED)

    def mark_failed(self, error_message: str, error_step: Optional[str] = None) -> None:
        """Mark the job as failed."""
        self.update_status(JobStatus.FAILED, error_message, error_step)

    def mark_cancelled(self) -> None:
        """Mark the job as cancelled."""
        self.update_status(JobStatus.CANCELLED)

    def set_media_info(self, media_item_id: str, source_id: str) -> None:
        """Set media item and source information."""
        self.media_item_id = media_item_id
        self.source_id = source_id
        self.updated_at = datetime.now(timezone.utc)

    def set_audio_location(self, s3_key: str) -> None:
        """Set the S3 location of the downloaded audio."""
        self.audio_s3_key = s3_key
        self.updated_at = datetime.now(timezone.utc)

    def set_transcription_location(self, s3_key: str) -> None:
        """Set the S3 location of the transcription."""
        self.transcription_s3_key = s3_key
        self.updated_at = datetime.now(timezone.utc)

    def set_summary_location(self, s3_key: str) -> None:
        """Set the S3 location of the summary."""
        self.summary_s3_key = s3_key
        self.updated_at = datetime.now(timezone.utc)

    def set_processing_duration(self, step: str, duration: int) -> None:
        """Set the processing duration for a specific step."""
        if step == "download":
            self.download_duration = duration
        elif step == "transcription":
            self.transcription_duration = duration
        elif step == "summarization":
            self.summarization_duration = duration

        self.updated_at = datetime.now(timezone.utc)

        self.updated_at = datetime.now(timezone.utc)

    def is_terminal_state(self) -> bool:
        """Check if the job is in a terminal state."""
        return self.status in [
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        ]

    def is_processing(self) -> bool:
        """Check if the job is currently being processed."""
        return self.status in [
            JobStatus.RSS_RESOLVING,
            JobStatus.DOWNLOADING,
            JobStatus.TRANSCRIBING,
            JobStatus.SUMMARIZING,
            JobStatus.NOTIFYING,
        ]

    def get_progress_percentage(self) -> int:
        """Get the progress percentage based on current status."""
        progress_map = {
            JobStatus.PENDING: 0,
            JobStatus.RSS_RESOLVING: 10,
            JobStatus.DOWNLOADING: 25,
            JobStatus.TRANSCRIBING: 50,
            JobStatus.SUMMARIZING: 75,
            JobStatus.NOTIFYING: 90,
            JobStatus.COMPLETED: 100,
            JobStatus.FAILED: 0,
            JobStatus.CANCELLED: 0,
        }
        return progress_map.get(self.status, 0)

    def update(self, **kwargs):
        """Update job attributes."""
        for key, value in kwargs.items():
            if hasattr(self, key) and key != "id":  # Don't allow ID updates
                setattr(self, key, value)
        
        # Update TTL on any update
        self.expire_at = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
        self.updated_at = datetime.now(timezone.utc)
        return self

    def __repr__(self):
        return f"<ProcessingJob(id='{self.id}', user_id='{self.user_id}', status='{self.status.value}')>"
