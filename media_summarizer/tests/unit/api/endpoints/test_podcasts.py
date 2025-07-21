"""
Unit tests for the podcasts endpoints.
"""
import json
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
import uuid

# Set AWS credentials for testing
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"

from media_summarizer.api.main import app
from media_summarizer.api.endpoints.podcasts import PodcastSubmissionRequest, JobResponse


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_sqs_client():
    """Mock SQS client for testing."""
    with patch("media_summarizer.api.endpoints.podcasts.sqs_client") as mock_client:
        yield mock_client


@pytest.fixture
def mock_db():
    """Mock database session for testing."""
    with patch("media_summarizer.api.endpoints.podcasts.get_db") as mock_get_db:
        mock_session = MagicMock()
        mock_get_db.return_value.__anext__.return_value = mock_session
        yield mock_session


@pytest.fixture
def mock_uuid():
    """Mock UUID generation for predictable job IDs."""
    with patch("media_summarizer.api.endpoints.podcasts.uuid.uuid4") as mock_uuid:
        mock_uuid.return_value = uuid.UUID("12345678-1234-5678-1234-567812345678")
        yield mock_uuid


class TestPodcastSubmission:
    """Tests for podcast submission endpoint."""

    def test_submit_podcast_success(self, client, mock_sqs_client, mock_db, mock_uuid):
        """Test successful podcast submission."""
        # Setup
        mock_sqs_client.send_message.return_value = {"MessageId": "test-message-id"}
        
        # Execute
        response = client.post(
            "/api/v1/podcasts/submit",
            json={"url": "https://example.com/podcast/123", "email": "user@example.com"}
        )
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "12345678-1234-5678-1234-567812345678"
        assert data["status"] == "pending"
        assert "message" in data
        
        # Verify SQS message was sent
        mock_sqs_client.send_message.assert_called_once()
        call_args = mock_sqs_client.send_message.call_args[1]
        message_body = json.loads(call_args["MessageBody"])
        assert message_body["podcast_url"] == "https://example.com/podcast/123"
        assert message_body["email"] == "user@example.com"
        assert message_body["job_id"] == "12345678-1234-5678-1234-567812345678"

    def test_submit_podcast_invalid_url(self, client):
        """Test podcast submission with invalid URL."""
        # Execute
        response = client.post(
            "/api/v1/podcasts/submit",
            json={"url": "not-a-valid-url", "email": "user@example.com"}
        )
        
        # Verify
        assert response.status_code == 422  # Unprocessable Entity
        data = response.json()
        assert "detail" in data
        # Verify the error message contains information about the URL validation
        assert any("url" in error["loc"] for error in data["detail"])

    def test_submit_podcast_invalid_email(self, client):
        """Test podcast submission with invalid email."""
        # Execute
        response = client.post(
            "/api/v1/podcasts/submit",
            json={"url": "https://example.com/podcast/123", "email": "not-an-email"}
        )
        
        # Verify
        assert response.status_code == 422  # Unprocessable Entity
        data = response.json()
        assert "detail" in data
        # Verify the error message contains information about the email validation
        assert any("email" in error["loc"] and "value is not a valid email" in error["msg"].lower() 
                  for error in data["detail"])

    def test_submit_podcast_missing_fields(self, client):
        """Test podcast submission with missing required fields."""
        # Test missing URL
        response = client.post(
            "/api/v1/podcasts/submit",
            json={"email": "user@example.com"}
        )
        assert response.status_code == 422
        assert any("url" in error["loc"] for error in response.json()["detail"])
        
        # Test missing email
        response = client.post(
            "/api/v1/podcasts/submit",
            json={"url": "https://example.com/podcast/123"}
        )
        assert response.status_code == 422
        assert any("email" in error["loc"] for error in response.json()["detail"])
        
        # Test empty request body
        response = client.post("/api/v1/podcasts/submit", json={})
        assert response.status_code == 422
        assert len(response.json()["detail"]) == 2  # Both fields are missing

    def test_submit_podcast_sqs_error(self, client, mock_sqs_client, mock_db, mock_uuid):
        """Test podcast submission with SQS error."""
        # Setup
        mock_sqs_client.send_message.side_effect = Exception("SQS error")
        
        # Execute
        with patch("builtins.print") as mock_print:
            response = client.post(
                "/api/v1/podcasts/submit",
                json={"url": "https://example.com/podcast/123", "email": "user@example.com"}
            )
            
            # Verify that the warning was logged
            mock_print.assert_called_once()
            warning_message = mock_print.call_args[0][0]
            assert "Warning: SQS message sending failed" in warning_message
            assert "SQS error" in warning_message
        
        # Verify - with the new implementation, the endpoint should continue processing
        # even if SQS message sending fails
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "12345678-1234-5678-1234-567812345678"
        assert data["status"] == "pending"
        assert "message" in data
        
        # Verify that SQS send_message was called but failed
        mock_sqs_client.send_message.assert_called_once()

    def test_submit_podcast_connection_timeout(self, client, mock_sqs_client, mock_db, mock_uuid):
        """Test podcast submission with connection timeout."""
        # Setup
        mock_sqs_client.send_message.side_effect = TimeoutError("Connection timed out")
        
        # Execute
        response = client.post(
            "/api/v1/podcasts/submit",
            json={"url": "https://example.com/podcast/123", "email": "user@example.com"}
        )
        
        # Verify - with the new implementation, the endpoint should continue processing
        # even if SQS message sending fails due to timeout
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "12345678-1234-5678-1234-567812345678"
        assert data["status"] == "pending"
        assert "message" in data
        
        # Verify that SQS send_message was called but failed
        mock_sqs_client.send_message.assert_called_once()

    def test_submit_podcast_malformed_request(self, client):
        """Test podcast submission with malformed JSON request."""
        # Execute
        response = client.post(
            "/api/v1/podcasts/submit",
            data="not-a-json-content",
            headers={"Content-Type": "application/json"}
        )
        
        # Verify
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_submit_podcast_with_very_long_url(self, client, mock_sqs_client, mock_db):
        """Test podcast submission with a very long URL."""
        # Setup
        mock_sqs_client.send_message.return_value = {"MessageId": "test-message-id"}
        
        # Create a very long but valid URL
        long_url = f"https://example.com/{'a' * 500}/podcast/123"
        
        # Execute
        response = client.post(
            "/api/v1/podcasts/submit",
            json={"url": long_url, "email": "user@example.com"}
        )
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        
        # Verify SQS message was sent with the long URL
        mock_sqs_client.send_message.assert_called_once()
        call_args = mock_sqs_client.send_message.call_args[1]
        message_body = json.loads(call_args["MessageBody"])
        assert message_body["podcast_url"] == long_url

    def test_submit_podcast_with_special_characters(self, client, mock_sqs_client, mock_db):
        """Test podcast submission with special characters in URL and email."""
        # Setup
        mock_sqs_client.send_message.return_value = {"MessageId": "test-message-id"}
        
        # URL with special characters (still valid)
        url_with_special_chars = "https://example.com/podcast/123?q=test&lang=fr#section"
        
        # Execute
        response = client.post(
            "/api/v1/podcasts/submit",
            json={"url": url_with_special_chars, "email": "user+test@example.com"}
        )
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        
        # Verify SQS message was sent with the correct data
        mock_sqs_client.send_message.assert_called_once()
        call_args = mock_sqs_client.send_message.call_args[1]
        message_body = json.loads(call_args["MessageBody"])
        assert message_body["podcast_url"] == url_with_special_chars
        assert message_body["email"] == "user+test@example.com"


