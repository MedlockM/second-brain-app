"""
Unit tests for the health endpoints.
"""
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from botocore.exceptions import ClientError

# Set AWS credentials for testing
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"

from media_summarizer.api.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database connection for testing."""
    mock_connection = AsyncMock()
    yield mock_connection


@pytest.fixture
def client_with_db_override(mock_db):
    """Create a test client with database dependency override."""
    from media_summarizer.utils.database_async import get_db

    app.dependency_overrides[get_db] = lambda: mock_db
    client = TestClient(app)
    yield client
    # Cleanup
    app.dependency_overrides.clear()


class TestBasicHealthCheck:
    """Test cases for basic health check endpoints."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, client_with_db_override, mock_db):
        """Test successful health check."""
        # Setup
        mock_client = AsyncMock()
        mock_client.list_tables.return_value = {"TableNames": ["users", "podcasts"]}
        mock_db.get_client.return_value.__aenter__.return_value = mock_client

        # Execute
        response = client_with_db_override.get("/api/v1/health")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Media Summarizer API"
        assert data["database"] == "connected"
        assert data["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_health_check_database_error(self, client_with_db_override, mock_db):
        """Test health check with database error."""
        # Setup
        mock_client = AsyncMock()
        mock_client.list_tables.side_effect = ClientError(
            error_response={'Error': {'Code': 'NetworkingError'}},
            operation_name='ListTables'
        )
        mock_db.get_client.return_value.__aenter__.return_value = mock_client

        # Execute
        response = client_with_db_override.get("/api/v1/health")

        # Verify
        assert response.status_code == 503
        assert "Service unhealthy" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_health_check_connection_timeout(self, client_with_db_override, mock_db):
        """Test health check with connection timeout."""
        # Setup
        mock_client = AsyncMock()
        mock_client.list_tables.side_effect = TimeoutError("Connection timeout")
        mock_db.get_client.return_value.__aenter__.return_value = mock_client

        # Execute
        response = client_with_db_override.get("/api/v1/health")

        # Verify
        assert response.status_code == 503
        assert "Service unhealthy" in response.json()["detail"]


class TestDetailedHealthCheck:
    """Test cases for detailed health check endpoints."""

    @pytest.mark.asyncio
    async def test_detailed_health_check_success(self, client_with_db_override, mock_db):
        """Test successful detailed health check."""
        # Setup
        mock_client = AsyncMock()
        expected_tables = ["users", "podcasts", "episodes", "credit_transactions", "processing_jobs"]
        mock_client.list_tables.return_value = {"TableNames": expected_tables}
        mock_db.get_client.return_value.__aenter__.return_value = mock_client

        # Execute
        response = client_with_db_override.get("/api/v1/health/detailed")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Media Summarizer API"
        assert data["version"] == "1.0.0"

        # Check database component
        db_component = data["components"]["database"]
        assert db_component["status"] == "healthy"
        assert db_component["type"] == "DynamoDB"
        assert db_component["tables_count"] == 5
        assert set(db_component["tables"]) == set(expected_tables)

    @pytest.mark.asyncio
    async def test_detailed_health_check_database_unhealthy(self, client_with_db_override, mock_db):
        """Test detailed health check with database issues."""
        # Setup
        mock_client = AsyncMock()
        mock_client.list_tables.side_effect = ClientError(
            error_response={'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
            operation_name='ListTables'
        )
        mock_db.get_client.return_value.__aenter__.return_value = mock_client

        # Execute
        response = client_with_db_override.get("/api/v1/health/detailed")

        # Verify
        assert response.status_code == 503
        data = response.json()["detail"]
        assert data["status"] == "unhealthy"

        # Check database component
        db_component = data["components"]["database"]
        assert db_component["status"] == "unhealthy"
        assert db_component["type"] == "DynamoDB"
        assert "error" in db_component

    @pytest.mark.asyncio
    async def test_detailed_health_check_degraded_service(self, client_with_db_override, mock_db):
        """Test detailed health check with degraded service status."""
        # Setup
        mock_client = AsyncMock()
        mock_client.list_tables.side_effect = Exception("Temporary connection issue")
        mock_db.get_client.return_value.__aenter__.return_value = mock_client

        # Execute
        response = client_with_db_override.get("/api/v1/health/detailed")

        # Verify
        assert response.status_code == 503
        data = response.json()["detail"]
        assert data["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_detailed_health_check_empty_tables(self, client_with_db_override, mock_db):
        """Test detailed health check with no tables."""
        # Setup
        mock_client = AsyncMock()
        mock_client.list_tables.return_value = {"TableNames": []}
        mock_db.get_client.return_value.__aenter__.return_value = mock_client

        # Execute
        response = client_with_db_override.get("/api/v1/health/detailed")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

        # Check database component
        db_component = data["components"]["database"]
        assert db_component["status"] == "healthy"
        assert db_component["tables_count"] == 0
        assert db_component["tables"] == []


class TestHealthCheckIntegration:
    """Test cases for health check integration scenarios."""

    @pytest.mark.asyncio
    async def test_health_check_with_partial_tables(self, client_with_db_override, mock_db):
        """Test health check when only some expected tables exist."""
        # Setup
        mock_client = AsyncMock()
        # Only some tables exist
        mock_client.list_tables.return_value = {"TableNames": ["users", "podcasts"]}
        mock_db.get_client.return_value.__aenter__.return_value = mock_client

        # Execute
        response = client_with_db_override.get("/api/v1/health/detailed")

        # Verify - service should still be healthy even with missing tables
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

        db_component = data["components"]["database"]
        assert db_component["tables_count"] == 2
        assert "users" in db_component["tables"]
        assert "podcasts" in db_component["tables"]

    @pytest.mark.asyncio
    async def test_health_check_malformed_response(self, client_with_db_override, mock_db):
        """Test health check with malformed DynamoDB response."""
        # Setup
        mock_client = AsyncMock()
        # Malformed response without TableNames
        mock_client.list_tables.return_value = {"SomethingElse": "value"}
        mock_db.get_client.return_value.__aenter__.return_value = mock_client

        # Execute
        response = client_with_db_override.get("/api/v1/health/detailed")

        # Verify - should handle gracefully
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

        db_component = data["components"]["database"]
        assert db_component["tables_count"] == 0
        assert db_component["tables"] == []

    @pytest.mark.asyncio
    async def test_health_check_client_creation_error(self, client_with_db_override, mock_db):
        """Test health check when client creation fails."""
        # Setup
        mock_db.get_client.side_effect = Exception("Failed to create DynamoDB client")

        # Execute
        response = client_with_db_override.get("/api/v1/health")

        # Verify
        assert response.status_code == 503
        assert "Service unhealthy" in response.json()["detail"]
        assert "Failed to create DynamoDB client" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_detailed_health_check_client_creation_error(self, client_with_db_override, mock_db):
        """Test detailed health check when client creation fails."""
        # Setup
        mock_db.get_client.side_effect = Exception("Failed to create DynamoDB client")

        # Execute
        response = client_with_db_override.get("/api/v1/health/detailed")

        # Verify
        assert response.status_code == 503
        data = response.json()["detail"]
        assert data["status"] == "unhealthy"

        db_component = data["components"]["database"]
        assert db_component["status"] == "unhealthy"
        assert "Failed to create DynamoDB client" in db_component["error"]


class TestHealthCheckEdgeCases:
    """Test cases for health check edge cases."""

    @pytest.mark.asyncio
    async def test_health_check_very_large_table_list(self, client_with_db_override, mock_db):
        """Test health check with a very large number of tables."""
        # Setup
        mock_client = AsyncMock()
        # Create a large list of table names
        large_table_list = [f"table_{i}" for i in range(1000)]
        mock_client.list_tables.return_value = {"TableNames": large_table_list}
        mock_db.get_client.return_value.__aenter__.return_value = mock_client

        # Execute
        response = client_with_db_override.get("/api/v1/health/detailed")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

        db_component = data["components"]["database"]
        assert db_component["tables_count"] == 1000
        assert len(db_component["tables"]) == 1000

    @pytest.mark.asyncio
    async def test_health_check_unicode_table_names(self, client_with_db_override, mock_db):
        """Test health check with Unicode table names."""
        # Setup
        mock_client = AsyncMock()
        unicode_tables = ["用户表", "播客表", "episodes_表"]
        mock_client.list_tables.return_value = {"TableNames": unicode_tables}
        mock_db.get_client.return_value.__aenter__.return_value = mock_client

        # Execute
        response = client_with_db_override.get("/api/v1/health/detailed")

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

        db_component = data["components"]["database"]
        assert db_component["tables_count"] == 3
        assert set(db_component["tables"]) == set(unicode_tables)

    @pytest.mark.asyncio
    async def test_health_check_async_context_manager_error(self, client_with_db_override, mock_db):
        """Test health check when async context manager fails."""
        # Setup
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.side_effect = Exception("Context manager error")
        mock_db.get_client.return_value = mock_context_manager

        # Execute
        response = client_with_db_override.get("/api/v1/health")

        # Verify
        assert response.status_code == 503
        assert "Service unhealthy" in response.json()["detail"]
        assert "Context manager error" in response.json()["detail"]
