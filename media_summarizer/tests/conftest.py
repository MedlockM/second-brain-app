"""
Configuration file for pytest.
This file contains fixtures and configuration that will be available to all tests.
"""
import os
import json
import pytest
import pytest_asyncio
import sys
from unittest.mock import MagicMock, AsyncMock, patch

# Configuration des variables d'environnement pour les tests
os.environ["ENVIRONMENT"] = "test"
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"  # LocalStack endpoint

# Check if we should mock Whisper
MOCK_WHISPER = os.environ.get("MOCK_WHISPER", "0") == "1"

# Configuration globale pour pytest
def pytest_configure(config):
    """Configure pytest with custom markers and settings."""
    # Add custom markers
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "api: mark test as API test")
    config.addinivalue_line("markers", "worker: mark test as worker test")
    config.addinivalue_line("markers", "adapter: mark test as adapter test")
    config.addinivalue_line("markers", "core: mark test as core component test")
    config.addinivalue_line("markers", "database: mark test as database test")

# Set custom options for pytest
def pytest_addoption(parser):
    """Add custom command line options to pytest."""
    parser.addoption(
        "--run-slow", 
        action="store_true", 
        default=False, 
        help="Run slow tests"
    )

# Skip slow tests by default
def pytest_collection_modifyitems(config, items):
    """Skip slow tests unless --run-slow is specified."""
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="Need --run-slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)

