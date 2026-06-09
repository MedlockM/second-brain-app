"""Skeletons for non-article sources discovered during Phase 4.

Each test submits a representative URL and is currently `xfail` or `skip`
because the source has not been validated end-to-end yet (or has a known
upstream issue). When the source becomes stable, flip the marker to make it
part of the regular happy path.
"""

from typing import Dict

import httpx
import pytest

from tests.e2e.conftest import poll_until


async def _ingest_and_wait(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
    url: str,
    timeout_s: float = 180,
) -> str:
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
        interval_s=5,
    )
    assert body.get("status") == "completed", (
        f"ingestion stayed in {body.get('status')}: {body}"
    )
    return media_item_id


@pytest.mark.e2e
async def test_youtube_ingestion(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    await _ingest_and_wait(
        http_client,
        auth_headers,
        "https://www.youtube.com/watch?v=arj7oStGLkU",
    )


async def _submit_podcast_and_wait(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
    podcast_url: str,
    timeout_s: float = 300,
) -> str:
    """Submit a podcast URL via /api/v1/podcasts/submit, then poll /api/media/{id}.

    The podcasts/submit endpoint exercises the full pipeline:
    URL → PodcastIndex resolver → audio_url enclosure → Deepgram → artifacts.
    Returns job_id (== media_item_id).
    """
    resp = await http_client.post(
        "/api/v1/podcasts/submit",
        json={"podcast_url": podcast_url},
        headers=auth_headers,
    )
    resp.raise_for_status()
    job_id = resp.json()["job_id"]
    body = await poll_until(
        client=http_client,
        url=f"/api/media/{job_id}",
        headers=auth_headers,
        predicate=lambda b: b.get("status") in ("completed", "failed"),
        timeout_s=timeout_s,
        interval_s=5,
    )
    assert body.get("status") == "completed", (
        f"podcast ingestion stayed in {body.get('status')}: {body}"
    )
    return job_id


@pytest.mark.e2e
async def test_podcast_via_direct_audio_url(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Direct audio URL ingestion (bypasses RSS/PodcastIndex, goes straight to
    Deepgram transcription).

    Uses a short (7s) spoken-word recording from the Internet Archive's
    permanently-archived LibriVox collection. Archive.org URLs are designed to
    be permanent (no link rot risk).
    """
    # LibriVox "Short Nonfiction Collection" - opening 7s reading (public domain).
    # This is a direct MP3 download URL from archive.org — permanent by design.
    await _ingest_and_wait(
        http_client,
        auth_headers,
        "https://archive.org/download/count_monte_cristo_0711_librivox/count_of_monte_cristo_001_dumas_64kb.mp3",
        timeout_s=300,
    )


@pytest.mark.e2e
async def test_podcast_via_podcastindex(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """End-to-end podcast pipeline:

      Apple Podcasts URL → /api/v1/podcasts/submit → PodcastIndex resolver
      → audio enclosure URL → Deepgram → completed.

    Picks a podcast known for short episodes (≤ 5 min) to keep Deepgram cost
    bounded. The fixture URL must be a real podcast page (not a direct MP3),
    otherwise the resolver path is skipped.
    """
    # The Daily — NYT has a known short trailer ~1-2 min, stable URL.
    # Replace with a more stable fixture if NYT migrates.
    await _submit_podcast_and_wait(
        http_client,
        auth_headers,
        "https://podcasts.apple.com/us/podcast/the-daily/id1200361736",
    )


@pytest.mark.e2e
async def test_x_ingestion(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Text-only tweet via X API. No Deepgram cost (text content only).

    Stable target: Jack Dorsey's first-ever tweet (immutable, public, text-only).
    """
    await _ingest_and_wait(
        http_client,
        auth_headers,
        "https://x.com/jack/status/20",
    )


@pytest.mark.e2e
async def test_tiktok_ingestion(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """TikTok ingestion. Picks a short stable public video to minimize Deepgram
    cost (worker uses native subtitles when available, falls back to Deepgram).
    """
    await _ingest_and_wait(
        http_client,
        auth_headers,
        "https://www.tiktok.com/@scout2015/video/6718335390845095173",
    )


@pytest.mark.e2e
async def test_instagram_ingestion(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Instagram Reel via Apify. Reels are capped at 90s by IG, so cost is bounded.
    Uses Apify's native transcript field when available (no Deepgram cost).

    Fixture: NatGeo educational reel with clear English narration (not music-only).
    Previous fixture (CtMSAg9JqWZ) had no speech, causing empty transcript.
    """
    # NatGeo short educational reel with clear English narration.
    await _ingest_and_wait(
        http_client,
        auth_headers,
        "https://www.instagram.com/reel/CzHnAVRo6Cf/",
    )


@pytest.mark.e2e
async def test_document_upload(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Document upload via POST /api/media/upload (multipart). Uses a tiny
    1-page PDF fixture (~640 bytes) to keep LlamaParse cost minimal."""
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "sample.pdf"
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
    body = await poll_until(
        client=http_client,
        url=f"/api/media/{media_item_id}",
        headers=auth_headers,
        predicate=lambda b: b.get("status") in ("completed", "failed"),
        timeout_s=180,
        interval_s=5,
    )
    assert body.get("status") == "completed", (
        f"document upload stayed in {body.get('status')}: {body}"
    )
