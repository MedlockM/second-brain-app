"""
Queue-first YouTube ingestion worker.

Pipeline (Apify-only, task-309):
- Consumes messages from YOUTUBE_INGESTION_QUEUE
- Starts an Apify YouTube Transcript actor run, then completes the job from the
  actor callback (with an SQS backstop if the callback never lands)
- On actor failure the job is marked failed with a specific user-facing message;
  there is no audio fallback, because no supported actor exposes a raw audio URL

Why Apify is the only path
--------------------------
yt-dlp used to run first, with Apify kept as an IP-block fallback (task-177).
Measured on dev on 2026-08-20, that primary was structurally dead from Lambda:
10 of 12 YouTube jobs succeeded via `apify_youtube_transcript`, zero via yt-dlp,
and every single yt-dlp attempt logged `Sign in to confirm you're not a bot`.
The dead round-trip cost ~6.4 s per invocation against ~1.6 s for pure-Apify
ones, on every save. The branch was deleted rather than demoted. The yt-dlp
package stays in the image for the TikTok worker and the Instagram resolver,
which still use it successfully.

Transcript language (task-216)
------------------------------
The target language is NOT decided here. It is resolved by the API from the
user's ``reading_language`` preference (task-190), overridable per submission via
``transcript_language`` in ``POST /api/media/ingest-url``, and travels
API -> orchestrator -> SQS -> this worker. The worker only consumes it:

- Apify path: sends ``language`` in the actor input when the configured actor
  supports it, so the actor returns that language's captions directly (saves a
  downstream translation LLM call).

When the requested language is unavailable for a video, a language-aware actor
answers ``error_category="language_not_available"``; the worker then retries once
without ``language`` to get the video's default captions, and the task-192
pipeline (detection + GPT-5-nano translation) brings the transcript to the user's
reading_language downstream.

Apify actor dialects
--------------------
``APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID`` comes from Secrets Manager at runtime, so
code cannot assume which actor is configured (the Lambda bootstrap uses
``os.environ.setdefault``: the secret always wins over the code default). Each
supported actor therefore declares its own input/output dialect in
``_APIFY_ACTOR_DIALECTS``:

- ``starvibe~youtube-video-transcript``: accepts ``language`` (ISO 639-1),
  returns ``transcript_text`` — the language-aware target of task-216.
- ``scrape-creators~best-youtube-transcripts-scraper``: accepts only
  ``videoUrls``, returns ``transcript_only_text`` and an English language name.
  No language control possible.

An unknown actor id fails fast with ``apify_actor_unsupported`` instead of being
sent a payload it will reject with a generic 400.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from enum import Enum
from io import BytesIO
from typing import Any, Dict, Optional

from media_summarizer.core.media_ingestion.media_metadata import (
    normalize_cover_url,
    select_creator,
    youtube_video_id,
)
from media_summarizer.core.media_ingestion.title_derivation import select_title
from media_summarizer.core.services import quota_enforcer
from media_summarizer.core.services.transcript_formatting import (
    count_paragraphs,
    group_caption_lines,
    normalize_transcript_text,
)
from media_summarizer.infrastructure import apify_adapter
from media_summarizer.infrastructure.apify_adapter import ApifyActorKind
from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils.env import required_env
from media_summarizer.utils.language_codes import (
    normalize_language_code,
    resolve_language_code,
)
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
    setup_logging,
)
from media_summarizer.workers import apify_orchestration
from media_summarizer.workers.base_worker import (
    get_sqs_receive_params,
    process_message_with_retry,
)

logger = logging.getLogger(__name__)

TRANSCRIPT_BUCKET = required_env("TRANSCRIPT_BUCKET")
YOUTUBE_INGESTION_QUEUE = required_env("YOUTUBE_INGESTION_QUEUE")
EPISODE_COMPLETED_EVENTS_QUEUE = required_env("EPISODE_COMPLETED_EVENTS_QUEUE")
YOUTUBE_WORKER_MAX_RETRIES = 3

_STARVIBE_ACTOR = "starvibe~youtube-video-transcript"
_SCRAPE_CREATORS_ACTOR = "scrape-creators~best-youtube-transcripts-scraper"

# Per-actor input/output dialects. Verified live against the Apify build schemas
# on 2026-08-05. `supports_language` drives whether task-216 can request the
# user's reading_language at all on the Apify path.
_APIFY_ACTOR_DIALECTS: Dict[str, Dict[str, Any]] = {
    _STARVIBE_ACTOR: {
        "supports_language": True,
        "url_field": "youtube_url",
        "url_is_list": False,
        "text_fields": ("transcript_text",),
        "extra_input": {"include_transcript_text": True},
    },
    _SCRAPE_CREATORS_ACTOR: {
        "supports_language": False,
        "url_field": "videoUrls",
        "url_is_list": True,
        "text_fields": ("transcript_only_text",),
        "extra_input": {},
    },
}

# Field names under which a transcript actor may expose the video title. Neither
# actor guarantees it in its output schema, so all known spellings are tried and
# a missing title simply leaves the submission-time value in place (task-266).
_APIFY_TITLE_FIELDS = ("title", "video_title", "videoTitle", "name")

# Same story for the channel and the cover: neither actor declares them in
# its output schema, so every known spelling is probed and a miss simply
# leaves the field empty -- for the cover, the deterministic `i.ytimg.com` URL
# the resolver already stored at submission time stays in place (task-353).
_APIFY_CREATOR_FIELDS = ("channel", "channel_name", "channelName", "author", "uploader")
_APIFY_THUMBNAIL_FIELDS = ("thumbnail", "thumbnail_url", "thumbnailUrl", "cover")

_UNAVAILABLE_MESSAGE = "This YouTube video is unavailable or cannot be processed."
_TEMPORARY_MESSAGE = "YouTube extraction is temporarily unavailable. Please retry."
_GEO_RESTRICTED_MESSAGE = "This YouTube video is geo-restricted and cannot be accessed."
_AGE_RESTRICTED_MESSAGE = "This YouTube video is age-restricted and cannot be processed."


# ---------------------------------------------------------------------------
# Error classes
# ---------------------------------------------------------------------------


class ApifyTranscriptFailure(str, Enum):
    """Stable failure details for the Apify YouTube transcript branch.

    Surfaced in ``YouTubeIngestionError.details`` (and therefore in job
    ``extraction_metadata.failure_details`` and the failure event reason), so
    they are part of the observability contract: do not rename without updating
    dashboards/alarms.
    """

    TOKEN_MISSING = "apify_token_missing"
    ACTOR_MISSING = "apify_actor_missing"
    # Configured actor id has no known input/output dialect: raised before any
    # HTTP call so a misconfigured runtime secret is diagnosable instead of
    # surfacing as an opaque provider 400.
    ACTOR_UNSUPPORTED = "apify_actor_unsupported"
    NETWORK_ERROR = "apify_network"
    PAYMENT_REQUIRED = "apify_payment_required"
    AUTH_ERROR = "apify_auth_error"
    SERVER_ERROR = "apify_server_error"
    CLIENT_ERROR = "apify_client_error"
    INVALID_JSON = "apify_invalid_json"
    NO_RESULTS = "apify_no_results"
    INVALID_RESULT = "apify_invalid_result"
    ACTOR_ERROR = "apify_actor_error"
    EMPTY_TRANSCRIPT = "apify_empty_transcript"
    # Refusal reasons the actor reports through `error_category`, kept distinct
    # from the generic ACTOR_ERROR so the user is told *why* the video cannot be
    # read. These replace the predicates the yt-dlp branch used to run against
    # its own exception strings (task-309).
    GEO_RESTRICTED = "apify_geo_restricted"
    AGE_RESTRICTED = "apify_age_restricted"
    VIDEO_UNAVAILABLE = "apify_video_unavailable"


class YouTubeIngestionError(Exception):
    def __init__(
        self,
        code: str,
        *,
        details: Optional[str] = None,
        retryable: bool = False,
        user_message: Optional[str] = None,
    ) -> None:
        super().__init__(details or code)
        self.code = code
        self.details = (details or "").strip()
        self.retryable = retryable
        self.user_message = user_message or "Unable to process this YouTube URL."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _requested_transcript_language(message_body: Dict[str, Any]) -> Optional[str]:
    """Target transcript language carried by the SQS message (task-216).

    ``transcript_language`` is the value the API resolved from the request
    override or the user's ``reading_language``. ``language``/``locale`` remain
    accepted as weaker hints for messages produced outside the API path.

    Returns ``None`` when the message carries no usable language: there is
    deliberately NO hard-coded default anymore, so we never silently ask a
    provider for a language the user never picked.
    """
    for key in ("transcript_language", "language", "locale"):
        language = normalize_language_code(message_body.get(key))
        if language:
            return language
    return None


def _apify_actor_id_for_api(actor_id: str) -> str:
    return actor_id.strip().replace("/", "~")


def _extract_video_id(normalized_url: str) -> str:
    """The video id, or a non-retryable ingestion error when the URL has none.

    The parsing itself lives in ``media_metadata.youtube_video_id``, which the
    resolver uses to derive the submission-time cover: one parser, so the id this
    worker works on is by construction the id that cover points at.
    """
    video_id = youtube_video_id(normalized_url)
    if video_id:
        return video_id
    raise YouTubeIngestionError(
        "youtube_unavailable",
        details="missing_video_id",
        retryable=False,
        user_message=_UNAVAILABLE_MESSAGE,
    )




# ---------------------------------------------------------------------------
# Apify YouTube Transcript (primary path)
# ---------------------------------------------------------------------------


def _apify_actor_dialect(actor_id: str) -> Dict[str, Any]:
    """Return the input/output dialect for the configured actor.

    Raises ``apify_actor_unsupported`` when the runtime secret names an actor
    this worker does not know how to talk to, naming the offending id and the
    supported set so the misconfiguration is immediately actionable.
    """
    normalized = _apify_actor_id_for_api(actor_id)
    dialect = _APIFY_ACTOR_DIALECTS.get(normalized)
    if dialect is None:
        log_event(
            logger,
            logging.ERROR,
            "config.actor_unsupported",
            (
                "APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID names an actor this worker has "
                "no payload dialect for; update the runtime secret to a supported "
                "actor before relying on the Apify fallback"
            ),
            configured_actor_id=normalized,
            supported_actor_ids=sorted(_APIFY_ACTOR_DIALECTS),
            transcript_source="apify_transcript",
        )
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details=(f"{ApifyTranscriptFailure.ACTOR_UNSUPPORTED.value}:{normalized}"),
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )
    return dialect


def _build_apify_transcript_payload(
    source_url: str,
    *,
    transcript_language: Optional[str],
    dialect: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the Apify actor input for one video, in the actor's own dialect.

    ``language`` (bare ISO 639-1) is only sent to actors that declare
    ``supports_language``; sending it to an actor that does not accept it would
    be rejected as ``invalid-input``. It is also omitted when the target
    language is unknown, in which case the actor picks the video's default
    caption track.
    """
    url_value = [source_url] if dialect["url_is_list"] else source_url
    payload: Dict[str, Any] = {dialect["url_field"]: url_value}
    payload.update(dialect["extra_input"])
    if transcript_language and dialect["supports_language"]:
        payload["language"] = transcript_language
    return payload


