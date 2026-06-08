"""
Deepgram transcription worker.

Active transcription path:
- Consumes messages from DEEPGRAM_TRANSCRIPTION_QUEUE
- Reads audio_url from message payload
- Sends Deepgram a pre-recorded URL payload
- Uploads transcript to S3
- Publishes episode completion status events
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import time
from io import BytesIO
from math import ceil
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from media_summarizer.utils import s3, sqs
from media_summarizer.utils.logging_config import (
    bind_log_context,
    log_event,
    reset_log_context,
    setup_logging,
)
from media_summarizer.core.services.minute_pool import finalize_usage
from media_summarizer.workers.base_worker import process_message_with_retry

logger = logging.getLogger(__name__)


class NonRetryableDeepgramError(Exception):
    """Raised for non-retryable Deepgram request failures."""


class RetryableDeepgramError(Exception):
    """Raised for transient/retryable Deepgram request failures."""


TRANSCRIPT_BUCKET = os.environ.get(
    "TRANSCRIPT_BUCKET", "media-summarizer-transcripts"
)
AUDIO_BUCKET = os.environ.get("AUDIO_BUCKET", "media-summarizer-audio")
EPISODE_COMPLETION_EVENTS_QUEUE = os.environ.get(
    "EPISODE_COMPLETION_EVENTS_QUEUE", "episode-completion-events"
)
EPISODE_COMPLETED_EVENTS_QUEUE = os.environ.get(
    "EPISODE_COMPLETED_EVENTS_QUEUE", "episode-completed-events"
)
DEEPGRAM_TRANSCRIPTION_QUEUE = os.environ.get(
    "DEEPGRAM_TRANSCRIPTION_QUEUE", "deepgram-transcription-queue"
)

# Worker retry handling (SQS-level via base worker)
WORKER_MAX_RETRIES = int(os.environ.get("DEEPGRAM_WORKER_MAX_RETRIES", "3"))

# Deepgram API configuration
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
DEEPGRAM_API_URL = os.environ.get(
    "DEEPGRAM_API_URL", "https://api.deepgram.com/v1/listen"
)
DEEPGRAM_MODEL = os.environ.get("DEEPGRAM_MODEL", "nova-3")
DEEPGRAM_TIMEOUT_SECONDS = float(os.environ.get("DEEPGRAM_TIMEOUT_SECONDS", "300"))
DEEPGRAM_API_RETRIES = int(os.environ.get("DEEPGRAM_API_RETRIES", "3"))

DEEPGRAM_DETECT_LANGUAGE = os.environ.get("DEEPGRAM_DETECT_LANGUAGE", "true").lower() == "true"
DEEPGRAM_SMART_FORMAT = os.environ.get("DEEPGRAM_SMART_FORMAT", "true").lower() == "true"
DEEPGRAM_PUNCTUATE = os.environ.get("DEEPGRAM_PUNCTUATE", "true").lower() == "true"
DEEPGRAM_PARAGRAPHS = os.environ.get("DEEPGRAM_PARAGRAPHS", "true").lower() == "true"
DEEPGRAM_UTTERANCES = os.environ.get("DEEPGRAM_UTTERANCES", "true").lower() == "true"

# Heartbeat/visibility settings
HEARTBEAT_INTERVAL = float(os.environ.get("HEARTBEAT_INTERVAL", "60"))
DEEPGRAM_VISIBILITY_TIMEOUT = int(
    os.environ.get("DEEPGRAM_VISIBILITY_TIMEOUT", "1800")
)


def _build_deepgram_query_params() -> Dict[str, str]:
    return {
        "model": DEEPGRAM_MODEL,
        "detect_language": str(DEEPGRAM_DETECT_LANGUAGE).lower(),
        "smart_format": str(DEEPGRAM_SMART_FORMAT).lower(),
        "punctuate": str(DEEPGRAM_PUNCTUATE).lower(),
        "paragraphs": str(DEEPGRAM_PARAGRAPHS).lower(),
        "utterances": str(DEEPGRAM_UTTERANCES).lower(),
    }


def _is_valid_http_url(value: str) -> bool:
    v = (value or "").strip().lower()
    return v.startswith("http://") or v.startswith("https://")


def _looks_like_feed_url(value: str) -> bool:
    raw = (value or "").strip().lower()
    if not raw:
        return False
    try:
        path = (urlsplit(raw).path or "").lower()
    except ValueError:
        path = raw
    return path.endswith(".rss") or path.endswith(".xml")


async def upload_transcription(transcript_s3_key: str, transcription_text: str) -> None:
    transcript_file = BytesIO(transcription_text.encode("utf-8"))
    await s3.upload_file_object(
        bucket=TRANSCRIPT_BUCKET,
        key=transcript_s3_key,
        file_obj=transcript_file,
        content_type="text/plain",
        metadata={
            "content-type": "text/plain",
            "job-type": "podcast-transcription",
            "provider": "deepgram",
            "model": DEEPGRAM_MODEL,
        },
    )
    log_event(
        logger,
        logging.DEBUG,
        "external_call.succeeded",
        "Uploaded Deepgram transcription",
        provider="s3",
        transcript_source="deepgram",
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(DEEPGRAM_API_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(
        (RetryableDeepgramError, httpx.TimeoutException, httpx.TransportError)
    ),
)
async def call_deepgram_api(*, audio_url: str, job_id: str) -> Dict[str, Any]:
    if not DEEPGRAM_API_KEY:
        raise NonRetryableDeepgramError("DEEPGRAM_API_KEY is required")

    if not _is_valid_http_url(audio_url):
        raise NonRetryableDeepgramError("audio_url must be a valid http(s) URL")
    if _looks_like_feed_url(audio_url):
        raise NonRetryableDeepgramError(
            "audio_url points to an RSS/feed URL; resolve enclosure URL before Deepgram"
        )

    query_params = _build_deepgram_query_params()
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "application/json",
    }

    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=DEEPGRAM_TIMEOUT_SECONDS) as client:
            response = await client.post(
                DEEPGRAM_API_URL,
                params=query_params,
                headers=headers,
                json={"url": audio_url},
            )
    except (httpx.TimeoutException, httpx.TransportError):
        raise

    latency_seconds = time.time() - started
    status = response.status_code

    if status in (401, 403, 400, 404, 415, 422):
        raise NonRetryableDeepgramError(
            f"Deepgram non-retryable HTTP {status}: {response.text[:500]}"
        )
    if status == 429 or status >= 500:
        raise RetryableDeepgramError(
            f"Deepgram transient HTTP {status}: {response.text[:500]}"
        )
    if status >= 300:
        raise NonRetryableDeepgramError(
            f"Deepgram unexpected HTTP {status}: {response.text[:500]}"
        )

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise NonRetryableDeepgramError(
            "Deepgram response is not valid JSON"
        ) from exc

    request_id = (payload.get("metadata") or {}).get("request_id")
    log_event(
        logger,
        logging.INFO,
        "external_call.succeeded",
        "Deepgram request succeeded",
        provider="deepgram",
        transcript_source="deepgram",
        job_id=job_id,
        status=status,
        duration_ms=int(latency_seconds * 1000),
        provider_request_id=request_id,
        audio_url=audio_url,
    )
    return payload


def _resolve_audio_content_type(
    *,
    content_mime_type: Optional[str],
    original_name: Optional[str],
) -> str:
    mime_type = (content_mime_type or "").strip().lower()
    if mime_type.startswith("audio/") or mime_type.startswith("video/"):
        return mime_type

    guessed, _ = mimetypes.guess_type((original_name or "").strip())
    guessed = (guessed or "").strip().lower()
    if guessed.startswith("audio/") or guessed.startswith("video/"):
        return guessed
    return "application/octet-stream"


@retry(
    reraise=True,
    stop=stop_after_attempt(DEEPGRAM_API_RETRIES),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(
        (RetryableDeepgramError, httpx.TimeoutException, httpx.TransportError)
    ),
)
async def call_deepgram_api_from_bytes(
    *,
    audio_bytes: bytes,
    content_type: str,
    job_id: str,
) -> Dict[str, Any]:
    if not DEEPGRAM_API_KEY:
        raise NonRetryableDeepgramError("DEEPGRAM_API_KEY is required")
    if not audio_bytes:
        raise NonRetryableDeepgramError("audio bytes must be non-empty")

    query_params = _build_deepgram_query_params()
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": content_type,
    }

    started = time.time()
    try:
        async with httpx.AsyncClient(timeout=DEEPGRAM_TIMEOUT_SECONDS) as client:
            response = await client.post(
                DEEPGRAM_API_URL,
                params=query_params,
                headers=headers,
                content=audio_bytes,
            )
    except (httpx.TimeoutException, httpx.TransportError):
        raise

    latency_seconds = time.time() - started
    status = response.status_code

    if status in (401, 403, 400, 404, 415, 422):
        raise NonRetryableDeepgramError(
            f"Deepgram non-retryable HTTP {status}: {response.text[:500]}"
        )
    if status == 429 or status >= 500:
        raise RetryableDeepgramError(
            f"Deepgram transient HTTP {status}: {response.text[:500]}"
        )
    if status >= 300:
        raise NonRetryableDeepgramError(
            f"Deepgram unexpected HTTP {status}: {response.text[:500]}"
        )

    try:
        payload = response.json()
    except json.JSONDecodeError as exc:
        raise NonRetryableDeepgramError(
            "Deepgram response is not valid JSON"
        ) from exc

    request_id = (payload.get("metadata") or {}).get("request_id")
    log_event(
        logger,
        logging.INFO,
        "external_call.succeeded",
        "Deepgram file-bytes request succeeded",
        provider="deepgram",
        transcript_source="deepgram",
        job_id=job_id,
        status=status,
        duration_ms=int(latency_seconds * 1000),
        provider_request_id=request_id,
        content_type=content_type,
        audio_size_bytes=len(audio_bytes),
    )
    return payload


def extract_transcript(payload: Dict[str, Any]) -> Dict[str, Any]:
    results = payload.get("results") or {}
    channels = results.get("channels") or []
    alternatives = (channels[0].get("alternatives") if channels else None) or []
    alt = alternatives[0] if alternatives else {}

    transcript_text = (alt.get("transcript") or "").strip()
    if not transcript_text:
        raise NonRetryableDeepgramError("Deepgram transcript is empty")

    utterances = results.get("utterances") or []
    words = alt.get("words") or []
    metadata = payload.get("metadata") or {}

    language = (
        alt.get("detected_language")
        or metadata.get("language")
        or "unknown"
    )
    segments_count = len(utterances) if utterances else len(words)

    return {
        "text": transcript_text,
        "language": language,
        "segments_count": segments_count,
        "request_id": metadata.get("request_id"),
    }


async def publish_failure_event(
    *,
    job_id: Optional[str],
    media_key: Optional[str],
    reason: str,
) -> None:
    if not job_id:
        return
    await sqs.send_message(
        queue_name=EPISODE_COMPLETION_EVENTS_QUEUE,
        message_body={
            "event_type": "episode_completion_status",
            "status": "failure",
            "media_key": media_key,
            "canonical_job_id": job_id,
            "reason": reason,
        },
    )


async def process_deepgram_message(message_body: Dict[str, Any]) -> None:
    job_id = message_body.get("job_id")
    audio_url = message_body.get("audio_url")
    audio_s3_key = message_body.get("audio_s3_key")

    if not job_id:
        raise NonRetryableDeepgramError("Missing required fields in transcription message")
    if not isinstance(job_id, str):
        raise NonRetryableDeepgramError("Invalid field types in transcription message")

    from media_summarizer.utils import database_async

    job = await database_async.get_processing_job_by_id(job_id)
    if job:
        job.mark_transcribing()
        await database_async.update_processing_job(job)

    if not audio_url and job:
        audio_url = getattr(job, "episode_url", None)
    if not audio_s3_key and job:
        audio_s3_key = getattr(job, "audio_s3_key", None)

    deepgram_payload: Dict[str, Any]
    started = time.time()
    if isinstance(audio_url, str) and audio_url.strip():
        deepgram_payload = await call_deepgram_api(
            audio_url=audio_url.strip(),
            job_id=job_id,
        )
    elif isinstance(audio_s3_key, str) and audio_s3_key.strip():
        audio_bytes = await s3.download_file_to_memory(AUDIO_BUCKET, audio_s3_key.strip())
        content_type = _resolve_audio_content_type(
            content_mime_type=message_body.get("content_mime_type"),
            original_name=message_body.get("original_name"),
        )
        deepgram_payload = await call_deepgram_api_from_bytes(
            audio_bytes=audio_bytes,
            content_type=content_type,
            job_id=job_id,
        )
    else:
        raise NonRetryableDeepgramError(
            "Missing required field: audio_url or audio_s3_key"
        )
    transcription_duration = time.time() - started

    transcript = extract_transcript(deepgram_payload)
    transcript_text = transcript["text"]
    transcript_s3_key = f"{job_id}.txt"
    await upload_transcription(transcript_s3_key, transcript_text)

    transcription_metadata = {
        "provider": "deepgram",
        "request_id": transcript.get("request_id"),
        "model_used": DEEPGRAM_MODEL,
        "language": transcript.get("language"),
        "segments_count": transcript.get("segments_count", 0),
        "duration_seconds": transcription_duration,
        "audio_url": audio_url.strip() if isinstance(audio_url, str) and audio_url.strip() else None,
        "audio_s3_key": audio_s3_key.strip()
        if isinstance(audio_s3_key, str) and audio_s3_key.strip()
        else None,
        "content_mime_type": message_body.get("content_mime_type"),
        "transcribed_at": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
        ),
    }

    if job:
        job.set_transcription_location(transcript_s3_key)
        job.set_transcription_metadata(transcription_metadata)
        job.set_processing_duration("transcription", int(transcription_duration))
        await database_async.update_processing_job(job)

    audio_duration_seconds_raw = message_body.get("audio_duration_seconds")
    try:
        audio_duration_seconds = int(float(audio_duration_seconds_raw))
    except (TypeError, ValueError):
        audio_duration_seconds = 0
    minutes_used = (
        max(1, ceil(audio_duration_seconds / 60))
        if audio_duration_seconds > 0
        else 1
    )

    await sqs.send_message(
        queue_name=EPISODE_COMPLETION_EVENTS_QUEUE,
        message_body={
            "event_type": "episode_completion_status",
            "status": "success",
            "media_key": message_body.get("media_key"),
            "canonical_job_id": job_id,
            "minutes_used": minutes_used,
            "transcription_s3_key": transcript_s3_key,
            "transcription_metadata": transcription_metadata,
        },
    )

    # Finalize minute usage for the canonical submitter after transcription succeeds.
    # This is the billing event tied to transcription (the expensive step).
    try:
        await finalize_usage(job_id, minutes_used)
    except Exception as e:
        log_event(
            logger,
            logging.WARNING,
            "billing.finalize_failed",
            "Failed to finalize minute usage after transcription",
            job_id=job_id,
            minutes_used=minutes_used,
            exc_info=e,
        )

    # Mark the canonical job as completed now that transcription is done.
    if job:
        job.mark_completed()
        await database_async.update_processing_job(job)

    # Publish episode_completed event for watcher fan-out via media_completed_worker.
    # This enables watchers of shared media keys to get their jobs finalized.
    try:
        await sqs.send_message(
            queue_name=EPISODE_COMPLETED_EVENTS_QUEUE,
            message_body={
                "event_type": "episode_completed",
                "media_key": message_body.get("media_key"),
                "canonical_job_id": job_id,
                "minutes_used": minutes_used,
                "transcription_s3_key": transcript_s3_key,
            },
        )
    except Exception as e:
        log_event(
            logger,
            logging.WARNING,
            "event.publish_failed",
            "Failed to publish episode_completed event for watcher fan-out",
            job_id=job_id,
            media_key=message_body.get("media_key"),
            exc_info=e,
        )

    log_event(
        logger,
        logging.INFO,
        "transcription.completed",
        "Deepgram transcription completed",
        provider="deepgram",
        transcript_source="deepgram",
        job_id=job_id,
        media_item_id=job_id,
    )


async def process_message(message: Dict[str, Any]) -> None:
    receipt_handle = message.get("ReceiptHandle")
    heartbeat_task: Optional[asyncio.Task] = None
    body: Dict[str, Any] = {}

    async def _heartbeat_loop() -> None:
        try:
            await sqs.change_message_visibility(
                queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
                receipt_handle=receipt_handle,
                timeout_seconds=DEEPGRAM_VISIBILITY_TIMEOUT,
            )
            while True:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                await sqs.change_message_visibility(
                    queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
                    receipt_handle=receipt_handle,
                    timeout_seconds=DEEPGRAM_VISIBILITY_TIMEOUT,
                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log_event(
                logger,
                logging.WARNING,
                "external_call.failed",
                "Deepgram heartbeat failed",
                provider="sqs",
                queue=DEEPGRAM_TRANSCRIPTION_QUEUE,
                exc_info=e,
            )

    try:
        body = json.loads(message.get("Body", "{}"))
        context_token = bind_log_context(
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            queue=DEEPGRAM_TRANSCRIPTION_QUEUE,
            provider="deepgram",
            transcript_source="deepgram",
        )
        if receipt_handle:
            heartbeat_task = asyncio.create_task(_heartbeat_loop())

        await process_deepgram_message(body)
    except NonRetryableDeepgramError as e:
        await publish_failure_event(
            job_id=body.get("job_id"),
            media_key=body.get("media_key"),
            reason=f"deepgram_non_retryable: {e}",
        )
        log_event(
            logger,
            logging.ERROR,
            "transcription.failed",
            "Deepgram transcription failed with non-retryable error",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            provider="deepgram",
            transcript_source="deepgram",
            error_code="deepgram_non_retryable",
            detail=str(e),
        )
        return
    except Exception as e:
        receive_count = int(
            (message.get("Attributes") or {}).get("ApproximateReceiveCount", "1")
        )
        if receive_count >= WORKER_MAX_RETRIES:
            try:
                await publish_failure_event(
                    job_id=body.get("job_id"),
                    media_key=body.get("media_key"),
                    reason=f"deepgram_failed_after_retries: {e}",
                )
            except Exception as publish_error:
                log_event(
                    logger,
                    logging.WARNING,
                    "external_call.failed",
                    "Failed to publish final Deepgram failure event",
                    provider="sqs",
                    queue=EPISODE_COMPLETION_EVENTS_QUEUE,
                    job_id=body.get("job_id"),
                    exc_info=publish_error,
                )
        raise
    finally:
        if "context_token" in locals():
            reset_log_context(context_token)
        if heartbeat_task:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass


async def poll_queue() -> None:
    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting Deepgram transcription worker",
        queue=DEEPGRAM_TRANSCRIPTION_QUEUE,
        provider="deepgram",
    )

    while True:
        try:
            messages = await sqs.receive_messages(
                queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
                max_messages=1,
                wait_time_seconds=20,
                visibility_timeout=DEEPGRAM_VISIBILITY_TIMEOUT,
            )
            if messages:
                for message in messages:
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
                        max_retries=WORKER_MAX_RETRIES,
                        worker_name="deepgram_transcription",
                    )
            await asyncio.sleep(1)
        except Exception as e:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "Deepgram queue polling failed",
                queue=DEEPGRAM_TRANSCRIPTION_QUEUE,
                provider="deepgram",
                exc_info=e,
            )
            await asyncio.sleep(5)


async def main() -> None:
    setup_logging("deepgram-worker")
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
