"""
Unit tests for the UserRssFeed model.
"""

import pytest
from datetime import datetime, timezone

from media_summarizer.core.models.rss_feed import FeedStatus, UserRssFeed


class TestUserRssFeedModel:
    """Test cases for the UserRssFeed model."""

    def test_create_feed_with_defaults(self):
        """Test creating a feed with minimum required fields."""
        feed = UserRssFeed(
            user_id="user-123",
            feed_url="https://example.com/feed.xml",
        )
        assert feed.user_id == "user-123"
        assert feed.feed_url == "https://example.com/feed.xml"
        assert feed.status == FeedStatus.ACTIVE
        assert feed.feed_title is None
        assert feed.last_polled_at is None
        assert feed.last_error is None
        assert feed.item_guids_seen == []
        assert feed.id is not None

    def test_create_feed_with_all_fields(self):
        """Test creating a feed with all fields."""
        feed = UserRssFeed(
            user_id="user-123",
            feed_url="https://example.com/feed.xml",
            feed_title="My Blog Feed",
            status=FeedStatus.PAUSED,
        )
        assert feed.feed_title == "My Blog Feed"
        assert feed.status == FeedStatus.PAUSED

    def test_user_id_validation_empty(self):
        """Test that empty user_id is rejected."""
        with pytest.raises(ValueError):
            UserRssFeed(user_id="", feed_url="https://example.com/feed.xml")

    def test_user_id_validation_whitespace(self):
        """Test that whitespace-only user_id is rejected."""
        with pytest.raises(ValueError):
            UserRssFeed(user_id="   ", feed_url="https://example.com/feed.xml")

    def test_feed_url_validation_empty(self):
        """Test that empty feed_url is rejected."""
        with pytest.raises(ValueError):
            UserRssFeed(user_id="user-123", feed_url="")

    def test_mark_polled(self):
        """Test marking a feed as polled."""
        feed = UserRssFeed(user_id="user-123", feed_url="https://example.com/feed.xml")
        original_updated_at = feed.updated_at
        feed.mark_polled()
        assert feed.last_polled_at is not None
        assert feed.last_error is None
        assert feed.updated_at >= original_updated_at

    def test_mark_poll_error(self):
        """Test recording a poll error."""
        feed = UserRssFeed(user_id="user-123", feed_url="https://example.com/feed.xml")
        feed.mark_poll_error("Connection timeout")
        assert feed.last_polled_at is not None
        assert feed.last_error == "Connection timeout"

    def test_add_seen_guids(self):
        """Test adding GUIDs to the seen set."""
        feed = UserRssFeed(user_id="user-123", feed_url="https://example.com/feed.xml")
        feed.add_seen_guids(["guid-1", "guid-2"])
        assert "guid-1" in feed.item_guids_seen
        assert "guid-2" in feed.item_guids_seen
        # Adding duplicates should not increase length
        feed.add_seen_guids(["guid-2", "guid-3"])
        assert len(feed.item_guids_seen) == 3

    def test_is_guid_seen(self):
        """Test checking if a GUID has been seen."""
        feed = UserRssFeed(
            user_id="user-123",
            feed_url="https://example.com/feed.xml",
            item_guids_seen=["guid-1", "guid-2"],
        )
        assert feed.is_guid_seen("guid-1") is True
        assert feed.is_guid_seen("guid-3") is False

    def test_to_dynamodb_item(self):
        """Test DynamoDB serialization."""
        feed = UserRssFeed(
            user_id="user-123",
            feed_url="https://example.com/feed.xml",
            feed_title="My Feed",
        )
        item = feed.to_dynamodb_item()
        assert item["id"] == feed.id
        assert item["user_id"] == "user-123"
        assert item["feed_url"] == "https://example.com/feed.xml"
        assert item["feed_title"] == "My Feed"
        assert item["status"] == "active"
        assert item["item_guids_seen"] == []
        assert "last_polled_at" not in item  # None values excluded
        assert "last_error" not in item

    def test_to_dynamodb_item_with_poll_info(self):
        """Test DynamoDB serialization after polling."""
        feed = UserRssFeed(
            user_id="user-123",
            feed_url="https://example.com/feed.xml",
        )
        feed.mark_poll_error("timeout")
        item = feed.to_dynamodb_item()
        assert "last_polled_at" in item
        assert item["last_error"] == "timeout"

    def test_from_dynamodb_item(self):
        """Test DynamoDB deserialization."""
        now = datetime.now(timezone.utc)
        item = {
            "id": "feed-abc",
            "user_id": "user-123",
            "feed_url": "https://example.com/feed.xml",
            "feed_title": "Test Feed",
            "status": "paused",
            "item_guids_seen": ["g1", "g2"],
            "last_polled_at": now.isoformat(),
            "last_error": "some error",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        feed = UserRssFeed.from_dynamodb_item(item)
        assert feed.id == "feed-abc"
        assert feed.user_id == "user-123"
        assert feed.feed_url == "https://example.com/feed.xml"
        assert feed.feed_title == "Test Feed"
        assert feed.status == FeedStatus.PAUSED
        assert feed.item_guids_seen == ["g1", "g2"]
        assert feed.last_polled_at is not None
        assert feed.last_error == "some error"

    def test_from_dynamodb_item_minimal(self):
        """Test DynamoDB deserialization with minimal fields."""
        now = datetime.now(timezone.utc)
        item = {
            "id": "feed-abc",
            "user_id": "user-123",
            "feed_url": "https://example.com/feed.xml",
            "status": "active",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        feed = UserRssFeed.from_dynamodb_item(item)
        assert feed.feed_title is None
        assert feed.last_polled_at is None
        assert feed.last_error is None
        assert feed.item_guids_seen == []

    def test_roundtrip_serialization(self):
        """Test that serialization/deserialization is lossless."""
        feed = UserRssFeed(
            user_id="user-123",
            feed_url="https://example.com/feed.xml",
            feed_title="Round Trip",
        )
        feed.add_seen_guids(["a", "b", "c"])
        feed.mark_polled()

        item = feed.to_dynamodb_item()
        restored = UserRssFeed.from_dynamodb_item(item)

        assert restored.id == feed.id
        assert restored.user_id == feed.user_id
        assert restored.feed_url == feed.feed_url
        assert restored.feed_title == feed.feed_title
        assert restored.status == feed.status
        assert set(restored.item_guids_seen) == set(feed.item_guids_seen)
