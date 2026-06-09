"""E2E test fixtures for Phase 4 validation against AWS dev.

These tests hit a real backend API (default: AWS dev) and create real DynamoDB
records, S3 objects, and SQS messages. The session-scoped `test_user` fixture
takes care of teardown — it deletes the user, their auth tokens, processing
jobs, media artifacts, tags and folders at the end of the session, succeed or
fail.

Configuration:
- API_BASE_URL env var (default: AWS dev URL).
- AWS credentials read by media_summarizer.utils.database_async via .env at
  the repo root.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any, Awaitable, Callable, Dict, Optional

import httpx
import pytest
import pytest_asyncio

DEFAULT_API_URL = "https://jji077bi8e.execute-api.eu-west-3.amazonaws.com"
ARTICLE_FIXTURE_URL = "https://en.wikipedia.org/wiki/Personal_knowledge_management"


@pytest.fixture(scope="session")
def api_base_url() -> str:
    return os.getenv("API_BASE_URL", DEFAULT_API_URL).rstrip("/")


@pytest_asyncio.fixture(scope="session")
async def http_client(api_base_url: str):
    async with httpx.AsyncClient(base_url=api_base_url, timeout=30.0) as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def test_user(http_client: httpx.AsyncClient):
    """Register a fresh user; teardown deletes everything they own."""
    suffix = f"{int(time.time())}-{uuid.uuid4().hex[:6]}"
    email = f"e2e-test-{suffix}@test.local"
    password = "E2eTestPassword123!"

    resp = await http_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    resp.raise_for_status()
    user_id = resp.json()["id"]
    user = {"email": email, "password": password, "id": user_id}

    print(f"\n[e2e] created test user {email} (id={user_id})")

    try:
        yield user
    finally:
        await _teardown_user(http_client, user_id)


@pytest_asyncio.fixture(scope="session")
async def auth_token(http_client: httpx.AsyncClient, test_user: Dict[str, str]) -> str:
    resp = await http_client.post(
        "/api/v1/auth/login",
        json={"email": test_user["email"], "password": test_user["password"]},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


@pytest.fixture(scope="session")
def auth_headers(auth_token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}


@pytest_asyncio.fixture(scope="session")
async def ingested_article(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> str:
    """Ingest a Wikipedia article and wait for `completed`. Returns media_item_id.

    Cached per-session so all artifact tests can reuse the same article
    (saves ~15s per artifact test).
    """
    resp = await http_client.post(
        "/api/media/ingest-url",
        json={"url": ARTICLE_FIXTURE_URL},
        headers=auth_headers,
    )
    resp.raise_for_status()
    payload = resp.json()
    media_item_id = payload["media_item_id"]
    print(f"\n[e2e] ingested article {media_item_id} ({ARTICLE_FIXTURE_URL})")

    await poll_until(
        client=http_client,
        url=f"/api/media/{media_item_id}",
        headers=auth_headers,
        predicate=lambda body: body.get("status") in ("completed", "failed"),
        timeout_s=120,
        interval_s=3,
    )
    final_status = (await http_client.get(
        f"/api/media/{media_item_id}", headers=auth_headers
    )).json()["status"]
    assert final_status == "completed", (
        f"Article ingestion did not complete: status={final_status}"
    )
    return media_item_id


# =============================================================================
# Helpers
# =============================================================================


async def poll_until(
    client: httpx.AsyncClient,
    url: str,
    headers: Dict[str, str],
    predicate: Callable[[Dict[str, Any]], bool],
    timeout_s: float = 60.0,
    interval_s: float = 5.0,
) -> Dict[str, Any]:
    """Poll `url` until `predicate(body)` is truthy or timeout. Returns last body.

    Raises TimeoutError if predicate never matches.
    """
    deadline = asyncio.get_event_loop().time() + timeout_s
    last_body: Dict[str, Any] = {}
    while asyncio.get_event_loop().time() < deadline:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        last_body = resp.json()
        if predicate(last_body):
            return last_body
        await asyncio.sleep(interval_s)
    raise TimeoutError(
        f"poll_until timed out after {timeout_s}s on {url}; last body: {last_body}"
    )


# =============================================================================
# Teardown
# =============================================================================


async def _teardown_user(client: httpx.AsyncClient, user_id: str) -> None:
    """Best-effort cleanup of everything a test user persisted in AWS dev.

    Each step is wrapped in try/except so a partial failure doesn't block the
    rest. Errors are printed but not raised — teardown must not turn a passing
    test into a failure.
    """
    print(f"\n[e2e] teardown user {user_id}")

    try:
        from media_summarizer.utils import database_async
    except Exception as exc:
        print(f"[e2e] teardown: cannot import database_async ({exc!r}); skipping")
        return

    await _teardown_user_inner(client, user_id, database_async)


async def _teardown_user_inner(
    client: httpx.AsyncClient,
    user_id: str,
    database_async,  # type: ignore[no-redef]
) -> None:
    # 1. List orphaned data before deleting.
    jobs = await _safe_call(
        "list processing jobs",
        lambda: database_async.get_processing_jobs_by_user_id(user_id),
        default=[],
    )
    auth_tokens = await _safe_call(
        "list auth tokens",
        lambda: database_async.get_auth_tokens_by_user_id(user_id),
        default=[],
    )
    tags = await _safe_call(
        "list tags",
        lambda: database_async.get_tags_by_user_id(user_id),
        default=[],
    )
    folders = await _safe_call(
        "list folders",
        lambda: database_async.get_folders_by_user_id(user_id),
        default=[],
    )

    # 2. Delete all artifacts for each processing job (via media_artifacts GSI).
    for job in jobs or []:
        job_id = getattr(job, "id", None) or getattr(job, "job_id", None)
        if not job_id:
            continue
        await _safe_call(
            f"delete artifacts for media {job_id}",
            lambda jid=job_id: _delete_artifacts_for_media(jid),
        )

    # 3. Delete processing jobs.
    for job in jobs or []:
        job_id = getattr(job, "id", None) or getattr(job, "job_id", None)
        if not job_id:
            continue
        await _safe_call(
            f"delete processing job {job_id}",
            lambda jid=job_id: database_async.delete_processing_job(jid),
        )

    # 4. Delete auth tokens.
    for token in auth_tokens or []:
        token_id = getattr(token, "id", None) or getattr(token, "token_id", None)
        if not token_id:
            continue
        await _safe_call(
            f"delete auth token {token_id}",
            lambda tid=token_id: database_async.delete_auth_token(tid),
        )

    # 5. Delete tags + folders (no high-level helpers — direct boto3).
    for tag in tags or []:
        tag_id = getattr(tag, "id", None) or getattr(tag, "tag_id", None)
        if tag_id:
            await _safe_call(
                f"delete tag {tag_id}",
                lambda tid=tag_id: _delete_item(database_async.USER_TAGS_TABLE, "id", tid),
            )
    for folder in folders or []:
        folder_id = getattr(folder, "id", None) or getattr(folder, "folder_id", None)
        if folder_id:
            await _safe_call(
                f"delete folder {folder_id}",
                lambda fid=folder_id: _delete_item(database_async.USER_FOLDERS_TABLE, "id", fid),
            )

    # 6. Delete the user — try API first (exercises the real flow), fallback
    # to direct DB delete.
    api_ok = False
    try:
        # The DELETE endpoint requires authentication. We may have already
        # invalidated the token by deleting auth_tokens above, so this can
        # legitimately fail. Use the direct DB call as fallback.
        resp = await client.delete(f"/api/v1/users/{user_id}")
        api_ok = resp.status_code in (200, 204, 404)
        print(f"[e2e]   api DELETE /users/{user_id} -> {resp.status_code}")
    except Exception as exc:
        print(f"[e2e]   api DELETE failed: {exc!r}")
    if not api_ok:
        await _safe_call(
            f"delete user {user_id} (db fallback)",
            lambda: database_async.delete_user(user_id),
        )

    print(f"[e2e] teardown done for {user_id}")


async def _safe_call(
    label: str,
    fn: Callable[[], Awaitable[Any]],
    default: Optional[Any] = None,
) -> Any:
    try:
        result = await fn()
        return result
    except Exception as exc:
        print(f"[e2e]   {label} failed: {exc!r}")
        return default


async def _delete_artifacts_for_media(media_item_id: str) -> None:
    """Query media_artifacts GSI media-item-index and delete every row."""
    import aioboto3

    from media_summarizer.utils.media_artifacts import MEDIA_ARTIFACTS_TABLE

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    session = aioboto3.Session(region_name=region)
    async with session.resource("dynamodb") as dynamodb:
        table = await dynamodb.Table(MEDIA_ARTIFACTS_TABLE)
        resp = await table.query(
            IndexName="media-item-index",
            KeyConditionExpression="media_item_id = :mid",
            ExpressionAttributeValues={":mid": media_item_id},
        )
        for item in resp.get("Items", []):
            artifact_id = item.get("artifact_id")
            if artifact_id:
                await table.delete_item(Key={"artifact_id": artifact_id})


async def _delete_item(table_name: str, key_name: str, key_value: str) -> None:
    """Delete a single item by primary key from any DynamoDB table."""
    import aioboto3

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    session = aioboto3.Session(region_name=region)
    async with session.resource("dynamodb") as dynamodb:
        table = await dynamodb.Table(table_name)
        await table.delete_item(Key={key_name: key_value})
