"""
Simple HTTP server for integration tests.
"""
import http.server
import socketserver
import threading
import time
from typing import Dict, Any


class TestHTTPServer:
    """A simple HTTP server for testing RSS feeds and audio files."""

    def __init__(self, port: int = 8001):
        self.port = port
        self.server = None
        self.thread = None
        self.responses = {}

    def add_response(self, path: str, content: Any, content_type: str = "text/plain"):
        """Add a response for a specific path."""
        self.responses[path] = {
            'content': content,
            'content_type': content_type
        }

    def add_rss_feed(self, path: str, title: str = "Test Podcast", episode_title: str = "Test Episode"):
        """Add an RSS feed response."""
        audio_url = f"http://localhost:{self.port}/test_audio.mp3"

        rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{title}</title>
    <link
