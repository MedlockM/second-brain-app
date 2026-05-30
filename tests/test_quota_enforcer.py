"""
Unit tests for the quota_enforcer service (task-110).

Covers:
- Hard cap enforcement (monthly limits per media type per tier)
- Daily rate limit enforcement
- Max audio duration per import
- Tier-level audio gating (text_only refuses audio)
- Cost monitoring hard block
- Free trial cap overrides
- Media type classification
"""

import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from media_summarizer.core.services.quota_enforcer import (
    check_submission_allowed,
    record_submission,
    estimate_submission_cost,
    classify_media_type,
    QuotaCheckResult,
    QUOTA_CATEGORY_AUDIO,
    QUOTA_CATEGORY_ARTICLE,
    QUOTA_CATEGORY_DOCUMENT,
    QUOTA_CATEGORY_YOUTUBE,
)
from media_summarizer.core.services.pricing_config_service import DEFAULT_PRICING_CONFIG


# Helper to run async tests
def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# --- Fixture helpers ---

def _mock_subscription(tier_value: str, status: str = "active"):
    """Create a mock subscription object."""
    sub = MagicMock()
    sub.tier = MagicMock()
    sub.tier.value = tier_value
    sub.status = MagicMock()
    sub.status.value = status
    sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=15)
    return sub


def _mock_user(created_days_ago: int = 5):
    """Create a mock user object."""
    user = MagicMock()
    user.id = "test-user-123"
    user.email = "test@example.com"
    user.created_at = datetime.now(timezone.utc) - timedelta(days=created_days_ago)
    return user


def _empty_monthly_usage():
    return {
        "audio_minutes_used": 0,
        "articles_count": 0,
        "documents_count": 0,
        "youtube_count": 0,
        "cost_eur_estimated": 0.0,
    }


def _empty_daily_usage():
    return {
        "audio_imports": 0,
        "text_imports": 0,
        "document_imports": 0,
        "last_text_import_ts": [],
        "last_api_call_ts": [],
    }


# --- Test: classify_media_type ---

class TestClassifyMediaType:
    def test_podcast_is_audio(self):
        assert classify_media_type("podcast") == QUOTA_CATEGORY_AUDIO

    def test_audio_is_audio(self):
        assert classify_media_type("audio") == QUOTA_CATEGORY_AUDIO

    def test_rss_is_audio(self):
        assert classify_media_type("rss") == QUOTA_CATEGORY_AUDIO

    def test_youtube_is_youtube(self):
        assert classify_media_type("youtube") == QUOTA_CATEGORY_YOUTUBE

    def test_video_is_youtube(self):
        assert classify_media_type("video") == QUOTA_CATEGORY_YOUTUBE

    def test_document_is_document(self):
        assert classify_media_type("document") == QUOTA_CATEGORY_DOCUMENT

    def test_web_is_article(self):
        assert classify_media_type("web") == QUOTA_CATEGORY_ARTICLE

    def test_tiktok_is_article(self):
        assert classify_media_type("tiktok") == QUOTA_CATEGORY_ARTICLE

    def test_instagram_is_article(self):
        assert classify_media_type("instagram") == QUOTA_CATEGORY_ARTICLE

    def test_unknown_defaults_to_article(self):
        assert classify_media_type("something_new") == QUOTA_CATEGORY_ARTICLE


# --- Test: text_only tier refuses audio ---

class TestTierAudioGating:
    @patch("media_summarizer.core.services.quota_enforcer.quota_usage_db")
    @patch("media_summarizer.core.services.quota_enforcer._get_user_tier")
    @patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config")
    def test_text_only_refuses_audio(self, mock_config, mock_tier, mock_db):
        mock_tier.return_value = asyncio.coroutine(lambda: "text_only")()
        mock_config.return_value = asyncio.coroutine(lambda: DEFAULT_PRICING_CONFIG)()

        # Use AsyncMock
        mock_tier.side_effect = None
        mock_tier.return_value = "text_only"
        mock_tier.__class__ = AsyncMock
        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="text_only")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=False)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    result = run(check_submission_allowed("user-1", "podcast", duration_seconds=300))

        assert not result.allowed
        assert result.error_code == "tier_quota_exceeded"

    @patch("media_summarizer.core.services.quota_enforcer.quota_usage_db")
    def test_text_only_allows_article(self, mock_db):
        mock_db.get_monthly_usage = AsyncMock(return_value=_empty_monthly_usage())
        mock_db.get_daily_usage = AsyncMock(return_value=_empty_daily_usage())

        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="text_only")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=False)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    result = run(check_submission_allowed("user-1", "web", duration_seconds=0))

        assert result.allowed


