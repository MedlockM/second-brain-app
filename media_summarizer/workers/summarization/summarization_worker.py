"""
Summarization worker for processing transcriptions and generating summaries using LLM.
"""
import json
import logging
from typing import Dict, Any, Optional, List

import aiohttp
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class LLMAPIError(Exception):
    """Exception raised when there's an error with the LLM API."""
    pass

class SummarizationWorker:
    """Worker for generating summaries from transcriptions using LLM."""
    
    def __init__(self, llm_api_url: str, llm_api_key: str):
        """
        Initialize the summarization worker.
        
        Args:
            llm_api_url: URL of the LLM API
            llm_api_key: API key for the LLM API
        """
        self.llm_api_url = llm_api_url
        self.llm_api_key = llm_api_key
        self.max_chunk_size = 4000  # Maximum size of text chunk to send to LLM
        self.max_retries = 3
    
    # For testing purposes, we'll make this configurable
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=lambda e: isinstance(e, (LLMAPIError, aiohttp.ClientError)),
        reraise=True
    )
    async def _call_llm_api(self, prompt: str) -> Dict[str, Any]:
        """
        Call the LLM API with the given prompt.
        
        Args:
            prompt: The prompt to send to the LLM API
            
        Returns:
            The response from the LLM API
            
        Raises:
            LLMAPIError: If there's an error with the LLM API after retries
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.llm_api_key}"
        }
        
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that summarizes podcast transcriptions."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1000
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.llm_api_url,
                    headers=headers,
                    json=payload,
                    timeout=60
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"LLM API error: {response.status} - {error_text}")
                        raise LLMAPIError(f"LLM API returned status {response.status}: {error_text}")
                    
                    return await response.json()
        except asyncio.TimeoutError:
            logger.error("LLM API request timed out")
            raise LLMAPIError("LLM API request timed out")
        except aiohttp.ClientError as e:
            logger.error(f"LLM API request failed: {str(e)}")
            raise LLMAPIError(f"LLM API request failed: {str(e)}")
    
    def _chunk_text(self, text: str) -> List[str]:
        """
        Split the text into chunks of maximum size.
        
        Args:
            text: The text to split
            
        Returns:
            List of text chunks
        """
        # Simple chunking by character count
        # In a real implementation, we would use more sophisticated chunking
        # that respects sentence or paragraph boundaries
        chunks = []
        for i in range(0, len(text), self.max_chunk_size):
            chunks.append(text[i:i + self.max_chunk_size])
        return chunks
    
    async def generate_summary(self, transcription: str) -> Dict[str, Any]:
        """
        Generate a summary from the given transcription.
        
        Args:
            transcription: The transcription text to summarize
            
        Returns:
            Dictionary containing the summary and metadata
            
        Raises:
            LLMAPIError: If there's an error with the LLM API
        """
        if not transcription:
            raise ValueError("Transcription cannot be empty")
        
        # For very long transcriptions, we need to chunk the text
        if len(transcription) > self.max_chunk_size:
            return await self._process_long_transcription(transcription)
        
        # For shorter transcriptions, we can process directly
        return await self._process_short_transcription(transcription)
    
    async def _process_short_transcription(self, transcription: str) -> Dict[str, Any]:
        """
        Process a short transcription that fits within the token limit.
        
        Args:
            transcription: The transcription text to summarize
            
        Returns:
            Dictionary containing the summary and metadata
        """
        prompt = f"""
        Please summarize the following podcast transcription:
        
        {transcription}
        
        Provide a structured summary with the following sections:
        1. Main topics
        2. Key points
        3. Notable quotes
        4. Conclusion
        
        Format your response as JSON with these sections as keys.
        """
        
        response = await self._call_llm_api(prompt)
        
        try:
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            # Extract JSON from the content (it might be wrapped in markdown code blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            summary_data = json.loads(content)
            
            return {
                "summary": summary_data,
                "metadata": {
                    "model": response.get("model", "unknown"),
                    "usage": response.get("usage", {}),
                    "chunked": False
                }
            }
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logger.error(f"Failed to parse LLM response: {str(e)}")
            raise LLMAPIError(f"Failed to parse LLM response: {str(e)}")
    
    async def _process_long_transcription(self, transcription: str) -> Dict[str, Any]:
        """
        Process a long transcription by chunking it and then combining the results.
        
        Args:
            transcription: The transcription text to summarize
            
        Returns:
            Dictionary containing the summary and metadata
        """
        chunks = self._chunk_text(transcription)
        logger.info(f"Processing long transcription in {len(chunks)} chunks")
        
        # First, summarize each chunk
        chunk_summaries = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)}")
            prompt = f"""
            Please summarize the following chunk ({i+1}/{len(chunks)}) of a podcast transcription:
            
            {chunk}
            
            Provide a brief summary of the main points in this chunk.
            """
            
            response = await self._call_llm_api(prompt)
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            chunk_summaries.append(content)
        
        # Then, combine the chunk summaries
        combined_summary = "\n\n".join([f"Chunk {i+1}: {summary}" for i, summary in enumerate(chunk_summaries)])
        
        # Finally, create a structured summary from the combined summaries
        prompt = f"""
        Below are summaries of different chunks of a podcast transcription:
        
        {combined_summary}
        
        Based on these summaries, provide a structured summary of the entire podcast with the following sections:
        1. Main topics
        2. Key points
        3. Notable quotes (if any were mentioned in the summaries)
        4. Conclusion
        
        Format your response as JSON with these sections as keys.
        """
        
        response = await self._call_llm_api(prompt)
        
        try:
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            # Extract JSON from the content (it might be wrapped in markdown code blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            summary_data = json.loads(content)
            
            return {
                "summary": summary_data,
                "metadata": {
                    "model": response.get("model", "unknown"),
                    "usage": response.get("usage", {}),
                    "chunked": True,
                    "chunk_count": len(chunks)
                }
            }
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logger.error(f"Failed to parse LLM response: {str(e)}")
            raise LLMAPIError(f"Failed to parse LLM response: {str(e)}")

async def process_message(message: Dict[str, Any], 
                         llm_api_url: str, 
                         llm_api_key: str) -> Dict[str, Any]:
    """
    Process a message from the queue.
    
    Args:
        message: The message from the queue
        llm_api_url: URL of the LLM API
        llm_api_key: API key for the LLM API
        
    Returns:
        Dictionary containing the processing result
        
    Raises:
        ValueError: If the message is invalid
        LLMAPIError: If there's an error with the LLM API
    """
    if not isinstance(message, dict):
        try:
            message = json.loads(message)
        except (TypeError, json.JSONDecodeError):
            raise ValueError("Invalid message format")
    
    job_id = message.get("job_id")
    transcription_key = message.get("transcription_key")
    user_id = message.get("user_id")
    
    if not job_id or not transcription_key or not user_id:
        raise ValueError("Missing required fields in message")
    
    # In a real implementation, we would fetch the transcription from S3
    # For now, we'll assume the transcription is in the message
    transcription = message.get("transcription", "")
    
    if not transcription:
        raise ValueError("Transcription cannot be empty")
        
    if not isinstance(transcription, str):
        raise ValueError("Transcription must be a string")
    
    worker = SummarizationWorker(llm_api_url, llm_api_key)
    summary_result = await worker.generate_summary(transcription)
    
    # In a real implementation, we would save the summary to S3 and update the job status
    
    return {
        "job_id": job_id,
        "user_id": user_id,
        "summary": summary_result["summary"],
        "metadata": summary_result["metadata"]
    }