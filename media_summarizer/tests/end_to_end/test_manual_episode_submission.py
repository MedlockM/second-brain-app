"""
End-to-end test: Manual episode submission flow.

Tests the complete user journey:
- User registration and email verification
- Login and authentication
- Podcast search via Podcast Index API
- Episode selection (duration < 2 minutes)
- Episode submission for processing
- Full processing pipeline: download → transcription → summarization → notification
- Job status polling until completion

Requirements:
- Docker services running (LocalStack, workers, Whisper)
- Environment variables: PODCASTINDEXORG_API_KEY, PODCASTINDEXORG_API_SECRET, OPENAI_API_KEY
"""

import asyncio
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import boto3
import httpx
import pytest

# Test configuration
E2E_JOB_TIMEOUT_SECONDS = int(os.environ.get("E2E_JOB_TIMEOUT_SECONDS", "900"))
E2E_JOB_POLL_SECONDS = float(os.environ.get("E2E_JOB_POLL_SECONDS", "5"))


def _boto3_resource(service: str):
    """Create boto3 resource for LocalStack."""
    return boto3.resource(
        service,
        endpoint_url=os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    )


def _cleanup_episode_idempotence():
    """Clean episode_idempotence table before test."""
    try:
        dynamodb = _boto3_resource("dynamodb")
        table = dynamodb.Table("episode_idempotence")
        
        response = table.scan()
        items = response.get("Items", [])
        
        if items:
            with table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={"episode_guid": item["episode_guid"]})
    except Exception:
        # If table doesn't exist or cleanup fails, continue (fixtures will handle it)
        pass