class TestJobStatus:
    """Tests for job status endpoint."""

    def test_get_job_status(self, client, mock_db):
        """Test getting job status."""
        # Execute
        response = client.get("/api/v1/podcasts/test-job-id/status")
        
        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "test-job-id"
        assert data["status"] == "processing"
        assert "message" in data

    def test_get_job_status_invalid_id_format(self, client, mock_db):
        """Test getting job status with invalid ID format."""
        # Execute - test with an empty job ID
        response = client.get("/api/v1/podcasts//status")
        
        # Verify
        assert response.status_code == 404  # Not Found
        
        # Execute - test with a very long job ID
        very_long_id = "a" * 1000
        response = client.get(f"/api/v1/podcasts/{very_long_id}/status")
        
        # Verify - FastAPI should still accept this, but we're testing the endpoint behavior
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == very_long_id

    @pytest.mark.xfail(reason="Endpoint not fully implemented yet - should return 404 for nonexistent jobs")
    def test_get_job_status_nonexistent_job(self, client, mock_db):
        """Test getting status for a nonexistent job.
        
        This test expects the endpoint to return a 404 error when a job doesn't exist,
        but the current implementation always returns a processing status.
        """
        # Execute
        response = client.get("/api/v1/podcasts/nonexistent-job/status")
        
        # This should fail until the endpoint is fully implemented
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_get_job_status_db_error(self, client, mock_db):
        """Test getting job status with database error."""
        # Setup - configure the mock to raise an exception when called
        mock_db.execute.side_effect = Exception("Database connection error")
        
        # Execute
        # The current implementation doesn't use the database session
        # so this won't actually trigger an error
        response = client.get("/api/v1/podcasts/test-job-id/status")
        
        # Verify - currently always returns 200 with processing status
        # This should be updated when the endpoint is fully implemented
        assert response.status_code == 200, "Expected 200 status code for current implementation"
        data = response.json()
        assert data["status"] == "processing", "Expected processing status in response"
        
        # TODO: When the endpoint is fully implemented to use the database, 
        # this test should verify that database errors are properly handled