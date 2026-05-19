"""
End-to-end tests for the Media Summarizer application.

This package contains tests that verify complete user workflows and system behavior
from start to finish, using real services and minimal mocking to ensure the entire
system works correctly in production-like conditions.

Test Categories:
- Complete podcast processing workflows (submission to email delivery)
- User journey tests (API interactions, credit management, job tracking)
- System integration tests (all services working together)

Requirements:
- All external services must be running (LocalStack, Docker Whisper, etc.)
- Tests use real AWS services via LocalStack
- Tests use real Docker Whisper service
- Minimal mocking, focused on external dependencies only

Test Markers:
- @pytest.mark.e2e: Marks test as end-to-end
- @pytest.mark.requires_all_services: Requires all external services
- @pytest.mark.slow: Long-running tests
"""
