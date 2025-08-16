"""
HTTPx-based async HTTP test server for integration tests.

This module provides utilities for creating async HTTP servers using httpx
for testing RSS feeds and audio file downloads, as specified in the integration
test strategy.
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, Callable, Awaitable
from pathlib import Path

import httpx
from fastapi import FastAPI, Response, Request
from fastapi.responses import PlainTextResponse, FileResponse
import uvicorn

logger = logging.getLogger(__name__)


class HTTPXTestServer:
    """
    Async HTTP test server using FastAPI and httpx for integration tests.

    This server provides a more robust and async-compatible alternative to
    the basic HTTP server, following the integration test strategy requirement
    for "HTTP async server using httpx".
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 8001):
        self.host = host
        self.port = port
        self.app = FastAPI()
        self.server = None
        self.server_task = None
        self.responses: Dict[str, Dict[str, Any]] = {}
        self.custom_handlers: Dict[str, Callable] = {}

        # Set up default routes
        self._setup_routes()

    def _setup_routes(self):
        """Set up the FastAPI routes for handling test requests."""

        @self.app.get("/{path:path}")
        async def handle_get(path: str, request: Request):
            """Handle GET requests with registered responses."""
            full_path = f"/{path}"

            # Check for custom handlers first
            if full_path in self.custom_handlers:
                return await self.custom_handlers[full_path](request)

            # Check for registered responses
            if full_path in self.responses:
                response_data = self.responses[full_path]
                content = response_data["content"]
                content_type = response_data.get("content_type", "text/plain")
                status_code = response_data.get("status_code", 200)
                headers = response_data.get("headers", {})

                # Handle different content types
                if isinstance(content, bytes):
                    return Response(
                        content=content,
                        status_code=status_code,
                        headers={"content-type": content_type, **headers}
                    )
                else:
                    return Response(
                        content=str(content),
                        status_code=status_code,
                        headers={"content-type": content_type, **headers}
                    )

            # Return 404 for unregistered paths
            return Response(
                content="Not Found",
                status_code=404,
                headers={"content-type": "text/plain"}
            )

        @self.app.post("/{path:path}")
        async def handle_post(path: str, request: Request):
            """Handle POST requests with registered responses."""
            full_path = f"/{path}"

            # Check for custom handlers first
            if full_path in self.custom_handlers:
                return await self.custom_handlers[full_path](request)

            # Check for registered responses
            if full_path in self.responses:
                response_data = self.responses[full_path]
                content = response_data["content"]
                content_type = response_data.get("content_type", "application/json")
                status_code = response_data.get("status_code", 200)
                headers = response_data.get("headers", {})

                return Response(
                    content=content if isinstance(content, (str, bytes)) else json.dumps(content),
                    status_code=status_code,
                    headers={"content-type": content_type, **headers}
                )

            # Return 404 for unregistered paths
            return Response(
                content="Not Found",
                status_code=404,
                headers={"content-type": "text/plain"}
            )

    def add_response(
        self,
        path: str,
        content: Any,
        content_type: str = "text/plain",
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None
    ):
        """
        Add a static response for a specific path.

        Args:
            path: The URL path (should start with /)
            content: The response content (str, bytes, or dict)
            content_type: The Content-Type header
            status_code: HTTP status code
            headers: Additional headers
        """
        self.responses[path] = {
            "content": content,
            "content_type": content_type,
            "status_code": status_code,
            "headers": headers or {}
        }

    def add_rss_feed(self, path: str, rss_content: str):
        """
        Add an RSS feed response.

        Args:
            path: The URL path for the RSS feed
            rss_content: The RSS XML content
        """
        self.add_response(
            path,
            rss_content,
            content_type="application/rss+xml"
        )

    def add_audio_file(self, path: str, audio_content: bytes):
        """
        Add an audio file response.

        Args:
            path: The URL path for the audio file
            audio_content: The audio file content as bytes
        """
        self.add_response(
            path,
            audio_content,
            content_type="audio/mpeg"
        )

    def add_json_response(self, path: str, data: Dict[str, Any], status_code: int = 200):
        """
        Add a JSON response.

        Args:
            path: The URL path
            data: The JSON data
            status_code: HTTP status code
        """
        self.add_response(
            path,
            json.dumps(data),
            content_type="application/json",
            status_code=status_code
        )

    def add_error_response(self, path: str, status_code: int, message: str = "Error"):
        """
        Add an error response.

        Args:
            path: The URL path
            status_code: HTTP error status code
            message: Error message
        """
        self.add_response(
            path,
            message,
            content_type="text/plain",
            status_code=status_code
        )

    def add_custom_handler(self, path: str, handler: Callable[[Request], Awaitable[Response]]):
        """
        Add a custom async handler for a path.

        Args:
            path: The URL path
            handler: Async function that takes Request and returns Response
        """
        self.custom_handlers[path] = handler

    def add_redirect(self, path: str, target_url: str, status_code: int = 302):
        """
        Add a redirect response.

        Args:
            path: The URL path to redirect from
            target_url: The target URL to redirect to
            status_code: HTTP redirect status code (302, 301, etc.)
        """
        self.add_response(
            path,
            "",
            status_code=status_code,
            headers={"Location": target_url}
        )

    async def start(self):
        """Start the async HTTP server."""
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="error"  # Reduce noise in tests
        )
        self.server = uvicorn.Server(config)

        # Start server in a background task
        self.server_task = asyncio.create_task(self.server.serve())

        # Wait a bit for server to start
        await asyncio.sleep(0.1)

        # Verify server is running
        await self._wait_for_server()

        logger.info(f"HTTPx test server started at http://{self.host}:{self.port}")

    async def stop(self):
        """Stop the async HTTP server."""
        if self.server:
            self.server.should_exit = True

        if self.server_task:
            try:
                await asyncio.wait_for(self.server_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Server shutdown timed out")
                self.server_task.cancel()
                try:
                    await self.server_task
                except asyncio.CancelledError:
                    pass

        logger.info("HTTPx test server stopped")

    async def _wait_for_server(self, timeout: float = 5.0):
        """Wait for the server to be ready to accept connections."""
        start_time = asyncio.get_event_loop().time()

        while True:
            try:
                async with httpx.AsyncClient() as client:
                    # Try to connect to a non-existent endpoint
                    # We expect 404, but it means server is responding
                    response = await client.get(
                        f"http://{self.host}:{self.port}/health-check-ping",
                        timeout=1.0
                    )
                    # Any response (including 404) means server is up
                    break
            except (httpx.ConnectError, httpx.TimeoutException):
                if asyncio.get_event_loop().time() - start_time > timeout:
                    raise TimeoutError(f"Server failed to start within {timeout} seconds")
                await asyncio.sleep(0.1)

    @property
    def base_url(self) -> str:
        """Get the base URL of the server."""
        return f"http://{self.host}:{self.port}"

    def get_url(self, path: str) -> str:
        """Get the full URL for a path."""
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.base_url}{path}"

    def clear_responses(self):
        """Clear all registered responses and handlers."""
        self.responses.clear()
        self.custom_handlers.clear()


