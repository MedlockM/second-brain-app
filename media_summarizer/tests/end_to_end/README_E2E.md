# End-to-End Tests

This directory contains end-to-end tests for the Media Summarizer application.

## Current Tests

### Manual Episode Submission (`test_manual_episode_submission.py`)

Tests the complete user journey for manually submitting an episode:
- User registration and email verification
- Login and authentication  
- Podcast search via Podcast Index API
- Episode selection (duration < 2 minutes for fast testing)
- Episode submission for processing
- Full processing pipeline: download → transcription → summarization → notification
- Job status polling until completion

## Running Tests

### Using pytest directly

```bash
# Run all E2E tests
pytest media_summarizer/tests/end_to_end/ -v -m e2e

# Run specific test
pytest media_summarizer/tests/end_to_end/test_manual_episode_submission.py -v

# Run without coverage
pytest media_summarizer/tests/end_to_end/test_manual_episode_submission.py -v --override-ini "addopts="
```

### Using the helper script

```bash
# Simple wrapper that runs the test with appropriate settings
python scripts/run_e2e_manual.py

# Or with uv
uv run python scripts/run_e2e_manual.py
```

## Requirements

### Services
- Docker services running:
  - LocalStack (for AWS services: S3, SQS, DynamoDB, SES)
  - Workers (download, transcription, summarization, email, episode-events)
  - Whisper (for transcription)
  - API server

```bash
# Start all services
docker-compose -f docker-compose.dev.yml --profile full up -d
```

### Environment Variables

Required:
- `PODCASTINDEXORG_API_KEY` - Podcast Index API key
- `PODCASTINDEXORG_API_SECRET` - Podcast Index API secret
- `OPENAI_API_KEY` - OpenAI API key for summarization

Optional:
- `E2E_JOB_TIMEOUT_SECONDS` - Max time to wait for job completion (default: 900)
- `E2E_JOB_POLL_SECONDS` - Polling interval for job status (default: 5)

## Test Configuration

Tests use pytest markers:
- `@pytest.mark.e2e` - Marks test as end-to-end
- `@pytest.mark.requires_all_services` - Requires all services running
- `@pytest.mark.asyncio` - Async test support

## Notes

- Tests automatically clean the `episode_idempotence` table before running
- Tests use short episodes (< 2 minutes) to minimize processing time
- Each test run creates a new test user with seeded minutes
- Tests poll job status every 5 seconds (configurable) until completion or timeout

## Troubleshooting

### Test fails with "Could not connect to endpoint"
Make sure LocalStack and all services are running:
```bash
docker-compose -f docker-compose.dev.yml ps
```

### Test times out
- Check worker logs for errors
- Increase `E2E_JOB_TIMEOUT_SECONDS` if needed
- Verify OpenAI API key is valid

### Email verification issues
This is expected in LocalStack. The test still validates the core flow.
