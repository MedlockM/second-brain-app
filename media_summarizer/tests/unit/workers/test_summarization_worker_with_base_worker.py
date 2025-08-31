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
            "Body": json.dumps({
                "job_id": "test-summary-123",
                "transcript_s3_key": "transcriptions/test-summary-123.txt",
                "transcript_bucket": "media-summarizer-transcriptions",
                "podcast_title": "Tech Talk Podcast",
                "episode_title": "AI Revolution",
                "email": "test@example.com"
            }),
            "ReceiptHandle": "test-receipt-handle"
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
        with patch('media_summarizer.workers.summarization.summarization_worker.generate_summary_with_retry') as mock_generate, \
             patch('media_summarizer.utils.s3.upload_file_object') as mock_upload, \
             patch('media_summarizer.utils.s3.generate_presigned_url') as mock_presigned, \
             patch('media_summarizer.utils.sqs.send_message') as mock_notify, \
             patch('media_summarizer.utils.database_async.get_processing_job_by_id') as mock_get_job, \
             patch('media_summarizer.utils.database_async.update_processing_job') as mock_update_job, \
             patch('media_summarizer.utils.s3.download_file_to_memory') as mock_download:

            # Configurer les mocks
            mock_generate.return_value = {"main_topics": ["AI", "Technology"], "key_points": ["AI advancement", "Technology impact"], "notable_quotes": [], "conclusion": "AI is transforming technology"}
            mock_upload.return_value = None
            mock_presigned.return_value = "https://example.com/presigned-url"
            mock_notify.return_value = None
            mock_get_job.return_value = MagicMock()  # Mock job object
            mock_update_job.return_value = None
            mock_download.return_value = b"This is a test transcription"

            # Traiter le message
            await process_message(test_message)

            # Vérifications
            mock_generate.assert_called_once()
            mock_upload.assert_called_once()
            mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_summarization_worker_handles_missing_required_fields(self):
        """Test que le summarization worker gère les champs manquants."""
        test_message = {
            "Body": json.dumps({
                "job_id": "test-missing-fields-101"
                # transcript_s3_key et email manquants
            }),
            "ReceiptHandle": "test-receipt-handle"
        }

        # Le traitement devrait lever une exception pour champ manquant
        with pytest.raises(ValueError, match="Missing required fields in summarization message"):
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

        # Créer un message de test au format SQS
        test_message = {
            "Body": json.dumps({
                "job_id": "test-llm-error-654",
                "transcript_s3_key": "test-transcript.txt",
                "transcript_bucket": "media-summarizer-transcriptions",
                "email": "test@example.com"
            }),
            "ReceiptHandle": "test-receipt-handle"
        }

        # Mock LLM qui échoue
        with patch('media_summarizer.workers.summarization.summarization_worker.generate_summary_with_retry') as mock_generate, \
             patch('media_summarizer.utils.database_async.get_processing_job_by_id') as mock_get_job, \
             patch('media_summarizer.utils.database_async.update_processing_job') as mock_update_job, \
             patch('media_summarizer.utils.s3.download_file_to_memory') as mock_download, \
             patch('media_summarizer.utils.sqs.send_message') as mock_sqs_send:

            mock_generate.side_effect = Exception("LLM API timeout")
            mock_get_job.return_value = MagicMock()
            mock_update_job.return_value = None
            mock_download.return_value = b"Test transcription"
            mock_sqs_send.return_value = None

            # Le traitement devrait lever l'exception LLM
            with pytest.raises(Exception, match="LLM API timeout"):
                await process_message(test_message)

    @pytest.mark.asyncio
    async def test_summarization_worker_sqs_format_handling(self):
        """Test que le summarization worker gère le format de message SQS."""
        test_message = {
            "Body": json.dumps({
                "job_id": "test-sqs-format-321",
                "transcript_s3_key": "test-transcript.txt",
                "transcript_bucket": "media-summarizer-transcriptions",
                "email": "test@example.com"
            }),
            "ReceiptHandle": "test-receipt-handle"
        }

        # Mock LLM API response
        mock_llm_response = {
            "choices": [{
                "message": {
                    "content": '{"main_topics": ["SQS"], "key_points": ["Message format"], "conclusion": "SQS format works"}'
                }
            }],
            "model": "gpt-4",
            "usage": {"total_tokens": 50}
        }

        with patch('media_summarizer.workers.summarization.summarization_worker.generate_summary_with_retry') as mock_generate, \
             patch('media_summarizer.utils.s3.upload_file_object') as mock_upload, \
             patch('media_summarizer.utils.s3.generate_presigned_url') as mock_presigned, \
             patch('media_summarizer.utils.sqs.send_message') as mock_notify, \
             patch('media_summarizer.utils.database_async.get_processing_job_by_id') as mock_get_job, \
             patch('media_summarizer.utils.database_async.update_processing_job') as mock_update_job, \
             patch('media_summarizer.utils.s3.download_file_to_memory') as mock_download:

            mock_generate.return_value = {"main_topics": ["SQS"], "key_points": ["Message format"], "conclusion": "SQS format works"}
            mock_upload.return_value = None
            mock_presigned.return_value = "https://example.com/sqs-presigned-url"
            mock_notify.return_value = None
            mock_get_job.return_value = MagicMock()
            mock_update_job.return_value = None
            mock_download.return_value = b"SQS test transcription"

            # Traitement du message SQS
            await process_message(test_message)

            # Vérifications
            mock_generate.assert_called_once()
            mock_upload.assert_called_once()
            mock_notify.assert_called_once()
