"""Single non-blocking adapter for every Apify actor used by ingestion.

The adapter owns all Apify HTTP details and runtime configuration. Callers start
an actor, persist the returned run ID, and leave the invocation; terminal
results arrive through the per-run webhook and are read from the run dataset.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from enum import Enum
from hmac import compare_digest
from typing import Any
from urllib.parse import quote

import httpx

APIFY_API_BASE_URL = "https://api.apify.com/v2"
APIFY_REQUEST_TIMEOUT_SECONDS = float(os.environ.get("APIFY_REQUEST_TIMEOUT_SECONDS", "15"))
APIFY_ACTOR_TIMEOUT_SECONDS = int(os.environ.get("APIFY_ACTOR_TIMEOUT_SECONDS", "600"))
APIFY_BACKSTOP_DELAY_SECONDS = 900

APIFY_TERMINAL_EVENTS = (
    "ACTOR.RUN.SUCCEEDED",
    "ACTOR.RUN.FAILED",
    "ACTOR.RUN.ABORTED",
    "ACTOR.RUN.TIMED_OUT",
)
APIFY_TERMINAL_STATUSES = frozenset({"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"})


class ApifyActorKind(str, Enum):
    INSTAGRAM_REEL = "instagram_reel"
    INSTAGRAM_POST = "instagram_post"
    TIKTOK_TRANSCRIPT = "tiktok_transcript"
    YOUTUBE_TRANSCRIPT = "youtube_transcript"


@dataclass(frozen=True)
class ApifyRun:
    run_id: str
    dataset_id: str
    actor_id: str


@dataclass(frozen=True)
class ApifyWebhookPayload:
    job_id: str
    source_platform: str
    run_id: str
    status: str
    dataset_id: str | None


class ApifyAdapterError(RuntimeError):
    """Stable provider failure raised by the shared adapter."""

    def __init__(self, code: str, *, retryable: bool, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code
        self.retryable = retryable
        self.detail = detail


def _normalize_actor_id(actor_id: str) -> str:
    return actor_id.strip().replace("/", "~")


def _actor_configuration(kind: ApifyActorKind) -> tuple[str, str]:
    if kind == ApifyActorKind.INSTAGRAM_REEL:
        token = os.environ.get("APIFY_INSTAGRAM_API_TOKEN", "")
        actor_id = os.environ.get("APIFY_INSTAGRAM_REEL_ACTOR_ID", "apify~instagram-reel-scraper")
    elif kind == ApifyActorKind.INSTAGRAM_POST:
        token = os.environ.get("APIFY_INSTAGRAM_API_TOKEN", "")
        actor_id = os.environ.get("APIFY_INSTAGRAM_POST_ACTOR_ID", "apify~instagram-post-scraper")
    elif kind == ApifyActorKind.TIKTOK_TRANSCRIPT:
        token = os.environ.get("APIFY_TIKTOK_API_TOKEN", "")
        actor_id = os.environ.get(
            "APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID",
            "scrape-creators~best-tiktok-transcripts-scraper",
        )
    else:
        token = os.environ.get("APIFY_YOUTUBE_API_TOKEN", "")
        actor_id = os.environ.get(
            "APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID",
            "starvibe~youtube-video-transcript",
        )
    return token.strip(), _normalize_actor_id(actor_id)


def configured_actor_id(kind: ApifyActorKind) -> str:
    """Return the configured actor ID without exposing its credential."""
    _, actor_id = _actor_configuration(kind)
    return actor_id


def webhook_secret_configured() -> bool:
    return bool(os.environ.get("APIFY_WEBHOOK_SECRET", "").strip())


def webhook_is_authorized(authorization: str) -> bool:
    """Compare the webhook Bearer credential without timing-sensitive equality."""
    expected = os.environ.get("APIFY_WEBHOOK_SECRET", "").strip()
    if not expected:
        return False
    supplied = authorization.strip()
    if supplied.startswith("Bearer "):
        supplied = supplied[7:]
    return compare_digest(supplied, expected)


def parse_webhook_payload(body: Any) -> ApifyWebhookPayload:
    if not isinstance(body, dict):
        raise ValueError("Webhook body must be an object")
    resource = body.get("resource")
    if not isinstance(resource, dict):
        raise ValueError("Webhook resource is missing")

    job_id = str(body.get("job_id") or "").strip()
    source_platform = str(body.get("source_platform") or "").strip().lower()
    run_id = str(resource.get("id") or "").strip()
    status = str(resource.get("status") or "").strip().upper()
    dataset_value = resource.get("defaultDatasetId")
    dataset_id = str(dataset_value).strip() if dataset_value else None

    if not job_id or source_platform not in {"instagram", "tiktok", "youtube"}:
        raise ValueError("Webhook correlation fields are invalid")
    if not run_id or status not in APIFY_TERMINAL_STATUSES:
        raise ValueError("Webhook run fields are invalid")
    if status == "SUCCEEDED" and not dataset_id:
        raise ValueError("Successful run has no dataset ID")

    return ApifyWebhookPayload(
        job_id=job_id,
        source_platform=source_platform,
        run_id=run_id,
        status=status,
        dataset_id=dataset_id,
    )


def _webhook_definition(*, job_id: str, source_platform: str) -> str:
    callback_url = os.environ.get("APIFY_WEBHOOK_URL", "").strip()
    webhook_secret = os.environ.get("APIFY_WEBHOOK_SECRET", "").strip()
    if not callback_url:
        raise ApifyAdapterError("apify_webhook_url_missing", retryable=False)
    if not webhook_secret:
        raise ApifyAdapterError("apify_webhook_secret_missing", retryable=False)

    correlation = json.dumps(
        {"job_id": job_id, "source_platform": source_platform},
        separators=(",", ":"),
    )
    payload_template = correlation[:-1] + ',"resource":{{resource}}}'
    definitions = [
        {
            "eventTypes": list(APIFY_TERMINAL_EVENTS),
            "requestUrl": callback_url,
            "payloadTemplate": payload_template,
            "headersTemplate": json.dumps(
                {"Authorization": f"Bearer {webhook_secret}"},
                separators=(",", ":"),
            ),
        }
    ]
    encoded = base64.b64encode(json.dumps(definitions, separators=(",", ":")).encode("utf-8"))
    return encoded.decode("ascii")


def _raise_for_response(response: httpx.Response, operation: str) -> None:
    status_code = response.status_code
    if status_code < 400:
        return
    if status_code == 402:
        code, retryable = "apify_payment_required", False
    elif status_code in (401, 403):
        code, retryable = "apify_auth_error", False
    elif status_code == 429:
        code, retryable = "apify_rate_limited", True
    elif status_code >= 500:
        code, retryable = "apify_server_error", True
    else:
        code, retryable = "apify_client_error", False
    raise ApifyAdapterError(
        code,
        retryable=retryable,
        detail=f"{operation}:{status_code}",
    )


async def start_actor_run(
    *,
    kind: ApifyActorKind,
    input_data: dict[str, Any],
    job_id: str,
    source_platform: str,
) -> ApifyRun:
    """Start one actor with terminal webhooks and return immediately."""
    token, actor_id = _actor_configuration(kind)
    if not token:
        raise ApifyAdapterError("apify_token_missing", retryable=False)
    if not actor_id:
        raise ApifyAdapterError("apify_actor_missing", retryable=False)

    run_url = f"{APIFY_API_BASE_URL}/acts/{quote(actor_id, safe='~')}/runs"
    params: dict[str, str | int] = {
        "timeout": APIFY_ACTOR_TIMEOUT_SECONDS,
        "webhooks": _webhook_definition(
            job_id=job_id,
            source_platform=source_platform,
        ),
    }
    headers = {"Authorization": f"Bearer {token}"}

    try:
        async with httpx.AsyncClient(timeout=APIFY_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(
                run_url,
                params=params,
                headers=headers,
                json=input_data,
            )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise ApifyAdapterError(
            "apify_network_error",
            retryable=True,
            detail=type(exc).__name__,
        ) from exc

    _raise_for_response(response, "start_run")
    try:
        data = response.json().get("data", {})
    except (ValueError, AttributeError) as exc:
        raise ApifyAdapterError("apify_invalid_json", retryable=True) from exc

    run_id = str(data.get("id") or "").strip()
    dataset_id = str(data.get("defaultDatasetId") or "").strip()
    if not run_id or not dataset_id:
        raise ApifyAdapterError("apify_invalid_run", retryable=True)
    return ApifyRun(run_id=run_id, dataset_id=dataset_id, actor_id=actor_id)


def _token_for_platform(source_platform: str) -> str:
    if source_platform == "instagram":
        return os.environ.get("APIFY_INSTAGRAM_API_TOKEN", "").strip()
    if source_platform == "tiktok":
        return os.environ.get("APIFY_TIKTOK_API_TOKEN", "").strip()
    if source_platform == "youtube":
        return os.environ.get("APIFY_YOUTUBE_API_TOKEN", "").strip()
    return ""


async def fetch_dataset_items(*, source_platform: str, dataset_id: str) -> list[dict[str, Any]]:
    """Fetch a completed run's dataset without polling its status."""
    token = _token_for_platform(source_platform)
    if not token:
        raise ApifyAdapterError("apify_token_missing", retryable=False)
    if not dataset_id:
        raise ApifyAdapterError("apify_dataset_missing", retryable=False)

    dataset_url = f"{APIFY_API_BASE_URL}/datasets/{quote(dataset_id, safe='')}/items"
    try:
        async with httpx.AsyncClient(timeout=APIFY_REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(
                dataset_url,
                params={"clean": "true", "format": "json", "limit": 100},
                headers={"Authorization": f"Bearer {token}"},
            )
    except (httpx.TimeoutException, httpx.TransportError) as exc:
        raise ApifyAdapterError(
            "apify_network_error",
            retryable=True,
            detail=type(exc).__name__,
        ) from exc

    _raise_for_response(response, "fetch_dataset")
    try:
        items = response.json()
    except ValueError as exc:
        raise ApifyAdapterError("apify_invalid_json", retryable=True) from exc
    if not isinstance(items, list):
        raise ApifyAdapterError("apify_invalid_dataset", retryable=False)
    return [item for item in items if isinstance(item, dict)]
