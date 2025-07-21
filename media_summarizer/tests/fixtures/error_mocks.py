"""
Error mock fixtures for tests.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_http_client_with_timeout():
    """
    Create a mock HTTP client that simulates timeouts.
    
    Returns:
        A mock HTTP client with methods that raise timeout errors
    """
    mock = MagicMock()
    mock.get = AsyncMock(side_effect=TimeoutError("HTTP request timed out"))
    mock.post = AsyncMock(side_effect=TimeoutError("HTTP request timed out"))
    mock.put = AsyncMock(side_effect=TimeoutError("HTTP request timed out"))
    mock.delete = AsyncMock(side_effect=TimeoutError("HTTP request timed out"))
    return mock


@pytest.fixture
def mock_http_client_with_connection_error():
    """
    Create a mock HTTP client that simulates connection errors.
    
    Returns:
        A mock HTTP client with methods that raise connection errors
    """
    class ConnectionError(Exception):
        pass
    
    mock = MagicMock()
    mock.get = AsyncMock(side_effect=ConnectionError("Connection refused"))
    mock.post = AsyncMock(side_effect=ConnectionError("Connection refused"))
    mock.put = AsyncMock(side_effect=ConnectionError("Connection refused"))
    mock.delete = AsyncMock(side_effect=ConnectionError("Connection refused"))
    return mock


@pytest.fixture
def mock_http_client_with_status_error():
    """
    Create a mock HTTP client that returns error status codes.
    
    Returns:
        A mock HTTP client that returns responses with error status codes
    """
    class MockResponse:
        def __init__(self, status_code, json_data=None, text=""):
            self.status_code = status_code
            self._json_data = json_data or {}
            self.text = text
            
        async def json(self):
            return self._json_data
            
        async def __aenter__(self):
            return self
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    mock = MagicMock()
    mock.get = AsyncMock(return_value=MockResponse(404, {"error": "Not found"}))
    mock.post = AsyncMock(return_value=MockResponse(400, {"error": "Bad request"}))
    mock.put = AsyncMock(return_value=MockResponse(500, {"error": "Server error"}))
    mock.delete = AsyncMock(return_value=MockResponse(403, {"error": "Forbidden"}))
    return mock


@pytest.fixture
def mock_db_session_with_error():
    """
    Create a mock database session that raises exceptions.
    
    Returns:
        A mock database session with methods that raise exceptions
    """
    from sqlalchemy.exc import SQLAlchemyError
    
    mock = MagicMock()
    mock.execute = AsyncMock(side_effect=SQLAlchemyError("Database error"))
    mock.commit = AsyncMock(side_effect=SQLAlchemyError("Commit error"))
    mock.rollback = AsyncMock()
    
    # Mock context manager
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock()
    
    return mock


@pytest.fixture
def mock_db_connection_error():
    """
    Create a mock database connection that fails.
    
    Returns:
        A function that raises a connection error when called
    """
    from sqlalchemy.exc import OperationalError
    
    async def _raise_connection_error(*args, **kwargs):
        raise OperationalError("Connection failed", None, None)
    
    return _raise_connection_error


@pytest.fixture
def mock_whisper_error():
    """
    Create a mock for Whisper transcription errors.
    
    Returns:
        A function that raises an error when called
    """
    def _raise_whisper_error(*args, **kwargs):
        raise RuntimeError("Whisper transcription failed")
    
    return _raise_whisper_error


@pytest.fixture
def mock_openai_error():
    """
    Create a mock for OpenAI API errors.
    
    Returns:
        A function that raises an error when called
    """
    class OpenAIError(Exception):
        pass
    
    async def _raise_openai_error(*args, **kwargs):
        raise OpenAIError("OpenAI API request failed")
    
    return _raise_openai_error