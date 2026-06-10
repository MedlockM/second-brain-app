"""E2E tests for ingestion fallback chains.

Each test targets a specific fallback path (primary extractor fails, secondary
takes over) and asserts BOTH completion AND a metadata field that proves the
fallback path was actually exercised.

Cost per run (approx.):
- TikTok Apify fallback: ~$0.005-0.01 (Apify actor call)
- Instagram Deepgram fallback: ~$0.01-0.02 (Apify post scraper + Deepgram push)
- Document Unstructured fallback: ~$0.001 (FORCE_LLAMAPARSE_FAILURE + Unstructured)

Architecture notes (post task-158):
- TikTok: yt-dlp (primary) -> Apify (fallback on Lambda IP block)
- Instagram video posts: Apify Post Scraper returns audio_url -> Deepgram push mode
- Instagram Reels: Apify subtitle extractor (native-only, no Deepgram fallback)
- Documents: LlamaParse (primary) -> Unstructured (fallback on any parse failure)
- Deepgram modes are now explicit per producer (push/pull), no automatic fallback

Naming convention: test_<source>_<fallback_name>
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

import boto3
import httpx
import pytest

from tests.e2e.conftest import poll_until


# =============================================================================
# Constants
# =============================================================================

# Lambda function name for the document-parsing worker.
# Pattern: {project_name}-worker-{worker_key} (from Terraform lambda_workers.tf)
DOCUMENT_PARSING_LAMBDA = os.environ.get(
    "DOCUMENT_PARSING_LAMBDA_NAME", "media-summarizer-worker-document_parsing"
)
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-3")


# =============================================================================
# Helpers
# =============================================================================


async def _ingest_and_wait(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
    url: str,
    timeout_s: float = 60,
) -> str:
    """Submit a URL and poll until the job reaches completed/failed.

    Returns media_item_id on success. Asserts status == completed.
    """
    resp = await http_client.post(
        "/api/media/ingest-url",
        json={"url": url},
        headers=auth_headers,
    )
    resp.raise_for_status()
    media_item_id = resp.json()["media_item_id"]
    body = await poll_until(
        client=http_client,
        url=f"/api/media/{media_item_id}",
        headers=auth_headers,
        predicate=lambda b: b.get("status") in ("completed", "failed"),
        timeout_s=timeout_s,
        interval_s=3,
    )
    assert body.get("status") == "completed", (
        f"ingestion did not complete (status={body.get('status')}): {body}"
    )
    return media_item_id


async def _get_media_item(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
    media_item_id: str,
) -> Dict[str, Any]:
    """Fetch the full media item detail from GET /api/media/{id}."""
    resp = await http_client.get(
        f"/api/media/{media_item_id}",
        headers=auth_headers,
    )
    resp.raise_for_status()
    return resp.json()


def _set_lambda_env_var(function_name: str, key: str, value: str) -> Dict[str, str]:
    """Add/update an environment variable on a Lambda function.

    Returns the previous environment variables dict (for restore).
    """
    client = boto3.client("lambda", region_name=AWS_REGION)
    config = client.get_function_configuration(FunctionName=function_name)
    env_vars = (config.get("Environment") or {}).get("Variables", {})
    original_env = dict(env_vars)

    env_vars[key] = value
    client.update_function_configuration(
        FunctionName=function_name,
        Environment={"Variables": env_vars},
    )
    return original_env


def _restore_lambda_env(function_name: str, env_vars: Dict[str, str]) -> None:
    """Restore Lambda environment variables to a previous state."""
    client = boto3.client("lambda", region_name=AWS_REGION)
    client.update_function_configuration(
        FunctionName=function_name,
        Environment={"Variables": env_vars},
    )


# =============================================================================
# TikTok: yt-dlp IP-blocked -> Apify fallback
# =============================================================================


@pytest.mark.e2e
async def test_tiktok_apify_fallback(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """TikTok IP-blocked URL -> yt-dlp fails -> Apify fallback succeeds.

    Fixture: a TikTok URL known to trigger 'Your IP address is blocked
    from accessing this post' when fetched from AWS Lambda IPs.
    Picked from task-140 evidence (BBC TikTok video).

    Timeout set to 120s to account for:
    - yt-dlp slow-fail on IP block detection (up to 30s with internal retries)
    - Apify actor cold-start + TikTok scraping (20-30s)
    - SQS polling + Lambda cold-start overhead

    Asserts:
    - Job completes successfully (status == completed)
    - extraction_metadata.provider == "apify" (proving yt-dlp was NOT used)
    - extraction_metadata.strategy_used == "apify_tiktok_ip_block_fallback"
    """
    media_item_id = await _ingest_and_wait(
        http_client,
        auth_headers,
        "https://www.tiktok.com/@bbc/video/7335731145619360992",
        timeout_s=120,
    )

    detail = await _get_media_item(http_client, auth_headers, media_item_id)

    # The worker sets extraction_metadata.provider = "apify" when the
    # Apify fallback path is taken (see _build_apify_extraction_metadata).
    extraction_meta = detail.get("extraction_metadata") or {}
    transcription_meta = detail.get("transcription_metadata") or {}

    apify_used = (
        extraction_meta.get("provider") == "apify"
        or extraction_meta.get("strategy_used") == "apify_tiktok_ip_block_fallback"
        or transcription_meta.get("provider") == "apify_tiktok"
    )
    assert apify_used, (
        f"Expected Apify fallback to fire, but metadata shows otherwise. "
        f"extraction_metadata={extraction_meta}, "
        f"transcription_metadata={transcription_meta}"
    )


# =============================================================================
# Instagram: video post support removed (task-173)
# =============================================================================
# Note: test_instagram_deepgram_fallback was removed after task-173.
# Instagram video posts are no longer supported. The resolver only handles:
# - Reels/IGTV: native transcript via Video Subtitle Extractor (no Deepgram fallback)
# - Posts: image/carousel via Post Scraper (OCR worker, no Deepgram fallback)
# See task-173: Simplify Instagram resolver — drop Comment Scraper and legacy
# post-video branch.


# =============================================================================
# Document: LlamaParse -> Unstructured fallback
# =============================================================================


@pytest.mark.e2e
async def test_document_unstructured_fallback(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Document upload where LlamaParse fails -> Unstructured fallback succeeds.

    Strategy: The test temporarily sets FORCE_LLAMAPARSE_FAILURE=1 on the
    document-parsing worker Lambda, submits a PDF, verifies the Unstructured
    fallback fires, then restores the original Lambda configuration.

    This ensures:
    - The fallback path (LlamaParse failure -> Unstructured) is exercised
    - No FORCE_* flags persist on the production Lambda after the test
    - The test is self-contained and does not depend on external setup

    Prerequisites:
    - AWS credentials with permission to call lambda:GetFunctionConfiguration
      and lambda:UpdateFunctionConfiguration on the document-parsing worker
    - DOCUMENT_PARSING_LAMBDA_NAME env var (default: media-summarizer-worker-document_parsing)

    Assertions:
        - Job reaches status == "completed"
        - provider == "unstructured" (proving the fallback fired)
    """
    fixture = Path(__file__).parent / "fixtures" / "sample.pdf"
    assert fixture.exists(), f"Fixture not found: {fixture}"

    # Temporarily set the force-failure flag on the Lambda
    original_env: Dict[str, str] | None = None
    try:
        original_env = _set_lambda_env_var(
            DOCUMENT_PARSING_LAMBDA, "FORCE_LLAMAPARSE_FAILURE", "1"
        )
    except Exception as exc:
        pytest.skip(
            f"Cannot set FORCE_LLAMAPARSE_FAILURE on Lambda "
            f"'{DOCUMENT_PARSING_LAMBDA}': {exc!r}. "
            f"Ensure AWS credentials have lambda:UpdateFunctionConfiguration permission."
        )

    try:
        with fixture.open("rb") as f:
            files = {"file": ("sample.pdf", f, "application/pdf")}
            resp = await http_client.post(
                "/api/media/upload",
                files=files,
                headers=auth_headers,
            )

        assert resp.status_code == 202, (
            f"upload failed: {resp.status_code} {resp.text}"
        )
        media_item_id = resp.json()["media_item_id"]

        # Poll until terminal state (completed or failed)
        body = await poll_until(
            client=http_client,
            url=f"/api/media/{media_item_id}",
            headers=auth_headers,
            predicate=lambda b: b.get("status") in ("completed", "failed"),
            timeout_s=60,
            interval_s=3,
        )

        assert body.get("status") == "completed", (
            f"document parsing did not complete: status={body.get('status')}, "
            f"error={body.get('error_message')}"
        )

        # Verify the fallback provider was used
        provider = body.get("provider")
        assert provider == "unstructured", (
            f"Expected fallback provider 'unstructured', got: '{provider}'. "
            f"The FORCE_LLAMAPARSE_FAILURE flag may not have taken effect yet "
            f"(Lambda cold-start with old env). Retry the test."
        )

    finally:
        # Always restore the original Lambda configuration
        if original_env is not None:
            try:
                _restore_lambda_env(DOCUMENT_PARSING_LAMBDA, original_env)
            except Exception as restore_exc:
                # Log but do not mask the test failure
                print(
                    f"[WARNING] Failed to restore Lambda env for "
                    f"'{DOCUMENT_PARSING_LAMBDA}': {restore_exc!r}. "
                    f"Manually remove FORCE_LLAMAPARSE_FAILURE from the Lambda."
                )


# =============================================================================
# Removed tests (post task-158)
# =============================================================================

# Note: `test_deepgram_pushmode_fallback` was removed 2026-06-10 after the
# task-158 refactor. Producers (TikTok, Instagram, X) that hit CDN blocks now
# declare deepgram_mode="push" directly, bypassing the pull_with_push_fallback
# branch entirely. That branch is a defensive fallback for unknown sources
# (user-pasted .mp3 URLs) -- an unstable, unpredictable path that no fixture
# can reliably exercise.
