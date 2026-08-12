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
    media_artifacts     the generated content, keyed by media_item_id.
    media_idempotence   global per-content processing ledger, keyed by media_key.

Identity
--------
``media_item_id`` is derived deterministically from ``(user_id, media_key)``.
Two consequences callers must internalize:

1. The same user saving the same content twice always lands on the same row,
   which is what makes the save path idempotent with no read and no transaction.
2. The id is **opaque**. Nothing may parse it, and rows reconstructed by the
   Phase 2 backfill (task-241) will keep their legacy job id verbatim so the
   existing ``media_artifacts`` rows, Algolia records and S3 keys stay valid.

Nullability
-----------
``processing_status`` and ``last_job_id`` are ``None`` by default and stay
optional forever (invariant I3). They are denormalised operational hints: the
library must render fully without them, and ``last_job_id`` is explicitly allowed
to point at a job that no longer exists.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

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


def build_media_item_id(user_id: str, media_key: str) -> str:
    """Derive the deterministic durable id for a (user, content) pair.

    ``"mi_" + sha256(f"{user_id}|{media_key}").hexdigest()[:32]`` exactly as
    specified in §4.1. Truncated to 32 hex characters, i.e. 128 bits, which keeps
    the id short enough to read in a log line while making collisions irrelevant
    at any plausible scale.

    The separator matters: it is what stops ``("ab", "c")`` and ``("a", "bc")``
    from colliding.
    """
    user_id = (user_id or "").strip()
    media_key = (media_key or "").strip()
    if not user_id:
        raise ValueError("user_id is required to derive a media_item_id")
    if not media_key:
        raise ValueError("media_key is required to derive a media_item_id")
    digest = hashlib.sha256(f"{user_id}|{media_key}".encode("utf-8")).hexdigest()
    return f"mi_{digest[:32]}"


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
    # Pointer for debugging and correlation only. Allowed to dangle once the job
    # expires, and never dereferenced on a read path.
    last_job_id: Optional[str] = None

    # --- soft deletion: written ONLY by the user-deletion use case -----------
    deleted_at: Optional[datetime] = None
    purge_at: Optional[int] = None

    # Provenance for rows reconstructed by the Phase 2 backfill (task-241), e.g.
    # "processing_jobs" or "media_artifacts". Absent on rows created by a live
    # save, which makes the backfill's rollback a targeted delete instead of a
    # guess about which rows were synthesised.
    backfilled_from: Optional[str] = None

    schema_version: int = USER_MEDIA_SCHEMA_VERSION

    @property
    def folder_sort_key(self) -> str:
        return build_folder_sort_key(self.folder_id, self.saved_at)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Serialize for the idempotent create.

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
            "backfilled_from": self.backfilled_from,
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
