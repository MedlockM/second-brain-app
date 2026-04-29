"""
Unit tests for the RSS feed service.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Pre-mock modules that may be missing in this worktree
for _mod in [
    "media_summarizer.utils.podcastindex_limiter",
    "media_summarizer.utils.distributed_rate_limiter",
    "media_summarizer.utils.tiktok_limiter",
    "media_summarizer.api.models.media_contracts",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from media_summarizer.core.models.rss_feed import FeedStatus, UserRssFeed
from media_summarizer.core.services.rss_feed_service import (
    FeedServiceError,
    FeedServiceException,
    _get_audio_enclosure,
    _get_item_guid,
    _get_item_link,
    _is_audio_enclosure,
    list_feeds,
    parse_feed,
    pause_feed,
    poll_feed,
    resume_feed,
    subscribe,
    unsubscribe,
)


class TestAudioDetection:
    """Test audio enclosure detection helpers."""

    def test_is_audio_enclosure_by_mime(self):
        assert _is_audio_enclosure({"type": "audio/mpeg", "href": "file.dat"}) is True
        assert _is_audio_enclosure({"type": "audio/mp4", "href": "file.dat"}) is True

    def test_is_audio_enclosure_by_extension(self):
        assert _is_audio_enclosure({"type": "", "href": "https://cdn.com/ep.mp3"}) is True
        assert _is_audio_enclosure({"type": "", "href": "https://cdn.com/ep.m4a"}) is True

    def test_is_not_audio_enclosure(self):
        assert _is_audio_enclosure({"type": "application/pdf", "href": "doc.pdf"}) is False
        assert _is_audio_enclosure({"type": "", "href": "https://cdn.com/image.jpg"}) is False

    def test_get_item_guid_from_id(self):
        entry = MagicMock()
        entry.id = "unique-id-123"
        entry.link = "https://example.com/post"
        assert _get_item_guid(entry) == "unique-id-123"

    def test_get_item_guid_from_link(self):
        entry = MagicMock()
        entry.id = ""
        entry.link = "https://example.com/post"
        assert _get_item_guid(entry) == "https://example.com/post"

    def test_get_item_guid_from_title(self):
        entry = MagicMock()
        entry.id = ""
        entry.link = ""
        entry.title = "My Post Title"
        assert _get_item_guid(entry) == "title:My Post Title"

    def test_get_item_link(self):
        entry = MagicMock()
        entry.link = "https://example.com/article"
        assert _get_item_link(entry) == "https://example.com/article"

    def test_get_item_link_from_links_list(self):
        entry = MagicMock()
        entry.link = ""
        entry.links = [{"rel": "alternate", "href": "https://example.com/alt"}]
        assert _get_item_link(entry) == "https://example.com/alt"

    def test_get_audio_enclosure_found(self):
        entry = MagicMock()
        entry.enclosures = [{"type": "audio/mpeg", "href": "https://cdn.com/ep1.mp3"}]
        entry.links = []
        result = _get_audio_enclosure(entry)
        assert result is not None
        assert result["href"] == "https://cdn.com/ep1.mp3"

    def test_get_audio_enclosure_not_found(self):
        entry = MagicMock()
        entry.enclosures = [{"type": "application/pdf", "href": "doc.pdf"}]
        entry.links = []
        assert _get_audio_enclosure(entry) is None


class TestParseFeed:
    """Test feed parsing logic."""

    def test_invalid_url_raises(self):
        with pytest.raises(FeedServiceException) as exc_info:
            parse_feed("not-a-url")
        assert exc_info.value.code == FeedServiceError.FEED_INVALID_URL

    def test_empty_url_raises(self):
        with pytest.raises(FeedServiceException) as exc_info:
            parse_feed("")
        # Pydantic validator might catch this first, but the parse_feed
        # should still handle edge cases
        assert exc_info.value.code in (
            FeedServiceError.FEED_INVALID_URL,
            FeedServiceError.FEED_PARSE_ERROR,
        )

    @patch("media_summarizer.core.services.rss_feed_service.feedparser.parse")
    def test_parse_success_article(self, mock_parse):
        """Test parsing a feed with article entries."""
        mock_entry = MagicMock()
        mock_entry.id = "guid-1"
        mock_entry.title = "Article Title"
        mock_entry.link = "https://blog.example.com/post-1"
        mock_entry.published = "Mon, 01 Jan 2024 00:00:00 GMT"
        mock_entry.enclosures = []
        mock_entry.links = []

        mock_parse.return_value = MagicMock(
            bozo=False,
            feed=MagicMock(title="My Blog"),
            entries=[mock_entry],
        )

        result = parse_feed("https://blog.example.com/feed")
        assert result["title"] == "My Blog"
        assert len(result["items"]) == 1
        assert result["items"][0]["guid"] == "guid-1"
        assert result["items"][0]["item_type"] == "article"
        assert result["items"][0]["link"] == "https://blog.example.com/post-1"

    @patch("media_summarizer.core.services.rss_feed_service.feedparser.parse")
    def test_parse_success_audio(self, mock_parse):
        """Test parsing a feed with audio enclosures (podcast)."""
        mock_entry = MagicMock()
        mock_entry.id = "episode-guid-1"
        mock_entry.title = "Episode 1"
        mock_entry.link = "https://podcast.example.com/ep-1"
        mock_entry.published = "Mon, 01 Jan 2024 00:00:00 GMT"
        mock_entry.enclosures = [
            {"type": "audio/mpeg", "href": "https://cdn.example.com/ep1.mp3"}
        ]
        mock_entry.links = []

        mock_parse.return_value = MagicMock(
            bozo=False,
            feed=MagicMock(title="My Podcast"),
            entries=[mock_entry],
        )

        result = parse_feed("https://podcast.example.com/feed")
        assert result["title"] == "My Podcast"
        assert len(result["items"]) == 1
        assert result["items"][0]["item_type"] == "audio"
        assert result["items"][0]["audio_url"] == "https://cdn.example.com/ep1.mp3"

    @patch("media_summarizer.core.services.rss_feed_service.feedparser.parse")
    def test_parse_bozo_without_entries_raises(self, mock_parse):
        """Test that a bozo feed with no entries raises an error."""
        mock_parse.return_value = MagicMock(
            bozo=True,
            bozo_exception=Exception("malformed XML"),
            entries=[],
        )

        with pytest.raises(FeedServiceException) as exc_info:
            parse_feed("https://example.com/bad-feed")
        assert exc_info.value.code == FeedServiceError.FEED_PARSE_ERROR

    @patch("media_summarizer.core.services.rss_feed_service.feedparser.parse")
    def test_parse_bozo_with_entries_succeeds(self, mock_parse):
        """Test that a bozo feed with entries still succeeds (partial parse)."""
        mock_entry = MagicMock()
        mock_entry.id = "guid-1"
        mock_entry.title = "Post"
        mock_entry.link = "https://example.com/post"
        mock_entry.published = None
        mock_entry.enclosures = []
        mock_entry.links = []

        mock_parse.return_value = MagicMock(
            bozo=True,
            bozo_exception=Exception("minor issue"),
            feed=MagicMock(title="Partial Feed"),
            entries=[mock_entry],
        )

        result = parse_feed("https://example.com/partial-feed")
        assert result["title"] == "Partial Feed"
        assert len(result["items"]) == 1


class TestSubscribe:
    """Test feed subscription logic."""

    @pytest.mark.asyncio
    @patch("media_summarizer.core.services.rss_feed_service.database_async")
    @patch("media_summarizer.core.services.rss_feed_service.parse_feed")
    async def test_subscribe_success(self, mock_parse, mock_db):
        """Test successful subscription."""
        mock_parse.return_value = {"title": "New Blog", "items": []}
        mock_db.get_rss_feeds_by_user_id = AsyncMock(return_value=[])
        mock_db.create_rss_feed = AsyncMock(side_effect=lambda f: f)

        feed = await subscribe("user-123", "https://blog.example.com/feed")
        assert feed.user_id == "user-123"
        assert feed.feed_url == "https://blog.example.com/feed"
        assert feed.feed_title == "New Blog"
        mock_db.create_rss_feed.assert_called_once()

    @pytest.mark.asyncio
    @patch("media_summarizer.core.services.rss_feed_service.database_async")
    @patch("media_summarizer.core.services.rss_feed_service.parse_feed")
    async def test_subscribe_duplicate_raises(self, mock_parse, mock_db):
        """Test that subscribing to the same feed twice raises."""
        mock_parse.return_value = {"title": "Existing Blog", "items": []}
        existing_feed = UserRssFeed(
            user_id="user-123",
            feed_url="https://blog.example.com/feed",
        )
        mock_db.get_rss_feeds_by_user_id = AsyncMock(return_value=[existing_feed])

        with pytest.raises(FeedServiceException) as exc_info:
            await subscribe("user-123", "https://blog.example.com/feed")
        assert exc_info.value.code == FeedServiceError.FEED_ALREADY_SUBSCRIBED


class TestUnsubscribe:
    """Test feed unsubscribe logic."""

    @pytest.mark.asyncio
    @patch("media_summarizer.core.services.rss_feed_service.database_async")
    async def test_unsubscribe_success(self, mock_db):
        """Test successful unsubscription."""
        feed = UserRssFeed(
            id="feed-abc",
            user_id="user-123",
            feed_url="https://example.com/feed",
        )
        mock_db.get_rss_feed_by_id = AsyncMock(return_value=feed)
        mock_db.delete_rss_feed = AsyncMock(return_value=True)

        result = await unsubscribe("user-123", "feed-abc")
        assert result is True
        mock_db.delete_rss_feed.assert_called_once_with("feed-abc")

    @pytest.mark.asyncio
    @patch("media_summarizer.core.services.rss_feed_service.database_async")
    async def test_unsubscribe_not_found(self, mock_db):
        """Test unsubscribe with nonexistent feed."""
        mock_db.get_rss_feed_by_id = AsyncMock(return_value=None)

        with pytest.raises(FeedServiceException) as exc_info:
            await unsubscribe("user-123", "feed-nonexistent")
        assert exc_info.value.code == FeedServiceError.FEED_NOT_FOUND

    @pytest.mark.asyncio
    @patch("media_summarizer.core.services.rss_feed_service.database_async")
    async def test_unsubscribe_access_denied(self, mock_db):
        """Test unsubscribe with wrong user."""
        feed = UserRssFeed(
            id="feed-abc",
            user_id="other-user",
            feed_url="https://example.com/feed",
        )
        mock_db.get_rss_feed_by_id = AsyncMock(return_value=feed)

        with pytest.raises(FeedServiceException) as exc_info:
            await unsubscribe("user-123", "feed-abc")
        assert exc_info.value.code == FeedServiceError.FEED_ACCESS_DENIED


class TestPauseFeed:
    """Test feed pause/resume logic."""

    @pytest.mark.asyncio
    @patch("media_summarizer.core.services.rss_feed_service.database_async")
    async def test_pause_feed_success(self, mock_db):
        feed = UserRssFeed(
            id="feed-abc",
            user_id="user-123",
            feed_url="https://example.com/feed",
            status=FeedStatus.ACTIVE,
        )
        mock_db.get_rss_feed_by_id = AsyncMock(return_value=feed)
        mock_db.update_rss_feed = AsyncMock(side_effect=lambda f: f)

        result = await pause_feed("user-123", "feed-abc")
        assert result.status == FeedStatus.PAUSED

    @pytest.mark.asyncio
    @patch("media_summarizer.core.services.rss_feed_service.database_async")
    async def test_resume_feed_success(self, mock_db):
        feed = UserRssFeed(
            id="feed-abc",
            user_id="user-123",
            feed_url="https://example.com/feed",
            status=FeedStatus.PAUSED,
        )
        mock_db.get_rss_feed_by_id = AsyncMock(return_value=feed)
        mock_db.update_rss_feed = AsyncMock(side_effect=lambda f: f)

        result = await resume_feed("user-123", "feed-abc")
        assert result.status == FeedStatus.ACTIVE


class TestPollFeed:
    """Test feed polling logic."""

    @pytest.mark.asyncio
    @patch("media_summarizer.core.services.rss_feed_service.database_async")
    @patch("media_summarizer.core.services.rss_feed_service.parse_feed")
    async def test_poll_returns_new_items(self, mock_parse, mock_db):
        """Test polling a feed with new items."""
        feed = UserRssFeed(
            user_id="user-123",
            feed_url="https://example.com/feed",
            item_guids_seen=["old-guid-1"],
        )
        mock_parse.return_value = {
            "title": "Test",
            "items": [
                {"guid": "old-guid-1", "title": "Old", "link": "http://a.com", "item_type": "article", "audio_url": None, "published": None},
                {"guid": "new-guid-2", "title": "New", "link": "http://b.com", "item_type": "article", "audio_url": None, "published": None},
            ],
        }
        mock_db.update_rss_feed = AsyncMock(side_effect=lambda f: f)

        new_items = await poll_feed(feed)
        assert len(new_items) == 1
        assert new_items[0]["guid"] == "new-guid-2"
        assert "new-guid-2" in feed.item_guids_seen

    @pytest.mark.asyncio
    @patch("media_summarizer.core.services.rss_feed_service.database_async")
    @patch("media_summarizer.core.services.rss_feed_service.parse_feed")
    async def test_poll_handles_parse_error(self, mock_parse, mock_db):
        """Test polling gracefully handles parse errors."""
        feed = UserRssFeed(
            user_id="user-123",
            feed_url="https://example.com/feed",
        )
        mock_parse.side_effect = FeedServiceException(
            FeedServiceError.FEED_PARSE_ERROR, "Parse failed"
        )
        mock_db.update_rss_feed = AsyncMock(side_effect=lambda f: f)

        new_items = await poll_feed(feed)
        assert new_items == []
        assert feed.last_error is not None

    @pytest.mark.asyncio
    @patch("media_summarizer.core.services.rss_feed_service.database_async")
    @patch("media_summarizer.core.services.rss_feed_service.parse_feed")
    async def test_poll_no_new_items(self, mock_parse, mock_db):
        """Test polling when all items are already seen."""
        feed = UserRssFeed(
            user_id="user-123",
            feed_url="https://example.com/feed",
            item_guids_seen=["guid-1", "guid-2"],
        )
        mock_parse.return_value = {
            "title": "Test",
            "items": [
                {"guid": "guid-1", "title": "Old1", "link": "http://a.com", "item_type": "article", "audio_url": None, "published": None},
                {"guid": "guid-2", "title": "Old2", "link": "http://b.com", "item_type": "article", "audio_url": None, "published": None},
            ],
        }
        mock_db.update_rss_feed = AsyncMock(side_effect=lambda f: f)

        new_items = await poll_feed(feed)
        assert new_items == []
