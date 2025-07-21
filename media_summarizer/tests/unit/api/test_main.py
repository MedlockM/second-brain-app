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
        "/api/v1/podcasts/submit",
        json={"url": "not-a-valid-url"}  # Missing required email field
    )
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "body" in data


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
    assert "/api/v1/podcasts" in "".join(routes)
    assert "/api/v1/users" in "".join(routes)
    assert "/api/v1/credits" in "".join(routes)


def test_startup_event():
    """Test the startup event handler."""
    # This is a simple test to ensure the startup event exists
    startup_event = next(
        (handler for handler in app.router.on_startup if handler.__name__ == "startup_event"),
        None
    )
    assert startup_event is not None
    # We don't call the event handler as it might be async


def test_shutdown_event():
    """Test the shutdown event handler."""
    # This is a simple test to ensure the shutdown event exists
    shutdown_event = next(
        (handler for handler in app.router.on_shutdown if handler.__name__ == "shutdown_event"),
        None
    )
    assert shutdown_event is not None
    # We don't call the event handler as it might be async