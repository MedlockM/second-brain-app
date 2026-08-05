"""
RSS feed subscription service.

Business logic for subscribing, listing, pausing/resuming, unsubscribing,
and polling RSS feeds. Each feed item is routed to the existing ingestion
pipeline (article extraction or audio download).
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit

import feedparser

from media_summarizer.core.models.rss_feed import FeedStatus, UserRssFeed
from media_summarizer.utils import database_async

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Error enum
# ─────────────────────────────────────────────────────────────────────────────


class FeedServiceError(str, Enum):
    """Stable error codes for the RSS feed service."""

    FEED_NOT_FOUND = "FEED_NOT_FOUND"
    FEED_ACCESS_DENIED = "FEED_ACCESS_DENIED"
    FEED_PARSE_ERROR = "FEED_PARSE_ERROR"
    FEED_ALREADY_SUBSCRIBED = "FEED_ALREADY_SUBSCRIBED"
    FEED_INVALID_URL = "FEED_INVALID_URL"


class FeedServiceException(Exception):
    """Exception raised by the feed service with a stable error code."""

    def __init__(self, code: FeedServiceError, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


# ─────────────────────────────────────────────────────────────────────────────
# Audio detection helpers
# ─────────────────────────────────────────────────────────────────────────────

_AUDIO_MIME_PREFIXES = ("audio/",)
_AUDIO_EXTENSIONS = (".mp3", ".m4a", ".aac", ".ogg", ".wav", ".flac", ".opus")


def _is_audio_enclosure(enclosure: Dict[str, Any]) -> bool:
    """Check if an RSS enclosure is an audio file."""
    mime_type = (enclosure.get("type") or "").lower()
    if any(mime_type.startswith(prefix) for prefix in _AUDIO_MIME_PREFIXES):
        return True
    href = (enclosure.get("href") or enclosure.get("url") or "").lower()
    return href.endswith(_AUDIO_EXTENSIONS)


def _get_item_guid(entry: Any) -> str:
    """Extract a stable GUID from a feed entry.

    Priority: entry.id > entry.link > entry.title (fallback hash).
    """
    if hasattr(entry, "id") and entry.id:
        return entry.id
    if hasattr(entry, "link") and entry.link:
        return entry.link
    # Last resort: use the title
    title = getattr(entry, "title", "") or ""
    return f"title:{title}"


def _get_item_link(entry: Any) -> Optional[str]:
    """Extract the primary link from a feed entry."""
    if hasattr(entry, "link") and entry.link:
        return entry.link
    # Some feeds only have links list
    links = getattr(entry, "links", [])
    for link in links:
        if link.get("rel") == "alternate":
            return link.get("href")
    if links:
        return links[0].get("href")
    return None


def _get_audio_enclosure(entry: Any) -> Optional[Dict[str, Any]]:
    """Return the first audio enclosure from a feed entry, or None."""
    enclosures = getattr(entry, "enclosures", [])
    for enc in enclosures:
        if _is_audio_enclosure(enc):
            return enc
    # Also check links with rel=enclosure
    links = getattr(entry, "links", [])
    for link in links:
        if link.get("rel") == "enclosure" and _is_audio_enclosure(link):
            return link
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Feed parsing
# ─────────────────────────────────────────────────────────────────────────────


def parse_feed(feed_url: str) -> Dict[str, Any]:
    """Parse an RSS/Atom feed and return structured data.

    Returns:
        Dict with keys: title, items (list of dicts with guid, title, link,
        published, audio_url, item_type)

    Raises:
        FeedServiceException on parse errors.
    """
    try:
        split = urlsplit(feed_url)
        if not split.scheme or not split.netloc:
            raise FeedServiceException(
                FeedServiceError.FEED_INVALID_URL,
                f"Invalid feed URL: {feed_url}",
            )
    except ValueError:
        raise FeedServiceException(
            FeedServiceError.FEED_INVALID_URL,
            f"Invalid feed URL: {feed_url}",
        )

    parsed = feedparser.parse(feed_url)

    if parsed.bozo and not parsed.entries:
        # bozo with entries means partial parse (acceptable)
        bozo_exc = getattr(parsed, "bozo_exception", None)
        raise FeedServiceException(
            FeedServiceError.FEED_PARSE_ERROR,
            f"Failed to parse feed: {bozo_exc or 'unknown error'}",
        )

    feed_title = getattr(parsed.feed, "title", None) or feed_url

    items: List[Dict[str, Any]] = []
    for entry in parsed.entries:
        guid = _get_item_guid(entry)
        title = getattr(entry, "title", "") or ""
        link = _get_item_link(entry)
        published = getattr(entry, "published", None)

        audio_enc = _get_audio_enclosure(entry)
        if audio_enc:
            audio_url = audio_enc.get("href") or audio_enc.get("url") or ""
            item_type = "audio"
        else:
            audio_url = None
            item_type = "article"

        items.append({
            "guid": guid,
            "title": title,
            "link": link,
            "published": published,
            "audio_url": audio_url,
            "item_type": item_type,
        })

    return {
        "title": feed_title,
        "items": items,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Subscription management
# ─────────────────────────────────────────────────────────────────────────────


async def subscribe(user_id: str, feed_url: str) -> UserRssFeed:
    """Subscribe a user to an RSS feed.

    Validates the URL, parses the feed to get the title, checks for
    duplicate subscriptions, and creates the record.

    Returns:
        The created UserRssFeed.

    Raises:
        FeedServiceException on invalid URL, parse error, or duplicate.
    """
    # Validate and parse the feed
    feed_data = parse_feed(feed_url)

    # Check for duplicate subscription
    existing_feeds = await database_async.get_rss_feeds_by_user_id(user_id)
    normalized_url = feed_url.strip().rstrip("/")
    for existing in existing_feeds:
        if existing.feed_url.strip().rstrip("/") == normalized_url:
            raise FeedServiceException(
                FeedServiceError.FEED_ALREADY_SUBSCRIBED,
                "Already subscribed to this feed",
            )

    feed = UserRssFeed(
        user_id=user_id,
        feed_url=feed_url.strip(),
        feed_title=feed_data["title"],
    )

    created = await database_async.create_rss_feed(feed)
    return created


async def list_feeds(user_id: str) -> List[Dict[str, Any]]:
    """List all RSS feed subscriptions for a user.

    Returns:
        List of feed dicts suitable for API response.
    """
    feeds = await database_async.get_rss_feeds_by_user_id(user_id)
    return [
        {
            "id": f.id,
            "feed_url": f.feed_url,
            "feed_title": f.feed_title,
            "status": f.status.value,
            "last_polled_at": f.last_polled_at.isoformat() if f.last_polled_at else None,
            "last_error": f.last_error,
            "items_ingested": len(f.item_guids_seen),
            "created_at": f.created_at.isoformat(),
            "updated_at": f.updated_at.isoformat(),
        }
        for f in feeds
    ]


async def unsubscribe(user_id: str, feed_id: str) -> bool:
    """Unsubscribe from an RSS feed.

    Raises:
        FeedServiceException if feed not found or access denied.

    Returns:
        True on success.
    """
    feed = await database_async.get_rss_feed_by_id(feed_id)
    if feed is None:
        raise FeedServiceException(
            FeedServiceError.FEED_NOT_FOUND,
            f"Feed {feed_id} not found",
        )
    if feed.user_id != user_id:
        raise FeedServiceException(
            FeedServiceError.FEED_ACCESS_DENIED,
            "Access denied",
        )
    await database_async.delete_rss_feed(feed_id)
    return True


async def pause_feed(user_id: str, feed_id: str) -> UserRssFeed:
    """Pause polling for a feed subscription.

    Raises:
        FeedServiceException if feed not found or access denied.
    """
    feed = await database_async.get_rss_feed_by_id(feed_id)
    if feed is None:
        raise FeedServiceException(
            FeedServiceError.FEED_NOT_FOUND,
            f"Feed {feed_id} not found",
        )
    if feed.user_id != user_id:
        raise FeedServiceException(
            FeedServiceError.FEED_ACCESS_DENIED,
            "Access denied",
        )
    feed.status = FeedStatus.PAUSED
    feed.touch()
    return await database_async.update_rss_feed(feed)


async def resume_feed(user_id: str, feed_id: str) -> UserRssFeed:
    """Resume polling for a paused feed subscription.

    Raises:
        FeedServiceException if feed not found or access denied.
    """
    feed = await database_async.get_rss_feed_by_id(feed_id)
    if feed is None:
        raise FeedServiceException(
            FeedServiceError.FEED_NOT_FOUND,
            f"Feed {feed_id} not found",
        )
    if feed.user_id != user_id:
        raise FeedServiceException(
            FeedServiceError.FEED_ACCESS_DENIED,
            "Access denied",
        )
    feed.status = FeedStatus.ACTIVE
    feed.touch()
    return await database_async.update_rss_feed(feed)


# ─────────────────────────────────────────────────────────────────────────────
# Polling logic (called by the worker)
# ─────────────────────────────────────────────────────────────────────────────


async def poll_feed(feed: UserRssFeed) -> List[Dict[str, Any]]:
    """Poll a single feed and return new items to ingest.

    Updates the feed record with seen GUIDs and poll timestamp.

    Returns:
        List of item dicts (only new/unseen items).
    """
    try:
        feed_data = parse_feed(feed.feed_url)
    except FeedServiceException as e:
        feed.mark_poll_error(str(e))
        await database_async.update_rss_feed(feed)
        return []

    new_items: List[Dict[str, Any]] = []
    new_guids: List[str] = []

    for item in feed_data["items"]:
        guid = item["guid"]
        if feed.is_guid_seen(guid):
            continue
        new_items.append(item)
        new_guids.append(guid)

    # Record all new GUIDs as seen
    if new_guids:
        feed.add_seen_guids(new_guids)

    feed.mark_polled()
    await database_async.update_rss_feed(feed)

    return new_items
