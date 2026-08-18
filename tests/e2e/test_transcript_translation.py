"""E2E test for the source-agnostic transcript detect+translate step (task-192).

Scenario: a user with ``reading_language=fr`` ingests an English-language
Instagram Reel and requests a summary artifact.

Expected:
- the Deepgram transcription worker pre-translates the raw transcript to the
  user's ``reading_language`` (task-192 follow-up) and caches it in S3
  *before* marking the job completed, so by the time ingestion reaches
  ``ready_for_artifacts`` the FIRST ``/raw-content`` call is a cache hit and
  returns well within a few seconds. This is a regression test for the
  "Unable to load the transcript right now" bug: the synchronous translation
  call (GPT-5-nano, ~18-27s) was dangerously close to API Gateway HTTP API's
  hard 30s integration timeout, causing client-visible 504s even though the
  Lambda eventually succeeded. By pre-warming the cache inside the
  long-running (600s timeout) transcription worker, ``/raw-content`` must
  stay comfortably under that limit.
- the underlying transcript (``/raw-content``) is translated to French: the
  user's preferred reading language applies to the raw transcript too, with
  translation provenance exposed in the response's ``translation`` field.
- the summary artifact is also translated to French (``translation.is_translated``,
  ``translated_from="en"``, ``target_language="fr"``), and its content reads
  in French.

Uses a dedicated user (not the shared session ``test_user``) so that setting
``reading_language=fr`` cannot affect other E2E tests running in the same
session.
"""

from __future__ import annotations

import time
import uuid
from typing import AsyncIterator, Dict

import httpx
import pytest
import pytest_asyncio
from langdetect import DetectorFactory, detect

from tests.e2e.conftest import _teardown_user, poll_until

INSTAGRAM_REEL_URL = "https://www.instagram.com/reel/DZjAGUKSLeu/"

DetectorFactory.seed = 0


@pytest_asyncio.fixture(scope="module")
async def french_reader_headers(
    http_client: httpx.AsyncClient,
) -> AsyncIterator[Dict[str, str]]:
    """A dedicated user with ``reading_language=fr``, isolated from `test_user`."""
    suffix = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
    email = f"e2e-test-{suffix}@test.local"
    password = "E2eTestPassword123!"

    resp = await http_client.post(
        "/api/auth/register",
        json={"email": email, "password": password},
    )
    resp.raise_for_status()
    # /register returns a full session (access_token, refresh_token, user)
    user_id = resp.json()["user"]["id"]
    print(f"\n[e2e] created french_reader user {email} (id={user_id})")

    resp = await http_client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await http_client.patch(
        "/api/auth/me",
        json={"reading_language": "fr"},
        headers=headers,
    )
    resp.raise_for_status()
    assert resp.json()["reading_language"] == "fr"

    try:
        yield headers
    finally:
        await _teardown_user(http_client, user_id)


@pytest.mark.e2e
async def test_instagram_reel_translated_for_french_reader(
    http_client: httpx.AsyncClient,
    french_reader_headers: Dict[str, str],
) -> None:
    # 1. Ingest the English Instagram Reel.
    resp = await http_client.post(
        "/api/media/ingest-url",
        json={"url": INSTAGRAM_REEL_URL},
        headers=french_reader_headers,
    )
    resp.raise_for_status()
    media_item_id = resp.json()["media_item_id"]
    print(f"\n[e2e] ingested Instagram reel {media_item_id} ({INSTAGRAM_REEL_URL})")

    body = await poll_until(
        client=http_client,
        url=f"/api/media/{media_item_id}",
        headers=french_reader_headers,
        predicate=lambda b: b.get("media_item", {}).get("status")
        in ("ready_for_artifacts", "failed", "cancelled"),
        timeout_s=60,
        interval_s=3,
    )
    media_status = body.get("media_item", {}).get("status")
    assert media_status == "ready_for_artifacts", (
        f"ingestion stayed in {media_status}: {body}"
    )

    # 2. By the time ingestion reaches ready_for_artifacts, the Deepgram
    # worker has already pre-translated the transcript to the user's
    # reading_language (task-192 follow-up) and cached it in S3 -- it runs
    # this step synchronously, before marking the job completed, inside its
    # own 600s Lambda timeout. So no extra grace period is needed here.
    # The FIRST /raw-content call must now be a cache hit: a tight timeout
    # (well under API Gateway's hard 30s integration timeout) proves the
    # translation was NOT computed synchronously on this request. If the
    # pre-warm worker regresses, this call falls back to the synchronous
    # ~18-27s translation and times out here -- reproducing the "Unable to
    # load the transcript right now" bug users hit in production.
    resp = await http_client.get(
        f"/api/media/{media_item_id}/raw-content",
        headers=french_reader_headers,
        timeout=12.0,
    )
    resp.raise_for_status()
    raw_body = resp.json()
    raw_content = raw_body["content"]
    assert raw_content.strip(), "raw transcript is empty"
    assert detect(raw_content) == "fr", raw_content[:200]

    raw_translation = raw_body.get("translation") or {}
    assert raw_translation.get("detected_language") == "en", raw_translation
    assert raw_translation.get("target_language") == "fr", raw_translation
    assert raw_translation.get("is_translated") is True, raw_translation
    assert raw_translation.get("translated_from") == "en", raw_translation

    # 3. Request a summary artifact -> triggers the detect+translate step.
    # The transcript translation cache is already warm from step 2, so this
    # should be fast; the longer timeout is kept as a safety margin in case
    # of a cache miss (e.g. different target language).
    resp = await http_client.post(
        f"/api/media/{media_item_id}/artifacts",
        json={"artifact_type": "summary_short"},
        headers=french_reader_headers,
        timeout=120.0,
    )
    resp.raise_for_status()
    artifact_id = resp.json()["artifact_id"]

    artifact = await poll_until(
        client=http_client,
        url=f"/api/artifacts/{artifact_id}",
        headers=french_reader_headers,
        predicate=lambda b: b.get("status") in ("ready", "failed"),
        timeout_s=120,
        interval_s=3,
    )
    assert artifact.get("status") == "ready", (
        f"artifact stayed in {artifact.get('status')}: {artifact}"
    )

    resp = await http_client.get(
        f"/api/artifacts/{artifact_id}/content", headers=french_reader_headers
    )
    resp.raise_for_status()
    envelope = resp.json()["content"]

    # The transcript was detected as English and translated to French.
    translation = envelope.get("translation") or {}
    assert translation.get("detected_language") == "en", translation
    assert translation.get("target_language") == "fr", translation
    assert translation.get("is_translated") is True, translation
    assert translation.get("translated_from") == "en", translation

    # The summary itself is in French.
    summary = envelope["content"]
    summary_text = " ".join(
        [summary["headline"], summary["takeaway"], *summary["key_points"]]
    )
    assert detect(summary_text) == "fr", summary_text
