"""
Tests unitaires pour Summarization Worker - logique métier spécifique.

Ces tests se concentrent sur la logique métier du Summarization Worker,
les tests de base_worker (retry, logging, etc.) étant dans test_base_worker.py
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from media_summarizer.workers.summarization.summarization_worker import process_message


class TestSummarizationWorkerBusinessLogic:
    """Tests pour la logique métier spécifique du Summarization Worker."""

    @pytest.mark.asyncio
    async def test_summarization_worker_successful_processing(self):
        """Test que le summarization worker traite correctement un message valide."""
        test_message = {
            "job_id": "test-summary-123",
            "transcription": "This is a test transcription of a podcast episode about AI and technology.",
            "transcript_s3_key": "transcriptions/test-summary-123.txt",
            "podcast_title": "Tech Talk Podcast",
            "episode_title": "AI Revolution",
            "user_id": "user123",
            "email": "test@example.com"
        }

        # Mock LLM API response
        mock_llm_response = {
            "choices": [{
                "message": {
                    "content": '{"main_topics": ["AI", "Technology"], "key_points": ["AI advancement", "Technology impact"], "notable_quotes": [], "conclusion": "AI is transforming technology"}'
                }
            }],
            "model": "gpt-4",
            "usage": {"total_tokens": 100}
        }

        # Mock des services
        with patch('media_summarizer.workers.summarization.summarization_worker.call_llm_api') as mock_llm, \
             patch('media_summarizer.workers.summarization.summarization_worker.s3.upload_file_object') as mock_upload, \
             patch('media_summarizer.workers.summarization.summarization_worker.sqs.send_message') as mock_notify, \
             patch('media_summarizer.utils.database_async.get_processing_job_by_id') as mock_get_job, \
             patch('media_summarizer.utils.database_async.update_processing_job') as mock_update_job, \
             patch('media_summarizer.workers.summarization.summarization_worker.s3.download_file_to_memory') as mock_download:
            
            # Configurer les mocks
            mock_llm.return_value = mock_llm_response
            mock_upload.return_value = None
            mock_notify.return_value = None
            mock_get_job.return_value = MagicMock()  # Mock job object
            mock_update_job.return_value = None
            mock_download.return_value = b"This is a test transcription"

            # Traiter le message
            await process_message(test_message)

            # Vérifications
            mock_llm.assert_called_once()
            mock_upload.assert_called_once()
            mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_summarization_worker_handles_missing_required_fields(self):
        """Test que le summarization worker gère les champs manquants."""
        test_message = {
            "job_id": "test-missing-fields-101"
            # transcription et user_id manquants
        }

        # Le traitement devrait lever une exception pour champ manquant
        with pytest.raises(KeyError):
            await process_message(test_message)

    @pytest.mark.asyncio
    async def test_summarization_worker_llm_error_propagation(self):
        """Test que les erreurs LLM sont correctement propagées."""
        test_message = {
            "job_id": "test-llm-error-456",
            "transcription": "Test transcription",
            "transcript_s3_key": "transcriptions/test-llm-error-456.txt",
            "user_id": "user456",
            "podcast_title": "Test Podcast",
            "episode_title": "Test Episode",
            "email": "test@example.com"
        }

        # Mock LLM API qui échoue
        with patch('media_summarizer.workers.summarization.summarization_worker.call_llm_api') as mock_llm, \
             patch('media_summarizer.workers.summarization.summarization_worker.database_async.get_processing_job_by_id') as mock_get_job, \
             patch('media_summarizer.workers.summarization.summarization_worker.database_async.update_processing_job') as mock_update_job, \
             patch('media_summarizer.workers.summarization.summarization_worker.s3.download_file_to_memory') as mock_download:
            
            mock_llm.side_effect = Exception("LLM API timeout")
            mock_get_job.return_value = MagicMock()
            mock_update_job.return_value = None
            mock_download.return_value = b"Test transcription"

            # Le traitement devrait lever l'exception
            with pytest.raises(Exception, match="LLM API timeout"):
                await process_message(test_message)

    @pytest.mark.asyncio
    async def test_summarization_worker_sqs_format_handling(self):
        """Test que le summarization worker gère le format SQS."""
        # Message au format SQS
        sqs_message = {
            "Body": json.dumps({
                "job_id": "sqs-summary-001",
                "transcription": "SQS test transcription",
                "transcript_s3_key": "transcriptions/sqs-summary-001.txt",
                "user_id": "sqs-user-001",
                "podcast_title": "SQS Test Podcast",
                "episode_title": "SQS Episode",
                "email": "test@example.com"
            })
        }

        # Mock pour succès
        mock_llm_response = {
            "choices": [{
                "message": {
                    "content": '{"main_topics": ["SQS"], "key_points": ["test"], "notable_quotes": [], "conclusion": "SQS test"}'
                }
            }],
            "model": "gpt-4",
            "usage": {"total_tokens": 50}
        }
        
        with patch('media_summarizer.workers.summarization.summarization_worker.call_llm_api') as mock_llm, \
             patch('media_summarizer.workers.summarization.summarization_worker.s3.upload_file_object') as mock_upload, \
             patch('media_summarizer.workers.summarization.summarization_worker.sqs.send_message') as mock_notify, \
             patch('media_summarizer.workers.summarization.summarization_worker.database_async.get_processing_job_by_id') as mock_get_job, \
             patch('media_summarizer.workers.summarization.summarization_worker.database_async.update_processing_job') as mock_update_job, \
             patch('media_summarizer.workers.summarization.summarization_worker.s3.download_file_to_memory') as mock_download:
            
            mock_llm.return_value = mock_llm_response
            mock_upload.return_value = None
            mock_notify.return_value = None
            mock_get_job.return_value = MagicMock()
            mock_update_job.return_value = None
            mock_download.return_value = b"SQS test transcription"

            # Traitement du message SQS
            await process_message(sqs_message)

            # Vérifications
            mock_llm.assert_called_once()
            mock_upload.assert_called_once()
            mock_notify.assert_called_once()