def _apify_item_transcript_text(item: Dict[str, Any], dialect: Dict[str, Any]) -> str:
    """Extract the readable transcript text from an actor dataset item.

    Each actor names its flat transcript field differently
    (``transcript_text`` for starvibe, ``transcript_only_text`` for
    scrape-creators), so the field names come from the dialect. Both actors also
    return a timestamped ``transcript`` segment array, used as a fallback when
    the flat field is missing.

    Both shapes go through the shared normalizer so the stored transcript is
    paragraph-delimited rather than a wall of text or one cue per line
    (task-231 option B).
    """
    for field in dialect["text_fields"]:
        flat = item.get(field)
        if isinstance(flat, str) and flat.strip():
            return normalize_transcript_text(flat, source="youtube")

    segments = item.get("transcript")
    if isinstance(segments, list):
        lines = [
            str(segment.get("text")).strip()
            for segment in segments
            if isinstance(segment, dict) and str(segment.get("text") or "").strip()
        ]
        if lines:
            return group_caption_lines(lines, source="youtube")
    return ""


def _apify_item_string(item: Dict[str, Any], fields: tuple[str, ...]) -> Optional[str]:
    """First non-empty string the dataset item carries under ``fields``."""
    for field in fields:
        value = item.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _is_language_not_available(item: Dict[str, Any]) -> bool:
    """Whether the actor refused the run only because the language is missing."""
    return (
        str(item.get("status") or "").strip().lower() == "error"
        and str(item.get("error_category") or "").strip().lower() == "language_not_available"
    )


