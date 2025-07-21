# Integration Tests

This directory contains integration tests for the Media Summarizer application. These tests verify that different components of the system work together correctly.

## Testing Strategy

According to our testing strategy, integration tests should:

1. Test interactions between components
2. Use LocalStack as much as possible for real AWS service interactions rather than mocking
3. Use the Stripe library with test API keys for Stripe-related components

## Improved Integration Tests

We've created improved versions of the integration tests that follow these guidelines:

- `test_credit_management_workflow_improved.py`: Tests the credit management workflow using real LocalStack services and the Stripe API with test keys
- `test_podcast_submission_workflow_improved.py`: Tests the podcast submission workflow using real LocalStack services
- `test_transcription_summarization_workflow_improved.py`: Tests the transcription and summarization workflow using real LocalStack services

## Prerequisites

To run these tests, you need:

1. LocalStack running locally:
   ```bash
   docker run --rm -it -p 4566:4566 -p 4510-4559:4510-4559 localstack/localstack
   ```

2. A Stripe test API key in your `.env` file:
   ```
   STRIPE_TEST_API_KEY=sk_test_...
   ```

## Running the Tests

To run the integration tests:

```bash
# Activate the virtual environment
source .venv/bin/activate

# Run all integration tests
pytest media_summarizer/tests/integration/

# Run a specific integration test
pytest media_summarizer/tests/integration/workflows/test_credit_management_workflow_improved.py
```

## Test Structure

The integration tests use the `BaseIntegrationTestCase` class from `media_summarizer/tests/utils/base_test_classes.py`, which provides:

- Fixtures for creating real LocalStack clients (SQS, S3, SES)
- A fixture for creating a real Stripe client with the test API key
- Helper methods for common test operations

## Mocking vs. Real Services

While we aim to use real services as much as possible, some components still need to be mocked:

- **Whisper Model**: We mock the Whisper transcription model to avoid the computational overhead
- **Database**: We still use a mock database session to avoid setting up a test database
- **External APIs**: APIs other than AWS and Stripe are still mocked

## Future Improvements

To further improve the integration tests:

1. Set up a test PostgreSQL database for database integration tests
2. Use Docker Compose to start all required services for testing
3. Implement more comprehensive cleanup of test resources
4. Add more detailed assertions for the actual content of messages and files