"""
Unit tests for the users endpoints.
"""
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

# Set AWS credentials for testing
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"

from media_summarizer.api.main import app
from media_summarizer.api.endpoints.users import (
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest
)
from media_summarizer.core.models import User


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database connection for testing."""
    with patch("media_summarizer.api.endpoints.users.get_db") as mock_get_db:
        mock_connection = AsyncMock()
        mock_get_db.return_value = mock_connection
        yield mock_connection


@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    return User(
        id="user123",
        email="test@example.com",
        credits=100
    )


class TestUserCreation:
    """Test cases for user creation endpoints."""

    @pytest.mark.asyncio
    async def test_create_user_success(self, client, mock_db, sample_user):
        """Test successful user creation."""
        with patch("media_summarizer.api.endpoints.users.database_async.get_user_by_email") as mock_get_by_email:
            with patch("media_summarizer.api.endpoints.users.database_async.create_user") as mock_create:
                mock_get_by_email.return_value = None  # User doesn't exist
                mock_create.return_value = sample_user

                response = client.post("/api/v1/users", json={
                    "email": "test@example.com"
                })

                assert response.status_code == 201
                data = response.json()
                assert data["email"] == "test@example.com"
                assert data["credits"] == 100
                assert "id" in data
                assert "created_at" in data
                assert "updated_at" in data
                mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_email_already_exists(self, client, mock_db, sample_user):
        """Test user creation with existing email."""
        with patch("media_summarizer.api.endpoints.users.database_async.get_user_by_email") as mock_get_by_email:
            mock_get_by_email.return_value = sample_user  # User exists

            response = client.post("/api/v1/users", json={
                "email": "test@example.com"
            })

            assert response.status_code == 409
            assert response.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"

    @pytest.mark.asyncio
    async def test_create_user_invalid_email(self, client):
        """Test user creation with invalid email."""
        response = client.post("/api/v1/users", json={
            "email": "invalid-email"
        })

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_create_user_missing_email(self, client):
        """Test user creation with missing email."""
        response = client.post("/api/v1/users", json={})

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_create_user_database_error(self, client, mock_db):
        """Test user creation with database error."""
        with patch("media_summarizer.api.endpoints.users.database_async.get_user_by_email") as mock_get_by_email:
            with patch("media_summarizer.api.endpoints.users.database_async.create_user") as mock_create:
                mock_get_by_email.return_value = None
                mock_create.side_effect = Exception("Database error")

                response = client.post("/api/v1/users", json={
                    "email": "test@example.com"
                })

                assert response.status_code == 500
                assert response.json()["error"]["code"] == "INTERNAL_ERROR"


class TestUserRetrieval:
    """Test cases for user retrieval endpoints."""

    @pytest.mark.asyncio
    async def test_get_user_by_id_success(self, client, mock_db, sample_user):
        """Test successful user retrieval by ID."""
        with patch("media_summarizer.api.endpoints.users.database_async.get_user_by_id") as mock_get_by_id:
            mock_get_by_id.return_value = sample_user

            response = client.get("/api/v1/users/user123")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "user123"
            assert data["email"] == "test@example.com"
            assert data["credits"] == 100

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found(self, client, mock_db):
        """Test user retrieval by ID when user doesn't exist."""
        with patch("media_summarizer.api.endpoints.users.database_async.get_user_by_id") as mock_get_by_id:
            mock_get_by_id.return_value = None

            response = client.get("/api/v1/users/nonexistent")

            assert response.status_code == 404
            assert response.json()["error"]["code"] == "USER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_user_by_email_success(self, client, mock_db, sample_user):
        """Test successful user retrieval by email."""
        with patch("media_summarizer.api.endpoints.users.database_async.get_user_by_email") as mock_get_by_email:
            mock_get_by_email.return_value = sample_user

            response = client.get("/api/v1/users/email/test@example.com")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "user123"
            assert data["email"] == "test@example.com"
            assert data["credits"] == 100

    @pytest.mark.asyncio
    async def test_get_user_by_email_not_found(self, client, mock_db):
        """Test user retrieval by email when user doesn't exist."""
        with patch("media_summarizer.api.endpoints.users.database_async.get_user_by_email") as mock_get_by_email:
            mock_get_by_email.return_value = None

            response = client.get("/api/v1/users/email/nonexistent@example.com")

            assert response.status_code == 404
            assert response.json()["error"]["code"] == "USER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_get_user_by_email_invalid_format(self, client):
        """Test user retrieval by email with invalid email format."""
        response = client.get("/api/v1/users/email/invalid-email")

        assert response.status_code == 422  # Validation error


