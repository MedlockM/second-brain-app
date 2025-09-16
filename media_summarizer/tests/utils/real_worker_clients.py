"""
Real worker service utilities for integration tests.

This module provides utilities to interact with actual worker services
running in Docker containers instead of mocking them, as required by
the integration test guidelines.
"""
import asyncio
import json
import logging
import time
from typing import Dict, Any, Optional, List
import uuid

import aioboto3
from media_summarizer.tests.utils.docker_service_utils import DockerClient, DockerServiceError
from media_summarizer.tests.utils.localstack_helpers import (
    AWS_ENDPOINT_URL,
    AWS_REGION,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY
)

logger = logging.getLogger(__name__)

# Queue names from docker-compose configuration
QUEUE_NAMES = {
    "audio_download": "audio-download-queue",
    "transcription": "transcription-queue",
    "summarization": "summarization-queue",
    "email_notification": "email-notification-queue"
}

class RealWorkerClient:
    """
    Base class for interacting with real worker services.

    This class provides common functionality for sending messages to workers
    and verifying their processing through the actual SQS queues.
    """

    def __init__(self):
        self.docker_client = DockerClient()
        self.session = aioboto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )

    def _get_queue_url(self, queue_name: str) -> str:
        """Get the full queue URL for LocalStack."""
        return f"{AWS_ENDPOINT_URL}/000000000000/{queue_name}"

    async def _send_message(self, queue_name: str, message: Dict[str, Any]) -> str:
        """Send a message to a SQS queue."""
        queue_url = self._get_queue_url(queue_name)

        async with self.session.client('sqs', endpoint_url=AWS_ENDPOINT_URL) as sqs:
            try:
                response = await sqs.send_message(
                    QueueUrl=queue_url,
                    MessageBody=json.dumps(message)
                )
                message_id = response.get('MessageId')
                logger.info(f"Sent message {message_id} to queue {queue_name}")
                return message_id
            except Exception as e:
                logger.error(f"Failed to send message to {queue_name}: {e}")
                raise

    async def _wait_for_message(self, queue_name: str, timeout: int = 30,
                              expected_job_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Wait for a message in a queue, optionally filtering by job_id."""
        queue_url = self._get_queue_url(queue_name)
        start_time = time.time()

        async with self.session.client('sqs', endpoint_url=AWS_ENDPOINT_URL) as sqs:
            while time.time() - start_time < timeout:
                try:
                    response = await sqs.receive_message(
                        QueueUrl=queue_url,
                        MaxNumberOfMessages=10,
                        WaitTimeSeconds=2
                    )

                    messages = response.get('Messages', [])
                    for message in messages:
                        body = json.loads(message.get('Body', '{}'))

                        # If we're looking for a specific job_id, filter by it
                        if expected_job_id:
                            if body.get('job_id') == expected_job_id:
                                # Delete the message and return it
                                await sqs.delete_message(
                                    QueueUrl=queue_url,
                                    ReceiptHandle=message['ReceiptHandle']
                                )
                                return body
                        else:
                            # Return any message
                            await sqs.delete_message(
                                QueueUrl=queue_url,
                                ReceiptHandle=message['ReceiptHandle']
                            )
                            return body

                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(f"Error waiting for message in {queue_name}: {e}")
                    await asyncio.sleep(1)

        logger.warning(f"No message received in {queue_name} within {timeout}s")
        return None

    def _is_worker_running(self, worker_name: str) -> bool:
        """Check if a worker container is running."""
        return self.docker_client.is_container_healthy(worker_name)


class RealRSSWorkerClient(RealWorkerClient):
    """Client for simulating an RSS resolution step feeding the download queue."""

    def is_available(self) -> bool:
        # If download worker is running, we consider RSS step available in tests
        return self._is_worker_running("download-worker")

    async def submit_rss_job(self, podcast_url: str, email: str, user_id: str, job_id: str | None = None) -> str:
        """
        Simulate an RSS resolution by enqueueing a message for the download worker.
        """
        if not job_id:
            job_id = str(uuid.uuid4())
        message = {
            "job_id": job_id,
            "podcast_url": podcast_url,
            "user_email": email,
            "user_id": user_id,
        }
        await self._send_message(QUEUE_NAMES["audio_download"], message)
        return job_id

    async def wait_for_download_message(self, job_id: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Wait for the message to be visible in the download queue (loopback for tests)."""
        return await self._wait_for_message(QUEUE_NAMES["audio_download"], timeout=timeout, expected_job_id=job_id)


class RealDownloadWorkerClient(RealWorkerClient):
    """Client for testing the download worker."""

    def is_available(self) -> bool:
        """Check if the download worker is available."""
        return self._is_worker_running("download-worker")

    async def submit_download_job(self, audio_url: str, job_id: str = None) -> str:
        """
        Submit a job to the download worker.

        Args:
            audio_url: URL of the audio file to download
            job_id: Job ID (will generate if not provided)

        Returns:
            Job ID
        """
        if not job_id:
            job_id = str(uuid.uuid4())

        message = {
            "job_id": job_id,
            "audio_url": audio_url,
            "bucket_name": "media-summarizer-audio"
        }

        await self._send_message(QUEUE_NAMES["audio_download"], message)
        return job_id

    async def wait_for_transcription_message(self, job_id: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Wait for the download worker to produce a transcription message."""
        return await self._wait_for_message(
            QUEUE_NAMES["transcription"],
            timeout=timeout,
            expected_job_id=job_id
        )


class RealTranscriptionWorkerClient(RealWorkerClient):
    """Client for testing the transcription worker (Whisper)."""

    def is_available(self) -> bool:
        """Check if the transcription worker is available."""
        return self._is_worker_running("whisper")

    async def submit_transcription_job(self, s3_audio_key: str, job_id: str = None) -> str:
        """
        Submit a job to the transcription worker.

        Args:
            s3_audio_key: S3 key of the audio file to transcribe
            job_id: Job ID (will generate if not provided)

        Returns:
            Job ID
        """
        if not job_id:
            job_id = str(uuid.uuid4())

        message = {
            "job_id": job_id,
            "s3_audio_key": s3_audio_key,
            "bucket_name": "media-summarizer-audio"
        }

        await self._send_message(QUEUE_NAMES["transcription"], message)
        return job_id

    async def wait_for_summarization_message(self, job_id: str, timeout: int = 60) -> Optional[Dict[str, Any]]:
        """Wait for the transcription worker to produce a summarization message."""
        return await self._wait_for_message(
            QUEUE_NAMES["summarization"],
            timeout=timeout,
            expected_job_id=job_id
        )


class RealSummarizationWorkerClient(RealWorkerClient):
    """Client for testing the summarization worker."""

    def is_available(self) -> bool:
        """Check if the summarization worker is available."""
        return self._is_worker_running("summarize-worker")

    async def submit_summarization_job(self, transcription_key: str, job_id: str = None) -> str:
        """
        Submit a job to the summarization worker.

        Args:
            transcription_key: S3 key of the transcription file
            job_id: Job ID (will generate if not provided)

        Returns:
            Job ID
        """
        if not job_id:
            job_id = str(uuid.uuid4())

        message = {
            "job_id": job_id,
            "transcription_key": transcription_key
        }

        await self._send_message(QUEUE_NAMES["summarization"], message)
        return job_id

    async def wait_for_email_message(self, job_id: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Wait for the summarization worker to produce an email message."""
        return await self._wait_for_message(
            QUEUE_NAMES["email_notification"],
            timeout=timeout,
            expected_job_id=job_id
        )


class RealEmailWorkerClient(RealWorkerClient):
    """Client for testing the email worker."""

    def is_available(self) -> bool:
        """Check if the email worker is available."""
        return self._is_worker_running("email-worker")

    async def submit_email_job(self, recipient: str, subject: str, content: str, job_id: str = None) -> str:
        """
        Submit a job to the email worker.

        Args:
            recipient: Email recipient
            subject: Email subject
            content: Email content
            job_id: Job ID (will generate if not provided)

        Returns:
            Job ID
        """
        if not job_id:
            job_id = str(uuid.uuid4())

        message = {
            "job_id": job_id,
            "recipient": recipient,
            "subject": subject,
            "content": content
        }

        await self._send_message(QUEUE_NAMES["email_notification"], message)
        return job_id




class RealWorkflowClient:
    """
    Client for testing complete workflows through real worker services.

    This client can orchestrate complete end-to-end workflows by chaining
    multiple worker services together.
    """

    def __init__(self):
        self.rss_client = RealRSSWorkerClient()
        self.download_client = RealDownloadWorkerClient()
        self.transcription_client = RealTranscriptionWorkerClient()
        self.summarization_client = RealSummarizationWorkerClient()
        self.email_client = RealEmailWorkerClient()

    def are_all_workers_available(self) -> bool:
        """Check if all workers are available."""
        return (
            self.rss_client.is_available() and
            self.download_client.is_available() and
            self.transcription_client.is_available() and
            self.summarization_client.is_available() and
            self.email_client.is_available()
        )



# Factory functions used by tests/base classes

def create_rss_worker_client() -> RealRSSWorkerClient:
    return RealRSSWorkerClient()


def create_download_worker_client() -> RealDownloadWorkerClient:
    return RealDownloadWorkerClient()


def create_transcription_worker_client() -> RealTranscriptionWorkerClient:
    return RealTranscriptionWorkerClient()


def create_summarization_worker_client() -> RealSummarizationWorkerClient:
    return RealSummarizationWorkerClient()


def create_email_worker_client() -> RealEmailWorkerClient:
    return RealEmailWorkerClient()


def create_workflow_client() -> RealWorkflowClient:
    return RealWorkflowClient()

    def get_unavailable_workers(self) -> List[str]:
        """Get list of unavailable workers."""
        unavailable = []

        if not self.rss_client.is_available():
            unavailable.append("rss-worker")
        if not self.download_client.is_available():
            unavailable.append("download-worker")
        if not self.transcription_client.is_available():
            unavailable.append("whisper")
        if not self.summarization_client.is_available():
            unavailable.append("summarize-worker")
        if not self.email_client.is_available():
            unavailable.append("email-worker")

        return unavailable

    async def submit_complete_workflow(self, podcast_url: str, email: str, user_id: str = "test-user") -> str:
        """
        Submit a complete podcast processing workflow.

        Args:
            podcast_url: URL of the podcast
            email: Email for notifications
            user_id: User ID

        Returns:
            Job ID
        """
        return await self.rss_client.submit_rss_job(podcast_url, email, user_id)

    async def wait_for_workflow_completion(self, job_id: str, timeout: int = 300) -> Dict[str, Any]:
        """
        Wait for a complete workflow to finish.

        Args:
            job_id: Job ID to track
            timeout: Maximum time to wait in seconds

        Returns:
            Dictionary with workflow results and status
        """
        start_time = time.time()
        workflow_status = {
            "job_id": job_id,
            "completed_steps": [],
            "current_step": "rss_resolution",
            "success": False,
            "error": None,
            "messages": {}
        }

        try:
            # Step 1: Wait for RSS resolution to complete
            logger.info(f"Waiting for RSS resolution for job {job_id}")
            download_message = await self.rss_client.wait_for_download_message(
                job_id, timeout=min(60, timeout)
            )

            if not download_message:
                workflow_status["error"] = "RSS resolution timed out"
                return workflow_status

            workflow_status["completed_steps"].append("rss_resolution")
            workflow_status["messages"]["download"] = download_message
            workflow_status["current_step"] = "audio_download"

            # Step 2: Wait for audio download to complete
            logger.info(f"Waiting for audio download for job {job_id}")
            remaining_time = timeout - (time.time() - start_time)
            transcription_message = await self.download_client.wait_for_transcription_message(
                job_id, timeout=min(60, remaining_time)
            )

            if not transcription_message:
                workflow_status["error"] = "Audio download timed out"
                return workflow_status

            workflow_status["completed_steps"].append("audio_download")
            workflow_status["messages"]["transcription"] = transcription_message
            workflow_status["current_step"] = "transcription"

            # Step 3: Wait for transcription to complete
            logger.info(f"Waiting for transcription for job {job_id}")
            remaining_time = timeout - (time.time() - start_time)
            summarization_message = await self.transcription_client.wait_for_summarization_message(
                job_id, timeout=min(120, remaining_time)  # Transcription takes longer
            )

            if not summarization_message:
                workflow_status["error"] = "Transcription timed out"
                return workflow_status

            workflow_status["completed_steps"].append("transcription")
            workflow_status["messages"]["summarization"] = summarization_message
            workflow_status["current_step"] = "summarization"

            # Step 4: Wait for summarization to complete
            logger.info(f"Waiting for summarization for job {job_id}")
            remaining_time = timeout - (time.time() - start_time)
            email_message = await self.summarization_client.wait_for_email_message(
                job_id, timeout=min(60, remaining_time)
            )

            if not email_message:
                workflow_status["error"] = "Summarization timed out"
                return workflow_status

            workflow_status["completed_steps"].append("summarization")
            workflow_status["messages"]["email"] = email_message
            workflow_status["current_step"] = "email_notification"
            workflow_status["success"] = True

            logger.info(f"Complete workflow finished successfully for job {job_id}")

        except Exception as e:
            logger.error(f"Workflow failed for job {job_id}: {e}")
            workflow_status["error"] = str(e)

        return workflow_status


# Factory functions for different use cases


def create_download_worker_client() -> RealDownloadWorkerClient:
    """Create a real download worker client."""
    return RealDownloadWorkerClient()


def create_transcription_worker_client() -> RealTranscriptionWorkerClient:
    """Create a real transcription worker client."""
    return RealTranscriptionWorkerClient()


def create_summarization_worker_client() -> RealSummarizationWorkerClient:
    """Create a real summarization worker client."""
    return RealSummarizationWorkerClient()


def create_email_worker_client() -> RealEmailWorkerClient:
    """Create a real email worker client."""
    return RealEmailWorkerClient()


def create_workflow_client() -> RealWorkflowClient:
    """Create a complete workflow client."""
    return RealWorkflowClient()




# Test utilities
async def test_all_workers_connection() -> Dict[str, bool]:
    """Test connection to all worker services."""
    workflow_client = RealWorkflowClient()

    return {
        "download-worker": workflow_client.download_client.is_available(),
        "whisper": workflow_client.transcription_client.is_available(),
        "summarize-worker": workflow_client.summarization_client.is_available(),
        "email-worker": workflow_client.email_client.is_available()
    }


async def verify_queue_connectivity() -> Dict[str, bool]:
    """Verify connectivity to all SQS queues."""
    client = RealWorkerClient()
    results = {}

    for queue_type, queue_name in QUEUE_NAMES.items():
        try:
            # Try to send a test message
            test_message = {"test": True, "job_id": "connectivity-test"}
            await client._send_message(queue_name, test_message)
            results[queue_type] = True
        except Exception as e:
            logger.error(f"Queue {queue_name} connectivity failed: {e}")
            results[queue_type] = False

    return results
