"""
Artifact generation: scope resolution, short-window deduplication, storage.

Both scopes go through one mechanism (task-269 decision, strategy S1): a media
artifact is a collection artifact whose ``sources`` has one element. A request
resolves the scope's sources, checks the ceilings, writes **one immutable history
entry** and enqueues **one** SQS message per artifact type. Nothing is ever
overwritten, nothing is invalidated, and no code asks "does an artifact of this
type already exist?".

Deduplication is short-window only, and it needs no lock table: the
``artifact_id`` is a hash of (user, scope, type, parameters, generator version,
source ids, current 120 s window), so a double tap computes the same id twice and
the conditional write rejects the second. At 121 s the same request is a
*regeneration*, which is exactly what the append-only model is for.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from media_summarizer.core.models import ProcessingJob
from media_summarizer.core.models.media_artifact import (
    ArtifactLlmUsage,
    ArtifactScope,
    ArtifactSource,
    ArtifactStorageRef,
    MediaArtifactRecord,
    MediaArtifactStatus,
    MediaArtifactType,
    build_scope_key,
)
from media_summarizer.core.services.transcript_translation import (
    TranslationInProgressError,
    job_source_language_hint,
    persist_detected_language,
    resolve_or_enqueue_translated_transcript,
)
from media_summarizer.utils import media_artifacts, s3, sqs
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

ARTIFACT_GENERATION_ENABLED = os.environ.get(
    "ARTIFACT_GENERATION_ENABLED", "true"
).lower() == "true"
TRANSCRIPT_BUCKET = required_env("TRANSCRIPT_BUCKET")
SUMMARY_BUCKET = required_env("SUMMARY_BUCKET")
SUMMARY_SHORT_BUCKET = required_env("SUMMARY_SHORT_BUCKET")
SUMMARY_DETAILED_BUCKET = required_env("SUMMARY_DETAILED_BUCKET")
QUIZ_BUCKET = required_env("QUIZ_BUCKET")
NOTES_BUCKET = required_env("NOTES_BUCKET")
FLASHCARDS_BUCKET = required_env("FLASHCARDS_BUCKET")
ARTIFACT_GENERATOR_QUEUE = required_env("ARTIFACT_GENERATOR_QUEUE")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-nano-2026-03-17")
# LLM models per artifact type — validated by owner in task-72 benchmark:
# summary_short: gpt-5-nano-2025-08-07
# all other artifacts: gpt-5.4-nano-2026-03-17
SUMMARY_SHORT_MODEL = os.environ.get("SUMMARY_SHORT_LLM_MODEL", "gpt-5-nano-2025-08-07")
SUMMARY_DETAILED_MODEL = os.environ.get("SUMMARY_DETAILED_LLM_MODEL", OPENAI_MODEL)
NOTES_MODEL = os.environ.get("NOTES_LLM_MODEL", OPENAI_MODEL)
FLASHCARDS_MODEL = os.environ.get("FLASHCARDS_LLM_MODEL", OPENAI_MODEL)

# The two ceilings a request must fit under. Both derive from the model's input
# window, not from pricing, which is why they are code constants and stay out of
# `pricing_config`: no tier can buy 50 sources into a 272k-token context.
# 25 sources at the measured median (4 622 tokens) is 42.7% of the window; the
# token ceiling is the guard that catches a collection of unusually long sources.
MAX_COLLECTION_SOURCES = 25
MAX_COLLECTION_CORPUS_TOKENS = 120_000
# `tiktoken` is not in the Lambda image, so the corpus is measured in UTF-8 bytes
# and converted. ±10%, which the 2.3x margin to the model's window absorbs.
BYTES_PER_TOKEN = 3.4

# Two identical requests less than this apart are the same tap, not a
# regeneration. This carries no expiry semantics: it never says an artifact stays
# valid for 120 s, only that a click is not two clicks.
DEDUP_WINDOW_SECONDS = 120
# Matches the artifact_generator Lambda's 300 s timeout, so a worker killed
# mid-generation leaves an entry another invocation can reclaim.
GENERATION_LEASE_SECONDS = 300

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
    """At least one source is still being transcribed or translated.

    Retryable as-is: the call that raised it already kicked off the missing
    translations, and nothing was written, so the history stays free of
    stillborn entries.
    """

    def __init__(
        self,
        message: str,
        *,
        pending_titles: Optional[List[str]] = None,
        pending_count: int = 0,
    ) -> None:
        super().__init__(message)
        self.pending_titles = pending_titles or []
        self.pending_count = pending_count or len(self.pending_titles)


class ArtifactScopeEmptyError(ArtifactServiceError):
    """The scope holds no usable source at all."""


class ArtifactScopeTooLargeError(ArtifactServiceError):
    """The scope exceeds a ceiling. Carries the four numbers the UI displays."""

    def __init__(
        self,
        message: str,
        *,
        source_count: int,
        max_sources: int,
        estimated_tokens: int,
        max_tokens: int,
    ) -> None:
        super().__init__(message)
        self.source_count = source_count
        self.max_sources = max_sources
        self.estimated_tokens = estimated_tokens
        self.max_tokens = max_tokens


class ArtifactNotFoundError(ArtifactServiceError):
    pass


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _artifact_type(value: Any) -> MediaArtifactType:
    if isinstance(value, MediaArtifactType):
        return value
    return MediaArtifactType(str(value))


def _artifact_scope(value: Any) -> ArtifactScope:
    if isinstance(value, ArtifactScope):
        return value
    return ArtifactScope(str(value))


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


def get_generator_version(artifact_type: MediaArtifactType) -> str:
    versions = {
        MediaArtifactType.SUMMARY_SHORT: os.environ.get(
            "SUMMARY_SHORT_ARTIFACT_GENERATOR_VERSION",
            f"summary_short:{SUMMARY_SHORT_MODEL}:prompt-v2",
        ),
        MediaArtifactType.SUMMARY_DETAILED: os.environ.get(
            "SUMMARY_DETAILED_ARTIFACT_GENERATOR_VERSION",
            f"summary_detailed:{SUMMARY_DETAILED_MODEL}:prompt-v2",
        ),
        MediaArtifactType.QUIZ: os.environ.get(
            "QUIZ_ARTIFACT_GENERATOR_VERSION",
            f"quiz:{OPENAI_MODEL}:prompt-v2",
        ),
        MediaArtifactType.NOTES: os.environ.get(
            "NOTES_ARTIFACT_GENERATOR_VERSION",
            f"notes:{NOTES_MODEL}:prompt-v2",
        ),
        MediaArtifactType.FLASHCARDS: os.environ.get(
            "FLASHCARDS_ARTIFACT_GENERATOR_VERSION",
            f"flashcards:{FLASHCARDS_MODEL}:prompt-v2",
        ),
    }
    return versions[artifact_type]


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
    return allowed or set(REQUESTABLE_ARTIFACT_TYPES)


def estimate_tokens(byte_length: int) -> int:
    return int(byte_length / BYTES_PER_TOKEN)


def build_artifact_id(
    *,
    user_id: str,
    scope: ArtifactScope,
    scope_id: str,
    artifact_type: MediaArtifactType,
    parameters: Dict[str, Any],
    generator_version: str,
    source_media_item_ids: List[str],
    window_index: int,
) -> str:
    """Deterministic id — the whole of the deduplication mechanism.

    Everything that changes the output is in the hash, so two requests collide
    only when they would produce the same artifact from the same sources within
    the same window. Two reading languages give different ``parameters``, hence
    different ids, hence two legitimate entries.
    """
    material = "|".join(
        [
            user_id,
            scope.value,
            scope_id,
            artifact_type.value,
            _stable_json(parameters),
            generator_version,
            ",".join(sorted(source_media_item_ids)),
            str(window_index),
        ]
    )
    return f"art_{_sha256_text(material)[:32]}"


def _window_index(moment: datetime) -> int:
    return int(moment.timestamp() // DEDUP_WINDOW_SECONDS)


# ---------------------------------------------------------------------------
# Scope resolution
# ---------------------------------------------------------------------------


class ResolvedSource:
    """One source ready to enter the corpus, with the bytes already measured."""

    def __init__(
        self,
        *,
        media_item_id: str,
        title: Optional[str],
        transcript_s3_key: str,
        language: Optional[str],
        byte_length: int,
        translation_metadata: Dict[str, Any],
    ) -> None:
        self.media_item_id = media_item_id
        self.title = title
        self.transcript_s3_key = transcript_s3_key
        self.language = language
        self.byte_length = byte_length
        self.translation_metadata = translation_metadata

    def snapshot(self) -> ArtifactSource:
        return ArtifactSource(
            media_item_id=self.media_item_id,
            title=self.title,
            transcript_s3_key=self.transcript_s3_key,
            language=self.language,
        )


class ScopeResolution:
    """What a scope resolved to: usable sources, exclusions, and the volume."""

    def __init__(
        self,
        *,
        sources: List[ResolvedSource],
        excluded: List[ArtifactSource],
        target_language: Optional[str],
    ) -> None:
        self.sources = sources
        self.excluded = excluded
        self.target_language = target_language

    @property
    def estimated_tokens(self) -> int:
        return estimate_tokens(sum(source.byte_length for source in self.sources))

    def snapshot(self) -> List[ArtifactSource]:
        """The immutable snapshot: what was read, then what was skipped."""
        return [source.snapshot() for source in self.sources] + self.excluded


async def _load_transcript_bytes(job: ProcessingJob) -> Tuple[str, bytes]:
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
    return transcript_s3_key, transcript_bytes


async def resolve_source(
    *,
    job: ProcessingJob,
    media_item_id: str,
    title: Optional[str],
    reading_language: Optional[str],
) -> ResolvedSource:
    """Resolve one source to the exact text the model will read.

    Reuses the per-media path unchanged (task-189/192): detect the language
    locally, reuse the cached translation in S3 when there is one, enqueue the
    translation worker otherwise. So the corpus the model sees is monolingual and
    a collection of already-read media costs nothing extra.
    """
    transcript_s3_key, transcript_bytes = await _load_transcript_bytes(job)
    transcript_text = transcript_bytes.decode("utf-8", errors="ignore")

    outcome = await resolve_or_enqueue_translated_transcript(
        transcript_s3_key=transcript_s3_key,
        transcript_text=transcript_text,
        target_language=reading_language,
        source=getattr(job, "source_platform", None),
        source_language_hint=job_source_language_hint(job),
        job_id=getattr(job, "id", None),
        transcript_bucket=TRANSCRIPT_BUCKET,
    )
    await persist_detected_language(job, outcome.detected_language)

    if outcome.transcript_s3_key == transcript_s3_key:
        effective_bytes = transcript_bytes
    else:
        effective_bytes = await s3.download_file_to_memory(
            bucket=TRANSCRIPT_BUCKET,
            key=outcome.transcript_s3_key,
        )

    metadata = outcome.metadata()
    return ResolvedSource(
        media_item_id=media_item_id,
        title=title,
        transcript_s3_key=outcome.transcript_s3_key,
        language=metadata.get("target_language") or outcome.detected_language,
        byte_length=len(effective_bytes),
        translation_metadata=metadata,
    )


async def resolve_scope_sources(
    *,
    user_id: str,
    scope: ArtifactScope,
    scope_id: str,
    reading_language: Optional[str],
) -> ScopeResolution:
    """List a scope's sources and resolve each one's effective transcript.

    For a folder the scope covers the folder **and every descendant**, matching
    ``GET /api/media?folder_id=`` and therefore the Sources tab the user is
    looking at: generating over a strict subset of what that tab shows would
    produce a ``source_count`` that contradicts the screen.

    A source still being transcribed or translated aborts the whole request with
    :class:`ArtifactTranscriptNotReadyError`; one whose transcript will never
    arrive is excluded and recorded, so a single broken media cannot lock a
    collection out forever.
    """
    from media_summarizer.core.services.durable_media_service import resolve_job_for_record

    records = await _list_scope_media_records(
        user_id=user_id, scope=scope, scope_id=scope_id
    )

    resolved: List[ResolvedSource] = []
    excluded: List[ArtifactSource] = []
    pending_titles: List[str] = []

    async def resolve_one(record: Any) -> Tuple[Any, Any]:
        media_item_id = getattr(record, "media_item_id", None) or getattr(record, "id", "")
        title = getattr(record, "title", None)
        job = await resolve_job_for_record(record)
        if job is None:
            return record, ArtifactSource(
                media_item_id=media_item_id,
                title=title,
                excluded=True,
                excluded_reason="transcript_unavailable",
            )
        try:
            return record, await resolve_source(
                job=job,
                media_item_id=media_item_id,
                title=title,
                reading_language=reading_language,
            )
        except TranslationInProgressError:
            return record, "pending"
        except ArtifactTranscriptNotReadyError:
            return record, ArtifactSource(
                media_item_id=media_item_id,
                title=title,
                excluded=True,
                excluded_reason="transcript_unavailable",
            )

    # In parallel: the API Lambda has a 30 s budget and 25 sources are ~400 kB of
    # S3 reads. Language detection is local, so nothing here calls an LLM.
    outcomes = await asyncio.gather(*(resolve_one(record) for record in records))

    for record, outcome in outcomes:
        if outcome == "pending":
            pending_titles.append(getattr(record, "title", None) or "")
            continue
        if isinstance(outcome, ArtifactSource):
            excluded.append(outcome)
            continue
        resolved.append(outcome)

    if pending_titles:
        raise ArtifactTranscriptNotReadyError(
            "Some sources are still being prepared (transcription or translation "
            "in progress). Retry in a moment.",
            pending_titles=[title for title in pending_titles if title],
            pending_count=len(pending_titles),
        )

    target_language: Optional[str] = None
    for source in resolved:
        candidate = source.translation_metadata.get("target_language")
        if candidate:
            target_language = candidate
            break

    return ScopeResolution(
        sources=resolved,
        excluded=excluded,
        target_language=target_language,
    )


async def _list_scope_media_records(
    *,
    user_id: str,
    scope: ArtifactScope,
    scope_id: str,
) -> List[Any]:
    from media_summarizer.core.services.folder_service import _get_descendant_ids
    from media_summarizer.utils import database_async
    from media_summarizer.utils import user_media as user_media_store

    if scope == ArtifactScope.MEDIA:
        record = await user_media_store.get_user_media(user_id, scope_id)
        return [record] if record is not None else []

    all_folders = await database_async.get_folders_by_user_id(user_id)
    folder_ids = [scope_id, *_get_descendant_ids(scope_id, all_folders)]

    seen: Dict[str, Any] = {}
    pages = await asyncio.gather(
        *(user_media_store.list_for_folder(user_id, folder_id) for folder_id in folder_ids)
    )
    for page in pages:
        for record in page:
            # A media filed in two sub-folders is one source, not two.
            seen.setdefault(record.media_item_id, record)
    return list(seen.values())


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


async def list_scope_artifacts(
    *,
    user_id: str,
    scope: ArtifactScope,
    scope_id: str,
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
) -> Tuple[List[MediaArtifactRecord], Optional[str]]:
    """Every entry of a scope, newest first, all types mixed.

    This single response is what replaced ``artifact_statuses``: it carries the
    history *and* the in-flight entries (``queued`` / ``generating``), so the
    mobile polls one endpoint per scope instead of one per artifact type.
    """
    return await media_artifacts.list_artifacts_by_scope(
        scope_key=build_scope_key(user_id=user_id, scope=scope, scope_id=scope_id),
        limit=limit,
        cursor=cursor,
    )


async def get_media_artifact_record(
    artifact_id: str,
) -> Optional[MediaArtifactRecord]:
    return await media_artifacts.get_media_artifact_by_id(artifact_id)


# ---------------------------------------------------------------------------
# Generation request
# ---------------------------------------------------------------------------


class ArtifactGenerationPlan:
    """Everything decided before anything is written.

    Split in two on purpose: the quota must be checked *after* the deduplication
    verdict (a repeated tap consumes nothing) and *before* the write (a denied
    request leaves no entry). Planning and committing as separate steps is what
    lets the endpoint express that order without an extra read (task-269 §10.3).
    """

    def __init__(
        self,
        *,
        existing: Optional[MediaArtifactRecord],
        record: Optional[MediaArtifactRecord],
        message: Optional[Dict[str, Any]],
    ) -> None:
        self.existing = existing
        self.record = record
        self.message = message

    @property
    def deduplicated(self) -> bool:
        return self.existing is not None


async def plan_artifact_generation(
    *,
    user_id: str,
    scope: Any,
    scope_id: str,
    artifact_type: Any,
    resolution: ScopeResolution,
    parameters: Optional[Dict[str, Any]] = None,
) -> ArtifactGenerationPlan:
    """Decide what would be written, and whether this is just the same tap again."""
    if not ARTIFACT_GENERATION_ENABLED:
        raise ArtifactGenerationDisabledError("Artifact generation is disabled.")

    resolved_scope = _artifact_scope(scope)
    resolved_type = _artifact_type(artifact_type)
    if resolved_type not in _allowed_artifact_types():
        raise ArtifactTypeNotEnabledError(
            f"Artifact type '{resolved_type.value}' is not enabled."
        )
    if resolved_type not in REQUESTABLE_ARTIFACT_TYPES:
        raise ArtifactTypeNotEnabledError(
            f"Artifact type '{resolved_type.value}' is not implemented yet."
        )

    merged_parameters = dict(parameters or {})
    if resolution.target_language:
        merged_parameters["language"] = resolution.target_language
    normalized_parameters = normalize_artifact_parameters(merged_parameters)

    generator_version = get_generator_version(resolved_type)
    source_ids = [source.media_item_id for source in resolution.sources]
    now = _now_utc()

    def artifact_id_for(window_index: int) -> str:
        return build_artifact_id(
            user_id=user_id,
            scope=resolved_scope,
            scope_id=scope_id,
            artifact_type=resolved_type,
            parameters=normalized_parameters,
            generator_version=generator_version,
            source_media_item_ids=source_ids,
            window_index=window_index,
        )

    current_window = _window_index(now)
    # The previous window is checked too: a double tap straddling a window
    # boundary would otherwise slip through a purely time-sliced key.
    previous = await media_artifacts.get_media_artifact_by_id(
        artifact_id_for(current_window - 1)
    )
    if previous is not None and (
        now - previous.created_at
    ) <= timedelta(seconds=DEDUP_WINDOW_SECONDS):
        log_event(
            logger,
            logging.INFO,
            "artifact.deduplicated",
            "Artifact request deduplicated inside the dedup window",
            artifact_id=previous.artifact_id,
            artifact_type=previous.artifact_type.value,
            scope=resolved_scope.value,
            scope_id=scope_id,
        )
        return ArtifactGenerationPlan(existing=previous, record=None, message=None)

    record = MediaArtifactRecord(
        artifact_id=artifact_id_for(current_window),
        user_id=user_id,
        scope=resolved_scope,
        scope_id=scope_id,
        scope_key=build_scope_key(
            user_id=user_id, scope=resolved_scope, scope_id=scope_id
        ),
        artifact_type=resolved_type,
        status=MediaArtifactStatus.QUEUED,
        parameters=normalized_parameters,
        generator_version=generator_version,
        source_count=len(resolution.sources),
        sources=resolution.snapshot(),
        created_at=now,
        updated_at=now,
    )

    message = {
        "artifact_id": record.artifact_id,
        "user_id": user_id,
        "scope": resolved_scope.value,
        "scope_id": scope_id,
        "artifact_type": resolved_type.value,
        "parameters": normalized_parameters,
        "generator_version": generator_version,
        # Same corpus prefix for the 5 types of one request, so OpenAI's prompt
        # cache is what shares the corpus between the 5 independent invocations —
        # no intermediate store and no coordination lock of ours (task-269 §2.6).
        "prompt_cache_key": _prompt_cache_key(
            scope=resolved_scope,
            scope_id=scope_id,
            sources=resolution.sources,
        ),
        # Keys only: not a byte of transcript travels through the queue. ~5 kB at
        # the 25-source ceiling, against SQS's 256 kB limit.
        "sources": [
            {
                "media_item_id": source.media_item_id,
                "title": source.title,
                "transcript_bucket": TRANSCRIPT_BUCKET,
                "transcript_s3_key": source.transcript_s3_key,
                "language": source.language,
            }
            for source in resolution.sources
        ],
        # Translation provenance of the first source, which is what the mobile
        # renders as the "Translated from XX" badge (task-192).
        "translation": (
            resolution.sources[0].translation_metadata if resolution.sources else {}
        ),
    }
    return ArtifactGenerationPlan(existing=None, record=record, message=message)


async def commit_artifact_generation(
    plan: ArtifactGenerationPlan,
) -> Tuple[MediaArtifactRecord, bool]:
    """Write the entry and enqueue it, or return the winner of a concurrent tap.

    ``deduplicated`` means "this was the same tap" — never "we reused an older
    artifact". The caller must not debit any counter when it is true.
    """
    if plan.existing is not None:
        return plan.existing, True
    if plan.record is None or plan.message is None:
        raise ArtifactServiceError("Artifact generation plan is empty.")

    record = plan.record
    try:
        await media_artifacts.create_media_artifact(record)
    except media_artifacts.ArtifactAlreadyExistsError:
        existing = await media_artifacts.get_media_artifact_by_id(record.artifact_id)
        if existing is None:
            raise ArtifactServiceError(
                "Artifact id was claimed concurrently but cannot be read back."
            )
        log_event(
            logger,
            logging.INFO,
            "artifact.deduplicated",
            "Concurrent identical artifact request collapsed",
            artifact_id=existing.artifact_id,
            artifact_type=existing.artifact_type.value,
            scope=existing.scope.value,
            scope_id=existing.scope_id,
        )
        return existing, True

    try:
        await sqs.send_message(
            queue_name=get_artifact_queue(record.artifact_type),
            message_body=plan.message,
        )
    except Exception as exc:
        await fail_artifact_generation(
            artifact_id=record.artifact_id,
            error_message=f"artifact_enqueue_failed: {exc}",
            error_code="INTERNAL_ERROR",
        )
        raise

    log_event(
        logger,
        logging.INFO,
        "artifact.enqueued",
        "Artifact generation enqueued",
        artifact_id=record.artifact_id,
        artifact_type=record.artifact_type.value,
        scope=record.scope.value,
        scope_id=record.scope_id,
        source_count=record.source_count,
        queue=get_artifact_queue(record.artifact_type),
    )
    return record, False


def _prompt_cache_key(
    *,
    scope: ArtifactScope,
    scope_id: str,
    sources: List[ResolvedSource],
) -> str:
    material = "|".join(
        [scope.value, scope_id, *[source.transcript_s3_key for source in sources]]
    )
    return _sha256_text(material)[:48]


def enforce_scope_ceilings(resolution: ScopeResolution) -> None:
    """Refuse rather than truncate.

    A truncated artifact would claim to cover sources whose text never reached
    the model, which makes its own snapshot a lie — and the snapshot is the thing
    that makes the history interpretable. Same reason there is no "25 most
    recent" auto-selection: that is truncation wearing a hat.
    """
    source_count = len(resolution.sources)
    estimated_tokens = resolution.estimated_tokens
    if source_count == 0:
        raise ArtifactScopeEmptyError(
            "This collection has no source with a usable transcript yet."
        )
    if source_count > MAX_COLLECTION_SOURCES or estimated_tokens > MAX_COLLECTION_CORPUS_TOKENS:
        raise ArtifactScopeTooLargeError(
            "This collection is too large to generate over. Generate on a "
            "smaller sub-collection instead.",
            source_count=source_count,
            max_sources=MAX_COLLECTION_SOURCES,
            estimated_tokens=estimated_tokens,
            max_tokens=MAX_COLLECTION_CORPUS_TOKENS,
        )


# ---------------------------------------------------------------------------
# Worker-side transitions
# ---------------------------------------------------------------------------


async def claim_artifact_generation(artifact_id: str) -> Optional[MediaArtifactRecord]:
    """Take the generation lease, or return ``None`` to stand down.

    ``None`` means the entry is already terminal or another worker owns a live
    lease — an SQS redelivery or a Lambda replay. The caller must acknowledge its
    message without calling the LLM.
    """
    claimed = await media_artifacts.claim_artifact_generation(
        artifact_id=artifact_id,
        lease_expires_at=_now_utc() + timedelta(seconds=GENERATION_LEASE_SECONDS),
    )
    if not claimed:
        return None
    record = await media_artifacts.get_media_artifact_by_id(artifact_id)
    if record is None:
        return None
    log_event(
        logger,
        logging.INFO,
        "artifact.generating",
        "Artifact generation started",
        artifact_id=record.artifact_id,
        artifact_type=record.artifact_type.value,
        scope=record.scope.value,
        scope_id=record.scope_id,
    )
    return record


async def complete_artifact_generation(
    *,
    artifact_id: str,
    content: Dict[str, Any],
    title: Optional[str] = None,
    llm_usage: Optional[ArtifactLlmUsage] = None,
) -> MediaArtifactRecord:
    """Store the content and seal the entry. It is never written again after this."""
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
            "scope": record.scope.value,
        },
    )

    now = _now_utc()
    record.status = MediaArtifactStatus.READY
    record.storage = storage
    # Copied onto the row so the history listing needs no S3 access at all —
    # that is what keeps a page of N entries at one DynamoDB query.
    if title:
        record.title = title
    if llm_usage is not None:
        record.llm_usage = llm_usage
    record.lease_expires_at = None
    record.error_code = None
    record.error_message = None
    record.updated_at = now
    record.completed_at = now
    await media_artifacts.update_media_artifact(record)

    log_event(
        logger,
        logging.INFO,
        "artifact.completed",
        "Artifact generation completed",
        artifact_id=artifact_id,
        artifact_type=record.artifact_type.value,
        scope=record.scope.value,
        scope_id=record.scope_id,
        source_count=record.source_count,
    )
    return record


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
    record.lease_expires_at = None
    record.updated_at = now
    record.completed_at = now
    await media_artifacts.update_media_artifact(record)

    log_event(
        logger,
        logging.ERROR,
        "artifact.failed",
        "Artifact generation failed",
        artifact_id=artifact_id,
        artifact_type=record.artifact_type.value,
        scope=record.scope.value,
        scope_id=record.scope_id,
        error_code=error_code,
        detail=error_message,
    )
    return record