# --- Test: hard cap enforcement ---

class TestHardCaps:
    def test_monthly_audio_cap_reached(self):
        usage = _empty_monthly_usage()
        usage["audio_minutes_used"] = 300  # Mix tier limit

        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="mix")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=False)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_monthly_usage", new=AsyncMock(return_value=usage)):
                        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_daily_usage", new=AsyncMock(return_value=_empty_daily_usage())):
                            result = run(check_submission_allowed("user-1", "podcast", duration_seconds=60))

        assert not result.allowed
        assert result.error_code == "tier_quota_exceeded"

    def test_monthly_article_cap_reached(self):
        usage = _empty_monthly_usage()
        usage["articles_count"] = 500  # Mix tier limit

        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="mix")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=False)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_monthly_usage", new=AsyncMock(return_value=usage)):
                        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_daily_usage", new=AsyncMock(return_value=_empty_daily_usage())):
                            result = run(check_submission_allowed("user-1", "web", duration_seconds=0))

        assert not result.allowed
        assert result.error_code == "tier_quota_exceeded"

    def test_monthly_document_cap_not_reached(self):
        usage = _empty_monthly_usage()
        usage["documents_count"] = 50  # Mix limit is 100

        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="mix")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=False)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_monthly_usage", new=AsyncMock(return_value=usage)):
                        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_daily_usage", new=AsyncMock(return_value=_empty_daily_usage())):
                            result = run(check_submission_allowed("user-1", "document", duration_seconds=0))

        assert result.allowed

    def test_monthly_youtube_cap_reached(self):
        usage = _empty_monthly_usage()
        usage["youtube_count"] = 100  # Mix tier limit

        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="mix")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=False)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_monthly_usage", new=AsyncMock(return_value=usage)):
                        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_daily_usage", new=AsyncMock(return_value=_empty_daily_usage())):
                            result = run(check_submission_allowed("user-1", "youtube", duration_seconds=0))

        assert not result.allowed
        assert result.error_code == "tier_quota_exceeded"


# --- Test: daily rate limits ---

class TestDailyRateLimits:
    def test_daily_audio_limit_reached(self):
        daily = _empty_daily_usage()
        daily["audio_imports"] = 10  # Mix tier limit

        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="mix")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=False)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_monthly_usage", new=AsyncMock(return_value=_empty_monthly_usage())):
                        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_daily_usage", new=AsyncMock(return_value=daily)):
                            result = run(check_submission_allowed("user-1", "podcast", duration_seconds=60))

        assert not result.allowed
        assert result.error_code == "daily_rate_limit"
        assert result.http_status == 429

    def test_daily_text_limit_reached(self):
        daily = _empty_daily_usage()
        daily["text_imports"] = 30  # Mix tier limit

        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="mix")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=False)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_monthly_usage", new=AsyncMock(return_value=_empty_monthly_usage())):
                        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_daily_usage", new=AsyncMock(return_value=daily)):
                            result = run(check_submission_allowed("user-1", "web", duration_seconds=0))

        assert not result.allowed
        assert result.error_code == "daily_rate_limit"
        assert result.http_status == 429

    def test_daily_document_limit_reached(self):
        daily = _empty_daily_usage()
        daily["document_imports"] = 10  # Mix tier limit

        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="mix")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=False)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_monthly_usage", new=AsyncMock(return_value=_empty_monthly_usage())):
                        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_daily_usage", new=AsyncMock(return_value=daily)):
                            result = run(check_submission_allowed("user-1", "document", duration_seconds=0))

        assert not result.allowed
        assert result.error_code == "daily_rate_limit"
        assert result.http_status == 429


# --- Test: max audio duration per import ---

