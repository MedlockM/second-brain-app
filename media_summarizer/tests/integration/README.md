# Integration Tests

This directory contains integration tests for the Media Summarizer application. These tests verify that different components of the system work together correctly.

## Testing Strategy

According to our testing strategy, integration tests should:

1. Test interactions between components
2. Use LocalStack as much as possible for real AWS service interactions rather than mocking
3. Use the Stripe library with test API keys for Stripe-related components
4. Use HTTP async server using httpx (not custom HTTP servers)
5. Use Whisper model from docker-compose.dev.yml (real Docker service, not mocked)
6. Mock LLM API calls with OpenAI interface
7. Test complete workflows or significant parts of workflows
8. Minimize mock objects and use real service implementations where possible

## Test Files

### Integration Tests (Strategy Compliant)
- `test_credit_management_workflow.py`: Tests credit management with real database, real Stripe API, real LocalStack services, and httpx async server
- `test_podcast_submission_workflow.py`: Tests complete podcast workflow with httpx async server, real LocalStack services, real Docker Whisper service
- `test_transcription_summarization_workflow.py`: Tests transcription/summarization with real Docker Whisper service, httpx async server, real S3/SQS interactions
- `test_podcast_workflow_components.py`: Tests individual workflow components with real Docker Whisper service and httpx async server

All test files now follow the integration testing strategy requirements with real service interactions and proper technology choices.

## Key Improvements in New Tests

### 1. Real Service Interactions
- **LocalStack Services**: All AWS services (S3, SQS, SES, DynamoDB) use real LocalStack instances
- **HTTPx Async Server**: Uses httpx-based async HTTP server for RSS feeds and audio downloads (as specified in strategy)
- **Real Docker Whisper Service**: Uses actual Whisper service running in docker-compose.dev.yml (as specified in strategy)
- **Real Database**: Uses real database connections (SQLite for testing, can be PostgreSQL)
- **Real Stripe API**: Uses actual Stripe test API with test keys

### 2. Minimal Mocking
- **Only Mock LLM API**: LLM API calls are mocked using OpenAI interface (as specified in strategy)
- **Real Whisper Service**: Uses actual Docker Whisper service from docker-compose.dev.yml (no mocking)
- **No AWS Service Mocks**: All AWS interactions use LocalStack
- **No Database Mocks**: Uses real database sessions and transactions
- **HTTPx Async Server**: Uses real httpx async server for RSS/audio content (as specified in strategy)

### 3. Complete Workflow Testing
- **End-to-End Tests**: Test complete workflows from API to email notification
- **Real File Operations**: Actual file uploads/downloads with S3
- **Real Message Passing**: Actual SQS message sending and receiving
- **Real Transcription**: Actual Whisper transcription using Docker service
- **HTTPx Async Requests**: Real HTTP requests using httpx async client
- **Real Error Handling**: Tests error propagation through real services

## Prerequisites

To run these tests, you need:

1. **Docker services running** (includes LocalStack, Whisper, and other services):
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

2. **Stripe test API key** in your `.env` file:
   ```
   STRIPE_TEST_API_KEY=sk_test_...
   ```

3. **Python environment** with all dependencies:
   ```bash
   source .venv/bin/activate
   uv pip install -e ".[dev]"
   ```

4. **Verify Whisper Docker service** is running:
   ```bash
   docker ps | grep whisper
   ```

## Running the Tests

### Run Integration Tests
```bash
# Run all integration tests
pytest media_summarizer/tests/integration/workflows/ -v

# Run specific test
pytest media_summarizer/tests/integration/workflows/test_podcast_submission_workflow.py -v

# Run with detailed output
pytest media_summarizer/tests/integration/workflows/test_credit_management_workflow.py -v -s
```

### Run All Integration Tests
```bash
# Run all integration tests
pytest media_summarizer/tests/integration/ -v

# Run with coverage
pytest media_summarizer/tests/integration/ --cov=media_summarizer --cov-report=html
```

## Test Structure

The improved integration tests use:

- **BaseIntegrationTestCase**: Provides real LocalStack clients, real Whisper client, and httpx server fixtures
- **Real Service Fixtures**: LocalStack SQS, S3, SES, DynamoDB clients, real Docker Whisper client, httpx async server
- **Test Utilities**: Helper functions for verifying real service interactions
- **Strategy Compliance**: Uses real Docker Whisper service and httpx async server as specified

## What Makes These "True" Integration Tests

### ✅ Good Integration Test Practices (Strategy Compliant)
- Tests actual component interactions
- Uses real services (LocalStack for AWS, real Stripe API, real Docker Whisper)
- Uses httpx async server for HTTP requests (as specified in strategy)
- Uses real Whisper service from docker-compose.dev.yml (as specified in strategy)
- Tests complete workflows end-to-end
- Verifies actual file uploads, message passing, database transactions, real transcription
- Tests error handling with real service failures

### ❌ Anti-Patterns Avoided
- Excessive mocking of internal services
- Mocking Whisper service instead of using real Docker service
- Using custom HTTP servers instead of httpx async server
- Testing components in isolation (that's for unit tests)
- Mocking AWS services instead of using LocalStack
- Not testing actual data flow between components
- Ignoring error handling and edge cases

## Debugging Integration Tests

### LocalStack Issues
```bash
# Check LocalStack status
curl http://localhost:4566/health

# View LocalStack logs
docker-compose -f docker-compose.dev.yml logs localstack
```

### Whisper Docker Service Issues
```bash
# Check if Whisper container is running
docker ps | grep whisper

# View Whisper service logs
docker-compose -f docker-compose.dev.yml logs whisper

# Test Whisper service connectivity
python -c "from media_summarizer.tests.utils.real_whisper_client import test_whisper_connection; print(test_whisper_connection())"
```

### Test Debugging
```bash
# Run with verbose output
pytest -v -s media_summarizer/tests/integration/workflows/test_podcast_submission_workflow.py::TestPodcastSubmissionWorkflowFocused::test_api_to_sqs_integration_with_httpx_server

# Run with pdb debugger
pytest --pdb media_summarizer/tests/integration/workflows/test_credit_management_workflow.py

# Test specific integration with real services
pytest -v -s media_summarizer/tests/integration/workflows/test_transcription_summarization_workflow.py::TestTranscriptionSummarizationWorkflowReal::test_transcription_worker_with_real_s3_and_sqs
```

## Future Improvements

1. **Real PostgreSQL Database**: Replace SQLite with containerized PostgreSQL for database tests
2. **Automated Service Health Checks**: Wait for all Docker services to be ready before running tests
3. **Performance Optimization**: Parallel test execution and resource cleanup
4. **More Comprehensive Assertions**: Verify actual file contents, message formats, email content, transcription quality
5. **Load Testing**: Test system behavior under concurrent requests
6. **Real Audio File Testing**: Use actual audio files for more realistic Whisper transcription testing