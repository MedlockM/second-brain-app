"""
Search indexing service for managing transcript documents in Typesense.

Provides functions to index, delete, and search transcript documents
with per-user tenant isolation via user_id filtering.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import typesense

from media_summarizer.utils.typesense_client import (
    TRANSCRIPTS_COLLECTION,
    ensure_collection,
    get_client,
)

logger = logging.getLogger(__name__)


def index_transcript(
    *,
    user_id: str,
    media_item_id: str,
    transcript_text: str,
    title: Optional[str] = None,
    source_platform: Optional[str] = None,
    created_at: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Index a transcript document in Typesense.

    Uses media_item_id as the document ID for idempotent upserts.

    Args:
        user_id: Owner of the transcript (for tenant isolation).
        media_item_id: Unique identifier for the media item (used as doc ID).
        transcript_text: Full transcript text to index.
        title: Optional title/description of the media.
        source_platform: Optional platform source (youtube, audio, web, etc.).
        created_at: Unix timestamp of creation. Defaults to current time.

    Returns:
        Typesense response dict for the indexed document.
    """
    ensure_collection()
    client = get_client()

    document = {
        "id": media_item_id,
        "user_id": user_id,
        "media_item_id": media_item_id,
        "transcript": transcript_text,
        "title": title or "",
        "source_platform": source_platform or "",
        "created_at": created_at or int(time.time()),
    }

    try:
        result = client.collections[TRANSCRIPTS_COLLECTION].documents.upsert(document)
        logger.info(
            f"Indexed transcript for media_item_id={media_item_id}, user_id={user_id}"
        )
        return result
    except Exception as e:
        logger.error(
            f"Failed to index transcript for media_item_id={media_item_id}: {e}"
        )
        raise


def delete_document(media_item_id: str) -> bool:
    """
    Delete a transcript document from the search index.

    Args:
        media_item_id: ID of the document to delete.

    Returns:
        True if deletion was successful, False if document was not found.
    """
    client = get_client()
    try:
        client.collections[TRANSCRIPTS_COLLECTION].documents[media_item_id].delete()
        logger.info(f"Deleted transcript document: {media_item_id}")
        return True
    except typesense.exceptions.ObjectNotFound:
        logger.warning(f"Document not found for deletion: {media_item_id}")
        return False
    except Exception as e:
        logger.error(f"Failed to delete document {media_item_id}: {e}")
        raise


def search_transcripts(
    *,
    user_id: str,
    query: str,
    page: int = 1,
    per_page: int = 10,
    filter_by_platform: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search transcripts for a specific user.

    Enforces per-user tenant isolation by filtering on user_id.

    Args:
        user_id: User ID for tenant isolation (mandatory).
        query: Search query string.
        page: Page number (1-indexed).
        per_page: Number of results per page (max 100).
        filter_by_platform: Optional platform filter (e.g. "youtube").

    Returns:
        Typesense search response dict containing:
        - found: total number of matching documents
        - hits: list of matching documents with highlights
        - page: current page number
    """
    ensure_collection()
    client = get_client()

    # Enforce per_page bounds
    per_page = min(max(1, per_page), 100)

    # Build filter string - always include user_id for tenant isolation
    filter_by = f"user_id:={user_id}"
    if filter_by_platform:
        filter_by += f" && source_platform:={filter_by_platform}"

    search_params = {
        "q": query,
        "query_by": "transcript,title",
        "filter_by": filter_by,
        "sort_by": "_text_match:desc,created_at:desc",
        "page": page,
        "per_page": per_page,
        "highlight_full_fields": "transcript",
        "highlight_affix_num_tokens": 20,
    }

    try:
        result = client.collections[TRANSCRIPTS_COLLECTION].documents.search(
            search_params
        )
        logger.debug(
            f"Search completed: query='{query}', user_id={user_id}, "
            f"found={result.get('found', 0)}"
        )
        return result
    except Exception as e:
        logger.error(f"Search failed for user_id={user_id}, query='{query}': {e}")
        raise
