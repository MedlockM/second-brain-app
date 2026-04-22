"""
Canonical internal models for media artifacts and generation locks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _new_artifact_id() -> str:
    return f"art_{uuid.uuid4().hex}"


class MediaArtifactType(str, Enum):
    SUMMARY = "summary"
    QUIZ = "quiz"
    NOTES = "notes"
    FLASHCARDS = "flashcards"


class MediaArtifactStatus(str, Enum):
    QUEUED = "queued"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class ArtifactGenerationStatus(str, Enum):
    RESERVED = "reserved"
    READY = "ready"
    FAILED = "failed"


class ArtifactStorageRef(BaseModel):
    bucket: str
    key: str
    content_type: str = "application/json"
    content_sha256: Optional[str] = None


class MediaArtifactRecord(BaseModel):
    artifact_id: str = Field(default_factory=_new_artifact_id)
    media_item_id: str
    artifact_type: MediaArtifactType
    status: MediaArtifactStatus = MediaArtifactStatus.QUEUED
    parameters: Dict[str, Any] = Field(default_factory=dict)
    request_fingerprint: str
    generation_fingerprint: str
    generator_version: str
    transcript_s3_key: str
    transcript_sha256: str
    storage: Optional[ArtifactStorageRef] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    reused_from_artifact_id: Optional[str] = None
    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)
    completed_at: Optional[datetime] = None

    def to_dynamodb_item(self) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "artifact_id": self.artifact_id,
            "media_item_id": self.media_item_id,
            "artifact_type": self.artifact_type.value,
            "status": self.status.value,
            "parameters": self.parameters,
            "request_fingerprint": self.request_fingerprint,
            "generation_fingerprint": self.generation_fingerprint,
            "generator_version": self.generator_version,
            "transcript_s3_key": self.transcript_s3_key,
            "transcript_sha256": self.transcript_sha256,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if self.storage is not None:
            item["storage"] = self.storage.model_dump(exclude_none=True)
        if self.error_code:
            item["error_code"] = self.error_code
        if self.error_message:
            item["error_message"] = self.error_message
        if self.reused_from_artifact_id:
            item["reused_from_artifact_id"] = self.reused_from_artifact_id
        if self.completed_at is not None:
            item["completed_at"] = self.completed_at.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "MediaArtifactRecord":
        payload = dict(item)
        payload["artifact_type"] = MediaArtifactType(payload["artifact_type"])
        payload["status"] = MediaArtifactStatus(payload["status"])
        payload["created_at"] = datetime.fromisoformat(payload["created_at"])
        payload["updated_at"] = datetime.fromisoformat(payload["updated_at"])
        if payload.get("completed_at"):
            payload["completed_at"] = datetime.fromisoformat(payload["completed_at"])
        storage = payload.get("storage")
        if storage is not None:
            payload["storage"] = ArtifactStorageRef(**storage)
        return cls(**payload)


class ArtifactGenerationLock(BaseModel):
    generation_fingerprint: str
    artifact_type: MediaArtifactType
    generator_version: str
    transcript_sha256: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    status: ArtifactGenerationStatus = ArtifactGenerationStatus.RESERVED
    artifact_id: str
    storage: Optional[ArtifactStorageRef] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)
    completed_at: Optional[datetime] = None

    def to_dynamodb_item(self) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "generation_fingerprint": self.generation_fingerprint,
            "artifact_type": self.artifact_type.value,
            "generator_version": self.generator_version,
            "transcript_sha256": self.transcript_sha256,
            "parameters": self.parameters,
            "status": self.status.value,
            "artifact_id": self.artifact_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if self.storage is not None:
            item["storage"] = self.storage.model_dump(exclude_none=True)
        if self.error_code:
            item["error_code"] = self.error_code
        if self.error_message:
            item["error_message"] = self.error_message
        if self.completed_at is not None:
            item["completed_at"] = self.completed_at.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "ArtifactGenerationLock":
        payload = dict(item)
        payload["artifact_type"] = MediaArtifactType(payload["artifact_type"])
        payload["status"] = ArtifactGenerationStatus(payload["status"])
        payload["created_at"] = datetime.fromisoformat(payload["created_at"])
        payload["updated_at"] = datetime.fromisoformat(payload["updated_at"])
        if payload.get("completed_at"):
            payload["completed_at"] = datetime.fromisoformat(payload["completed_at"])
        storage = payload.get("storage")
        if storage is not None:
            payload["storage"] = ArtifactStorageRef(**storage)
        return cls(**payload)