def _classify_actor_error(item: Dict[str, Any]) -> YouTubeIngestionError:
    """Map an actor error item to a specific user-facing failure.

    The actors report a free-form ``error_category`` rather than a closed
    vocabulary, so each family is matched on a substring of the lowercased
    value. The mapping is:

    ==========================  ==============================  =========================
    ``error_category`` contains  ``ApifyTranscriptFailure``       error code
    ==========================  ==============================  =========================
    ``geo``, ``region``,         ``GEO_RESTRICTED``              ``youtube_geo_restricted``
    ``country``
    ``age``, ``sign_in``,        ``AGE_RESTRICTED``              ``youtube_age_restricted``
    ``login``
    ``unavailable``,             ``VIDEO_UNAVAILABLE``           ``youtube_unavailable``
    ``private``, ``deleted``,
    ``removed``, ``not_found``
    anything else                ``ACTOR_ERROR``                 ``youtube_unavailable``
    ==========================  ==============================  =========================

    ``language_not_available`` never reaches here: the callback branch retries
    it on the video's default track before parsing.

    All four are terminal -- retrying a geo-blocked or deleted video from the
    same actor cannot succeed -- so none is marked retryable.
    """
    category = str(item.get("error_category") or "").strip().lower()

    if any(token in category for token in ("geo", "region", "country")):
        return YouTubeIngestionError(
            "youtube_geo_restricted",
            details=ApifyTranscriptFailure.GEO_RESTRICTED.value,
            retryable=False,
            user_message=_GEO_RESTRICTED_MESSAGE,
        )
    if any(token in category for token in ("age", "sign_in", "signin", "login")):
        return YouTubeIngestionError(
            "youtube_age_restricted",
            details=ApifyTranscriptFailure.AGE_RESTRICTED.value,
            retryable=False,
            user_message=_AGE_RESTRICTED_MESSAGE,
        )
    if any(
        token in category
        for token in ("unavailable", "private", "deleted", "removed", "not_found")
    ):
        return YouTubeIngestionError(
            "youtube_unavailable",
            details=ApifyTranscriptFailure.VIDEO_UNAVAILABLE.value,
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )
    return YouTubeIngestionError(
        "youtube_unavailable",
        details=(
            f"{ApifyTranscriptFailure.ACTOR_ERROR.value}:{category}"
            if category
            else ApifyTranscriptFailure.ACTOR_ERROR.value
        ),
        retryable=False,
        user_message=_UNAVAILABLE_MESSAGE,
    )


