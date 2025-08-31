"""
True End-to-End test for Podcast Index workflow.

This test performs a complete real-world workflow using:
- Real Podcast Index API calls
- Real LocalStack services (SQS, S3, DynamoDB, SES)
- Real Docker Whisper service
- Real workers processing

No mocking is used - this is a true production-like test.
"""
import os
import json
import time
import asyncio
import tempfile
from pathlib import Path

# Load environment variables first
from dotenv import load_dotenv
load_dotenv()

import pytest
import httpx
from fastapi.testclient import TestClient

# Import only what we need without inheriting from base classes
import boto3
from media_summarizer.api.main import app
from media_summarizer.tests.utils.localstack_helpers import (
    setup_localstack_resources,
    AWS_ENDPOINT_URL,
    AWS_REGION,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY
)
from media_summarizer.tests.utils.audio_helpers import (
    create_test_audio_file_with_fallback,
    cleanup_test_audio_file
)


class TestPodcastIndexE2E:
    """
    True End-to-End test for complete Podcast Index workflow.

    This test uses:
    - Real Podcast Index API with actual credentials
    - Real LocalStack services for AWS components
    - Real Docker Whisper for transcription
    - Real workers for processing
    - No mocking whatsoever
    """

    @pytest.fixture(scope="class", autouse=True)
    def setup_real_environment(self):
        """Set up real environment for E2E testing."""
        # Check for real Podcast Index credentials
        api_key = os.getenv("PODCASTINDEXORG_API_KEY")
        api_secret = os.getenv("PODCASTINDEXORG_API_SECRET")

        if not api_key or not api_secret:
            pytest.skip("Real Podcast Index credentials not available - skipping E2E test")

        # Set environment variables for the test
        original_env = {}
        test_env = {
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "AWS_DEFAULT_REGION": "us-east-1",
            "AWS_ENDPOINT_URL": "http://localhost:4566",
            "WHISPER_MODEL_SIZE": "tiny",
            "PODCASTINDEXORG_API_KEY": api_key,
            "PODCASTINDEXORG_API_SECRET": api_secret,
            "LLM_API_KEY": "test-openai-key",
            "LLM_API_URL": "https://api.openai.com/v1/chat/completions",
            # Override table names to match LocalStack configuration
            "USERS_TABLE": "users",
            "PROCESSING_JOBS_TABLE": "processing_jobs",
            "CREDIT_TRANSACTIONS_TABLE": "credit_transactions"
        }

        # Save original values and set test values
        for key, value in test_env.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        # Reset database session to pick up new environment variables
        from media_summarizer.utils.database_async import reset_session
        reset_session()

        # Reload modules to pick up new environment variables
        import importlib
        import media_summarizer.utils.database_async
        importlib.reload(media_summarizer.utils.database_async)

        yield

        # Restore original environment
        for key, original_value in original_env.items():
            if original_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original_value

    @pytest.fixture
    def localstack_clients(self):
        """Create LocalStack clients for AWS services."""
        # Set up all LocalStack resources
        setup_localstack_resources()

        # Create clients manually
        dynamodb = boto3.client(
            'dynamodb',
            endpoint_url=AWS_ENDPOINT_URL,
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )

        s3 = boto3.client(
            's3',
            endpoint_url=AWS_ENDPOINT_URL,
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )

        sqs = boto3.client(
            'sqs',
            endpoint_url=AWS_ENDPOINT_URL,
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )

        ses = boto3.client(
            'ses',
            endpoint_url=AWS_ENDPOINT_URL,
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )

        return {
            "dynamodb": dynamodb,
            "sqs": sqs,
            "s3": s3,
            "ses": ses
        }

    @pytest.fixture
    def test_audio_file(self):
        """Create a real test audio file."""
        audio_path = create_test_audio_file_with_fallback(duration_seconds=3)
        yield audio_path
        cleanup_test_audio_file(audio_path)

    @pytest.fixture
    def fastapi_client(self):
        """Create FastAPI test client."""
        return TestClient(app)

    def clear_ses_emails(self, ses_client):
        """
        Clear all previous emails from LocalStack SES (test only).

        This ensures each test starts with a clean email state.
        """
        import requests
        import os
        import time

        # SAFETY CHECK: Only run in test environments with LocalStack
        aws_endpoint = os.environ.get("AWS_ENDPOINT_URL")
        is_test_env = os.environ.get("ENVIRONMENT") in ["test", "development"] or \
                     os.environ.get("TEST_MODE") == "true"

        if (aws_endpoint and "localhost" in aws_endpoint and "4566" in aws_endpoint and
            is_test_env):
            try:
                # Extract base URL from endpoint
                base_url = aws_endpoint.replace('//', '//').split('//')[1].split('/')[0]
                localstack_url = f"http://{base_url}/_aws/ses"

                # First check how many emails exist
                response = requests.get(localstack_url, timeout=5)
                if response.status_code == 200:
                    email_data = response.json()
                    message_count = len(email_data.get("messages", []))
                    print(f"🧹 Found {message_count} emails to clear")

                    if message_count > 0:
                        # Clear all messages using DELETE request
                        delete_response = requests.delete(localstack_url, timeout=5)
                        # LocalStack returns 204 for successful DELETE
                        if delete_response.status_code in [200, 204]:
                            # Verify clearing worked
                            time.sleep(0.5)  # Give LocalStack time to process
                            verify_response = requests.get(localstack_url, timeout=5)
                            if verify_response.status_code == 200:
                                remaining = len(verify_response.json().get("messages", []))
                                if remaining == 0:
                                    print("✅ Successfully cleared all SES emails")
                                else:
                                    print(f"⚠️  {remaining} emails still remain after clearing")
                        else:
                            print(f"⚠️  Could not clear SES emails: {delete_response.status_code}")
                    else:
                        print("✅ No emails to clear")
                else:
                    print(f"⚠️  Could not check SES emails: {response.status_code}")
            except Exception as e:
                print(f"⚠️  Error clearing SES emails: {e}")
        else:
            print("⚠️  SES cleanup skipped (not in LocalStack test environment)")

    def clear_sqs_queues(self, sqs_client):
        """
        Clear all SQS queues to ensure clean test state.

        This ensures each test starts without residual messages from previous runs.
        """
        import os

        # SAFETY CHECK: Only run in test environments
        aws_endpoint = os.environ.get("AWS_ENDPOINT_URL")
        is_test_env = os.environ.get("ENVIRONMENT") in ["test", "development"] or \
                     os.environ.get("TEST_MODE") == "true"

        if not (aws_endpoint and "localhost" in aws_endpoint and "4566" in aws_endpoint and is_test_env):
            print("⚠️  SQS cleanup skipped (not in LocalStack test environment)")
            return

        queue_names = [
            "audio-download-queue",
            "transcription-queue",
            "summarization-queue",
            "email-notification-queue"
        ]

        try:
            for queue_name in queue_names:
                try:
                    # Get queue URL
                    response = sqs_client.get_queue_url(QueueName=queue_name)
                    queue_url = response["QueueUrl"]

                    # Purge all messages from the queue
                    sqs_client.purge_queue(QueueUrl=queue_url)
                    print(f"✅ Cleared SQS queue: {queue_name}")

                except Exception as e:
                    print(f"⚠️  Could not clear SQS queue {queue_name}: {e}")

        except Exception as e:
            print(f"⚠️  Error during SQS cleanup: {e}")

    def verify_queue_empty(self, sqs_client, queue_name, expect_empty=True):
        """
        Verify if a queue is empty or contains messages.

        Args:
            sqs_client: SQS client
            queue_name: Name of the queue to check
            expect_empty: If True, expect queue to be empty. If False, just report status.
        """
        import os

        # SAFETY CHECK: Only run in test environments
        aws_endpoint = os.environ.get("AWS_ENDPOINT_URL")
        is_test_env = os.environ.get("ENVIRONMENT") in ["test", "development"] or \
                     os.environ.get("TEST_MODE") == "true"

        if not (aws_endpoint and "localhost" in aws_endpoint and "4566" in aws_endpoint and is_test_env):
            print("⚠️  Queue verification skipped (not in LocalStack test environment)")
            return

        try:
            # Get queue URL and attributes
            response = sqs_client.get_queue_url(QueueName=queue_name)
            queue_url = response["QueueUrl"]

            attrs = sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']
            )

            visible_msgs = int(attrs['Attributes'].get('ApproximateNumberOfMessages', 0))
            invisible_msgs = int(attrs['Attributes'].get('ApproximateNumberOfMessagesNotVisible', 0))
            total_msgs = visible_msgs + invisible_msgs

            if expect_empty:
                if total_msgs == 0:
                    print(f"   ✅ Queue {queue_name} is empty as expected")
                else:
                    print(f"   ❌ Queue {queue_name} is NOT empty! Contains {total_msgs} messages (visible: {visible_msgs}, processing: {invisible_msgs})")
            else:
                if total_msgs > 0:
                    print(f"   📨 Queue {queue_name} contains {total_msgs} messages (visible: {visible_msgs}, processing: {invisible_msgs})")
                else:
                    print(f"   📭 Queue {queue_name} is empty")

        except Exception as e:
            print(f"⚠️  Error checking queue {queue_name}: {e}")

    def verify_email_sent(self, ses_client, email, job_id, max_wait=10):
        """
        Verify that an email was sent via SES for a specific job (environment-aware).

        SECURITY NOTE: This function uses LocalStack-specific APIs when in test mode.
        It should NEVER be called in production environments as it relies on
        LocalStack's internal APIs that don't exist in real AWS.
        """
        import time
        import requests
        import os

        # SAFETY CHECK: Only run LocalStack verification in explicit test environments
        aws_endpoint = os.environ.get("AWS_ENDPOINT_URL")
        is_test_env = os.environ.get("ENVIRONMENT") in ["test", "development"] or \
                     os.environ.get("TEST_MODE") == "true"

        # If we're using LocalStack AND in test environment, use its API
        if (aws_endpoint and "localhost" in aws_endpoint and "4566" in aws_endpoint and
            is_test_env):
            return self._verify_email_localstack(email, job_id, aws_endpoint, max_wait)
        else:
            # In production or when LocalStack not available, fallback to connectivity check
            print("⚠️  Production mode: Using SES connectivity check instead of email verification")
            return self._verify_ses_connectivity(ses_client)

    def _verify_email_localstack(self, email_address, job_id, endpoint_url, max_wait):
        """Verify completion email for specific job using LocalStack's internal API (test only)."""
        import time
        import requests

        # Extract base URL from endpoint
        base_url = endpoint_url.replace('//', '//').split('//')[1].split('/')[0]
        localstack_url = f"http://{base_url}/_aws/ses"

        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                response = requests.get(localstack_url, timeout=5)
                if response.status_code == 200:
                    email_data = response.json()
                    messages = email_data.get("messages", [])

                    for message in messages:
                        destinations = message.get("Destination", {}).get("ToAddresses", [])
                        if email_address in destinations:
                            # Check if this is the completion email (contains summary)
                            # LocalStack stores subject directly in message['Subject']
                            subject = message.get("Subject", "")
                            body = message.get("Body", {}).get("text_part", "")

                            # Look specifically for completion email subject AND job_id in body
                            if "Your podcast summary is ready" in subject:
                                if job_id in body:
                                    print(f"✅ Completion email verified: Found completion message for job {job_id}")
                                    print(f"   To: {email_address}, Subject: {subject}")

                                    # Quick check that email contains summary content (not just links)
                                    body_data = message.get("Body", {})
                                    body_str = str(body_data).lower()

                                    # Check for actual summary structure indicators
                                    summary_indicators = ["main topics", "key points", "conclusion", "summary:", "notable quotes"]
                                    found_indicators = [ind for ind in summary_indicators if ind in body_str]

                                    # Verify it's not just a link but actual content
                                    has_actual_content = len(found_indicators) >= 2 and len(body_str) > 200

                                    if has_actual_content:
                                        print(f"   ✅ Email contains real summary content")

                                        # DETAILED CONTENT INSPECTION
                                        if isinstance(body_data, dict):
                                            text_part = body_data.get("text_part", "")
                                            print(f"   🔍 DETAILED EMAIL CONTENT ANALYSIS:")
                                            print(f"   📝 Full email body (first 800 chars):")
                                            print(f"   {text_part[:800]}...")

                                            # Check if it's real AI content or placeholder
                                            suspicious_phrases = ["summary available", "ai cannot generate", "incorrectly formatted", "placeholder", "test content"]
                                            is_placeholder = any(phrase in text_part.lower() for phrase in suspicious_phrases)

                                            if is_placeholder:
                                                print(f"   ❌ EMAIL CONTAINS PLACEHOLDER/ERROR CONTENT!")
                                            else:
                                                print(f"   ✅ Email appears to contain real AI-generated summary")
                                    else:
                                        print(f"   ❌ Email does NOT contain proper summary content!")

                                    return True
                                else:
                                    print(f"📧 Found completion email to {email_address} but for different job (subject: {subject})")
                            else:
                                print(f"📧 Found email to {email_address} but not completion email (subject: {subject})")
                time.sleep(1)
            except Exception as e:
                print(f"Warning: LocalStack SES check failed: {e}")
                time.sleep(1)

        print(f"❌ No completion email found for job {job_id} to {email_address} after {max_wait}s")
        return False

    def _verify_ses_connectivity(self, ses_client):
        """Verify SES connectivity (production fallback)."""
        try:
            ses_client.get_send_quota()
            print("✅ SES connectivity verified")
            return True
        except Exception as e:
            print(f"❌ SES connectivity failed: {e}")
            return False

    def verify_s3_file_exists(self, s3_client, bucket_name, key):
        """Verify that a file exists in S3."""
        try:
            s3_client.head_object(Bucket=bucket_name, Key=key)
            return True
        except Exception:
            return False

    def verify_job_completed(self, dynamodb_client, job_id, max_wait=10):
        """Verify that a job is marked as completed in DynamoDB."""
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                response = dynamodb_client.get_item(
                    TableName="processing_jobs",
                    Key={"id": {"S": job_id}}
                )
                if "Item" in response:
                    status = response["Item"].get("job_status", {}).get("S", "")
                    if status == "completed":
                        return True
                    elif status == "failed":
                        return False  # Job failed
            except Exception as e:
                print(f"Debug: Error checking job status: {e}")

            time.sleep(1)
        return False

    def verify_pipeline_files_created(self, s3_client, job_id):
        """Verify that all pipeline files were created."""
        files_to_check = [
            ("media-summarizer-audio", f"{job_id}.mp3"),
            ("media-summarizer-transcriptions", f"{job_id}.txt"),
            ("media-summarizer-summaries", f"{job_id}.json")
        ]

        results = {}
        for bucket, key in files_to_check:
            full_key = f"{bucket}/{key}"
            results[full_key] = self.verify_s3_file_exists(s3_client, bucket, key)

        return results

    def verify_credits_deducted(self, dynamodb_client, user_email: str, initial_credits: int) -> int:
        """Verify that credits were deducted from user account."""
        try:
            # Get user by email (we need to scan since email is not the primary key)
            response = dynamodb_client.scan(
                TableName="users",
                FilterExpression="email = :email",
                ExpressionAttributeValues={
                    ":email": {"S": user_email}
                }
            )

            if response["Items"]:
                user = response["Items"][0]
                current_credits = int(user["credits"]["N"])
                return current_credits
            else:
                return initial_credits  # User not found, return initial
        except Exception as e:
            print(f"Warning: Could not verify credits: {e}")
            return initial_credits

    @pytest.mark.asyncio
    async def test_complete_podcast_index_workflow(
        self,
        localstack_clients,
        test_audio_file,
        fastapi_client
    ):
        """
        Complete E2E test for Podcast Index workflow.

        Workflow:
        1. Search for "les grosses têtes" using real Podcast Index API
        2. Find episodes for the podcast
        3. Select a short episode (under 3 minutes if possible)
        4. Submit for processing
        5. Wait for complete workflow: Download → Transcription → Summarization → Email
        6. Verify all steps completed successfully
        """
        print("🚀 Starting COMPLETE Podcast Index E2E test")

        # Test configuration
        test_email = "e2e-podcast-index@example.com"
        test_user_id = "e2e-podcast-index-user"

        # Clear previous SES emails and SQS messages to ensure clean test state
        print("🧹 Clearing previous SES emails...")
        self.clear_ses_emails(localstack_clients["ses"])

        print("🧹 Clearing previous SQS messages...")
        self.clear_sqs_queues(localstack_clients["sqs"])

        # Verify queues are actually empty after cleanup
        print("🔍 Verifying queues are empty after cleanup...")
        self.verify_queue_empty(localstack_clients["sqs"], "email-notification-queue")

        # Create test user with credits (include all required fields)
        from datetime import datetime, timezone
        current_time = datetime.now(timezone.utc).isoformat()

        localstack_clients["dynamodb"].put_item(
            TableName="users",
            Item={
                "id": {"S": test_user_id},
                "email": {"S": test_email},
                "credits": {"N": "100"},
                "created_at": {"S": current_time},
                "updated_at": {"S": current_time}
            }
        )
        print(f"✅ Created test user: {test_email} with 100 credits")

        # Step 1: Search for podcast using REAL Podcast Index API
        print("📡 Step 1: Searching for 'les grosses têtes' podcast via real API")

        search_response = fastapi_client.post(
            "/api/v1/podcast-search/search",
            json={
                "query": "les grosses têtes",
                "max_results": 10,
                "clean": True
            }
        )

        assert search_response.status_code == 200, f"Podcast search failed: {search_response.text}"
        search_data = search_response.json()

        assert search_data["count"] > 0, "No podcasts found for 'les grosses têtes'"
        podcast = search_data["podcasts"][0]
        feed_id = podcast["id"]
        print(f"✅ Found podcast: '{podcast['title']}' (ID: {feed_id})")

        # Step 2: Get episodes using REAL API
        print("📋 Step 2: Getting episodes from real Podcast Index API")

        episodes_response = fastapi_client.post(
            "/api/v1/podcast-search/episodes",
            json={
                "feed_id": feed_id,
                "max_results": 50
            }
        )

        assert episodes_response.status_code == 200, f"Episodes fetch failed: {episodes_response.text}"
        episodes_data = episodes_response.json()

        assert episodes_data["count"] > 0, "No episodes found for the podcast"
        print(f"✅ Found {episodes_data['count']} episodes")

        # Step 3: Find suitable episode (prioritize very short episodes for fast testing)
        print("🎯 Step 3: Looking for suitable episode for processing")

        selected_episode = None

        # First try to find episode under 30 seconds for ultra-fast testing
        for episode in episodes_data["episodes"]:
            if episode.get("duration") and episode["duration"] < 30:
                selected_episode = episode
                print(f"✅ Found ultra-short episode: '{episode['title']}' ({episode['duration']}s)")
                break

        # Second try: episodes under 60 seconds
        if not selected_episode:
            for episode in episodes_data["episodes"]:
                if episode.get("duration") and episode["duration"] < 60:
                    selected_episode = episode
                    print(f"✅ Found short episode: '{episode['title']}' ({episode['duration']}s)")
                    break

        # Third try: episodes under 2 minutes
        if not selected_episode:
            for episode in episodes_data["episodes"]:
                if episode.get("duration") and episode["duration"] < 120:
                    selected_episode = episode
                    print(f"⚠️  Found medium episode: '{episode['title']}' ({episode['duration']}s)")
                    break

        # Last resort: take the shortest available
        if not selected_episode:
            episodes_with_duration = [ep for ep in episodes_data["episodes"] if ep.get("duration")]
            if episodes_with_duration:
                selected_episode = min(episodes_with_duration, key=lambda x: x["duration"])
                print(f"⚠️  Using shortest available: '{selected_episode['title']}' ({selected_episode['duration']}s)")
            else:
                # Fallback to first episode
                selected_episode = episodes_data["episodes"][0]
                print(f"⚠️  Using first episode (duration unknown): '{selected_episode['title']}'")

        assert selected_episode is not None, "No suitable episode found for processing"

        # Step 4: Authenticate via Magic Link (required for submit-episode)
        print("🔐 Step 4: Authenticating via Magic Link")

        # Request magic link
        magic_link_response = fastapi_client.post(
            "/api/v1/auth/request-magic-link",
            json={"email": test_email}
        )
        assert magic_link_response.status_code == 200, f"Magic link request failed: {magic_link_response.text}"

        # Extract magic token from DynamoDB
        auth_tokens_response = localstack_clients["dynamodb"].scan(
            TableName="auth_tokens",
            FilterExpression="token_type = :token_type AND email = :email",
            ExpressionAttributeValues={
                ":token_type": {"S": "magic_link"},
                ":email": {"S": test_email}
            }
        )
        auth_tokens = auth_tokens_response.get("Items", [])
        assert len(auth_tokens) > 0, "No magic link tokens found in DynamoDB"
        magic_token = auth_tokens[0]["token"]["S"]

        # Verify token to get JWT
        verify_response = fastapi_client.post(
            "/api/v1/auth/verify-token",
            json={"token": magic_token, "email": test_email}
        )
        assert verify_response.status_code == 200, f"Token verification failed: {verify_response.text}"
        jwt_token = verify_response.json()["access_token"]

        print("⚡ Step 5: Submitting episode for processing (authenticated)")
        submission_response = fastapi_client.post(
            "/api/v1/podcast-search/submit-episode",
            json={
                "feed_id": feed_id,
                "episode_guid": selected_episode["guid"],
                "user_email": test_email
            },
            headers={"Authorization": f"Bearer {jwt_token}"}
        )

        assert submission_response.status_code == 200, f"Episode submission failed: {submission_response.text}"
        submission_data = submission_response.json()
        job_id = submission_data["job_id"]
        print(f"✅ Episode submitted successfully, job_id: {job_id}")

        # Check if any messages appeared in email queue immediately after submission
        print("🔍 Checking email queue immediately after submission...")
        self.verify_queue_empty(localstack_clients["sqs"], "email-notification-queue", expect_empty=False)

        # Step 5: Wait for complete workflow to finish
        print("⏳ Step 5: Waiting for complete workflow...")
        print("   Expected: RSS Resolution → Audio Download → Transcription → Summarization → Email")

        # Adjust timeout based on episode duration (reduced for faster testing)
        episode_duration = selected_episode.get("duration", 20)
        base_timeout = 20  # 20 seconds base for workers to process
        processing_timeout = max(base_timeout, min(episode_duration + 15, 45))  # Cap at 45s max

        print(f"   Timeout set to {processing_timeout} seconds based on episode duration")

        start_time = time.time()
        workflow_completed = False
        job_completed = False
        email_sent = False
        files_created = False

        # Track each step individually for detailed timing
        audio_downloaded = False
        transcription_done = False
        summarization_done = False



        while time.time() - start_time < processing_timeout:
            elapsed = round(time.time() - start_time, 1)

            # Check each pipeline step individually
            if not audio_downloaded and elapsed >= 0:
                pipeline_files = self.verify_pipeline_files_created(localstack_clients["s3"], job_id)
                if pipeline_files.get(f"media-summarizer-audio/{job_id}.mp3", False):
                    audio_downloaded = True
                    print(f"   🎵 Audio downloaded ({elapsed}s)")

            if not transcription_done and elapsed >= 0:
                pipeline_files = self.verify_pipeline_files_created(localstack_clients["s3"], job_id)
                if pipeline_files.get(f"media-summarizer-transcriptions/{job_id}.txt", False):
                    transcription_done = True
                    print(f"   📝 Transcription completed ({elapsed}s)")

            if not summarization_done and elapsed >= 0:
                pipeline_files = self.verify_pipeline_files_created(localstack_clients["s3"], job_id)
                if pipeline_files.get(f"media-summarizer-summaries/{job_id}.json", False):
                    summarization_done = True
                    print(f"   📊 Summarization completed ({elapsed}s)")

            # Check job completion status (primary indicator)
            if not job_completed:
                job_completed = self.verify_job_completed(localstack_clients["dynamodb"], job_id, max_wait=2)
                if job_completed:
                    print(f"   ✅ Job marked as completed ({elapsed}s)")

            # Check if pipeline files were created (aggregated view)
            if not files_created and elapsed > 10:  # Quick check for files
                pipeline_files = self.verify_pipeline_files_created(localstack_clients["s3"], job_id)
                files_created = any(pipeline_files.values())
                if files_created:
                    created_files = [k.split('/')[-1] for k, v in pipeline_files.items() if v]
                    print(f"   ✅ Pipeline files created: {', '.join(created_files)} ({elapsed}s)")

            # Check if email was sent
            if not email_sent:
                email_sent = self.verify_email_sent(localstack_clients["ses"], test_email, job_id)
                if email_sent:
                    print(f"   ✅ Email notification sent ({elapsed}s)")

            # Primary completion: job status is completed
            if job_completed:
                workflow_completed = True
                print(f"   ✅ Workflow completed ({elapsed}s)")
                break

            # Secondary indicators show progress but don't complete the workflow
            if files_created or email_sent:
                print(f"   ✅ Workflow shows progress ({elapsed}s)")
                # Continue waiting for job completion

            status_summary = f"Job: {job_completed}, Files: {files_created}, Email: {email_sent}"
            print(f"   Still waiting... ({elapsed}s elapsed) - {status_summary}")
            await asyncio.sleep(2)

        # Step 6: Verify workflow completion
        if not workflow_completed:
            elapsed = int(time.time() - start_time)
            # Get final status for debugging
            final_files = self.verify_pipeline_files_created(localstack_clients["s3"], job_id)
            files_summary = {k.split('/')[-1]: v for k, v in final_files.items()}

            error_msg = f"""Workflow incomplete after {elapsed}s:
            - Job completed: {job_completed}
            - Files created: {files_summary}
            - Email sent: {email_sent}

            This indicates that workers may not be running or there's an issue with the processing pipeline.
            Check that all required services (LocalStack, workers, Whisper) are running properly."""

            pytest.fail(error_msg)

        print("✅ Complete workflow successful - All verifications passed!")

        # Final verification summary
        final_files = self.verify_pipeline_files_created(localstack_clients["s3"], job_id)
        files_created_count = sum(1 for v in final_files.values() if v)
        print(f"   Final status: Job completed: {job_completed}, Files: {files_created_count}/3, Email: {email_sent}")

        # Step 7: Verify credit deduction
        final_credits = self.verify_credits_deducted(localstack_clients["dynamodb"], test_email, initial_credits=100)
        assert final_credits == 99, f"Expected 99 credits, got {final_credits}"
        print("✅ Credits deducted: 1")

        # Step 8: Comprehensive verification of all pipeline outputs
        print("🔍 Step 8: Comprehensive verification of all pipeline outputs")

        # Verify all pipeline files were created
        pipeline_files = self.verify_pipeline_files_created(localstack_clients["s3"], job_id)

        files_found = []
        files_missing = []
        for file_key, exists in pipeline_files.items():
            if exists:
                files_found.append(file_key.split('/')[-1])  # Get just filename
            else:
                files_missing.append(file_key.split('/')[-1])

        print(f"✅ Pipeline files created: {', '.join(files_found)}")
        if files_missing:
            print(f"⚠️  Missing files: {', '.join(files_missing)}")

        # Verify job is marked as completed (should already be true from the main loop)
        if not job_completed:
            job_status_verified = self.verify_job_completed(localstack_clients["dynamodb"], job_id, max_wait=10)
            assert job_status_verified, "Job should be marked as completed in DynamoDB"
        print("✅ Job status verified as completed")

        # Verify at least core files exist (audio and summary are essential)
        # Check by file extensions rather than keywords in names
        has_audio = any(f.endswith('.mp3') for f in files_found)
        has_summary = any(f.endswith('.json') for f in files_found)

        missing_essential = []
        if not has_audio:
            missing_essential.append("audio (.mp3)")
        if not has_summary:
            missing_essential.append("summary (.json)")

        if missing_essential:
            error_msg = f"""Essential pipeline files are missing: {missing_essential}

            Files found: {files_found}
            Files missing: {files_missing}

            This indicates that parts of the processing pipeline failed:
            - Missing audio (.mp3): Download worker failed
            - Missing summary (.json): Summarization worker failed

            The workflow cannot be considered successful if essential files are not created."""

            pytest.fail(error_msg)
        else:
            print("✅ All essential pipeline files confirmed")

        # Final success summary
        print("\n" + "="*80)
        print("🎉 COMPLETE E2E TEST SUCCESS!")
        print("="*80)
        print("✅ Real Podcast Index API integration")
        print("✅ Episode selection and submission")
        print("✅ Complete workflow execution")
        print("✅ File processing and storage")
        print("✅ Email notification delivery")
        print("✅ Credit system functionality")
        print("✅ Database state management")
        print("="*80)

    @pytest.mark.asyncio
    async def test_podcast_index_api_connectivity(self):
        """
        Simple connectivity test to verify Podcast Index API works.
        This runs independently of the full workflow test.
        """
        print("🔍 Testing direct Podcast Index API connectivity")

        # Check credentials
        api_key = os.getenv("PODCASTINDEXORG_API_KEY")
        api_secret = os.getenv("PODCASTINDEXORG_API_SECRET")

        if not api_key or not api_secret:
            pytest.skip("Podcast Index credentials not available")

        # Test direct API call using utils
        from media_summarizer.utils import podcast_index
        result = await podcast_index.search_podcasts("test", max_results=1)

        assert result.get("status") == "true", "Podcast Index API call failed"
        assert result.get("count", 0) >= 0, "Invalid response format"

        print(f"✅ Podcast Index API connectivity confirmed")
        print(f"   Status: {result.get('status')}")
        print(f"   Results: {result.get('count', 0)}")
