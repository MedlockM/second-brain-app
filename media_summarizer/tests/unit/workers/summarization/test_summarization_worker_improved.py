"""
Improved tests for the summarization worker with better edge case coverage.
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
from tenacity import RetryError

# Sample data for tests
SAMPLE_TRANSCRIPTION_SHORT = """
This is a podcast about artificial intelligence. The host discusses the latest developments
in machine learning and neural networks. They interview a researcher who talks about their
work on natural language processing. The podcast concludes with a discussion about the
ethical implications of AI.
"""

SAMPLE_TRANSCRIPTION_LONG = """
This is a podcast about artificial intelligence. The host discusses the latest developments
in machine learning and neural networks. They interview a researcher who talks about their
work on natural language processing. The podcast concludes with a discussion about the
ethical implications of AI.
""" * 20  # Repeat to make it longer than the max chunk size

SAMPLE_TRANSCRIPTION_VERY_LONG = """
This is a podcast about artificial intelligence. The host discusses the latest developments
in machine learning and neural networks. They interview a researcher who talks about their
work on natural language processing. The podcast concludes with a discussion about the
ethical implications of AI.
""" * 100  # Very long transcription to test chunking limits

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
                "content": """```json
{
    "main_topics": ["Artificial Intelligence", "Machine Learning", "Neural Networks", "Natural Language Processing", "AI Ethics"],
    "key_points": [
        "Latest developments in machine learning and neural networks were discussed",
        "A researcher was interviewed about their work on natural language processing",
        "The ethical implications of AI were explored"
    ],
    "notable_quotes": ["Quote about AI from the researcher"],
    "conclusion": "The podcast emphasized the importance of considering ethical aspects when developing AI technologies."
}
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


class TestSummarizationWorkerImproved:
    """Improved tests for the SummarizationWorker class."""
    
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
    async def test_call_llm_api_server_error(self, worker):
        """Test handling of server errors from LLM API."""
        with patch("aiohttp.ClientSession") as mock_session:
            # Mock a server error response
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Internal Server Error")
            mock_response.__aenter__.return_value = mock_response
            
            mock_session_instance = MagicMock()
            mock_session_instance.post.return_value = mock_response
            mock_session_instance.__aenter__.return_value = mock_session_instance
            
            mock_session.return_value = mock_session_instance
            
            # Test that the server error is properly handled
            with pytest.raises(LLMAPIError) as excinfo:
                await worker._call_llm_api("Test prompt")
            
            assert "Internal Server Error" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_call_llm_api_connection_error(self, worker):
        """Test handling of connection errors."""
        with patch("aiohttp.ClientSession") as mock_session:
            # Mock a connection error
            mock_session_instance = MagicMock()
            mock_session_instance.post.side_effect = aiohttp.ClientError("Connection refused")
            mock_session_instance.__aenter__.return_value = mock_session_instance
            
            mock_session.return_value = mock_session_instance
            
            # Test that the connection error is properly handled
            with pytest.raises(LLMAPIError) as excinfo:
                await worker._call_llm_api("Test prompt")
            
            assert "Connection refused" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_call_llm_api_dns_error(self, worker):
        """Test handling of DNS resolution errors."""
        with patch("aiohttp.ClientSession") as mock_session:
            # Mock a DNS resolution error
            mock_session_instance = MagicMock()
            mock_session_instance.post.side_effect = aiohttp.ClientError("Name or service not known")
            mock_session_instance.__aenter__.return_value = mock_session_instance
            
            mock_session.return_value = mock_session_instance
            
            # Test that the DNS error is properly handled
            with pytest.raises(LLMAPIError) as excinfo:
                await worker._call_llm_api("Test prompt")
            
            assert "Name or service not known" in str(excinfo.value)
    
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
    async def test_generate_summary_with_very_long_text(self, worker, mock_aiohttp_session):
        """Test summary generation for very long text."""
        # Set a small chunk size to force many chunks
        worker.max_chunk_size = 50
        
        # Mock the _process_long_transcription method to avoid making too many API calls
        with patch.object(worker, "_process_long_transcription") as mock_process_long:
            mock_process_long.return_value = {
                "summary": {
                    "main_topics": ["Topic 1", "Topic 2"],
                    "key_points": ["Point 1", "Point 2"],
                    "notable_quotes": ["Quote 1"],
                    "conclusion": "Conclusion"
                },
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
                                "content": """```json
{
    "main_topics": ["Topic 1", "Topic 2"],
    "key_points": ["Point 1", "Point 2"],
    "notable_quotes": ["Quote 1"],
    "conclusion": "Conclusion"
}
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
            # Mock a response with missing required fields - use valid JSON without comments
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


