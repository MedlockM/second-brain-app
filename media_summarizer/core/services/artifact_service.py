"""
Canonical artifact storage, request idempotence, and shared cache orchestration.
"""

from __future__ import annotations

import hashlib
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, Iterable, List, Optional, Tuple

from media_summarizer.core.models import ProcessingJob
from media_summarizer.core.models.media_artifact import (
    ArtifactGenerationLock,
    ArtifactGenerationStatus,
    ArtifactStorageRef,
    MediaArtifactRecord,
    MediaArtifactStatus,
    MediaArtifactType,
)
from media_summarizer.core.services.transcript_translation import (
    ensure_translated_transcript,
    job_source_language_hint,
    persist_detected_language,
)
from media_summarizer.utils import artifact_idempotence, media_artifacts, s3, sqs
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

ARTIFACT_GENERATION_ENABLED = os.environ.get(
    "ARTIFACT_GENERATION_ENABLED", "true"
).lower() == "true"
TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcripts"
)
SUMMARY_BUCKET = os.environ.get("SUMMARY_BUCKET", "media-summarizer-summaries")
SUMMARY_SHORT_BUCKET = os.environ.get("SUMMARY_SHORT_BUCKET", "media-summarizer-summary-short")
SUMMARY_DETAILED_BUCKET = os.environ.get("SUMMARY_DETAILED_BUCKET", "media-summarizer-summary-detailed")
QUIZ_BUCKET = os.environ.get("QUIZ_BUCKET", "media-summarizer-quiz")
NOTES_BUCKET = os.environ.get("NOTES_BUCKET", "media-summarizer-notes")
FLASHCARDS_BUCKET = os.environ.get("FLASHCARDS_BUCKET", "media-summarizer-flashcards")
ARTIFACT_GENERATOR_QUEUE = os.environ.get(
    "ARTIFACT_GENERATOR_QUEUE", "artifact-generator-queue"
)
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-nano-2026-03-17")
# LLM models per artifact type — validated by owner in task-72 benchmark:
# summary_short: gpt-5-nano-2025-08-07
# all other artifacts: gpt-5.4-nano-2026-03-17
SUMMARY_SHORT_MODEL = os.environ.get("SUMMARY_SHORT_LLM_MODEL", "gpt-5-nano-2025-08-07")
SUMMARY_DETAILED_MODEL = os.environ.get("SUMMARY_DETAILED_LLM_MODEL", OPENAI_MODEL)
NOTES_MODEL = os.environ.get("NOTES_LLM_MODEL", OPENAI_MODEL)
FLASHCARDS_MODEL = os.environ.get("FLASHCARDS_LLM_MODEL", OPENAI_MODEL)

READY_STATUSES = {
    MediaArtifactStatus.QUEUED,
    MediaArtifactStatus.GENERATING,
    MediaArtifactStatus.READY,
}
TERMINAL_PENDING_STATUSES = {
    MediaArtifactStatus.QUEUED,
    MediaArtifactStatus.GENERATING,
}
REQUESTABLE_ARTIFACT_TYPES = {
    MediaArtifactType.SUMMARY_SHORT,
    MediaArtifactType.SUMMARY_DETAILED,
    MediaArtifactType.QUIZ,
    MediaArtifactType.NOTES,
    MediaArtifactType.FLASHCARDS,
}


class ArtifactServiceError(Exception):
    pass


class ArtifactGenerationDisabledError(ArtifactServiceError):
    pass


class ArtifactTypeNotEnabledError(ArtifactServiceError):
    pass


class ArtifactTranscriptNotReadyError(ArtifactServiceError):
    pass


class ArtifactNotFoundError(ArtifactServiceError):
    pass


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _artifact_type(value: Any) -> MediaArtifactType:
    if isinstance(value, MediaArtifactType):
        return value
    return MediaArtifactType(str(value))


