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

import os

# Force AWS_REGION to match the dev env BEFORE any media_summarizer import.
# Reason: python-dotenv loads .env with override=False, so a shell-exported
# AWS_REGION (e.g. AWS_REGION=us-east-1 from the developer's shell init) wins
# over .env's AWS_REGION=eu-west-3. The teardown then queries DynamoDB tables
# in the wrong region and gets ResourceNotFoundException.
# Override here to make E2E runs robust regardless of shell state.
os.environ["AWS_REGION"] = os.getenv("E2E_AWS_REGION", "eu-west-3")
os.environ["AWS_DEFAULT_REGION"] = os.environ["AWS_REGION"]

# Export required table env vars BEFORE any media_summarizer import.
# Reason: database_async.py calls required_env() at module load (task-237),
# which raises RuntimeError if these are unset. E2E runs against dev, so
# hardcode the -dev suffixed names here.
os.environ.setdefault("USERS_TABLE", "users-dev")
os.environ.setdefault("PROCESSING_JOBS_TABLE", "processing_jobs-dev")
os.environ.setdefault("AUTH_TOKENS_TABLE", "auth_tokens-dev")
os.environ.setdefault("USER_FOLDERS_TABLE", "user_folders-dev")
os.environ.setdefault("USER_TAGS_TABLE", "user_tags-dev")
os.environ.setdefault("USER_RSS_FEEDS_TABLE", "user_rss_feeds-dev")

import asyncio
import subprocess
import sys
import time
import uuid
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, Optional

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
        "/api/auth/register",
        json={"email": email, "password": password},
    )
    resp.raise_for_status()
    # /register returns a full session (access_token, refresh_token, user)
    user_id = resp.json()["user"]["id"]
    user = {"email": email, "password": password, "id": user_id}

    print(f"\n[e2e] created test user {email} (id={user_id})")

    try:
        yield user
    finally:
        await _teardown_user(http_client, user)


@pytest_asyncio.fixture(scope="session")
async def auth_token(http_client: httpx.AsyncClient, test_user: Dict[str, str]) -> str:
    resp = await http_client.post(
        "/api/auth/login",
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
        timeout_s=30,
        interval_s=2,
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


async def _teardown_user(client: httpx.AsyncClient, user: Dict[str, str]) -> None:
    """Best-effort cleanup of everything a test user persisted in AWS dev.

    Two steps, in order:

    1. ``DELETE /api/account`` (task-224), so a real run exercises the shipped
       deletion flow rather than only the test-side shortcut.
    2. ``scripts/delete_e2e_account.py`` (task-247), which sweeps both -dev and
       unsuffixed tables and removes every child row (auth tokens, processing
       jobs, artifacts, tags, folders, submissions, usage counters), reusing the
       same logic as purge_e2e_accounts.py (task-246).

    Step 2 always runs, whatever step 1 answered: the API purge is not the
    cleanup guarantee, the sweep is.

    Errors are printed but not raised — teardown must not turn a passing test
    into a failure.
    """
    user_id = user["id"]
    email = user["email"]
    print(f"\n[e2e] teardown user {user_id} ({email})")

    # First exercise the real deletion flow (task-224): DELETE /api/account
    # derives the account from the session and takes no id. The sweep below
    # remains the cleanup guarantee, so a failure here must not fail the test —
    # but it must not pass unnoticed either. task-253: this teardown was the
    # only thing exercising the shipped deletion path, and it printed a 404 for
    # a day without anything going red. An unexpected status now raises a
    # warning, which surfaces in the pytest summary.
    delete_headers = await _login_headers(client, user)
    if delete_headers:
        try:
            resp = await client.delete("/api/account", headers=delete_headers)
            print(f"[e2e]   api DELETE /api/account ({user_id}) -> {resp.status_code}")
            if resp.status_code != 204:
                warnings.warn(
                    f"DELETE /api/account answered {resp.status_code}, expected 204. "
                    "A 404 means the route is not mounted on the deployed image "
                    "(see task-253); the mobile deletion flow in "
                    "mobile/src/services/accountService.ts calls this exact "
                    "endpoint, and App Store guideline 5.1.1(v) requires it.",
                    stacklevel=2,
                )
        except Exception as exc:
            print(f"[e2e]   api DELETE failed: {exc!r}")
            warnings.warn(f"DELETE /api/account raised {exc!r}", stacklevel=2)

    # Guaranteed sweep (task-247): handles both -dev and unsuffixed tables and
    # removes the child rows the API purge may not have reached.
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "delete_e2e_account.py"

    try:
        result = subprocess.run(
            [sys.executable, str(script), email],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        if result.returncode != 0:
            print(
                f"[e2e] teardown script exited {result.returncode}; "
                "account may not have been deleted"
            )
    except Exception as exc:
        print(f"[e2e] teardown failed: {exc!r}")

    print(f"[e2e] teardown done for {user_id}")


async def _login_headers(
    client: httpx.AsyncClient, user: Dict[str, str]
) -> Optional[Dict[str, str]]:
    """Log the test user in and return Bearer headers, or None on failure.

    The session-scoped `auth_token` fixture may have expired over a long run, so
    the teardown logs in again rather than reusing it.
    """
    try:
        resp = await client.post(
            "/api/auth/login",
            json={"email": user["email"], "password": user["password"]},
        )
        resp.raise_for_status()
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}
    except Exception as exc:
        print(f"[e2e]   login for teardown failed: {exc!r}")
        return None
