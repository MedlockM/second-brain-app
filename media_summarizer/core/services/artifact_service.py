"""
Artifact generation: scope resolution, reuse of what already exists, storage.

Both scopes go through one mechanism (task-269 decision, strategy S1): a media
artifact is a folder artifact whose ``sources`` has one element. A request
resolves the scope's sources, checks the ceilings, writes **one immutable history
entry** and enqueues **one** SQS message per artifact type.

One rule decides whether anything is generated at all (task-316 owner decision):
**an existing artifact is reused as soon as the set of sources behind it is
identical, and a generation only happens when that set differs.** The
``artifact_id`` is a hash of (user, scope, scope_id, type, parameters, sorted
source ids) with no time component, so finding the artifact that already answers a
request is a single ``GetItem`` with no time bound and no lock table. A media item
has exactly one source and that set never changes, so "one generation per type
per media" follows from the same rule with no special case; a folder can
legitimately produce a new entry, and only once its sources have changed.

The history stays append-only: a different source set writes a new entry next to
the older ones, and nothing is ever overwritten or invalidated. The single
exception is an entry that *failed* — it holds no artifact to reuse, so a request
for the same key reclaims it and generates again rather than being barred forever
by one transient provider error.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from media_summarizer.core.models import ProcessingJob
from media_summarizer.core.models.media_artifact import (
    DEFAULT_ARTIFACT_TYPES_ALLOWED,
    ArtifactLlmUsage,
    ArtifactScope,
    ArtifactSource,
    ArtifactStorageRef,
    MediaArtifactRecord,
    MediaArtifactStatus,
    MediaArtifactType,
    build_scope_key,
    content_scope_id_from_scope_key,
)
from media_summarizer.core.models.processing_job import JobStatus
from media_summarizer.core.models.user_media import ReviewBlurb, UserMediaStatus
from media_summarizer.core.services.transcript_translation import (
    TranslationInProgressError,
    TranslationPermanentlyFailedError,
    job_source_language_hint,
    normalize_language_tag,
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
REVIEW_BLURB_BUCKET = required_env("REVIEW_BLURB_BUCKET")
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
# token ceiling is the guard that catches a folder of unusually long sources.
MAX_FOLDER_SOURCES = 25
MAX_FOLDER_CORPUS_TOKENS = 120_000
# `tiktoken` is not in the Lambda image, so the corpus is measured in UTF-8 bytes
# and converted. ±10%, which the 2.3x margin to the model's window absorbs.
BYTES_PER_TOKEN = 3.4

# Matches the artifact_generator Lambda's 300 s timeout, so a worker killed
# mid-generation leaves an entry another invocation can reclaim.
GENERATION_LEASE_SECONDS = 300

# How long a request may sit waiting for its sources to become readable before it
# becomes a `failed` entry (task-360). One hour is far above the whole pipeline
# under load — a long podcast's transcription plus the translation of its
# transcript — so reaching it means the preparation is stuck, not slow. Bounding
# it is the point: an unbounded wait is a spinner nobody ends, which is what the
# refusal it replaces at least avoided.
AWAITING_SOURCES_TIMEOUT_SECONDS = int(
    os.environ.get("ARTIFACT_AWAITING_TIMEOUT_SECONDS", "3600")
)

REQUESTABLE_ARTIFACT_TYPES = {
    MediaArtifactType.SUMMARY_SHORT,
    MediaArtifactType.SUMMARY_DETAILED,
    MediaArtifactType.QUIZ,
    MediaArtifactType.NOTES,
    MediaArtifactType.FLASHCARDS,
}

# Types nobody can ask for. They are generated by a backend trigger only, live on
# ``ArtifactScope.MEDIA`` only, cost no quota (nothing was requested), and are
# filtered out of ``list_scope_artifacts`` — the history is the list of what the
# user asked for, and an internal artifact was never asked for. Keeping them out of
# ``REQUESTABLE_ARTIFACT_TYPES`` rather than adding a flag is what makes every
# user-facing surface exclude them by default instead of by remembering to.
INTERNAL_ARTIFACT_TYPES = {
    MediaArtifactType.REVIEW_BLURB,
}

# What the pipeline can actually produce: the union of the two sets above, i.e.
# what has a generator registered. ``plan_artifact_generation`` gates on this, while
# ``ArtifactCreateRequest`` rejects ``INTERNAL_ARTIFACT_TYPES`` outright — a request
# is refused before the quota is even looked at.
GENERATABLE_ARTIFACT_TYPES = REQUESTABLE_ARTIFACT_TYPES | INTERNAL_ARTIFACT_TYPES


# Why a source is in the snapshot without having been read. Both are recorded
# rather than dropped: the snapshot is what makes an artifact interpretable, and
# "13 of 15 sources" needs the two missing ones to say what happened to them.
#: No transcript, and none is coming: the ingestion failed, was cancelled, or
#: finished without producing readable text. Deliberately not the same fact as a
#: transcription still running — that one is a wait, and conflating the two is
#: what used to answer "nothing to generate" while the pipeline was working
#: (task-360).
EXCLUDED_REASON_TRANSCRIPT_UNAVAILABLE = "transcript_unavailable"
#: A transcript exists, but the translation into the reading language was refused
#: by the provider for good, so the text the corpus wanted will never exist.
EXCLUDED_REASON_TRANSLATION_FAILED = "translation_failed"

# The two preparations a request can be waiting on, recorded on the snapshot line
# of the source it is waiting for. Which one it is decides nothing in the code —
# both resume through the same path — but it is what makes a waiting entry
# readable in the table and in a log.
PREPARATION_TRANSCRIPTION = "transcription"
PREPARATION_TRANSLATION = "translation"

# Pipeline stages that mean "the text is coming". Compared by value, never by
# membership of the enum: ``JobStatus`` mixes in ``str`` but keeps ``Enum``'s
# identity hash, so ``JobStatus.PENDING in {"pending"}`` is False.
_JOB_STATUSES_IN_PREPARATION = frozenset(
    {
        JobStatus.PENDING.value,
        JobStatus.EXTRACTING.value,
        JobStatus.TRANSCRIBING.value,
        JobStatus.SUMMARIZING.value,
    }
)
#: Same question asked of the library row, for the window where no job answers for
#: the content yet (the ledger is written before the job, and a job is allowed to
#: expire while the library row stays).
_LIBRARY_STATUSES_IN_PREPARATION = frozenset(
    {UserMediaStatus.PENDING.value, UserMediaStatus.PROCESSING.value}
)

#: ``error_code`` of an entry whose wait was ended rather than served. All three
#: are terminal and actionable: the tile shows the failed state task-328 defined,
#: and asking again starts a fresh generation over whatever is readable by then.
ERROR_CODE_PREPARATION_TIMEOUT = "sources_preparation_timeout"
ERROR_CODE_PREPARATION_FAILED = "sources_preparation_failed"
ERROR_CODE_SOURCES_CHANGED = "sources_changed"


class ArtifactServiceError(Exception):
    pass


class ArtifactGenerationDisabledError(ArtifactServiceError):
    pass


class ArtifactTypeNotEnabledError(ArtifactServiceError):
    pass


class ArtifactTranscriptNotReadyError(ArtifactServiceError):
    """At least one source is still being transcribed or translated.

    **Never reaches a user request** since task-360: a requested generation is
    deferred into a waiting entry instead of refused. What is left is the internal
    path — ``review_blurb_service`` and ``digest_service`` generate from a backend
    trigger, have no tile to spin and no one to notify, so for them "not ready" is
    "give up for this run" and they catch this. Nothing was written when it is
    raised, so the history stays free of stillborn entries.
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