def _parse_apify_transcript(
    source_url: str,
    *,
    items: list[dict[str, Any]],
    actor_id: str,
    transcript_language: Optional[str],
    language_fallback: bool,
) -> Dict[str, Any]:
    """Parse the completed actor dataset without any provider wait."""
    dialect = _apify_actor_dialect(actor_id)
    language_supported = bool(dialect["supports_language"])
    if not items:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details=ApifyTranscriptFailure.NO_RESULTS.value,
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )
    item = items[0]

    if str(item.get("status") or "").strip().lower() == "error":
        raise _classify_actor_error(item)

    transcript_text = _apify_item_transcript_text(item, dialect)
    if not transcript_text:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details=ApifyTranscriptFailure.EMPTY_TRANSCRIPT.value,
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    # Paragraph count rather than the actor's cue count, so the value is
    # comparable with the Deepgram path (task-231 section 13.1).
    segments_count = count_paragraphs(transcript_text)

    return {
        "text": transcript_text,
        "title": _apify_item_string(item, _APIFY_TITLE_FIELDS),
        "creator": _apify_item_string(item, _APIFY_CREATOR_FIELDS),
        "thumbnail": _apify_item_string(item, _APIFY_THUMBNAIL_FIELDS),
        # Language actually delivered by the actor; may differ from the request
        # when we fell back to the video default or the actor cannot select a
        # language at all (task-192 translates downstream). Resolved through
        # `resolve_language_code` because scrape-creators reports an English
        # display name ("English") where starvibe reports a code ("en").
        "language": resolve_language_code(item.get("language")),
        "requested_language": transcript_language,
        "language_supported": language_supported,
        "language_fallback": language_fallback,
        "selected_language_label": item.get("selected_language") or item.get("language"),
        "actor_id": _apify_actor_id_for_api(actor_id),
        "segments_count": segments_count,
        "source_detail": "apify_youtube_transcript",
        "source_url": source_url,
        "fetched_at": _now_iso_utc(),
        "is_automatic": bool(item.get("is_auto_generated")),
    }


