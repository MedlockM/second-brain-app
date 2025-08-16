#!/usr/bin/env python3
"""
Test script for Media Summarizer horizontal scaling system.
This script validates that the scaling infrastructure works correctly.
"""
import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "media-summarizer")
CLUSTER_NAME = f"{PROJECT_NAME}-cluster"

# Test configuration
TEST_TIMEOUT = 300  # 5 minutes
POLLING_INTERVAL = 10  # 10 seconds


class ScalingTestSuite:
    """Test suite for horizontal scaling infrastructure."""

    def __init__(self):
        self.aws_region = AWS_REGION
        self.project_name = PROJECT_NAME
        self.cluster_name = CLUSTER_NAME

        # Initialize AWS clients
        self.sqs_client = boto3.client("sqs", region_name=self.aws_region)
        self.ecs_client = boto3.client("ecs", region_name=self.aws_region)
        self.lambda_client = boto3.client("lambda", region_name=self.aws_region)
        self.cloudwatch_client = boto3.client("cloudwatch", region_name=self.aws_region)

        # Queue names
        self.queue_names = [
            "audio-download-queue",
            "transcription-queue",
            "summarization-queue",
            "email-notification-queue"
        ]

        # Get queue URLs
        self.queue_urls = {}
        for queue_name in self.queue_names:
            try:
                response = self.sqs_client.get_queue_url(QueueName=queue_name)
                self.queue_urls[queue_name] = response["QueueUrl"]
            except ClientError as e:
                logger.error(f"Failed to get URL for queue {queue_name}: {e}")

    def get_queue_message_count(self, queue_url: str) -> int:
        """Get the number of visible messages in a queue."""
        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=["ApproximateNumberOfMessages"]
            )
            return int(response["Attributes"]["ApproximateNumberOfMessages"])
        except ClientError as e:
            logger.error(f"Failed to get message count: {e}")
            return 0

    def get_running_tasks_count(self, worker_type: str) -> int:
        """Get the number of running tasks for a specific worker type."""
        try:
            response = self.ecs_client.list_tasks(
                cluster=self.cluster_name,
                desiredStatus="RUNNING"
            )

            if not response["taskArns"]:
                return 0

            # Describe tasks to get task definition ARNs
            tasks_response = self.ecs_client.describe_tasks(
                cluster=self.cluster_name,
                tasks=response["taskArns"]
            )

            # Count tasks that match our worker type
            count = 0
            for task in tasks_response["tasks"]:
                task_def_arn = task["taskDefinitionArn"]
                if worker_type in task_def_arn:
                    count += 1

            return count
        except ClientError as e:
            logger.error(f"Failed to get running tasks count: {e}")
            return 0

    def send_test_message(self, queue_name: str, message_data: Dict) -> bool:
        """Send a test message to a specific queue."""
        if queue_name not in self.queue_urls:
            logger.error(f"Queue {queue_name} not found")
            return False

        try:
            self.sqs_client.send_message(
                QueueUrl=self.queue_urls[queue_name],
                MessageBody=json.dumps(message_data)
            )
            logger.info(f"Sent test message to {queue_name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to send message to {queue_name}: {e}")
            return False

    def purge_queue(self, queue_name: str) -> bool:
        """Purge all messages from a queue."""
        if queue_name not in self.queue_urls:
            logger.error(f"Queue {queue_name} not found")
            return False

        try:
            self.sqs_client.purge_queue(QueueUrl=self.queue_urls[queue_name])
            logger.info(f"Purged queue {queue_name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to purge queue {queue_name}: {e}")
            return False

    def invoke_scaling_controller(self, test_data: Dict) -> Dict:
        """Invoke the scaling controller Lambda function."""
        function_name = f"{self.project_name}-scaling-controller"

        try:
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                Payload=json.dumps(test_data)
            )

            payload = json.loads(response["Payload"].read())
            if "errorMessage" in payload:
                logger.error(f"Lambda function error: {payload['errorMessage']}")
                return {"success": False, "error": payload["errorMessage"]}

            return {"success": True, "response": payload}
        except ClientError as e:
            logger.error(f"Failed to invoke scaling controller: {e}")
            return {"success": False, "error": str(e)}

    async def wait_for_tasks(self, worker_type: str, expected_count: int, timeout: int = 120) -> bool:
        """Wait for a specific number of tasks to be running."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            current_count = self.get_running_tasks_count(worker_type)
            logger.info(f"Current {worker_type} tasks: {current_count}, expected: {expected_count}")

            if current_count >= expected_count:
                return True

            await asyncio.sleep(POLLING_INTERVAL)

        return False

    async def test_basic_scaling(self) -> bool:
        """Test basic scaling functionality."""
        logger.info("Testing basic scaling functionality...")

        # Clean up any existing messages
        for queue_name in self.queue_names:
            self.purge_queue(queue_name)

        # Wait for queues to be empty
        await asyncio.sleep(60)  # SQS purge can take up to 60 seconds

        # Send test messages to download queue
        test_messages = [
            {
                "job_id": f"test-job-{i}",
                "podcast_url": f"https://example.com/podcast-{i}.rss",
                "user_id": "test-user",
                "email": "test@example.com"
            }
            for i in range(3)
        ]

        for message in test_messages:
            if not self.send_test_message("audio-download-queue", message):
                logger.error("Failed to send test message")
                return False

        # Verify messages are in queue
        await asyncio.sleep(5)
        message_count = self.get_queue_message_count(self.queue_urls["audio-download-queue"])
        logger.info(f"Messages in download queue: {message_count}")

        if message_count != len(test_messages):
            logger.error(f"Expected {len(test_messages)} messages, found {message_count}")
            return False

        # Invoke scaling controller
        scaling_result = self.invoke_scaling_controller({
            "action": "scale",
            "source": "test",
            "queues": ["audio-download-queue"]
        })

        if not scaling_result["success"]:
            logger.error(f"Scaling controller invocation failed: {scaling_result.get('error')}")
            return False

        logger.info(f"Scaling controller response: {scaling_result['response']}")

        # Wait for tasks to be launched
        if not await self.wait_for_tasks("rss", 3, timeout=120):
            logger.error("Expected RSS tasks were not launched within timeout")
            return False

        logger.info("Basic scaling test passed!")
        return True

    async def test_max_workers_limit(self) -> bool:
        """Test that the system respects max workers limit."""
        logger.info("Testing max workers limit...")

        # Clean up queues
        for queue_name in self.queue_names:
            self.purge_queue(queue_name)

        await asyncio.sleep(60)

        # Send many messages (more than max limit)
        test_messages = [
            {
                "job_id": f"test-job-limit-{i}",
                "podcast_url": f"https://example.com/podcast-{i}.rss",
                "user_id": "test-user",
                "email": "test@example.com"
            }
            for i in range(20)  # More than max_parallel_workers (15)
        ]

        for message in test_messages:
            if not self.send_test_message("audio-download-queue", message):
                logger.error("Failed to send test message")
                return False

        # Invoke scaling controller
        scaling_result = self.invoke_scaling_controller({
            "action": "scale",
            "source": "test"
        })

        if not scaling_result["success"]:
            logger.error(f"Scaling controller invocation failed: {scaling_result.get('error')}")
            return False

        # Check that no more than 15 workers are launched
        await asyncio.sleep(30)
        total_tasks = sum(
            self.get_running_tasks_count(worker_type)
            for worker_type in ["rss", "download", "whisper", "summarization", "email"]
        )

        if total_tasks > 15:
            logger.error(f"Too many workers launched: {total_tasks} > 15")
            return False

        logger.info(f"Max workers limit respected: {total_tasks} <= 15")
        return True

    async def test_multi_queue_scaling(self) -> bool:
        """Test scaling across multiple queues."""
        logger.info("Testing multi-queue scaling...")

        # Clean up queues
        for queue_name in self.queue_names:
            self.purge_queue(queue_name)

        await asyncio.sleep(60)

        # Send messages to multiple queues
        test_data = {
            "audio-download-queue": [
                {"job_id": f"download-job-{i}", "audio_url": f"https://example.com/audio-{i}.mp3"}
                for i in range(3)
            ],
            "summarization-queue": [
                {"job_id": f"summary-job-{i}", "transcript": f"Test transcript {i}"}
                for i in range(2)
            ]
        }

        for queue_name, messages in test_data.items():
            for message in messages:
                if not self.send_test_message(queue_name, message):
                    logger.error(f"Failed to send message to {queue_name}")
                    return False

        # Invoke scaling controller
        scaling_result = self.invoke_scaling_controller({
            "action": "scale",
            "source": "test"
        })

        if not scaling_result["success"]:
            logger.error(f"Scaling controller invocation failed: {scaling_result.get('error')}")
            return False

        # Verify appropriate workers are launched
        await asyncio.sleep(30)

        rss_tasks = self.get_running_tasks_count("rss")
        download_tasks = self.get_running_tasks_count("download")
        summary_tasks = self.get_running_tasks_count("summarization")

        logger.info(f"Tasks launched - RSS: {rss_tasks}, Download: {download_tasks}, Summary: {summary_tasks}")

        # We expect at least some tasks for each queue type
        if rss_tasks == 0 or download_tasks == 0 or summary_tasks == 0:
            logger.error("Not all queue types have workers launched")
            return False

        logger.info("Multi-queue scaling test passed!")
        return True

    async def test_no_scaling_when_no_messages(self) -> bool:
        """Test that no scaling occurs when queues are empty."""
        logger.info("Testing no scaling when queues are empty...")

        # Clean up queues
        for queue_name in self.queue_names:
            self.purge_queue(queue_name)

        await asyncio.sleep(60)

        # Get initial task count
        initial_task_count = sum(
            self.get_running_tasks_count(worker_type)
            for worker_type in ["rss", "download", "whisper", "summarization", "email"]
        )

        # Invoke scaling controller with empty queues
        scaling_result = self.invoke_scaling_controller({
            "action": "scale",
            "source": "test"
        })

        if not scaling_result["success"]:
            logger.error(f"Scaling controller invocation failed: {scaling_result.get('error')}")
            return False

        # Wait a bit and check that no new tasks were launched
        await asyncio.sleep(30)
        final_task_count = sum(
            self.get_running_tasks_count(worker_type)
            for worker_type in ["rss", "download", "whisper", "summarization", "email"]
        )

        if final_task_count > initial_task_count:
            logger.error(f"Unexpected tasks launched: {final_task_count} > {initial_task_count}")
            return False

        logger.info("No scaling with empty queues test passed!")
        return True

    async def cleanup_test_resources(self):
        """Clean up test resources."""
        logger.info("Cleaning up test resources...")

        # Purge all queues
        for queue_name in self.queue_names:
            self.purge_queue(queue_name)

        # Wait for any running tasks to complete (they should be ephemeral)
        logger.info("Waiting for ephemeral tasks to complete...")
        await asyncio.sleep(120)  # Give tasks time to finish processing and terminate

        logger.info("Cleanup completed.")

    async def run_all_tests(self) -> bool:
        """Run all scaling tests."""
        logger.info("Starting scaling test suite...")

        tests = [
            ("Basic Scaling", self.test_basic_scaling),
            ("Max Workers Limit", self.test_max_workers_limit),
            ("Multi-Queue Scaling", self.test_multi_queue_scaling),
            ("No Scaling When Empty", self.test_no_scaling_when_no_messages),
        ]

        passed = 0
        failed = 0

        for test_name, test_func in tests:
            logger.info(f"\n{'='*50}")
            logger.info(f"Running test: {test_name}")
            logger.info(f"{'='*50}")

            try:
                if await test_func():
                    logger.info(f"✅ {test_name} PASSED")
                    passed += 1
                else:
                    logger.error(f"❌ {test_name} FAILED")
                    failed += 1
            except Exception as e:
                logger.error(f"❌ {test_name} FAILED with exception: {e}")
                failed += 1

            # Wait between tests
            await asyncio.sleep(10)

        # Cleanup
        await self.cleanup_test_resources()

        # Summary
        logger.info(f"\n{'='*50}")
        logger.info(f"TEST SUMMARY")
        logger.info(f"{'='*50}")
        logger.info(f"Total tests: {passed + failed}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Success rate: {(passed / (passed + failed)) * 100:.1f}%")

        return failed == 0


async def main():
    """Main test execution."""
    test_suite = ScalingTestSuite()

    try:
        success = await test_suite.run_all_tests()
        exit_code = 0 if success else 1
    except Exception as e:
        logger.error(f"Test suite failed with exception: {e}")
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
