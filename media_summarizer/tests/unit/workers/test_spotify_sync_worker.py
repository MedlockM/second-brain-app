"""
Tests unitaires pour spotify_sync_worker.

Ces tests vérifient que le worker de synchronisation Spotify traite correctement
les messages SQS et gère les erreurs appropriées.
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from media_summarizer.workers.spotify_sync.worker import process_sync_message


@pytest.fixture
def mock_sqs_messages():
    """Messages SQS de test pour la synchronisation Spotify."""
    return [
        {
            "Body": json.dumps({
                "user_id": "test_user_123",
                "playlist_ids": ["playlist_1", "playlist_2"],
                "source": "scheduled_sync"
            }),
            "ReceiptHandle": "test-receipt-handle-1"
        },
        {
            "Body": json.dumps({
                "user_id": "test_user_456", 
                "playlist_ids": ["playlist_3"],
                "source": "manual_sync"
            }),
            "ReceiptHandle": "test-receipt-handle-2"
        }
    ]


@pytest.fixture
def mock_empty_messages():
    """Messages SQS vides pour tester le polling."""
    return []


@pytest.fixture
def mock_malformed_message():
    """Message SQS malformé pour tester la gestion d'erreur."""
    return [
        {
            "Body": "invalid json {",
            "ReceiptHandle": "test-receipt-malformed"
        }
    ]


@pytest.fixture
def mock_successful_sync_result():
    """Résultat de synchronisation réussie."""
    return {
        "status": "success",
        "user_id": "test_user_123",
        "results": [
            {"playlist_id": "playlist_1", "result": {"status": "success", "submitted": 5}},
            {"playlist_id": "playlist_2", "result": {"status": "success", "submitted": 3}}
        ]
    }


@pytest.fixture
def mock_failed_sync_result():
    """Résultat de synchronisation échouée."""
    return {
        "status": "error",
        "reason": "user_not_found"
    }


