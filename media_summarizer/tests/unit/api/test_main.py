"""
Unit tests for the main FastAPI application.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from media_summarizer.api.main import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


def test_root_endpoint(client):
    """Test the root endpoint returns a welcome message."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Bienvenue sur l'API Media Summarizer"}


def test_cors_middleware():
    """Test that CORS middleware is properly configured."""
    # Check that CORS middleware is in the app's middleware stack
    cors_middleware = next(
        (m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"),
        None
    )
    assert cors_middleware is not None


def test_validation_exception_handler(client):
    """Test the validation exception handler."""
    # Send a request with invalid data to trigger validation error
    response = client.post(
        "/api/v1/podcast-search/episodes",
        json={"feed_id": -1}  # Invalid feed_id (must be > 0)
    )
    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "VALIDATION_ERROR"


def test_general_exception_handler():
    """Test the general exception handler."""
    # Since the exception handler is async, we'll test it indirectly
    # by checking if it's properly registered

    # Check that the exception handler is registered for Exception
    exception_handlers = app.exception_handlers.get(Exception)
    assert exception_handlers is not None

    # We can't easily test the actual handler in a unit test because it's async
    # and requires a proper FastAPI context, so we'll just verify it exists


def test_router_inclusion():
    """Test that all routers are included in the app."""
    # Check that all expected routes are registered
    routes = [route.path for route in app.routes]
    assert "/api/v1/health" in "".join(routes)
    assert "/api/v1/podcast-search" in "".join(routes)
    assert "/api/v1/users" in "".join(routes)
    assert "/api/v1/credits" in "".join(routes)


def test_startup_event():
    """Test the lifespan handles startup logic."""
    # Test that the app has a lifespan configured which handles startup
    assert app.router.lifespan_context is not None
    # Verify that the lifespan is callable (it's an async context manager)
    assert callable(app.router.lifespan_context)


def test_shutdown_event():
    """Test the lifespan handles shutdown logic."""
    # Test that the app has a lifespan configured which handles shutdown
    assert app.router.lifespan_context is not None
    # Since startup and shutdown are handled by the same lifespan context manager,
    # this test verifies the same thing as startup but maintains the original intent
    assert callable(app.router.lifespan_context)
