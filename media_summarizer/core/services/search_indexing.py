"""
Search indexing service for managing transcript documents in Algolia.

Provides functions to index, delete, and search transcript documents.

Multi-tenant model: single shared index per environment. Tenant isolation
is enforced by a ``user_id`` attribute on every record. Search-time
isolation is guaranteed by secured API keys (for direct client access)
or by explicit ``user_id`` filter (for backend-proxied search).

Transcripts are chunked into records of <10 KB to comply with the
Algolia record size limit.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from algoliasearch.http.exceptions import RequestException

from media_summarizer.utils.algolia_client import (
    configure_shared_index_settings,
    get_client,
    get_shared_index_name,
)

logger = logging.getLogger(__name__)

# Maximum chunk size in bytes for Algolia record size limit.
# Reserve ~500 bytes for metadata fields (objectID, media_item_id, user_id,
# title, source_platform, created_at, chunk_index) to stay safely under 10 KB.
_MAX_CHUNK_TEXT_BYTES = 9500

# Track whether index settings have been configured in this process lifetime
_settings_configured = False


def _chunk_transcript(text: str) -> List[str]:
    """
    Split transcript text into chunks that fit within the Algolia record size limit.

    Each chunk is at most _MAX_CHUNK_TEXT_BYTES when UTF-8 encoded.
    Splits on whitespace boundaries to avoid breaking words.

    Args:
        text: Full transcript text.

    Returns:
        List of text chunks.
    """
    if not text:
        return []

    encoded = text.encode("utf-8")
    if len(encoded) <= _MAX_CHUNK_TEXT_BYTES:
        return [text]

    chunks: List[str] = []
    current_start = 0

    while current_start < len(text):
        # Find the end position that fits within the byte limit
        remaining = text[current_start:]
        remaining_encoded = remaining.encode("utf-8")

        if len(remaining_encoded) <= _MAX_CHUNK_TEXT_BYTES:
            chunks.append(remaining)
            break

        # Binary search for the character position that fits
        # Start with an estimate based on byte ratio
        estimate = int(len(remaining) * _MAX_CHUNK_TEXT_BYTES / len(remaining_encoded))
        # Adjust down until it fits
        candidate = remaining[:estimate]
        while len(candidate.encode("utf-8")) > _MAX_CHUNK_TEXT_BYTES:
            estimate -= 100
            candidate = remaining[:estimate]

        # Try to split on whitespace boundary (look backwards from the limit)
        split_pos = candidate.rfind(" ")
        if split_pos == -1 or split_pos < len(candidate) // 2:
            # No good whitespace boundary found, just cut at the byte limit
            split_pos = len(candidate)

        chunk_text = remaining[:split_pos].rstrip()
        if chunk_text:
            chunks.append(chunk_text)
        current_start += split_pos
        # Skip leading whitespace of next chunk
        while current_start < len(text) and text[current_start] == " ":
            current_start += 1

    return chunks


def _ensure_settings_once() -> None:
    """Configure shared index settings once per process lifetime."""
    global _settings_configured
    if _settings_configured:
        return
    try:
        configure_shared_index_settings()
        _settings_configured = True
    except Exception as e:
        # Non-fatal: settings may already be configured from a previous deploy
        logger.warning(f"Failed to configure shared index settings (non-fatal): {e}")


def index_transcript(
    *,
    user_id: str,
    media_item_id: str,
    transcript_text: str,
    title: Optional[str] = None,
    creator_name: Optional[str] = None,
    source_platform: Optional[str] = None,
    created_at: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Index a transcript document in the shared Algolia index.

    Chunks the transcript into records of <10 KB each. Each chunk is stored
    as a separate Algolia record with objectID = "{media_item_id}_chunk_{i}".
    Every record carries a ``user_id`` attribute for tenant isolation.

    Args:
        user_id: Owner of the transcript (stored on each record for filtering).
        media_item_id: Unique identifier for the media item.
        transcript_text: Full transcript text to index.
        title: Optional title/description of the media.
        creator_name: Optional publisher of the media (channel, show, site).
        source_platform: Optional platform source (youtube, audio, web, etc.).
        created_at: Unix timestamp of creation. Defaults to current time.

    Returns:
        Dict with indexing metadata (num_chunks, media_item_id).
    """
    client = get_client()
    index_name = get_shared_index_name()

    chunks = _chunk_transcript(transcript_text)
    if not chunks:
        logger.warning(
            f"Empty transcript for media_item_id={media_item_id}, skipping indexing"
        )
        return {"media_item_id": media_item_id, "num_chunks": 0}

    timestamp = created_at or int(time.time())

    records = []
    for i, chunk_text in enumerate(chunks):
        record = {
            "objectID": f"{media_item_id}_chunk_{i}",
            "media_item_id": media_item_id,
            "user_id": user_id,
            "title": title or "",
            "creator_name": creator_name or "",
            "source_platform": source_platform or "",
            "created_at": timestamp,
            "chunk_index": i,
            "transcript": chunk_text,
        }
        records.append(record)

    try:
        # Ensure the shared index has the correct settings (once per process)
        _ensure_settings_once()

        # First delete any existing chunks for this media item
        # (handles re-indexing after transcript update)
        _delete_chunks_for_media(client, index_name, media_item_id)

        # Save all chunks
        client.save_objects(index_name=index_name, objects=records)
        logger.info(
            f"Indexed transcript for media_item_id={media_item_id}, "
            f"user_id={user_id}, chunks={len(records)}"
        )
        return {"media_item_id": media_item_id, "num_chunks": len(records)}
    except Exception as e:
        logger.error(
            f"Failed to index transcript for media_item_id={media_item_id}: {e}"
        )
        raise


