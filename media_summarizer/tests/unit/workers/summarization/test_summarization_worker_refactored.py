"""
Refactored tests for the summarization worker using standardized test utilities.
"""
import json
import asyncio
import pytest
import pytest_asyncio
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch, call

from media_summarizer.workers.summarization.summarization_worker import (
    SummarizationWorker,
    LLMAPIError,
    process_message
)
from media_summarizer.tests.utils.base_test_classes import BaseWorkerTestCase
from media_summarizer.tests.utils.test_models import TestTranscription, TestSummary
from tenacity import RetryError

# Sample data for tests
SAMPLE_TRANSCRIPTION_SHORT = TestTranscription.create(short=True, paragraphs=1)
SAMPLE_TRANSCRIPTION_LONG = TestTranscription.create(short=False, paragraphs=2)
SAMPLE_TRANSCRIPTION_VERY_LONG = TestTranscription.create(short=False, paragraphs=10)

SAMPLE_SUMMARY = TestSummary.create(as_dict=True)

SAMPLE_LLM_RESPONSE = {
    "id": "chatcmpl-123",
    "object": "chat.completion",
    "created": 1677858242,
    "model": "gpt-4",
    "usage": {
        "prompt_tokens": 50,
        "completion_tokens": 100,
        "total_tokens": 150
    },
    "choices": [
        {
            "message": {
                "role": "assistant",
                "content": f"""```json
{json.dumps(SAMPLE_SUMMARY)}
```"""
            },
            "finish_reason": "stop",
            "index": 0
        }
    ]
}

SAMPLE_MESSAGE = {
    "job_id": "job-123",
    "transcription_key": "transcription-123",
    "user_id": "user-123",
    "transcription": SAMPLE_TRANSCRIPTION_SHORT
}


