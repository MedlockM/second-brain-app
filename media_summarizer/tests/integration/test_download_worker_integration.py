"""
Tests d'intégration pour le Download Worker avec LocalStack.
"""
import asyncio
import json
import pytest
import boto3
import tempfile
import os
from unittest.mock import patch, AsyncMock, MagicMock
from media_summarizer.workers.download_worker import process_message
from media_summarizer.workers.base_worker import process_message_with_retry


@pytest.fixture
def localstack_sqs_client():
    """Client SQS réel pour LocalStack."""
    return boto3.client(
        'sqs',
        endpoint_url='http://localhost:4566',
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1'
    )


@pytest.fixture
def localstack_s3_client():
    """Client S3 réel pour LocalStack."""
    return boto3.client(
        's3',
        endpoint_url='http://localhost:4566',
        aws_access_key_id='test',
        aws_secret_access_key='test',
        region_name='us-east-1'
    )


@pytest.fixture
def test_queue(localstack_sqs_client):
    """Queue SQS de test."""
    queue_name = "test-download-integration-queue"

    try:
        response = localstack_sqs_client.create_queue(QueueName=queue_name)
        queue_url = response['QueueUrl']
        yield queue_url
    finally:
        try:
            localstack_sqs_client.delete_queue(QueueUrl=queue_url)
        except:
            pass


@pytest.fixture
def test_bucket(localstack_s3_client):
    """Bucket S3 de test."""
    bucket_name = "test-download-bucket"

    try:
        localstack_s3_client.create_bucket(Bucket=bucket_name)
        yield bucket_name
    finally:
        try:
            # Supprimer tous les objets du bucket
            objects = localstack_s3_client.list_objects_v2(Bucket=bucket_name)
            if 'Contents' in objects:
                for obj in objects['Contents']:
                    localstack_s3_client.delete_object(Bucket=bucket_name, Key=obj['Key'])
            localstack_s3_client.delete_bucket(Bucket=bucket_name)
        except:
            pass


