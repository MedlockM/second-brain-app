"""
Typesense client configuration and collection management.

Provides a lazily-initialized Typesense client and the transcript collection
schema used for per-user lexical search over media transcripts.

Environment variables:
    TYPESENSE_API_KEY: Admin API key for Typesense Cloud
    TYPESENSE_HOST: Typesense Cloud host (e.g. xxx.a1.typesense.net)
    TYPESENSE_PORT: Port (default 443)
    TYPESENSE_PROTOCOL: Protocol (default https)
    TYPESENSE_CONNECTION_TIMEOUT: Connection timeout in seconds (default 5)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import typesense

logger = logging.getLogger(__name__)

# Configuration from environment
TYPESENSE_API_KEY = os.environ.get("TYPESENSE_API_KEY", "")
TYPESENSE_HOST = os.environ.get("TYPESENSE_HOST", "localhost")
TYPESENSE_PORT = os.environ.get("TYPESENSE_PORT", "443")
TYPESENSE_PROTOCOL = os.environ.get("TYPESENSE_PROTOCOL", "https")
TYPESENSE_CONNECTION_TIMEOUT = int(os.environ.get("TYPESENSE_CONNECTION_TIMEOUT", "5"))

# Collection name
TRANSCRIPTS_COLLECTION = "transcripts"

# Collection schema for transcripts
TRANSCRIPTS_SCHEMA = {
    "name": TRANSCRIPTS_COLLECTION,
    "fields": [
        {"name": "user_id", "type": "string", "facet": True},
        {"name": "media_item_id", "type": "string"},
        {"name": "transcript", "type": "string"},
        {"name": "title", "type": "string", "optional": True},
        {"name": "source_platform", "type": "string", "optional": True, "facet": True},
        {"name": "created_at", "type": "int64", "sort": True},
    ],
    "default_sorting_field": "created_at",
}

# Singleton client instance
_client: Optional[typesense.Client] = None


def get_client() -> typesense.Client:
    """
    Get or create the Typesense client singleton.

    Returns:
        Configured Typesense client instance.

    Raises:
        RuntimeError: If TYPESENSE_API_KEY is not configured.
    """
    global _client
    if _client is not None:
        return _client

    if not TYPESENSE_API_KEY:
        raise RuntimeError(
            "TYPESENSE_API_KEY environment variable is required for search functionality"
        )

    _client = typesense.Client(
        {
            "nodes": [
                {
                    "host": TYPESENSE_HOST,
                    "port": TYPESENSE_PORT,
                    "protocol": TYPESENSE_PROTOCOL,
                }
            ],
            "api_key": TYPESENSE_API_KEY,
            "connection_timeout_seconds": TYPESENSE_CONNECTION_TIMEOUT,
        }
    )
    logger.info(
        f"Typesense client initialized: {TYPESENSE_PROTOCOL}://{TYPESENSE_HOST}:{TYPESENSE_PORT}"
    )
    return _client


def ensure_collection() -> None:
    """
    Ensure the transcripts collection exists in Typesense.
    Creates it if it does not exist; no-op if it already exists.
    """
    client = get_client()
    try:
        client.collections[TRANSCRIPTS_COLLECTION].retrieve()
        logger.debug(f"Collection '{TRANSCRIPTS_COLLECTION}' already exists")
    except typesense.exceptions.ObjectNotFound:
        client.collections.create(TRANSCRIPTS_SCHEMA)
        logger.info(f"Created Typesense collection '{TRANSCRIPTS_COLLECTION}'")
    except Exception as e:
        logger.error(f"Failed to ensure Typesense collection: {e}")
        raise


def reset_client() -> None:
    """Reset the singleton client (useful for testing)."""
    global _client
    _client = None
