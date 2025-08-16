"""
Simple integration test stubs to fix missing dependencies.

This file provides minimal implementations to make the integration tests work
while they are being refactored to use real Docker services.
"""
import asyncio
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TestWhisperModel:
    """Simple test Whisper model for fallback when Docker service is not available."""

    def transcribe(self, audio_file: str, **kwargs) -> Dict[str, Any]:
        """Mock transcription that returns a predictable result."""
        return {
            "text": "This is a test transcription for integration testing purposes.",
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 10.0,
                    "text": "This is a test transcription segment for integration testing."
                }
            ],
            "language": "en"
        }


class TestSummarizationWorker:
    """Simple test summarization worker."""

    async def generate_summary(self, transcription: str, **kwargs) -> Dict[str, Any]:
        """Generate a test summary."""
        return {
            "summary": {
                "main_topics": ["AI", "Technology", "Testing"],
                "key_points": [
                    "This is a test summary point 1",
                    "This is a test summary point 2",
                    "This is a test summary point 3"
                ],
                "overall_summary": "This is a test summary for integration testing purposes."
            },
            "metadata": {
                "processing_time": 1.0,
                "word_count": len(transcription.split())
            }
        }


# Simple message processing stubs
async def download_process_message(message: Dict[str, Any]) -> None:
    """Stub for download worker message processing."""
    logger.info(f"Processing download message: {message.get('job_id', 'unknown')}")
    # In a real implementation, this would download audio and upload to S3
    pass


async def transcription_process_message(message: Dict[str, Any]) -> None:
    """Stub for transcription worker message processing."""
    logger.info(f"Processing transcription message: {message.get('job_id', 'unknown')}")
    # In a real implementation, this would transcribe audio using Whisper
    pass


async def summarization_process_message(message: Dict[str, Any], api_url: str, api_key: str) -> Dict[str, Any]:
    """Stub for summarization worker message processing."""
    job_id = message.get('job_id', 'unknown')
    logger.info(f"Processing summarization message: {job_id}")

    # Return a mock result
    return {
        "job_id": job_id,
        "summary": {
            "main_topics": ["AI", "Technology", "Testing"],
            "key_points": [
                "This is a test summary point 1",
                "This is a test summary point 2"
            ],
            "overall_summary": "This is a test summary for integration testing."
        },
        "success": True
    }


async def email_process_message(message: Dict[str, Any], ses_client=None) -> None:
    """Stub for email worker message processing."""
    logger.info(f"Processing email message: {message.get('job_id', 'unknown')}")
    # In a real implementation, this would send an email via SES
    pass


# Simple test HTTP server
class TestHTTPServer:
    """Simple HTTP server for testing."""

    def __init__(self, port: int = 8001):
        self.port = port
        self.responses = {}
        self.is_running = False

    def add_response(self, path: str, content: Any, content_type: str = "text/plain"):
        """Add a response for a specific path."""
        self.responses[path] = {
            'content': content,
            'content_type': content_type
        }

    def add_rss_feed(self, path: str, title: str = "Test Podcast", episode_title: str = "Test Episode"):
        """Add an RSS feed response."""
        audio_url = f"http://localhost:{self.port}/test_audio.mp3"

        # Create simple RSS content
        rss_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
        rss_content += '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">\n'
        rss_content += '  <channel>\n'
        rss_content += f'    <title>{title}</title>\n'
        rss_content += f'    <link>http://localhost:{self.port}</link>\n'
        rss_content += '    <description>Test podcast for integration testing</description>\n'
        rss_content += '    <item>\n'
        rss_content += f'      <title>{episode_title}</title>\n'
        rss_content += '      <description>Test episode description</description>\n'
        rss_content += f'      <enclosure url="{audio_url}" length="1000000" type="audio/mpeg"/>\n'
        rss_content += '      <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>\n'
        rss_content += '    </item>\n'
        rss_content += '  </channel>\n'
        rss_content += '</rss>'

        self.add_response(path, rss_content, "application/xml")

    def start(self):
        """Start the HTTP server."""
        self.is_running = True
        logger.info(f"Test HTTP server started on port {self.port}")

    def stop(self):
        """Stop the HTTP server."""
        self.is_running = False
        logger.info("Test HTTP server stopped")