class TestProcessMessageImproved:
    """Improved tests for the process_message function."""
    
    @pytest_asyncio.fixture
    async def mock_summarization_worker(self):
        """Create a mock for SummarizationWorker."""
        with patch("media_summarizer.workers.summarization.summarization_worker.SummarizationWorker") as mock_worker_class:
            mock_worker_instance = MagicMock()
            mock_worker_instance.generate_summary = AsyncMock(return_value={
                "summary": {
                    "main_topics": ["Topic 1", "Topic 2"],
                    "key_points": ["Point 1", "Point 2"],
                    "notable_quotes": ["Quote 1"],
                    "conclusion": "Conclusion text"
                },
                "metadata": {
                    "model": "gpt-4",
                    "usage": {"total_tokens": 150},
                    "chunked": False
                }
            })
            mock_worker_class.return_value = mock_worker_instance
            yield mock_worker_class
    
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
        
        assert "Transcription cannot be empty" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_process_message_with_very_long_transcription(self, mock_summarization_worker):
        """Test processing a very long transcription."""
        message = {
            "job_id": "job-123",
            "transcription_key": "transcription-123",
            "user_id": "user-123",
            "transcription": SAMPLE_TRANSCRIPTION_VERY_LONG
        }
        
        # Configure the mock to indicate chunking was used
        mock_worker_instance = mock_summarization_worker.return_value
        mock_worker_instance.generate_summary.return_value = {
            "summary": {
                "main_topics": ["Topic 1", "Topic 2"],
                "key_points": ["Point 1", "Point 2"],
                "notable_quotes": ["Quote 1"],
                "conclusion": "Conclusion text"
            },
            "metadata": {
                "model": "gpt-4",
                "usage": {"total_tokens": 1500},
                "chunked": True,
                "chunk_count": 100
            }
        }
        
        result = await process_message(
            message,
            llm_api_url="https://api.openai.com/v1/chat/completions",
            llm_api_key="test-api-key"
        )
        
        # Verify the result
        assert result["job_id"] == message["job_id"]
        assert result["user_id"] == message["user_id"]
        assert "summary" in result
        assert "metadata" in result
        assert result["metadata"]["chunked"]
        assert result["metadata"]["chunk_count"] == 100
    
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
    
    @pytest.mark.asyncio
    async def test_process_message_with_malformed_transcription(self, mock_summarization_worker):
        """Test handling of malformed transcription."""
        message = {
            "job_id": "job-123",
            "transcription_key": "transcription-123",
            "user_id": "user-123",
            "transcription": 12345  # Not a string
        }
        
        with pytest.raises(ValueError) as excinfo:
            await process_message(
                message,
                llm_api_url="https://api.openai.com/v1/chat/completions",
                llm_api_key="test-api-key"
            )
        
        assert "Transcription" in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_process_message_with_special_characters(self, mock_summarization_worker):
        """Test processing transcription with special characters."""
        message = {
            "job_id": "job-123",
            "transcription_key": "transcription-123",
            "user_id": "user-123",
            "transcription": "This is a transcription with special characters: !@#$%^&*()_+{}|:<>?[]\\;',./~`"
        }
        
        result = await process_message(
            message,
            llm_api_url="https://api.openai.com/v1/chat/completions",
            llm_api_key="test-api-key"
        )
        
        # Verify the result
        assert result["job_id"] == message["job_id"]
        assert result["user_id"] == message["user_id"]
        assert "summary" in result
        assert "metadata" in result
        
        # Verify that the worker was called with the correct transcription
        mock_worker_instance = mock_summarization_worker.return_value
        mock_worker_instance.generate_summary.assert_called_once_with(message["transcription"])
    
    @pytest.mark.asyncio
    async def test_process_message_with_unicode_characters(self, mock_summarization_worker):
        """Test processing transcription with unicode characters."""
        message = {
            "job_id": "job-123",
            "transcription_key": "transcription-123",
            "user_id": "user-123",
            "transcription": "This is a transcription with unicode characters: こんにちは世界"
        }
        
        result = await process_message(
            message,
            llm_api_url="https://api.openai.com/v1/chat/completions",
            llm_api_key="test-api-key"
        )
        
        # Verify the result
        assert result["job_id"] == message["job_id"]
        assert result["user_id"] == message["user_id"]
        assert "summary" in result
        assert "metadata" in result
        
        # Verify that the worker was called with the correct transcription
        mock_worker_instance = mock_summarization_worker.return_value
        mock_worker_instance.generate_summary.assert_called_once_with(message["transcription"])