"""Phase 4 happy path: article ingestion + on-demand artifact generation.

These tests reproduce the manual curl sequence used during the V1 launch plan
Phase 4 validation. They share a single `ingested_article` fixture so the four
artifact tests run against the same media item — total wall time ~30s for the
whole module on a warm AWS dev environment.
"""

from typing import Any, Dict

import httpx
import pytest

from tests.e2e.conftest import ARTICLE_FIXTURE_URL, poll_until


@pytest.mark.e2e
async def test_ingest_article_url_returns_202(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """POST /api/media/ingest-url accepts a valid article URL."""
    resp = await http_client.post(
        "/api/media/ingest-url",
        json={"url": ARTICLE_FIXTURE_URL},
        headers=auth_headers,
    )
    assert resp.status_code == 202, f"unexpected status {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body.get("media_item_id"), f"missing media_item_id: {body}"
    assert body.get("status") == "pending"
    assert body.get("source_platform") == "web"


@pytest.mark.e2e
async def test_article_reaches_completed(ingested_article: str) -> None:
    """The session-scoped fixture proves the article reached `completed`.

    Asserting it explicitly here is redundant but produces a clear test name
    in the report and isolates the ingestion phase from the artifact phase.
    """
    assert ingested_article, "ingested_article fixture did not return a media_item_id"


# =============================================================================
# Artifact generation — one test per type
# =============================================================================


async def _trigger_and_wait_artifact(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
    media_item_id: str,
    artifact_type: str,
) -> Dict[str, Any]:
    """POST then poll the artifact list until this type reaches `ready`."""
    trigger = await http_client.post(
        f"/api/media/{media_item_id}/artifacts",
        json={"artifact_type": artifact_type},
        headers=auth_headers,
    )
    assert trigger.status_code == 202, (
        f"artifact_type={artifact_type} trigger failed: "
        f"{trigger.status_code} {trigger.text}"
    )
    # Accept `queued` (fresh) or `ready` (idempotent: same fingerprint
    # already generated previously, e.g. when re-running the suite).
    assert trigger.json().get("status") in ("queued", "ready"), (
        f"unexpected trigger status: {trigger.json()}"
    )

    body = await poll_until(
        client=http_client,
        url=f"/api/media/{media_item_id}/artifacts",
        headers=auth_headers,
        predicate=lambda b: any(
            a.get("artifact_type") == artifact_type
            and a.get("status") in ("ready", "completed", "failed")
            for a in (b.get("artifacts") or b.get("items") or [])
        ),
        timeout_s=60,
        interval_s=3,
    )

    artifacts = body.get("artifacts") or body.get("items") or []
    matching = [a for a in artifacts if a.get("artifact_type") == artifact_type]
    assert matching, f"no {artifact_type} artifact found in {body}"
    artifact = matching[0]
    assert artifact.get("status") in ("ready", "completed"), (
        f"{artifact_type} did not reach ready: {artifact}"
    )
    assert artifact.get("s3_key"), f"{artifact_type} has no s3_key: {artifact}"
    return artifact


@pytest.mark.e2e
async def test_artifact_summary_e2e(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
    ingested_article: str,
) -> None:
    await _trigger_and_wait_artifact(
        http_client, auth_headers, ingested_article, "summary"
    )


@pytest.mark.e2e
async def test_artifact_notes_e2e(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
    ingested_article: str,
) -> None:
    await _trigger_and_wait_artifact(
        http_client, auth_headers, ingested_article, "notes"
    )


@pytest.mark.e2e
async def test_artifact_flashcards_e2e(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
    ingested_article: str,
) -> None:
    await _trigger_and_wait_artifact(
        http_client, auth_headers, ingested_article, "flashcards"
    )


@pytest.mark.e2e
async def test_artifact_quiz_e2e(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
    ingested_article: str,
) -> None:
    await _trigger_and_wait_artifact(
        http_client, auth_headers, ingested_article, "quiz"
    )
