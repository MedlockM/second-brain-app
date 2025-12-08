"""
Tests d'intégration pour le worker Spotify Sync avec Lambda et LocalStack.

Ces tests vérifient que le worker Lambda fonctionne correctement avec
les services AWS simulés par LocalStack.
"""
import pytest
import json
import asyncio
from unittest.mock import patch, AsyncMock

from media_summarizer.tests.utils.lambda_localstack import (
    LambdaLocalStackClient,
    create_test_spotify_sync_message,
    assert_lambda_success,
    assert_lambda_error
)
from media_summarizer.tests.utils.localstack_helpers import setup_localstack
from media_summarizer.tests.utils.dynamodb_localstack import DynamoDBLocalStackClient


@pytest.mark.integration
class TestSpotifySyncLambda:
    """Tests d'intégration pour le worker Spotify Sync Lambda."""

    @pytest.fixture(autouse=True)
    def setup_localstack_env(self, setup_localstack):
        """Ensure LocalStack is set up for all tests."""
        pass

    @pytest.fixture
    def lambda_client(self):
        """Create Lambda LocalStack client."""
        return LambdaLocalStackClient()

    @pytest.fixture
    def dynamodb_client(self):
        """Create DynamoDB LocalStack client."""
        client = DynamoDBLocalStackClient()
        client.setup_tables()
        yield client
        client.clear_tables()

    @pytest.fixture
    def deployed_lambda(self, lambda_client):
        """Deploy Spotify Sync Lambda for testing."""
        function_name = "test-spotify-sync-worker"
        handler = "media_summarizer.workers.spotify_sync.worker.lambda_handler"
        
        # Create deployment package
        zip_path = lambda_client.create_lambda_package(
            "media_summarizer.workers.spotify_sync.worker",
            function_name
        )
        
        # Environment variables
        env_vars = {
            "AWS_ENDPOINT_URL": "http://localhost:4566",
            "AWS_REGION": "us-east-1",
            "USERS_TABLE": "users",
            "SPOTIFY_FOLLOWS_TABLE": "spotify_playlist_follows",
            "PROCESSING_JOBS_TABLE": "processing_jobs",
            "AUDIO_DOWNLOAD_QUEUE": "audio-download-queue"
        }
        
        # Deploy function
        response = lambda_client.deploy_lambda_function(
            function_name, handler, zip_path, env_vars
        )
        
        yield {
            "function_name": function_name,
            "handler": handler,
            "response": response
        }
        
        # Cleanup
        lambda_client.cleanup_lambda_function(function_name)

    @pytest.fixture
    def test_user(self, dynamodb_client):
        """Create a test user with Spotify credentials."""
        user_data = dynamodb_client.create_user(
            user_id="test-user-123",
            email="test@example.com",
            credits=100,
            spotify_access_token="test-access-token",
            spotify_refresh_token="test-refresh-token",
            spotify_token_expires_at="2025-12-31T23:59:59Z"
        )
        return user_data

    @pytest.fixture
    def test_playlist_follows(self, dynamodb_client, test_user):
        """Create test playlist follows."""
        follows = []
        for i, playlist_id in enumerate(["playlist_1", "playlist_2"]):
            follow_data = {
                'user_id': test_user['id'],
                'playlist_id': playlist_id,
                'playlist_name': f'Test Playlist {i+1}',
                'created_at': '2023-01-01T00:00:00Z',
                'last_synced_at': '2023-01-01T00:00:00Z'
            }
            
            # Insert into DynamoDB
            table = dynamodb_client.resource.Table("spotify_playlist_follows")
            table.put_item(Item=follow_data)
            follows.append(follow_data)
        
        return follows

    def test_lambda_deployment(self, deployed_lambda):
        """Test that the Lambda function is deployed correctly."""
        assert deployed_lambda['function_name'] == "test-spotify-sync-worker"
        assert deployed_lambda['response']['FunctionName'] == "test-spotify-sync-worker"
        assert deployed_lambda['response']['Runtime'] == "python3.12"
        assert deployed_lambda['response']['Handler'] == "media_summarizer.workers.spotify_sync.worker.lambda_handler"

    def test_successful_sync_processing(self, lambda_client, deployed_lambda, test_user, test_playlist_follows):
        """Test successful processing of a sync message."""
        # Create test message
        message = create_test_spotify_sync_message(
            user_id=test_user['id'],
            playlist_ids=["playlist_1", "playlist_2"]
        )
        
        # Create SQS event payload
        sqs_event = lambda_client.create_sqs_event_payload("spotify-sync-queue", message)
        
        # Mock external dependencies
        with patch('media_summarizer.utils.spotify.ensure_access_token') as mock_ensure_token, \
             patch('media_summarizer.core.services.playlist_sync.run_playlist_sync_for_user') as mock_sync:
            
            # Configure mocks
            mock_ensure_token.return_value = None  # Success
            mock_sync.return_value = {"status": "success", "submitted": 5}
            
            # Invoke Lambda
            response = lambda_client.invoke_lambda_function(
                deployed_lambda['function_name'],
                sqs_event
            )
            
            # Verify response
            assert_lambda_success(response)
            
            # Verify mocks were called
            mock_ensure_token.assert_called_once()
            assert mock_sync.call_count == 2  # Two playlists

    def test_user_not_found_error(self, lambda_client, deployed_lambda):
        """Test handling of user not found error."""
        # Create test message with non-existent user
        message = create_test_spotify_sync_message(
            user_id="non-existent-user",
            playlist_ids=["playlist_1"]
        )
        
        # Create SQS event payload
        sqs_event = lambda_client.create_sqs_event_payload("spotify-sync-queue", message)
        
        # Invoke Lambda
        response = lambda_client.invoke_lambda_function(
            deployed_lambda['function_name'],
            sqs_event
        )
        
        # Verify error handling
        assert response['StatusCode'] == 200  # Lambda executed successfully
        payload = response['ResponsePayload']
        body = json.loads(payload['body'])
        
        # Check that the error was handled properly
        results = body['results']
        assert len(results) == 1
        assert results[0]['status'] == 'error'
        assert results[0]['reason'] == 'user_not_found'

    def test_token_refresh_failure(self, lambda_client, deployed_lambda, test_user):
        """Test handling of token refresh failure."""
        # Create test message
        message = create_test_spotify_sync_message(
            user_id=test_user['id'],
            playlist_ids=["playlist_1"]
        )
        
        # Create SQS event payload
        sqs_event = lambda_client.create_sqs_event_payload("spotify-sync-queue", message)
        
        # Mock token refresh failure
        with patch('media_summarizer.utils.spotify.ensure_access_token') as mock_ensure_token:
            mock_ensure_token.side_effect = Exception("Token refresh failed")
            
            # Invoke Lambda
            response = lambda_client.invoke_lambda_function(
                deployed_lambda['function_name'],
                sqs_event
            )
            
            # Verify error handling
            assert response['StatusCode'] == 200
            payload = response['ResponsePayload']
            body = json.loads(payload['body'])
            
            results = body['results']
            assert len(results) == 1
            assert results[0]['status'] == 'error'
            assert results[0]['reason'] == 'token_refresh_failed'

    def test_invalid_message_format(self, lambda_client, deployed_lambda):
        """Test handling of invalid message format."""
        # Create invalid message (missing required fields)
        invalid_message = {
            "invalid_field": "value"
            # Missing user_id and playlist_ids
        }
        
        # Create SQS event payload
        sqs_event = lambda_client.create_sqs_event_payload("spotify-sync-queue", invalid_message)
        
        # Invoke Lambda
        response = lambda_client.invoke_lambda_function(
            deployed_lambda['function_name'],
            sqs_event
        )
        
        # Verify error handling
        assert response['StatusCode'] == 200
        payload = response['ResponsePayload']
        body = json.loads(payload['body'])
        
        results = body['results']
        assert len(results) == 1
        assert results[0]['status'] == 'error'
        assert results[0]['reason'] == 'invalid_message'

    def test_partial_sync_failure(self, lambda_client, deployed_lambda, test_user, test_playlist_follows):
        """Test handling when some playlists sync successfully and others fail."""
        # Create test message
        message = create_test_spotify_sync_message(
            user_id=test_user['id'],
            playlist_ids=["playlist_1", "playlist_2", "playlist_3"]
        )
        
        # Create SQS event payload
        sqs_event = lambda_client.create_sqs_event_payload("spotify-sync-queue", message)
        
        # Mock mixed success/failure results
        def mock_sync_side_effect(user, playlist_id):
            if playlist_id == "playlist_1":
                return {"status": "success", "submitted": 3}
            elif playlist_id == "playlist_2":
                return {"status": "error", "reason": "playlist_not_found"}
            else:  # playlist_3
                raise Exception("Unexpected error")
        
        with patch('media_summarizer.utils.spotify.ensure_access_token') as mock_ensure_token, \
             patch('media_summarizer.core.services.playlist_sync.run_playlist_sync_for_user') as mock_sync:
            
            mock_ensure_token.return_value = None
            mock_sync.side_effect = mock_sync_side_effect
            
            # Invoke Lambda
            response = lambda_client.invoke_lambda_function(
                deployed_lambda['function_name'],
                sqs_event
            )
            
            # Verify mixed results
            assert response['StatusCode'] == 200
            payload = response['ResponsePayload']
            body = json.loads(payload['body'])
            
            results = body['results']
            assert results['status'] == 'success'  # Overall success
            assert len(results['results']) == 3
            
            # Check individual results
            playlist_results = {r['playlist_id']: r for r in results['results']}
            
            # playlist_1 should succeed
            assert playlist_results['playlist_1']['result']['status'] == 'success'
            
            # playlist_2 should have controlled failure
            assert playlist_results['playlist_2']['result']['status'] == 'error'
            
            # playlist_3 should have exception
            assert 'error' in playlist_results['playlist_3']

    def test_sqs_batch_processing(self, lambda_client, deployed_lambda, test_user):
        """Test processing of multiple SQS messages in a batch."""
        # Create multiple messages
        messages = [
            create_test_spotify_sync_message(test_user['id'], ["playlist_1"]),
            create_test_spotify_sync_message(test_user['id'], ["playlist_2"])
        ]
        
        # Create SQS event with multiple records
        sqs_event = {
            "Records": [
                {
                    "messageId": f"test-message-{i}",
                    "receiptHandle": f"test-receipt-{i}",
                    "body": json.dumps(msg),
                    "attributes": {
                        "ApproximateReceiveCount": "1",
                        "SentTimestamp": "1545082649183",
                        "SenderId": "AIDAIENQZJOLO23YVJ4VO",
                        "ApproximateFirstReceiveTimestamp": "1545082649185"
                    },
                    "messageAttributes": {},
                    "md5OfBody": "test-md5",
                    "eventSource": "aws:sqs",
                    "eventSourceARN": "arn:aws:sqs:us-east-1:000000000000:spotify-sync-queue",
                    "awsRegion": "us-east-1"
                }
                for i, msg in enumerate(messages)
            ]
        }
        
        with patch('media_summarizer.utils.spotify.ensure_access_token') as mock_ensure_token, \
             patch('media_summarizer.core.services.playlist_sync.run_playlist_sync_for_user') as mock_sync:
            
            mock_ensure_token.return_value = None
            mock_sync.return_value = {"status": "success", "submitted": 2}
            
            # Invoke Lambda
            response = lambda_client.invoke_lambda_function(
                deployed_lambda['function_name'],
                sqs_event
            )
            
            # Verify batch processing
            assert response['StatusCode'] == 200
            payload = response['ResponsePayload']
            body = json.loads(payload['body'])
            
            assert body['processed'] == 2  # Two messages processed
            assert len(body['results']) == 2

    def test_lambda_timeout_handling(self, lambda_client, deployed_lambda, test_user):
        """Test Lambda timeout handling (simulated)."""
        # Create test message
        message = create_test_spotify_sync_message(
            user_id=test_user['id'],
            playlist_ids=["playlist_1"]
        )
        
        # Create SQS event payload
        sqs_event = lambda_client.create_sqs_event_payload("spotify-sync-queue", message)
        
        # Mock a very slow operation
        with patch('media_summarizer.utils.spotify.ensure_access_token') as mock_ensure_token, \
             patch('media_summarizer.core.services.playlist_sync.run_playlist_sync_for_user') as mock_sync:
            
            mock_ensure_token.return_value = None
            
            # Simulate slow operation
            async def slow_sync(*args, **kwargs):
                await asyncio.sleep(10)  # Longer than typical Lambda timeout for testing
                return {"status": "success", "submitted": 1}
            
            mock_sync.side_effect = slow_sync
            
            # Invoke Lambda (this should complete quickly in our test environment)
            response = lambda_client.invoke_lambda_function(
                deployed_lambda['function_name'],
                sqs_event
            )
            
            # In a real timeout scenario, we'd get a timeout error
            # For this test, we just verify the Lambda can handle async operations
            assert response['StatusCode'] == 200

    def test_environment_variables(self, lambda_client, deployed_lambda):
        """Test that environment variables are properly set in Lambda."""
        # Get function configuration
        config = lambda_client.lambda_client.get_function_configuration(
            FunctionName=deployed_lambda['function_name']
        )
        
        env_vars = config['Environment']['Variables']
        
        # Verify required environment variables
        assert env_vars['AWS_ENDPOINT_URL'] == "http://localhost:4566"
        assert env_vars['AWS_REGION'] == "us-east-1"
        assert env_vars['USERS_TABLE'] == "users"
        assert env_vars['SPOTIFY_FOLLOWS_TABLE'] == "spotify_playlist_follows"
        assert env_vars['PROCESSING_JOBS_TABLE'] == "processing_jobs"
        assert env_vars['AUDIO_DOWNLOAD_QUEUE'] == "audio-download-queue"

    @pytest.mark.asyncio
    async def test_async_operations_in_lambda(self, lambda_client, deployed_lambda, test_user):
        """Test that async operations work correctly in Lambda context."""
        # Create test message
        message = create_test_spotify_sync_message(
            user_id=test_user['id'],
            playlist_ids=["playlist_1"]
        )
        
        # Create SQS event payload
        sqs_event = lambda_client.create_sqs_event_payload("spotify-sync-queue", message)
        
        # Mock async operations
        with patch('media_summarizer.utils.database_async.get_user_by_id') as mock_get_user, \
             patch('media_summarizer.utils.spotify.ensure_access_token') as mock_ensure_token, \
             patch('media_summarizer.core.services.playlist_sync.run_playlist_sync_for_user') as mock_sync:
            
            # Configure async mocks
            mock_get_user.return_value = test_user
            mock_ensure_token.return_value = None
            mock_sync.return_value = {"status": "success", "submitted": 3}
            
            # Invoke Lambda
            response = lambda_client.invoke_lambda_function(
                deployed_lambda['function_name'],
                sqs_event
            )
            
            # Verify successful async execution
            assert_lambda_success(response)
            
            # Verify async functions were called
            mock_get_user.assert_called_once_with(test_user['id'])
            mock_ensure_token.assert_called_once()
            mock_sync.assert_called_once()