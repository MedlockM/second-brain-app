"""
Durable canonical record of a media item saved by a user.

THE source of truth for "what is in my library". Introduced by task-240 per the
owner-validated Option A of
``docs/research/task-218-durable-media-library-persistence/README.md`` (§4.1-4.3).

How it relates to the other stores:

    user_media          durable, user-owned. Never expires unless the user
                        deletes the item. Answers "what did I save, how is it
                        organized, is it ready".
    processing_jobs     purely operational and expirable. Answers "what is the
                        pipeline doing right now". Its disappearance must be
                        invisible to the library.
    media_artifacts     user-owned generated content, scoped by media_key.
    media_idempotence   global per-content processing ledger, keyed by media_key.

Identity
--------
``media_item_id`` identifies one user save, while ``media_key`` identifies the
content globally. Saving the same content twice therefore creates two opaque
``mi_`` ids that may carry different folders and tags while both point at the
same transcript and artifact history.

Nullability
-----------
``processing_status`` and ``last_job_id`` are ``None`` by default and stay
optional forever (invariant I3). They are denormalised operational hints: the
library must render fully without them, and ``last_job_id`` is explicitly allowed
to point at a job that no longer exists.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

# Bumped when the persisted shape changes in a way readers must know about.
USER_MEDIA_SCHEMA_VERSION = 1

# Sort-key segment used when a row has no folder, so folder_sort_key is always
# present and the folder LSI never silently drops an item.
NO_FOLDER_SEGMENT = "none"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class UserMediaStatus(str, Enum):
    """Lifecycle of the *library entry*, not of the pipeline.

    Deliberately coarse: the library only needs to know whether the entry is
    usable. The fine-grained pipeline stages stay in ``processing_jobs``, which
    is allowed to disappear.
    """

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


def new_media_item_id() -> str:
    """Return the opaque id of one save, independent from content identity."""
    return f"mi_{uuid4().hex}"


def build_folder_sort_key(folder_id: Optional[str], saved_at: datetime) -> str:
    """Composite LSI range key: one folder's contents in a single Query."""
    return f"{folder_id or NO_FOLDER_SEGMENT}#{saved_at.isoformat()}"


class UserMediaRecord(BaseModel):
    """One saved media item, owned by exactly one user."""

    # --- identity / ownership (write-once, by the create path only) ----------
    user_id: str
    media_item_id: str
    # Content identity (mkey_v1_<sha256>). Maps a library row back to the global
    # processing ledger and to other users' copies of the same content.
    media_key: str

    # --- display metadata ----------------------------------------------------
    title: Optional[str] = None
    source_url: Optional[str] = None
    source_platform: Optional[str] = None
    media_type: Optional[str] = None
    duration_seconds: Optional[int] = None
    thumbnail_url: Optional[str] = None
    language: Optional[str] = None

    # --- organization (user-authored: never clobbered by the pipeline) -------
    # Exactly one folder, defaulting to the user's "Uncategorized" folder so an
    # entry is always reachable through folder navigation.
    folder_id: Optional[str] = None
    tag_ids: List[str] = Field(default_factory=list)

    # --- ordering ------------------------------------------------------------
    saved_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)

    # --- denormalised operational hints (nullable by contract, invariant I3) --
    processing_status: Optional[UserMediaStatus] = None
    # Pointer for debugging and correlation. Global content reads prefer
    # media_key; direct document/audio uploads use this owned pointer.
    last_job_id: Optional[str] = None

    # --- soft deletion: written ONLY by the user-deletion use case -----------
    deleted_at: Optional[datetime] = None
    purge_at: Optional[int] = None

    schema_version: int = USER_MEDIA_SCHEMA_VERSION

    @property
    def folder_sort_key(self) -> str:
        return build_folder_sort_key(self.folder_id, self.saved_at)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Serialize for the one-row-per-save create.

        Only the create path uses this. Every later mutation is an
        attribute-level ``UpdateItem`` (invariant I1), so this method never has
        to preserve a field written by someone else.

        ``deleted_at`` and ``purge_at`` are deliberately never emitted here: a
        freshly saved row is not in a deleted state, and only the deletion use
        case may write them.
        """
        item: Dict[str, Any] = {
            "user_id": self.user_id,
            "media_item_id": self.media_item_id,
            "media_key": self.media_key,
            "saved_at": self.saved_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "folder_sort_key": self.folder_sort_key,
            "tag_ids": list(self.tag_ids),
            "schema_version": self.schema_version,
        }
        optional: Dict[str, Any] = {
            "title": self.title,
            "source_url": self.source_url,
            "source_platform": self.source_platform,
            "media_type": self.media_type,
            "duration_seconds": self.duration_seconds,
            "thumbnail_url": self.thumbnail_url,
            "language": self.language,
            "folder_id": self.folder_id,
            "processing_status": (
                self.processing_status.value if self.processing_status else None
            ),
            "last_job_id": self.last_job_id,
        }
        for key, value in optional.items():
            if value is not None and value != "":
                item[key] = value
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "UserMediaRecord":
        payload = dict(item)
        # Derived on write, recomputed from folder_id + saved_at on read.
        payload.pop("folder_sort_key", None)

        for field_name in ("saved_at", "updated_at", "deleted_at"):
            raw = payload.get(field_name)
            if isinstance(raw, str) and raw:
                payload[field_name] = datetime.fromisoformat(raw)
            elif raw in ("", None):
                payload.pop(field_name, None)

        status = payload.get("processing_status")
        if status:
            try:
                payload["processing_status"] = UserMediaStatus(status)
            except ValueError:
                # A status from a future or legacy writer must not make the whole
                # library row unreadable: degrade to "unknown" rather than raise.
                payload["processing_status"] = None
        else:
            payload.pop("processing_status", None)

        # DynamoDB numbers come back as Decimal.
        for field_name in ("duration_seconds", "purge_at", "schema_version"):
            raw = payload.get(field_name)
            if raw is not None:
                try:
                    payload[field_name] = int(raw)
                except (TypeError, ValueError):
                    payload.pop(field_name, None)

        tag_ids = payload.get("tag_ids")
        payload["tag_ids"] = [str(t) for t in tag_ids] if tag_ids else []

        return cls(**payload)
