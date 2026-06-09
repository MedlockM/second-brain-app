"""
Queue-first YouTube ingestion worker.

Pipeline:
- Consumes messages from YOUTUBE_INGESTION_QUEUE
- Fetches transcript via Apify YouTube Transcript actor
- Uploads transcript text to S3 and publishes completion events on success
- Marks jobs as failed when transcript cannot be retrieved
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from io import BytesIO
import os
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlsplit

import httpx

from media_summarizer.core.config import settings
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
YOUTUBE_INGESTION_QUEUE = os.environ.get(
    "YOUTUBE_INGESTION_QUEUE", "youtube-ingestion-queue"
)
DEEPGRAM_TRANSCRIPTION_QUEUE = os.environ.get(
    "DEEPGRAM_TRANSCRIPTION_QUEUE", "deepgram-transcription-queue"
)
EPISODE_COMPLETION_EVENTS_QUEUE = os.environ.get(
    "EPISODE_COMPLETION_EVENTS_QUEUE", "episode-completion-events"
)
YOUTUBE_WORKER_MAX_RETRIES = 3

APIFY_API_BASE_URL = "https://api.apify.com/v2"

_UNAVAILABLE_MESSAGE = "This YouTube video is unavailable or cannot be processed."
_TEMPORARY_APIFY_MESSAGE = (
    "YouTube transcript retrieval is temporarily unavailable. Please retry."
)
_QUOTA_EXCEEDED_MESSAGE = (
    "YouTube processing is temporarily at capacity. Please try again later."
)
_AGE_RESTRICTED_MESSAGE = (
    "This video requires authentication that we cannot provide."
)
_GEO_RESTRICTED_MESSAGE = (
    "This video is not available in our processing region."
)


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


# -- Apify run status codes --

class ApifyRunStatus:
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"
    TIMED_OUT = "TIMED-OUT"


# -- Observability helpers --

_CLOUDWATCH_NAMESPACE = "MediaSummarizer/YouTube"


async def _emit_metric(metric_name: str, value: float = 1.0, dimensions: Optional[Dict[str, str]] = None) -> None:
    """Emit a CloudWatch metric. Best-effort, never raises."""
    try:
        import aioboto3

        session = aioboto3.Session()
        async with session.client(
            "cloudwatch",
            region_name=os.environ.get("AWS_DEFAULT_REGION", "eu-west-3"),
        ) as cw:
            metric_data: Dict[str, Any] = {
                "MetricName": metric_name,
                "Value": value,
                "Unit": "Count",
            }
            if dimensions:
                metric_data["Dimensions"] = [
                    {"Name": k, "Value": v} for k, v in dimensions.items()
                ]
            await cw.put_metric_data(
                Namespace=_CLOUDWATCH_NAMESPACE,
                MetricData=[metric_data],
            )
    except Exception:
        pass


# -- Utility functions --

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


# -- Apify transcript fetcher --

async def _fetch_apify_transcript(video_id: str, source_url: str) -> Dict[str, Any]:
    """
    Fetch transcript via Apify YouTube Transcript actor.

    Workflow:
    1. POST /v2/acts/{actor_id}/runs to start the actor
    2. Poll GET /v2/actor-runs/{runId} until terminal status
    3. GET /v2/datasets/{datasetId}/items to retrieve transcript data
    4. Normalize to downstream contract

    Reads config at call time (no module-level reads).
    """
    api_token = settings.APIFY_YOUTUBE_API_TOKEN
    actor_id = settings.APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID
    timeout_seconds = settings.APIFY_TIMEOUT_SECONDS
    poll_interval = settings.APIFY_POLL_INTERVAL_SECONDS
    max_polls = settings.APIFY_MAX_POLLS

    if not api_token:
        raise YouTubeIngestionError(
            "apify_actor_failed",
            details="missing_apify_youtube_api_token",
            retryable=False,
            user_message=_TEMPORARY_APIFY_MESSAGE,
        )
    if not actor_id:
        raise YouTubeIngestionError(
            "apify_actor_failed",
            details="missing_apify_youtube_transcript_actor_id",
            retryable=False,
            user_message=_TEMPORARY_APIFY_MESSAGE,
        )

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    input_data = {
        "urls": [source_url],
        "videoId": video_id,
    }

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        # Step 1: Start the actor run
        run_url = f"{APIFY_API_BASE_URL}/acts/{actor_id}/runs"
        try:
            response = await client.post(run_url, headers=headers, json=input_data)
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            await _emit_metric("apify_youtube_api_calls", dimensions={"outcome": "timeout"})
            raise YouTubeIngestionError(
                "apify_timeout",
                details=f"actor_start_timeout:{type(exc).__name__}",
                retryable=True,
                user_message=_TEMPORARY_APIFY_MESSAGE,
            ) from exc

        # Map HTTP status codes to error types
        if response.status_code in (401, 403):
            await _emit_metric("apify_youtube_api_calls", dimensions={"outcome": "actor_failed"})
            raise YouTubeIngestionError(
                "apify_actor_failed",
                details=f"http_{response.status_code}",
                retryable=False,
                user_message=_TEMPORARY_APIFY_MESSAGE,
            )
        if response.status_code == 429:
            await _emit_metric("apify_youtube_api_calls", dimensions={"outcome": "quota_exceeded"})
            raise YouTubeIngestionError(
                "apify_quota_exceeded",
                details="http_429",
                retryable=True,
                user_message=_QUOTA_EXCEEDED_MESSAGE,
            )
        if response.status_code >= 500:
            await _emit_metric("apify_youtube_api_calls", dimensions={"outcome": "timeout"})
            raise YouTubeIngestionError(
                "apify_timeout",
                details=f"http_{response.status_code}",
                retryable=True,
                user_message=_TEMPORARY_APIFY_MESSAGE,
            )
        if response.status_code >= 400:
            await _emit_metric("apify_youtube_api_calls", dimensions={"outcome": "actor_failed"})
            raise YouTubeIngestionError(
                "apify_actor_failed",
                details=f"http_{response.status_code}",
                retryable=False,
                user_message=_TEMPORARY_APIFY_MESSAGE,
            )

        run_data = response.json().get("data", {})
        run_id = run_data.get("id")
        if not run_id:
            await _emit_metric("apify_youtube_api_calls", dimensions={"outcome": "actor_failed"})
            raise YouTubeIngestionError(
                "apify_actor_failed",
                details="missing_run_id",
                retryable=True,
                user_message=_TEMPORARY_APIFY_MESSAGE,
            )

        # Step 2: Poll until the run completes
        run_status_url = f"{APIFY_API_BASE_URL}/actor-runs/{run_id}"
        dataset_id: Optional[str] = None

        for _ in range(max_polls):
            await asyncio.sleep(poll_interval)

            try:
                status_response = await client.get(run_status_url, headers=headers)
            except (httpx.TimeoutException, httpx.ConnectError):
                continue

            if status_response.status_code != 200:
                continue

            status_data = status_response.json().get("data", {})
            run_status = status_data.get("status", "")

            if run_status == ApifyRunStatus.SUCCEEDED:
                dataset_id = status_data.get("defaultDatasetId")
                break
            elif run_status in (
                ApifyRunStatus.FAILED,
                ApifyRunStatus.ABORTED,
                ApifyRunStatus.TIMED_OUT,
            ):
                await _emit_metric("apify_youtube_api_calls", dimensions={"outcome": "actor_failed"})
                raise YouTubeIngestionError(
                    "apify_actor_failed",
                    details=f"run_status_{run_status}",
                    retryable=False,
                    user_message=_TEMPORARY_APIFY_MESSAGE,
                )

        if not dataset_id:
            await _emit_metric("apify_youtube_api_calls", dimensions={"outcome": "timeout"})
            raise YouTubeIngestionError(
                "apify_timeout",
                details="polling_exhausted",
                retryable=True,
                user_message=_TEMPORARY_APIFY_MESSAGE,
            )

        # Step 3: Retrieve dataset items
        dataset_url = f"{APIFY_API_BASE_URL}/datasets/{dataset_id}/items?format=json&limit=100"
        try:
            dataset_response = await client.get(dataset_url, headers=headers)
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            await _emit_metric("apify_youtube_api_calls", dimensions={"outcome": "timeout"})
            raise YouTubeIngestionError(
                "apify_timeout",
                details=f"dataset_fetch_timeout:{type(exc).__name__}",
                retryable=True,
                user_message=_TEMPORARY_APIFY_MESSAGE,
            ) from exc

        if dataset_response.status_code != 200:
            await _emit_metric("apify_youtube_api_calls", dimensions={"outcome": "actor_failed"})
            raise YouTubeIngestionError(
                "apify_actor_failed",
                details=f"dataset_http_{dataset_response.status_code}",
                retryable=True,
                user_message=_TEMPORARY_APIFY_MESSAGE,
            )

        items = dataset_response.json()
        if not isinstance(items, list):
            items = []

    # Emit success metric and credits consumed
    await _emit_metric("apify_youtube_api_calls", dimensions={"outcome": "success"})
    await _emit_metric("apify_youtube_credits_consumed", value=1.0)

    # Step 4: Normalize the result
    return _normalize_apify_result(items, source_url, video_id)


def _normalize_apify_result(
    items: list[Dict[str, Any]],
    source_url: str,
    video_id: str,
) -> Dict[str, Any]:
    """
    Normalize Apify actor output to the downstream transcript contract.

    Expected item shape (actor-dependent):
    - Timed segments: [{text, start, duration}, ...]
    - Flat text: {text: "...", ...} or transcript field as string
    - Error signals: {error: "...", ...} with possible unavailable/geo/age markers
    """
    if not items:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details="empty_dataset",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    item = items[0]

    # Check for actor-emitted error signals
    error_signal = item.get("error") or item.get("errorMessage") or ""
    if error_signal:
        error_lower = str(error_signal).lower()
        if any(kw in error_lower for kw in ("unavailable", "private", "deleted", "removed")):
            raise YouTubeIngestionError(
                "youtube_unavailable",
                details=f"actor_signal:{error_signal[:200]}",
                retryable=False,
                user_message=_UNAVAILABLE_MESSAGE,
            )
        if "geo" in error_lower:
            raise YouTubeIngestionError(
                "youtube_geo_restricted",
                details=f"actor_signal:{error_signal[:200]}",
                retryable=False,
                user_message=_GEO_RESTRICTED_MESSAGE,
            )
        if any(kw in error_lower for kw in ("age", "restricted", "members")):
            raise YouTubeIngestionError(
                "youtube_age_restricted",
                details=f"actor_signal:{error_signal[:200]}",
                retryable=False,
                user_message=_AGE_RESTRICTED_MESSAGE,
            )
        raise YouTubeIngestionError(
            "apify_actor_failed",
            details=f"actor_error:{error_signal[:200]}",
            retryable=False,
            user_message=_TEMPORARY_APIFY_MESSAGE,
        )

    # Extract transcript text
    # Try timed segments first (list of dicts with "text" key)
    transcript_segments = item.get("transcript") or item.get("captions") or item.get("subtitles")
    language = item.get("language") or item.get("lang") or None
    language_code = item.get("languageCode") or item.get("language_code") or language or None

    text = ""
    segments_count = 0

    if isinstance(transcript_segments, list) and transcript_segments:
        # Timed segments: fuse into text
        lines = []
        for seg in transcript_segments:
            if isinstance(seg, dict):
                seg_text = (seg.get("text") or "").strip()
                if seg_text:
                    lines.append(seg_text)
            elif isinstance(seg, str):
                seg_text = seg.strip()
                if seg_text:
                    lines.append(seg_text)
        text = "\n".join(lines).strip()
        segments_count = len(lines)
    elif isinstance(transcript_segments, str) and transcript_segments.strip():
        # Flat text from actor
        text = transcript_segments.strip()
        segments_count = 0
    else:
        # Try top-level "text" field
        top_text = item.get("text") or item.get("content") or ""
        if isinstance(top_text, str) and top_text.strip():
            text = top_text.strip()
            segments_count = 0

    if not text:
        raise YouTubeIngestionError(
            "youtube_unavailable",
            details="no_transcript_in_payload",
            retryable=False,
            user_message=_UNAVAILABLE_MESSAGE,
        )

    return {
        "text": text,
        "language": language or language_code,
        "language_code": language_code,
        "segments_count": segments_count,
        "source_detail": "apify_youtube",
        "source_url": source_url,
        "fetched_at": _now_iso_utc(),
    }


# -- S3 upload and event helpers --

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
            "provider": "apify_youtube",
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


def _build_extraction_metadata(
    *,
    video_id: str,
    source_url: str,
    transcript_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "extractor": "apify_youtube",
        "extractor_version": "v1",
        "selected_strategy": "apify_transcript",
        "video_id": video_id,
        "source_url": source_url,
        "transcript_source_detail": transcript_result["source_detail"],
        "language_code": transcript_result.get("language_code"),
        "segments_count": transcript_result.get("segments_count"),
        "fetched_at": transcript_result["fetched_at"],
    }


def _build_transcription_metadata(
    *,
    transcript_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "provider": "apify_youtube",
        "model_used": "apify_youtube_transcript",
        "language": transcript_result.get("language"),
        "segments_count": transcript_result.get("segments_count"),
        "duration_seconds": 0,
        "source_url": transcript_result["source_url"],
        "transcribed_at": transcript_result["fetched_at"],
        "source_detail": transcript_result["source_detail"],
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
        "extractor_version": "v2",
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


# -- Main processing --

async def process_youtube_message(message_body: Dict[str, Any]) -> Dict[str, Any]:
    job_id = (message_body.get("job_id") or "").strip()
    normalized_url = (message_body.get("normalized_url") or "").strip()

    if not job_id:
        raise YouTubeIngestionError(
            "apify_actor_failed",
            details="missing_job_id",
            retryable=False,
            user_message=_TEMPORARY_APIFY_MESSAGE,
        )
    if not normalized_url:
        raise YouTubeIngestionError(
            "apify_actor_failed",
            details="missing_normalized_url",
            retryable=False,
            user_message=_TEMPORARY_APIFY_MESSAGE,
        )

    job = await database_async.get_processing_job_by_id(job_id)
    if not job:
        raise YouTubeIngestionError(
            "apify_actor_failed",
            details=f"processing_job_not_found:{job_id}",
            retryable=False,
            user_message=_TEMPORARY_APIFY_MESSAGE,
        )

    video_id = _extract_video_id(normalized_url)

    # Primary path: fetch transcript via Apify
    transcript_result = await _fetch_apify_transcript(video_id, normalized_url)

    # Upload to S3 and publish completion event
    transcript_s3_key = await _upload_native_transcript(job_id, transcript_result["text"])
    transcription_metadata = _build_transcription_metadata(
        transcript_result=transcript_result
    )
    job.set_transcription_location(transcript_s3_key)
    job.set_transcription_metadata(transcription_metadata)
    job.extraction_metadata = _build_extraction_metadata(
        video_id=video_id,
        source_url=normalized_url,
        transcript_result=transcript_result,
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
        "mode": "apify_transcript",
        "job_id": job_id,
        "media_key": message_body.get("media_key"),
        "video_id": video_id,
        "source_detail": transcript_result["source_detail"],
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
        log_event(
            logger,
            logging.INFO,
            "transcription.completed",
            "YouTube Apify transcript completed",
            job_id=result["job_id"],
            media_item_id=result["job_id"],
            transcript_source="apify_youtube",
            fallback_strategy=result["source_detail"],
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
        # Emit failure metric
        await _emit_metric("apify_youtube_api_calls", dimensions={"outcome": exc.code})
    except Exception as exc:
        if receive_count < YOUTUBE_WORKER_MAX_RETRIES:
            raise

        final_error = YouTubeIngestionError(
            "apify_actor_failed",
            details=f"unexpected:{type(exc).__name__}",
            retryable=False,
            user_message=_TEMPORARY_APIFY_MESSAGE,
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
