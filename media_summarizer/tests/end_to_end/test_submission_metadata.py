
import os
import uuid
# import pytest # Not available in container
import httpx
from datetime import datetime
import asyncio
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# @pytest.mark.e2e
# @pytest.mark.asyncio
async def test_submission_metadata_integrity():
    """
    Test that checking episode submission metadata (titles, dates) are correctly populated
    immediately after submission.
    
    This ensures that the 'Processing...' card on frontend has all necessary info
    without waiting for the job to complete.
    """
    # Check required environment variables
    if not os.getenv("PODCASTINDEXORG_API_KEY") or not os.getenv("PODCASTINDEXORG_API_SECRET"):
        print("PODCASTINDEXORG_API_KEY/SECRET not set - SKIPPING")
        return

    # We import app here to use with httpx.ASGITransport, assuming the test runs against the local app instance
    # defined in the test environment (standard logic in this project's e2e tests).
    from media_summarizer.api.main import app
    from media_summarizer.utils import database_async
    from media_summarizer.core.models.auth import TokenType

    # Use HTTPX to talk to the API
    # Note: "http://test" is a placeholder base URL for ASGI transport
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as api:

        # 1. User Registration & Setup
        # ----------------------------
        email = f"metadata-test-{uuid.uuid4().hex[:8]}@example.com"
        password = "TestPassword!123"

        # Register
        r = await api.post("/api/v1/auth/register", json={"email": email, "password": password})
        assert r.status_code == 201, f"Register failed: {r.text}"
        user_id = r.json()["id"]

        # Seed minutes to allow submission
        # (Reusing direct DB access logic from other tests would be ideal, but here we embed it for standalone safety)
        # We'll use a simplified version of _seed_minutes_for_user or just assume the test env allows it.
        # Let's try to verify email directly to bypass restrictions if any.
        
        # Verify Email
        tokens = await database_async.get_auth_tokens_by_user_id(user_id, token_type=TokenType.EMAIL_VERIFICATION)
        if tokens:
            tokens.sort(key=lambda t: t.created_at, reverse=True)
            verify_token = tokens[0].token
            await api.post("/api/v1/auth/verify-email", json={"token": verify_token, "email": email})
        
        # Login
        r = await api.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, "Login failed"
        access_token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Seed minutes via DB directly (hacky but reliable for tests)
        # Using a simpler approach: creating a minute bucket directly if possible, 
        # but importing boto3 inside async test might block.
        # Instead, we rely on the fact that registered users might get trial minutes 
        # OR we just rely on the mock/localstack environment.
        # Let's assume we need to seed:
        
        import boto3
        try:
             # Basic seed if not present
             dynamodb = boto3.resource(
                'dynamodb',
                endpoint_url=os.environ.get('AWS_ENDPOINT_URL'),
                region_name=os.environ.get('AWS_REGION'),
                aws_access_key_id='test',
                aws_secret_access_key='test'
             )
             table = dynamodb.Table(os.environ.get('USERS_TABLE', 'users'))
             # We can't easily seed minutes without the Minutes table structure knowledge
             # But looking at previous test, there is a minute_buckets table.
             mb_table = dynamodb.Table('minute_buckets')
             mb_table.put_item(Item={
                "id": f"mb_test_{user_id}",
                "user_id": user_id,
                "source_type": "pack",
                "minutes_remaining": 999,
                "minutes_total": 999,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "expires_at": datetime.now().isoformat()
             })
        except Exception as e:
            print(f"Warning: Failed to seed minutes: {e}")


        # 2. Search & Select Podcast
        # --------------------------
        # "Les Grosses Têtes" is good because we know it exists.
        # Use GET as per frontend implementation
        r = await api.get("/api/v1/podcasts/search", 
                           params={"query": "les grosses têtes", "page": 1, "page_size": 5, "clean": True},
                           headers=headers)
        
        assert r.status_code == 200, f"Search failed: {r.text}"
        data = r.json()
        assert data.get("total", 0) > 0, "No podcasts found"
        
        podcast = data["results"][0]
        feed_id = int(podcast["id"])
        podcast_title_expected = podcast["title"]
        print(f"Selected Podcast: {podcast_title_expected} (ID: {feed_id})")

        # 3. Get Episodes & Submit
        # ------------------------
        r = await api.post("/api/v1/podcast-search/episodes",
                           json={"feed_id": feed_id, "max_results": 5},
                           headers=headers)
        assert r.status_code == 200, "Get episodes failed"
        episodes_data = r.json()
        episodes = episodes_data.get("episodes", [])
        assert episodes, "No episodes found"
        
        # Pick the first one
        episode = episodes[0]
        episode_guid = episode["guid"]
        episode_title_expected = episode["title"]
        try:
             episode_date_expected = int(episode.get("date_published", 0))
        except:
             episode_date_expected = 0
             
        print(f"Selected Episode: {episode_title_expected} (GUID: {episode_guid}, Date: {episode_date_expected})")
        
        # Submit
        r = await api.post("/api/v1/podcast-search/submit-episode",
                           json={"feed_id": feed_id, "episode_guid": episode_guid},
                           headers=headers)
        
        assert r.status_code == 200, f"Submission failed: {r.text}"
        submission_resp = r.json()
        job_id = submission_resp["job_id"]
        
        # 4. Verify Metadata
        # ------------------
        
        print("Submission Response:", submission_resp)
        
        # Verify Submission Response keys
        assert submission_resp.get("podcast_title") == podcast_title_expected, \
            f"Submission Resp: Podcast title mismatch. Got '{submission_resp.get('podcast_title')}', expected '{podcast_title_expected}'"
            
        assert submission_resp.get("episode_title") == episode_title_expected, \
            f"Submission Resp: Episode title mismatch. Got '{submission_resp.get('episode_title')}', expected '{episode_title_expected}'"
            
        # 5. Fetch Job Details (frontend poll simulation)
        # -----------------------------------------------
        r = await api.get(f"/api/v1/jobs/{job_id}", headers=headers)
        assert r.status_code == 200, "Fetch job failed"
        job_details = r.json()
        
        print("Job Details from API:", job_details)
        
        # Verify Job Details keys
        # Podcast Title
        actual_podcast_title = job_details.get("podcast_title")
        assert actual_podcast_title == podcast_title_expected, \
            "Job Details: podcast_title does not match selected podcast"

        # Episode Title
        actual_episode_title = job_details.get("episode_title")
        assert actual_episode_title == episode_title_expected, \
            "Job Details: episode_title does not match selected episode"
            
        # Date Published (Now exposed in API)
        actual_date = job_details.get("episode_date_published")
        # Assert it matches or is at least present and valid
        # Note: Depending on processing, it should be passed through.
        assert actual_date is not None, "Job Details: episode_date_published is missing (None)"
        assert actual_date == episode_date_expected, f"Job Details: date mismatch {actual_date} != {episode_date_expected}"
        
        print("SUCCESS: Metadata integrity verified!")



if __name__ == "__main__":
    asyncio.run(test_submission_metadata_integrity())