class TestMaxAudioDuration:
    def test_mix_tier_rejects_over_60_min(self):
        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="mix")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=False)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    # 61 minutes = 3660 seconds
                    result = run(check_submission_allowed("user-1", "podcast", duration_seconds=3660))

        assert not result.allowed
        assert result.error_code == "audio_too_long"

    def test_audio_heavy_allows_89_min(self):
        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="audio_heavy")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=False)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_monthly_usage", new=AsyncMock(return_value=_empty_monthly_usage())):
                        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_daily_usage", new=AsyncMock(return_value=_empty_daily_usage())):
                            # 89 minutes = 5340 seconds
                            result = run(check_submission_allowed("user-1", "podcast", duration_seconds=5340))

        assert result.allowed

    def test_audio_heavy_rejects_over_90_min(self):
        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="audio_heavy")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=False)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    # 91 minutes = 5460 seconds
                    result = run(check_submission_allowed("user-1", "podcast", duration_seconds=5460))

        assert not result.allowed
        assert result.error_code == "audio_too_long"


# --- Test: cost monitoring hard block ---

class TestCostMonitoring:
    def test_cost_hard_block_mix(self):
        usage = _empty_monthly_usage()
        usage["cost_eur_estimated"] = 6.5  # Mix hard_block is 6.0

        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="mix")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=False)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_monthly_usage", new=AsyncMock(return_value=usage)):
                        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_daily_usage", new=AsyncMock(return_value=_empty_daily_usage())):
                            result = run(check_submission_allowed("user-1", "web", duration_seconds=0))

        assert not result.allowed
        assert result.error_code == "cost_hard_block"

    def test_cost_below_warning_allows(self):
        usage = _empty_monthly_usage()
        usage["cost_eur_estimated"] = 2.0  # Mix warning is 4.0

        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="mix")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=False)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_monthly_usage", new=AsyncMock(return_value=usage)):
                        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_daily_usage", new=AsyncMock(return_value=_empty_daily_usage())):
                            result = run(check_submission_allowed("user-1", "web", duration_seconds=0))

        assert result.allowed


# --- Test: free trial overrides ---

class TestFreeTrial:
    def test_free_trial_applies_reduced_article_cap(self):
        """Free trial on Mix caps articles at 300 instead of 500."""
        usage = _empty_monthly_usage()
        usage["articles_count"] = 300  # Free trial limit (Mix normal is 500)

        mock_user = _mock_user(created_days_ago=5)  # Within 30-day trial

        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="mix")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=True)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_monthly_usage", new=AsyncMock(return_value=usage)):
                        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_daily_usage", new=AsyncMock(return_value=_empty_daily_usage())):
                            result = run(check_submission_allowed("user-1", "web", duration_seconds=0))

        assert not result.allowed
        assert result.error_code == "tier_quota_exceeded"

    def test_free_trial_applies_reduced_document_cap(self):
        """Free trial on Mix caps documents at 50 instead of 100."""
        usage = _empty_monthly_usage()
        usage["documents_count"] = 50  # Free trial limit (Mix normal is 100)

        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="mix")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=True)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_monthly_usage", new=AsyncMock(return_value=usage)):
                        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_daily_usage", new=AsyncMock(return_value=_empty_daily_usage())):
                            result = run(check_submission_allowed("user-1", "document", duration_seconds=0))

        assert not result.allowed
        assert result.error_code == "tier_quota_exceeded"

    def test_free_trial_cost_hard_block(self):
        """Free trial cost monitoring uses lower threshold (5.0 instead of 6.0)."""
        usage = _empty_monthly_usage()
        usage["cost_eur_estimated"] = 5.5  # Free trial hard_block is 5.0

        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value="mix")):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=True)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_monthly_usage", new=AsyncMock(return_value=usage)):
                        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_daily_usage", new=AsyncMock(return_value=_empty_daily_usage())):
                            result = run(check_submission_allowed("user-1", "web", duration_seconds=0))

        assert not result.allowed
        assert result.error_code == "cost_hard_block"


# --- Test: record_submission ---

