"""
Queue-first YouTube ingestion worker.

Pipeline:
- Consumes messages from YOUTUBE_INGESTION_QUEUE
- Attempts native transcript retrieval in the order manual -> auto
- Uploads native transcript text to S3 and publishes completion events on success
- Falls back to yt-dlp audio URL resolution and reuses the Deepgram queue when
  no native transcript is available
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from io import BytesIO
import os
from typing import Any, Dict, Iterable, Optional
from urllib.parse import parse_qs, urlsplit

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    AgeRestricted,
    CouldNotRetrieveTranscript,
    IpBlocked,
    NoTranscriptFound,
    RequestBlocked,
    TranscriptsDisabled,
    VideoUnavailable,
    VideoUnplayable,
    YouTubeRequestFailed,
)

from media_summarizer.utils import database_async, s3, sqs
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
    setup_logging,
)
from media_summarizer.workers.base_worker import (
    get_sqs_receive_params,
    process_message_with_retry,
)

logger = logging.getLogger(__name__)

TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcriptions"
)
YOUTUBE_INGESTION_QUEUE = os.environ.get(
    "YOUTUBE_INGESTION_QUEUE", "youtube-ingestion-queue"
)
DEEPGRAM_TRANSCRIPTION_QUEUE = os.environ.get(
    "DEEPGRAM_TRANSCRIPTION_QUEUE", "deepgram-transcription-queue"
)
EPISODE_COMPLETED_EVENTS_QUEUE = os.environ.get(
    "EPISODE_COMPLETED_EVENTS_QUEUE", "episode-completed-events"
)
YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS = float(
    os.environ.get("YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS", "20")
)
YTDLP_TIMEOUT_SECONDS = float(os.environ.get("YTDLP_TIMEOUT_SECONDS", "30"))
YOUTUBE_WORKER_MAX_RETRIES = 3

_NATIVE_TRANSCRIPT_PROVIDER = "youtube_transcript_api"
_YTDLP_EXTRACTOR_VERSION = "v1"
_AUDIO_URL_PROTOCOLS = {
    "http",
    "https",
    "http_dash_segments",
    "https_dash_segments",
}
_UNAVAILABLE_MESSAGE = "This YouTube video is unavailable or cannot be processed."
_TEMPORARY_TRANSCRIPT_MESSAGE = (
    "YouTube transcript retrieval is temporarily unavailable. Please retry."
)
_TEMPORARY_AUDIO_MESSAGE = "YouTube audio extraction failed. Please retry."


class NativeTranscriptUnavailable(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


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


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _looks_like_unavailable_error(message: str) -> bool:
    normalized = (message or "").lower()
    return any(
        token in normalized
        for token in (
            "unavailable",
            "unplayable",
            "private video",
            "private",
            "deleted",
            "removed",
            "age-restricted",
            "age restricted",
            "members-only",
            "members only",
        )
    )


def _extract_video_id(normalized_url: str) -> str:
    split = urlsplit((normalized_url or "").strip())
    host = (split.hostname or "").lower()
    path = split.path or ""
    parts = [segment for segment in path.split("/") if segment]
    query = parse_qs(split.query)

    if host in {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}:
        if path == "/watch":
            video_id = (query.get("v") or [""])[0].strip()
            if video_id:
                return video_id
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
            return parts[1].strip()
    if host in {"youtu.be", "www.youtu.be"} and parts:
        return parts[0].strip()
    raise YouTubeIngestionError(
        "youtube_unavailable",
        details="missing_video_id",
        retryable=False,
        user_message=_UNAVAILABLE_MESSAGE,
    )


def _snippet_text(snippet: Any) -> str:
    if isinstance(snippet, dict):
        return str(snippet.get("text") or "").strip()
    return str(getattr(snippet, "text", "") or "").strip()


def _normalize_native_transcript(
    *,
    transcript: Any,
    transcript_object: Any,
    source_detail: str,
    source_url: str,
) -> Dict[str, Any]:
    if hasattr(transcript, "to_raw_data"):
        raw_snippets = transcript.to_raw_data()
    else:
        raw_snippets = list(transcript)

    lines = [text for text in (_snippet_text(item) for item in raw_snippets) if text]
    text = "\n".join(lines).strip()
    if not text:
        raise NativeTranscriptUnavailable("empty_native_transcript")

    language = str(
        getattr(transcript, "language", None)
        or getattr(transcript_object, "language", None)
        or ""
    ).strip() or None
    language_code = str(
        getattr(transcript, "language_code", None)
        or getattr(transcript_object, "language_code", None)
        or ""
    ).strip() or None

    return {
        "text": text,
        "language": language or language_code,
        "language_code": language_code,
        "segments_count": len(lines),
        "source_detail": source_detail,
        "source_url": source_url,
        "fetched_at": _now_iso_utc(),
    }


def _select_transcript(transcript_list: Iterable[Any]) -> tuple[Any, str]:
    manual_transcript = None
    generated_transcript = None

    for transcript in transcript_list:
        is_generated = bool(getattr(transcript, "is_generated", False))
        if is_generated:
            if generated_transcript is None:
                generated_transcript = transcript
        elif manual_transcript is None:
            manual_transcript = transcript

    if manual_transcript is not None:
        return manual_transcript, "youtube_manual"
    if generated_transcript is not None:
        return generated_transcript, "youtube_auto"
    raise NativeTranscriptUnavailable("no_native_transcript")


async def _fetch_native_transcript(video_id: str, source_url: str) -> Dict[str, Any]:
    api = YouTubeTranscriptApi()

    async def _list_transcripts() -> Any:
        return await asyncio.to_thread(api.list, video_id)

    try:
        transcript_list = await asyncio.wait_for(
            _list_transcripts(),
            timeout=YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS,
        )
        transcript_object, source_detail = _select_transcript(transcript_list)
        transcript = await asyncio.wait_for(
            asyncio.to_thread(transcript_object.fetch),
            timeout=YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS,
        )
        return _normalize_native_transcript(
            transcript=transcript,
            transcript_object=transcript_object,
            source_detail=source_detail,
            source_url=source_url,
        )
    except NativeTranscriptUnavailable:
        raise
    except asyncio.TimeoutError as exc:
        raise YouTubeIngestionError(
            "youtube_timeout",
            details="youtube_transcript_timeout",
            retryable=True,
            user_message=_TEMPORARY_TRANSCRIPT_MESSAGE,
        ) from exc
    except (NoTranscriptFound, TranscriptsDisabled) as exc:
        raise NativeTranscriptUnavailable(type(exc).__name__.lower()) from exc
    except (VideoUnavailable, VideoUnplayable, AgeRestricted) as exc:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details=type(exc).__name__,
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        ) from exc
    except (RequestBlocked, IpBlocked, YouTubeRequestFailed) as exc:
        raise YouTubeIngestionError(
            "youtube_transcript_fetch_failed",
            details=type(exc).__name__,
            retryable=True,
            user_message=_TEMPORARY_TRANSCRIPT_MESSAGE,
        ) from exc
    except CouldNotRetrieveTranscript as exc:
        error_message = str(exc)
        if _looks_like_unavailable_error(error_message):
            raise YouTubeIngestionError(
                "youtube_unavailable",
                details=type(exc).__name__,
                retryable=False,
                user_message=_UNAVAILABLE_MESSAGE,
            ) from exc
        raise YouTubeIngestionError(
            "youtube_transcript_fetch_failed",
            details=type(exc).__name__,
            retryable=True,
            user_message=_TEMPORARY_TRANSCRIPT_MESSAGE,
        ) from exc
    except Exception as exc:
        if _looks_like_unavailable_error(str(exc)):
            raise YouTubeIngestionError(
                "youtube_unavailable",
                details=type(exc).__name__,
                retryable=False,
                user_message=_UNAVAILABLE_MESSAGE,
            ) from exc
        raise YouTubeIngestionError(
            "youtube_transcript_fetch_failed",
            details=type(exc).__name__,
            retryable=True,
            user_message=_TEMPORARY_TRANSCRIPT_MESSAGE,
        ) from exc


def _is_valid_http_url(value: str) -> bool:
    candidate = (value or "").strip().lower()
    return candidate.startswith("http://") or candidate.startswith("https://")


def _select_audio_stream(info: Dict[str, Any]) -> Dict[str, Any]:
    candidates: list[Dict[str, Any]] = []

    direct_url = info.get("url")
    if isinstance(direct_url, str) and _is_valid_http_url(direct_url):
        candidates.append(info)

    requested_downloads = info.get("requested_downloads")
    if isinstance(requested_downloads, list):
        for item in requested_downloads:
            if isinstance(item, dict):
                candidates.append(item)

    requested_formats = info.get("requested_formats")
    if isinstance(requested_formats, list):
        for item in requested_formats:
            if isinstance(item, dict):
                candidates.append(item)

    formats = info.get("formats")
    if isinstance(formats, list):
        for item in formats:
            if isinstance(item, dict):
                candidates.append(item)

    best_candidate = None
    best_score: tuple[float, float, float] | None = None

    for candidate in candidates:
        url = candidate.get("url")
        if not isinstance(url, str) or not _is_valid_http_url(url):
            continue

        protocol = str(candidate.get("protocol") or "").strip().lower()
        if protocol and protocol not in _AUDIO_URL_PROTOCOLS:
            continue

        acodec = str(candidate.get("acodec") or "").strip().lower()
        if acodec in {"", "none"}:
            continue

        vcodec = str(candidate.get("vcodec") or "").strip().lower()
        is_audio_only = 1.0 if vcodec in {"", "none"} else 0.0
        abr = float(candidate.get("abr") or 0.0)
        tbr = float(candidate.get("tbr") or 0.0)
        score = (is_audio_only, abr, tbr)
        if best_score is None or score > best_score:
            best_candidate = candidate
            best_score = score

    if best_candidate is None:
        raise YouTubeIngestionError(
            "youtube_audio_fallback_failed",
            details="no_transcribable_audio_url",
            retryable=False,
            user_message=_TEMPORARY_AUDIO_MESSAGE,
        )

    return best_candidate


async def _resolve_audio_fallback(
    *,
    normalized_url: str,
    video_id: str,
) -> Dict[str, Any]:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "bestaudio/best",
        "socket_timeout": YTDLP_TIMEOUT_SECONDS,
    }

    def _extract() -> Dict[str, Any]:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(normalized_url, download=False)

    try:
        info = await asyncio.wait_for(
            asyncio.to_thread(_extract),
            timeout=YTDLP_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise YouTubeIngestionError(
            "youtube_audio_fallback_failed",
            details="yt_dlp_timeout",
            retryable=True,
            user_message=_TEMPORARY_AUDIO_MESSAGE,
        ) from exc
    except yt_dlp.utils.DownloadError as exc:
        if _looks_like_unavailable_error(str(exc)):
            raise YouTubeIngestionError(
                "youtube_unavailable",
                details="yt_dlp_unavailable",
                retryable=False,
                user_message=_UNAVAILABLE_MESSAGE,
            ) from exc
        raise YouTubeIngestionError(
            "youtube_audio_fallback_failed",
            details=type(exc).__name__,
            retryable=False,
            user_message=_TEMPORARY_AUDIO_MESSAGE,
        ) from exc
    except Exception as exc:
        if _looks_like_unavailable_error(str(exc)):
            raise YouTubeIngestionError(
                "youtube_unavailable",
                details=type(exc).__name__,
                retryable=False,
                user_message=_UNAVAILABLE_MESSAGE,
            ) from exc
        raise YouTubeIngestionError(
            "youtube_audio_fallback_failed",
            details=type(exc).__name__,
            retryable=True,
            user_message=_TEMPORARY_AUDIO_MESSAGE,
        ) from exc

    selected = _select_audio_stream(info)
    audio_url = str(selected.get("url") or "").strip()
    if not audio_url:
        raise YouTubeIngestionError(
            "youtube_audio_fallback_failed",
            details="missing_audio_url",
            retryable=False,
            user_message=_TEMPORARY_AUDIO_MESSAGE,
        )

    duration_value = selected.get("duration") or info.get("duration") or 0
    try:
        audio_duration_seconds = int(float(duration_value))
    except (TypeError, ValueError):
        audio_duration_seconds = 0

    return {
        "audio_url": audio_url,
        "audio_duration_seconds": audio_duration_seconds,
        "video_id": video_id,
        "format_id": selected.get("format_id"),
        "format_note": selected.get("format_note") or info.get("format_note"),
        "ext": selected.get("ext") or info.get("ext"),
    }


async def _upload_native_transcript(job_id: str, text: str) -> str:
    transcript_s3_key = f"{job_id}.txt"
    await s3.upload_file_object(
        bucket=TRANSCRIPT_BUCKET,
        key=transcript_s3_key,
        file_obj=BytesIO(text.encode("utf-8")),
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
            "minutes_used": 1,
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


def _build_native_extraction_metadata(
    *,
    video_id: str,
    source_url: str,
    native_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "extractor": _NATIVE_TRANSCRIPT_PROVIDER,
        "extractor_version": "v1",
        "selected_strategy": "native_transcript",
        "video_id": video_id,
        "source_url": source_url,
        "transcript_source_detail": native_result["source_detail"],
        "language_code": native_result.get("language_code"),
        "segments_count": native_result.get("segments_count"),
        "fetched_at": native_result["fetched_at"],
        "native_transcript_fallback_reason": None,
    }


def _build_native_transcription_metadata(
    *,
    native_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "provider": "native_transcript",
        "model_used": _NATIVE_TRANSCRIPT_PROVIDER,
        "language": native_result.get("language"),
        "segments_count": native_result.get("segments_count"),
        "duration_seconds": 0,
        "source_url": native_result["source_url"],
        "transcribed_at": native_result["fetched_at"],
        "source_detail": native_result["source_detail"],
    }


def _build_audio_fallback_metadata(
    *,
    video_id: str,
    source_url: str,
    fallback_reason: str,
    audio_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "extractor": "yt_dlp",
        "extractor_version": _YTDLP_EXTRACTOR_VERSION,
        "selected_strategy": "audio_fallback",
        "video_id": video_id,
        "source_url": source_url,
        "audio_url": audio_result["audio_url"],
        "audio_duration_seconds": audio_result["audio_duration_seconds"],
        "native_transcript_fallback_reason": fallback_reason,
        "yt_dlp_format_id": audio_result.get("format_id"),
        "yt_dlp_format_note": audio_result.get("format_note"),
        "yt_dlp_ext": audio_result.get("ext"),
        "queued_at": _now_iso_utc(),
    }


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
        "extractor": "youtube_ingestion_worker",
        "extractor_version": "v1",
        "selected_strategy": "failed",
        "source_url": normalized_url,
        "video_id": video_id,
        "last_error_code": error.code,
        "failure_details": error.details or error.code,
        "failed_at": _now_iso_utc(),
    }
    job.mark_failed(
        error_message=error.user_message,
        error_step="youtube_ingestion",
    )
    await database_async.update_processing_job(job)


async def process_youtube_message(message_body: Dict[str, Any]) -> Dict[str, Any]:
    job_id = (message_body.get("job_id") or "").strip()
    normalized_url = (message_body.get("normalized_url") or "").strip()

    if not job_id:
        raise YouTubeIngestionError(
            "youtube_audio_fallback_failed",
            details="missing_job_id",
            retryable=False,
            user_message=_TEMPORARY_AUDIO_MESSAGE,
        )
    if not normalized_url:
        raise YouTubeIngestionError(
            "youtube_audio_fallback_failed",
            details="missing_normalized_url",
            retryable=False,
            user_message=_TEMPORARY_AUDIO_MESSAGE,
        )

    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        raise YouTubeIngestionError(
            "youtube_audio_fallback_failed",
            details=f"processing_job_not_found:{job_id}",
            retryable=False,
            user_message=_TEMPORARY_AUDIO_MESSAGE,
        )

    video_id = _extract_video_id(normalized_url)

    try:
        native_result = await _fetch_native_transcript(video_id, normalized_url)
    except NativeTranscriptUnavailable as exc:
        audio_result = await _resolve_audio_fallback(
            normalized_url=normalized_url,
            video_id=video_id,
        )
        extraction_metadata = _build_audio_fallback_metadata(
            video_id=video_id,
            source_url=normalized_url,
            fallback_reason=exc.reason,
            audio_result=audio_result,
        )
        job.extraction_metadata = extraction_metadata
        job.episode_url = audio_result["audio_url"]
        await database_async.update_processing_job(job)

        await sqs.send_message(
            queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
            message_body={
                "job_id": job.id,
                "user_id": message_body.get("user_id"),
                "user_email": message_body.get("user_email"),
                "audio_url": audio_result["audio_url"],
                "media_key": message_body.get("media_key"),
                "normalized_url": normalized_url,
                "episode_title": message_body.get("episode_title") or job.episode_title,
                "podcast_title": message_body.get("podcast_title") or job.podcast_title,
                "audio_duration_seconds": audio_result["audio_duration_seconds"],
            },
        )

        return {
            "mode": "deepgram_fallback",
            "job_id": job.id,
            "media_key": message_body.get("media_key"),
            "video_id": video_id,
            "fallback_reason": exc.reason,
        }

    transcript_s3_key = await _upload_native_transcript(job_id, native_result["text"])
    transcription_metadata = _build_native_transcription_metadata(
        native_result=native_result
    )
    job.set_transcription_location(transcript_s3_key)
    job.set_transcription_metadata(transcription_metadata)
    job.extraction_metadata = _build_native_extraction_metadata(
        video_id=video_id,
        source_url=normalized_url,
        native_result=native_result,
    )
    job.mark_completed()
    await database_async.update_processing_job(job)

    await _publish_success_event(
        job_id=job_id,
        media_key=message_body.get("media_key"),
        transcript_s3_key=transcript_s3_key,
        transcription_metadata=transcription_metadata,
    )

    return {
        "mode": "native_transcript",
        "job_id": job_id,
        "media_key": message_body.get("media_key"),
        "video_id": video_id,
        "source_detail": native_result["source_detail"],
    }


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

    receive_count = int(
        (message.get("Attributes") or {}).get("ApproximateReceiveCount", "1")
    )

    try:
        result = await process_youtube_message(body)
        if result["mode"] == "native_transcript":
            log_event(
                logger,
                logging.INFO,
                "transcription.completed",
                "YouTube native transcript completed",
                job_id=result["job_id"],
                media_item_id=result["job_id"],
                transcript_source="native_transcript",
                fallback_strategy=result["source_detail"],
            )
        else:
            log_event(
                logger,
                logging.INFO,
                "transcription.enqueued",
                "YouTube queued Deepgram fallback after native transcript miss",
                job_id=result["job_id"],
                media_item_id=result["job_id"],
                queue=DEEPGRAM_TRANSCRIPTION_QUEUE,
                transcript_source="deepgram",
                fallback_strategy=result["fallback_reason"],
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
            "youtube_audio_fallback_failed",
            details=f"unexpected:{type(exc).__name__}",
            retryable=False,
            user_message=_TEMPORARY_AUDIO_MESSAGE,
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
            receive_params = get_sqs_receive_params(visibility_timeout=300)
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