def _delete_chunks_for_media(client: Any, index_name: str, media_item_id: str) -> None:
    """Delete all existing chunks for a given media_item_id in the given index."""
    try:
        client.delete_by(
            index_name=index_name,
            delete_by_params={"filters": f"media_item_id:{media_item_id}"},
        )
    except Exception as e:
        # Log but don't fail - the save_objects will overwrite matching objectIDs anyway
        logger.debug(
            f"delete_by for media_item_id={media_item_id} raised: {e}"
        )


def delete_document(user_id: str, media_item_id: str) -> bool:
    """
    Delete all transcript chunks for a media item from the shared search index.

    Uses a compound filter to ensure only the specified user's records are
    affected (defense-in-depth).

    Args:
        user_id: Owner of the media (used as safety filter).
        media_item_id: ID of the media item whose chunks should be deleted.

    Returns:
        True if deletion was attempted (Algolia delete_by is fire-and-forget
        and does not report if documents existed).
    """
    client = get_client()
    index_name = get_shared_index_name()

    try:
        client.delete_by(
            index_name=index_name,
            delete_by_params={
                "filters": f"media_item_id:{media_item_id} AND user_id:{user_id}"
            },
        )
        logger.info(f"Deleted transcript chunks for media_item_id={media_item_id}")
        return True
    except Exception as e:
        logger.error(
            f"Failed to delete chunks for media_item_id={media_item_id}: {e}"
        )
        raise


