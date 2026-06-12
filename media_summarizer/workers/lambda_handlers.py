"""
AWS Lambda handler entrypoints for all SQS-triggered workers.

Each handler receives an SQS event from Lambda event source mapping, iterates
over the Records, and delegates to the existing per-message processing logic.
The handler reports batch item failures so Lambda only retries failed messages.

Module-level initialization loads secrets from Secrets Manager (once per cold
start) so all os.getenv() calls throughout the codebase resolve correctly.
"""

import asyncio
import json
import logging
import os
from typing import Any

import boto3

from media_summarizer.utils.logging_config import setup_logging

# ---------------------------------------------------------------------------
# Cold-start initialization: load secrets into environment
# ---------------------------------------------------------------------------

_secret_name = os.environ.get("RUNTIME_SECRET_NAME", "")
if _secret_name:
    _client = boto3.client("secretsmanager")
    _resp = _client.get_secret_value(SecretId=_secret_name)
    _secrets = json.loads(_resp["SecretString"])
    for _key, _value in _secrets.items():
        os.environ.setdefault(_key, str(_value))

setup_logging("lambda-worker")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Generic handler factory
# ---------------------------------------------------------------------------


def _build_handler(worker_module_path: str, process_func_name: str = "process_message"):
    """
    Build a Lambda handler that processes SQS records using the given worker's
    process_message function.

    The handler supports partial batch responses: it returns batchItemFailures
    for messages that failed, so Lambda only retries those specific messages.
    """

    def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
        import importlib

        module = importlib.import_module(worker_module_path)
        process_fn = getattr(module, process_func_name)

        records = event.get("Records", [])
        failures: list[dict[str, str]] = []

        for record in records:
            message_id = record.get("messageId", "unknown")
            # Construct a message dict that matches what the existing
            # process_message functions expect (Body + ReceiptHandle + Attributes)
            message = {
                "Body": record.get("body", "{}"),
                "ReceiptHandle": record.get("receiptHandle", ""),
                "MessageId": message_id,
                "Attributes": record.get("attributes", {}),
            }

            try:
                # Workers use async processing
                asyncio.run(process_fn(message))
            except Exception as exc:
                logger.error(
                    "Worker handler failed for message %s: %s",
                    message_id,
                    str(exc),
                    exc_info=True,
                )
                failures.append({"itemIdentifier": message_id})

        return {"batchItemFailures": failures}

    return handler


# ---------------------------------------------------------------------------
# Worker handlers (one per Lambda function)
# ---------------------------------------------------------------------------

podcastindex_resolution_handler = _build_handler(
    "media_summarizer.workers.podcastindex_resolution_worker"
)

article_extraction_handler = _build_handler(
    "media_summarizer.workers.article_extraction_worker"
)

x_ingestion_handler = _build_handler(
    "media_summarizer.workers.x_ingestion_worker"
)

youtube_ingestion_handler = _build_handler(
    "media_summarizer.workers.youtube_ingestion_worker"
)

tiktok_ingestion_handler = _build_handler(
    "media_summarizer.workers.tiktok_ingestion_worker"
)

instagram_ingestion_handler = _build_handler(
    "media_summarizer.workers.instagram_ingestion_worker"
)

deepgram_transcription_handler = _build_handler(
    "media_summarizer.workers.transcription.deepgram_worker"
)

document_parsing_handler = _build_handler(
    "media_summarizer.workers.document_parsing.worker"
)

search_indexing_handler = _build_handler(
    "media_summarizer.workers.search_indexing_worker",
    process_func_name="process_indexing_message",
)

rss_feed_poll_handler = _build_handler(
    "media_summarizer.workers.rss_feed_poll_worker"
)

media_completed_events_handler = _build_handler(
    "media_summarizer.workers.events.media_completed_worker",
    process_func_name="process_event",
)

flashcards_handler = _build_handler(
    "media_summarizer.workers.flashcards.worker"
)

notes_handler = _build_handler(
    "media_summarizer.workers.notes.worker"
)

quiz_handler = _build_handler(
    "media_summarizer.workers.quiz.worker"
)
