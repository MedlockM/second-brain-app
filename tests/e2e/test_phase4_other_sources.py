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


@pytest.mark.e2e
@pytest.mark.skip(reason="podcast E2E never validated; flip to active when ready")
async def test_podcast_ingestion(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    await _ingest_and_wait(
        http_client,
        auth_headers,
        "https://podcasts.apple.com/us/podcast/the-knowledge-project/id990149481",
    )


@pytest.mark.e2e
@pytest.mark.skip(reason="X (Twitter) E2E never validated; flip to active when ready")
async def test_x_ingestion(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    await _ingest_and_wait(
        http_client,
        auth_headers,
        "https://x.com/elonmusk/status/1234567890",
    )


@pytest.mark.e2e
@pytest.mark.skip(reason="TikTok E2E never validated; flip to active when ready")
async def test_tiktok_ingestion(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    await _ingest_and_wait(
        http_client,
        auth_headers,
        "https://www.tiktok.com/@scout2015/video/6718335390845095173",
    )


@pytest.mark.e2e
@pytest.mark.skip(reason="Instagram E2E never validated; flip to active when ready")
async def test_instagram_ingestion(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    await _ingest_and_wait(
        http_client,
        auth_headers,
        "https://www.instagram.com/reel/CtMSAg9JqWZ/",
    )


@pytest.mark.e2e
@pytest.mark.skip(reason="PDF/DOCX/PPTX upload E2E never validated; uses a different endpoint")
async def test_document_upload(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Document upload uses POST /api/media/upload (multipart), not ingest-url.

    When activated, this test should upload a small PDF fixture and poll until
    completion via the same status flow.
    """
    raise NotImplementedError("document upload skeleton, fill in when ready")
