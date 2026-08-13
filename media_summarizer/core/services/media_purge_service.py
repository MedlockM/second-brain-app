"""
The cascade that removes everything one media item owns.

Two callers, one implementation, on purpose:

- ``account_deletion_service.purge_account`` (task-224) runs it over every media
  item of an account being erased.
- ``workers/cleanup/media_lifecycle.py`` (task-243) runs it for a single item when
  the ``user_media`` TTL sweeps a row the user deleted 30 days earlier.

The two paths *must* delete the same things. A media item whose artifacts survive
its library row is exactly the failure §6.2 of
``docs/research/task-218-durable-media-library-persistence/README.md`` warns
about: ``media_item_id`` is deterministic in ``(user_id, media_key)``, so
re-saving the same URL after a purge lands on the same id and would inherit the
stale artifacts of its previous life. That is why this module exists instead of a
second copy of the same logic in the worker.

Content shared between accounts
-------------------------------
Artifacts are content-addressed: ``complete_artifact_generation`` writes one
``ArtifactStorageRef`` onto every artifact row sharing a
``generation_fingerprint`` and stores the same ref in the generation lock, so two
users who imported the same episode read the same S3 object. Deleting it because
one of them left would break the other. :func:`purge_artifacts_for_media_items`
therefore deletes an artifact object and its generation lock only when *no*
sibling artifact survives outside the set being purged.

Transcripts, audio and documents need no such guard: their keys are derived from
a job id (or, for share-extension uploads, from ``shared-audio/<user_id>/``), and
both are per user.
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Optional, Tuple

from media_summarizer.core.models.media_artifact import MediaArtifactRecord
from media_summarizer.utils import (
    artifact_idempotence,
    media_artifacts,
    s3,
    translation_idempotence,
)
from media_summarizer.utils.env import required_env

logger = logging.getLogger(__name__)


def _bump(counts: Dict[str, int], step: str, count: int = 1) -> None:
    counts[step] = counts.get(step, 0) + count


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


async def purge_artifacts_for_media_items(
    media_item_ids: Iterable[str],
) -> Dict[str, int]:
    """Delete every artifact of the given media items, plus their S3 objects.

    The set passed in defines what "doomed" means for the sibling rule below, so
    calling this once with N ids is not the same as calling it N times: two media
    items of the same account that share a generated object have their object
    deleted only in the first form. Both callers pass the largest set they own —
    the whole account for an erasure, one item for a TTL purge — which is the
    correct scope in each case.
    """
    counts: Dict[str, int] = {}
    doomed: Dict[str, MediaArtifactRecord] = {}
    for media_item_id in sorted(set(media_item_ids)):
        for record in await media_artifacts.list_media_artifacts_by_media_item(
            media_item_id
        ):
            doomed[record.artifact_id] = record

    by_generation: Dict[str, List[MediaArtifactRecord]] = {}
    for record in doomed.values():
        if record.generation_fingerprint:
            by_generation.setdefault(record.generation_fingerprint, []).append(record)

    for fingerprint, records in by_generation.items():
        siblings = await media_artifacts.list_media_artifacts_by_generation_fingerprint(
            fingerprint
        )
        if any(sibling.artifact_id not in doomed for sibling in siblings):
            # Another media item still reads this object. Its row and its request
            # pointer are this item's and still go; the bytes stay.
            _bump(counts, "artifact_objects_kept_shared", len(records))
            continue
        for bucket, key in _storage_refs(siblings or records):
            await s3.delete_object(bucket, key)
            _bump(counts, "artifact_objects_deleted")
        await artifact_idempotence.delete_generation_lock(fingerprint)
        _bump(counts, "artifact_generation_locks_deleted")

    for record in doomed.values():
        if record.request_fingerprint:
            await media_artifacts.delete_request_pointer(record.request_fingerprint)
            _bump(counts, "artifact_request_pointers_deleted")
        await media_artifacts.delete_media_artifact(record.artifact_id)
        _bump(counts, "artifact_rows_deleted")

    return counts


def _storage_refs(
    records: Iterable[MediaArtifactRecord],
) -> List[Tuple[str, str]]:
    """Deduplicated (bucket, key) pairs. Records without storage never generated."""
    refs: Dict[Tuple[str, str], None] = {}
    for record in records:
        storage = record.storage
        if storage and storage.bucket and storage.key:
            refs[(storage.bucket, storage.key)] = None
    return list(refs.keys())


# ---------------------------------------------------------------------------
# S3 objects produced by a processing job
# ---------------------------------------------------------------------------


async def purge_job_objects(
    job_id: str,
    *,
    transcription_s3_key: Optional[str] = None,
    audio_s3_key: Optional[str] = None,
    summary_s3_key: Optional[str] = None,
    quiz_s3_key: Optional[str] = None,
) -> Dict[str, int]:
    """Every S3 object one job produced, plus the translation locks it owns.

    Prefix sweeps are keyed on the bare job id, which is safe because job ids are
    fixed-length UUIDs: none is a prefix of another.

    The explicit keys are optional because the two callers know different things.
    The account purge still holds the job row and passes the keys recorded on it,
    which catches objects written outside the id prefix. The TTL purge only has
    ``user_media.last_job_id`` — the job row may have expired years ago — so it
    relies on the prefix sweeps alone.
    """
    if not job_id:
        return {}

    counts: Dict[str, int] = {}
    audio_bucket = required_env("AUDIO_BUCKET")
    transcript_bucket = required_env("TRANSCRIPT_BUCKET")
    document_bucket = required_env("DOCUMENT_BUCKET")

    transcript_keys = await list_prefix(transcript_bucket, job_id)
    if transcription_s3_key and transcription_s3_key not in transcript_keys:
        transcript_keys.append(transcription_s3_key)

    for key in transcript_keys:
        source_key, language = _split_translated_key(key)
        if source_key and language:
            # The lock is fingerprinted on the *source* key, so it is recoverable
            # only from the translated object that proves it exists.
            await translation_idempotence.delete_translation_lock(
                translation_idempotence.build_translation_fingerprint(
                    transcript_s3_key=source_key,
                    target_language=language,
                )
            )
            _bump(counts, "translation_locks_deleted")
        await s3.delete_object(transcript_bucket, key)
        _bump(counts, "transcript_objects_deleted")

    _bump(counts, "audio_objects_deleted", await purge_prefix(audio_bucket, job_id))
    if audio_s3_key and not audio_s3_key.startswith(job_id):
        await s3.delete_object(audio_bucket, audio_s3_key)
        _bump(counts, "audio_objects_deleted")

    # Documents are stored under a per-job folder ("<job_id>/<file_name>").
    _bump(
        counts,
        "document_objects_deleted",
        await purge_prefix(document_bucket, f"{job_id}/"),
    )

    # Pre-artifact jobs wrote their summary and quiz straight to a bucket instead
    # of going through media_artifacts, so those keys only exist on the job row.
    if summary_s3_key:
        await s3.delete_object(required_env("SUMMARY_BUCKET"), summary_s3_key)
        _bump(counts, "legacy_summary_objects_deleted")
    if quiz_s3_key:
        await s3.delete_object(required_env("QUIZ_BUCKET"), quiz_s3_key)
        _bump(counts, "legacy_quiz_objects_deleted")

    return counts


def _split_translated_key(key: str) -> Tuple[Optional[str], Optional[str]]:
    """Recover ``(source_key, language)`` from a translated transcript key.

    Inverse of ``build_translated_transcript_key``: ``<stem>.translated.<lang>.<ext>``
    -> ``(<stem>.<ext>, <lang>)``. Returns ``(None, None)`` for a source key.
    """
    marker = ".translated."
    if marker not in key:
        return None, None
    stem, remainder = key.split(marker, 1)
    parts = remainder.split(".", 1)
    language = parts[0]
    if not language:
        return None, None
    if len(parts) == 1:
        return stem, language
    return f"{stem}.{parts[1]}", language


# ---------------------------------------------------------------------------
# S3 prefix helpers
# ---------------------------------------------------------------------------


async def list_prefix(bucket: str, prefix: str) -> List[str]:
    if not prefix:
        raise ValueError("refusing to list a whole bucket: prefix is required")
    return [
        str(obj["Key"])
        for obj in await s3.list_objects(bucket, prefix=prefix, max_keys=1000)
        if obj.get("Key")
    ]


async def purge_prefix(bucket: str, prefix: str) -> int:
    """Delete every object under a prefix, one page at a time.

    Re-listing after each page rather than paginating with a continuation token:
    the page just deleted is gone, so the next LIST returns the next 1000 keys.
    An empty ``prefix`` would mean "empty this bucket" and is rejected outright.
    """
    if not prefix:
        raise ValueError("refusing to purge a whole bucket: prefix is required")
    deleted = 0
    while True:
        keys = await list_prefix(bucket, prefix)
        if not keys:
            return deleted
        for key in keys:
            await s3.delete_object(bucket, key)
            deleted += 1
        if len(keys) < 1000:
            return deleted