@asynccontextmanager
async def httpx_test_server(
    host: str = "127.0.0.1",
    port: int = 8001
) -> HTTPXTestServer:
    """
    Context manager for HTTPx test server.

    Usage:
        async with httpx_test_server() as server:
            server.add_rss_feed("/feed.xml", rss_content)
            # Use server.base_url in tests
    """
    server = HTTPXTestServer(host, port)
    try:
        await server.start()
        yield server
    finally:
        await server.stop()


class HTTPXTestClient:
    """
    Enhanced httpx client for integration tests.

    Provides additional utilities for testing HTTP interactions.
    """

    def __init__(self, base_url: Optional[str] = None, **client_kwargs):
        self.base_url = base_url
        self.client_kwargs = client_kwargs
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> httpx.AsyncClient:
        """Enter async context manager."""
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            **self.client_kwargs
        )
        return self._client

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager."""
        if self._client:
            await self._client.aclose()

    @staticmethod
    async def test_url_accessibility(url: str, timeout: float = 5.0) -> bool:
        """
        Test if a URL is accessible.

        Args:
            url: The URL to test
            timeout: Request timeout

        Returns:
            True if URL is accessible, False otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=timeout)
                return response.status_code < 500
        except Exception:
            return False

    @staticmethod
    async def download_content(url: str, timeout: float = 30.0) -> bytes:
        """
        Download content from a URL.

        Args:
            url: The URL to download from
            timeout: Request timeout

        Returns:
            Downloaded content as bytes
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=timeout)
            response.raise_for_status()
            return response.content


# Pytest fixtures for easy use
def pytest_httpx_server():
    """Factory function for pytest fixtures."""
    return httpx_test_server


def pytest_httpx_client():
    """Factory function for pytest fixtures."""
    def _create_client(base_url: Optional[str] = None, **kwargs):
        return HTTPXTestClient(base_url, **kwargs)
    return _create_client


# Utility functions for loading test data
def load_test_rss_feed(filename: str = "sample_rss.xml") -> str:
    """
    Load a test RSS feed from fixtures.

    Args:
        filename: Name of the RSS file in fixtures directory

    Returns:
        RSS feed content as string
    """
    # Try to find the fixtures directory
    fixtures_paths = [
        Path(__file__).parent.parent / "fixtures",
        Path(__file__).parent.parent / "tests" / "fixtures"
    ]

    for fixtures_dir in fixtures_paths:
        rss_file = fixtures_dir / filename
        if rss_file.exists():
            return rss_file.read_text(encoding="utf-8")

    # Return a default RSS feed if file not found
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">'
            '<channel>'
            '<title>Test Podcast</title>'
            '<link>https://example.com</link>'
            '<description>A test podcast for integration testing</description>'
            '<language>en-us</language>'
            '<itunes:author>Test Author</itunes:author>'
            '<item>'
            '<title>Test Episode</title>'
            '<description>This is a test episode</description>'
            '<pubDate>Tue, 22 Jul 2025 12:00:00 GMT</pubDate>'
            '<enclosure url="https://example.com/episode.mp3" length="12345678" type="audio/mpeg"/>'
            '<guid isPermaLink="false">test-episode-guid</guid>'
            '</item>'
            '</channel>'
            '</rss>')
