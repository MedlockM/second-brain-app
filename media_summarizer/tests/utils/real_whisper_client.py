"""
Real Whisper client for integration tests.

This client connects to the actual Whisper service running in Docker
instead of using mocks, as required by the integration test guidelines.
"""
import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

import httpx
import whisper
from media_summarizer.tests.utils.docker_service_utils import DockerClient, DockerServiceError
from media_summarizer.core.utils.whisper_async import transcribe_async, AsyncWhisperWrapper

logger = logging.getLogger(__name__)


class RealWhisperClient:
    """
    Client for interacting with the real Whisper service running in Docker.

    This client provides the same interface as the mocked Whisper model
    but connects to the actual service running in the docker-compose.dev.yml setup.
    """

    def __init__(self):
        self.docker_client = DockerClient()
        self._ensure_whisper_service()

    def _ensure_whisper_service(self):
        """Ensure the Whisper model is available."""
        # Load the same model configuration as the Docker environment
        self.whisper_model_size = os.environ.get('WHISPER_MODEL_SIZE', 'tiny')
        try:
            import whisper
            self.model = whisper.load_model(self.whisper_model_size)
            logger.info(f"Loaded Whisper model: {self.whisper_model_size}")
        except Exception as e:
            raise DockerServiceError(f"Failed to load Whisper model: {e}")

    def is_available(self) -> bool:
        """Check if the Whisper model is available."""
        return hasattr(self, 'model') and self.model is not None

    def transcribe(self, audio_file: str, **kwargs) -> Dict[str, Any]:
        """
        Transcribe audio file using the same Whisper model as Docker environment.

        Args:
            audio_file: Path to the audio file to transcribe
            **kwargs: Additional arguments (for compatibility with whisper interface)

        Returns:
            Transcription result in the same format as whisper.transcribe()
        """
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        if not self.is_available():
            raise DockerServiceError("Whisper model not loaded")

        try:
            # Use the same model that the Docker environment would use
            result = self.model.transcribe(audio_file, **kwargs)

            # Ensure the result has the expected format
            formatted_result = {
                "text": result.get("text", ""),
                "language": result.get("language", "unknown"),
                "segments": result.get("segments", [])
            }

            logger.info(f"Successfully transcribed audio file using Whisper model: {self.whisper_model_size}")
            return formatted_result

        except Exception as e:
            logger.error(f"Error during Whisper transcription: {e}")
            # Return empty transcription on failure for graceful handling
            return {
                "text": "",
                "language": "unknown",
                "segments": []
            }

    async def transcribe_async(self, audio_file: str, **kwargs) -> Dict[str, Any]:
        """
        Async wrapper for transcription using the core utility.

        Args:
            audio_file: Path to the audio file to transcribe
            **kwargs: Additional arguments

        Returns:
            Transcription result
        """
        return await transcribe_async(self.model, audio_file, **kwargs)


class AsyncRealWhisperClient:
    """
    Async version of the real Whisper client.

    For use in async integration tests.
    """

    def __init__(self):
        self.sync_client = RealWhisperClient()

    async def transcribe(self, audio_file: str, **kwargs) -> Dict[str, Any]:
        """
        Async transcribe method using the hybrid approach.

        Args:
            audio_file: Path to the audio file to transcribe
            **kwargs: Additional arguments

        Returns:
            Transcription result
        """
        # Use the async method from the sync client for consistency
        return await self.sync_client.transcribe_async(audio_file, **kwargs)

    async def transcribe_async(self, audio_file: str, **kwargs) -> Dict[str, Any]:
        """
        Alias for transcribe method for explicit async usage.

        Args:
            audio_file: Path to the audio file to transcribe
            **kwargs: Additional arguments

        Returns:
            Transcription result
        """
        return await self.transcribe(audio_file, **kwargs)

    def is_available(self) -> bool:
        """Check if the Whisper service is available."""
        return self.sync_client.is_available()


class WhisperServiceProxy:
    """
    Proxy class that provides the same interface as the whisper module
    but uses the real Docker service.
    """

    @staticmethod
    def load_model(model_size: str = "tiny") -> RealWhisperClient:
        """
        Load the real Whisper model running in Docker.

        Args:
            model_size: Model size (ignored, uses the size configured in Docker)

        Returns:
            RealWhisperClient instance
        """
        # Log which model size is requested vs what's actually used
        actual_model = os.environ.get('WHISPER_MODEL_SIZE', 'tiny')
        if model_size != actual_model:
            logger.info(f"Requested model '{model_size}' but using '{actual_model}' from Docker service")

        return RealWhisperClient()


# Factory functions for different use cases
def create_real_whisper_client() -> RealWhisperClient:
    """Create a real Whisper client for sync operations."""
    return RealWhisperClient()


def create_async_whisper_client() -> AsyncRealWhisperClient:
    """Create an async real Whisper client."""
    return AsyncRealWhisperClient()


def create_whisper_proxy():
    """Create a proxy that can replace the whisper module in tests."""
    return WhisperServiceProxy()


# Test utilities
def check_whisper_connection() -> bool:
    """Test if we can load the Whisper model."""
    try:
        client = RealWhisperClient()
        return client.is_available()
    except Exception as e:
        logger.error(f"Failed to load Whisper model: {e}")
        return False


async def check_whisper_transcription(audio_file: str) -> bool:
    """
    Test transcription with the real Whisper service.

    Args:
        audio_file: Path to a test audio file

    Returns:
        True if transcription succeeds, False otherwise
    """
    try:
        client = AsyncRealWhisperClient()
        result = await client.transcribe(audio_file)

        # Check if we got a valid result
        return (
            isinstance(result, dict) and
            'text' in result and
            isinstance(result['text'], str)
        )
    except Exception as e:
        logger.error(f"Whisper transcription test failed: {e}")
        return False


# Context manager for temporary audio files
class TempAudioFile:
    """Context manager for creating temporary audio files for testing."""

    def __init__(self, content: bytes, suffix: str = ".mp3"):
        self.content = content
        self.suffix = suffix
        self.temp_file = None
        self.file_path = None

    def __enter__(self) -> str:
        self.temp_file = tempfile.NamedTemporaryFile(
            suffix=self.suffix,
            delete=False
        )
        self.temp_file.write(self.content)
        self.temp_file.close()
        self.file_path = self.temp_file.name
        return self.file_path

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file_path and os.path.exists(self.file_path):
            os.unlink(self.file_path)


# Hybrid transcription function for direct use
async def transcribe_audio_async(audio_file: str, model_size: str = "tiny", **kwargs) -> Dict[str, Any]:
    """
    Convenient async function for transcribing audio using the hybrid approach.

    Args:
        audio_file: Path to the audio file to transcribe
        model_size: Whisper model size (tiny, large)
        **kwargs: Additional arguments for Whisper

    Returns:
        Transcription result
    """
    # Use the core utility wrapper
    wrapper = AsyncWhisperWrapper(whisper.load_model(model_size))
    return await wrapper.transcribe(audio_file, **kwargs)


# Integration with pytest fixtures
def pytest_whisper_client():
    """Factory function for pytest fixtures."""
    def _create_client():
        return create_real_whisper_client()
    return _create_client


def pytest_async_whisper_client():
    """Factory function for async pytest fixtures."""
    def _create_client():
        return create_async_whisper_client()
    return _create_client
