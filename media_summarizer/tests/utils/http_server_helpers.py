"""
Test HTTP server utility for integration tests.

This module provides a simple HTTP server for testing RSS feeds,
audio downloads, and other HTTP-based interactions.
"""
import http.server
import json
import logging
import os
import socketserver
import threading
import time
from typing import Dict, Any, Optional
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class TestHTTPServer:
    """A simple HTTP server for testing RSS feeds and audio files."""

    def __init__(self, port: int = 8001, host: str = "localhost"):
        self.port = port
        self.host = host
        self.server = None
        self.thread = None
        self.responses = {}
        self.request_log = []
        self.is_running = False

    def add_response(self, path: str, content: Any, content_type: str = "text/plain", status_code: int = 200):
        """
        Add a response for a specific path.

        Args:
            path: The URL path to respond to
            content: The content to return (string or bytes)
            content_type: The content type header
            status_code: HTTP status code to return
        """
        self.responses[path] = {
            'content': content,
            'content_type': content_type,
            'status_code': status_code
        }

    def add_rss_feed(self, path: str, title: str = "Test Podcast",
                     episode_title: str = "Test Episode",
                     audio_url: str = None):
        """
        Add an RSS feed response.

        Args:
            path: The URL path for the RSS feed
            title: Podcast title
            episode_title: Episode title
            audio_url: URL of the audio file (will use server URL if not provided)
        """
        if audio_url is None:
            audio_url = f"http://{self.host}:{self.port}/test_audio.mp3"

        rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
    <channel>
        <title>{title}</title>
        <description>Test podcast for integration testing</description>
        <link>http://{self.host}:{self.port}</link>
        <item>
            <title>{episode_title}</title>
            <description>Test episode description</description>
            <enclosure url="{audio_url}" type="audio/mpeg" length="1000000"/>
            <guid>{audio_url}</guid>
            <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
        </item>
    </channel>
</rss>"""

        self.add_response(path, rss_content, "application/rss+xml")

    def add_audio_file(self, path: str = "/test_audio.mp3"):
        """
        Add a mock audio file response.

        Args:
            path: The URL path for the audio file
        """
        # Create mock audio content (just some bytes)
        audio_content = b"Mock audio file content for testing"
        self.add_response(path, audio_content, "audio/mpeg")

    def start(self):
        """Start the HTTP server."""
        handler = self._create_request_handler()
        self.server = socketserver.TCPServer((self.host, self.port), handler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        self.is_running = True

        # Wait a bit for server to start
        time.sleep(0.1)
        logger.info(f"Test HTTP server started on {self.host}:{self.port}")

    def stop(self):
        """Stop the HTTP server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=1)
            self.is_running = False
            logger.info("Test HTTP server stopped")

    def clear_log(self):
        """Clear the request log."""
        self.request_log.clear()

    def get_requests(self):
        """Get all logged requests."""
        return self.request_log.copy()

    def _create_request_handler(self):
        """Create a request handler class with access to server instance."""
        server_instance = self

        class TestRequestHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                # Suppress default logging
                pass

            def do_GET(self):
                # Log the request
                server_instance.request_log.append({
                    'method': 'GET',
                    'path': self.path,
                    'headers': dict(self.headers)
                })

                # Check if we have a response for this path
                parsed_url = urlparse(self.path)
                path = parsed_url.path

                if path in server_instance.responses:
                    response_data = server_instance.responses[path]

                    self.send_response(response_data['status_code'])
                    self.send_header('Content-Type', response_data['content_type'])
                    self.end_headers()

                    content = response_data['content']
                    if isinstance(content, str):
                        content = content.encode('utf-8')

                    self.wfile.write(content)
                else:
                    # Return 404 for unknown paths
                    self.send_response(404)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'Not Found')

        return TestRequestHandler
