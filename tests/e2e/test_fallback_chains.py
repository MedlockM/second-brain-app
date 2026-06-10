"""E2E tests for ingestion fallback chains.

Each test targets a specific fallback path (primary extractor fails, secondary
takes over) and asserts BOTH completion AND a metadata field that proves the
fallback path was actually exercised.

Cost per run (approx.):
- TikTok Apify fallback: ~$0.005-0.01 (Apify actor call)
- Instagram Deepgram fallback: ~$0.01-0.02 (Apify call + Deepgram 90s max)
- Document Unstructured fallback: ~$0.001 (LlamaParse forced failure + Unstructured)
- Deepgram push-mode fallback: ~$0.005 (Lambda download + Deepgram push-mode)

IMPORTANT: Some tests require specific environment variables on the **worker**
Lambda (not the test runner):
- Document fallback: FORCE_LLAMAPARSE_FAILURE=1 on document-parsing worker
- Deepgram push-mode fallback: FORCE_DEEPGRAM_PUSH_MODE=1 on Deepgram worker
  (only affects pull_with_push_fallback mode; push/pull modes are unaffected)

Naming convention: test_<source>_<fallback_name>
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import httpx
import pytest

from tests.e2e.conftest import poll_until


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
    """TikTok IP-blocked URL -> yt-dlp fails -> Apify fallback succeeds.

    Fixture: a TikTok URL known to trigger 'Your IP address is blocked
    from accessing this post' when fetched from AWS Lambda IPs.
    Picked from task-140 evidence (BBC TikTok video).

    Asserts:
    - Job completes successfully (status == completed)
    - extraction_metadata.provider == "apify" (proving yt-dlp was NOT used)
    """
    media_item_id = await _ingest_and_wait(
        http_client,
        auth_headers,
        "https://www.tiktok.com/@bbc/video/7335731145619360992",
        timeout_s=60,
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
# Document: LlamaParse -> Unstructured fallback
# =============================================================================


@pytest.mark.e2e
async def test_document_unstructured_fallback(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Document upload where LlamaParse fails -> Unstructured fallback succeeds.

    Prerequisites:
        The document-parsing worker must have FORCE_LLAMAPARSE_FAILURE=1 set
        in its environment. This causes LlamaParse to return a simulated
        rate-limit error, triggering the Unstructured fallback path.

    Assertions:
        - Job reaches status == "completed"
        - provider == "unstructured" (proving the fallback fired)

    Fixture:
        tests/e2e/fixtures/sample.pdf -- the same 1-page PDF used by the
        happy-path test. Any valid PDF works since the failure is forced via
        environment variable, not file content.
    """
    fixture = Path(__file__).parent / "fixtures" / "sample.pdf"
    assert fixture.exists(), f"Fixture not found: {fixture}"

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
        timeout_s=30,
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
        f"Ensure FORCE_LLAMAPARSE_FAILURE=1 is set on the document-parsing worker."
    )


# Note: a previous `test_deepgram_pushmode_fallback` exercising the
# pull_with_push_fallback branch was removed 2026-06-10 after the task-158
# refactor. Producers (TikTok, Instagram, X) that hit CDN blocks now declare
# deepgram_mode="push" directly, bypassing the fallback branch entirely.
# The fallback branch only triggers on user-pasted .mp3 URLs (an unstable,
# unpredictable path that no fixture can reliably exercise).