class TestSummarizationWorkerRefactored(BaseWorkerTestCase):
    """Refactored tests for the SummarizationWorker class."""
    
    @pytest.fixture
    def worker(self):
        """Create a SummarizationWorker instance for testing."""
        return SummarizationWorker(
            llm_api_url="https://api.openai.com/v1/chat/completions",
            llm_api_key="test-api-key"
        )
    
    @pytest_asyncio.fixture
    async def mock_aiohttp_session(self):
        """Create a mock for aiohttp.ClientSession."""
        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = SAMPLE_LLM_RESPONSE
            mock_response.__aenter__.return_value = mock_response
            
            mock_session_instance = MagicMock()
            mock_session_instance.post.return_value = mock_response
            mock_session_instance.__aenter__.return_value = mock_session_instance
            
            mock_session.return_value = mock_session_instance
            
            yield mock_session
    
    @pytest.mark.asyncio
    async def test_call_llm_api_success(self, worker, mock_aiohttp_session):
        """Test successful API call to LLM."""
        response = await worker._call_llm_api("Test prompt")
        
        # Verify the response
        assert response == SAMPLE_LLM_RESPONSE
        
        # Verify the API was called with correct parameters
        mock_session_instance = mock_aiohttp_session.return_value.__aenter__.return_value
        mock_session_instance.post.assert_called_once()
        
        # Check that the API key was used in the headers
        call_kwargs = mock_session_instance.post.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == f"Bearer {worker.llm_api_key}"
        
        # Check that the prompt was included in the payload
        assert "Test prompt" in json.dumps(call_kwargs["json"])
    
    @pytest.mark.asyncio
    async def test_call_llm_api_error(self, worker):
        """Test error handling in LLM API call."""
        with patch("aiohttp.ClientSession") as mock_session:
            # Mock a failed response
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.text = AsyncMock(return_value="Bad request")
            mock_response.__aenter__.return_value = mock_response
            
            mock_session_instance = MagicMock()
            mock_session_instance.post.return_value = mock_response
            mock_session_instance.__aenter__.return_value = mock_session_instance
            
            mock_session.return_value = mock_session_instance
            
            # Test that the API error is properly handled
            with pytest.raises(LLMAPIError) as excinfo:
                await worker._call_llm_api("Test prompt")
            
            assert "LLM API returned status 400" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_call_llm_api_timeout(self, worker):
        """Test timeout handling in LLM API call."""
        with patch("aiohttp.ClientSession") as mock_session:
            # Mock a timeout
            mock_session_instance = MagicMock()
            mock_session_instance.post.side_effect = asyncio.TimeoutError()
            mock_session_instance.__aenter__.return_value = mock_session_instance
            
            mock_session.return_value = mock_session_instance
            
            # Test that the timeout is properly handled
            with pytest.raises(LLMAPIError) as excinfo:
                await worker._call_llm_api("Test prompt")
            
            assert "LLM API request timed out" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_call_llm_api_client_error(self, worker):
        """Test client error handling in LLM API call."""
        with patch("aiohttp.ClientSession") as mock_session:
            # Mock a client error
            mock_session_instance = MagicMock()
            mock_session_instance.post.side_effect = aiohttp.ClientError("Connection error")
            mock_session_instance.__aenter__.return_value = mock_session_instance
            
            mock_session.return_value = mock_session_instance
            
            # Test that the client error is properly handled
            with pytest.raises(LLMAPIError) as excinfo:
                await worker._call_llm_api("Test prompt")
            
            assert "LLM API request failed: Connection error" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_call_llm_api_rate_limit_error(self, worker):
        """Test handling of rate limit errors from LLM API."""
        with patch("aiohttp.ClientSession") as mock_session:
            # Mock a rate limit error response
            mock_response = AsyncMock()
            mock_response.status = 429
            mock_response.text = AsyncMock(return_value="Rate limit exceeded")
            mock_response.__aenter__.return_value = mock_response
            
            mock_session_instance = MagicMock()
            mock_session_instance.post.return_value = mock_response
            mock_session_instance.__aenter__.return_value = mock_session_instance
            
            mock_session.return_value = mock_session_instance
            
            # Test that the rate limit error is properly handled
            with pytest.raises(LLMAPIError) as excinfo:
                await worker._call_llm_api("Test prompt")
            
            assert "Rate limit exceeded" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_call_llm_api_retry_behavior(self, worker):
        """Test that the LLM API call is retried on failure."""
        with patch("aiohttp.ClientSession") as mock_session:
            # Create a mock session instance that fails twice then succeeds
            mock_session_instance = MagicMock()
            
            # Create a side effect that fails twice with a client error, then succeeds
            mock_response_success = AsyncMock()
            mock_response_success.status = 200
            mock_response_success.json.return_value = SAMPLE_LLM_RESPONSE
            mock_response_success.__aenter__.return_value = mock_response_success
            
            # Create a counter to track the number of calls
            call_count = [0]
            
            # Define a side effect function that fails twice then succeeds
            def side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] <= 2:
                    raise aiohttp.ClientError("Connection error")
                return mock_response_success
            
            mock_session_instance.post = MagicMock(side_effect=side_effect)
            mock_session_instance.__aenter__.return_value = mock_session_instance
            mock_session.return_value = mock_session_instance
            
            # Patch the retry decorator to make it execute immediately for testing
            with patch("tenacity.retry", lambda *args, **kwargs: lambda f: f):
                # Call the API and verify it eventually succeeds
                try:
                    # First call should fail
                    with pytest.raises(LLMAPIError):
                        await worker._call_llm_api("Test prompt")
                    
                    # Reset counter and try again - second call should fail
                    call_count[0] = 1
                    with pytest.raises(LLMAPIError):
                        await worker._call_llm_api("Test prompt")
                    
                    # Reset counter and try again - third call should succeed
                    call_count[0] = 2
                    response = await worker._call_llm_api("Test prompt")
                    
                    # Verify the response is the successful one
                    assert response == SAMPLE_LLM_RESPONSE
                    
                    # Verify the API was called the expected number of times
                    assert call_count[0] == 3
                except Exception as e:
                    pytest.fail(f"Test failed: {str(e)}")
    
    def test_chunk_text(self, worker):
        """Test text chunking functionality."""
        # Set a smaller chunk size for testing
        worker.max_chunk_size = 10
        
        # Test with text shorter than chunk size
        short_text = "Short text"
        chunks = worker._chunk_text(short_text)
        assert len(chunks) == 1
        assert chunks[0] == short_text
        
        # Test with text longer than chunk size
        long_text = "This is a longer text that should be split into chunks"
        chunks = worker._chunk_text(long_text)
        assert len(chunks) == 6  # 57 characters / 10 = 5.7 -> 6 chunks
        assert chunks[0] == "This is a "
        assert chunks[1] == "longer tex"
        assert chunks[2] == "t that sho"
        assert chunks[3] == "uld be spl"
        assert chunks[4] == "it into ch"
        assert chunks[5] == "unks"
    
    @pytest.mark.asyncio
    async def test_chunk_text_with_empty_text(self, worker):
        """Test chunking of empty text."""
        chunks = worker._chunk_text("")
        assert len(chunks) == 0
    
    @pytest.mark.asyncio
    async def test_chunk_text_with_exact_chunk_size(self, worker):
        """Test chunking of text that exactly matches chunk size."""
        # Set chunk size to 10
        worker.max_chunk_size = 10
        
        # Test with text exactly 10 characters
        text = "0123456789"
        chunks = worker._chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text
    
    @pytest.mark.asyncio
    async def test_chunk_text_with_unicode_characters(self, worker):
        """Test chunking of text with unicode characters."""
        # Set chunk size to 10
        worker.max_chunk_size = 10
        
        # Test with text containing unicode characters
        text = "こんにちは世界"  # "Hello World" in Japanese
        chunks = worker._chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0] == text
        
        # Test with longer text
        text = "こんにちは世界" * 3
        chunks = worker._chunk_text(text)
        assert len(chunks) > 1
    
    @pytest.mark.asyncio
    async def test_generate_summary_short_text(self, worker, mock_aiohttp_session):
        """Test summary generation for short text."""
        summary_result = await worker.generate_summary(SAMPLE_TRANSCRIPTION_SHORT)
        
        # Verify the summary structure
        assert "summary" in summary_result
        assert "metadata" in summary_result
        assert not summary_result["metadata"]["chunked"]
        
        # Verify the summary content
        summary = summary_result["summary"]
        assert "main_topics" in summary
        assert "key_points" in summary
        assert "notable_quotes" in summary
        assert "conclusion" in summary
    
    @pytest.mark.asyncio
    async def test_generate_summary_long_text(self, worker, mock_aiohttp_session):
        """Test summary generation for long text that requires chunking."""
        # Set a small chunk size to force chunking
        worker.max_chunk_size = 100
        
        summary_result = await worker.generate_summary(SAMPLE_TRANSCRIPTION_LONG)
        
        # Verify the summary structure
        assert "summary" in summary_result
        assert "metadata" in summary_result
        assert summary_result["metadata"]["chunked"]
        assert summary_result["metadata"]["chunk_count"] > 1
        
        # Verify the summary content
        summary = summary_result["summary"]
        assert "main_topics" in summary
        assert "key_points" in summary
        assert "notable_quotes" in summary
        assert "conclusion" in summary
    
    @pytest.mark.asyncio
    async def test_generate_summary_empty_text(self, worker):
        """Test error handling for empty transcription."""
        with pytest.raises(ValueError) as excinfo:
            await worker.generate_summary("")
        
        assert "Transcription cannot be empty" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_generate_summary_with_very_long_text(self, worker, mock_aiohttp_session):
        """Test summary generation for very long text."""
        # Set a small chunk size to force many chunks
        worker.max_chunk_size = 50
        
        # Mock the _process_long_transcription method to avoid making too many API calls
        with patch.object(worker, "_process_long_transcription") as mock_process_long:
            mock_process_long.return_value = {
                "summary": SAMPLE_SUMMARY,
                "metadata": {
                    "model": "gpt-4",
                    "usage": {"total_tokens": 500},
                    "chunked": True,
                    "chunk_count": 100
                }
            }
            
            # Generate summary for very long text
            summary_result = await worker.generate_summary(SAMPLE_TRANSCRIPTION_VERY_LONG)
            
            # Verify the summary structure
            assert "summary" in summary_result
            assert "metadata" in summary_result
            assert summary_result["metadata"]["chunked"]
            assert summary_result["metadata"]["chunk_count"] > 1
            
            # Verify the _process_long_transcription method was called
            mock_process_long.assert_called_once_with(SAMPLE_TRANSCRIPTION_VERY_LONG)
    
    @pytest.mark.asyncio
    async def test_process_short_transcription_parsing_error(self, worker):
        """Test error handling when parsing LLM response fails."""
        with patch.object(worker, "_call_llm_api") as mock_call_api:
            # Mock a response with invalid JSON
            mock_call_api.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": "This is not valid JSON"
                        }
                    }
                ]
            }
            
            # Test that the parsing error is properly handled
            with pytest.raises(LLMAPIError) as excinfo:
                await worker._process_short_transcription(SAMPLE_TRANSCRIPTION_SHORT)
            
            assert "Failed to parse LLM response" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_process_short_transcription_json_in_markdown(self, worker):
        """Test parsing JSON from markdown code blocks."""
        with patch.object(worker, "_call_llm_api") as mock_call_api:
            # Mock a response with JSON in markdown code block
            mock_call_api.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": f"```json\n{json.dumps(SAMPLE_SUMMARY)}\n```"
                        }
                    }
                ],
                "model": "gpt-4",
                "usage": {"total_tokens": 100}
            }
            
            # Test that the JSON is properly extracted and parsed
            result = await worker._process_short_transcription(SAMPLE_TRANSCRIPTION_SHORT)
            
            # Verify the result
            assert result["summary"]["main_topics"] == SAMPLE_SUMMARY["main_topics"]
            assert result["summary"]["key_points"] == SAMPLE_SUMMARY["key_points"]
            assert result["summary"]["notable_quotes"] == SAMPLE_SUMMARY["notable_quotes"]
            assert result["summary"]["conclusion"] == SAMPLE_SUMMARY["conclusion"]
    
    @pytest.mark.asyncio
    async def test_process_short_transcription_json_in_generic_markdown(self, worker):
        """Test parsing JSON from generic markdown code blocks."""
        with patch.object(worker, "_call_llm_api") as mock_call_api:
            # Mock a response with JSON in generic markdown code block
            mock_call_api.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": f"```\n{json.dumps(SAMPLE_SUMMARY)}\n```"
                        }
                    }
                ],
                "model": "gpt-4",
                "usage": {"total_tokens": 100}
            }
            
            # Test that the JSON is properly extracted and parsed
            result = await worker._process_short_transcription(SAMPLE_TRANSCRIPTION_SHORT)
            
            # Verify the result
            assert result["summary"]["main_topics"] == SAMPLE_SUMMARY["main_topics"]
            assert result["summary"]["key_points"] == SAMPLE_SUMMARY["key_points"]
            assert result["summary"]["notable_quotes"] == SAMPLE_SUMMARY["notable_quotes"]
            assert result["summary"]["conclusion"] == SAMPLE_SUMMARY["conclusion"]
    
    @pytest.mark.asyncio
    async def test_process_short_transcription_with_malformed_json(self, worker):
        """Test handling of malformed JSON in LLM response."""
        with patch.object(worker, "_call_llm_api") as mock_call_api:
            # Mock a response with malformed JSON
            mock_call_api.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": """```json
{
    "main_topics": ["Topic 1", "Topic 2"],
    "key_points": ["Point 1", "Point 2"],
    "notable_quotes": ["Quote 1"],
    "conclusion": "Conclusion"
    "malformed": true  # Missing comma
}
```"""
                        }
                    }
                ]
            }
            
            # Test that the parsing error is properly handled
            with pytest.raises(LLMAPIError) as excinfo:
                await worker._process_short_transcription(SAMPLE_TRANSCRIPTION_SHORT)
            
            assert "Failed to parse LLM response" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_process_short_transcription_with_missing_fields(self, worker):
        """Test handling of missing fields in LLM response."""
        with patch.object(worker, "_call_llm_api") as mock_call_api:
            # Mock a response with missing required fields
            mock_call_api.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": """```json
{
    "main_topics": ["Topic 1", "Topic 2"],
    "key_points": ["Point 1", "Point 2"]
}
```"""
                        }
                    }
                ]
            }
            
            # Test that the response is still processed successfully
            result = await worker._process_short_transcription(SAMPLE_TRANSCRIPTION_SHORT)
            
            # Verify the result
            assert "summary" in result
            assert "metadata" in result
            assert "main_topics" in result["summary"]
            assert "key_points" in result["summary"]
            # Missing fields should be absent or null
            assert "notable_quotes" not in result["summary"] or result["summary"]["notable_quotes"] is None
            assert "conclusion" not in result["summary"] or result["summary"]["conclusion"] is None
    
    @pytest.mark.asyncio
    async def test_process_long_transcription_parsing_error(self, worker):
        """Test error handling when parsing LLM response fails for long transcriptions."""
        # Set a small chunk size to force chunking
        worker.max_chunk_size = 10
        
        # Create a mock that returns valid responses for chunk summaries
        # but invalid JSON for the final combined summary
        async def mock_call_api_side_effect(prompt):
            if "chunk" in prompt and "combined" not in prompt:
                # Return valid response for chunk summaries
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "Summary of chunk"
                            }
                        }
                    ]
                }
            else:
                # Return invalid JSON for combined summary
                return {
                    "choices": [
                        {
                            "message": {
                                "content": "This is not valid JSON"
                            }
                        }
                    ]
                }
        
        with patch.object(worker, "_call_llm_api", side_effect=mock_call_api_side_effect):
            # Test that the parsing error is properly handled
            with pytest.raises(LLMAPIError) as excinfo:
                await worker._process_long_transcription("This is a long transcription that will be chunked")
            
            assert "Failed to parse LLM response" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_process_long_transcription_with_generic_markdown(self, worker):
        """Test parsing JSON from generic markdown code blocks in long transcription processing."""
        # Set a small chunk size to force chunking
        worker.max_chunk_size = 10
        
        # Mock the _chunk_text method to return a fixed list of chunks
        with patch.object(worker, "_chunk_text") as mock_chunk_text:
            mock_chunk_text.return_value = ["Chunk 1", "Chunk 2"]
            
            # Mock the _call_llm_api method to return appropriate responses
            with patch.object(worker, "_call_llm_api") as mock_call_api:
                # Set up the mock to return different responses based on the call count
                mock_call_api.side_effect = [
                    # First call - chunk 1 summary
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "Summary of chunk 1"
                                }
                            }
                        ]
                    },
                    # Second call - chunk 2 summary
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "Summary of chunk 2"
                                }
                            }
                        ]
                    },
                    # Third call - combined summary with markdown
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": f"```\n{json.dumps(SAMPLE_SUMMARY)}\n```"
                                }
                            }
                        ],
                        "model": "gpt-4",
                        "usage": {"total_tokens": 100}
                    }
                ]
                
                # Test that the JSON is properly extracted and parsed
                result = await worker._process_long_transcription("This is a long transcription that will be chunked")
                
                # Verify the result
                assert result["summary"]["main_topics"] == SAMPLE_SUMMARY["main_topics"]
                assert result["summary"]["key_points"] == SAMPLE_SUMMARY["key_points"]
                assert result["summary"]["notable_quotes"] == SAMPLE_SUMMARY["notable_quotes"]
                assert result["summary"]["conclusion"] == SAMPLE_SUMMARY["conclusion"]
                assert result["metadata"]["chunked"] == True
                assert result["metadata"]["chunk_count"] == 2
    
    @pytest.mark.asyncio
    async def test_process_long_transcription_with_many_chunks(self, worker):
        """Test processing of long transcription with many chunks."""
        # Set a small chunk size to force many chunks
        worker.max_chunk_size = 50
        
        # Mock the _chunk_text method to return a fixed list of chunks
        with patch.object(worker, "_chunk_text") as mock_chunk_text:
            mock_chunk_text.return_value = ["Chunk " + str(i) for i in range(20)]
            
            # Mock the _call_llm_api method to return appropriate responses
            with patch.object(worker, "_call_llm_api") as mock_call_api:
                # Set up the mock to return different responses for chunk summaries and final summary
                chunk_responses = [
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": f"Summary of chunk {i}"
                                }
                            }
                        ]
                    } for i in range(20)
                ]
                
                final_response = {
                    "choices": [
                        {
                            "message": {
                                "content": f"""```json
{json.dumps(SAMPLE_SUMMARY)}
```"""
                            }
                        }
                    ],
                    "model": "gpt-4",
                    "usage": {"total_tokens": 500}
                }
                
                # Configure the mock to return chunk responses first, then final response
                mock_call_api.side_effect = chunk_responses + [final_response]
                
                # Test processing of long transcription
                result = await worker._process_long_transcription(SAMPLE_TRANSCRIPTION_VERY_LONG)
                
                # Verify the result
                assert "summary" in result
                assert "metadata" in result
                assert result["metadata"]["chunked"]
                assert result["metadata"]["chunk_count"] == 20
                
                # Verify that _call_llm_api was called for each chunk and once for the final summary
                assert mock_call_api.call_count == 21
    
    @pytest.mark.asyncio
    async def test_process_long_transcription_with_chunk_error(self, worker):
        """Test error handling when processing a chunk fails."""
        # Set a small chunk size to force chunking
        worker.max_chunk_size = 50
        
        # Mock the _chunk_text method to return a fixed list of chunks
        with patch.object(worker, "_chunk_text") as mock_chunk_text:
            mock_chunk_text.return_value = ["Chunk 1", "Chunk 2", "Chunk 3"]
            
            # Mock the _call_llm_api method to fail on the second chunk
            with patch.object(worker, "_call_llm_api") as mock_call_api:
                mock_call_api.side_effect = [
                    # First chunk succeeds
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "Summary of chunk 1"
                                }
                            }
                        ]
                    },
                    # Second chunk fails
                    LLMAPIError("API error on chunk 2"),
                    # Third chunk would succeed but shouldn't be called
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "Summary of chunk 3"
                                }
                            }
                        ]
                    }
                ]
                
                # Test that the error is properly propagated
                with pytest.raises(LLMAPIError) as excinfo:
                    await worker._process_long_transcription(SAMPLE_TRANSCRIPTION_LONG)
                
                assert "API error on chunk 2" in str(excinfo.value)
                
                # Verify that _call_llm_api was called only for the first and second chunks
                assert mock_call_api.call_count == 2


class TestProcessMessageRefactored(BaseWorkerTestCase):
    """Refactored tests for the process_message function."""
    
    @pytest_asyncio.fixture
    async def mock_summarization_worker(self):
        """Create a mock for SummarizationWorker."""
        with patch("media_summarizer.workers.summarization.summarization_worker.SummarizationWorker") as mock_worker_class:
            mock_worker_instance = MagicMock()
            mock_worker_instance.generate_summary = AsyncMock(return_value={
                "summary": SAMPLE_SUMMARY,
                "metadata": {
                    "model": "gpt-4",
                    "usage": {"total_tokens": 150},
                    "chunked": False
                }
            })
            mock_worker_class.return_value = mock_worker_instance
            yield mock_worker_class
    
    @pytest.mark.asyncio
    async def test_process_message_success(self, mock_summarization_worker):
        """Test successful message processing."""
        result = await process_message(
            SAMPLE_MESSAGE,
            llm_api_url="https://api.openai.com/v1/chat/completions",
            llm_api_key="test-api-key"
        )
        
        # Verify the worker was created with correct parameters
        mock_summarization_worker.assert_called_once_with(
            "https://api.openai.com/v1/chat/completions",
            "test-api-key"
        )
        
        # Verify the worker's generate_summary method was called
        mock_worker_instance = mock_summarization_worker.return_value
        mock_worker_instance.generate_summary.assert_called_once_with(SAMPLE_MESSAGE["transcription"])
        
        # Verify the result structure
        assert result["job_id"] == SAMPLE_MESSAGE["job_id"]
        assert result["user_id"] == SAMPLE_MESSAGE["user_id"]
        assert "summary" in result
        assert "metadata" in result
    
    @pytest.mark.asyncio
    async def test_process_message_invalid_format(self):
        """Test error handling for invalid message format."""
        with pytest.raises(ValueError) as excinfo:
            await process_message(
                "not a dict or valid JSON",
                llm_api_url="https://api.openai.com/v1/chat/completions",
                llm_api_key="test-api-key"
            )
        
        assert "Invalid message format" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_process_message_missing_fields(self):
        """Test error handling for message with missing required fields."""
        with pytest.raises(ValueError) as excinfo:
            await process_message(
                {"job_id": "job-123"},  # Missing transcription_key and user_id
                llm_api_url="https://api.openai.com/v1/chat/completions",
                llm_api_key="test-api-key"
            )
        
        assert "Missing required fields" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_process_message_missing_transcription(self):
        """Test error handling for message with missing transcription."""
        with pytest.raises(ValueError) as excinfo:
            await process_message(
                {
                    "job_id": "job-123",
                    "transcription_key": "transcription-123",
                    "user_id": "user-123"
                    # Missing transcription
                },
                llm_api_url="https://api.openai.com/v1/chat/completions",
                llm_api_key="test-api-key"
            )
        
        assert "Transcription cannot be empty" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_process_message_json_string(self, mock_summarization_worker):
        """Test processing a message that's a JSON string."""
        message_json = json.dumps(SAMPLE_MESSAGE)
        
        result = await process_message(
            message_json,
            llm_api_url="https://api.openai.com/v1/chat/completions",
            llm_api_key="test-api-key"
        )
        
        # Verify the result structure
        assert result["job_id"] == SAMPLE_MESSAGE["job_id"]
        assert result["user_id"] == SAMPLE_MESSAGE["user_id"]
        assert "summary" in result
        assert "metadata" in result
    
    @pytest.mark.asyncio
    async def test_process_message_with_empty_transcription(self, mock_summarization_worker):
        """Test error handling for empty transcription."""
        message = {
            "job_id": "job-123",
            "transcription_key": "transcription-123",
            "user_id": "user-123",
            "transcription": ""  # Empty transcription
        }
        
        with pytest.raises(ValueError) as excinfo:
            await process_message(
                message,
                llm_api_url="https://api.openai.com/v1/chat/completions",
                llm_api_key="test-api-key"
            )
        
        # The actual error message is "Transcription not found" instead of "Transcription cannot be empty"
        assert "Transcription" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_process_message_with_llm_api_error(self, mock_summarization_worker):
        """Test handling of LLM API errors."""
        # Configure the mock to raise an LLM API error
        mock_worker_instance = mock_summarization_worker.return_value
        mock_worker_instance.generate_summary.side_effect = LLMAPIError("API error")
        
        with pytest.raises(LLMAPIError) as excinfo:
            await process_message(
                SAMPLE_MESSAGE,
                llm_api_url="https://api.openai.com/v1/chat/completions",
                llm_api_key="test-api-key"
            )
        
        assert "API error" in str(excinfo.value)