async def _start_apify_transcript_run(
    *,
    job: Any,
    source_url: str,
    transcript_language: Optional[str],
    message_body: Dict[str, Any],
    language_fallback: bool = False,
    replace_active_run: bool = False,
) -> Dict[str, Any]:
    actor_id = apify_adapter.configured_actor_id(ApifyActorKind.YOUTUBE_TRANSCRIPT)
    dialect = _apify_actor_dialect(actor_id)
    language_supported = bool(dialect["supports_language"])
    if transcript_language and not language_supported:
        log_event(
            logger,
            logging.WARNING,
            "transcription.language_request_unsupported",
            "Configured Apify actor cannot select a transcript language",
            transcript_source="apify_transcript",
            configured_actor_id=actor_id,
            language_aware_actor_id=_STARVIBE_ACTOR,
            requested_language=transcript_language,
        )

    payload_language = None if language_fallback else transcript_language
    context = {
        **message_body,
        "normalized_url": source_url,
        "transcript_language": transcript_language,
        "apify_language_fallback": language_fallback,
    }
    try:
        run = await apify_orchestration.start_run_for_job(
            job=job,
            kind=ApifyActorKind.YOUTUBE_TRANSCRIPT,
            source_platform="youtube",
            input_data=_build_apify_transcript_payload(
                source_url,
                transcript_language=payload_language,
                dialect=dialect,
            ),
            queue_name=YOUTUBE_INGESTION_QUEUE,
            context=context,
            replace_active_run=replace_active_run,
        )
    except apify_adapter.ApifyAdapterError as exc:
        raise YouTubeIngestionError(
            "youtube_apify_failed",
            details=exc.code,
            retryable=exc.retryable,
            user_message=(_TEMPORARY_MESSAGE if exc.retryable else _UNAVAILABLE_MESSAGE),
        ) from exc
    return {
        "mode": "apify_pending",
        "job_id": job.id,
        "media_key": message_body.get("media_key"),
        "apify_run_id": run.run_id,
        "language_fallback": language_fallback,
    }


# ---------------------------------------------------------------------------
# S3 upload + event publishing
# ---------------------------------------------------------------------------


async def _upload_transcript(job_id: str, text: str) -> str:
    """Upload the transcript, normalized to paragraph-delimited plain text.

    The normalizer is idempotent, so text already structured upstream (Apify
    flat field, grouped cue lines) passes through untouched.
    """
    transcript_s3_key = f"{job_id}.txt"
    normalized = normalize_transcript_text(text, source="youtube")
    await s3.upload_file_object(
        bucket=TRANSCRIPT_BUCKET,
        key=transcript_s3_key,
        file_obj=BytesIO(normalized.encode("utf-8")),
        content_type="text/plain",
        metadata={
            "content-type": "text/plain",
            "job-type": "youtube-transcript",
            "provider": "native_transcript",
        },
    )
    return transcript_s3_key


async def _publish_success_event(
    *,
    job_id: str,
    media_key: Optional[str],
    transcript_s3_key: str,
    transcription_metadata: Dict[str, Any],
) -> None:
    await sqs.send_message(
        queue_name=EPISODE_COMPLETED_EVENTS_QUEUE,
        message_body={
            "event_type": "episode_completion_status",
            "status": "success",
            "media_key": media_key,
            "canonical_job_id": job_id,
            "transcription_s3_key": transcript_s3_key,
            "transcription_metadata": transcription_metadata,
        },
    )


async def _publish_failure_event(
    *,
    job_id: Optional[str],
    media_key: Optional[str],
    reason: str,
) -> None:
    if not job_id:
        return
    await sqs.send_message(
        queue_name=EPISODE_COMPLETED_EVENTS_QUEUE,
        message_body={
            "event_type": "episode_completion_status",
            "status": "failure",
            "media_key": media_key,
            "canonical_job_id": job_id,
            "reason": reason,
        },
    )


# ---------------------------------------------------------------------------
# Metadata builders
# ---------------------------------------------------------------------------


def _build_apify_extraction_metadata(
    *,
    video_id: str,
    source_url: str,
    apify_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "provider": "apify",
        "extractor": "apify_youtube_transcript",
        "extractor_version": "v1",
        "strategy_used": "apify_transcript",
        "video_id": video_id,
        "source_url": source_url,
        "actor_id": apify_result.get("actor_id"),
        "requested_language": apify_result.get("requested_language"),
        "transcript_language": apify_result.get("language"),
        # False when the configured actor has no language input at all: the
        # request could not be honoured, so a downstream translation is expected.
        "language_supported": apify_result.get("language_supported", False),
        "language_fallback": apify_result.get("language_fallback", False),
        "selected_language_label": apify_result.get("selected_language_label"),
        "is_automatic_caption": apify_result.get("is_automatic", False),
        "segments_count": apify_result.get("segments_count"),
        "fetched_at": apify_result["fetched_at"],
    }


