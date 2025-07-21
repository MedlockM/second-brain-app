"""
API testing fixtures.
"""
import pytest
from fastapi.testclient import TestClient
import json
from typing import Dict, Any, Optional


@pytest.fixture
def test_client():
    """
    Create a FastAPI TestClient for API testing.
    
    Returns:
        A FastAPI TestClient instance
    """
    from media_summarizer.api.main import app
    return TestClient(app)


@pytest.fixture
def api_auth_headers():
    """
    Create authentication headers for API tests.
    
    Returns:
        A dictionary with authentication headers
    """
    return {
        "Authorization": "Bearer test-token",
        "Content-Type": "application/json"
    }


@pytest.fixture
def create_auth_headers():
    """
    Create a function to generate authentication headers with custom user ID.
    
    Returns:
        A function that generates authentication headers
    """
    def _create_headers(user_id: str = "test-user"):
        return {
            "Authorization": f"Bearer test-token-{user_id}",
            "Content-Type": "application/json"
        }
    return _create_headers


@pytest.fixture
def mock_auth_middleware():
    """
    Create a mock authentication middleware for API tests.
    
    This fixture can be used to bypass authentication in API tests.
    
    Returns:
        A mock authentication middleware function
    """
    async def mock_auth(request):
        request.state.user = {
            "id": "test-user",
            "email": "test@example.com",
            "credits": 10
        }
        return request
    
    return mock_auth


@pytest.fixture
def api_response_factory():
    """
    Create a factory function for generating API response objects.
    
    Returns:
        A function that generates API response objects
    """
    def _create_response(
        status_code: int = 200,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ):
        response = {"success": status_code < 400}
        
        if data is not None:
            response["data"] = data
            
        if error is not None:
            response["error"] = error
            
        return response
    
    return _create_response