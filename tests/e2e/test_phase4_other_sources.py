"""Skeletons for non-article sources discovered during Phase 4.

Each test submits a representative URL and is currently `xfail` or `skip`
because the source has not been validated end-to-end yet (or has a known
upstream issue). When the source becomes stable, flip the marker to make it
part of the regular happy path.
"""

from typing import Dict

import httpx
import pytest

from tests.e2e.conftest import poll_until, upload_document_file


async def _ingest_and_wait(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
    url: str,
    timeout_s: float = 30,
) -> str:
    """Submit a URL and poll until the job reaches completed/failed.

    Default 30s timeout (was 180s): if a happy-path E2E takes more than 30s,
    something is genuinely wrong (bot detection, CDN block, etc.) and we want
    the test to fail fast rather than hang. Override per-test if needed for
    sources with legitimately longer transcription times.
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
    timeout_s: float = 60,
) -> str:
    """Submit a podcast URL via /api/podcasts/submit, then poll /api/media/{id}.

    The podcasts/submit endpoint exercises the full pipeline:
    URL → PodcastIndex resolver → audio_url enclosure → Deepgram → artifacts.
    Returns job_id (== media_item_id).
    """
    resp = await http_client.post(
        "/api/podcasts/submit",
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

      Apple Podcasts EPISODE URL → /api/podcasts/submit → PodcastIndex
      resolver → audio enclosure URL → Deepgram → completed.

    Fixture is an episode-level URL (with `?i=<episode_id>`). Show-level
    URLs (without `?i=`) may also work but force the resolver to pick "the
    most recent episode" which is non-deterministic and may surface short
    spoken-word episodes randomly. Episode-level URLs are deterministic —
    the resolver normalizes the episode ID and queries PodcastIndex
    directly for that specific episode.
    """
    # French podcast episode "Pépite — Ils ont le bracelet, ils mangent tout"
    # show_id=369369012, episode_id=1000771893347 — owner-provided fixture
    # 2026-06-09. Stable URL pattern (Apple Podcasts URLs are immutable).
    await _submit_podcast_and_wait(
        http_client,
        auth_headers,
        "https://podcasts.apple.com/fr/podcast/p%C3%A9pite-ils-ont-le-bracelet-ils-mangent-tout-az-d%C3%A9teste/id369369012?i=1000771893347",
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
    """TikTok ingestion happy path with native auto-captions.

    Fixture: NatGeo TikTok with English voiceover and auto-captions enabled.
    yt-dlp from Lambda picks up the native captions, no Deepgram fallback
    needed.

    Caveats:
    - TikTok sometimes blocks AWS Lambda IPs on certain videos (cf. task-140).
      If this fixture starts failing with "IP address is blocked", swap for
      another stable account (@cnn, @washingtonpost, @ted) — most major media
      accounts work.
    - Videos without native auto-captions force a Deepgram fallback that fails
      with 403 from TikTok's CDN (cf. task-139). Always pick a fixture with
      auto-captions for happy-path E2E.
    """
    await _ingest_and_wait(
        http_client,
        auth_headers,
        "https://www.tiktok.com/@natgeo/video/7164880277226016043",
    )


@pytest.mark.e2e
async def test_instagram_ingestion(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Instagram Reel via Apify. Reels are capped at 90s by IG, so cost is bounded.
    Uses Apify's native transcript field when available (no Deepgram cost).

    Fixture: owner-provided stable public Reel (2026-06-09).
    """
    await _ingest_and_wait(
        http_client,
        auth_headers,
        "https://www.instagram.com/natgeo/reel/DZaHxtTglqb/?hl=fr",
    )


@pytest.mark.e2e
async def test_document_upload(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Document upload: presigned PUT then POST /api/media/upload with the key.
    Uses a tiny 1-page PDF fixture (~640 bytes) to keep LlamaParse cost minimal."""
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "sample.pdf"
    resp = await upload_document_file(
        http_client,
        auth_headers,
        file_name="sample.pdf",
        content=fixture.read_bytes(),
        content_type="application/pdf",
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
        timeout_s=60,
        interval_s=3,
    )
    assert body.get("status") == "completed", (
        f"document upload stayed in {body.get('status')}: {body}"
    )
