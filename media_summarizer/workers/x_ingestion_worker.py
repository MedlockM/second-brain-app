"""
Queue-first X/Twitter post ingestion worker.

Pipeline:
- Consumes messages from X_INGESTION_QUEUE
- Calls the X API v2 lookup endpoint for a public post
- Uploads transcript text to S3 and publishes completion events on success
- Persists transcription/extraction metadata on the processing job
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from io import BytesIO
import os
from typing import Any, Dict, Optional
from urllib.parse import unquote

import httpx

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
    "TRANSCRIPT_BUCKET", "media-summarizer-transcripts"
)
X_INGESTION_QUEUE = os.environ.get("X_INGESTION_QUEUE", "x-ingestion-queue")
EPISODE_COMPLETION_EVENTS_QUEUE = os.environ.get(
    "EPISODE_COMPLETION_EVENTS_QUEUE", "episode-completion-events"
)
X_API_TIMEOUT_SECONDS = float(os.environ.get("X_API_TIMEOUT_SECONDS", "20"))
X_WORKER_MAX_RETRIES = max(1, int(os.environ.get("X_WORKER_MAX_RETRIES", "3")))
X_API_BASE_URL = os.environ.get("X_API_BASE_URL", "https://api.x.com/2").rstrip("/")
_RAW_X_BEARER_TOKEN = os.environ.get("X_API_BEARER_TOKEN", "").strip()
X_API_BEARER_TOKEN = unquote(_RAW_X_BEARER_TOKEN).strip()

_DEFAULT_TEMPORARY_MESSAGE = "X post lookup is temporarily unavailable. Please retry."
_DEFAULT_UNAVAILABLE_MESSAGE = "This X post is unavailable or cannot be processed."
_DEFAULT_CREDITS_MESSAGE = (
    "X API credits are depleted for lookup requests. Please recharge and retry."
)
_LOOKUP_QUERY_PARAMS = {
    "tweet.fields": (
        "created_at,author_id,conversation_id,lang,public_metrics,entities,note_tweet"
    ),
    "expansions": "author_id",
    "user.fields": "username,name",
}


class XIngestionError(Exception):
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
        self.user_message = user_message or _DEFAULT_TEMPORARY_MESSAGE


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _word_count(text: str) -> int:
    return len([token for token in text.split() if token.strip()])


def _first_line(text: str) -> str:
    for line in text.splitlines():
        value = " ".join(line.split()).strip()
        if value:
            return value
    return ""


def _truncate(text: str, limit: int) -> str:
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def _lookup_headers() -> Dict[str, str]:
    if not X_API_BEARER_TOKEN:
        raise XIngestionError(
            "x_lookup_auth_failed",
            details="missing_bearer_token",
            retryable=False,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )
    return {"Authorization": f"Bearer {X_API_BEARER_TOKEN}"}


def _extract_text(tweet_payload: Dict[str, Any]) -> str:
    note_tweet = tweet_payload.get("note_tweet")
    if isinstance(note_tweet, dict):
        note_text = str(note_tweet.get("text") or "").strip()
        if note_text:
            return note_text
    return str(tweet_payload.get("text") or "").strip()


def _user_by_author_id(payload: Dict[str, Any], author_id: str) -> Dict[str, Any]:
    includes = payload.get("includes")
    if not isinstance(includes, dict):
        return {}
    users = includes.get("users")
    if not isinstance(users, list):
        return {}
    for user in users:
        if isinstance(user, dict) and str(user.get("id") or "").strip() == author_id:
            return user
    return {}


async def _lookup_post(tweet_id: str) -> Dict[str, Any]:
    endpoint = f"{X_API_BASE_URL}/tweets/{tweet_id}"
    headers = _lookup_headers()

    try:
        async with httpx.AsyncClient(timeout=X_API_TIMEOUT_SECONDS) as client:
            response = await client.get(
                endpoint,
                params=_LOOKUP_QUERY_PARAMS,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise XIngestionError(
            "x_lookup_timeout",
            details=type(exc).__name__,
            retryable=True,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        ) from exc
    except httpx.TransportError as exc:
        raise XIngestionError(
            "x_lookup_failed",
            details=type(exc).__name__,
            retryable=True,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        ) from exc

    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    status_code = response.status_code
    detail = str(payload.get("detail") or payload.get("title") or "").strip()

    if status_code == 404:
        raise XIngestionError(
            "x_lookup_not_found",
            details=detail or "status=404",
            retryable=False,
            user_message=_DEFAULT_UNAVAILABLE_MESSAGE,
        )
    if status_code == 401:
        raise XIngestionError(
            "x_lookup_auth_failed",
            details=detail or "status=401",
            retryable=False,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )
    if status_code == 402:
        raise XIngestionError(
            "x_lookup_credits_depleted",
            details=detail or "status=402",
            retryable=False,
            user_message=_DEFAULT_CREDITS_MESSAGE,
        )
    if status_code == 403:
        raise XIngestionError(
            "x_lookup_forbidden",
            details=detail or "status=403",
            retryable=False,
            user_message=_DEFAULT_UNAVAILABLE_MESSAGE,
        )
    if status_code == 429:
        raise XIngestionError(
            "x_lookup_rate_limited",
            details=detail or "status=429",
            retryable=True,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )
    if status_code >= 500:
        raise XIngestionError(
            "x_lookup_failed",
            details=detail or f"status={status_code}",
            retryable=True,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )
    if status_code >= 400:
        raise XIngestionError(
            "x_lookup_failed",
            details=detail or f"status={status_code}",
            retryable=False,
            user_message=_DEFAULT_UNAVAILABLE_MESSAGE,
        )

    data = payload.get("data")
    if not isinstance(data, dict):
        raise XIngestionError(
            "x_lookup_invalid_payload",
            details="missing_data",
            retryable=False,
            user_message=_DEFAULT_UNAVAILABLE_MESSAGE,
        )

    text = _extract_text(data)
    if not text:
        raise XIngestionError(
            "x_lookup_empty",
            details="empty_text",
            retryable=False,
            user_message=_DEFAULT_UNAVAILABLE_MESSAGE,
        )

    author_id = str(data.get("author_id") or "").strip()
    author = _user_by_author_id(payload, author_id) if author_id else {}
    username = str(author.get("username") or "").strip() or None
    author_name = str(author.get("name") or "").strip() or None

    return {
        "tweet_id": str(data.get("id") or tweet_id).strip(),
        "conversation_id": str(data.get("conversation_id") or "").strip() or None,
        "author_id": author_id or None,
        "author_username": username,
        "author_name": author_name,
        "created_at": str(data.get("created_at") or "").strip() or None,
        "lang": str(data.get("lang") or "").strip() or None,
        "public_metrics": data.get("public_metrics")
        if isinstance(data.get("public_metrics"), dict)
        else {},
        "text": text,
        "fetched_at": _now_iso_utc(),
    }


async def _upload_transcript(job_id: str, text: str) -> str:
    transcript_s3_key = f"{job_id}.txt"
    await s3.upload_file_object(
        bucket=TRANSCRIPT_BUCKET,
        key=transcript_s3_key,
        file_obj=BytesIO(text.encode("utf-8")),
        content_type="text/plain",
        metadata={
            "content-type": "text/plain",
            "job-type": "x-post-transcription",
            "provider": "x-api-lookup",
        },
    )
    return transcript_s3_key


def _build_titles(lookup_result: Dict[str, Any]) -> tuple[str, str]:
    username = str(lookup_result.get("author_username") or "").strip()
    podcast_title = f"X - @{username}" if username else "X post"
    first_line = _first_line(str(lookup_result.get("text") or ""))
    episode_title = _truncate(first_line, 120) if first_line else ""
    if not episode_title:
        episode_title = f"X post {lookup_result.get('tweet_id')}"
    return podcast_title, episode_title


def _build_extraction_metadata(
    *,
    requested_url: str,
    lookup_result: Dict[str, Any],
    last_error_code: Optional[str] = None,
    failure_details: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "source_platform": "x",
        "extractor": "x_ingestion_worker",
        "extractor_version": "v1",
        "tweet_id": lookup_result.get("tweet_id"),
        "conversation_id": lookup_result.get("conversation_id"),
        "author_id": lookup_result.get("author_id"),
        "author_username": lookup_result.get("author_username"),
        "author_name": lookup_result.get("author_name"),
        "created_at": lookup_result.get("created_at"),
        "lang": lookup_result.get("lang"),
        "public_metrics": lookup_result.get("public_metrics") or {},
        "requested_url": requested_url,
        "fetched_at": lookup_result.get("fetched_at") or _now_iso_utc(),
        "last_error_code": last_error_code,
        "failure_details": failure_details,
    }


async def _publish_success_event(
    *,
    job_id: str,
    media_key: Optional[str],
    transcript_s3_key: str,
    transcription_metadata: Dict[str, Any],
) -> None:
    await sqs.send_message(
        queue_name=EPISODE_COMPLETION_EVENTS_QUEUE,
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
        queue_name=EPISODE_COMPLETION_EVENTS_QUEUE,
        message_body={
            "event_type": "episode_completion_status",
            "status": "failure",
            "media_key": media_key,
            "canonical_job_id": job_id,
            "reason": reason,
        },
    )


async def _mark_job_failed(
    *,
    job_id: Optional[str],
    requested_url: str,
    tweet_id: Optional[str],
    error: XIngestionError,
) -> None:
    if not job_id:
        return

    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        return

    failed_lookup = {
        "tweet_id": tweet_id,
        "conversation_id": None,
        "author_id": None,
        "author_username": None,
        "author_name": None,
        "created_at": None,
        "lang": None,
        "public_metrics": {},
        "fetched_at": _now_iso_utc(),
    }
    job.extraction_metadata = _build_extraction_metadata(
        requested_url=requested_url,
        lookup_result=failed_lookup,
        last_error_code=error.code,
        failure_details=error.details or error.code,
    )
    job.extraction_metadata["failed_at"] = _now_iso_utc()
    job.mark_failed(
        error_message=error.user_message,
        error_step="x_ingestion",
    )
    await database_async.update_processing_job(job)


async def process_x_message(message_body: Dict[str, Any]) -> Dict[str, Any]:
    job_id = (message_body.get("job_id") or "").strip()
    normalized_url = (message_body.get("normalized_url") or "").strip()
    tweet_id = (message_body.get("tweet_id") or "").strip()

    if not job_id:
        raise XIngestionError(
            "x_lookup_failed",
            details="missing_job_id",
            retryable=False,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )
    if not normalized_url:
        raise XIngestionError(
            "x_lookup_failed",
            details="missing_normalized_url",
            retryable=False,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )
    if not tweet_id:
        raise XIngestionError(
            "x_lookup_failed",
            details="missing_tweet_id",
            retryable=False,
            user_message=_DEFAULT_UNAVAILABLE_MESSAGE,
        )

    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        raise XIngestionError(
            "x_lookup_failed",
            details=f"processing_job_not_found:{job_id}",
            retryable=False,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )

    job.mark_transcribing()
    await database_async.update_processing_job(job)

    lookup_result = await _lookup_post(tweet_id)
    transcript_text = str(lookup_result["text"]).strip()
    transcript_s3_key = await _upload_transcript(job_id, transcript_text)

    podcast_title, episode_title = _build_titles(lookup_result)
    transcription_metadata = {
        "provider": "x_api_lookup",
        "model_used": "x_api_v2",
        "language": lookup_result.get("lang"),
        "segments_count": _word_count(transcript_text),
        "duration_seconds": 0,
        "source_url": normalized_url,
    }
    extraction_metadata = _build_extraction_metadata(
        requested_url=normalized_url,
        lookup_result=lookup_result,
    )

    job.podcast_title = podcast_title
    job.episode_title = episode_title
    job.set_transcription_location(transcript_s3_key)
    job.set_transcription_metadata(transcription_metadata)
    job.extraction_metadata = extraction_metadata
    job.mark_completed()
    await database_async.update_processing_job(job)

    return {
        "job_id": job_id,
        "media_key": message_body.get("media_key"),
        "transcript_s3_key": transcript_s3_key,
        "transcription_metadata": transcription_metadata,
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
            "Invalid JSON in X ingestion message",
            queue=X_INGESTION_QUEUE,
            exc_info=exc,
        )
        return

    context_token = bind_log_context(
        job_id=body.get("job_id"),
        media_item_id=body.get("job_id"),
        queue=X_INGESTION_QUEUE,
        resolver_key=body.get("resolver_key") or "x.default",
        source_platform=body.get("source_platform") or "x",
        provider="x_api_lookup",
        transcript_source="x_api_lookup",
    )

    receive_count = int(
        (message.get("Attributes") or {}).get("ApproximateReceiveCount", "1")
    )

    try:
        result = await process_x_message(body)
        await _publish_success_event(
            job_id=result["job_id"],
            media_key=result.get("media_key"),
            transcript_s3_key=result["transcript_s3_key"],
            transcription_metadata=result["transcription_metadata"],
        )
        log_event(
            logger,
            logging.INFO,
            "transcription.completed",
            "X post ingestion completed",
            transcript_source="x_api_lookup",
            job_id=result["job_id"],
            media_item_id=result["job_id"],
        )
    except XIngestionError as exc:
        should_retry = exc.retryable and receive_count < X_WORKER_MAX_RETRIES
        if should_retry:
            raise

        await _mark_job_failed(
            job_id=body.get("job_id"),
            requested_url=(body.get("normalized_url") or "").strip(),
            tweet_id=(body.get("tweet_id") or "").strip() or None,
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
            "X post ingestion failed",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            transcript_source="x_api_lookup",
            error_code=exc.code,
            detail=exc.details,
        )
    except Exception as exc:
        if receive_count < X_WORKER_MAX_RETRIES:
            raise

        final_error = XIngestionError(
            "x_lookup_failed",
            details=f"unexpected:{type(exc).__name__}",
            retryable=False,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )
        await _mark_job_failed(
            job_id=body.get("job_id"),
            requested_url=(body.get("normalized_url") or "").strip(),
            tweet_id=(body.get("tweet_id") or "").strip() or None,
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
            "X post ingestion failed after retries",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            transcript_source="x_api_lookup",
            error_code=final_error.code,
            exc_info=exc,
        )
    finally:
        reset_log_context(context_token)


async def process_messages_batch(messages: list[Dict[str, Any]]) -> None:
    async def process_one(message: Dict[str, Any]) -> bool:
        return await process_message_with_retry(
            message=message,
            processor=process_message,
            queue_name=X_INGESTION_QUEUE,
            max_retries=X_WORKER_MAX_RETRIES,
            worker_name="x-ingestion",
        )

    tasks = [asyncio.create_task(process_one(message)) for message in messages]
    await asyncio.gather(*tasks, return_exceptions=True)


async def poll_queue() -> None:
    log_event(
        logger,
        logging.INFO,
        "worker.started",
        "Starting X ingestion worker",
        queue=X_INGESTION_QUEUE,
    )
    while True:
        try:
            receive_params = get_sqs_receive_params(visibility_timeout=300)
            messages = await sqs.receive_messages(
                queue_name=X_INGESTION_QUEUE,
                max_messages=receive_params["MaxNumberOfMessages"],
                wait_time_seconds=receive_params["WaitTimeSeconds"],
                visibility_timeout=receive_params["VisibilityTimeout"],
            )
            if messages:
                await process_messages_batch(messages)
            else:
                await asyncio.sleep(1)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "X ingestion polling failed",
                queue=X_INGESTION_QUEUE,
                exc_info=exc,
            )
            await asyncio.sleep(5)


async def main() -> None:
    setup_logging("x-ingestion-worker")
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