def _build_apify_transcription_metadata(
    *,
    apify_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "provider": "apify_transcript",
        "model_used": "apify_youtube_transcript_scraper",
        "actor_id": apify_result.get("actor_id"),
        # Language of the delivered transcript. Consumed by task-192
        # (`job_source_language_hint`) to decide whether a translation to the
        # user's reading_language is still needed.
        "language": apify_result.get("language"),
        "requested_language": apify_result.get("requested_language"),
        "segments_count": apify_result.get("segments_count"),
        "duration_seconds": 0,
        "source_url": apify_result.get("source_url"),
        "transcribed_at": apify_result["fetched_at"],
        "source_detail": apify_result["source_detail"],
    }




# ---------------------------------------------------------------------------
# Job state management
# ---------------------------------------------------------------------------


async def _mark_job_failed(
    *,
    job_id: Optional[str],
    normalized_url: str,
    video_id: Optional[str],
    error: YouTubeIngestionError,
) -> None:
    if not job_id:
        return

    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        return

    job.extraction_metadata = {
        "provider": "youtube_ingestion_worker",
        "extractor": "youtube_ingestion_worker",
        "extractor_version": "v1",
        "strategy_used": "failed",
        "source_url": normalized_url,
        "video_id": video_id,
        "last_error_code": error.code,
        "failure_details": error.details or error.code,
        "failed_at": _now_iso_utc(),
    }
    if job.apify_state == "processing":
        job.apify_state = "processed"
        job.apify_completed_at = datetime.now(timezone.utc)
    job.mark_failed(
        error_message=error.user_message,
        error_step="youtube_ingestion",
    )
    await database_async.update_processing_job(job)


# ---------------------------------------------------------------------------
# Main message processor
# ---------------------------------------------------------------------------


