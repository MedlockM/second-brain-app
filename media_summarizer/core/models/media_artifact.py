"""
Canonical internal model for AI artifacts.

One record type serves both scopes (task-269/270): a media artifact is a
collection artifact with a single source. The record is an **append-only history
entry** — once it reaches ``ready`` it is never modified again. There is no
staleness flag, no expiry, no automatic regeneration: adding a media to a
collection creates a gap between an entry's ``sources`` snapshot and the
collection's current contents, and that gap *is* the history rather than a defect
to repair.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class MediaArtifactType(str, Enum):
    SUMMARY_SHORT = "summary_short"
    SUMMARY_DETAILED = "summary_detailed"
    QUIZ = "quiz"
    NOTES = "notes"
    FLASHCARDS = "flashcards"


class MediaArtifactStatus(str, Enum):
    QUEUED = "queued"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"


class ArtifactScope(str, Enum):
    """What an artifact was generated over.

    ``FOLDER`` is what the UI calls a collection; the backend vocabulary stays
    ``folder`` everywhere (task-270).
    """

    MEDIA = "media"
    FOLDER = "folder"


def build_scope_key(*, user_id: str, scope: "ArtifactScope | str", scope_id: str) -> str:
    """Hash key of the ``scope-index`` GSI.

    ``user_id`` is part of it on purpose: isolation between users becomes
    structural, so a listing query cannot reach another account's scope. That is
    what replaces the old ownership check, which resolved the artifact's media
    item — impossible for a collection artifact, which has no media.
    """
    scope_value = scope.value if isinstance(scope, ArtifactScope) else str(scope)
    return f"{user_id}#{scope_value}#{scope_id}"


class ArtifactStorageRef(BaseModel):
    bucket: str
    key: str
    content_type: str = "application/json"
    content_sha256: Optional[str] = None


class ArtifactSource(BaseModel):
    """One entry of an artifact's immutable source snapshot.

    ``transcript_s3_key`` is the key **actually** read, translation included, so
    the snapshot designates the exact text the model saw. ``excluded`` marks a
    source that carried no usable transcript: it is recorded rather than dropped,
    so the artifact stays honest about what it could not read.
    """

    media_item_id: str
    title: Optional[str] = None
    transcript_s3_key: Optional[str] = None
    language: Optional[str] = None
    excluded: bool = False
    excluded_reason: Optional[str] = None


class ArtifactLlmUsage(BaseModel):
    """What the generation actually consumed, read off the provider response."""

    prompt_tokens: int = 0
    cached_tokens: int = 0
    completion_tokens: int = 0
    cost_eur: float = 0.0


class MediaArtifactRecord(BaseModel):
    # Deterministic, derived from (user, scope, type, parameters, sources, dedup
    # window) by ``artifact_service.build_artifact_id`` — never random.
    artifact_id: str
    user_id: str
    scope: ArtifactScope
    scope_id: str
    scope_key: str
    artifact_type: MediaArtifactType
    status: MediaArtifactStatus = MediaArtifactStatus.QUEUED
    parameters: Dict[str, Any] = Field(default_factory=dict)
    generator_version: str
    title: Optional[str] = None
    source_count: int = 0
    sources: List[ArtifactSource] = Field(default_factory=list)
    storage: Optional[ArtifactStorageRef] = None
    llm_usage: Optional[ArtifactLlmUsage] = None
    # Worker lease, so a generation abandoned mid-flight becomes recoverable
    # instead of pinning the entry in ``generating`` forever.
    lease_expires_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)
    completed_at: Optional[datetime] = None

    def to_dynamodb_item(self) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "artifact_id": self.artifact_id,
            "user_id": self.user_id,
            "scope": self.scope.value,
            "scope_id": self.scope_id,
            "scope_key": self.scope_key,
            "artifact_type": self.artifact_type.value,
            "status": self.status.value,
            "parameters": self.parameters,
            "generator_version": self.generator_version,
            "source_count": self.source_count,
            "sources": [
                source.model_dump(exclude_none=True) for source in self.sources
            ],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if self.title:
            item["title"] = self.title
        if self.storage is not None:
            item["storage"] = self.storage.model_dump(exclude_none=True)
        if self.llm_usage is not None:
            item["llm_usage"] = self.llm_usage.model_dump()
        if self.lease_expires_at is not None:
            item["lease_expires_at"] = self.lease_expires_at.isoformat()
        if self.error_code:
            item["error_code"] = self.error_code
        if self.error_message:
            item["error_message"] = self.error_message
        if self.completed_at is not None:
            item["completed_at"] = self.completed_at.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "MediaArtifactRecord":
        payload = dict(item)
        payload["scope"] = ArtifactScope(payload["scope"])
        payload["artifact_type"] = MediaArtifactType(payload["artifact_type"])
        payload["status"] = MediaArtifactStatus(payload["status"])
        payload["created_at"] = datetime.fromisoformat(payload["created_at"])
        payload["updated_at"] = datetime.fromisoformat(payload["updated_at"])
        for optional_timestamp in ("completed_at", "lease_expires_at"):
            if payload.get(optional_timestamp):
                payload[optional_timestamp] = datetime.fromisoformat(
                    payload[optional_timestamp]
                )
            else:
                payload.pop(optional_timestamp, None)
        payload["source_count"] = int(payload.get("source_count") or 0)
        storage = payload.get("storage")
        if storage is not None:
            payload["storage"] = ArtifactStorageRef(**storage)
        usage = payload.get("llm_usage")
        if usage is not None:
            payload["llm_usage"] = ArtifactLlmUsage(
                prompt_tokens=int(usage.get("prompt_tokens") or 0),
                cached_tokens=int(usage.get("cached_tokens") or 0),
                completion_tokens=int(usage.get("completion_tokens") or 0),
                cost_eur=float(usage.get("cost_eur") or 0.0),
            )
        payload["sources"] = [
            ArtifactSource(**source) for source in (payload.get("sources") or [])
        ]
        return cls(**payload)