class TestRecordSubmission:
    def test_record_audio_submission(self):
        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.increment_monthly_usage", new=AsyncMock()) as mock_monthly:
            with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.increment_daily_usage", new=AsyncMock()) as mock_daily:
                run(record_submission("user-1", "podcast", duration_seconds=600, estimated_cost_eur=0.08))

        mock_monthly.assert_called_once()
        call_kwargs = mock_monthly.call_args[1]
        assert call_kwargs["audio_minutes"] == 10
        assert call_kwargs["cost_eur"] == 0.08

        mock_daily.assert_called_once()
        daily_kwargs = mock_daily.call_args[1]
        assert daily_kwargs["audio_imports"] == 1

    def test_record_article_submission(self):
        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.increment_monthly_usage", new=AsyncMock()) as mock_monthly:
            with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.increment_daily_usage", new=AsyncMock()) as mock_daily:
                run(record_submission("user-1", "web", duration_seconds=0, estimated_cost_eur=0.005))

        mock_monthly.assert_called_once()
        call_kwargs = mock_monthly.call_args[1]
        assert call_kwargs["articles"] == 1

        mock_daily.assert_called_once()
        daily_kwargs = mock_daily.call_args[1]
        assert daily_kwargs["text_imports"] == 1

    def test_record_document_submission(self):
        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.increment_monthly_usage", new=AsyncMock()) as mock_monthly:
            with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.increment_daily_usage", new=AsyncMock()) as mock_daily:
                run(record_submission("user-1", "document", duration_seconds=0, estimated_cost_eur=0.005))

        mock_monthly.assert_called_once()
        call_kwargs = mock_monthly.call_args[1]
        assert call_kwargs["documents"] == 1

        mock_daily.assert_called_once()
        daily_kwargs = mock_daily.call_args[1]
        assert daily_kwargs["document_imports"] == 1


# --- Test: estimate_submission_cost ---

class TestEstimateSubmissionCost:
    def test_audio_cost_per_minute(self):
        # 10 minutes of audio
        cost = estimate_submission_cost("podcast", duration_seconds=600)
        assert cost == pytest.approx(0.08, abs=0.001)

    def test_article_flat_cost(self):
        cost = estimate_submission_cost("web", duration_seconds=0)
        assert cost == 0.005

    def test_document_flat_cost(self):
        cost = estimate_submission_cost("document", duration_seconds=0)
        assert cost == 0.005

    def test_youtube_flat_cost(self):
        cost = estimate_submission_cost("youtube", duration_seconds=0)
        assert cost == 0.005


# --- Test: no subscription and no trial denies ---

class TestNoSubscription:
    def test_no_subscription_no_trial_denied(self):
        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value=None)):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=False)):
                result = run(check_submission_allowed("user-1", "web", duration_seconds=0))

        assert not result.allowed
        assert result.error_code == "tier_quota_exceeded"

    def test_no_subscription_with_trial_allowed(self):
        """User without subscription but within trial period should be treated as Mix."""
        with patch("media_summarizer.core.services.quota_enforcer._get_user_tier", new=AsyncMock(return_value=None)):
            with patch("media_summarizer.core.services.quota_enforcer._is_free_trial_active", new=AsyncMock(return_value=True)):
                with patch("media_summarizer.core.services.quota_enforcer.pricing_config_service.get_pricing_config", new=AsyncMock(return_value=DEFAULT_PRICING_CONFIG)):
                    with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_monthly_usage", new=AsyncMock(return_value=_empty_monthly_usage())):
                        with patch("media_summarizer.core.services.quota_enforcer.quota_usage_db.get_daily_usage", new=AsyncMock(return_value=_empty_daily_usage())):
                            result = run(check_submission_allowed("user-1", "web", duration_seconds=0))

        assert result.allowed


# --- Integration test: media_submission wiring ---

class TestMediaSubmissionWiring:
    def test_quota_denied_returns_skipped(self):
        """media_submission.submit_media_for_user should return skipped when quota check fails."""
        from media_summarizer.core.services import media_submission

        user = MagicMock()
        user.id = "user-1"
        user.email = "test@example.com"

        denied_result = QuotaCheckResult.denied(
            error_code="tier_quota_exceeded",
            message="Monthly quota reached",
            http_status=403,
        )

        with patch("media_summarizer.core.services.media_submission.get_total_available_minutes", new=AsyncMock(return_value=999)):
            with patch("media_summarizer.core.services.media_submission.check_submission_allowed", new=AsyncMock(return_value=denied_result)):
                result = run(media_submission.submit_media_for_user(
                    user=user,
                    media_key="test-key-1",
                    media_title="Test Episode",
                    source_title="Test Podcast",
                    audio_url="http://example.com/audio.mp3",
                    duration_seconds=600,
                    source="podcast",
                ))

        assert result["status"] == "skipped"
        assert result["reason"] == "tier_quota_exceeded"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