async def process_youtube_message(message_body: Dict[str, Any]) -> Dict[str, Any]:
    message_type = str(message_body.get("message_type") or "ingest")
    job_id = (message_body.get("job_id") or "").strip()
    normalized_url = (message_body.get("normalized_url") or "").strip()

    if not job_id:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details="missing_job_id",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )
    if not normalized_url:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details="missing_normalized_url",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details=f"processing_job_not_found:{job_id}",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    if message_type == "apify_backstop":
        expired = await apify_orchestration.expire_backstop(
            job_id=job_id,
            run_id=str(message_body.get("apify_run_id") or ""),
            source_platform="youtube",
        )
        if expired:
            await _publish_failure_event(
                job_id=job_id,
                media_key=message_body.get("media_key") or expired.media_key,
                reason="apify_callback_deadline_exceeded",
            )
        return {"mode": "apify_backstop", "job_id": job_id}

    callback_envelope = dict(message_body)
    apify_result: Optional[Dict[str, Any]] = None
    callback_message = message_type == "apify_callback"
    if callback_message:
        run_id = str(message_body.get("apify_run_id") or "").strip()
        job = await apify_orchestration.claim_callback(job_id, run_id)
        if not job:
            return {"mode": "apify_callback_ignored", "job_id": job_id}
        stored_context = dict(job.apify_context or {})
        message_body = stored_context
        normalized_url = str(stored_context.get("normalized_url") or "").strip()
        if str(message_body.get("job_id") or job_id) != job_id:
            raise YouTubeIngestionError(
                "youtube_apify_failed",
                details="apify_context_mismatch",
                retryable=False,
                user_message=_UNAVAILABLE_MESSAGE,
            )

    video_id = _extract_video_id(normalized_url)
    transcript_language = _requested_transcript_language(message_body)

    # -----------------------------------------------------------------------
    # APIFY ORCHESTRATION
    # -----------------------------------------------------------------------

    if callback_message:
        # Apify callback: check status and fetch the dataset
        callback_status = str(callback_envelope.get("apify_status") or "").upper()
        if callback_status != "SUCCEEDED":
            raise YouTubeIngestionError(
                "youtube_apify_failed",
                details=f"apify_terminal_{callback_status}",
                retryable=False,
                user_message=_UNAVAILABLE_MESSAGE,
            )
        try:
            items = await apify_adapter.fetch_dataset_items(
                source_platform="youtube",
                dataset_id=job.apify_dataset_id or "",
            )
        except apify_adapter.ApifyAdapterError as exc:
            raise YouTubeIngestionError(
                "youtube_apify_failed",
                details=exc.code,
                retryable=exc.retryable,
                user_message=(_TEMPORARY_MESSAGE if exc.retryable else _UNAVAILABLE_MESSAGE),
            ) from exc

        actor_id = job.apify_actor_id or ""
        dialect = _apify_actor_dialect(actor_id)
        language_fallback = bool(message_body.get("apify_language_fallback", False))

        # If the actor reports language not available, retry without language restriction
        # to get the video's default captions (task-192 handles downstream translation).
        if (
            items
            and transcript_language
            and bool(dialect["supports_language"])
            and not language_fallback
            and _is_language_not_available(items[0])
        ):
            log_event(
                logger,
                logging.INFO,
                "transcription.language_fallback",
                "Requested transcript language unavailable; starting default-track Apify run",
                transcript_source="apify_transcript",
                requested_language=transcript_language,
            )
            return await _start_apify_transcript_run(
                job=job,
                source_url=normalized_url,
                transcript_language=transcript_language,
                message_body=message_body,
                language_fallback=True,
                replace_active_run=True,
            )

        # Any remaining `status="error"` item is mapped to a specific
        # user-facing failure by `_classify_actor_error` (geo / age /
        # unavailable), which carries the full mapping table.
        apify_result = _parse_apify_transcript(
            normalized_url,
            items=items,
            actor_id=actor_id,
            transcript_language=transcript_language,
            language_fallback=language_fallback,
        )
    else:
        # Inbound message: start Apify actor run
        return await _start_apify_transcript_run(
            job=job,
            source_url=normalized_url,
            transcript_language=transcript_language,
            message_body=message_body,
        )

    # -----------------------------------------------------------------------
    # APIFY SUCCESS: upload transcript and complete job
    # -----------------------------------------------------------------------

    transcript_s3_key = await _upload_transcript(job_id, apify_result["text"])
    transcription_metadata = _build_apify_transcription_metadata(
        apify_result=apify_result,
    )
    job.set_transcription_location(transcript_s3_key)
    job.set_transcription_metadata(transcription_metadata)
    job.extraction_metadata = _build_apify_extraction_metadata(
        video_id=video_id,
        source_url=normalized_url,
        apify_result=apify_result,
    )

    # Title from the actor payload when it carries one (task-266). Written
    # before `mark_completed`, so the completion event -- and therefore the
    # Algolia record built from it -- already sees the real title and no
    # re-index pass is needed.
    apify_title = select_title([apify_result.get("title")])
    if apify_title:
        job.title = apify_title

    # Neither transcript actor declares a thumbnail or a channel in its output
    # schema. All known channel spellings are probed and a missing one simply
    # leaves the field empty.
    apify_creator = select_creator(
        [apify_result.get("creator")],
        title=job.title,
    )
    if apify_creator:
        job.creator_name = apify_creator

    # An actor that *does* return a thumbnail upgrades the cover; there is no
    # fallback to rebuild here, because the deterministic `i.ytimg.com` URL was
    # written onto the library row at submission time and is what the tile has
    # been showing since (task-353). Rebuilding it at completion would only
    # re-write the value it already holds -- and would keep the audio-fallback
    # branch, which never reaches this line, coverless.
    apify_cover = normalize_cover_url(apify_result.get("thumbnail"))
    if apify_cover:
        job.media_image = apify_cover

    job.mark_completed()
    if not await apify_orchestration.complete_callback(job):
        return {"mode": "apify_callback_ignored", "job_id": job_id}

    # Captions bought from Apify: a flat unit whatever the video length
    # (task-287). Charged here, after the callback claim, because this is
    # where the provider actually delivered -- a run that failed or a
    # duplicate callback costs the user nothing.
    apify_user_id = message_body.get("user_id")
    if apify_user_id:
        await quota_enforcer.record_captions_purchase(
            apify_user_id,
            idempotency_token=quota_enforcer.gate_token(job_id),
        )

    await _publish_success_event(
        job_id=job_id,
        media_key=message_body.get("media_key"),
        transcript_s3_key=transcript_s3_key,
        transcription_metadata=transcription_metadata,
    )

    return {
        "mode": "apify_transcript",
        "job_id": job_id,
        "media_key": message_body.get("media_key"),
        "video_id": video_id,
        "source_detail": "apify_youtube_transcript",
        "requested_language": transcript_language,
        "transcript_language": apify_result.get("language"),
        "language_supported": apify_result.get("language_supported"),
        "language_fallback": apify_result.get("language_fallback"),
        "actor_id": apify_result.get("actor_id"),
    }


# ---------------------------------------------------------------------------
# SQS message handler
# ---------------------------------------------------------------------------


