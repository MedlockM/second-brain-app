"""E2E tests for ingestion fallback chains.

Each test targets a specific fallback path (primary extractor fails, secondary
takes over) and asserts BOTH completion AND a metadata field that proves the
fallback path was actually exercised.

Cost per run (approx.):
- TikTok Apify fallback: ~$0.005-0.01 (Apify actor call)
- Instagram Deepgram fallback: ~$0.01-0.02 (Apify call + Deepgram 90s max)

Naming convention: test_<source>_<fallback_name>
"""

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
# Instagram: Apify transcript -> Deepgram fallback
# =============================================================================

# Fixture rationale:
# This reel is a short visual/music-focused Instagram Reel from BBC Earth
# that has no spoken narration or creator-provided captions. The Apify
# instagram-reel-scraper returns an empty or below-threshold transcript field
# for such reels, triggering the Deepgram audio fallback path.
#
# Selection criteria:
#   1. Must be a public, stable Reel (not Stories, not deleted)
#   2. Must NOT have native captions in Apify response (triggers fallback)
#   3. Must have audible content (even ambient/music) so Deepgram returns
#      a non-empty result and the pipeline completes successfully
#   4. Short duration (<30s) to minimize Deepgram cost
#
# If this fixture becomes unstable (deleted, made private, or Apify starts
# returning captions for it), replace with another music/visual reel from
# a major media account (@bbcearth, @natgeo, @discoverynature).
INSTAGRAM_DEEPGRAM_FALLBACK_FIXTURE_URL = (
    "https://www.instagram.com/reel/CwHSCpMoe7Z/"
)


@pytest.mark.e2e
@pytest.mark.timeout(60)
async def test_instagram_deepgram_fallback(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Instagram Reel without Apify auto-caption triggers Deepgram fallback.

    Verifies:
    - The ingestion pipeline completes (status == "completed")
    - The transcript was obtained via Deepgram (transcript_source == "deepgram")
      rather than the primary Apify native transcript path
    """
    media_item_id = await _ingest_and_wait(
        http_client,
        auth_headers,
        INSTAGRAM_DEEPGRAM_FALLBACK_FIXTURE_URL,
        timeout_s=60,
    )

    detail = await _get_media_item(http_client, auth_headers, media_item_id)

    # AC #3: Assert transcript_source indicates Deepgram fallback was used
    assert detail.get("transcript_source") == "deepgram", (
        f"Expected transcript_source 'deepgram' (fallback path), "
        f"got '{detail.get('transcript_source')}'. "
        f"This means the Apify native transcript was used instead of the "
        f"Deepgram fallback, or the fixture reel now has captions. "
        f"Full response: {detail}"
    )
