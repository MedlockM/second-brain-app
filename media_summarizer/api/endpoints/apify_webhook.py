"""Authenticated ingress for terminal Apify actor-run webhooks."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request, status

from media_summarizer.infrastructure import apify_adapter
from media_summarizer.utils import database_async, sqs
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import log_event

router = APIRouter()
logger = logging.getLogger(__name__)

_MAX_WEBHOOK_BODY_BYTES = 64 * 1024
_QUEUE_BY_PLATFORM = {
    "instagram": required_env("INSTAGRAM_INGESTION_QUEUE"),
    "tiktok": required_env("TIKTOK_INGESTION_QUEUE"),
    "youtube": required_env("YOUTUBE_INGESTION_QUEUE"),
}


@router.post("/webhooks/apify", status_code=status.HTTP_202_ACCEPTED)
async def handle_apify_webhook(request: Request) -> dict[str, str]:
    """Validate a provider callback and durably hand it back to its worker."""
    if not apify_adapter.webhook_secret_configured():
        logger.error("APIFY_WEBHOOK_SECRET is not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured",
        )
    if not apify_adapter.webhook_is_authorized(request.headers.get("Authorization", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization",
        )

    raw_body = await request.body()
    if len(raw_body) > _MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Webhook payload too large",
        )
    try:
        payload = apify_adapter.parse_webhook_payload(json.loads(raw_body))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload",
        ) from exc

    job = await database_async.get_processing_job_by_id(payload.job_id)
    if not job:
        return {"status": "ignored", "reason": "job_not_found"}

    if not job.apify_run_id:
        # A very fast actor can call back between the start response and the
        # immediate DynamoDB write. A non-2xx response makes Apify retry after
        # the correlation has become visible instead of discarding the event.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Run correlation is not persisted yet",
        )

    if payload.run_id != job.apify_run_id or payload.source_platform != job.apify_source_platform:
        log_event(
            logger,
            logging.WARNING,
            "apify.webhook.correlation_mismatch",
            "Ignored Apify webhook that did not match the current job run",
            job_id=job.id,
            source_platform=payload.source_platform,
            apify_run_id=payload.run_id,
        )
        return {"status": "ignored", "reason": "correlation_mismatch"}

    if payload.status == "SUCCEEDED" and payload.dataset_id != job.apify_dataset_id:
        return {"status": "ignored", "reason": "dataset_mismatch"}

    if job.is_terminal_state() or job.apify_state in {"processed", "expired"}:
        return {"status": "ignored", "reason": "already_processed"}

    context = dict(job.apify_context or {})
    await sqs.send_message(
        queue_name=_QUEUE_BY_PLATFORM[payload.source_platform],
        message_body={
            **context,
            "message_type": "apify_callback",
            "job_id": job.id,
            "apify_run_id": payload.run_id,
            "apify_status": payload.status,
        },
    )
    return {"status": "queued"}
