# Testing Guide for Media Summarizer

This document provides guidelines and best practices for writing tests for the Media Summarizer application.

## Table of Contents

1. [Test Structure](#test-structure)
2. [Test Types](#test-types)
3. [Test Naming Conventions](#test-naming-conventions)
4. [Test Fixtures](#test-fixtures)
5. [Mocking External Dependencies](#mocking-external-dependencies)
6. [Test Isolation](#test-isolation)
7. [Test Coverage](#test-coverage)
8. [Running Tests](#running-tests)
9. [Continuous Integration](#continuous-integration)
10. [Troubleshooting](#troubleshooting)

## Test Structure

The test directory structure mirrors the application structure:

```
media_summarizer/tests/
├── unit/                    # Unit tests
│   ├── adapters/            # Tests for adapters
│   ├── api/                 # Tests for API endpoints
│   ├── core/                # Tests for core domain logic
│   └── workers/             # Tests for workers
├── integration/             # Integration tests
│   └── workflows/           # Tests for end-to-end workflows
├── fixtures/                # Test fixtures
└── utils/                   # Test utilities
```

## Test Types

### Unit Tests

Unit tests focus on testing individual components in isolation. They should be:

- Fast: Each test should run in milliseconds
- Independent: No dependencies on external services or other components
- Repeatable: Same results every time they run
- Self-validating: Automatically determine if the test passed or failed
- Timely: Written at the same time as the code they test

Example:

```python
@pytest.mark.asyncio
async def test_send_email(mock_ses_client):
    """Test sending an email."""
    # Setup
    adapter = EmailAdapter()
    recipient = "user@example.com"
    subject = "Test Subject"
    body_text = "Test body text"
    
    # Execute
    result = await adapter.send_email(
        recipient, subject, body_text, ses_client=mock_ses_client
    )
    
    # Verify
    mock_ses_client.send_email.assert_called_once()
    assert result["MessageId"] == "test-message-id"
```

### Integration Tests

Integration tests verify that different components work together correctly. They should:

- Test interactions between components
- Use real dependencies when possible, or realistic mocks
- Cover complete workflows
- Validate end-to-end functionality

Example:

```python
@pytest.mark.asyncio
async def test_podcast_submission_workflow(test_client, mock_sqs_client):
    """Test the podcast submission workflow."""
    # Submit a podcast URL
    response = test_client.post(
        "/submit",
        json={"url": "https://example.com/podcast", "email": "user@example.com"}
    )
    
    # Verify the response
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    
    # Verify that a message was sent to the queue
    mock_sqs_client.send_message.assert_called_once()
```

## Test Naming Conventions

Follow these naming conventions for tests:

- Test files: `test_<module_name>.py`
- Test classes: `Test<ComponentName>`
- Test methods: `test_<function_name>_<scenario>`

Examples:
- `test_email_adapter.py`
- `TestEmailAdapter`
- `test_send_email_with_html_body`

## Test Fixtures

Use pytest fixtures to set up test dependencies and reduce code duplication:

```python
@pytest.fixture
def mock_ses_client():
    """Mock SES client for testing."""
    mock_client = AsyncMock()
    mock_client.send_email = AsyncMock(return_value={"MessageId": "test-message-id"})
    return mock_client

@pytest.fixture
def sample_podcast():
    """Create a sample podcast for testing."""
    return Podcast(
        id="podcast-123",
        title="Test Podcast",
        feed_url="https://example.com/feed.xml"
    )
```

Use the base test classes provided in `media_summarizer/tests/utils/base_test_classes.py` to standardize your tests:

```python
from media_summarizer.tests.utils.base_test_classes import BaseWorkerTestCase

class TestMyWorker(BaseWorkerTestCase):
    @pytest.mark.asyncio
    async def test_worker_method(self, mock_sqs_client, mock_s3_client):
        # Test implementation
```

## Mocking External Dependencies

Always mock external dependencies in unit tests:

```python
# Mock boto3 client
with patch("boto3.client") as mock_boto3:
    mock_client = AsyncMock()
    mock_boto3.return_value = mock_client
    
    # Test code that uses boto3
```

Use the helper functions in `media_summarizer/tests/utils/test_helpers.py` to simplify assertions:

```python
from media_summarizer.tests.utils.test_helpers import assert_sqs_message_sent

# Verify that a message was sent to SQS
message_body = assert_sqs_message_sent(
    mock_sqs_client,
    expected_queue_url="test-queue",
    expected_body_contains={"job_id": "job-123"}
)
```

## Test Isolation

Ensure that tests are isolated from each other:

- Use fresh test data for each test
- Clean up any resources created during the test
- Don't rely on the state from previous tests
- Use `@pytest.mark.asyncio` for async tests
- Use `pytest-asyncio` with `auto` mode for proper async test isolation

## Test Coverage

Aim for at least 80% code coverage:

- Use `pytest-cov` to measure coverage
- Focus on covering critical paths and edge cases
- Don't chase 100% coverage at the expense of test quality
- Regularly review coverage reports to identify gaps

Run coverage reports:

```bash
# Run tests with coverage
python -m media_summarizer.scripts.run_coverage --all

# Run tests in parallel with coverage
python -m media_summarizer.scripts.run_parallel_tests --coverage --html
```

## Running Tests

### Running All Tests

```bash
# Run all tests
pytest

# Run tests in parallel
python -m media_summarizer.scripts.run_parallel_tests
```

### Running Specific Tests

```bash
# Run a specific test file
pytest media_summarizer/tests/unit/adapters/email/test_email_adapter.py

# Run a specific test class
pytest media_summarizer/tests/unit/adapters/email/test_email_adapter.py::TestEmailAdapter

# Run a specific test method
pytest media_summarizer/tests/unit/adapters/email/test_email_adapter.py::TestEmailAdapter::test_send_email
```

### Running Tests by Type

```bash
# Run only unit tests
pytest media_summarizer/tests/unit/

# Run only integration tests
pytest media_summarizer/tests/integration/

# Skip integration tests
pytest -k "not integration"
```

### Running Tests in Parallel

```bash
# Run tests in parallel with auto-detection of CPU cores
python -m media_summarizer.scripts.run_parallel_tests

# Run tests in parallel with a specific number of workers
python -m media_summarizer.scripts.run_parallel_tests --workers 4

# Run tests in parallel with coverage
python -m media_summarizer.scripts.run_parallel_tests --coverage --html
```

## Continuous Integration

The CI pipeline runs tests automatically on every push and pull request:

- Tests are run in parallel to speed up the build
- Coverage reports are generated and uploaded to Codecov
- A coverage badge is updated on the main branch

See `.github/workflows/test-coverage.yml` for details.

## Troubleshooting

### Common Issues

1. **Tests are failing with "Event loop is closed"**
   - Make sure you're using `@pytest.mark.asyncio` for async tests
   - Check that you're not mixing sync and async code incorrectly

2. **Mocks are not working as expected**
   - Verify that you're patching the correct path
   - Check that the mock is set up before the code under test is executed
   - Make sure you're asserting on the correct mock

3. **Tests are too slow**
   - Use parallel test execution with `run_parallel_tests.py`
   - Mark slow tests with `@pytest.mark.slow` and skip them during development
   - Optimize test fixtures to reduce setup time

4. **Tests are failing intermittently**
   - Check for test isolation issues
   - Look for race conditions in async tests
   - Verify that tests don't depend on external state

### Getting Help

If you're having trouble with tests, check these resources:

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- Ask for help in the team chat or create an issue