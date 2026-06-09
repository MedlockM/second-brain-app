"""E2E tests for ingestion fallback chains.

These tests exercise the secondary (fallback) transcription paths that activate
when the primary provider does not return usable content. Each test picks a
fixture URL that is known to trigger the fallback and verifies both final status
and the transcript_source metadata field.

Cost per run (approx.):
- Instagram Deepgram fallback: ~$0.01-0.02 (Apify call + Deepgram 90s max)
"""

from __future__ import annotations

from typing import Any, Dict

import httpx
import pytest

from tests.e2e.conftest import poll_until

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _ingest_and_wait(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
    url: str,
    timeout_s: float = 60,
) -> Dict[str, Any]:
    """Submit a URL, poll until terminal state, and return the full media detail.

    Returns the full response body (not just the media_item_id) so callers can
    inspect metadata fields like transcript_source.
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
    return body


# ---------------------------------------------------------------------------
# Instagram: Apify transcript -> Deepgram fallback
# ---------------------------------------------------------------------------

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
    detail = await _ingest_and_wait(
        http_client,
        auth_headers,
        INSTAGRAM_DEEPGRAM_FALLBACK_FIXTURE_URL,
        timeout_s=60,
    )

    # AC #3: Assert both status and transcript_source
    assert detail.get("status") == "completed", (
        f"Expected status 'completed', got '{detail.get('status')}'. "
        f"Full response: {detail}"
    )
    assert detail.get("transcript_source") == "deepgram", (
        f"Expected transcript_source 'deepgram' (fallback path), "
        f"got '{detail.get('transcript_source')}'. "
        f"This means the Apify native transcript was used instead of the "
        f"Deepgram fallback, or the fixture reel now has captions. "
        f"Full response: {detail}"
    )
