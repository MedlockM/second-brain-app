"""
Algolia client configuration for full-text search.

Provides a lazily-initialized Algolia search client and index reference
used for per-user lexical search over media transcripts.

Environment variables:
    ALGOLIA_APP_ID: Algolia Application ID
    ALGOLIA_API_KEY: Algolia Admin API key (for indexing and search)
    ALGOLIA_INDEX_NAME: Name of the Algolia index (default: "transcripts")
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from algoliasearch.search.client import SearchClientSync

logger = logging.getLogger(__name__)

# Configuration from environment.
# strip() guards against corrupted values (e.g. trailing comment accidentally
# stored inside the secret string in Secrets Manager).
ALGOLIA_APP_ID = os.environ.get("ALGOLIA_APP_ID", "").strip()
ALGOLIA_API_KEY = os.environ.get("ALGOLIA_API_KEY", "").strip()
ALGOLIA_INDEX_NAME = os.environ.get("ALGOLIA_INDEX_NAME", "transcripts").strip()

# Singleton client instance
_client: Optional[SearchClientSync] = None


def get_client() -> SearchClientSync:
    """
    Get or create the Algolia client singleton.

    Returns:
        Configured Algolia SearchClientSync instance.

    Raises:
        RuntimeError: If ALGOLIA_APP_ID or ALGOLIA_API_KEY is not configured.
    """
    global _client
    if _client is not None:
        return _client

    if not ALGOLIA_APP_ID or not ALGOLIA_API_KEY:
        raise RuntimeError(
            "ALGOLIA_APP_ID and ALGOLIA_API_KEY environment variables are required "
            "for search functionality"
        )

    _client = SearchClientSync(ALGOLIA_APP_ID, ALGOLIA_API_KEY)
    logger.info(f"Algolia client initialized for app_id={ALGOLIA_APP_ID}")
    return _client


def get_index_name() -> str:
    """Return the configured Algolia index name."""
    return ALGOLIA_INDEX_NAME


def ensure_index_settings() -> None:
    """
    Ensure the Algolia index has the correct settings for search and filtering.

    Configures:
    - searchableAttributes: transcript, title (with priority)
    - attributesForFaceting: user_id, media_item_id, source_platform (for filtering)

    This is idempotent - Algolia will no-op if settings are already correct.
    """
    client = get_client()
    index_name = get_index_name()
    try:
        client.set_settings(
            index_name=index_name,
            index_settings={
                "searchableAttributes": [
                    "title",
                    "transcript",
                ],
                "attributesForFaceting": [
                    "filterOnly(user_id)",
                    "filterOnly(media_item_id)",
                    "filterOnly(source_platform)",
                ],
                "attributesToRetrieve": [
                    "media_item_id",
                    "title",
                    "source_platform",
                    "created_at",
                    "chunk_index",
                    "transcript",
                    "user_id",
                ],
                "ranking": [
                    "typo",
                    "geo",
                    "words",
                    "filters",
                    "proximity",
                    "attribute",
                    "exact",
                    "custom",
                ],
            },
        )
        logger.info(f"Algolia index settings configured for '{index_name}'")
    except Exception as e:
        logger.error(f"Failed to configure Algolia index settings: {e}")
        raise


def reset_client() -> None:
    """Reset the singleton client (useful for testing)."""
    global _client
    _client = None