class ArtifactTranslationFailedError(ArtifactServiceError):
    """Every source of the scope was dropped for a translation that will not come.

    The counterpart of :class:`ArtifactTranscriptNotReadyError`, and the reason
    the two cannot share a code: this one is not retryable, and a client told to
    "retry in a moment" retries forever (task-327). It reaches the client as its
    own ``error_code`` so the UI can state a failure instead of a wait.
    """

    def __init__(
        self,
        message: str,
        *,
        failed_titles: Optional[List[str]] = None,
        failed_count: int = 0,
    ) -> None:
        super().__init__(message)
        self.failed_titles = failed_titles or []
        self.failed_count = failed_count or len(self.failed_titles)


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
    """The canonical form of a request's parameters, on the way in *and* back out.

    Idempotent, and total over what DynamoDB hands back: a number stored here
    returns as a ``Decimal``, which ``_stable_json`` cannot serialise. Converting it
    is what lets a deferred request recompute its own id from the stored entry and
    land on the same hash (task-360).
    """

    def _normalize(node: Any) -> Any:
        if isinstance(node, dict):
            return {str(key): _normalize(node[key]) for key in sorted(node)}
        if isinstance(node, list):
            return [_normalize(item) for item in node]
        if isinstance(node, Decimal):
            as_int = int(node)
            return as_int if node == as_int else float(node)
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
            f"summary_short:{SUMMARY_SHORT_MODEL}:prompt-v4",
        ),
        MediaArtifactType.SUMMARY_DETAILED: os.environ.get(
            "SUMMARY_DETAILED_ARTIFACT_GENERATOR_VERSION",
            f"summary_detailed:{SUMMARY_DETAILED_MODEL}:prompt-v4",
        ),
        MediaArtifactType.QUIZ: os.environ.get(
            "QUIZ_ARTIFACT_GENERATOR_VERSION",
            f"quiz:{OPENAI_MODEL}:prompt-v4",
        ),
        MediaArtifactType.NOTES: os.environ.get(
            "NOTES_ARTIFACT_GENERATOR_VERSION",
            f"notes:{NOTES_MODEL}:prompt-v4",
        ),
        MediaArtifactType.FLASHCARDS: os.environ.get(
            "FLASHCARDS_ARTIFACT_GENERATOR_VERSION",
            f"flashcards:{FLASHCARDS_MODEL}:prompt-v4",
        ),
        # v3: v1's prose paragraph was unreadable on the triage card, and v2's
        # structured card asked for bullets of up to 110 characters when the card
        # can show ~65 -- half of them came back clipped mid-word. v3 states the
        # lengths the card can actually render and drops the audience line, which
        # the owner found told them nothing the hook did not. Note that a bump
        # regenerates nothing on its own: `build_artifact_id` deliberately excludes
        # the generator version, so old blurbs have to be purged explicitly.
        MediaArtifactType.REVIEW_BLURB: os.environ.get(
            "REVIEW_BLURB_ARTIFACT_GENERATOR_VERSION",
            f"review_blurb:{OPENAI_MODEL}:prompt-v3",
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
        MediaArtifactType.REVIEW_BLURB: REVIEW_BLURB_BUCKET,
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
    raw = os.environ.get("ARTIFACT_TYPES_ALLOWED", DEFAULT_ARTIFACT_TYPES_ALLOWED)
    allowed = set()
    for chunk in raw.split(","):
        value = chunk.strip()
        if not value:
            continue
        try:
            allowed.add(MediaArtifactType(value))
        except ValueError:
            logger.warning("Ignoring unknown artifact type in ARTIFACT_TYPES_ALLOWED: %s", value)
    return allowed or set(GENERATABLE_ARTIFACT_TYPES)


def estimate_tokens(byte_length: int) -> int:
    return int(byte_length / BYTES_PER_TOKEN)


def build_artifact_id(
    *,
    user_id: str,
    scope: ArtifactScope,
    scope_id: str,
    artifact_type: MediaArtifactType,
    parameters: Dict[str, Any],
    source_media_item_ids: List[str],
) -> str:
    """Deterministic id — the whole of the reuse mechanism.

    The key is **what the user asked for**: owner, scope, artifact type,
    parameters, and the sorted set of sources behind it. Two requests collide
    exactly when an existing artifact already answers the second one, and that
    collision is what makes reuse a single ``GetItem``.

    Deliberately *not* in the hash:

    - **Time.** There is no window and no expiry. The same request an hour or a
      month later resolves to the same id, which is what "generate once per media"
      means concretely.
    - **``generator_version``.** It is recorded on the entry for traceability, but
      keying on it would hand out one fresh generation per prompt bump — the exact
      thing the owner's decision rules out. The corollary is deliberate: bumping a
      prompt does **not** invalidate anything already generated.

    ``parameters`` carries the reading language, so two reading languages are two
    different ids and therefore two legitimate entries. The decision is about
    regenerating, not about translating.
    """
    material = "|".join(
        [
            user_id,
            scope.value,
            scope_id,
            artifact_type.value,
            _stable_json(parameters),
            ",".join(sorted(source_media_item_ids)),
        ]
    )
    return f"art_{_sha256_text(material)[:32]}"


# ---------------------------------------------------------------------------
# Scope resolution
# ---------------------------------------------------------------------------


class ResolvedSource:
    """One source ready to enter the corpus, with the bytes already measured."""

    def __init__(
        self,
        *,
        media_item_id: str,
        content_id: str,
        title: Optional[str],
        transcript_s3_key: str,
        language: Optional[str],
        byte_length: int,
        translation_metadata: Dict[str, Any],
        published: Optional[str] = None,
        captured: Optional[str] = None,
    ) -> None:
        self.media_item_id = media_item_id
        self.content_id = content_id
        self.title = title
        self.transcript_s3_key = transcript_s3_key
        self.language = language
        self.byte_length = byte_length
        self.translation_metadata = translation_metadata
        #: ``YYYY-MM-DD`` publication date, when the pipeline resolved a real one.
        #: Only the podcast path does today, so it is usually None.
        self.published = published
        #: ``YYYY-MM-DD`` day the text entered the library. Always known, and the
        #: date a scraped bulletin's "today" actually refers to. Both go in the
        #: corpus header so the model can anchor point-in-time facts instead of
        #: freezing "today" into a permanent artifact (task-316 §2.7).
        self.captured = captured

    def snapshot(self) -> ArtifactSource:
        return ArtifactSource(
            media_item_id=self.media_item_id,
            title=self.title,
            transcript_s3_key=self.transcript_s3_key,
            language=self.language,
        )


class PendingSource:
    """One source whose text is coming but is not there yet.

    Carries the same two ids as a resolved source, because both are needed and for
    different things: ``content_id`` (the deduplicated ``media_key``) enters the
    ``artifact_id`` hash, so a waiting entry keys on the sources it *expects*;
    ``media_item_id`` is the library row a completion event resolves to, so a
    waiting entry can be matched against the media that just became readable.
    """

    def __init__(
        self,
        *,
        media_item_id: str,
        content_id: str,
        title: Optional[str],
        preparation: str,
    ) -> None:
        self.media_item_id = media_item_id
        self.content_id = content_id
        self.title = title
        self.preparation = preparation

    def snapshot(self) -> ArtifactSource:
        return ArtifactSource(
            media_item_id=self.media_item_id,
            title=self.title,
            preparation=self.preparation,
        )


class ScopeResolution:
    """What a scope resolved to: usable sources, exclusions, and the volume.

    ``pending`` is the third outcome and the whole of task-360: a source being
    transcribed or translated is neither readable nor lost, so the request is
    honoured over a source set that includes it and starts once it lands. It used
    to abort the request with a refusal the user had to come back and retry.
    """

    def __init__(
        self,
        *,
        sources: List[ResolvedSource],
        excluded: List[ArtifactSource],
        pending: List[PendingSource],
        target_language: Optional[str],
    ) -> None:
        self.sources = sources
        self.excluded = excluded
        self.pending = pending
        self.target_language = target_language

    @property
    def estimated_tokens(self) -> int:
        return estimate_tokens(sum(source.byte_length for source in self.sources))

    @property
    def is_awaiting(self) -> bool:
        """True when at least one source's text is still being prepared."""
        return bool(self.pending)

    @property
    def expected_source_ids(self) -> List[str]:
        """The content ids the finished artifact will cover: read *and* awaited.

        This is what ``artifact_id`` is keyed on, which is what makes a deferred
        request and the generation that follows one single entry: the id computed
        while a source is still being transcribed is the id the completed
        resolution computes once it is readable.
        """
        return [source.content_id for source in self.sources] + [
            source.content_id for source in self.pending
        ]

    def snapshot(self) -> List[ArtifactSource]:
        """The immutable snapshot: what was read, what is awaited, what was skipped."""
        return (
            [source.snapshot() for source in self.sources]
            + [source.snapshot() for source in self.pending]
            + self.excluded
        )


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


def _iso_date(value: Any) -> Optional[str]:
    """``YYYY-MM-DD`` from a datetime or a Unix timestamp, or None.

    Only the date survives: the corpus header exists to let the model anchor a
    point-in-time fact to a day, and an hour would be noise the model has to read
    on every source.
    """
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, (int, float)) and value > 0:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).date().isoformat()
    return None


