"""
Algolia client configuration for full-text search.

Provides a lazily-initialized Algolia search client and per-user index
resolution used for lexical search over media transcripts.

Each user owns a dedicated Algolia index named
``{ALGOLIA_INDEX_PREFIX}_user_{user_id}`` so that a user's search only
ever touches their own records (physical isolation, no logical filtering).

Environment variables:
    ALGOLIA_APP_ID: Algolia Application ID
    ALGOLIA_API_KEY: Algolia Admin API key (for indexing and search)
    ALGOLIA_INDEX_PREFIX: Prefix for per-user index names (default: "transcripts")
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

from algoliasearch.search.client import SearchClientSync

logger = logging.getLogger(__name__)

# Configuration from environment.
# strip() guards against corrupted values (e.g. trailing comment accidentally
# stored inside the secret string in Secrets Manager).
ALGOLIA_APP_ID = os.environ.get("ALGOLIA_APP_ID", "").strip()
ALGOLIA_API_KEY = os.environ.get("ALGOLIA_API_KEY", "").strip()
ALGOLIA_INDEX_PREFIX = os.environ.get("ALGOLIA_INDEX_PREFIX", "transcripts").strip()

# Algolia index names accept [a-zA-Z0-9_-]. Any other character in a user_id
# is replaced with "-" to produce a deterministic, valid index name.
_INVALID_INDEX_CHARS = re.compile(r"[^a-zA-Z0-9_-]")

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


def get_index_name(user_id: str) -> str:
    """
    Return the per-user Algolia index name for a given user.

    The name is deterministic: ``{ALGOLIA_INDEX_PREFIX}_user_{user_id}``.
    Characters outside the Algolia-allowed set ``[a-zA-Z0-9_-]`` are
    replaced with ``-`` to guarantee a valid index name.

    Args:
        user_id: Owner of the index.

    Returns:
        The resolved index name.

    Raises:
        ValueError: If ``user_id`` is empty.
    """
    if not user_id:
        raise ValueError("user_id is required to resolve an Algolia index name")
    safe_user_id = _INVALID_INDEX_CHARS.sub("-", user_id)
    return f"{ALGOLIA_INDEX_PREFIX}_user_{safe_user_id}"


def ensure_index_settings(user_id: str) -> None:
    """
    Ensure a user's Algolia index has the correct settings for search and filtering.

    Configures:
    - searchableAttributes: title, transcript (with priority)
    - attributesForFaceting: media_item_id, source_platform (for filtering)

    This is idempotent - Algolia will no-op if settings are already correct.

    Args:
        user_id: Owner of the index to configure.
    """
    client = get_client()
    index_name = get_index_name(user_id)
    try:
        client.set_settings(
            index_name=index_name,
            index_settings={
                "searchableAttributes": [
                    "title",
                    "transcript",
                ],
                "attributesForFaceting": [
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
