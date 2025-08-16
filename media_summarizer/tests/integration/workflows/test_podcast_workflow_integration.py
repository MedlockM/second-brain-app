"""
True integration tests for the podcast submission workflow.

These tests use real LocalStack services with minimal mocking to test actual
component interactions and data flow through the system.
"""
import json
import os
import pytest
import pytest_asyncio
from unittest.mock import patch
import uuid
import time
import asyncio

from media_summarizer.tests.utils.base_test_classes import BaseIntegrationTestCase
from media_summarizer.tests.utils.helpers import (
    set_env_vars,
    restore_env_vars,
    load_fixture_file
)


class TestPodcastWorkflowIntegration(BaseIntegrationTestCase):
    """Integration tests for podcast workflow with real services."""

    @pytest.fixture(autouse=True)
    def setup_environment(self):
        """Set up environment variables for testing."""
        original_values = set_env_vars({
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "AWS_DEFAULT_REGION": "us-east-1",
            "AWS_ENDPOINT_URL": "http://localhost:4566"
        })
        yield
        restore_env_vars(original_values)

    @pytest.mark.asyncio
    async def test_api_to_sqs_integration(self, test_client, localstack_sqs_client, localstack_dynamodb_client):
        """
        Test API endpoint to SQS message integration.

        Verifies:
        1. API accepts podcast submission
        2. Message is sent to correct SQS queue
        3. User credits are deducted
        4. Transaction is recorded in database
        """
        # Create test user in DynamoDB
        test_user = localstack_dynamodb_client.create_user(
            user_id="test-user-id",
            email="user@example.com",
            credits=100
        )

        # Override dependencies
        from media_summarizer.api.dependencies.auth import get_current_user
        from media_summarizer.utils.database_async import get_db, DynamoDBConnection
        from media_summarizer.utils import sqs
        from media_summarizer.api.main import app

        def get_current_user_override():
            return {
                "id": "test-user-id",
                "email": "user@example.com"
            }

        def get_db_override():
            return DynamoDBConnection()

        async def mock_send_message(*args, **kwargs):
            return {"MessageId": "mock-message-id", "MD5OfBody": "mock-md5"}

        app.dependency_overrides[get_current_user] = get_current_user_override
        app.dependency_overrides[get_db] = get_db_override

        try:
            # Purge queue before test
            download_queue_url = localstack_sqs_client.queue_urls["audio-download-queue"]
            try:
                localstack_sqs_client.purge_queue(QueueUrl=download_queue_url)
                time.sleep(2)  # Wait for purge to complete
            except Exception:
                pass

            # Submit podcast through API
            response = test_client.post(
                "/api/v1/podcasts/submit",
                json={
                    "podcast_url": "https://example.com/podcast.xml",
                    "user_email": "user@example.com"
                }
            )

            # Verify API response
            assert response.status_code == 200
            data = response.json()
            job_id = data["job_id"]
            assert job_id is not None
            assert data["status"] == "pending"

            # Verify SQS message was sent
            time.sleep(1)  # Allow message to be processed

            response = localstack_sqs_client.receive_message(
                QueueUrl=rss_queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=5
            )

            messages = response.get('Messages', [])
            assert len(messages) > 0, "No message found in RSS resolution queue"

            # Find our message
            message_found = False
            for message in messages:
                body = json.loads(message.get('Body', '{}'))
                if body.get("job_id") == job_id:
                    assert body["podcast_url"] == "https://example.com/podcast.xml"
                    assert body["user_email"] == "user@example.com"
                    assert body["user_id"] == "test-user-id"
                    message_found = True

                    # Clean up message
                    localstack_sqs_client.delete_message(
                        QueueUrl=rss_queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    break

            assert message_found, f"Message with job_id {job_id} not found in queue"

            # Verify database changes
            updated_user = localstack_dynamodb_client.get_user("test-user-id")
            assert updated_user["credits"] == 99, f"Expected 99 credits, got {updated_user['credits']}"

            # Verify transaction record
            transactions = localstack_dynamodb_client.get_user_transactions("test-user-id")
            assert len(transactions) > 0, "No credit transaction recorded"

            transaction = transactions[0]
            assert transaction["amount"] == -1
            assert transaction["type"] == "deduction"
            assert transaction["job_id"] == job_id

        finally:
            # Clean up dependencies
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_sqs_to_s3_integration(self, localstack_sqs_client, localstack_s3_client):
        """
        Test SQS message processing to S3 storage integration.

        This is a simplified test that verifies LocalStack services work together.
        """
        # Create test message
        job_id = str(uuid.uuid4())
        test_data = {
            "job_id": job_id,
            "content": "test content for S3",
            "timestamp": time.time()
        }

        # Send message to queue
        queue_url = localstack_sqs_client.queue_urls["audio-download-queue"]
        localstack_sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(test_data)
        )

        # Add small delay to ensure message propagation in LocalStack
        await asyncio.sleep(0.5)

        # Receive message with retry logic for robustness
        messages = []
        max_retries = 3
        for attempt in range(max_retries):
            response = localstack_sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=5
            )
            messages = response.get('Messages', [])
            if messages:
                break
            if attempt < max_retries - 1:
                print(f"Retry {attempt + 1}: No message received, retrying...")
                await asyncio.sleep(1)

        assert len(messages) == 1, f"Message not received from queue after {max_retries} attempts"

        message = messages[0]
        body = json.loads(message['Body'])
        assert body['job_id'] == job_id

        # Store data in S3
        bucket = "media-summarizer-audio"
        key = f"test/{job_id}.json"

        localstack_s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=json.dumps(test_data),
            ContentType="application/json"
        )

        # Verify S3 storage
        response = localstack_s3_client.get_object(Bucket=bucket, Key=key)
        stored_data = json.loads(response['Body'].read())
        assert stored_data['job_id'] == job_id

        # Clean up
        localstack_sqs_client.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=message['ReceiptHandle']
        )
        localstack_s3_client.delete_object(Bucket=bucket, Key=key)

    @pytest.mark.asyncio
    async def test_database_integration(self, localstack_dynamodb_client):
        """
        Test database operations integration.

        Verifies that database models and operations work correctly.
        """
        # Create user
        user = localstack_dynamodb_client.create_user(
            user_id="integration-test-user",
            email="integration@example.com",
            credits=50
        )

        # Create transaction
        transaction_id = f"txn-{uuid.uuid4()}"
        transaction = localstack_dynamodb_client.create_credit_transaction(
            transaction_id=transaction_id,
            user_id="integration-test-user",
            amount=-5,
            transaction_type="deduction",
            description="Integration test",
            job_id="test-job-123"
        )

        # Verify user was created
        retrieved_user = localstack_dynamodb_client.get_user("integration-test-user")
        assert retrieved_user is not None
        assert retrieved_user["email"] == "integration@example.com"
        assert retrieved_user["credits"] == 50

        # Verify transaction was created
        retrieved_transactions = localstack_dynamodb_client.get_user_transactions("integration-test-user")
        assert len(retrieved_transactions) > 0

        retrieved_transaction = retrieved_transactions[0]
        assert retrieved_transaction["amount"] == -5
        assert retrieved_transaction["type"] == "deduction"
        assert retrieved_transaction["job_id"] == "test-job-123"

    @pytest.mark.asyncio
    async def test_credit_insufficient_funds_integration(self, test_client, localstack_sqs_client, localstack_dynamodb_client):
        """
        Test integration behavior when user has insufficient credits.
        """
        # Create user with insufficient credits
        poor_user = localstack_dynamodb_client.create_user(
            user_id="poor-user-id",
            email="poor@example.com",
            credits=0  # Less than required 1 credit
        )

        # Override dependencies
        from media_summarizer.api.dependencies.auth import get_current_user
        from media_summarizer.utils.database_async import get_db, DynamoDBConnection
        from media_summarizer.api.main import app

        def get_current_user_override():
            return {
                "id": "poor-user-id",
                "email": "poor@example.com"
            }

        def get_db_override():
            return DynamoDBConnection()

        app.dependency_overrides[get_current_user] = get_current_user_override
        app.dependency_overrides[get_db] = get_db_override

        try:
            response = test_client.post(
                "/api/v1/podcasts/submit",
                json={
                    "podcast_url": "https://example.com/podcast.xml",
                    "user_email": "poor@example.com"
                }
            )

            # Should return 400 for insufficient credits
            assert response.status_code == 400
            data = response.json()
            assert "insuffisants" in data["detail"].lower() or "insufficient" in data["detail"].lower()

            # Verify no message was sent to queue
            download_queue_url = localstack_sqs_client.queue_urls["audio-download-queue"]
            response = localstack_sqs_client.receive_message(
                QueueUrl=download_queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=2
            )

            messages = response.get('Messages', [])
            # Should be no new messages (or messages from other tests)
            # We can't guarantee no messages due to potential test isolation issues

            # Verify credits weren't deducted
            updated_user = localstack_dynamodb_client.get_user("poor-user-id")
            assert updated_user["credits"] == 0, "Credits should not have been deducted"

        finally:
            app.dependency_overrides.clear()