async def resolve_source(
    *,
    job: ProcessingJob,
    media_item_id: str,
    content_id: str,
    title: Optional[str],
    reading_language: Optional[str],
    captured: Optional[str] = None,
) -> ResolvedSource:
    """Resolve one source to the exact text the model will read.

    Reuses the per-media path unchanged (task-189/192): detect the language
    locally, reuse the cached translation in S3 when there is one, enqueue the
    translation worker otherwise. So the corpus the model sees is monolingual and
    a folder of already-read media costs nothing extra.

    ``captured`` comes from the caller because it lives on the durable library row
    while the publication date lives on the job, and the job is what this function
    already holds.
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
        content_id=content_id,
        title=title,
        transcript_s3_key=outcome.transcript_s3_key,
        language=metadata.get("target_language") or outcome.detected_language,
        byte_length=len(effective_bytes),
        translation_metadata=metadata,
        published=_iso_date(getattr(job, "media_date_published", None)),
        captured=captured,
    )


def _is_still_being_ingested(record: Any, job: Optional[ProcessingJob]) -> bool:
    """Whether this media's text is on its way, as opposed to never coming.

    The distinction ``EXCLUDED_REASON_TRANSCRIPT_UNAVAILABLE`` used to swallow.
    The job is the precise answer when there is one; the library row's own coarse
    status covers the window where no job answers for the content — the durable
    row is written before the job, and a job is allowed to expire under a row that
    stays.
    """
    if job is not None:
        job_status = getattr(job, "status", None)
        return str(getattr(job_status, "value", job_status) or "") in (
            _JOB_STATUSES_IN_PREPARATION
        )
    library_status = getattr(record, "processing_status", None)
    return str(getattr(library_status, "value", library_status) or "") in (
        _LIBRARY_STATUSES_IN_PREPARATION
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

    Each source lands in exactly one of three places, and the three are never
    conflated (task-360):

    - **read** — its effective transcript exists and was measured;
    - **pending** — its text is coming: the ingestion is still running, or the
      translation into the reading language is queued (this call is what reserved
      and dispatched it). The request is honoured over it and waits;
    - **excluded** — its text will never come: the ingestion failed or produced
      nothing readable, or the provider refused the translation for good
      (task-327). Recorded in the snapshot rather than dropped, so one broken
      media cannot lock a folder out and the artifact stays honest about what
      it could not read.

    ``target_language`` is derived from the *reading language*, not from a source
    that happened to resolve. It is the same value either way — every translation
    outcome reports the normalized target it was asked for — and deriving it here
    is what makes it knowable before any source is readable, hence what makes a
    waiting entry's ``artifact_id`` equal to the one the finished resolution
    computes.
    """
    from media_summarizer.core.services.durable_media_service import resolve_job_for_record

    records = await _list_scope_media_records(
        user_id=user_id, scope=scope, scope_id=scope_id
    )

    resolved: List[ResolvedSource] = []
    excluded: List[ArtifactSource] = []
    pending: List[PendingSource] = []

    async def resolve_one(record: Any) -> Any:
        media_item_id = getattr(record, "media_item_id", None) or getattr(record, "id", "")
        content_id = getattr(record, "media_key", None) or media_item_id
        title = getattr(record, "title", None)

        def _pending(preparation: str) -> PendingSource:
            return PendingSource(
                media_item_id=media_item_id,
                content_id=content_id,
                title=title,
                preparation=preparation,
            )

        def _excluded(reason: str) -> ArtifactSource:
            return ArtifactSource(
                media_item_id=media_item_id,
                title=title,
                excluded=True,
                excluded_reason=reason,
            )

        job = await resolve_job_for_record(record)
        if job is None:
            if _is_still_being_ingested(record, job):
                return _pending(PREPARATION_TRANSCRIPTION)
            return _excluded(EXCLUDED_REASON_TRANSCRIPT_UNAVAILABLE)
        try:
            return await resolve_source(
                job=job,
                media_item_id=media_item_id,
                content_id=content_id,
                title=title,
                reading_language=reading_language,
                captured=_iso_date(getattr(record, "saved_at", None)),
            )
        except TranslationInProgressError:
            return _pending(PREPARATION_TRANSLATION)
        except TranslationPermanentlyFailedError:
            return _excluded(EXCLUDED_REASON_TRANSLATION_FAILED)
        except ArtifactTranscriptNotReadyError:
            # No transcript behind the job yet. Whether that is a wait or a dead
            # end is the job's own status, never the absence of the file.
            if _is_still_being_ingested(record, job):
                return _pending(PREPARATION_TRANSCRIPTION)
            return _excluded(EXCLUDED_REASON_TRANSCRIPT_UNAVAILABLE)

    # In parallel: the API Lambda has a 30 s budget and 25 sources are ~400 kB of
    # S3 reads. Language detection is local, so nothing here calls an LLM.
    outcomes = await asyncio.gather(*(resolve_one(record) for record in records))

    for outcome in outcomes:
        if isinstance(outcome, PendingSource):
            pending.append(outcome)
        elif isinstance(outcome, ArtifactSource):
            excluded.append(outcome)
        else:
            resolved.append(outcome)

    return ScopeResolution(
        sources=resolved,
        excluded=excluded,
        pending=pending,
        target_language=normalize_language_tag(reading_language),
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
            # Several saves may point at one content item. A folder reads
            # that transcript once, regardless of how many rows reference it.
            seen.setdefault(record.media_key, record)
    return list(seen.values())


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


async def list_scope_artifacts(
    *,
    user_id: str,
    scope: ArtifactScope,
    scope_id: str,
    content_scope_id: Optional[str] = None,
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
) -> Tuple[List[MediaArtifactRecord], Optional[str]]:
    """Every *requestable* entry of a scope, newest first, all types mixed.

    This single response is what replaced ``artifact_statuses``: it carries the
    history *and* the in-flight entries (``queued`` / ``generating``), so the
    mobile polls one endpoint per scope instead of one per artifact type.

    Internal types are dropped: the history is the list of what the user asked
    for, and the mobile row falls back to the raw ``artifact_type`` string when it
    does not know a type — leaking ``review_blurb`` here would render a row
    literally labelled "review_blurb" next to the five real ones.

    The filter runs on the page, not in the query, so a page may come back shorter
    than ``limit`` while still handing out a cursor. The mobile already treats
    ``limit`` as a ceiling and paginates on the cursor, and at one internal entry
    per media the difference is at most one row per page.

    It is also where a wait that ran out is ended (task-360). Doing it on read is
    what makes the deadline felt at the only moment it matters — someone is looking
    at the tile — instead of at the next nightly pass.
    """
    records, next_cursor = await media_artifacts.list_artifacts_by_scope(
        scope_key=build_scope_key(
            user_id=user_id,
            scope=scope,
            scope_id=content_scope_id or scope_id,
        ),
        limit=limit,
        cursor=cursor,
    )
    visible = [
        record
        for record in records
        if record.artifact_type not in INTERNAL_ARTIFACT_TYPES
    ]
    return await end_overdue_waits(visible), next_cursor


async def end_overdue_waits(
    records: List[MediaArtifactRecord],
) -> List[MediaArtifactRecord]:
    """Fail the entries whose wait for their sources ran out, in place.

    Two-step on purpose. ``scope-index`` projects ``created_at`` but not
    ``awaiting_expires_at``, and the two differ for a reclaimed entry — it keeps its
    original position in the history while its deadline restarts — so the projected
    date can only *rule out* an expiry, never confirm one. Ruling out is enough to
    make the common poll free: a wait under way costs no read here, and only a
    ``queued`` entry older than the timeout is fetched to be judged on its real
    deadline.

    Never fatal: a listing that cannot end a wait still shows the history.
    """
    now = _now_utc()
    cutoff = now - timedelta(seconds=AWAITING_SOURCES_TIMEOUT_SECONDS)
    suspects = [
        index
        for index, record in enumerate(records)
        if record.status == MediaArtifactStatus.QUEUED and record.created_at <= cutoff
    ]
    if not suspects:
        return records

    updated = list(records)
    for index in suspects:
        artifact_id = updated[index].artifact_id
        try:
            full = await media_artifacts.get_media_artifact_by_id(artifact_id)
            if full is None or not _is_awaiting_overdue(full, now=now):
                continue
            if not await media_artifacts.fail_awaiting_artifact(
                artifact_id=artifact_id,
                error_code=ERROR_CODE_PREPARATION_TIMEOUT,
                error_message=(
                    "The sources of this generation were still being prepared "
                    "when the request expired."
                ),
            ):
                continue
        except Exception as exc:  # noqa: BLE001 - a listing must still answer
            logger.warning(
                "Could not end the overdue wait of artifact %s: %s", artifact_id, exc
            )
            continue
        log_event(
            logger,
            logging.WARNING,
            "artifact.wait_expired",
            "Artifact wait ended: its sources were still not readable",
            artifact_id=artifact_id,
            artifact_type=updated[index].artifact_type.value,
            timeout_seconds=AWAITING_SOURCES_TIMEOUT_SECONDS,
        )
        updated[index] = updated[index].model_copy(
            update={
                "status": MediaArtifactStatus.FAILED,
                "error_code": ERROR_CODE_PREPARATION_TIMEOUT,
                "awaiting_expires_at": None,
                "completed_at": now,
                "updated_at": now,
            }
        )
    return updated


async def latest_internal_artifact_status(
    *,
    user_id: str,
    content_scope_id: str,
) -> Optional[MediaArtifactStatus]:
    """Status of the newest internal entry of a media scope, or ``None`` if it has none.

    The counterpart of ``list_scope_artifacts`` and the reason its filter can stay
    exactly as it is: the media detail response needs to know how the internal
    ``review_blurb`` generation went (task-363), and that question is answered here
    instead of by widening what the AI tab is served. Nothing about the history
    listing changes — a row literally labelled "review_blurb" next to the five real
    ones is still what the filter exists to prevent.

    ``content_scope_id`` is the ``media_key``, not the ``media_item_id``: internal
    entries are written under the content identity (see
    ``review_blurb_service.trigger_review_blurb_generation``), so that is the scope
    key they are indexed by.

    Read without a ``limit`` on purpose: a media scope holds at most one entry per
    type, so the whole scope is one query, and a page-bounded read could hand back
    a first page of user artifacts with the internal entry left on the next one.
    """
    records, _ = await media_artifacts.list_artifacts_by_scope(
        scope_key=build_scope_key(
            user_id=user_id,
            scope=ArtifactScope.MEDIA,
            scope_id=content_scope_id,
        ),
    )
    # Newest first, so the first internal entry seen is the current one.
    for record in records:
        if record.artifact_type in INTERNAL_ARTIFACT_TYPES:
            return record.status
    return None


async def get_media_artifact_record(
    artifact_id: str,
) -> Optional[MediaArtifactRecord]:
    return await media_artifacts.get_media_artifact_by_id(artifact_id)


# ---------------------------------------------------------------------------
# Generation request
# ---------------------------------------------------------------------------


class ArtifactGenerationOutcome(str, Enum):
    """What a committed request actually did. Four cases, never conflated.

    ``REUSED`` and ``COLLAPSED`` both mean "no generation was started, and no
    counter moves", but they are not the same fact and the caller must be able to
    tell them apart: one is an artifact that already existed over the same
    sources, the other is the second of two taps racing on the same write.
    """

    #: A new entry was written and enqueued.
    CREATED = "created"
    #: A previously failed entry for the same key was reclaimed and re-enqueued.
    RETRIED = "retried"
    #: An artifact already covering these sources answered the request.
    REUSED = "reused"
    #: A concurrent identical request won the conditional write; this one lost.
    COLLAPSED = "collapsed"


class ArtifactGenerationPlan:
    """Everything decided before anything is written.

    Split in two on purpose: the quota must be checked *after* the reuse verdict
    (a request answered by an existing artifact consumes nothing) and *before* the
    write (a denied request leaves no entry). Planning and committing as separate
    steps is what lets the endpoint express that order without an extra read
    (task-269 §10.3).
    """

    def __init__(
        self,
        *,
        reused: Optional[MediaArtifactRecord],
        record: Optional[MediaArtifactRecord],
        message: Optional[Dict[str, Any]],
        reclaims_failed: bool = False,
        awaits_sources: bool = False,
    ) -> None:
        self.reused = reused
        self.record = record
        self.message = message
        #: ``record`` carries the id of a failed entry to overwrite in place,
        #: rather than an id nothing is stored under yet.
        self.reclaims_failed = reclaims_failed
        #: The entry is written but **not** enqueued: at least one source is still
        #: being prepared, and a completion event resumes it (task-360). The debit
        #: happens here all the same — the request was accepted, and the resume
        #: never charges anything, which is what keeps one deferred generation to
        #: one debit.
        self.awaits_sources = awaits_sources

    @property
    def reuses_existing(self) -> bool:
        """True when an existing artifact answers the request, so nothing runs."""
        return self.reused is not None


async def plan_artifact_generation(
    *,
    user_id: str,
    scope: Any,
    scope_id: str,
    content_scope_id: Optional[str] = None,
    artifact_type: Any,
    resolution: ScopeResolution,
    parameters: Optional[Dict[str, Any]] = None,
) -> ArtifactGenerationPlan:
    """Decide whether an artifact already answers this request, or what to write.

    The lookup has **no time bound**: the id is derived from the sources alone, so
    an entry found here is an artifact generated over exactly these sources,
    whenever that happened. Reusing it is the answer — no generation, no debit.
    Only a *failed* entry is not an answer, and it is reclaimed instead.

    A resolution that still has sources in preparation plans the same entry under
    the same id — the id hashes the sources the artifact *will* read, not the ones
    already readable — and simply leaves it un-enqueued (task-360).
    """
    if not ARTIFACT_GENERATION_ENABLED:
        raise ArtifactGenerationDisabledError("Artifact generation is disabled.")

    resolved_scope = _artifact_scope(scope)
    resolved_type = _artifact_type(artifact_type)
    if resolved_type not in _allowed_artifact_types():
        raise ArtifactTypeNotEnabledError(
            f"Artifact type '{resolved_type.value}' is not enabled."
        )
    if resolved_type not in GENERATABLE_ARTIFACT_TYPES:
        raise ArtifactTypeNotEnabledError(
            f"Artifact type '{resolved_type.value}' is not implemented yet."
        )
    # An internal type has no user-facing entry point, so the only thing that can
    # aim it at a folder is a backend caller getting its scope wrong. Refusing
    # here rather than trusting the caller keeps the invariant next to the rule it
    # protects: a folder artifact would land in a listing that filters this type
    # out, i.e. it would be generated, billed, and unreadable.
    if resolved_type in INTERNAL_ARTIFACT_TYPES and resolved_scope != ArtifactScope.MEDIA:
        raise ArtifactTypeNotEnabledError(
            f"Artifact type '{resolved_type.value}' is internal and only exists on "
            f"the media scope, not on '{resolved_scope.value}'."
        )
    # Deferring only makes sense for a request someone is waiting on. An internal
    # type is triggered *by* the end of a preparation, so a waiting entry there
    # would be a background job scheduling its own retry through the artifact
    # table — and it has no tile to spin, no user to inform. Its callers already
    # catch this error and give up for this run.
    if resolution.is_awaiting and resolved_type in INTERNAL_ARTIFACT_TYPES:
        raise ArtifactTranscriptNotReadyError(
            f"Artifact type '{resolved_type.value}' is internal and is not "
            "deferred while its sources are being prepared.",
            pending_titles=[source.title for source in resolution.pending if source.title],
            pending_count=len(resolution.pending),
        )

    merged_parameters = dict(parameters or {})
    if resolution.target_language:
        merged_parameters["language"] = resolution.target_language
    normalized_parameters = normalize_artifact_parameters(merged_parameters)

    generator_version = get_generator_version(resolved_type)
    effective_scope_id = content_scope_id or scope_id
    # Sources still in preparation are hashed in like readable ones: they are part
    # of what this artifact will have read, and leaving them out would give the
    # deferred request one id and the generation that follows another — two
    # entries, two debits (task-360).
    source_ids = resolution.expected_source_ids
    now = _now_utc()

    artifact_id = build_artifact_id(
        user_id=user_id,
        scope=resolved_scope,
        scope_id=effective_scope_id,
        artifact_type=resolved_type,
        parameters=normalized_parameters,
        source_media_item_ids=source_ids,
    )

    existing = await media_artifacts.get_media_artifact_by_id(artifact_id)
    if existing is not None and _is_awaiting_overdue(existing, now=now):
        # The wait behind this id ran out and nobody has ended it yet (the sweep
        # runs on read, and this request may be the first read since). End it here
        # so the request in hand starts a fresh wait instead of being answered by a
        # dead one.
        if await media_artifacts.fail_awaiting_artifact(
            artifact_id=existing.artifact_id,
            error_code=ERROR_CODE_PREPARATION_TIMEOUT,
            error_message=(
                "The sources of this generation were still being prepared when the "
                "request expired."
            ),
        ):
            existing = await media_artifacts.get_media_artifact_by_id(artifact_id)
    if existing is not None and existing.status != MediaArtifactStatus.FAILED:
        log_event(
            logger,
            logging.INFO,
            "artifact.reused",
            "Existing artifact reused: the sources behind it are unchanged",
            artifact_id=existing.artifact_id,
            artifact_type=existing.artifact_type.value,
            artifact_status=existing.status.value,
            scope=resolved_scope.value,
            scope_id=scope_id,
            source_count=existing.source_count,
        )
        return ArtifactGenerationPlan(reused=existing, record=None, message=None)

    record = MediaArtifactRecord(
        artifact_id=artifact_id,
        user_id=user_id,
        scope=resolved_scope,
        scope_id=scope_id,
        scope_key=build_scope_key(
            user_id=user_id, scope=resolved_scope, scope_id=effective_scope_id
        ),
        artifact_type=resolved_type,
        status=MediaArtifactStatus.QUEUED,
        parameters=normalized_parameters,
        # Recorded, never keyed on: this is what says which prompt produced which
        # artifact, and a retry below stamps the version that actually reran.
        generator_version=generator_version,
        source_count=len(source_ids),
        sources=resolution.snapshot(),
        # A reclaimed entry keeps its original position in the history: the GSI
        # sorts on `created_at`, and a retry is the same generation attempted
        # again, not a later one.
        created_at=existing.created_at if existing is not None else now,
        updated_at=now,
        # The deadline is stored rather than derived from `created_at`, which a
        # reclaimed entry inherits from the attempt before: a retried request would
        # otherwise be born already expired.
        awaiting_expires_at=(
            now + timedelta(seconds=AWAITING_SOURCES_TIMEOUT_SECONDS)
            if resolution.is_awaiting
            else None
        ),
    )

    if resolution.is_awaiting:
        log_event(
            logger,
            logging.INFO,
            "artifact.awaiting_sources",
            "Artifact request accepted while its sources are still being prepared",
            artifact_id=record.artifact_id,
            artifact_type=resolved_type.value,
            scope=resolved_scope.value,
            scope_id=scope_id,
            source_count=record.source_count,
            pending_count=len(resolution.pending),
            preparations=sorted(
                {source.preparation for source in resolution.pending}
            ),
            awaiting_expires_at=record.awaiting_expires_at.isoformat()
            if record.awaiting_expires_at
            else None,
        )
        return ArtifactGenerationPlan(
            reused=None,
            record=record,
            # No message: a waiting entry is not enqueued, and the message the
            # generation eventually needs cannot be built yet — it carries the
            # transcript keys that do not exist.
            message=None,
            reclaims_failed=existing is not None,
            awaits_sources=True,
        )

    return ArtifactGenerationPlan(
        reused=None,
        record=record,
        message=build_generation_message(record=record, resolution=resolution),
        reclaims_failed=existing is not None,
    )


def _is_awaiting_overdue(
    record: MediaArtifactRecord,
    *,
    now: Optional[datetime] = None,
) -> bool:
    """True when this entry is waiting for sources and its deadline has passed."""
    if record.status != MediaArtifactStatus.QUEUED or record.awaiting_expires_at is None:
        return False
    return record.awaiting_expires_at <= (now or _now_utc())


def build_generation_message(
    *,
    record: MediaArtifactRecord,
    resolution: ScopeResolution,
) -> Dict[str, Any]:
    """The SQS payload of one generation.

    Built from the record plus a resolution whose sources are all readable, which
    is what lets a deferred request produce it at resume time from the very same
    code as an immediate one — the entry says what to generate, the fresh
    resolution says which text to read.
    """
    effective_scope_id = content_scope_id_from_scope_key(record.scope_key)
    return {
        "artifact_id": record.artifact_id,
        "user_id": record.user_id,
        "scope": record.scope.value,
        "scope_id": record.scope_id,
        "artifact_type": record.artifact_type.value,
        "parameters": record.parameters,
        "generator_version": record.generator_version,
        # Same corpus prefix for the 5 types of one request, so OpenAI's prompt
        # cache is what shares the corpus between the 5 independent invocations —
        # no intermediate store and no coordination lock of ours (task-269 §2.6).
        "prompt_cache_key": _prompt_cache_key(
            scope=record.scope,
            scope_id=effective_scope_id,
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
                # Dates the worker puts in the corpus header, so the model can
                # anchor a fact that is only true at one instant instead of
                # writing "today" into a permanent artifact (task-316 §2.7).
                "published": source.published,
                "captured": source.captured,
            }
            for source in resolution.sources
        ],
        # Translation provenance of the first source, which is what the mobile
        # renders as the "Translated from XX" badge (task-192).
        "translation": (
            resolution.sources[0].translation_metadata if resolution.sources else {}
        ),
    }


