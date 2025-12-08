"""
Tests for Spotify Sync Worker Lambda function.

Tests the Lambda handler and message processing logic.
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from media_summarizer.workers.spotify_sync.worker import process_sync_message, lambda_handler


@pytest.fixture
def mock_user():
    """Mock user object."""
    user = MagicMock()
    user.id = "test_user_123"
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_sync_result():
    """Mock successful sync result."""
    return {
        "status": "success",
        "submitted": 5,
        "skipped": 2,
        "errors": 0
    }


@pytest.fixture
def valid_message_body():
    """Valid message body for testing."""
    return {
        "user_id": "test_user_123",
        "playlist_ids": ["playlist_1", "playlist_2"],
        "source": "scheduled_sync"
    }


@pytest.fixture
def lambda_event():
    """Lambda SQS event for testing."""
    return {
        "Records": [
            {
                "messageId": "test-message-id",
                "receiptHandle": "test-receipt-handle",
                "body": json.dumps({
                    "user_id": "test_user_123",
                    "playlist_ids": ["playlist_1", "playlist_2"],
                    "source": "test"
                }),
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
        ]
    }


class TestSpotifySyncWorkerLambda:
    """Tests for the Spotify Sync Worker Lambda function."""

    @pytest.mark.asyncio
    async def test_process_sync_message_success(self, valid_message_body, mock_user, mock_sync_result):
        """Test successful message processing."""
        with patch('media_summarizer.workers.spotify_sync.worker.database_async.get_user_by_id') as mock_get_user, \
             patch('media_summarizer.workers.spotify_sync.worker.ensure_access_token') as mock_token, \
             patch('media_summarizer.workers.spotify_sync.worker.run_playlist_sync_for_user') as mock_sync, \
             patch('media_summarizer.workers.spotify_sync.worker.spotify_follows_db.get_follow') as mock_get_follow, \
             patch('media_summarizer.workers.spotify_sync.worker.spotify_follows_db.upsert_follow') as mock_upsert:
            
            # Setup mocks
            mock_get_user.return_value = mock_user
            mock_token.return_value = None
            mock_sync.return_value = mock_sync_result
            mock_get_follow.return_value = MagicMock()
            mock_upsert.return_value = None
            
            # Execute
            result = await process_sync_message(valid_message_body)
            
            # Verify
            assert result["status"] == "success"
            assert result["user_id"] == "test_user_123"
            assert result["successful_syncs"] == 2
            assert result["total_playlists"] == 2
            assert len(result["results"]) == 2
            
            # Verify calls
            mock_get_user.assert_called_once_with("test_user_123")
            mock_token.assert_called_once_with(mock_user)
            assert mock_sync.call_count == 2

    @pytest.mark.asyncio
    async def test_process_sync_message_missing_user_id(self):
        """Test handling of missing user_id."""
        message_body = {"playlist_ids": ["playlist_1"]}
        
        result = await process_sync_message(message_body)
        
        assert result["status"] == "error"
        assert result["reason"] == "missing_user_id"

    @pytest.mark.asyncio
    async def test_process_sync_message_no_playlists(self):
        """Test handling of empty playlist_ids."""
        message_body = {"user_id": "test_user", "playlist_ids": []}
        
        result = await process_sync_message(message_body)
        
        assert result["status"] == "error"
        assert result["reason"] == "no_playlists"

    @pytest.mark.asyncio
    async def test_process_sync_message_user_not_found(self, valid_message_body):
        """Test handling of user not found."""
        with patch('media_summarizer.workers.spotify_sync.worker.database_async.get_user_by_id') as mock_get_user:
            mock_get_user.return_value = None
            
            result = await process_sync_message(valid_message_body)
            
            assert result["status"] == "error"
            assert result["reason"] == "user_not_found"

    @pytest.mark.asyncio
    async def test_process_sync_message_token_refresh_failed(self, valid_message_body, mock_user):
        """Test handling of token refresh failure."""
        with patch('media_summarizer.workers.spotify_sync.worker.database_async.get_user_by_id') as mock_get_user, \
             patch('media_summarizer.workers.spotify_sync.worker.ensure_access_token') as mock_token:
            
            mock_get_user.return_value = mock_user
            mock_token.side_effect = Exception("Token refresh failed")
            
            result = await process_sync_message(valid_message_body)
            
            assert result["status"] == "error"
            assert result["reason"] == "token_refresh_failed"
            assert "Token refresh failed" in result["error"]

    @pytest.mark.asyncio
    async def test_process_sync_message_partial_failure(self, valid_message_body, mock_user):
        """Test handling of partial sync failures."""
        with patch('media_summarizer.workers.spotify_sync.worker.database_async.get_user_by_id') as mock_get_user, \
             patch('media_summarizer.workers.spotify_sync.worker.ensure_access_token') as mock_token, \
             patch('media_summarizer.workers.spotify_sync.worker.run_playlist_sync_for_user') as mock_sync:
            
            mock_get_user.return_value = mock_user
            mock_token.return_value = None
            
            # First playlist succeeds, second fails
            mock_sync.side_effect = [
                {"status": "success", "submitted": 3},
                {"status": "error", "reason": "playlist_not_found"}
            ]
            
            result = await process_sync_message(valid_message_body)
            
            assert result["status"] == "partial_failure"  # Some succeeded, some failed
            assert result["successful_syncs"] == 1
            assert result["total_playlists"] == 2

    @pytest.mark.asyncio
    async def test_process_sync_message_unexpected_error(self, valid_message_body):
        """Test handling of unexpected errors."""
        with patch('media_summarizer.workers.spotify_sync.worker.database_async.get_user_by_id') as mock_get_user:
            mock_get_user.side_effect = Exception("Database connection failed")
            
            result = await process_sync_message(valid_message_body)
            
            assert result["status"] == "error"
            assert result["reason"] == "unexpected_error"
            assert "Database connection failed" in result["error"]

    def test_lambda_handler_success(self, lambda_event):
        """Test successful Lambda handler execution."""
        with patch('media_summarizer.workers.spotify_sync.worker.process_sync_message') as mock_process:
            mock_process.return_value = {
                "status": "success",
                "user_id": "test_user_123",
                "successful_syncs": 2,
                "total_playlists": 2,
                "results": []
            }
            
            # Mock asyncio.run to avoid actual async execution in test
            with patch('asyncio.run') as mock_run:
                mock_run.return_value = mock_process.return_value
                
                result = lambda_handler(lambda_event, {})
                
                assert result["statusCode"] == 200
                body = json.loads(result["body"])
                assert body["processed"] == 1
                assert len(body["results"]) == 1

    def test_lambda_handler_malformed_json(self):
        """Test Lambda handler with malformed JSON."""
        event = {
            "Records": [
                {
                    "body": "invalid json {",
                    "messageId": "test-id"
                }
            ]
        }
        
        result = lambda_handler(event, {})
        
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["processed"] == 1
        assert body["results"][0]["status"] == "error"

    def test_lambda_handler_empty_records(self):
        """Test Lambda handler with empty records."""
        event = {"Records": []}
        
        result = lambda_handler(event, {})
        
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["processed"] == 0
        assert body["results"] == []

    @pytest.mark.asyncio
    async def test_database_error_handling(self, valid_message_body, mock_user):
        """Test handling of database errors during follow updates."""
        with patch('media_summarizer.workers.spotify_sync.worker.database_async.get_user_by_id') as mock_get_user, \
             patch('media_summarizer.workers.spotify_sync.worker.ensure_access_token') as mock_token, \
             patch('media_summarizer.workers.spotify_sync.worker.run_playlist_sync_for_user') as mock_sync, \
             patch('media_summarizer.workers.spotify_sync.worker.spotify_follows_db.get_follow') as mock_get_follow:
            
            mock_get_user.return_value = mock_user
            mock_token.return_value = None
            mock_sync.return_value = {"status": "success", "submitted": 3}
            mock_get_follow.side_effect = Exception("Database error")
            
            result = await process_sync_message(valid_message_body)
            
            # Should still succeed despite database error in follow update
            assert result["status"] == "success"
            assert result["successful_syncs"] == 2

    @pytest.mark.asyncio
    async def test_concurrent_playlist_processing(self, mock_user):
        """Test that playlists are processed sequentially (not concurrently)."""
        message_body = {
            "user_id": "test_user",
            "playlist_ids": ["playlist_1", "playlist_2", "playlist_3"]
        }
        
        call_order = []
        
        async def mock_sync_with_delay(user, playlist_id):
            call_order.append(playlist_id)
            await asyncio.sleep(0.01)  # Small delay to test ordering
            return {"status": "success", "submitted": 1}
        
        with patch('media_summarizer.workers.spotify_sync.worker.database_async.get_user_by_id') as mock_get_user, \
             patch('media_summarizer.workers.spotify_sync.worker.ensure_access_token') as mock_token, \
             patch('media_summarizer.workers.spotify_sync.worker.run_playlist_sync_for_user') as mock_sync:
            
            mock_get_user.return_value = mock_user
            mock_token.return_value = None
            mock_sync.side_effect = mock_sync_with_delay
            
            result = await process_sync_message(message_body)
            
            # Verify sequential processing
            assert call_order == ["playlist_1", "playlist_2", "playlist_3"]
            assert result["status"] == "success"
            assert result["successful_syncs"] == 3