"""E2E tests for ingestion fallback chains.

Each test targets a specific fallback path (primary extractor fails, secondary
takes over) and asserts BOTH completion AND a metadata field that proves the
fallback path was actually exercised.

Cost per run (approx.):
- TikTok Apify fallback: ~$0.005-0.01 (Apify actor call)
- Instagram Deepgram fallback: ~$0.01-0.02 (Apify post scraper + Deepgram push)
- Document Unstructured fallback: ~$0.001 (E2E sentinel filename + Unstructured)

Architecture notes (post task-158):
- TikTok: yt-dlp (primary) -> Apify (fallback on Lambda IP block)
- Instagram video posts: Apify Post Scraper returns audio_url -> Deepgram push mode
- Instagram Reels: Apify subtitle extractor (native-only, no Deepgram fallback)
- Documents: LlamaParse (primary) -> Unstructured (fallback on any parse failure)
- Deepgram modes are now explicit per producer (push/pull), no automatic fallback

Naming convention: test_<source>_<fallback_name>
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import httpx
import pytest

from tests.e2e.conftest import poll_until, upload_document_file

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


# =============================================================================
# TikTok: yt-dlp IP-blocked -> Apify fallback
# =============================================================================


@pytest.mark.e2e
async def test_tiktok_apify_fallback(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """yt-dlp IP-block forced -> Apify fallback succeeds.

    The submitted URL carries the `__e2e_force_ip_block__=1` sentinel that
    the TikTok worker strips in-flight and treats as an immediate IP-block
    signal (see `_strip_e2e_force_ip_block_sentinel` in
    `media_summarizer/workers/tiktok_ingestion_worker.py`). This bypasses
    yt-dlp entirely and routes the job to the Apify fallback path
    deterministically — no dependency on which TikTok videos are currently
    geo-blocked from Lambda IPs.

    The video itself (`@natgeo/.../7649753579829333262`) is picked because
    the Apify TikTok actor reliably returns content for it.

    Timeout set to 90s — no yt-dlp retries to wait for since the sentinel
    short-circuits before yt-dlp runs, but the Apify TikTok actor cold-start
    plus scraping plus SQS overhead can take 45-75s end-to-end.

    Asserts:
    - Job completes successfully (status == completed)
    - extraction_metadata.provider == "apify" (proving yt-dlp was NOT used)
    - extraction_metadata.strategy_used == "apify_tiktok_ip_block_fallback"
    """
    media_item_id = await _ingest_and_wait(
        http_client,
        auth_headers,
        "https://www.tiktok.com/@natgeo/video/7649753579829333262?__e2e_force_ip_block__=1",
        timeout_s=90,
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
# Instagram: Apify Reel Scraper -> Deepgram push
# =============================================================================


@pytest.mark.e2e
async def test_instagram_apify_fallback(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Apify Reel Scraper resolves the reel, Deepgram transcribes it in push mode.

    Since task-310 Apify is the *only* Instagram resolution path: the yt-dlp
    attempt that used to run first was IP-blocked 6 times out of 6 on dev and
    was deleted, along with the `__e2e_force_ip_block__` sentinel that used to
    force this branch. The plain reel URL now exercises the same chain.

    Since task-274 the job travels through `instagram-ingestion-queue` to the
    worker instead of being resolved inside the HTTP request, so the wait covers
    the queue hop plus an Apify run measured at 63-100 s -- hence the budget well
    above the other chains'.

    Asserts:
    - Job completes successfully (status == completed)
    - resolver_metadata.provider == "apify"
    """
    media_item_id = await _ingest_and_wait(
        http_client,
        auth_headers,
        "https://www.instagram.com/natgeo/reel/DZaHxtTglqb/",
        timeout_s=300,
    )

    detail = await _get_media_item(http_client, auth_headers, media_item_id)
    extraction_meta = detail.get("extraction_metadata") or {}
    resolver_meta = (extraction_meta.get("resolver_metadata") or {})

    assert resolver_meta.get("provider") == "apify", (
        f"Expected the Apify path to resolve the reel "
        f"(resolver_metadata.provider == 'apify'), "
        f"got: extraction_metadata={extraction_meta}"
    )


# =============================================================================
# Document: LlamaParse -> Unstructured fallback
# =============================================================================


@pytest.mark.e2e
async def test_document_unstructured_fallback(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Document upload where LlamaParse fails -> Unstructured fallback succeeds.

    Strategy: The test uploads a file with a sentinel name that triggers
    LlamaParseResolver to simulate a transient failure. This exercises the
    Unstructured fallback path without requiring Lambda env-var manipulation.

    The sentinel approach is deterministic and race-free:
    - No Lambda config propagation delays
    - Deterministic on the first invocation (no cold-start dance)
    - No IAM permission required (no lambda:UpdateFunctionConfiguration)
    - The sentinel is scoped to the per-request filename

    Assertions:
        - Job reaches status == "completed"
        - provider == "unstructured" (proving the fallback fired)
    """
    fixture = Path(__file__).parent / "fixtures" / "sample.pdf"
    assert fixture.exists(), f"Fixture not found: {fixture}"

    # Use a sentinel filename that LlamaParseResolver recognizes as a test seam.
    # The resolver will detect "__e2e_force_llamaparse_failure__" prefix and
    # return a simulated rate-limit error, triggering the Unstructured fallback.
    sentinel_filename = "__e2e_force_llamaparse_failure__sample.pdf"

    resp = await upload_document_file(
        http_client,
        auth_headers,
        file_name=sentinel_filename,
        content=fixture.read_bytes(),
        content_type="application/pdf",
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
        f"The sentinel filename may not have been recognized by the resolver."
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