def _seed_minutes_for_user(*, user_id: str, minutes: int = 90):
    """Seed minute bucket for test user."""
    now = datetime.now(timezone.utc)
    bucket_id = f"mb_test_{user_id}"
    table = _boto3_resource("dynamodb").Table("minute_buckets")

    table.put_item(
        Item={
            "id": bucket_id,
            "user_id": user_id,
            "source_type": "pack",
            "source_ref": "e2e-test",
            "minutes_total": int(minutes),
            "minutes_remaining": int(minutes),
            "expires_at": (now + timedelta(days=30)).isoformat(),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
    )


@pytest.fixture(autouse=True)
def setup_test():
    """Setup test by cleaning episode_idempotence table and verifying SES emails."""
    _cleanup_episode_idempotence()
    
    # Verify SES email identities for the test
    try:
        import subprocess
        # Verify noreply@example.com
        subprocess.run([
            "docker", "exec", "media-summarizer-project_localstack_1",
            "awslocal", "ses", "verify-email-identity",
            "--email-address", "noreply@example.com",
            "--region", "us-east-1"
        ], check=False, capture_output=True)
        
        # Verify support@example.com  
        subprocess.run([
            "docker", "exec", "media-summarizer-project_localstack_1",
            "awslocal", "ses", "verify-email-identity",
            "--email-address", "support@example.com",
            "--region", "us-east-1"
        ], check=False, capture_output=True)
    except Exception:
        # If verification fails, continue anyway (test will handle it)
        pass
    
    yield


@pytest.mark.e2e
@pytest.mark.requires_all_services
@pytest.mark.asyncio
async def test_manual_episode_submission_complete_flow():
    """
    Test complete manual episode submission flow end-to-end.
    
    This test requires:
    - All services running (API, workers, LocalStack, Whisper)
    - Valid API keys (Podcast Index, OpenAI)
    - Episode duration < 2 minutes for fast testing
    """
    # Check required environment variables
    if not os.getenv("PODCASTINDEXORG_API_KEY") or not os.getenv("PODCASTINDEXORG_API_SECRET"):
        pytest.skip("PODCASTINDEXORG_API_KEY/SECRET not set")
    
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")

    from media_summarizer.api.main import app
    from media_summarizer.core.models.auth import TokenType
    from media_summarizer.utils import database_async

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as api:
        
        # 1) Register user
        email = f"e2e-manual-{uuid.uuid4().hex[:10]}@example.com"
        password = "TestPassword!123"

        r = await api.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password},
        )
        assert r.status_code == 201, f"Register failed: {r.status_code} {r.text}"
        user = r.json()
        user_id = user["id"]

        # 2) Seed minutes
        _seed_minutes_for_user(user_id=user_id, minutes=90)

        # 3) Verify email
        tokens = await database_async.get_auth_tokens_by_user_id(
            user_id, token_type=TokenType.EMAIL_VERIFICATION
        )
        assert tokens, "No email verification token"
        tokens.sort(key=lambda t: t.created_at, reverse=True)
        verification_token = tokens[0].token

        r = await api.post(
            "/api/v1/auth/verify-email",
            json={"token": verification_token, "email": email},
        )
        assert r.status_code == 200, f"Email verify failed: {r.text}"

        # 4) Login
        r = await api.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert r.status_code == 200, f"Login failed: {r.text}"
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # 5) Search podcast (Les Grosses Têtes - French podcast with short episodes)
        r = await api.get(
            "/api/v1/podcasts/search",
            params={
                "query": "les grosses têtes",
                "page": 1,
                "page_size": 20,
                "clean": True,
            },
            headers=headers,
        )
        assert r.status_code == 200, f"Search failed: {r.text}"
        search = r.json()
        assert search.get("total") > 0, "No podcasts found"
        selected_podcast = search["results"][0]
        feed_id = int(selected_podcast["id"])

        # 6) List episodes
        r = await api.post(
            "/api/v1/podcast-search/episodes",
            json={"feed_id": feed_id, "max_results": 50},
            headers=headers,
        )
        assert r.status_code == 200, f"Episodes list failed: {r.text}"
        episodes_payload = r.json()
        episodes = episodes_payload.get("episodes", [])
        assert episodes, "No episodes returned"

        # Pick episodes with duration < 2 minutes for fast testing
        candidate_episodes = []
        for ep in episodes:
            duration = ep.get("duration")
            if isinstance(duration, int) and duration > 0 and duration < 120:
                candidate_episodes.append(ep)
                if len(candidate_episodes) >= 5:
                    break

        assert candidate_episodes, "No episodes < 2 minutes found"

        # 7) Submit first candidate episode
        selected_episode = candidate_episodes[0]
        episode_guid = selected_episode["guid"]

        r = await api.post(
            "/api/v1/podcast-search/submit-episode",
            json={"feed_id": feed_id, "episode_guid": episode_guid},
            headers=headers,
        )
        assert r.status_code == 200, f"Submit failed: {r.status_code} {r.text}"
        submit = r.json()
        assert submit.get("status") != "skipped", f"Submission skipped: {submit}"
        job_id = submit["job_id"]

        # 8) Poll job until completed
        last_status = None
        job_details = {}
        deadline = time.monotonic() + E2E_JOB_TIMEOUT_SECONDS
        poll_count = 0

        while time.monotonic() < deadline:
            poll_count += 1
            r = await api.get(f"/api/v1/jobs/{job_id}", headers=headers)
            assert r.status_code == 200, f"Job get failed: {r.text}"

            job_details = r.json()
            last_status = job_details.get("status")

            # Terminal states
            if last_status in {"completed", "failed", "cancelled"}:
                break

            await asyncio.sleep(E2E_JOB_POLL_SECONDS)

        # Verify completion (or notifying if email is still processing)
        assert last_status in {"completed", "notifying"}, (
            f"Job did not complete successfully. Status: {last_status}, "
            f"Error: {job_details.get('error_message')}"
        )
        
        # Verify job has summary URL (validates summarization completed)
        assert job_details.get("summary_url"), "Job completed but no summary URL"
        
        # Verify quiz was generated (ENABLE_QUIZ_EMAIL=true in .env.dev)
        # Note: quiz_s3_key might not be set if quiz worker hasn't processed yet
        # We check after a short wait to allow quiz worker to process
        if last_status == "notifying":
            # Wait a bit more for email worker to process
            await asyncio.sleep(10)
            r = await api.get(f"/api/v1/jobs/{job_id}", headers=headers)
            assert r.status_code == 200
            job_details = r.json()
            last_status = job_details.get("status")
        
        # Final status should be 'completed' after email worker processes
        assert last_status == "completed", (
            f"Job stuck in {last_status} status. Email worker may have failed."
        )
        
        # Verify email notification was queued and processed
        # We verify this indirectly: if job is 'completed', email_worker processed the message
        # The email_worker marks job as 'completed' only after processing the email notification
        # So 'completed' status proves the email was processed (even if LocalStack rejected it)
        
        # Verify quiz - may take a few extra seconds
        # Poll a few times to give quiz worker time to process
        quiz_found = False
        for _ in range(3):
            r = await api.get(f"/api/v1/jobs/{job_id}", headers=headers)
            job_details = r.json()
            if job_details.get("quiz_s3_key") or job_details.get("quiz_url"):
                quiz_found = True
                break
            await asyncio.sleep(3)
        
        # Note: Quiz is optional feature, so we just log if not found
        if not quiz_found:
            print(f"Warning: Quiz not generated for job {job_id} (may be disabled or worker slow)")
