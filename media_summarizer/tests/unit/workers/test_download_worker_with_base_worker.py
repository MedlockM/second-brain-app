"""
Tests unitaires pour Download Worker - logique métier spécifique.

Ces tests se concentrent sur la logique métier du Download Worker,
les tests de base_worker (retry, logging, etc.) étant dans test_base_worker.py
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from media_summarizer.workers.download_worker import process_message


class TestDownloadWorkerBusinessLogic:
    """Tests pour la logique métier spécifique du Download Worker."""

    @pytest.mark.asyncio
    async def test_download_worker_successful_processing(self):
        """Test que le download worker traite correctement un message valide."""
        test_message = {
            "job_id": "test-download-123",
            "audio_url": "https://example.com/podcast-episode.mp3",
            "podcast_title": "Test Podcast",
            "episode_title": "Test Episode",
            "user_id": "user123",
            "email": "test@example.com"
        }

        # Mock download et upload
        with patch('media_summarizer.workers.download_worker.download_audio') as mock_download, \
             patch('media_summarizer.utils.s3.upload_file') as mock_s3_upload, \
             patch('media_summarizer.utils.sqs.send_message') as mock_sqs_send, \
             patch('media_summarizer.utils.database_async.get_processing_job_by_id') as mock_get_job, \
             patch('media_summarizer.utils.database_async.update_processing_job') as mock_update_job:
            
            # Configurer les mocks
            mock_download.return_value = None  # Succès du téléchargement
            mock_s3_upload.return_value = {"ETag": "test-etag"}
            mock_sqs_send.return_value = None
            
            # Mock job status updates
            from media_summarizer.core.models.processing_job import ProcessingJob, JobStatus
            mock_job = ProcessingJob(user_id="test-user", user_email="test@example.com")
            mock_get_job.return_value = mock_job
            mock_update_job.return_value = mock_job

            # Traiter le message
            await process_message(test_message)

            # Vérifications
            mock_download.assert_called_once()
            mock_s3_upload.assert_called_once()
            mock_sqs_send.assert_called_once()
            mock_get_job.assert_called_once()
            mock_update_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_worker_handles_missing_required_fields(self):
        """Test que le download worker gère les champs manquants."""
        test_message = {
            "job_id": "test-missing-fields-101"
            # audio_url manquant
        }

        # Le traitement devrait lever une exception pour champ manquant
        with pytest.raises(ValueError, match="Missing required field: audio_url"):
            await process_message(test_message)

    @pytest.mark.asyncio
    async def test_download_worker_network_error_propagation(self):
        """Test que les erreurs réseau sont correctement propagées."""
        test_message = {
            "job_id": "test-network-error-456",
            "audio_url": "https://unreachable.example.com/podcast.mp3",
            "podcast_title": "Test Podcast",
            "episode_title": "Test Episode"
        }

        # Mock download qui échoue
        with patch('media_summarizer.workers.download_worker.download_audio') as mock_download, \
             patch('media_summarizer.workers.download_worker.database_async.get_processing_job_by_id') as mock_get_job, \
             patch('media_summarizer.workers.download_worker.database_async.update_processing_job') as mock_update_job:
            
            mock_download.side_effect = Exception("Network timeout")
            mock_get_job.return_value = MagicMock()
            mock_update_job.return_value = None

            # Le traitement devrait lever l'exception
            with pytest.raises(Exception, match="Network timeout"):
                await process_message(test_message)

    @pytest.mark.asyncio
    async def test_download_worker_s3_upload_error_propagation(self):
        """Test que les erreurs S3 sont correctement propagées."""
        test_message = {
            "job_id": "test-s3-error-789",
            "audio_url": "https://example.com/podcast.mp3",
            "podcast_title": "Test Podcast",
            "episode_title": "Test Episode"
        }

        # Mock download réussi mais upload S3 échoue
        with patch('media_summarizer.workers.download_worker.download_audio') as mock_download, \
             patch('media_summarizer.workers.download_worker.s3.upload_file') as mock_s3_upload, \
             patch('media_summarizer.workers.download_worker.database_async.get_processing_job_by_id') as mock_get_job, \
             patch('media_summarizer.workers.download_worker.database_async.update_processing_job') as mock_update_job:
            
            mock_download.return_value = None
            mock_s3_upload.side_effect = Exception("S3 upload failed")
            mock_get_job.return_value = MagicMock()
            mock_update_job.return_value = None

            # Le traitement devrait lever l'exception S3
            with pytest.raises(Exception, match="S3 upload failed"):
                await process_message(test_message)

    @pytest.mark.asyncio
    async def test_download_worker_sqs_format_handling(self):
        """Test que le download worker gère le format SQS."""
        # Message au format SQS
        sqs_message = {
            "Body": json.dumps({
                "job_id": "sqs-download-001",
                "audio_url": "https://example.com/sqs-podcast.mp3",
                "podcast_title": "SQS Test Podcast",
                "episode_title": "SQS Episode"
            })
        }

        # Mock pour succès
        with patch('media_summarizer.workers.download_worker.download_audio') as mock_download, \
             patch('media_summarizer.workers.download_worker.s3.upload_file') as mock_s3_upload, \
             patch('media_summarizer.workers.download_worker.sqs.send_message') as mock_sqs_send, \
             patch('media_summarizer.workers.download_worker.database_async.get_processing_job_by_id') as mock_get_job, \
             patch('media_summarizer.workers.download_worker.database_async.update_processing_job') as mock_update_job:
            
            mock_download.return_value = None
            mock_s3_upload.return_value = None
            mock_sqs_send.return_value = None
            mock_get_job.return_value = MagicMock()
            mock_update_job.return_value = None

            # Traitement du message SQS
            await process_message(sqs_message)

            # Vérifications
            mock_download.assert_called_once()
            mock_s3_upload.assert_called_once()
            mock_sqs_send.assert_called_once()