def normalize_artifact_parameters(value: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    def _normalize(node: Any) -> Any:
        if isinstance(node, dict):
            return {str(key): _normalize(node[key]) for key in sorted(node)}
        if isinstance(node, list):
            return [_normalize(item) for item in node]
        return node

    return _normalize(value or {})


def _stable_json(value: Dict[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def build_request_fingerprint(
    *,
    media_item_id: str,
    artifact_type: MediaArtifactType,
    parameters: Dict[str, Any],
) -> str:
    return _sha256_text(
        _stable_json(
            {
                "media_item_id": media_item_id,
                "artifact_type": artifact_type.value,
                "parameters": parameters,
            }
        )
    )


def get_generator_version(artifact_type: MediaArtifactType) -> str:
    versions = {
        MediaArtifactType.SUMMARY_SHORT: os.environ.get(
            "SUMMARY_SHORT_ARTIFACT_GENERATOR_VERSION",
            f"summary_short:{SUMMARY_SHORT_MODEL}:prompt-v1",
        ),
        MediaArtifactType.SUMMARY_DETAILED: os.environ.get(
            "SUMMARY_DETAILED_ARTIFACT_GENERATOR_VERSION",
            f"summary_detailed:{SUMMARY_DETAILED_MODEL}:prompt-v1",
        ),
        MediaArtifactType.QUIZ: os.environ.get(
            "QUIZ_ARTIFACT_GENERATOR_VERSION",
            f"quiz:{OPENAI_MODEL}:prompt-v1",
        ),
        MediaArtifactType.NOTES: os.environ.get(
            "NOTES_ARTIFACT_GENERATOR_VERSION",
            f"notes:{NOTES_MODEL}:prompt-v1",
        ),
        MediaArtifactType.FLASHCARDS: os.environ.get(
            "FLASHCARDS_ARTIFACT_GENERATOR_VERSION",
            f"flashcards:{FLASHCARDS_MODEL}:prompt-v1",
        ),
    }
    return versions[artifact_type]


def build_generation_fingerprint(
    *,
    transcript_sha256: str,
    artifact_type: MediaArtifactType,
    parameters: Dict[str, Any],
    generator_version: str,
) -> str:
    return _sha256_text(
        _stable_json(
            {
                "transcript_sha256": transcript_sha256,
                "artifact_type": artifact_type.value,
                "parameters": parameters,
                "generator_version": generator_version,
            }
        )
    )


def get_artifact_bucket(artifact_type: MediaArtifactType) -> str:
    buckets = {
        MediaArtifactType.SUMMARY_SHORT: SUMMARY_SHORT_BUCKET,
        MediaArtifactType.SUMMARY_DETAILED: SUMMARY_DETAILED_BUCKET,
        MediaArtifactType.QUIZ: QUIZ_BUCKET,
        MediaArtifactType.NOTES: NOTES_BUCKET,
        MediaArtifactType.FLASHCARDS: FLASHCARDS_BUCKET,
    }
    return buckets[artifact_type]


def get_artifact_queue(artifact_type: MediaArtifactType) -> str:
    """Return the SQS queue name for artifact generation.

    All artifact types route to the unified artifact-generator-queue (task-195).
    """
    return ARTIFACT_GENERATOR_QUEUE


def build_artifact_storage_key(
    *,
    artifact_id: str,
    artifact_type: MediaArtifactType,
) -> str:
    return f"{artifact_type.value}/{artifact_id}.json"


def _allowed_artifact_types() -> set[MediaArtifactType]:
    raw = os.environ.get("ARTIFACT_TYPES_ALLOWED", "summary_short,summary_detailed,quiz,notes,flashcards")
    allowed = set()
    for chunk in raw.split(","):
        value = chunk.strip()
        if not value:
            continue
        try:
            allowed.add(MediaArtifactType(value))
        except ValueError:
            logger.warning("Ignoring unknown artifact type in ARTIFACT_TYPES_ALLOWED: %s", value)
    return allowed or {
        MediaArtifactType.SUMMARY_SHORT,
        MediaArtifactType.SUMMARY_DETAILED,
        MediaArtifactType.QUIZ,
        MediaArtifactType.NOTES,
        MediaArtifactType.FLASHCARDS,
    }


async def _load_transcript_bytes(job: ProcessingJob) -> Tuple[str, bytes, str]:
    transcript_s3_key = (getattr(job, "transcription_s3_key", None) or "").strip()
    if not transcript_s3_key:
        raise ArtifactTranscriptNotReadyError(
            "Transcript is not available for this media item."
        )

    transcript_bytes = await s3.download_file_to_memory(
        bucket=TRANSCRIPT_BUCKET,
        key=transcript_s3_key,
    )
    if not transcript_bytes or not transcript_bytes.strip():
        raise ArtifactTranscriptNotReadyError(
            "Transcript is empty or unavailable for this media item."
        )
    return transcript_s3_key, transcript_bytes, _sha256_bytes(transcript_bytes)


class _EffectiveTranscript:
    """The transcript (possibly translated) that artifacts will be built from."""

    def __init__(
        self,
        *,
        transcript_s3_key: str,
        transcript_sha256: str,
        translation_metadata: Dict[str, Any],
    ) -> None:
        self.transcript_s3_key = transcript_s3_key
        self.transcript_sha256 = transcript_sha256
        self.translation_metadata = translation_metadata

    @property
    def target_language(self) -> Optional[str]:
        return self.translation_metadata.get("target_language")


def _with_target_language(
    parameters: Optional[Dict[str, Any]],
    effective: "_EffectiveTranscript",
) -> Dict[str, Any]:
    """Force ``parameters['language']`` to the user's target reading language.

    Downstream generators build their ``_build_*_prompt`` ``language`` instruction
    from this value, so summary/notes/flashcards/quiz are produced in the target
    language regardless of the source language (AC#6).
    """
    merged = dict(parameters or {})
    target = effective.target_language
    if target:
        merged["language"] = target
    return merged


async def _resolve_effective_transcript(
    *,
    job: ProcessingJob,
    reading_language: Optional[str],
) -> "_EffectiveTranscript":
    """Load the transcript, run the common detect+translate step, and return the
    effective transcript key + sha that artifact generation must consume.

    Persists the detected language back onto the job's ``transcription_metadata``
    (idempotent) so detection is not repeated on every artifact request.
    """
    transcript_s3_key, transcript_bytes, original_sha256 = await _load_transcript_bytes(job)
    transcript_text = transcript_bytes.decode("utf-8", errors="ignore")

    outcome = await ensure_translated_transcript(
        transcript_s3_key=transcript_s3_key,
        transcript_text=transcript_text,
        target_language=reading_language,
        source=getattr(job, "source_platform", None),
        source_language_hint=job_source_language_hint(job),
        transcript_bucket=TRANSCRIPT_BUCKET,
    )

    await persist_detected_language(job, outcome.detected_language)

    if outcome.transcript_s3_key == transcript_s3_key:
        effective_sha = original_sha256
    else:
        translated_bytes = await s3.download_file_to_memory(
            bucket=TRANSCRIPT_BUCKET,
            key=outcome.transcript_s3_key,
        )
        effective_sha = _sha256_bytes(translated_bytes)

    return _EffectiveTranscript(
        transcript_s3_key=outcome.transcript_s3_key,
        transcript_sha256=effective_sha,
        translation_metadata=outcome.metadata(),
    )


def _build_generation_lock(
    *,
    artifact_type: MediaArtifactType,
    artifact_id: str,
    parameters: Dict[str, Any],
    transcript_sha256: str,
    generation_fingerprint: str,
    generator_version: str,
) -> ArtifactGenerationLock:
    return ArtifactGenerationLock(
        generation_fingerprint=generation_fingerprint,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        parameters=parameters,
        transcript_sha256=transcript_sha256,
        generator_version=generator_version,
        status=ArtifactGenerationStatus.RESERVED,
    )


async def list_media_artifact_records(media_item_id: str) -> List[MediaArtifactRecord]:
    return await media_artifacts.safe_list_media_artifacts_by_media_item(media_item_id)


async def get_media_artifact_record(
    artifact_id: str,
) -> Optional[MediaArtifactRecord]:
    return await media_artifacts.get_media_artifact_by_id(artifact_id)


def build_status_snapshots(
    records: Iterable[MediaArtifactRecord],
) -> Dict[MediaArtifactType, MediaArtifactRecord]:
    snapshots: Dict[MediaArtifactType, MediaArtifactRecord] = {}
    for record in records:
        current = snapshots.get(record.artifact_type)
        if current is None or record.updated_at >= current.updated_at:
            snapshots[record.artifact_type] = record
    return snapshots


async def request_artifact_generation(
    *,
    media_item_id: str,
    job: ProcessingJob,
    artifact_type: Any,
    parameters: Optional[Dict[str, Any]] = None,
    reading_language: Optional[str] = None,
) -> Tuple[MediaArtifactRecord, bool]:
    if not ARTIFACT_GENERATION_ENABLED:
        raise ArtifactGenerationDisabledError("Artifact generation is disabled.")

    resolved_type = _artifact_type(artifact_type)
    if resolved_type not in _allowed_artifact_types():
        raise ArtifactTypeNotEnabledError(
            f"Artifact type '{resolved_type.value}' is not enabled."
        )
    if resolved_type not in REQUESTABLE_ARTIFACT_TYPES:
        raise ArtifactTypeNotEnabledError(
            f"Artifact type '{resolved_type.value}' is not implemented yet."
        )

    # Common detect+translate step (task-192): runs once here, before fingerprint
    # computation, so the cache/idempotence keys reflect the transcript actually
    # fed to the model and every source funnels through the same logic.
    translation = await _resolve_effective_transcript(
        job=job,
        reading_language=reading_language,
    )

    normalized_parameters = normalize_artifact_parameters(
        _with_target_language(parameters, translation)
    )
    request_fingerprint = build_request_fingerprint(
        media_item_id=media_item_id,
        artifact_type=resolved_type,
        parameters=normalized_parameters,
    )
    request_pointer = await media_artifacts.get_request_pointer(request_fingerprint)
    if request_pointer:
        pointed_artifact_id = request_pointer.get("active_artifact_id")
        if isinstance(pointed_artifact_id, str) and pointed_artifact_id:
            for attempt in range(3):
                pointed = await media_artifacts.get_media_artifact_by_id(pointed_artifact_id)
                if pointed and pointed.status in READY_STATUSES:
                    log_event(
                        logger,
                        logging.INFO,
                        "artifact.reused",
                        "Artifact request reused active request pointer",
                        artifact_id=pointed.artifact_id,
                        media_item_id=media_item_id,
                        artifact_type=pointed.artifact_type.value,
                    )
                    return pointed, True
                if pointed is not None:
                    break
                if request_pointer.get("status") != "reserved" or attempt == 2:
                    break
                await asyncio.sleep(0.1)

    existing = await media_artifacts.get_latest_media_artifact_by_request_fingerprint(
        request_fingerprint
    )
    if existing and existing.status in READY_STATUSES:
        log_event(
            logger,
            logging.INFO,
            "artifact.reused",
            "Artifact request reused latest ready artifact",
            artifact_id=existing.artifact_id,
            media_item_id=media_item_id,
            artifact_type=existing.artifact_type.value,
        )
        return existing, True

    transcript_s3_key = translation.transcript_s3_key
    transcript_sha256 = translation.transcript_sha256
    generator_version = get_generator_version(resolved_type)
    generation_fingerprint = build_generation_fingerprint(
        transcript_sha256=transcript_sha256,
        artifact_type=resolved_type,
        parameters=normalized_parameters,
        generator_version=generator_version,
    )
    current_lock = await artifact_idempotence.get_generation_lock(generation_fingerprint)
    now = _now_utc()

    record = MediaArtifactRecord(
        media_item_id=media_item_id,
        artifact_type=resolved_type,
        status=MediaArtifactStatus.QUEUED,
        parameters=normalized_parameters,
        request_fingerprint=request_fingerprint,
        generation_fingerprint=generation_fingerprint,
        generator_version=generator_version,
        transcript_s3_key=transcript_s3_key,
        transcript_sha256=transcript_sha256,
        created_at=now,
        updated_at=now,
    )

    request_pointer = None
    pointer_created = await media_artifacts.reserve_request_pointer(
        request_fingerprint=request_fingerprint,
        artifact_id=record.artifact_id,
    )
    if not pointer_created:
        request_pointer = await media_artifacts.get_request_pointer(request_fingerprint)
        pointed_artifact_id = (
            request_pointer.get("active_artifact_id") if request_pointer else None
        )
        if isinstance(pointed_artifact_id, str) and pointed_artifact_id:
            for attempt in range(3):
                pointed = await media_artifacts.get_media_artifact_by_id(pointed_artifact_id)
                if pointed is not None:
                    return pointed, True
                if request_pointer is None or request_pointer.get("status") != "reserved" or attempt == 2:
                    break
                await asyncio.sleep(0.1)
        latest = await media_artifacts.get_latest_media_artifact_by_request_fingerprint(
            request_fingerprint
        )
        if latest is not None:
            return latest, True
        raise ArtifactServiceError(
            "Artifact request is already reserved but no artifact record is available yet."
        )

    if (
        current_lock
        and current_lock.status == ArtifactGenerationStatus.READY
        and current_lock.storage is not None
    ):
        record.status = MediaArtifactStatus.READY
        record.storage = current_lock.storage
        record.reused_from_artifact_id = current_lock.artifact_id
        record.completed_at = current_lock.completed_at or now
        await media_artifacts.create_media_artifact(record)
        await media_artifacts.save_request_pointer(
            request_fingerprint=request_fingerprint,
            artifact_id=record.artifact_id,
            status="ready",
            created_at=request_pointer.get("created_at") if request_pointer else None,
        )
        log_event(
            logger,
            logging.INFO,
            "artifact.reused",
            "Artifact request reused existing generation lock",
            artifact_id=record.artifact_id,
            media_item_id=media_item_id,
            artifact_type=record.artifact_type.value,
        )
        return record, True

    reservation_created = False
    if not current_lock or current_lock.status == ArtifactGenerationStatus.FAILED:
        reservation_created = await artifact_idempotence.reserve_generation(
            _build_generation_lock(
                artifact_type=resolved_type,
                artifact_id=record.artifact_id,
                parameters=normalized_parameters,
                transcript_sha256=transcript_sha256,
                generation_fingerprint=generation_fingerprint,
                generator_version=generator_version,
            )
        )
        if not reservation_created:
            current_lock = await artifact_idempotence.get_generation_lock(
                generation_fingerprint
            )
    try:
        await media_artifacts.create_media_artifact(record)
    except Exception:
        await media_artifacts.save_request_pointer(
            request_fingerprint=request_fingerprint,
            artifact_id=record.artifact_id,
            status="failed",
            created_at=request_pointer["created_at"] if request_pointer else None,
        )
        raise

    if (
        current_lock
        and current_lock.status == ArtifactGenerationStatus.READY
        and current_lock.storage is not None
    ):
        record.status = MediaArtifactStatus.READY
        record.storage = current_lock.storage
        record.reused_from_artifact_id = current_lock.artifact_id
        record.updated_at = _now_utc()
        record.completed_at = current_lock.completed_at or record.updated_at
        await media_artifacts.update_media_artifact(record)
        pointer_created_at = None
        current_pointer = await media_artifacts.get_request_pointer(request_fingerprint)
        if current_pointer is not None:
            pointer_created_at = current_pointer.get("created_at")
        await media_artifacts.save_request_pointer(
            request_fingerprint=request_fingerprint,
            artifact_id=record.artifact_id,
            status="ready",
            created_at=pointer_created_at,
        )
        log_event(
            logger,
            logging.INFO,
            "artifact.reused",
            "Artifact request reused completed generation",
            artifact_id=record.artifact_id,
            media_item_id=media_item_id,
            artifact_type=record.artifact_type.value,
        )
        return record, True

    if reservation_created:
        message = {
            "artifact_id": record.artifact_id,
            "media_item_id": media_item_id,
            "artifact_type": resolved_type.value,
            "parameters": normalized_parameters,
            "transcript_s3_key": transcript_s3_key,
            "transcript_bucket": TRANSCRIPT_BUCKET,
            "generation_fingerprint": generation_fingerprint,
            "generator_version": generator_version,
            "source_title": getattr(job, "title", None),
            "media_title": getattr(job, "title", None),
            "media_image": getattr(job, "media_image", None),
            # Translation provenance flows into the artifact envelope so the
            # mobile UI can render the "Translated from XX" badge (task-192).
            "translation": translation.translation_metadata,
        }
        try:
            await sqs.send_message(
                queue_name=get_artifact_queue(resolved_type),
                message_body=message,
            )
            log_event(
                logger,
                logging.INFO,
                "artifact.enqueued",
                "Artifact generation enqueued",
                artifact_id=record.artifact_id,
                media_item_id=media_item_id,
                artifact_type=resolved_type.value,
                queue=get_artifact_queue(resolved_type),
            )
        except Exception as exc:
            await fail_artifact_generation(
                artifact_id=record.artifact_id,
                error_message=f"artifact_enqueue_failed: {exc}",
                error_code="INTERNAL_ERROR",
            )
            raise

    return record, False


async def mark_artifact_generating(artifact_id: str) -> MediaArtifactRecord:
    record = await media_artifacts.get_media_artifact_by_id(artifact_id)
    if not record:
        raise ArtifactNotFoundError(f"Artifact {artifact_id} not found.")
    if record.status == MediaArtifactStatus.READY:
        return record
    record.status = MediaArtifactStatus.GENERATING
    record.updated_at = _now_utc()
    record.error_code = None
    record.error_message = None
    await media_artifacts.update_media_artifact(record)
    log_event(
        logger,
        logging.INFO,
        "artifact.generating",
        "Artifact generation started",
        artifact_id=record.artifact_id,
        media_item_id=record.media_item_id,
        artifact_type=record.artifact_type.value,
    )
    return record


async def complete_artifact_generation(
    *,
    artifact_id: str,
    content: Dict[str, Any],
) -> MediaArtifactRecord:
    record = await media_artifacts.get_media_artifact_by_id(artifact_id)
    if not record:
        raise ArtifactNotFoundError(f"Artifact {artifact_id} not found.")

    payload_json = json.dumps(content, indent=2, ensure_ascii=False)
    payload_bytes = payload_json.encode("utf-8")
    storage = ArtifactStorageRef(
        bucket=get_artifact_bucket(record.artifact_type),
        key=build_artifact_storage_key(
            artifact_id=artifact_id,
            artifact_type=record.artifact_type,
        ),
        content_type="application/json",
        content_sha256=_sha256_bytes(payload_bytes),
    )
    await s3.upload_file_object(
        bucket=storage.bucket,
        key=storage.key,
        file_obj=BytesIO(payload_bytes),
        content_type=storage.content_type,
        metadata={
            "artifact-id": artifact_id,
            "artifact-type": record.artifact_type.value,
            "generation-fingerprint": record.generation_fingerprint,
        },
    )

    now = _now_utc()
    record.status = MediaArtifactStatus.READY
    record.storage = storage
    record.error_code = None
    record.error_message = None
    record.updated_at = now
    record.completed_at = now
    await media_artifacts.update_media_artifact(record)

    related = await media_artifacts.list_media_artifacts_by_generation_fingerprint(
        record.generation_fingerprint
    )
    updated_record: Optional[MediaArtifactRecord] = record
    for item in related:
        if item.artifact_id == artifact_id:
            continue
        if item.status not in TERMINAL_PENDING_STATUSES:
            continue
        item.status = MediaArtifactStatus.READY
        item.storage = storage
        item.error_code = None
        item.error_message = None
        item.updated_at = now
        item.completed_at = now
        if item.artifact_id != artifact_id:
            item.reused_from_artifact_id = artifact_id
        await media_artifacts.update_media_artifact(item)

    lock = ArtifactGenerationLock(
        generation_fingerprint=record.generation_fingerprint,
        artifact_type=record.artifact_type,
        generator_version=record.generator_version,
        transcript_sha256=record.transcript_sha256,
        parameters=record.parameters,
        status=ArtifactGenerationStatus.READY,
        artifact_id=artifact_id,
        storage=storage,
        created_at=now,
        updated_at=now,
        completed_at=now,
    )
    existing_lock = await artifact_idempotence.get_generation_lock(
        record.generation_fingerprint
    )
    if existing_lock is not None:
        lock.created_at = existing_lock.created_at
    await artifact_idempotence.save_generation_lock(lock)
    request_pointer = await media_artifacts.get_request_pointer(record.request_fingerprint)
    await media_artifacts.save_request_pointer(
        request_fingerprint=record.request_fingerprint,
        artifact_id=artifact_id,
        status="ready",
        created_at=request_pointer.get("created_at") if request_pointer else None,
    )
    log_event(
        logger,
        logging.INFO,
        "artifact.completed",
        "Artifact generation completed",
        artifact_id=artifact_id,
        media_item_id=record.media_item_id,
        artifact_type=record.artifact_type.value,
    )
    return updated_record or await media_artifacts.get_media_artifact_by_id(artifact_id)


async def fail_artifact_generation(
    *,
    artifact_id: str,
    error_message: str,
    error_code: str = "INTERNAL_ERROR",
) -> Optional[MediaArtifactRecord]:
    record = await media_artifacts.get_media_artifact_by_id(artifact_id)
    if not record:
        return None

    now = _now_utc()
    record.status = MediaArtifactStatus.FAILED
    record.error_code = error_code
    record.error_message = error_message
    record.updated_at = now
    record.completed_at = now
    await media_artifacts.update_media_artifact(record)

    related = await media_artifacts.list_media_artifacts_by_generation_fingerprint(
        record.generation_fingerprint
    )
    updated_record: Optional[MediaArtifactRecord] = record
    for item in related:
        if item.artifact_id == artifact_id:
            continue
        if item.status not in TERMINAL_PENDING_STATUSES:
            continue
        item.status = MediaArtifactStatus.FAILED
        item.error_code = error_code
        item.error_message = error_message
        item.updated_at = now
        item.completed_at = now
        await media_artifacts.update_media_artifact(item)

    lock = ArtifactGenerationLock(
        generation_fingerprint=record.generation_fingerprint,
        artifact_type=record.artifact_type,
        generator_version=record.generator_version,
        transcript_sha256=record.transcript_sha256,
        parameters=record.parameters,
        status=ArtifactGenerationStatus.FAILED,
        artifact_id=artifact_id,
        error_code=error_code,
        error_message=error_message,
        created_at=now,
        updated_at=now,
        completed_at=now,
    )
    existing_lock = await artifact_idempotence.get_generation_lock(
        record.generation_fingerprint
    )
    if existing_lock is not None:
        lock.created_at = existing_lock.created_at
    await artifact_idempotence.save_generation_lock(lock)
    request_pointer = await media_artifacts.get_request_pointer(record.request_fingerprint)
    await media_artifacts.save_request_pointer(
        request_fingerprint=record.request_fingerprint,
        artifact_id=artifact_id,
        status="failed",
        created_at=request_pointer.get("created_at") if request_pointer else None,
    )
    log_event(
        logger,
        logging.ERROR,
        "artifact.failed",
        "Artifact generation failed",
        artifact_id=artifact_id,
        media_item_id=record.media_item_id,
        artifact_type=record.artifact_type.value,
        error_code=error_code,
        detail=error_message,
    )
    return updated_record