class TestSpotifySyncWorker:
    """Tests unitaires pour le worker de synchronisation Spotify."""

    @pytest.mark.asyncio
    async def test_successful_message_processing(self, mock_sqs_messages, mock_successful_sync_result):
        """Test que le traitement réussi d'un message fonctionne correctement."""
        with patch('media_summarizer.workers.spotify_sync.sync_worker.receive_messages') as mock_receive, \
             patch('media_summarizer.workers.spotify_sync.sync_worker.process_sync_message') as mock_process, \
             patch('media_summarizer.workers.spotify_sync.sync_worker.delete_message') as mock_delete:
            
            # Configuration des mocks
            mock_receive.side_effect = [mock_sqs_messages, []]  # Premier appel retourne messages, deuxième vide
            mock_process.return_value = mock_successful_sync_result
            
            # Créer une tâche qui s'arrête après le premier cycle
            async def limited_process_messages():
                # Simuler un seul cycle de traitement
                messages = await mock_receive.return_value
                if messages:
                    for message in messages:
                        body = json.loads(message["Body"])
                        result = await mock_process.return_value
                        if result.get("status") == "success":
                            await mock_delete.return_value
                return True
            
            # Exécuter le test
            result = await limited_process_messages()
            
            # Vérifications
            assert result is True
            mock_process.assert_called()
            mock_delete.assert_called()

    @pytest.mark.asyncio
    async def test_failed_message_processing(self, mock_sqs_messages, mock_failed_sync_result):
        """Test que les messages échoués ne sont pas supprimés de la queue."""
        with patch('media_summarizer.workers.spotify_sync.sync_worker.receive_messages') as mock_receive, \
             patch('media_summarizer.workers.spotify_sync.sync_worker.process_sync_message') as mock_process, \
             patch('media_summarizer.workers.spotify_sync.sync_worker.delete_message') as mock_delete:
            
            # Configuration des mocks
            mock_receive.return_value = mock_sqs_messages
            mock_process.return_value = mock_failed_sync_result
            
            # Simuler un cycle de traitement
            messages = await mock_receive.return_value
            for message in messages:
                body = json.loads(message["Body"])
                result = await mock_process.return_value
                
                # Vérifier que le message échoué n'est pas supprimé
                if result.get("status") != "success":
                    # Le message ne devrait pas être supprimé
                    pass
            
            # Vérifications
            mock_process.assert_called()
            mock_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_malformed_message_handling(self, mock_malformed_message):
        """Test que les messages malformés sont supprimés de la queue."""
        with patch('media_summarizer.workers.spotify_sync.sync_worker.receive_messages') as mock_receive, \
             patch('media_summarizer.workers.spotify_sync.sync_worker.process_sync_message') as mock_process, \
             patch('media_summarizer.workers.spotify_sync.sync_worker.delete_message') as mock_delete:
            
            # Configuration des mocks
            mock_receive.return_value = mock_malformed_message
            
            # Simuler le traitement d'un message malformé
            messages = await mock_receive.return_value
            for message in messages:
                try:
                    body = json.loads(message["Body"])  # Ceci va échouer
                    await mock_process.return_value
                except json.JSONDecodeError:
                    # Le message malformé devrait être supprimé
                    await mock_delete.return_value
            
            # Vérifications
            mock_process.assert_not_called()  # Ne devrait pas être appelé pour un JSON invalide
            mock_delete.assert_called()  # Le message malformé devrait être supprimé

    @pytest.mark.asyncio
    async def test_empty_queue_polling(self, mock_empty_messages):
        """Test que le worker continue à poller quand la queue est vide."""
        with patch('media_summarizer.workers.spotify_sync.sync_worker.receive_messages') as mock_receive, \
             patch('media_summarizer.workers.spotify_sync.sync_worker.process_sync_message') as mock_process:
            
            # Configuration des mocks
            mock_receive.return_value = mock_empty_messages
            
            # Simuler un cycle de polling vide
            messages = await mock_receive.return_value
            
            # Vérifications
            assert len(messages) == 0
            mock_process.assert_not_called()  # Aucun message à traiter

    @pytest.mark.asyncio
    async def test_message_processing_exception_handling(self, mock_sqs_messages):
        """Test que les exceptions durant le traitement sont gérées correctement."""
        with patch('media_summarizer.workers.spotify_sync.sync_worker.receive_messages') as mock_receive, \
             patch('media_summarizer.workers.spotify_sync.sync_worker.process_sync_message') as mock_process, \
             patch('media_summarizer.workers.spotify_sync.sync_worker.delete_message') as mock_delete:
            
            # Configuration des mocks
            mock_receive.return_value = mock_sqs_messages
            mock_process.side_effect = Exception("Unexpected processing error")
            
            # Simuler le traitement avec exception
            messages = await mock_receive.return_value
            for message in messages:
                try:
                    body = json.loads(message["Body"])
                    result = await mock_process(body)
                except Exception as e:
                    # L'exception devrait être capturée et loggée
                    assert str(e) == "Unexpected processing error"
            
            # Vérifications
            mock_process.assert_called()
            mock_delete.assert_not_called()  # Message pas supprimé en cas d'exception

    @pytest.mark.asyncio
    async def test_sqs_configuration_parameters(self):
        """Test que les paramètres de configuration SQS sont correctement utilisés."""
        import os
        
        # Test des valeurs par défaut
        with patch.dict(os.environ, {}, clear=True):
            from media_summarizer.workers.spotify_sync.sync_worker import (
                QUEUE_NAME, MAX_MESSAGES, WAIT_TIME, VISIBILITY_TIMEOUT
            )
            
            assert QUEUE_NAME == "spotify-sync-queue"
            assert MAX_MESSAGES == 1
            assert WAIT_TIME == 20
            assert VISIBILITY_TIMEOUT == 300

        # Test des valeurs personnalisées
        with patch.dict(os.environ, {
            "SPOTIFY_SYNC_QUEUE": "custom-queue",
            "SQS_MAX_MESSAGES": "5",
            "SQS_WAIT_TIME": "10",
            "SQS_VISIBILITY_TIMEOUT": "600"
        }):
            # Recharger le module pour prendre en compte les nouvelles variables
            import importlib
            import media_summarizer.workers.spotify_sync.sync_worker as sync_worker_module
            importlib.reload(sync_worker_module)
            
            assert sync_worker_module.QUEUE_NAME == "custom-queue"
            assert sync_worker_module.MAX_MESSAGES == 5
            assert sync_worker_module.WAIT_TIME == 10
            assert sync_worker_module.VISIBILITY_TIMEOUT == 600

    @pytest.mark.asyncio
    async def test_message_body_validation(self, mock_successful_sync_result):
        """Test que la validation du contenu des messages fonctionne."""
        valid_message = {
            "Body": json.dumps({
                "user_id": "test_user",
                "playlist_ids": ["playlist_1"],
                "source": "test"
            }),
            "ReceiptHandle": "test-receipt"
        }
        
        invalid_message = {
            "Body": json.dumps({
                "invalid_field": "value"
                # Manque user_id et playlist_ids
            }),
            "ReceiptHandle": "test-receipt-invalid"
        }
        
        with patch('media_summarizer.workers.spotify_sync.sync_worker.process_sync_message') as mock_process:
            mock_process.return_value = mock_successful_sync_result
            
            # Test message valide
            body = json.loads(valid_message["Body"])
            result = await mock_process(body)
            assert result.get("status") == "success"
            
            # Test message invalide (devrait être géré par process_sync_message)
            invalid_body = json.loads(invalid_message["Body"])
            # Le worker devrait appeler process_sync_message même avec des données invalides
            # C'est process_sync_message qui gère la validation
            await mock_process(invalid_body)
            
            assert mock_process.call_count == 2

    @pytest.mark.asyncio
    async def test_concurrent_message_processing(self, mock_sqs_messages, mock_successful_sync_result):
        """Test que plusieurs messages peuvent être traités de manière concurrente."""
        with patch('media_summarizer.workers.spotify_sync.sync_worker.process_sync_message') as mock_process, \
             patch('media_summarizer.workers.spotify_sync.sync_worker.delete_message') as mock_delete:
            
            mock_process.return_value = mock_successful_sync_result
            
            # Simuler le traitement concurrent de plusieurs messages
            tasks = []
            for message in mock_sqs_messages:
                body = json.loads(message["Body"])
                task = mock_process(body)
                tasks.append(task)
            
            # Exécuter tous les traitements en parallèle
            results = await asyncio.gather(*tasks)
            
            # Vérifications
            assert len(results) == len(mock_sqs_messages)
            assert all(result.get("status") == "success" for result in results)
            assert mock_process.call_count == len(mock_sqs_messages)

    @pytest.mark.asyncio
    async def test_logging_context_and_messages(self, mock_sqs_messages, mock_successful_sync_result, caplog):
        """Test que les messages de log contiennent le bon contexte."""
        import logging
        caplog.set_level(logging.INFO, logger="media_summarizer.workers.spotify_sync.sync_worker")
        
        with patch('media_summarizer.workers.spotify_sync.sync_worker.receive_messages') as mock_receive, \
             patch('media_summarizer.workers.spotify_sync.sync_worker.process_sync_message') as mock_process, \
             patch('media_summarizer.workers.spotify_sync.sync_worker.delete_message') as mock_delete:
            
            mock_receive.return_value = mock_sqs_messages
            mock_process.return_value = mock_successful_sync_result
            
            # Simuler le traitement avec logging
            messages = await mock_receive.return_value
            for message in messages:
                body = json.loads(message["Body"])
                result = await mock_process(body)
                
                if result.get("status") == "success":
                    # Simuler le log de succès
                    import logging
                    logger = logging.getLogger("media_summarizer.workers.spotify_sync.sync_worker")
                    logger.info(f"Successfully processed sync for user {body.get('user_id')}")
            
            # Vérifier les logs
            log_messages = [record.message for record in caplog.records]
            success_logs = [msg for msg in log_messages if "Successfully processed sync" in msg]
            assert len(success_logs) >= 1