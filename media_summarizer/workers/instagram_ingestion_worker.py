"""
Queue-first Instagram ingestion worker.

Pipeline:
- Consumes messages from INSTAGRAM_INGESTION_QUEUE
- Resolves the video download URL via GetInSaver API
- Queues the resolved audio URL to the Deepgram transcription queue
- Marks the processing job as extracting/transcribing along the way
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
import os
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

import httpx

from media_summarizer.utils import database_async, sqs
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

INSTAGRAM_INGESTION_QUEUE = os.environ.get(
    "INSTAGRAM_INGESTION_QUEUE", "instagram-ingestion-queue"
)
DEEPGRAM_TRANSCRIPTION_QUEUE = os.environ.get(
    "DEEPGRAM_TRANSCRIPTION_QUEUE", "deepgram-transcription-queue"
)
EPISODE_COMPLETION_EVENTS_QUEUE = os.environ.get(
    "EPISODE_COMPLETION_EVENTS_QUEUE", "episode-completion-events"
)
GETINSAVER_API_BASE_URL = os.environ.get(
    "GETINSAVER_API_BASE_URL", "https://getinsaver.com/api/v1"
).rstrip("/")
GETINSAVER_API_KEY = os.environ.get("GETINSAVER_API_KEY", "").strip()
GETINSAVER_TIMEOUT_SECONDS = float(
    os.environ.get("GETINSAVER_TIMEOUT_SECONDS", "20")
)
INSTAGRAM_WORKER_MAX_RETRIES = max(
    1, int(os.environ.get("INSTAGRAM_WORKER_MAX_RETRIES", "3"))
)

_IMAGE_DOWNLOAD_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
)

_DEFAULT_TEMPORARY_MESSAGE = (
    "Instagram media extraction is temporarily unavailable. Please retry."
)
_DEFAULT_UNAVAILABLE_MESSAGE = (
    "This Instagram post is unavailable or cannot be processed."
)
_DEFAULT_UNSUPPORTED_MESSAGE = (
    "Unable to extract transcribable media from this Instagram URL."
)


class InstagramIngestionError(Exception):
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


def _instagram_content_type_from_url(normalized_url: str) -> str:
    """Determine Instagram content type from URL path."""
    path = (urlsplit(normalized_url).path or "").lower()
    parts = [segment for segment in path.split("/") if segment]
    if not parts:
        raise InstagramIngestionError(
            "unsupported_content",
            details="empty_path",
            retryable=False,
            user_message=_DEFAULT_UNSUPPORTED_MESSAGE,
        )

    content_type = parts[0]
    if content_type == "reel":
        return "reel"
    if content_type == "p":
        return "post"
    if content_type == "tv":
        return "igtv"
    raise InstagramIngestionError(
        "unsupported_content",
        details=f"unrecognized_content_type:{content_type}",
        retryable=False,
        user_message=_DEFAULT_UNSUPPORTED_MESSAGE,
    )


def _looks_like_transcribable_download_url(candidate: str) -> bool:
    value = (candidate or "").strip()
    if not value.startswith(("http://", "https://")):
        return False
    path = (urlsplit(value).path or "").lower()
    return not path.endswith(_IMAGE_DOWNLOAD_EXTENSIONS)


def _extract_download_url(payload: Dict[str, Any]) -> str:
    """Extract the video download URL from GetInSaver response."""
    data = payload.get("data")
    if not isinstance(data, dict):
        raise InstagramIngestionError(
            "unsupported_content",
            details="missing_data_field",
            retryable=False,
            user_message=_DEFAULT_UNSUPPORTED_MESSAGE,
        )

    provider_media_type = str(data.get("type") or "").strip().lower()
    if provider_media_type in {"image", "photo"}:
        raise InstagramIngestionError(
            "unsupported_content",
            details="image_content_not_transcribable",
            retryable=False,
            user_message=_DEFAULT_UNSUPPORTED_MESSAGE,
        )

    downloads = data.get("downloads")
    if not isinstance(downloads, list) or not downloads:
        raise InstagramIngestionError(
            "unsupported_content",
            details="no_downloads_available",
            retryable=False,
            user_message=_DEFAULT_UNSUPPORTED_MESSAGE,
        )

    for item in downloads:
        if not isinstance(item, dict):
            continue
        candidate = item.get("url")
        if isinstance(candidate, str) and _looks_like_transcribable_download_url(
            candidate
        ):
            return candidate.strip()

    raise InstagramIngestionError(
        "unsupported_content",
        details="no_transcribable_download_url",
        retryable=False,
        user_message=_DEFAULT_UNSUPPORTED_MESSAGE,
    )


async def _resolve_instagram_download_url(
    normalized_url: str,
) -> tuple[str, Dict[str, Any]]:
    """Call GetInSaver API to resolve the video download URL."""
    content_type = _instagram_content_type_from_url(normalized_url)
    endpoint = f"{GETINSAVER_API_BASE_URL}/download/instagram"

    if not GETINSAVER_API_KEY:
        raise InstagramIngestionError(
            "auth_failed",
            details="missing_getinsaver_api_key",
            retryable=False,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )

    headers = {
        "Authorization": f"Bearer {GETINSAVER_API_KEY}",
        "Content-Type": "application/json",
    }
    request_payload = {
        "url": normalized_url,
        "type": content_type,
    }

    try:
        async with httpx.AsyncClient(timeout=GETINSAVER_TIMEOUT_SECONDS) as client:
            response = await client.post(
                endpoint,
                json=request_payload,
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise InstagramIngestionError(
            "provider_timeout",
            details=type(exc).__name__,
            retryable=True,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        ) from exc
    except httpx.TransportError as exc:
        raise InstagramIngestionError(
            "provider_transport_error",
            details=type(exc).__name__,
            retryable=True,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        ) from exc

    try:
        response_payload = response.json()
    except ValueError:
        response_payload = {}
    if not isinstance(response_payload, dict):
        response_payload = {}

    status_code = response.status_code
    if status_code in {400, 404, 422}:
        raise InstagramIngestionError(
            "unsupported_content",
            details=f"provider_status:{status_code}",
            retryable=False,
            user_message=_DEFAULT_UNAVAILABLE_MESSAGE,
        )
    if status_code in {401, 403}:
        raise InstagramIngestionError(
            "auth_failed",
            details=f"provider_status:{status_code}",
            retryable=False,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )
    if status_code == 429:
        raise InstagramIngestionError(
            "rate_limited",
            details="provider_status:429",
            retryable=True,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )
    if status_code >= 500:
        raise InstagramIngestionError(
            "provider_error",
            details=f"provider_status:{status_code}",
            retryable=True,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )
    if status_code >= 300:
        raise InstagramIngestionError(
            "unsupported_content",
            details=f"provider_status:{status_code}",
            retryable=False,
            user_message=_DEFAULT_UNAVAILABLE_MESSAGE,
        )

    if response_payload.get("success") is False:
        raise InstagramIngestionError(
            "unsupported_content",
            details="provider_success_false",
            retryable=False,
            user_message=_DEFAULT_UNAVAILABLE_MESSAGE,
        )

    download_url = _extract_download_url(response_payload)
    provider_metadata = {
        "instagram_content_type": content_type,
        "provider_media_type": (
            response_payload.get("data", {}).get("type")
            if isinstance(response_payload.get("data"), dict)
            else None
        ),
    }
    return download_url, provider_metadata


def _build_extraction_metadata(
    *,
    source_url: str,
    download_url: Optional[str] = None,
    content_type: Optional[str] = None,
    provider_metadata: Optional[Dict[str, Any]] = None,
    last_error_code: Optional[str] = None,
    failure_details: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "source_platform": "instagram",
        "extractor": "instagram_ingestion_worker",
        "extractor_version": "v1",
        "provider": "getinsaver",
        "source_url": source_url,
        "resolved_url": download_url,
        "instagram_content_type": content_type,
        "provider_media_type": (
            provider_metadata.get("provider_media_type")
            if provider_metadata
            else None
        ),
        "last_error_code": last_error_code,
        "failure_details": failure_details,
        "resolved_at": _now_iso_utc(),
    }


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
    normalized_url: str,
    error: InstagramIngestionError,
) -> None:
    if not job_id:
        return

    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        return

    job.extraction_metadata = _build_extraction_metadata(
        source_url=normalized_url,
        last_error_code=error.code,
        failure_details=error.details or error.code,
    )
    job.extraction_metadata["failed_at"] = _now_iso_utc()
    job.mark_failed(
        error_message=error.user_message,
        error_step="instagram_ingestion",
    )
    await database_async.update_processing_job(job)


async def process_instagram_message(message_body: Dict[str, Any]) -> Dict[str, Any]:
    """Process an Instagram ingestion message: resolve download URL and queue to Deepgram."""
    job_id = (message_body.get("job_id") or "").strip()
    normalized_url = (message_body.get("normalized_url") or "").strip()

    if not job_id:
        raise InstagramIngestionError(
            "invalid_message",
            details="missing_job_id",
            retryable=False,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )
    if not normalized_url:
        raise InstagramIngestionError(
            "invalid_message",
            details="missing_normalized_url",
            retryable=False,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )

    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        raise InstagramIngestionError(
            "invalid_message",
            details=f"processing_job_not_found:{job_id}",
            retryable=False,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )

    job.mark_downloading()
    await database_async.update_processing_job(job)

    download_url, provider_metadata = await _resolve_instagram_download_url(
        normalized_url
    )

    content_type = provider_metadata.get("instagram_content_type")
    extraction_metadata = _build_extraction_metadata(
        source_url=normalized_url,
        download_url=download_url,
        content_type=content_type,
        provider_metadata=provider_metadata,
    )

    job.extraction_metadata = extraction_metadata
    job.media_url = download_url
    job.mark_transcribing()
    await database_async.update_processing_job(job)

    await sqs.send_message(
        queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
        message_body={
            "job_id": job.id,
            "user_id": message_body.get("user_id"),
            "audio_url": download_url,
            "media_key": message_body.get("media_key"),
            "normalized_url": normalized_url,
            "episode_title": (
                message_body.get("episode_title")
                or job.title
                or "Instagram video"
            ),
            "podcast_title": message_body.get("podcast_title") or "Instagram",
            "audio_duration_seconds": 0,
        },
    )

    return {
        "job_id": job_id,
        "media_key": message_body.get("media_key"),
        "download_url": download_url,
        "content_type": content_type,
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
            "Invalid JSON in Instagram ingestion message",
            queue=INSTAGRAM_INGESTION_QUEUE,
            exc_info=exc,
        )
        return

    context_token = bind_log_context(
        job_id=body.get("job_id"),
        media_item_id=body.get("job_id"),
        queue=INSTAGRAM_INGESTION_QUEUE,
        resolver_key="instagram.default",
        source_platform="instagram",
        provider="getinsaver",
    )

    receive_count = int(
        (message.get("Attributes") or {}).get("ApproximateReceiveCount", "1")
    )

    try:
        result = await process_instagram_message(body)
        log_event(
            logger,
            logging.INFO,
            "transcription.enqueued",
            "Instagram video resolved and queued for Deepgram transcription",
            job_id=result["job_id"],
            media_item_id=result["job_id"],
            queue=DEEPGRAM_TRANSCRIPTION_QUEUE,
            transcript_source="deepgram",
            instagram_content_type=result.get("content_type"),
        )
    except InstagramIngestionError as exc:
        should_retry = exc.retryable and receive_count < INSTAGRAM_WORKER_MAX_RETRIES
        if should_retry:
            raise

        await _mark_job_failed(
            job_id=body.get("job_id"),
            normalized_url=(body.get("normalized_url") or "").strip(),
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
            "Instagram ingestion failed",
            job_id=body.get("job_id"),
            media_item_id=body.get("job_id"),
            error_code=exc.code,
            detail=exc.details,
        )
    except Exception as exc:
        if receive_count < INSTAGRAM_WORKER_MAX_RETRIES:
            raise

        final_error = InstagramIngestionError(
            "provider_error",
            details=f"unexpected:{type(exc).__name__}",
            retryable=False,
            user_message=_DEFAULT_TEMPORARY_MESSAGE,
        )
        await _mark_job_failed(
            job_id=body.get("job_id"),
            normalized_url=(body.get("normalized_url") or "").strip(),
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
            "Instagram ingestion failed after retries",
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
        "Starting Instagram ingestion worker",
        queue=INSTAGRAM_INGESTION_QUEUE,
    )
    while True:
        try:
            receive_params = get_sqs_receive_params(visibility_timeout=300)
            messages = await sqs.receive_messages(
                queue_name=INSTAGRAM_INGESTION_QUEUE,
                max_messages=receive_params["MaxNumberOfMessages"],
                wait_time_seconds=receive_params["WaitTimeSeconds"],
                visibility_timeout=receive_params["VisibilityTimeout"],
            )
            if messages:
                for message in messages:
                    await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        queue_name=INSTAGRAM_INGESTION_QUEUE,
                        max_retries=INSTAGRAM_WORKER_MAX_RETRIES,
                        worker_name="instagram_ingestion",
                    )
            else:
                await asyncio.sleep(1)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "worker.polling_error",
                "Instagram ingestion polling failed",
                queue=INSTAGRAM_INGESTION_QUEUE,
                exc_info=exc,
            )
            await asyncio.sleep(5)


async def main() -> None:
    setup_logging("instagram-ingestion-worker")
    await poll_queue()


if __name__ == "__main__":
    asyncio.run(main())
