# Test Utilities for Media Summarizer

This directory contains utilities and helpers for writing tests for the Media Summarizer application.

## Available Utilities

### Test Helpers (`test_helpers.py`)

Common helper functions for tests:

- `create_sqs_message()`: Create a mock SQS message for testing
- `create_api_auth_headers()`: Create mock authentication headers for API tests
- `assert_sqs_message_sent()`: Assert that a message was sent to SQS with expected content
- `assert_s3_file_uploaded()`: Assert that a file was uploaded to S3
- `assert_email_sent()`: Assert that an email was sent with expected content
- `set_env_vars()`: Set environment variables for testing
- `restore_env_vars()`: Restore environment variables to their original values

### Base Test Classes (`base_test_classes.py`)

Base classes for different types of tests:

- `BaseTestCase`: Base class for all test cases
- `BaseUnitTestCase`: Base class for unit tests
- `BaseWorkerTestCase`: Base class for worker tests
- `BaseAdapterTestCase`: Base class for adapter tests
- `BaseAPITestCase`: Base class for API tests
- `BaseIntegrationTestCase`: Base class for integration tests

### Test Models (`test_models.py`)

Test data models for use in tests:

- `TestUser`: Test user data model
- `TestPodcast`: Test podcast data model
- `TestEpisode`: Test episode data model
- `TestJob`: Test job data model
- `TestSummary`: Test summary data model
- `TestCreditTransaction`: Test credit transaction data model
- `TestFeedData`: Test RSS feed data

## Usage Examples

### Using Test Helpers

```python
from media_summarizer.tests.utils.test_helpers import create_sqs_message, create_api_auth_headers

# Create a mock SQS message
message = create_sqs_message({"job_id": "job-123", "status": "pending"})

# Create authentication headers
headers = create_api_auth_headers("user-123")
```

### Using Assertion Helpers

```python
from media_summarizer.tests.utils.test_helpers import assert_sqs_message_sent, assert_s3_file_uploaded, assert_email_sent

# Verify that a message was sent to SQS
message_body = assert_sqs_message_sent(
    mock_sqs_client,
    expected_queue_url="http://localhost:4566/000000000000/test-queue",
    expected_body_contains={"job_id": "job-123"}
)

# Verify that a file was uploaded to S3
s3_key = assert_s3_file_uploaded(
    mock_s3_client,
    expected_bucket="test-bucket",
    expected_key_prefix="audio/"
)

# Verify that an email was sent
email_message = assert_email_sent(
    mock_ses_client,
    expected_recipient="user@example.com",
    expected_subject_contains="Your podcast summary is ready",
    expected_body_contains="podcast summary"
)
```

### Using Base Test Classes

```python
import pytest
from media_summarizer.tests.utils.base_test_classes import BaseWorkerTestCase

class TestMyWorker(BaseWorkerTestCase):
    @pytest.mark.asyncio
    async def test_worker_method(self, mock_sqs_client, mock_s3_client):
        # Test a worker with SQS and S3 mocks
        # Create an SQS message for testing
        message = self.create_sqs_message({"key": "value"})
        
        # ... test implementation ...
```

### Using Test Models

```python
from media_summarizer.tests.utils.test_models import TestUser, TestPodcast, TestEpisode

# Create a test user
user = TestUser.create(
    user_id="user-123",
    email="user@example.com",
    credits=100
)

# Create a test podcast
podcast = TestPodcast.create(
    podcast_id="podcast-123",
    title="Test Podcast"
)

# Create a test episode
episode = TestEpisode.create(
    episode_id="episode-123",
    podcast_id=podcast["id"],
    title="Test Episode"
)
```

## Best Practices

1. **Use the base test classes** to standardize your tests and reduce boilerplate code.
2. **Use the test models** to create consistent test data.
3. **Use the assertion helpers** to make your tests more readable and maintainable.
4. **Isolate your tests** by using fresh test data for each test.
5. **Mock external dependencies** to avoid making real API calls during tests.
6. **Use descriptive test names** that explain what is being tested and the expected outcome.
7. **Group related tests** in the same test class.
8. **Keep tests independent** so they can be run in any order.