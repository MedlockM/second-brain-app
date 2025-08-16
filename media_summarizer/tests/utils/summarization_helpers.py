"""
Lightweight test implementation of SummarizationWorker for integration testing.

This module provides a simplified version of the SummarizationWorker that can be used
in integration tests without requiring the full LLM to be available.
"""
from typing import Dict, Any, List


class TestSummarizationWorker:
    """A lightweight test implementation of the SummarizationWorker."""
    
    def __init__(self, api_url: str = "https://api.example.com", api_key: str = "test-key"):
        """
        Initialize the test summarization worker.
        
        Args:
            api_url: The API URL to simulate
            api_key: The API key to simulate
        """
        self.api_url = api_url
        self.api_key = api_key
    
    async def generate_summary(self, transcription: str) -> Dict[str, Any]:
        """
        Generate a test summary for the given transcription.
        
        Args:
            transcription: The transcription text to summarize
            
        Returns:
            A dictionary containing the summary
        """
        # Extract topics based on keywords in the transcription
        topics = []
        if "artificial intelligence" in transcription.lower() or "ai" in transcription.lower():
            topics.append("Artificial Intelligence")
        if "healthcare" in transcription.lower() or "medical" in transcription.lower():
            topics.append("Healthcare")
        if "finance" in transcription.lower() or "banking" in transcription.lower():
            topics.append("Finance")
        if "ethics" in transcription.lower() or "ethical" in transcription.lower():
            topics.append("Ethics in Technology")
        
        # If no specific topics were found, add a generic one
        if not topics:
            topics = ["General Discussion"]
        
        # Generate key points based on the transcription
        key_points = self._extract_key_points(transcription)
        
        # Generate notable quotes
        quotes = self._extract_quotes(transcription)
        
        return {
            "summary": {
                "main_topics": topics,
                "key_points": key_points,
                "notable_quotes": quotes,
                "conclusion": "This is a test conclusion generated for integration testing."
            },
            "metadata": {
                "model": "test-model",
                "usage": {"total_tokens": 100},
                "chunked": False
            }
        }
    
    def _extract_key_points(self, text: str) -> List[str]:
        """Extract key points from the transcription."""
        # In a real implementation, this would use NLP techniques
        # For testing, we'll just return some fixed points
        points = [
            "This is a test key point for integration testing.",
            "The podcast discusses important topics related to technology."
        ]
        
        # Add conditional points based on content
        if "artificial intelligence" in text.lower() or "ai" in text.lower():
            points.append("AI is transforming various industries.")
            points.append("Ethical considerations are important in AI development.")
        
        if "future" in text.lower():
            points.append("Future developments will focus on new technologies.")
        
        return points
    
    def _extract_quotes(self, text: str) -> List[str]:
        """Extract notable quotes from the transcription."""
        # In a real implementation, this would use NLP techniques
        # For testing, we'll just return some fixed quotes
        quotes = []
        
        # Add conditional quotes based on content
        if "artificial intelligence" in text.lower() or "ai" in text.lower():
            quotes.append("AI is the new electricity.")
        
        if "ethics" in text.lower() or "ethical" in text.lower():
            quotes.append("Ethics must be at the forefront of technological development.")
        
        # Always include at least one quote
        if not quotes:
            quotes.append("This is a test quote for integration testing.")
        
        return quotes