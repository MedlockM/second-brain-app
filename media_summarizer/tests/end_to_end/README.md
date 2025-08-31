# End-to-End Tests for Authentication & Payment Integration

This directory contains comprehensive End-to-End (E2E) tests that validate the complete user journey from authentication through payment processing to podcast summarization.

## Overview

The E2E tests ensure that all components of the system work together correctly, including:

- **Authentication System**: Magic link generation and JWT authentication
- **Stripe Payment Integration**: Credit purchases and transaction recording
- **Credit Management**: Credit allocation, usage, and tracking
- **Podcast Processing**: Complete workflow from submission to results
- **Email Notifications**: User communication throughout the process

## Test Files

### `test_auth_payment_e2e.py`

Focuses specifically on the authentication and payment integration:

- **`test_complete_auth_payment_workflow`**: Complete workflow from signup to credit purchase
- **`test_auth_payment_error_scenarios`**: Error handling for invalid auth/payment attempts
- **`test_concurrent_auth_payment_requests`**: Concurrent user signup and payment processing

### `test_complete_user_journey_e2e.py`

Tests the full user experience including podcast processing:

- **`test_complete_user_journey_new_user`**: New user signup → payment → podcast processing
- **`test_complete_user_journey_existing_user`**: Existing user with credits → direct processing
- **`test_insufficient_credits_scenario`**: Credit top-up workflow when user runs out

### `test_podcast_index_e2e.py` (Existing)

Original E2E test focusing on podcast processing workflow.

## Architecture & Dependencies

### Required Services

The E2E tests require the following services to be running:

1. **LocalStack** (for AWS services simulation):
   - DynamoDB (users, magic_links, transactions, podcasts tables)
   - SES (email notifications)
   - SQS (processing queues)
   - S3 (file storage)

2. **Stripe Test Environment**:
   - Test API keys configured
   - Payment intents and webhooks

### Test Environment Setup

The tests use mocked AWS services via LocalStack and Stripe test mode:

```python
# Environment variables required
ENVIRONMENT=test
USE_LOCALSTACK=true
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
JWT_SECRET_KEY=test_secret
```

## Running the Tests

### Option 1: Using Makefile (Recommended)

```bash
# Run all E2E tests
make test-e2e

# Run only auth/payment tests
make test-e2e-auth

# Run only complete journey tests
make test-e2e-journey

# Run existing podcast tests
make test-e2e-existing

# Setup E2E environment only
make setup-e2e

# Generate E2E coverage report
make coverage-e2e
```

### Option 2: Using pytest directly

```bash
# Run all E2E tests
pytest media_summarizer/tests/end_to_end/ -m e2e -v -s

# Run specific test file
pytest media_summarizer/tests/end_to_end/test_auth_payment_e2e.py -v -s

# Run specific test method
pytest media_summarizer/tests/end_to_end/test_auth_payment_e2e.py::TestAuthPaymentE2E::test_complete_auth_payment_workflow -v -s
```

### Option 3: Docker Compose for E2E

```bash
# Start optimized E2E environment
docker-compose -f docker-compose.e2e.yml --profile infrastructure up -d

# Run tests with containerized environment
docker-compose -f docker-compose.e2e.yml --profile test-runner up --abort-on-container-exit

# Cleanup E2E environment
docker-compose -f docker-compose.e2e.yml down -v
```

## Test Scenarios Covered

### 1. New User Complete Journey

**Flow**: Signup → Authenticate → Purchase Credits → Process Podcast → Receive Results

1. **Authentication Phase**:
   - Request magic link for new email
   - Extract token from database (simulating email click)
   - Authenticate and receive JWT token
   - Verify user created in database with 0 credits

2. **Payment Phase**:
   - Create payment intent for 50 credits (€5.00)
   - Simulate successful Stripe payment
   - Verify credits added to user account
   - Record transaction in database

3. **Processing Phase**:
   - Submit podcast for processing
   - Verify credits deducted (5 credits)
   - Simulate processing completion
   - Verify results stored in S3

4. **Notification Phase**:
   - Check email notification queued
   - Verify user can access results

### 2. Existing User with Credits

**Flow**: Authenticate → Process Podcast (no payment needed)

- User has sufficient credits
- Direct podcast processing
- Credit deduction and result generation

### 3. Insufficient Credits Scenario

**Flow**: Authenticate → Attempt Processing → Credit Purchase → Retry Processing

- User attempts processing with insufficient credits
- System handles insufficient credit scenario
- User purchases additional credits
- Processing completes successfully

### 4. Error Scenarios

- Unauthenticated payment attempts
- Invalid magic link tokens
- Invalid payment data
- Concurrent request handling

## Test Data & Fixtures

### Mock Data

```python
# Test user emails
test_email = f"e2e-test-{uuid.uuid4().hex[:8]}@example.com"

# Test podcast URLs
podcast_url = "https://example.com/test-podcast.mp3"

# Credit packages
credits_50 = {"credits": 50, "amount_cents": 500}  # €5.00
credits_100 = {"credits": 100, "amount_cents": 1000}  # €10.00
```

### Database Tables Created

- **users**: User accounts and credit balances
- **magic_links**: Authentication tokens
- **transactions**: Payment records
- **podcasts**: Processing jobs
- **episodes**: Podcast episode metadata

### S3 Buckets Created

- **transcripts**: Processed transcript files
- **summaries**: Generated summary files
- **media-files**: Original audio files

## Verification Points

### Authentication Verification

- ✅ Magic link generated and stored
- ✅ JWT token issued and valid
- ✅ User session established
- ✅ Invalid tokens rejected