class TestUserUpdate:
    """Test cases for user update endpoints."""

    @pytest.mark.asyncio
    async def test_update_user_success(self, client, mock_db, sample_user):
        """Test successful user update."""
        updated_user = User(
            id=sample_user.id,
            email="updated@example.com",
            credits=sample_user.credits
        )

        with patch("media_summarizer.api.endpoints.users.database_async.get_user_by_id") as mock_get_by_id:
            with patch("media_summarizer.api.endpoints.users.database_async.get_user_by_email") as mock_get_by_email:
                with patch("media_summarizer.api.endpoints.users.database_async.update_user") as mock_update:
                    mock_get_by_id.return_value = sample_user
                    mock_get_by_email.return_value = None  # New email doesn't exist
                    mock_update.return_value = updated_user

                    response = client.put("/api/v1/users/user123", json={
                        "email": "updated@example.com"
                    })

                    assert response.status_code == 200
                    data = response.json()
                    assert data["email"] == "updated@example.com"
                    mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_not_found(self, client, mock_db):
        """Test user update when user doesn't exist."""
        with patch("media_summarizer.api.endpoints.users.database_async.get_user_by_id") as mock_get_by_id:
            mock_get_by_id.return_value = None

            response = client.put("/api/v1/users/nonexistent", json={
                "email": "updated@example.com"
            })

            assert response.status_code == 404
            assert response.json()["error"]["code"] == "USER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_update_user_email_conflict(self, client, mock_db, sample_user):
        """Test user update with email that already exists."""
        existing_user = User(
            id="other123",
            email="existing@example.com",
            credits=50
        )

        with patch("media_summarizer.api.endpoints.users.database_async.get_user_by_id") as mock_get_by_id:
            with patch("media_summarizer.api.endpoints.users.database_async.get_user_by_email") as mock_get_by_email:
                mock_get_by_id.return_value = sample_user
                mock_get_by_email.return_value = existing_user  # Email exists

                response = client.put("/api/v1/users/user123", json={
                    "email": "existing@example.com"
                })

                assert response.status_code == 409
                assert response.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"

    @pytest.mark.asyncio
    async def test_update_user_no_changes(self, client, mock_db, sample_user):
        """Test user update with no changes."""
        with patch("media_summarizer.api.endpoints.users.database_async.get_user_by_id") as mock_get_by_id:
            mock_get_by_id.return_value = sample_user

            response = client.put("/api/v1/users/user123", json={})

            assert response.status_code == 200
            data = response.json()
            assert data["email"] == sample_user.email

    @pytest.mark.asyncio
    async def test_update_user_invalid_email(self, client):
        """Test user update with invalid email."""
        response = client.put("/api/v1/users/user123", json={
            "email": "invalid-email"
        })

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_update_user_database_error(self, client, mock_db, sample_user):
        """Test user update with database error."""
        with patch("media_summarizer.api.endpoints.users.database_async.get_user_by_id") as mock_get_by_id:
            with patch("media_summarizer.api.endpoints.users.database_async.get_user_by_email") as mock_get_by_email:
                with patch("media_summarizer.api.endpoints.users.database_async.update_user") as mock_update:
                    mock_get_by_id.return_value = sample_user
                    mock_get_by_email.return_value = None
                    mock_update.side_effect = Exception("Database error")

                    response = client.put("/api/v1/users/user123", json={
                        "email": "updated@example.com"
                    })

                    assert response.status_code == 500
                    assert response.json()["error"]["code"] == "INTERNAL_ERROR"


class TestUserDeletion:
    """Test cases for user deletion endpoints."""

    @pytest.mark.asyncio
    async def test_delete_user_success(self, client, mock_db):
        """Test successful user deletion."""
        with patch("media_summarizer.api.endpoints.users.database_async.delete_user") as mock_delete:
            mock_delete.return_value = True

            response = client.delete("/api/v1/users/user123")

            assert response.status_code == 204
            mock_delete.assert_called_once_with("user123")

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, client, mock_db):
        """Test user deletion when user doesn't exist."""
        with patch("media_summarizer.api.endpoints.users.database_async.delete_user") as mock_delete:
            mock_delete.return_value = False

            response = client.delete("/api/v1/users/nonexistent")

            assert response.status_code == 404
            assert response.json()["error"]["code"] == "USER_NOT_FOUND"


class TestModelValidation:
    """Test cases for Pydantic model validation."""

    def test_user_create_request_validation(self):
        """Test UserCreateRequest validation."""
        # Valid request
        valid_request = UserCreateRequest(email="test@example.com")
        assert valid_request.email == "test@example.com"

        # Invalid email
        with pytest.raises(ValueError):
            UserCreateRequest(email="invalid-email")

    def test_user_update_request_validation(self):
        """Test UserUpdateRequest validation."""
        # Valid request with email
        valid_request = UserUpdateRequest(email="test@example.com")
        assert valid_request.email == "test@example.com"

        # Valid request without email
        valid_request = UserUpdateRequest()
        assert valid_request.email is None

        # Invalid email
        with pytest.raises(ValueError):
            UserUpdateRequest(email="invalid-email")

    def test_user_response_from_user(self, sample_user):
        """Test UserResponse.from_user method."""
        response = UserResponse.from_user(sample_user)

        assert response.id == sample_user.id
        assert response.email == sample_user.email
        assert response.credits == sample_user.credits
        assert response.created_at == sample_user.created_at.isoformat()
        assert response.updated_at == sample_user.updated_at.isoformat()