# AWS Service Mocks
@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client for testing."""
    mock = MagicMock()
    mock.upload_file = AsyncMock()
    mock.download_file = AsyncMock()
    mock.generate_presigned_url = MagicMock(return_value="https://example.com/presigned-url")
    return mock

@pytest.fixture
def mock_sqs_client():
    """Create a mock SQS client for testing."""
    mock = MagicMock()
    mock.send_message = AsyncMock()
    mock.receive_message = AsyncMock(return_value={"Messages": [{"Body": "{}", "ReceiptHandle": "receipt-123"}]})
    mock.delete_message = AsyncMock()
    return mock

@pytest.fixture
def mock_ses_client():
    """Create a mock SES client for testing."""
    mock = MagicMock()
    mock.send_email = AsyncMock(return_value={"MessageId": "message-123"})
    return mock

# Error Mocks
@pytest.fixture
def mock_s3_client_with_error():
    """Create a mock S3 client that generates errors."""
    mock = MagicMock()
    mock.upload_file = AsyncMock(side_effect=Exception("S3 upload error"))
    mock.download_file = AsyncMock(side_effect=Exception("S3 download error"))
    return mock

@pytest.fixture
def mock_http_client_with_timeout():
    """Create a mock HTTP client that simulates timeouts."""
    mock = MagicMock()
    mock.get = AsyncMock(side_effect=TimeoutError("HTTP request timed out"))
    mock.post = AsyncMock(side_effect=TimeoutError("HTTP request timed out"))
    return mock

# SQS Message Helpers
@pytest.fixture
def create_sqs_message():
    """Create a function to generate SQS message objects for testing."""
    def _create_message(body, receipt_handle="receipt-123"):
        return {
            "MessageId": "msg-123",
            "ReceiptHandle": receipt_handle,
            "Body": json.dumps(body) if isinstance(body, dict) else body,
            "Attributes": {
                "SentTimestamp": "1234567890"
            }
        }
    return _create_message

# API Test Helpers
@pytest.fixture
def create_api_auth_headers():
    """Create a function to generate authentication headers for API tests."""
    def _create_headers(user_id="test-user"):
        return {
            "Authorization": f"Bearer test-token-{user_id}"
        }
    return _create_headers

# Database Fixtures
@pytest_asyncio.fixture
async def test_db_engine():
    """Create an in-memory SQLite database engine for testing."""
    from sqlalchemy.ext.asyncio import create_async_engine
    
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture
async def test_db_session(test_db_engine):
    """Create a test database session."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    # Create tables
    from sqlalchemy.ext.asyncio import AsyncEngine
    from sqlalchemy import MetaData, Table, Column, Integer, String, ForeignKey, Text, DateTime, Boolean, Float
    
    metadata = MetaData()
    
    # Define tables here if needed for tests
    # Example:
    # users = Table(
    #     "users",
    #     metadata,
    #     Column("id", String, primary_key=True),
    #     Column("email", String, unique=True, nullable=False),
    #     Column("hashed_password", String, nullable=False),
    #     Column("created_at", DateTime, nullable=False),
    # )
    
    async with test_db_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    
    async_session = sessionmaker(
        test_db_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()

@pytest.fixture
def db_transaction_mock():
    """Create a mock for database transactions."""
    class AsyncContextManagerMock:
        async def __aenter__(self):
            return self
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    mock = AsyncMock()
    mock.transaction.return_value = AsyncContextManagerMock()
    return mock

# Test Data Models
class TestModels:
    """Test data models for generating sample data."""
    
    @staticmethod
    def podcast(override=None):
        """Generate a sample podcast dictionary."""
        data = {
            "id": "podcast-123",
            "title": "Test Podcast",
            "description": "A test podcast for unit testing",
            "feed_url": "https://example.com/feed.xml",
            "website": "https://example.com",
            "image_url": "https://example.com/image.jpg",
            "language": "en",
            "author": "Test Author",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z"
        }
        if override:
            data.update(override)
        return data
    
    @staticmethod
    def episode(override=None):
        """Generate a sample episode dictionary."""
        data = {
            "id": "episode-123",
            "podcast_id": "podcast-123",
            "title": "Test Episode",
            "description": "A test episode for unit testing",
            "audio_url": "https://example.com/episode.mp3",
            "image_url": "https://example.com/episode-image.jpg",
            "published_at": "2023-01-01T00:00:00Z",
            "duration": 1800,  # 30 minutes in seconds
            "file_size": 30000000,  # 30MB in bytes
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z"
        }
        if override:
            data.update(override)
        return data
    
    @staticmethod
    def user(override=None):
        """Generate a sample user dictionary."""
        data = {
            "id": "user-123",
            "email": "test@example.com",
            "hashed_password": "hashed_password_value",
            "full_name": "Test User",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "credits": 10
        }
        if override:
            data.update(override)
        return data
    
    @staticmethod
    def job(override=None):
        """Generate a sample job dictionary."""
        data = {
            "id": "job-123",
            "user_id": "user-123",
            "podcast_id": "podcast-123",
            "episode_id": "episode-123",
            "status": "pending",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "error": None
        }
        if override:
            data.update(override)
        return data
    
    @staticmethod
    def transcription(override=None):
        """Generate a sample transcription dictionary."""
        data = {
            "id": "transcription-123",
            "episode_id": "episode-123",
            "text": "This is a sample transcription text for testing purposes.",
            "language": "en",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z"
        }
        if override:
            data.update(override)
        return data
    
    @staticmethod
    def summary(override=None):
        """Generate a sample summary dictionary."""
        data = {
            "id": "summary-123",
            "episode_id": "episode-123",
            "text": "This is a sample summary text for testing purposes.",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:00:00Z",
            "topics": ["topic1", "topic2"],
            "key_points": ["point1", "point2", "point3"]
        }
        if override:
            data.update(override)
        return data

@pytest.fixture
def test_models():
    """Provide access to test data models."""
    return TestModels

# Whisper Mock
if MOCK_WHISPER:
    # Create a mock for the Whisper model
    class MockWhisperModel:
        def __init__(self):
            self.is_mock = True
        
        def transcribe(self, audio_file, **kwargs):
            """Mock transcription function that returns a predefined result."""
            return {
                "text": "This is a mock transcription for testing purposes.",
                "segments": [
                    {
                        "id": 0,
                        "start": 0.0,
                        "end": 10.0,
                        "text": "This is a mock transcription segment."
                    }
                ],
                "language": "en"
            }
    
    # Create a patch for the Whisper model
    @pytest.fixture(autouse=True)
    def mock_whisper():
        """Mock the Whisper model to avoid downloading it during tests."""
        with patch("whisper.load_model") as mock_load_model:
            mock_model = MockWhisperModel()
            mock_load_model.return_value = mock_model
            yield mock_load_model

# Test Data Samples
@pytest.fixture
def rss_feed_sample():
    """Provide a sample RSS feed XML."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Test Podcast</title>
    <link>https://example.com</link>
    <description>A test podcast for unit testing</description>
    <language>en-us</language>
    <itunes:author>Test Author</itunes:author>
    <itunes:image href="https://example.com/image.jpg"/>
    <item>
      <title>Test Episode</title>
      <description>A test episode for unit testing</description>
      <pubDate>Sat, 01 Jan 2023 00:00:00 +0000</pubDate>
      <enclosure url="https://example.com/episode.mp3" length="30000000" type="audio/mpeg"/>
      <guid isPermaLink="false">episode-123</guid>
      <itunes:duration>30:00</itunes:duration>
      <itunes:image href="https://example.com/episode-image.jpg"/>
    </item>
  </channel>
</rss>"""

@pytest.fixture
def api_responses():
    """Provide sample API responses for external services."""
    return {
        "spotify": {
            "success": {"name": "Test Podcast", "external_urls": {"spotify": "https://open.spotify.com/show/123"}},
            "error": {"error": {"status": 404, "message": "Podcast not found"}}
        },
        "apple": {
            "success": {"results": [{"trackName": "Test Podcast", "feedUrl": "https://example.com/feed.xml"}]},
            "error": {"errorMessage": "Resource not found"}
        }
    }