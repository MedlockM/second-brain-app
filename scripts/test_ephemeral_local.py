#!/usr/bin/env python3
"""
Script de test local pour les workers éphémères.
Ce script permet de tester le système de scaling horizontal en environnement de développement.
"""
import asyncio
import json
import logging
import os
import subprocess
import time
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
AWS_ENDPOINT_URL = "http://localhost:4566"
AWS_REGION = "us-east-1"
AWS_ACCESS_KEY_ID = "test"
AWS_SECRET_ACCESS_KEY = "test"


class LocalEphemeralTester:
    """Testeur pour les workers éphémères en environnement local."""

    def __init__(self):
        self.sqs_client = boto3.client(
            "sqs",
            endpoint_url=AWS_ENDPOINT_URL,
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )

        # Configuration des queues
        self.queue_configs = {
            "rss-resolution-queue": {
                "worker_type": "rss",
                "test_message": {
                    "job_id": "test-rss-001",
                    "podcast_url": "https://feeds.megaphone.fm/the-daily",
                    "user_id": "test-user",
                    "email": "test@example.com"
                }
            },
            "audio-download-queue": {
                "worker_type": "download",
                "test_message": {
                    "job_id": "test-download-001",
                    "audio_url": "https://example.com/test-audio.mp3",
                    "podcast_title": "Test Podcast",
                    "episode_title": "Test Episode"
                }
            },
            "transcription-queue": {
                "worker_type": "whisper",
                "test_message": {
                    "job_id": "test-whisper-001",
                    "audio_file_key": "test-audio.mp3",
                    "podcast_title": "Test Podcast",
                    "episode_title": "Test Episode"
                }
            },
            "summarization-queue": {
                "worker_type": "summarization",
                "test_message": {
                    "job_id": "test-summary-001",
                    "transcript": "This is a test transcript for summarization testing purposes.",
                    "podcast_title": "Test Podcast",
                    "episode_title": "Test Episode"
                }
            },
            "email-notification-queue": {
                "worker_type": "email",
                "test_message": {
                    "job_id": "test-email-001",
                    "user_email": "test@example.com",
                    "summary": "This is a test summary.",
                    "podcast_title": "Test Podcast",
                    "episode_title": "Test Episode",
                    "success": True
                }
            }
        }

        self.queue_urls = {}

    def check_localstack(self) -> bool:
        """Vérifie que LocalStack est accessible."""
        try:
            self.sqs_client.list_queues()
            logger.info("LocalStack is accessible")
            return True
        except Exception as e:
            logger.error(f"LocalStack is not accessible: {e}")
            return False

    def setup_queues(self) -> bool:
        """Crée les queues SQS nécessaires."""
        logger.info("Setting up SQS queues...")

        for queue_name in self.queue_configs.keys():
            try:
                # Essaie d'obtenir l'URL de la queue existante
                response = self.sqs_client.get_queue_url(QueueName=queue_name)
                self.queue_urls[queue_name] = response["QueueUrl"]
                logger.info(f"Queue {queue_name} already exists")
            except ClientError:
                # Crée la queue si elle n'existe pas
                try:
                    response = self.sqs_client.create_queue(
                        QueueName=queue_name,
                        Attributes={
                            "VisibilityTimeoutSeconds": "300",
                            "MessageRetentionPeriod": "1209600",  # 14 days
                        }
                    )
                    self.queue_urls[queue_name] = response["QueueUrl"]
                    logger.info(f"Created queue {queue_name}")
                except ClientError as e:
                    logger.error(f"Failed to create queue {queue_name}: {e}")
                    return False

        logger.info("All queues are ready")
        return True

    def send_test_message(self, queue_name: str) -> bool:
        """Envoie un message de test dans une queue."""
        if queue_name not in self.queue_urls:
            logger.error(f"Queue {queue_name} not found")
            return False

        try:
            message_body = json.dumps(self.queue_configs[queue_name]["test_message"])
            self.sqs_client.send_message(
                QueueUrl=self.queue_urls[queue_name],
                MessageBody=message_body
            )
            logger.info(f"Sent test message to {queue_name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to send message to {queue_name}: {e}")
            return False

    def get_queue_message_count(self, queue_name: str) -> int:
        """Obtient le nombre de messages dans une queue."""
        if queue_name not in self.queue_urls:
            return 0

        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=self.queue_urls[queue_name],
                AttributeNames=["ApproximateNumberOfMessages"]
            )
            return int(response["Attributes"]["ApproximateNumberOfMessages"])
        except ClientError as e:
            logger.error(f"Failed to get message count for {queue_name}: {e}")
            return 0

    def run_ephemeral_worker(self, worker_type: str, queue_name: str) -> bool:
        """Lance un worker éphémère via Docker."""
        logger.info(f"Starting ephemeral {worker_type} worker for {queue_name}...")

        # Variables d'environnement pour le worker
        env_vars = {
            "WORKER_TYPE": worker_type,
            "QUEUE_URL": self.queue_urls[queue_name],
            "QUEUE_NAME": queue_name,
            "EPHEMERAL_MODE": "true",
            "AWS_ENDPOINT_URL": AWS_ENDPOINT_URL,
            "AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY_ID,
            "AWS_SECRET_ACCESS_KEY": AWS_SECRET_ACCESS_KEY,
            "AWS_DEFAULT_REGION": AWS_REGION,
            "MAX_PROCESSING_TIME": "300",  # 5 minutes pour les tests
            "HEARTBEAT_INTERVAL": "30",
            "VISIBILITY_TIMEOUT": "120",
        }

        # Prépare la commande Docker
        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "media-summarizer-project_default",
        ]

        # Ajoute les variables d'environnement
        for key, value in env_vars.items():
            docker_cmd.extend(["-e", f"{key}={value}"])

        # Ajoute l'image et la commande
        docker_cmd.extend([
            "media-summarizer-project-ephemeral-worker",
            "python", "-m", "media_summarizer.workers.ephemeral_worker"
        ])

        try:
            # Lance le worker
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=360  # 6 minutes timeout
            )

            if result.returncode == 0:
                logger.info(f"Worker {worker_type} completed successfully")
                logger.debug(f"Worker output: {result.stdout}")
                return True
            else:
                logger.error(f"Worker {worker_type} failed with return code {result.returncode}")
                logger.error(f"Worker stderr: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"Worker {worker_type} timed out")
            return False
        except Exception as e:
            logger.error(f"Failed to run worker {worker_type}: {e}")
            return False

    def test_single_worker(self, queue_name: str) -> bool:
        """Teste un seul type de worker."""
        logger.info(f"\n{'='*50}")
        logger.info(f"Testing {queue_name}")
        logger.info(f"{'='*50}")

        worker_type = self.queue_configs[queue_name]["worker_type"]

        # Vérifie que la queue est vide
        initial_count = self.get_queue_message_count(queue_name)
        if initial_count > 0:
            logger.warning(f"Queue {queue_name} has {initial_count} messages, continuing anyway")

        # Envoie un message de test
        if not self.send_test_message(queue_name):
            logger.error(f"Failed to send test message to {queue_name}")
            return False

        # Vérifie que le message est dans la queue
        time.sleep(2)
        message_count = self.get_queue_message_count(queue_name)
        if message_count == 0:
            logger.error(f"Message not found in {queue_name}")
            return False

        logger.info(f"Message sent successfully, {message_count} messages in queue")

        # Lance le worker éphémère
        success = self.run_ephemeral_worker(worker_type, queue_name)

        if success:
            # Vérifie que le message a été traité
            time.sleep(2)
            final_count = self.get_queue_message_count(queue_name)
            if final_count < message_count:
                logger.info(f"✅ Worker {worker_type} processed message successfully")
                return True
            else:
                logger.error(f"❌ Message was not processed by {worker_type} worker")
                return False
        else:
            logger.error(f"❌ Worker {worker_type} failed to run")
            return False

    def test_all_workers(self) -> bool:
        """Teste tous les types de workers."""
        logger.info("Starting comprehensive ephemeral worker test...")

        if not self.check_localstack():
            logger.error("LocalStack not available, stopping tests")
            return False

        if not self.setup_queues():
            logger.error("Failed to setup queues, stopping tests")
            return False

        # Teste chaque worker individuellement
        results = {}
        for queue_name in self.queue_configs.keys():
            try:
                results[queue_name] = self.test_single_worker(queue_name)
            except Exception as e:
                logger.error(f"Test for {queue_name} failed with exception: {e}")
                results[queue_name] = False

            # Petite pause entre les tests
            time.sleep(5)

        # Résumé des résultats
        logger.info(f"\n{'='*50}")
        logger.info("TEST SUMMARY")
        logger.info(f"{'='*50}")

        passed = sum(1 for success in results.values() if success)
        total = len(results)

        for queue_name, success in results.items():
            status = "✅ PASSED" if success else "❌ FAILED"
            logger.info(f"{queue_name}: {status}")

        logger.info(f"\nOverall: {passed}/{total} tests passed")
        logger.info(f"Success rate: {(passed/total)*100:.1f}%")

        return passed == total

    def cleanup(self):
        """Nettoie les ressources de test."""
        logger.info("Cleaning up test resources...")

        for queue_name, queue_url in self.queue_urls.items():
            try:
                # Purge la queue
                self.sqs_client.purge_queue(QueueUrl=queue_url)
                logger.info(f"Purged queue {queue_name}")
            except ClientError as e:
                logger.warning(f"Failed to purge queue {queue_name}: {e}")

    def build_docker_image(self) -> bool:
        """Construit l'image Docker pour les tests."""
        logger.info("Building ephemeral worker Docker image...")

        try:
            result = subprocess.run([
                "docker", "build",
                "-f", "infrastructure/docker/ephemeral-worker.Dockerfile",
                "-t", "media-summarizer-project-ephemeral-worker",
                "."
            ], capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                logger.info("Docker image built successfully")
                return True
            else:
                logger.error(f"Failed to build Docker image: {result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Docker build timed out")
            return False
        except Exception as e:
            logger.error(f"Error building Docker image: {e}")
            return False


def main():
    """Point d'entrée principal."""
    import argparse

    parser = argparse.ArgumentParser(description="Test ephemeral workers locally")
    parser.add_argument(
        "--worker",
        choices=["rss", "download", "whisper", "summarization", "email"],
        help="Test specific worker type only"
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build Docker image before testing"
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip cleanup after tests"
    )

    args = parser.parse_args()

    tester = LocalEphemeralTester()

    try:
        # Construit l'image Docker si demandé
        if args.build:
            if not tester.build_docker_image():
                logger.error("Failed to build Docker image")
                return 1

        # Vérifie la disponibilité de LocalStack
        if not tester.check_localstack():
            logger.error("Please start LocalStack first with: docker-compose -f docker-compose.dev.yml up localstack")
            return 1

        # Configure les queues
        if not tester.setup_queues():
            logger.error("Failed to setup queues")
            return 1

        # Lance les tests
        if args.worker:
            # Teste un worker spécifique
            queue_mapping = {
                "rss": "rss-resolution-queue",
                "download": "audio-download-queue",
                "whisper": "transcription-queue",
                "summarization": "summarization-queue",
                "email": "email-notification-queue"
            }
            queue_name = queue_mapping[args.worker]
            success = tester.test_single_worker(queue_name)
        else:
            # Teste tous les workers
            success = tester.test_all_workers()

        # Nettoie les ressources
        if not args.no_cleanup:
            tester.cleanup()

        return 0 if success else 1

    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
        if not args.no_cleanup:
            tester.cleanup()
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if not args.no_cleanup:
            tester.cleanup()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
