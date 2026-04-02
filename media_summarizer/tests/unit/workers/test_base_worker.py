"""
Tests unitaires pour base_worker.

Ces tests vérifient que la logique de retry, logging et gestion d'erreur
du base_worker fonctionne correctement avec des mocks.
"""
import asyncio
import json
import pytest
import boto3
from unittest.mock import AsyncMock, MagicMock, patch
from media_summarizer.workers.base_worker import (
    process_message_with_retry,
    get_sqs_receive_params,
    send_error_notification
)


@pytest.fixture
def sqs_client():
    """Client SQS mocké."""
    return MagicMock()


@pytest.fixture
def test_queue_url():
    """URL de queue de test."""
    return "http://localhost:4566/000000000000/test-queue"


@pytest.fixture
def test_message():
    """Message SQS de test."""
    return {
        "Body": json.dumps({
            "job_id": "test-job-123",
            "test_data": "sample"
        }),
        "ReceiptHandle": "test-receipt-handle",
        "Attributes": {"ApproximateReceiveCount": "1"}
    }


class TestBaseWorker:
    """Tests unitaires pour base_worker."""

    @pytest.mark.asyncio
    async def test_successful_message_processing(self, sqs_client, test_queue_url, test_message):
        """Test que le traitement réussi d'un message fonctionne correctement."""
        # Mock processor qui réussit
        async def mock_processor(message):
            assert message == test_message
            return True

        # Mock delete
        sqs_client.delete_message = MagicMock()

        # Traiter le message
        with patch('media_summarizer.workers.base_worker.sqs.delete_message') as mock_delete:
            result = await process_message_with_retry(
                message=test_message,
                processor=mock_processor,
                queue_name="test-queue",
                max_retries=3,
                worker_name="test-worker"
            )

            # Vérifications
            assert result is True
            mock_delete.assert_called_once_with(
                queue_name="test-queue",
                receipt_handle="test-receipt-handle"
            )

    @pytest.mark.asyncio
    async def test_failed_message_retry_logic(self, sqs_client, test_queue_url):
        """Test que la logique de retry fonctionne correctement."""
        # Message avec plusieurs tentatives
        test_message = {
            "Body": json.dumps({"job_id": "test-retry-456"}),
            "ReceiptHandle": "test-receipt-retry",
            "Attributes": {"ApproximateReceiveCount": "2"}  # 2ème tentative
        }

        # Mock processor qui échoue
        async def failing_processor(message):
            raise Exception("Simulated failure")

        # Mock delete (ne devrait pas être appelé)
        sqs_client.delete_message = MagicMock()

        # Traiter le message
        with patch('media_summarizer.workers.base_worker.sqs.delete_message') as mock_delete:
            result = await process_message_with_retry(
                message=test_message,
                processor=failing_processor,
                queue_name="test-queue",
                max_retries=3,
                worker_name="test-worker"
            )

            # Vérifications
            assert result is False
            # Delete ne devrait pas être appelé car on n'a pas atteint max_retries
            mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_structured_logging_context(self, sqs_client, test_queue_url, test_message, caplog):
        """Test que le logging structuré inclut le bon contexte."""
        import logging
        caplog.set_level(logging.INFO, logger="media_summarizer.workers.base_worker")

        # Mock processor qui réussit
        async def mock_processor(message):
            return True

        sqs_client.delete_message = MagicMock()

        # Traiter le message
        with patch('media_summarizer.workers.base_worker.sqs.delete_message'):
            await process_message_with_retry(
                message=test_message,
                processor=mock_processor,
                queue_name="test-queue",
                max_retries=3,
                worker_name="test-worker"
            )

        # Vérifier les logs structurés
        log_messages = [record.message for record in caplog.records]
        
        # Devrait avoir des logs avec contexte worker
        worker_logs = [msg for msg in log_messages if "[test-worker]" in msg]
        assert len(worker_logs) >= 2, "Should have worker context logs"
        
        # Vérifier les messages spécifiques
        assert any("Processing message" in msg for msg in worker_logs)
        assert any("Message processed successfully" in msg for msg in worker_logs)

    def test_sqs_receive_params_configuration(self):
        """Test que les paramètres SQS sont correctement configurés."""
        params = get_sqs_receive_params(visibility_timeout=300)
        
        expected_params = {
            "MaxNumberOfMessages": 1,
            "WaitTimeSeconds": 20,
            "VisibilityTimeout": 300,
            "AttributeNames": ['ApproximateReceiveCount']
        }
        
        assert params == expected_params

    @pytest.mark.asyncio
    async def test_error_notification_sending(self, sqs_client):
        """Test que les notifications d'erreur sont envoyées correctement."""
        # Mock get_queue_url et send_message
        sqs_client.get_queue_url = MagicMock(return_value={
            'QueueUrl': 'http://localhost:4566/000000000000/email-notification-queue'
        })
        sqs_client.send_message = MagicMock()

        # Envoyer notification d'erreur
        with patch('media_summarizer.workers.base_worker.sqs.send_message') as mock_send:
            await send_error_notification(
                job_id="test-error-789",
                error_message="Test error message",
                step="rss-resolution"
            )

            # Vérifications
            mock_send.assert_called_once()
            
            # Vérifier le contenu du message
            call_args = mock_send.call_args
            queue_name = call_args.kwargs['queue_name']
            message_body = call_args.kwargs['message_body']
            
            assert queue_name == "email-notification-queue"
            assert message_body['job_id'] == "test-error-789"
            assert message_body['error'] == "Error"
            assert message_body['step'] == "rss-resolution"
            assert message_body['success'] is False

    @pytest.mark.asyncio
    async def test_worker_resilience_to_malformed_messages(self, sqs_client, test_queue_url):
        """Test que le worker gère correctement les messages malformés."""
        # Message avec JSON invalide
        malformed_message = {
            "Body": "invalid json {",
            "ReceiptHandle": "test-receipt-malformed",
            "Attributes": {"ApproximateReceiveCount": "1"}
        }

        # Mock processor qui va recevoir le message malformé et échouer
        async def mock_processor(message):
            # Le processor va essayer de parser le JSON et échouer
            body = json.loads(message["Body"])  # Ceci va lever une exception
            return True

        sqs_client.delete_message = MagicMock()

        # Traiter le message malformé
        with patch('media_summarizer.workers.base_worker.sqs.delete_message') as mock_delete:
            result = await process_message_with_retry(
                message=malformed_message,
                processor=mock_processor,
                queue_name="test-queue",
                max_retries=3,
                worker_name="test-worker"
            )

            # Le message devrait être traité comme un échec
            assert result is False
            # Pas de suppression car c'est la première tentative
            mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_concurrent_message_processing(self, sqs_client, test_queue_url):
        """Test que le traitement concurrent de messages fonctionne."""
        messages = []
        for i in range(3):
            messages.append({
                "Body": json.dumps({"job_id": f"concurrent-job-{i}"}),
                "ReceiptHandle": f"receipt-{i}",
                "Attributes": {"ApproximateReceiveCount": "1"}
            })

        processed_jobs = []

        async def tracking_processor(message):
            body = json.loads(message["Body"])
            processed_jobs.append(body["job_id"])
            await asyncio.sleep(0.1)  # Simule du travail
            return True

        sqs_client.delete_message = MagicMock()

        # Traiter les messages en parallèle
        with patch('media_summarizer.workers.base_worker.sqs.delete_message') as mock_delete:
            tasks = []
            for message in messages:
                task = process_message_with_retry(
                    message=message,
                    processor=tracking_processor,
                    queue_name="test-queue",
                    max_retries=3,
                    worker_name="test-worker"
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks)

            # Vérifications
            assert all(results), "All messages should be processed successfully"
            assert len(processed_jobs) == 3, "All jobs should be processed"
            assert mock_delete.call_count == 3, "All messages should be deleted"

    @pytest.mark.asyncio
    async def test_max_retries_reached_deletes_message(self, sqs_client, test_queue_url):
        """Test qu'après max_retries, le message est supprimé pour éviter les boucles infinies."""
        # Message qui a atteint le maximum de tentatives
        max_retry_message = {
            "Body": json.dumps({"job_id": "max-retry-job"}),
            "ReceiptHandle": "test-receipt-max",
            "Attributes": {"ApproximateReceiveCount": "3"}  # = max_retries
        }

        # Mock processor qui échoue toujours
        async def always_failing_processor(message):
            raise Exception("Permanent failure")

        sqs_client.delete_message = MagicMock()

        # Traiter le message
        with patch('media_summarizer.workers.base_worker.sqs.delete_message') as mock_delete:
            result = await process_message_with_retry(
                message=max_retry_message,
                processor=always_failing_processor,
                queue_name="test-queue",
                max_retries=3,
                worker_name="test-worker"
            )

            # Vérifications
            assert result is False
            # Le message devrait être supprimé pour éviter la boucle infinie
            mock_delete.assert_called_once_with(
                queue_name="test-queue",
                receipt_handle="test-receipt-max"
            )
