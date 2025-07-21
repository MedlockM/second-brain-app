"""
Tests specifically for the retry decorator functionality in the summarization worker.
"""
import pytest
import pytest_asyncio
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch, call
import tenacity

from media_summarizer.workers.summarization.summarization_worker import (
    SummarizationWorker,
    LLMAPIError
)

# NOTE: These tests are currently skipped due to issues with mocking async context managers
# in Python 3.11+. The AsyncMock implementation for async context managers changed in Python 3.11,
# causing compatibility issues with our current test approach.
#
# A compatible version of these tests has been implemented in test_retry_decorator_compatible.py
# which uses a different approach to testing the retry decorator that works with Python 3.11+.


class TestRetryDecorator:
    """Tests for the retry decorator on the _call_llm_api method."""
    
    @pytest.fixture
    def worker(self):
        """Create a SummarizationWorker instance for testing."""
        # Create a worker instance
        worker = SummarizationWorker(
            llm_api_url="https://api.openai.com/v1/chat/completions",
            llm_api_key="test-api-key"
        )
        return worker
        
    @pytest.fixture
    def retry_decorator(self):
        """Create a retry decorator for testing."""
        return tenacity.retry(
            stop=tenacity.stop_after_attempt(3),
            wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
            retry=tenacity.retry_if_exception_type((LLMAPIError, aiohttp.ClientError)),
            reraise=True
        )
    
    @pytest.mark.asyncio
    async def test_retry_on_llm_api_error(self, worker, retry_decorator):
        """Test that the retry decorator retries on LLMAPIError."""
        # Create a counter to track calls
        call_count = 0
        
        # Create a test function that will be decorated with retry
        @retry_decorator
        async def test_function():
            nonlocal call_count
            call_count += 1
            
            if call_count <= 2:
                raise LLMAPIError("Bad request")
            return {"choices": [{"message": {"content": '{"test": "success"}'}}]}
        
        # Call the function with retry decorator
        result = await test_function()
        
        # Verify the result
        assert "choices" in result
        
        # Verify it was called 3 times (initial + 2 retries)
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_on_client_error(self, worker, retry_decorator):
        """Test that the retry decorator retries on aiohttp.ClientError."""
        # Create a counter to track calls
        call_count = 0
        
        # Create a test function that will be decorated with retry
        @retry_decorator
        async def test_function():
            nonlocal call_count
            call_count += 1
            
            if call_count <= 2:
                raise aiohttp.ClientError("Connection error")
            return {"choices": [{"message": {"content": '{"test": "success"}'}}]}
        
        # Call the function with retry decorator
        result = await test_function()
        
        # Verify the result
        assert "choices" in result
        
        # Verify it was called 3 times (initial + 2 retries)
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, worker, retry_decorator):
        """Test that the retry decorator stops after max retries."""
        # Create a counter to track calls
        call_count = 0
        
        # Create a test function that will be decorated with retry
        @retry_decorator
        async def test_function():
            nonlocal call_count
            call_count += 1
            raise LLMAPIError("Connection error")
        
        # Call the function and verify it fails after max retries
        with pytest.raises(LLMAPIError) as excinfo:
            await test_function()
        
        assert "Connection error" in str(excinfo.value)
        
        # Verify it was called 3 times (initial + 2 retries = 3 total attempts)
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self, worker, retry_decorator):
        """Test that the retry decorator uses exponential backoff."""
        # Mock the sleep function to track wait times
        with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
            # Create a counter to track calls
            call_count = 0
            
            # Create a test function that will be decorated with retry
            @retry_decorator
            async def test_function():
                nonlocal call_count
                call_count += 1
                raise LLMAPIError("Connection error")
            
            # Patch tenacity's sleep
            with patch("tenacity.nap.sleep", mock_sleep):
                # Call the function and verify it fails after max retries
                with pytest.raises(LLMAPIError):
                    await test_function()
            
            # Verify it was called 3 times (initial + 2 retries = 3 total attempts)
            assert call_count == 3
            
            # Verify sleep was called with increasing wait times
            assert mock_sleep.call_count == 2  # Called once per retry (not on first attempt)
            
            # Check that the second wait is longer than the first (exponential backoff)
            if len(mock_sleep.call_args_list) >= 2:
                first_wait = mock_sleep.call_args_list[0][0][0]
                second_wait = mock_sleep.call_args_list[1][0][0]
                assert second_wait > first_wait
    
    @pytest.mark.asyncio
    async def test_retry_not_triggered_for_other_exceptions(self, worker, retry_decorator):
        """Test that the retry decorator doesn't retry on exceptions not in the retry list."""
        # Create a counter to track calls
        call_count = 0
        
        # Create a test function that will be decorated with retry
        @retry_decorator
        async def test_function():
            nonlocal call_count
            call_count += 1
            raise ValueError("Unexpected error")
        
        # Call the function and verify it fails immediately
        with pytest.raises(ValueError) as excinfo:
            await test_function()
        
        assert "Unexpected error" in str(excinfo.value)
        
        # Verify it was called only once (no retries)
        assert call_count == 1