async def commit_artifact_generation(
    plan: ArtifactGenerationPlan,
) -> Tuple[MediaArtifactRecord, ArtifactGenerationOutcome]:
    """Write the entry and enqueue it, or hand back what already answers the request.

    The outcome is the caller's contract. ``REUSED`` and ``COLLAPSED`` both forbid
    debiting any counter, and they say different things: the first is a cache hit
    on identical sources, the second is one of two concurrent taps losing the
    conditional write. ``RETRIED`` reruns a failed entry under its own id, so a
    caller keying its debit on ``artifact_id`` charges the generation once, not
    once per attempt.

    A waiting plan takes the same write and stops there: the entry exists, is
    ``queued``, and is what the history and the tile read; the enqueue happens once
    its last source becomes readable, from ``artifact_wait_service`` (task-360).
    """
    if plan.reused is not None:
        return plan.reused, ArtifactGenerationOutcome.REUSED
    if plan.record is None or (plan.message is None and not plan.awaits_sources):
        raise ArtifactServiceError("Artifact generation plan is empty.")

    record = plan.record
    if plan.reclaims_failed:
        # Conditional on the row still being `failed`: if a concurrent request
        # already reclaimed it, that request owns the generation and this one has
        # nothing left to do.
        if not await media_artifacts.reclaim_failed_artifact(record):
            return await _collapsed_onto_existing(record.artifact_id)
    else:
        try:
            await media_artifacts.create_media_artifact(record)
        except media_artifacts.ArtifactAlreadyExistsError:
            return await _collapsed_onto_existing(record.artifact_id)

    if plan.message is None:
        # Nothing to send, and nothing to undo either: the entry is legitimately
        # `queued` with no message in flight. The outcome still distinguishes a
        # first request from a retry, because that is what the caller debits on.
        return record, (
            ArtifactGenerationOutcome.RETRIED
            if plan.reclaims_failed
            else ArtifactGenerationOutcome.CREATED
        )

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

    outcome = (
        ArtifactGenerationOutcome.RETRIED
        if plan.reclaims_failed
        else ArtifactGenerationOutcome.CREATED
    )
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
        outcome=outcome.value,
    )
    return record, outcome