def delete_user_records(user_id: str) -> bool:
    """
    Delete all records for a user from the shared search index.

    Use when a user account is deleted.

    Args:
        user_id: ID of the user whose records should be deleted.

    Returns:
        True if deletion was attempted.
    """
    client = get_client()
    index_name = get_shared_index_name()

    try:
        client.delete_by(
            index_name=index_name,
            delete_by_params={"filters": f"user_id:{user_id}"},
        )
        logger.info(f"Deleted all records for user_id={user_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete records for user_id={user_id}: {e}")
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
    Search transcripts for a specific user in the shared index.

    Tenant isolation is logical: searches the shared index with an explicit
    ``user_id`` filter. This is used for backend-proxied search; for direct
    client search, use secured API keys instead.

    Deduplicates results by media_item_id (multiple chunks of the same
    document may match; only the best-scoring chunk per document is returned).

    Args:
        user_id: User ID to filter by (mandatory).
        query: Search query string.
        page: Page number (1-indexed).
        per_page: Number of results per page (max 100).
        filter_by_platform: Optional platform filter (e.g. "youtube").

    Returns:
        Dict containing:
        - found: total number of unique matching documents (approximate)
        - hits: list of deduplicated results with highlights
        - page: current page number
    """
    client = get_client()
    index_name = get_shared_index_name()

    # Enforce per_page bounds
    per_page = min(max(1, per_page), 100)

    # Build filters: always include user_id for tenant isolation
    filters = f"user_id:{user_id}"
    if filter_by_platform:
        filters += f" AND source_platform:{filter_by_platform}"

    # Request more results than needed to account for deduplication
    # (multiple chunks from same document may match)
    fetch_count = per_page * 4

    search_params = {
        "query": query,
        "filters": filters,
        "attributesToRetrieve": [
            "media_item_id",
            "title",
            "source_platform",
            "created_at",
            "chunk_index",
            "transcript",
        ],
        "attributesToHighlight": ["transcript", "title"],
        "attributesToSnippet": ["transcript:30"],
        "highlightPreTag": "<mark>",
        "highlightPostTag": "</mark>",
        "hitsPerPage": fetch_count,
        "page": 0,  # Algolia is 0-indexed; we handle pagination after dedup
        "typoTolerance": True,
    }

    try:
        response = client.search_single_index(
            index_name=index_name,
            search_params=search_params,
        )

    except RequestException as e:
        # The shared index may not exist yet if no records have been indexed.
        # Treat 404 as empty results rather than a 500.
        if getattr(e, "status_code", None) == 404:
            logger.info(
                f"Search returned empty: shared index not yet created "
                f"(user_id={user_id}, query='{query}')"
            )
            return {"found": 0, "hits": [], "page": page}
        logger.error(f"Search failed for user_id={user_id}, query='{query}': {e}")
        raise

    try:
        # Deduplicate by media_item_id, keeping the best hit per document
        seen_media: Dict[str, Dict[str, Any]] = {}
        hits_list = response.hits if hasattr(response, "hits") else []

        for hit in hits_list:
            # Access hit data - Hit model with extra='allow'
            hit_data = _extract_hit_data(hit)
            media_id = hit_data.get("media_item_id", "")

            if not media_id:
                continue

            # Keep only the first (best-scored) hit per media_item_id
            if media_id not in seen_media:
                seen_media[media_id] = hit_data

        # Apply pagination on deduplicated results
        all_results = list(seen_media.values())
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated = all_results[start_idx:end_idx]

        result = {
            "found": len(all_results),
            "hits": paginated,
            "page": page,
        }

        logger.debug(
            f"Search completed: query='{query}', user_id={user_id}, "
            f"found={result['found']}"
        )
        return result

    except Exception as e:
        logger.error(f"Search failed for user_id={user_id}, query='{query}': {e}")
        raise


def _extract_hit_data(hit: Any) -> Dict[str, Any]:
    """
    Extract structured data from an Algolia Hit object.

    Handles both the typed Hit model (v4 SDK) and plain dicts.
    """
    if isinstance(hit, dict):
        raw = hit
        highlight_result = raw.get("_highlightResult", {})
        snippet_result = raw.get("_snippetResult", {})
    else:
        # Algolia v4 SDK Hit object
        raw = hit.to_dict() if hasattr(hit, "to_dict") else {}
        highlight_result = raw.get("_highlightResult", {})
        snippet_result = raw.get("_snippetResult", {})

    # Extract highlight/snippet for transcript
    highlights = []

    # Try snippet first (more concise)
    transcript_snippet = snippet_result.get("transcript", {})
    if isinstance(transcript_snippet, dict) and transcript_snippet.get("value"):
        highlights.append({
            "field": "transcript",
            "snippet": transcript_snippet["value"],
        })
    elif highlight_result.get("transcript"):
        hl_transcript = highlight_result["transcript"]
        if isinstance(hl_transcript, dict) and hl_transcript.get("value"):
            highlights.append({
                "field": "transcript",
                "snippet": hl_transcript["value"],
            })

    # Title highlight
    title_hl = highlight_result.get("title", {})
    if isinstance(title_hl, dict) and title_hl.get("value") and title_hl.get("matchLevel", "none") != "none":
        highlights.append({
            "field": "title",
            "snippet": title_hl["value"],
        })

    return {
        "media_item_id": raw.get("media_item_id", ""),
        "title": raw.get("title", ""),
        "source_platform": raw.get("source_platform", ""),
        "created_at": raw.get("created_at", 0),
        "text_match_score": 0,  # Algolia does not expose a numeric score by default
        "highlights": highlights,
    }