async def process_message(message: Dict[str, Any]) -> None:
    body: Dict[str, Any] = {}

    try:
        body = json.loads(message.get("Body", "{}"))
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "worker.invalid_message",
            "Invalid JSON in YouTube ingestion message",
            queue=YOUTUBE_INGESTION_QUEUE,
            exc_info=exc,
        )
        return

    context_token = bind_log_context(
        job_id=body.get("job_id"),
        media_item_id=body.get("job_id"),
        queue=YOUTUBE_INGESTION_QUEUE,
        resolver_key=body.get("resolver_key") or "youtube.default",
        source_platform="youtube",
    )

    receive_count = int((message.get("Attributes") or {}).get("ApproximateReceiveCount", "1"))

    try:
        result = await process_youtube_message(body)
        mode = result["mode"]

        if mode == "apify_transcript":
            log_event(
                logger,
                logging.INFO,
                "transcription.completed",
                "YouTube transcript completed via Apify",
                job_id=result["job_id"],
                media_item_id=result["job_id"],
                transcript_source="apify_transcript",
                requested_language=result.get("requested_language"),
                transcript_language=result.get("transcript_language"),
                language_supported=result.get("language_supported"),
                language_fallback=result.get("language_fallback"),
                actor_id=result.get("actor_id"),
            )
        elif mode in {
            "apify_pending",
            "apify_callback_ignored",
            "apify_backstop",
        }:
            log_event(
                logger,
                logging.INFO,
                "apify.orchestration",
                "YouTube Apify orchestration advanced",
                job_id=result["job_id"],
                media_item_id=result["job_id"],
                orchestration_mode=mode,
            )
    except YouTubeIngestionError as exc:
        should_retry = exc.retryable and receive_count < YOUTUBE_WORKER_MAX_RETRIES
        if should_retry:
            raise

        video_id = None
        normalized_url = (body.get("normalized_url") or "").strip()
        if normalized_url:
            try:
                video_id = _extract_video_id(normalized_url)
            except YouTubeIngestionError:
                video_id = None

        await _mark_job_failed(
            job_id=body.get("job_id"),
            normalized_url=normalized_url,
            video_id=video_id,
            error=exc,
        )
        reason = exc.code if not exc.details else f"{exc.code}:{exc.details}"
        await _publish_failure_event(
            job_id=body.get("job_id"),
            media_key=body.get("media_key"),
            reason=reason,
        )
        log_event(
            logger,
            logging.ERROR,
            "transcription.failed",
            "YouTube ingestion failed",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            error_code=exc.code,
            detail=exc.details,
        )
    except Exception as exc:
        if receive_count < YOUTUBE_WORKER_MAX_RETRIES:
            raise

        final_error = YouTubeIngestionError(
            "youtube_unavailable",
            details=f"unexpected:{type(exc).__name__}",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )
        video_id = None
        normalized_url = (body.get("normalized_url") or "").strip()
        if normalized_url:
            try:
                video_id = _extract_video_id(normalized_url)
            except YouTubeIngestionError:
                video_id = None
        await _mark_job_failed(
            job_id=body.get("job_id"),
            normalized_url=normalized_url,
            video_id=video_id,
            error=final_error,
        )
        await _publish_failure_event(
            job_id=body.get("job_id"),
            media_key=body.get("media_key"),
            reason=f"{final_error.code}:{final_error.details}",
        )
        log_event(
            logger,
            logging.ERROR,
            "transcription.failed",
            "YouTube ingestion failed after retries",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            error_code=final_error.code,
            exc_info=exc,
        )
    finally:
        reset_log_context(context_token)


# ---------------------------------------------------------------------------
# Queue polling loop
# ---------------------------------------------------------------------------


async def poll_queue() -> None:
    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting YouTube ingestion worker",
        queue=YOUTUBE_INGESTION_QUEUE,
    )
    while True:
        try:
            receive_params = get_sqs_receive_params(visibility_timeout=360)
            messages = await sqs.receive_messages(
                queue_name=YOUTUBE_INGESTION_QUEUE,
                max_messages=receive_params["MaxNumberOfMessages"],
                wait_time_seconds=receive_params["WaitTimeSeconds"],
                visibility_timeout=receive_params["VisibilityTimeout"],
            )
            if messages:
                for message in messages:
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=YOUTUBE_INGESTION_QUEUE,
                        max_retries=YOUTUBE_WORKER_MAX_RETRIES,
                        worker_name="youtube_ingestion",
                    )
            else:
                await asyncio.sleep(1)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "YouTube ingestion polling failed",
                queue=YOUTUBE_INGESTION_QUEUE,
                exc_info=exc,
            )
            await asyncio.sleep(5)


async def main() -> None:
    setup_logging("youtube-ingestion-worker")
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