async def _collapsed_onto_existing(
    artifact_id: str,
) -> Tuple[MediaArtifactRecord, ArtifactGenerationOutcome]:
    """Read back the entry a concurrent identical request wrote first."""
    existing = await media_artifacts.get_media_artifact_by_id(artifact_id)
    if existing is None:
        raise ArtifactServiceError(
            "Artifact id was claimed concurrently but cannot be read back."
        )
    log_event(
        logger,
        logging.INFO,
        "artifact.collapsed",
        "Concurrent identical artifact request collapsed onto the one in flight",
        artifact_id=existing.artifact_id,
        artifact_type=existing.artifact_type.value,
        scope=existing.scope.value,
        scope_id=existing.scope_id,
    )
    return existing, ArtifactGenerationOutcome.COLLAPSED


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

    An empty scope is refused with the reason that emptied it — and a source still
    being prepared does not empty anything: it counts here exactly like a readable
    one, which is what turns "nothing is transcribed yet" from a refusal into a
    waiting entry (task-360). Only definitive exclusions can leave a scope empty,
    and a translation the provider refused for good is one: saying so is what keeps
    the client from retrying (task-327).

    The token ceiling can only be measured on the sources that are readable, so a
    deferred request is checked again at resume, when every transcript exists.
    """
    source_count = len(resolution.sources) + len(resolution.pending)
    estimated_tokens = resolution.estimated_tokens
    if source_count == 0:
        translation_failed = [
            source
            for source in resolution.excluded
            if source.excluded_reason == EXCLUDED_REASON_TRANSLATION_FAILED
        ]
        if translation_failed:
            raise ArtifactTranslationFailedError(
                "The translation of every source here failed and will not be "
                "retried automatically. Try again later.",
                failed_titles=[
                    source.title for source in translation_failed if source.title
                ],
                failed_count=len(translation_failed),
            )
        raise ArtifactScopeEmptyError(
            "This folder has no source with a usable transcript yet."
        )
    if source_count > MAX_FOLDER_SOURCES or estimated_tokens > MAX_FOLDER_CORPUS_TOKENS:
        raise ArtifactScopeTooLargeError(
            "This folder is too large to generate over. Generate on a "
            "smaller subfolder instead.",
            source_count=source_count,
            max_sources=MAX_FOLDER_SOURCES,
            estimated_tokens=estimated_tokens,
            max_tokens=MAX_FOLDER_CORPUS_TOKENS,
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

    # Only this type, and only at media scope: ``scope_id`` is the library row's
    # media id there, whereas at folder scope it is a folder id and the copy
    # would address a row that does not exist.
    if (
        record.artifact_type == MediaArtifactType.REVIEW_BLURB
        and record.scope == ArtifactScope.MEDIA
    ):
        await _mirror_review_blurb_onto_library_row(
            user_id=record.user_id,
            media_item_id=record.scope_id,
            blurb=_read_blurb(content),
            artifact_id=record.artifact_id,
        )

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


def _read_blurb(content: Dict[str, Any]) -> Optional[ReviewBlurb]:
    """Pull the triage card out of a stored ``review_blurb`` envelope.

    Validated rather than passed through: what goes onto the library row is read
    back by every list request, and an envelope in an older shape (the v1 prose)
    would otherwise travel all the way to the mobile client as a malformed card.
    """
    payload = content.get("content")
    if not isinstance(payload, dict):
        return None
    try:
        blurb = ReviewBlurb.model_validate(payload)
    except ValidationError:
        return None
    return blurb if blurb.hook.strip() else None


async def _mirror_review_blurb_onto_library_row(
    *,
    user_id: str,
    media_item_id: str,
    blurb: Optional[ReviewBlurb],
    artifact_id: str,
) -> bool:
    """Copy a finished blurb onto the ``user_media`` row that displays it.

    Same reason the model's ``title`` is copied onto the artifact row: the library
    list must render without an S3 read. A screen showing 50 rows would otherwise
    mean 50 artifact lookups plus 50 object downloads to display one card each,
    which is the cost this copy buys out — one attribute-level ``SET``, once per
    media forever.

    Never fatal. The artifact is stored and sealed by the time this runs, so a
    failure here must not turn a successful generation into a failed one;
    ``copy_review_blurb_to_library_row`` is the repair path for a row it missed.
    Returns whether the row now carries the prose.
    """
    if blurb is None:
        return False

    try:
        from media_summarizer.utils import user_media as user_media_store

        updated = await user_media_store.update_attributes(
            user_id=user_id,
            media_item_id=media_item_id,
            attributes={"review_blurb": blurb.model_dump()},
        )
        if not updated:
            log_event(
                logger,
                logging.INFO,
                "artifact.review_blurb_row_missing",
                "Library row is gone; keeping the artifact without its row copy",
                artifact_id=artifact_id,
                media_item_id=media_item_id,
            )
        return updated
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "artifact.review_blurb_copy_failed",
            "Failed to copy review_blurb onto the library row (non-fatal)",
            artifact_id=artifact_id,
            media_item_id=media_item_id,
            error_type=type(exc).__name__,
            detail=str(exc)[:200],
        )
        return False


async def copy_review_blurb_to_library_row(
    *,
    record: MediaArtifactRecord,
    media_item_id: str,
) -> bool:
    """Repair path: mirror an *already stored* blurb onto a row that lacks it.

    Two situations produce a ready artifact next to a row with no prose, and
    neither is worth a second generation:

    - the copy at completion time failed (S3 wrote, DynamoDB did not);
    - a second save of the same content by the same user resolves to the very same
      ``artifact_id`` — the id is derived from the content key, not from the row —
      so it is answered by ``REUSED`` and its own row was never written to. Hence
      ``media_item_id`` is a parameter instead of being read off ``record``: the
      row to fill is the caller's, not the one that first triggered the generation.

    One S3 read, and only on a row that has no blurb yet.
    """
    if record.artifact_type != MediaArtifactType.REVIEW_BLURB:
        return False
    if record.scope != ArtifactScope.MEDIA:
        return False
    if record.status != MediaArtifactStatus.READY or record.storage is None:
        return False

    try:
        raw = await s3.download_file_to_memory(
            bucket=record.storage.bucket,
            key=record.storage.key,
        )
        content = json.loads(raw.decode("utf-8", errors="ignore"))
    except Exception as exc:
        log_event(
            logger,
            logging.WARNING,
            "artifact.review_blurb_reread_failed",
            "Could not re-read a stored review_blurb to repair its library row",
            artifact_id=record.artifact_id,
            media_item_id=media_item_id,
            error_type=type(exc).__name__,
            detail=str(exc)[:200],
        )
        return False

    return await _mirror_review_blurb_onto_library_row(
        user_id=record.user_id,
        media_item_id=media_item_id,
        blurb=_read_blurb(content if isinstance(content, dict) else {}),
        artifact_id=record.artifact_id,
    )


async def fail_artifact_generation(
    *,
    artifact_id: str,
    error_message: str,
    error_code: Optional[str] = None,
) -> Optional[MediaArtifactRecord]:
    record = await media_artifacts.get_media_artifact_by_id(artifact_id)
    if not record:
        return None

    now = _now_utc()
    record.status = MediaArtifactStatus.FAILED
    effective_error_code = error_code or "INTERNAL_ERROR"
    record.error_code = effective_error_code
    record.error_message = error_message
    record.lease_expires_at = None
    # A failed entry is never waiting for a source any more: leaving the deadline on
    # it would make a resume hook believe the wait is still open and enqueue it.
    record.awaiting_expires_at = None
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
        error_code=effective_error_code,
        detail=error_message,
    )
    return record