### Payment Verification

- ✅ Payment intent created with correct amount
- ✅ Stripe integration working
- ✅ Credits added to user account
- ✅ Transaction recorded in database
- ✅ Payment history accessible

### Processing Verification

- ✅ Credits deducted for processing
- ✅ Podcast status updated throughout workflow
- ✅ Results stored in correct S3 locations
- ✅ Email notifications queued
- ✅ User can access final results

## Performance Considerations

### Test Duration

- **Individual tests**: 30-60 seconds each
- **Complete suite**: 5-10 minutes
- **Parallel execution**: Supported with separate test data

### Resource Usage

- **Memory**: ~500MB for LocalStack
- **CPU**: Moderate during processing simulation
- **Network**: Local only (no external API calls except Stripe test mode)

## Debugging & Troubleshooting

### Common Issues

1. **LocalStack not starting**:
   ```bash
   docker ps  # Check if container is running
   docker logs localstack-e2e  # Check logs
   ```

2. **Tests timing out**:
   - Increase timeouts in test configuration
   - Check LocalStack service health

3. **Stripe key issues**:
   - Verify test keys are configured
   - Check Stripe dashboard for test mode

4. **Database connection issues**:
   - Ensure DynamoDB tables are created
   - Check AWS credentials configuration

### Debugging Commands

```bash
# Check LocalStack health
curl http://localhost:4566/health

# List DynamoDB tables
aws --endpoint-url=http://localhost:4566 dynamodb list-tables

# Check SQS queues
aws --endpoint-url=http://localhost:4566 sqs list-queues

# View test logs
pytest --log-cli-level=DEBUG
```

### Test Output

Successful test run should show:

```
🎉 COMPLETE Auth + Payment E2E test completed successfully!
✅ User created: test@example.com
✅ Authentication successful
✅ Payment processed: €5.00 for 50 credits
✅ Credits added and used successfully
```

## Integration with CI/CD

### GitHub Actions

E2E tests are integrated into the CI/CD pipeline via `.github/workflows/e2e-tests.yml`:

```yaml
name: End-to-End Tests
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
  workflow_dispatch:
    inputs:
      test_scope:
        description: "Scope of E2E tests"
        type: choice
        options: [core, auth-payment, complete-journey, all]

jobs:
  e2e-auth-payment:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Auth & Payment E2E Tests
        run: |
          # Automated infrastructure setup
          # Docker Compose with LocalStack
          # Pytest execution with proper markers
```

### Test Markers

```bash
# Run only E2E tests
pytest -m e2e

# Skip E2E tests
pytest -m "not e2e"

# Run E2E tests requiring specific services
pytest -m "e2e and requires_stripe"
```

### CI/CD Features

- **Parallel Execution**: Auth/payment and user journey tests run in parallel
- **Automatic Infrastructure**: LocalStack and services auto-configured
- **Test Isolation**: Each job has isolated environment
- **Coverage Integration**: Results sent to Codecov
- **Artifact Collection**: Logs and results preserved on failure

## Future Enhancements

### CI/CD Best Practices Implemented

1. **Infrastructure as Code**: Docker Compose for reproducible environments
2. **Fast Feedback**: Parallel test execution and optimized containers
3. **Proper Isolation**: Each test run has clean environment
4. **Standard Tools**: Makefile, pytest, Docker - no custom scripts
5. **Comprehensive Reporting**: JUnit XML, coverage reports, artifacts

### Planned Improvements

1. **Visual Testing**: Screenshot comparison for UI workflows
2. **Performance Testing**: Load testing with multiple concurrent users
3. **Browser Testing**: Selenium-based frontend integration
4. **API Contract Testing**: Schema validation for all endpoints
5. **Chaos Testing**: Service failure simulation

### Additional Test Scenarios

1. **Payment Failures**: Failed credit card processing
2. **Service Outages**: AWS service unavailability
3. **Rate Limiting**: API rate limit handling
4. **Data Migration**: User data migration scenarios

## Contributing

When adding new E2E tests:

1. **Follow naming convention**: `test_*_e2e.py`
2. **Use proper markers**: `@pytest.mark.e2e` decorator
3. **Include comprehensive verification**: Database, API, file system checks
4. **Add appropriate cleanup**: Use fixtures for automatic cleanup
5. **Update CI/CD**: Add to `.github/workflows/e2e-tests.yml` if needed
6. **Document scenarios**: Update this README with new test scenarios
7. **Use standard tools**: Leverage Makefile and Docker Compose

### Development Workflow

```bash
# 1. Setup development environment
make setup-e2e

# 2. Write your E2E test
# File: media_summarizer/tests/end_to_end/test_your_feature_e2e.py

# 3. Test locally
make test-e2e-auth  # or appropriate target

# 4. Verify CI integration
git push  # Triggers GitHub Actions E2E pipeline

# 5. Cleanup
make docker-down
```

### Test Structure Template

```python
@pytest.mark.e2e
async def test_new_scenario_e2e(
    self,
    localstack_environment,
    test_client,
    stripe_client
):
    """Test description."""
    print("🚀 Starting test: New Scenario")
    
    # Setup
    # Test execution
    # Verification
    # Cleanup (handled by fixtures)
    
    print("🎉 Test completed successfully!")
```

### Infrastructure Integration

- **LocalStack**: Use `docker-compose.e2e.yml` for optimized testing
- **Initialization**: Scripts in `infrastructure/localstack/e2e-init/`
- **Environment**: Configure via Makefile or CI/CD variables
- **Monitoring**: Built-in health checks and logging
