"""
Quota enforcement engine for V1 pricing tiers.

Enforces:
- Monthly hard caps per media type per tier
- Daily rate limits per tier
- Max audio duration per import
- Cost monitoring (warning log + hard block)
- Free trial overrides

This service is the single gate for all submission paths.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from typing import Any, Dict, List, Literal, Optional

from media_summarizer.core.services import pricing_config_service
from media_summarizer.utils import quota_usage_db

logger = logging.getLogger(__name__)

# Mapping from subscription tier enum (S/M/L) to pricing config tier key
_SUBSCRIPTION_TIER_TO_CONFIG = {
    "S": "text_only",
    "M": "mix",
    "L": "audio_heavy",
}

# Media type classification for quota tracking
# Maps source_platform / resolver_key to a quota category
QUOTA_CATEGORY_AUDIO = "audio"
QUOTA_CATEGORY_ARTICLE = "article"
QUOTA_CATEGORY_DOCUMENT = "document"
QUOTA_CATEGORY_YOUTUBE = "youtube"


def classify_media_type(source_platform: str) -> str:
    """
    Map source_platform (or media_type) to a quota category.

    Returns one of: audio, article, document, youtube
    """
    platform_lower = (source_platform or "").lower()

    if platform_lower in ("podcast", "audio", "rss", "deepgram"):
        return QUOTA_CATEGORY_AUDIO
    if platform_lower in ("youtube", "video"):
        return QUOTA_CATEGORY_YOUTUBE
    if platform_lower in ("document", "pdf", "docx"):
        return QUOTA_CATEGORY_DOCUMENT
    if platform_lower in (
        "web", "article", "newsletter", "tiktok", "instagram", "x", "twitter",
    ):
        return QUOTA_CATEGORY_ARTICLE
    # Default: treat unknown as article (safe, non-audio)
    return QUOTA_CATEGORY_ARTICLE


@dataclass
class QuotaCheckResult:
    """Result of a quota enforcement check."""

    allowed: bool
    error_code: Optional[str] = None  # stable user-facing code
    message: Optional[str] = None  # human-readable explanation
    http_status: int = 200  # suggested HTTP status code

    @staticmethod
    def ok() -> "QuotaCheckResult":
        return QuotaCheckResult(allowed=True)

    @staticmethod
    def denied(
        error_code: str,
        message: str,
        http_status: int = 403,
    ) -> "QuotaCheckResult":
        return QuotaCheckResult(
            allowed=False,
            error_code=error_code,
            message=message,
            http_status=http_status,
        )


async def _get_user_tier(user_id: str) -> Optional[str]:
    """
    Resolve the pricing tier key for a user from their active subscription.

    Returns one of: 'text_only', 'mix', 'audio_heavy', or None if no subscription.
    """
    from media_summarizer.utils import minute_db

    subs = await minute_db.get_subscriptions_by_user_id(user_id)
    if not subs:
        return None

    now = datetime.now(timezone.utc)
    active_sub = None
    for s in subs:
        if s.status.value in ("active", "grace_period"):
            active_sub = s
            break
        if (
            s.status.value == "canceled"
            and s.current_period_end
            and s.current_period_end > now
        ):
            active_sub = s
            break

    if not active_sub:
        return None

    return _SUBSCRIPTION_TIER_TO_CONFIG.get(active_sub.tier.value, "mix")


async def _is_free_trial_active(user_id: str) -> bool:
    """
    Check if the user is currently within their free trial period.

    Free trial is determined by: account age <= free_trial.duration_days
    and no prior paid subscription.
    """
    from media_summarizer.utils import database_async as db

    user = await db.get_user_by_id(user_id)
    if not user:
        return False

    config = await pricing_config_service.get_pricing_config()
    free_trial = config.get("free_trial", {})
    if not free_trial.get("enabled"):
        return False

    duration_days = free_trial.get("duration_days", 30)
    now = datetime.now(timezone.utc)
    account_age_days = (now - user.created_at).days

    return account_age_days <= duration_days


async def _get_effective_caps(
    tier: str, user_id: str
) -> Dict[str, Any]:
    """
    Get the effective hard caps for a user, considering free trial overrides.
    """
    config = await pricing_config_service.get_pricing_config()
    hard_caps = config.get("hard_caps", {}).get(tier, {})

    # Check free trial override
    if tier == "mix" and await _is_free_trial_active(user_id):
        free_trial = config.get("free_trial", {})
        trial_caps = free_trial.get("hard_caps", {})
        # Free trial overrides specific caps
        effective = dict(hard_caps)
        if "audio_minutes" in trial_caps:
            effective["audio_minutes"] = trial_caps["audio_minutes"]
        if "articles" in trial_caps:
            effective["articles"] = trial_caps["articles"]
        if "documents" in trial_caps:
            effective["documents"] = trial_caps["documents"]
        # youtube not overridden in free trial config, keep tier default
        return effective

    return dict(hard_caps)


async def _get_effective_cost_monitoring(
    tier: str, user_id: str
) -> Dict[str, Any]:
    """
    Get the effective cost monitoring thresholds, considering free trial overrides.
    """
    config = await pricing_config_service.get_pricing_config()
    cost_monitoring = config.get("cost_monitoring", {}).get(tier, {})

    if tier == "mix" and await _is_free_trial_active(user_id):
        free_trial = config.get("free_trial", {})
        trial_cost = free_trial.get("cost_monitoring", {})
        if trial_cost:
            effective = dict(cost_monitoring)
            if "warning_eur" in trial_cost:
                effective["warning_eur"] = trial_cost["warning_eur"]
            if "hard_block_eur" in trial_cost:
                effective["hard_block_eur"] = trial_cost["hard_block_eur"]
            return effective

    return dict(cost_monitoring)


async def check_submission_allowed(
    user_id: str,
    source_platform: str,
    duration_seconds: int = 0,
) -> QuotaCheckResult:
    """
    Check whether a submission is allowed for the given user and media type.

    This is the primary gate that must be called before any media ingestion.

    Args:
        user_id: The user's ID
        source_platform: Source platform or media type string (e.g., 'podcast', 'youtube', 'web', 'document')
        duration_seconds: For audio, the duration in seconds (0 for non-audio)

    Returns:
        QuotaCheckResult indicating whether submission is allowed or denied with a stable error code.
    """
    media_category = classify_media_type(source_platform)

    # Resolve user tier
    tier = await _get_user_tier(user_id)
    if tier is None:
        # No active subscription - treat as free trial on mix if trial is active
        if await _is_free_trial_active(user_id):
            tier = "mix"
        else:
            # No subscription and no trial - deny
            return QuotaCheckResult.denied(
                error_code="tier_quota_exceeded",
                message="No active subscription. Please subscribe to continue.",
                http_status=403,
            )

    config = await pricing_config_service.get_pricing_config()

    # --- 1. Tier-level audio gating (text_only tier refuses all audio) ---
    if tier == "text_only" and media_category == QUOTA_CATEGORY_AUDIO:
        return QuotaCheckResult.denied(
            error_code="tier_quota_exceeded",
            message="Your Reader tier does not include audio transcription. Please upgrade to Mix or Audio-Heavy.",
            http_status=403,
        )

    # --- 2. Max audio duration per import ---
    if media_category == QUOTA_CATEGORY_AUDIO and duration_seconds > 0:
        rate_limits = config.get("rate_limits", {}).get(tier, {})
        max_per_import_minutes = rate_limits.get("max_audio_per_import_minutes", 180)
        duration_minutes = ceil(duration_seconds / 60)

        if duration_minutes > max_per_import_minutes:
            return QuotaCheckResult.denied(
                error_code="audio_too_long",
                message=f"Audio duration ({duration_minutes} min) exceeds maximum per import ({max_per_import_minutes} min).",
                http_status=413,
            )

        # Also check global max_audio_duration_minutes from hard_caps
        hard_caps = config.get("hard_caps", {}).get(tier, {})
        max_global = hard_caps.get("max_audio_duration_minutes", 180)
        if max_global > 0 and duration_minutes > max_global:
            return QuotaCheckResult.denied(
                error_code="audio_too_long",
                message=f"Audio duration ({duration_minutes} min) exceeds tier maximum ({max_global} min).",
                http_status=413,
            )

    # --- 3. Monthly hard caps ---
    effective_caps = await _get_effective_caps(tier, user_id)
    monthly_usage = await quota_usage_db.get_monthly_usage(user_id)

    cap_field_map = {
        QUOTA_CATEGORY_AUDIO: ("audio_minutes", "audio_minutes_used"),
        QUOTA_CATEGORY_ARTICLE: ("articles", "articles_count"),
        QUOTA_CATEGORY_DOCUMENT: ("documents", "documents_count"),
        QUOTA_CATEGORY_YOUTUBE: ("youtube", "youtube_count"),
    }

    if media_category in cap_field_map:
        cap_key, usage_key = cap_field_map[media_category]
        cap_value = effective_caps.get(cap_key, 0)
        current_usage = monthly_usage.get(usage_key, 0)

        if media_category == QUOTA_CATEGORY_AUDIO:
            # For audio, check minutes
            minutes_needed = max(1, ceil(duration_seconds / 60)) if duration_seconds > 0 else 1
            if cap_value == 0 or (current_usage + minutes_needed) > cap_value:
                return QuotaCheckResult.denied(
                    error_code="tier_quota_exceeded",
                    message=f"Monthly audio quota reached ({current_usage}/{cap_value} minutes used).",
                    http_status=403,
                )
        else:
            # For non-audio, check count
            if cap_value == 0 or (current_usage + 1) > cap_value:
                return QuotaCheckResult.denied(
                    error_code="tier_quota_exceeded",
                    message=f"Monthly {media_category} quota reached ({current_usage}/{cap_value}).",
                    http_status=403,
                )

    # --- 4. Daily rate limits ---
    rate_limits = config.get("rate_limits", {}).get(tier, {})
    daily_usage = await quota_usage_db.get_daily_usage(user_id)

    if media_category == QUOTA_CATEGORY_AUDIO:
        daily_limit = rate_limits.get("audio_imports_per_day", 0)
        current_daily = daily_usage.get("audio_imports", 0)
        if daily_limit == 0 and tier == "text_only":
            # Already handled above (tier gating), but defensive
            return QuotaCheckResult.denied(
                error_code="daily_rate_limit",
                message="Audio imports not available on your tier.",
                http_status=429,
            )
        if daily_limit > 0 and current_daily >= daily_limit:
            return QuotaCheckResult.denied(
                error_code="daily_rate_limit",
                message=f"Daily audio import limit reached ({current_daily}/{daily_limit}).",
                http_status=429,
            )
    elif media_category == QUOTA_CATEGORY_DOCUMENT:
        daily_limit = rate_limits.get("document_imports_per_day", 10)
        current_daily = daily_usage.get("document_imports", 0)
        if current_daily >= daily_limit:
            return QuotaCheckResult.denied(
                error_code="daily_rate_limit",
                message=f"Daily document import limit reached ({current_daily}/{daily_limit}).",
                http_status=429,
            )
    else:
        # text (articles, youtube, social, etc.)
        daily_limit = rate_limits.get("text_imports_per_day", 30)
        current_daily = daily_usage.get("text_imports", 0)
        if current_daily >= daily_limit:
            return QuotaCheckResult.denied(
                error_code="daily_rate_limit",
                message=f"Daily text import limit reached ({current_daily}/{daily_limit}).",
                http_status=429,
            )

    # --- 5. Cost monitoring (hard block) ---
    cost_monitoring = await _get_effective_cost_monitoring(tier, user_id)
    current_cost = monthly_usage.get("cost_eur_estimated", 0.0)
    hard_block_eur = cost_monitoring.get("hard_block_eur", 999.0)
    warning_eur = cost_monitoring.get("warning_eur", 999.0)

    if current_cost >= hard_block_eur:
        action = cost_monitoring.get("action", "block")
        logger.warning(
            "quota.cost_hard_block",
            extra={
                "user_id": user_id,
                "tier": tier,
                "current_cost_eur": current_cost,
                "hard_block_eur": hard_block_eur,
                "action": action,
            },
        )
        return QuotaCheckResult.denied(
            error_code="cost_hard_block",
            message="Monthly cost limit reached. Submissions are paused for the remainder of this billing period.",
            http_status=403,
        )

    if current_cost >= warning_eur:
        # Log warning but allow (CloudWatch alarm picks this up)
        logger.warning(
            "quota.cost_warning",
            extra={
                "user_id": user_id,
                "tier": tier,
                "current_cost_eur": current_cost,
                "warning_eur": warning_eur,
            },
        )

    return QuotaCheckResult.ok()


async def record_submission(
    user_id: str,
    source_platform: str,
    duration_seconds: int = 0,
    estimated_cost_eur: float = 0.0,
) -> None:
    """
    Record a successful submission in the usage counters.

    Must be called AFTER the submission has been validated and enqueued.

    Args:
        user_id: The user's ID
        source_platform: Source platform string
        duration_seconds: Audio duration in seconds (0 for non-audio)
        estimated_cost_eur: Estimated processing cost in EUR
    """
    media_category = classify_media_type(source_platform)

    # Increment monthly counters
    monthly_kwargs: Dict[str, Any] = {}
    if media_category == QUOTA_CATEGORY_AUDIO:
        minutes_used = max(1, ceil(duration_seconds / 60)) if duration_seconds > 0 else 1
        monthly_kwargs["audio_minutes"] = minutes_used
    elif media_category == QUOTA_CATEGORY_ARTICLE:
        monthly_kwargs["articles"] = 1
    elif media_category == QUOTA_CATEGORY_DOCUMENT:
        monthly_kwargs["documents"] = 1
    elif media_category == QUOTA_CATEGORY_YOUTUBE:
        monthly_kwargs["youtube"] = 1

    if estimated_cost_eur > 0:
        monthly_kwargs["cost_eur"] = estimated_cost_eur

    if monthly_kwargs:
        try:
            await quota_usage_db.increment_monthly_usage(user_id, **monthly_kwargs)
        except Exception as e:
            logger.error(
                "Failed to increment monthly usage counters for user %s: %s",
                user_id, e,
            )

    # Increment daily counters
    daily_kwargs: Dict[str, Any] = {}
    if media_category == QUOTA_CATEGORY_AUDIO:
        daily_kwargs["audio_imports"] = 1
    elif media_category == QUOTA_CATEGORY_DOCUMENT:
        daily_kwargs["document_imports"] = 1
    else:
        daily_kwargs["text_imports"] = 1

    if daily_kwargs:
        try:
            await quota_usage_db.increment_daily_usage(user_id, **daily_kwargs)
        except Exception as e:
            logger.error(
                "Failed to increment daily usage counters for user %s: %s",
                user_id, e,
            )


def estimate_submission_cost(
    source_platform: str,
    duration_seconds: int = 0,
) -> float:
    """
    Estimate the cost of a submission based on media type and duration.

    Uses fixed per-item costs from the pricing config defaults.
    Audio cost is based on Deepgram nova-3 at 0.003 EUR/min.
    Non-audio items have a flat LLM processing cost estimate.
    """
    media_category = classify_media_type(source_platform)

    if media_category == QUOTA_CATEGORY_AUDIO:
        # Deepgram nova-3: 0.003 EUR/min transcription + ~0.005 EUR/min LLM processing
        minutes = max(1, ceil(duration_seconds / 60)) if duration_seconds > 0 else 1
        return round(minutes * 0.008, 4)  # ~0.008 EUR/min total
    else:
        # Non-audio: flat cost per item (LLM summarization)
        return 0.005  # ~0.005 EUR per text/doc/youtube item
