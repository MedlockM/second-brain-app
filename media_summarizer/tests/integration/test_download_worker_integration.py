"""
Tests d'intégration pour le Download Worker avec LocalStack.
"""
import asyncio
import json
import pytest
import boto3
import tempfile
import os
import uuid
from unittest.mock import patch
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


@pytest.fixture(autouse=True)
def configure_utils_for_localstack():
    """Configure les utilitaires async SQS/S3 pour pointer vers LocalStack."""
    from media_summarizer.utils import sqs as utils_sqs, s3 as utils_s3
    utils_sqs.AWS_ENDPOINT_URL = 'http://localhost:4566'
    utils_sqs.AWS_REGION = 'us-east-1'
    utils_s3.AWS_ENDPOINT_URL = 'http://localhost:4566'
    utils_s3.AWS_REGION = 'us-east-1'
    # S'assurer que des credentials existent pour les clients aiobotocore/boto3
    os.environ.setdefault('AWS_ACCESS_KEY_ID', 'test')
    os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'test')
    os.environ.setdefault('AWS_DEFAULT_REGION', 'us-east-1')
    os.environ.setdefault('AWS_REGION', 'us-east-1')
    yield


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
    async def test_download_worker_with_real_sqs_and_s3(self, localstack_sqs_client, localstack_s3_client, test_queue, test_bucket, monkeypatch):
        """Test du Download worker avec vraies queues SQS et bucket S3."""
        # Utiliser le bucket de test dans le worker
        from media_summarizer.workers import download_worker as dw
        dw.AUDIO_BUCKET = test_bucket

        # Créer la queue de transcription réelle
        # Créer une queue de transcription unique par test et rediriger l'utilitaire vers celle-ci
        unique_trans_q_name = f"transcription-queue-{uuid.uuid4().hex[:8]}"
        trans_q_url = localstack_sqs_client.create_queue(QueueName=unique_trans_q_name)["QueueUrl"]

        # Monkeypatch le resolveur d'URL pour que 'transcription-queue' pointe vers notre queue unique
        from media_summarizer.utils import sqs as utils_sqs
        original_get_queue_url = utils_sqs.get_queue_url
        def _patched_get_queue_url(name: str) -> str:
            if name == "transcription-queue":
                return trans_q_url
            return original_get_queue_url(name)
        monkeypatch.setattr(utils_sqs, "get_queue_url", _patched_get_queue_url)

        # Purger la queue pour éviter des messages résiduels/inflight d'autres tests
        try:
            localstack_sqs_client.purge_queue(QueueUrl=trans_q_url)
        except Exception:
            pass

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

        # 2. Mock le téléchargement HTTP uniquement (le reste utilise S3/SQS réels via utils)
        with patch('media_summarizer.workers.download_worker.download_audio') as mock_download:
            mock_download.return_value = None  # download_audio écrit normalement dans un fichier temporaire

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
                queue_name="test-download-integration-queue",
                max_retries=3,
                worker_name="download-worker"
            )

            # 5. Vérifications
            assert result is True, "Download processing should succeed"

            # Vérifier l'upload S3
            s3_objects = localstack_s3_client.list_objects_v2(Bucket=test_bucket)
            keys = [obj['Key'] for obj in s3_objects.get('Contents', [])]
            assert f"{test_message_body['job_id']}.mp3" in keys, "Uploaded audio not found in S3"

            # Vérifier le message envoyé à la queue de transcription (with retry to handle eventual consistency)
            transcription_message = None
            for _ in range(12):  # étend la fenêtre de retry (~24s)
                trans_resp = localstack_sqs_client.receive_message(
                    QueueUrl=trans_q_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=2
                )
                if 'Messages' in trans_resp and trans_resp.get('Messages'):
                    m = trans_resp['Messages'][0]
                    transcription_message = json.loads(m['Body'])
                    # Supprimer le message reçu pour éviter qu'il reste en "inflight"
                    localstack_sqs_client.delete_message(
                        QueueUrl=trans_q_url,
                        ReceiptHandle=m['ReceiptHandle']
                    )
                    break
            assert transcription_message is not None, "No message received from transcription queue after retries"
            assert transcription_message["job_id"] == "download-integration-001"
            assert transcription_message["audio_s3_key"] == f"{test_message_body['job_id']}.mp3"
            assert transcription_message["podcast_title"] == "Integration Test Podcast"
            assert transcription_message["episode_title"] == "Test Episode"
            assert transcription_message["user_id"] == "user123"
            assert transcription_message["email"] == "test@example.com"
            assert transcription_message["success"] is True

            # Vérifier que la fonction de téléchargement a bien été appelée
            mock_download.assert_called_once()

        # 6. Vérifier que le message a été supprimé de la queue
        response = localstack_sqs_client.receive_message(
            QueueUrl=test_queue,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=1
        )
        assert not response.get('Messages'), "Message should be deleted after successful processing"

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
                queue_name="test-download-integration-queue",
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
                queue_name="test-download-integration-queue",
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
            queue_name="test-download-integration-queue",
            max_retries=3,
            worker_name="download-worker"
        )

        # 3. Vérifications
        assert result is False, "Invalid message should fail"

    @pytest.mark.asyncio
    async def test_multiple_download_messages_processing(self, localstack_sqs_client, localstack_s3_client, test_queue, test_bucket, monkeypatch):
        """Test du traitement de plusieurs messages de téléchargement."""
        # Utiliser le bucket de test dans le worker
        from media_summarizer.workers import download_worker as dw
        dw.AUDIO_BUCKET = test_bucket

        # Créer la queue de transcription réelle
        # Créer une queue de transcription unique par test et rediriger l'utilitaire vers celle-ci
        unique_trans_q_name = f"transcription-queue-{uuid.uuid4().hex[:8]}"
        trans_q_url = localstack_sqs_client.create_queue(QueueName=unique_trans_q_name)["QueueUrl"]

        # Monkeypatch le resolveur d'URL pour que 'transcription-queue' pointe vers notre queue unique
        from media_summarizer.utils import sqs as utils_sqs
        original_get_queue_url = utils_sqs.get_queue_url
        def _patched_get_queue_url(name: str) -> str:
            if name == "transcription-queue":
                return trans_q_url
            return original_get_queue_url(name)
        monkeypatch.setattr(utils_sqs, "get_queue_url", _patched_get_queue_url)

        # Purger la queue pour éviter des messages résiduels/inflight d'autres tests
        try:
            localstack_sqs_client.purge_queue(QueueUrl=trans_q_url)
        except Exception:
            pass

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

        # 2. Mock la fonction de téléchargement uniquement
        with patch('media_summarizer.workers.download_worker.download_audio') as mock_download:
            mock_download.return_value = None

            # 3. Traiter tous les messages jusqu'à en avoir effectivement 3
            processed = 0
            attempts = 0
            while processed < 3 and attempts < 20:
                response = localstack_sqs_client.receive_message(
                    QueueUrl=test_queue,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=2,
                    AttributeNames=['ApproximateReceiveCount']
                )

                if 'Messages' in response:
                    for message in response['Messages']:
                        result = await process_message_with_retry(
                            message=message,
                            processor=process_message,
                            queue_name="test-download-integration-queue",
                            max_retries=3,
                            worker_name="download-worker"
                        )
                        assert result is True, f"Message processing should succeed"
                        processed += 1
                attempts += 1

        # 4. Vérifications
        # Vérifier l'envoi de 3 messages vers la queue de transcription
        all_received = []
        attempts = 0
        while len(all_received) < 3 and attempts < 10:
            trans_resp = localstack_sqs_client.receive_message(
                QueueUrl=trans_q_url,
                MaxNumberOfMessages=3,
                WaitTimeSeconds=2
            )
            msgs = trans_resp.get('Messages', [])
            for m in msgs:
                all_received.append(json.loads(m['Body']))
                # Supprimer chaque message reçu pour éviter l'invisibilité
                localstack_sqs_client.delete_message(
                    QueueUrl=trans_q_url,
                    ReceiptHandle=m['ReceiptHandle']
                )
            attempts += 1
        assert len(all_received) == 3, f"Should process all messages, got {len(all_received)}"
        received_job_ids = {m["job_id"] for m in all_received}
        assert received_job_ids == set(job_ids), "All job IDs should be forwarded to transcription queue"