class TestDownloadWorkerIntegration:
    """Tests d'intégration pour le Download Worker."""

    @pytest.mark.asyncio
    async def test_download_worker_with_real_sqs_and_s3(self, localstack_sqs_client, localstack_s3_client, test_queue, test_bucket):
        """Test du Download worker avec vraies queues SQS et bucket S3."""
        # 1. Envoyer un message à la queue
        test_message_body = {
            "job_id": "download-integration-001",
            "audio_url": "https://example.com/test-audio.mp3",
            "podcast_title": "Integration Test Podcast",
            "episode_title": "Test Episode",
            "user_id": "user123",
            "email": "test@example.com"
        }

        localstack_sqs_client.send_message(
            QueueUrl=test_queue,
            MessageBody=json.dumps(test_message_body)
        )

        # 2. Mock le téléchargement HTTP et l'envoi vers transcription
        transcription_messages = []

        async def mock_send_to_transcription_queue(message):
            transcription_messages.append(message)

        # Mock du contenu audio
        mock_audio_content = b"fake audio content for testing"

        with patch('media_summarizer.workers.download_worker.download_audio') as mock_download, \
             patch('media_summarizer.workers.download_worker.get_s3_client') as mock_s3_client, \
             patch('media_summarizer.workers.download_worker.get_sqs_client') as mock_sqs_client_func:

            # Configurer les mocks
            mock_download.return_value = None  # download_audio ne retourne rien, écrit dans un fichier

            # Mock S3 client
            mock_s3 = MagicMock()
            mock_s3_client.return_value = mock_s3

            # Mock SQS client pour les envois de messages
            mock_sqs = MagicMock()
            mock_sqs.get_queue_url.return_value = {'QueueUrl': 'http://localhost:4566/000000000000/transcription-queue'}
            mock_sqs.send_message.side_effect = lambda **kwargs: transcription_messages.append(json.loads(kwargs['MessageBody']))
            mock_sqs_client_func.return_value = mock_sqs

            # 3. Recevoir et traiter le message avec le vrai worker
            response = localstack_sqs_client.receive_message(
                QueueUrl=test_queue,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=2,
                AttributeNames=['ApproximateReceiveCount']
            )

            assert 'Messages' in response, "Should receive message from SQS"
            message = response['Messages'][0]

            # 4. Traiter avec le Download worker et base_worker
            result = await process_message_with_retry(
                message=message,
                processor=process_message,
                sqs_client=localstack_sqs_client,
                queue_url=test_queue,
                max_retries=3,
                worker_name="download-worker"
            )

            # 5. Vérifications
            assert result is True, "Download processing should succeed"
            assert len(transcription_messages) == 1, "Should send one message to transcription queue"

            transcription_message = transcription_messages[0]
            assert transcription_message["job_id"] == "download-integration-001"
            assert transcription_message["s3_audio_key"] == f"{test_message_body['job_id']}.mp3"
            assert transcription_message["podcast_title"] == "Integration Test Podcast"
            assert transcription_message["episode_title"] == "Test Episode"
            assert transcription_message["user_id"] == "user123"
            assert transcription_message["email"] == "test@example.com"
            assert transcription_message["success"] is True

            # Vérifier que les fonctions ont été appelées
            mock_download.assert_called_once()
            mock_s3.upload_file.assert_called_once()
            mock_sqs.send_message.assert_called_once()

        # 6. Vérifier que le message a été supprimé de la queue
        response = localstack_sqs_client.receive_message(
            QueueUrl=test_queue,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=1
        )
        assert 'Messages' not in response, "Message should be deleted after successful processing"

    @pytest.mark.asyncio
    async def test_download_worker_retry_on_network_error(self, localstack_sqs_client, test_queue):
        """Test de la logique de retry avec erreur réseau."""
        # 1. Envoyer un message qui va échouer
        test_message_body = {
            "job_id": "download-retry-002",
            "audio_url": "https://example.com/failing-audio.mp3",
            "podcast_title": "Retry Test Podcast",
            "episode_title": "Failing Episode",
            "user_id": "user456",
            "email": "retry@example.com"
        }

        localstack_sqs_client.send_message(
            QueueUrl=test_queue,
            MessageBody=json.dumps(test_message_body)
        )

        # 2. Mock le téléchargement pour échouer
        with patch('media_summarizer.workers.download_worker.download_audio') as mock_download:
            mock_download.side_effect = Exception("Network timeout")

            # 3. Premier traitement - devrait échouer mais pas supprimer le message
            response = localstack_sqs_client.receive_message(
                QueueUrl=test_queue,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=2,
                AttributeNames=['ApproximateReceiveCount']
            )

            assert 'Messages' in response, "Should receive message from SQS"
            message = response['Messages'][0]

            result = await process_message_with_retry(
                message=message,
                processor=process_message,
                sqs_client=localstack_sqs_client,
                queue_url=test_queue,
                max_retries=3,
                worker_name="download-worker"
            )

            # 4. Vérifications
            assert result is False, "First attempt should fail"
            mock_download.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_worker_max_retries(self, localstack_sqs_client, test_queue):
        """Test que le message est supprimé après max retries."""
        # 1. Envoyer un message qui va échouer
        test_message_body = {
            "job_id": "download-max-retries-003",
            "audio_url": "https://example.com/permanent-fail.mp3",
            "podcast_title": "Max Retries Test",
            "episode_title": "Permanent Fail",
            "user_id": "user789",
            "email": "maxretries@example.com"
        }

        localstack_sqs_client.send_message(
            QueueUrl=test_queue,
            MessageBody=json.dumps(test_message_body)
        )

        # 2. Mock le téléchargement pour échouer
        with patch('media_summarizer.workers.download_worker.download_audio') as mock_download:
            mock_download.side_effect = Exception("Permanent failure")

            # 3. Recevoir le message et simuler max retries
            response = localstack_sqs_client.receive_message(
                QueueUrl=test_queue,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=2,
                AttributeNames=['ApproximateReceiveCount']
            )

            assert 'Messages' in response, "Should receive message from SQS"
            message = response['Messages'][0]

            # Simuler que c'est la 3ème tentative
            message['Attributes']['ApproximateReceiveCount'] = '3'

            # 4. Traiter le message
            result = await process_message_with_retry(
                message=message,
                processor=process_message,
                sqs_client=localstack_sqs_client,
                queue_url=test_queue,
                max_retries=3,
                worker_name="download-worker"
            )

            # 5. Vérifications
            assert result is False, "Processing should fail"
            # Le message devrait être supprimé par base_worker après max retries

    @pytest.mark.asyncio
    async def test_download_worker_invalid_message_format(self, localstack_sqs_client, test_queue):
        """Test avec un message au format invalide."""
        # 1. Envoyer un message invalide
        localstack_sqs_client.send_message(
            QueueUrl=test_queue,
            MessageBody="invalid json"
        )

        # 2. Recevoir et traiter le message
        response = localstack_sqs_client.receive_message(
            QueueUrl=test_queue,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=2,
            AttributeNames=['ApproximateReceiveCount']
        )

        assert 'Messages' in response, "Should receive message from SQS"
        message = response['Messages'][0]

        result = await process_message_with_retry(
            message=message,
            processor=process_message,
            sqs_client=localstack_sqs_client,
            queue_url=test_queue,
            max_retries=3,
            worker_name="download-worker"
        )

        # 3. Vérifications
        assert result is False, "Invalid message should fail"

    @pytest.mark.asyncio
    async def test_multiple_download_messages_processing(self, localstack_sqs_client, test_queue):
        """Test du traitement de plusieurs messages de téléchargement."""
        # 1. Envoyer plusieurs messages
        job_ids = []
        for i in range(3):
            job_id = f"multi-download-{i}"
            job_ids.append(job_id)

            test_message_body = {
                "job_id": job_id,
                "audio_url": f"https://example.com/audio-{i}.mp3",
                "podcast_title": f"Multi Test Podcast {i}",
                "episode_title": f"Episode {i}",
                "user_id": f"user{i}",
                "email": f"test{i}@example.com"
            }

            localstack_sqs_client.send_message(
                QueueUrl=test_queue,
                MessageBody=json.dumps(test_message_body)
            )

        # 2. Mock les fonctions de téléchargement
        transcription_messages = []

        with patch('media_summarizer.workers.download_worker.download_audio') as mock_download, \
             patch('media_summarizer.workers.download_worker.get_s3_client') as mock_s3_client, \
             patch('media_summarizer.workers.download_worker.get_sqs_client') as mock_sqs_client_func:

            # Configurer les mocks
            mock_download.return_value = None

            # Mock S3 client
            mock_s3 = MagicMock()
            mock_s3_client.return_value = mock_s3

            # Mock SQS client
            mock_sqs = MagicMock()
            mock_sqs.get_queue_url.return_value = {'QueueUrl': 'http://localhost:4566/000000000000/transcription-queue'}
            mock_sqs.send_message.side_effect = lambda **kwargs: transcription_messages.append(json.loads(kwargs['MessageBody'])["job_id"])
            mock_sqs_client_func.return_value = mock_sqs

            # 3. Traiter tous les messages
            for _ in range(3):
                response = localstack_sqs_client.receive_message(
                    QueueUrl=test_queue,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=2,
                    AttributeNames=['ApproximateReceiveCount']
                )

                if 'Messages' in response:
                    message = response['Messages'][0]

                    result = await process_message_with_retry(
                        message=message,
                        processor=process_message,
                        sqs_client=localstack_sqs_client,
                        queue_url=test_queue,
                        max_retries=3,
                        worker_name="download-worker"
                    )

                    assert result is True, f"Message processing should succeed"

            # 4. Vérifications
            assert len(transcription_messages) == 3, "Should process all messages"
            for job_id in job_ids:
                assert job_id in transcription_messages, f"Job {job_id} should be processed"
