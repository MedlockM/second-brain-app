"""
OpenAI API mock utility for integration tests.

This module provides utilities for mocking OpenAI API calls in integration tests,
as required by the integration test strategy: "LLM api call can be mocked with
the openai api interface."
"""
import os
import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, Any, List, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class OpenAIMockClient:
    """
    Mock OpenAI client that provides the same interface as the real OpenAI client
    but returns predefined responses for integration tests.
    """

    def __init__(self):
        self.responses = {}
        self.call_history = []
        self.default_responses = {
            "chat_completion": {
                "id": "chatcmpl-test123",
                "object": "chat.completion",
                "created": 1677652288,
                "model": "gpt-4",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "This is a mock summary of the podcast episode. It covers the main topics discussed and provides key insights."
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150
                }
            }
        }

    def set_chat_completion_response(self, content: str, model: str = "gpt-4"):
        """Set custom chat completion response."""
        self.responses["chat_completion"] = {
            "id": "chatcmpl-test123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": len(content.split()),
                "total_tokens": 100 + len(content.split())
            }
        }

    def create_chat_completion(self, messages: List[Dict[str, Any]], model: str = "gpt-4", **kwargs):
        """Mock chat completion creation."""
        # Record the call
        call_info = {
            "method": "create_chat_completion",
            "messages": messages,
            "model": model,
            "kwargs": kwargs
        }
        self.call_history.append(call_info)

        # Return mock response
        response = self.responses.get("chat_completion", self.default_responses["chat_completion"]).copy()
        response["model"] = model

        logger.info(f"Mock OpenAI chat completion called with {len(messages)} messages")
        return response

    async def acreate_chat_completion(self, messages: List[Dict[str, Any]], model: str = "gpt-4", **kwargs):
        """Async mock chat completion creation."""
        return self.create_chat_completion(messages, model, **kwargs)

    def get_call_history(self) -> List[Dict[str, Any]]:
        """Get history of all API calls made to the mock."""
        return self.call_history.copy()

    def reset(self):
        """Reset the mock to initial state."""
        self.responses.clear()
        self.call_history.clear()


# Factory functions
def create_openai_mock_client() -> OpenAIMockClient:
    """Create an OpenAI mock client."""
    return OpenAIMockClient()


# Pytest fixtures
@pytest.fixture
def openai_mock_client():
    """Create an OpenAI mock client fixture."""
    client = OpenAIMockClient()
    yield client
    client.reset()


@pytest.fixture
def openai_mock_with_patch():
    """Create OpenAI mock with automatic patching."""
    mock_client = OpenAIMockClient()

    with patch("openai.ChatCompletion.create", mock_client.create_chat_completion):
        with patch("openai.ChatCompletion.acreate", mock_client.acreate_chat_completion):
            yield mock_client

    mock_client.reset()
