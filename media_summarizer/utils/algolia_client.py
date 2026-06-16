"""
Algolia client configuration for full-text search.

Multi-tenant model: single shared index per environment with user_id-based
tenant isolation via secured API keys.

Index naming: ``media_items_{environment}`` (e.g. media_items_development,
media_items_production).

Security model:
- ALGOLIA_API_KEY (admin/write key): used server-side for indexing operations.
- ALGOLIA_SEARCH_API_KEY (search-only parent key): used server-side to derive
  per-user secured API keys. Never sent to clients.

Secured API keys embed a tamper-proof ``user_id`` filter so each client can
only retrieve their own records, regardless of client-side query params.

Reference: https://www.algolia.com/doc/guides/security/api-keys/how-to/user-restricted-access-to-data/

Environment variables:
    ALGOLIA_APP_ID: Algolia Application ID
    ALGOLIA_API_KEY: Algolia Admin API key (for indexing)
    ALGOLIA_SEARCH_API_KEY: Algolia Search-only API key (parent for secured keys)
    ENVIRONMENT: Current environment (development, staging, production)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

from algoliasearch.search.client import SearchClientSync
from algoliasearch.search.models.secured_api_key_restrictions import (
    SecuredApiKeyRestrictions,
)

logger = logging.getLogger(__name__)

# Configuration from environment.
# strip() guards against corrupted values (e.g. trailing comment accidentally
# stored inside the secret string in Secrets Manager).
ALGOLIA_APP_ID = os.environ.get("ALGOLIA_APP_ID", "").strip()
ALGOLIA_API_KEY = os.environ.get("ALGOLIA_API_KEY", "").strip()
ALGOLIA_SEARCH_API_KEY = os.environ.get("ALGOLIA_SEARCH_API_KEY", "").strip()
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").strip()

# Singleton client instance (uses admin key for write operations)
_client: Optional[SearchClientSync] = None


def get_client() -> SearchClientSync:
    """
    Get or create the Algolia client singleton (admin/write key).

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


def get_shared_index_name() -> str:
    """
    Return the canonical shared Algolia index name for the current environment.

    Format: ``media_items_{environment}`` (e.g. media_items_development).
    """
    return f"media_items_{ENVIRONMENT}"


def configure_shared_index_settings() -> None:
    """
    Configure the shared Algolia index with correct settings for multi-tenant search.

    Sets:
    - searchableAttributes: title, transcript (ordered priority)
    - attributesForFaceting: filterOnly(user_id), filterOnly(media_item_id),
      filterOnly(source_platform)
    - unretrievableAttributes: user_id (never returned to clients)
    - attributesToRetrieve: all fields except user_id

    This is idempotent - Algolia will no-op if settings are already correct.
    """
    client = get_client()
    index_name = get_shared_index_name()
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
                "unretrievableAttributes": [
                    "user_id",
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
        logger.info(f"Algolia shared index settings configured for '{index_name}'")
    except Exception as e:
        logger.error(f"Failed to configure Algolia shared index settings: {e}")
        raise


def generate_secured_search_key(user_id: str, ttl_seconds: int = 3600) -> dict:
    """
    Generate a secured API key for a specific user.

    The secured key embeds a tamper-proof filter ``user_id:{user_id}`` so the
    client can only retrieve records belonging to that user. The key has a
    short TTL (default 1 hour) and must be refreshed by the mobile client.

    Args:
        user_id: The user ID to embed in the key filter.
        ttl_seconds: Time-to-live in seconds (default 3600 = 1 hour).

    Returns:
        Dict with:
        - app_id: Algolia application ID
        - secured_key: The generated secured API key
        - index_name: The shared index name to search
        - valid_until: Unix timestamp when the key expires

    Raises:
        RuntimeError: If ALGOLIA_SEARCH_API_KEY is not configured.
        ValueError: If user_id is empty.
    """
    if not user_id:
        raise ValueError("user_id is required to generate a secured API key")

    if not ALGOLIA_SEARCH_API_KEY:
        raise RuntimeError(
            "ALGOLIA_SEARCH_API_KEY environment variable is required "
            "for generating secured search keys"
        )

    if not ALGOLIA_APP_ID:
        raise RuntimeError(
            "ALGOLIA_APP_ID environment variable is required "
            "for generating secured search keys"
        )

    client = get_client()
    valid_until = int(time.time()) + ttl_seconds

    restrictions = SecuredApiKeyRestrictions(
        filters=f"user_id:{user_id}",
        valid_until=valid_until,
        restrict_indices=[get_shared_index_name()],
    )

    secured_key = client.generate_secured_api_key(
        parent_api_key=ALGOLIA_SEARCH_API_KEY,
        restrictions=restrictions,
    )

    return {
        "app_id": ALGOLIA_APP_ID,
        "secured_key": secured_key,
        "index_name": get_shared_index_name(),
        "valid_until": valid_until,
    }


def reset_client() -> None:
    """Reset the singleton client (useful for testing)."""
    global _client
    _client = None
