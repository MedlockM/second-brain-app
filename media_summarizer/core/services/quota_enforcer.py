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
from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from typing import Any, Dict, Optional

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

# Deepgram nova-3 (~0.003 EUR/min) plus downstream LLM processing.
_AUDIO_COST_EUR_PER_MINUTE = 0.008


# Canonical platform string to pass to the quota engine for a submission that
# will be transcribed. Every path that spends Deepgram minutes must classify as
# audio, whatever the URL it came from (task-250 Layer 0).
QUOTA_PLATFORM_AUDIO = "audio"

# Platforms whose ingestion always ends in a paid transcription. `spotify`,
# `apple_podcasts`, `deezer` and `direct_url` used to fall through to the
# `article` default, which made the audio caps and the `text_only` tier gate
# unreachable for them.
_AUDIO_PLATFORMS = frozenset(
    {
        "podcast",
        "audio",
        "deepgram",
        "rss",
        "rss_feed",
        "spotify",
        "apple_podcasts",
        "deezer",
        "direct_url",
        "manual",
    }
)

_YOUTUBE_PLATFORMS = frozenset({"youtube", "video"})

_DOCUMENT_PLATFORMS = frozenset({"document", "pdf", "docx"})


def classify_media_type(source_platform: str) -> str:
    """
    Map source_platform (or media_type) to a quota category.

    Returns one of: audio, article, document, youtube

    Anything unrecognised stays `article`: a wrong guess must not silently open
    the audio budget. Paths that know they are about to transcribe pass
    `QUOTA_PLATFORM_AUDIO` explicitly instead of relying on this mapping (a
    YouTube video without captions, a TikTok without subtitles, a WhatsApp voice
    note).
    """
    platform_lower = (source_platform or "").strip().lower()

    if platform_lower in _AUDIO_PLATFORMS:
        return QUOTA_CATEGORY_AUDIO
    if platform_lower in _YOUTUBE_PLATFORMS:
        return QUOTA_CATEGORY_YOUTUBE
    if platform_lower in _DOCUMENT_PLATFORMS:
        return QUOTA_CATEGORY_DOCUMENT
    # Default: treat unknown as article (safe, non-audio). Covers web, article,
    # tiktok, instagram, x, twitter, whatsapp text shares and `unknown`.
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

    Fails open on purpose: if the tier or the counters cannot be read, the
    entitlement is *unknown*, not absent. Locking a paying subscriber out of the
    product because a DynamoDB call failed is a worse outcome than letting one
    submission through, so the failure is logged and the submission proceeds. A
    successful read that shows no subscription still denies.

    Args:
        user_id: The user's ID
        source_platform: Source platform or media type string (e.g., 'podcast', 'youtube', 'web', 'document')
        duration_seconds: For audio, the duration in seconds (0 for non-audio)

    Returns:
        QuotaCheckResult indicating whether submission is allowed or denied with a stable error code.
    """
    try:
        return await _evaluate_submission_allowed(
            user_id=user_id,
            source_platform=source_platform,
            duration_seconds=duration_seconds,
        )
    except Exception as exc:
        logger.error(
            "quota.check_failed_open",
            extra={
                "user_id": user_id,
                "source_platform": source_platform,
                "duration_seconds": duration_seconds,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
            exc_info=exc,
        )
        return QuotaCheckResult.ok()


async def _evaluate_submission_allowed(
    *,
    user_id: str,
    source_platform: str,
    duration_seconds: int = 0,
) -> QuotaCheckResult:
    """Quota evaluation proper. Raises on infrastructure failure; the caller
    (`check_submission_allowed`) decides what to do about it."""
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
    idempotency_token: Optional[str] = None,
) -> int:
    """
    Record a successful submission in the usage counters.

    Must be called AFTER the submission has been validated and enqueued.

    Args:
        user_id: The user's ID
        source_platform: Source platform string
        duration_seconds: Audio duration in seconds (0 for non-audio)
        estimated_cost_eur: Estimated processing cost in EUR
        idempotency_token: When set, the counters are incremented at most once
            for this token, whatever how many times the caller runs (SQS
            redelivery, worker retry).

    Returns:
        The number of audio minutes debited (0 for non-audio submissions). Audio
        callers must carry this figure downstream so the Deepgram settlement only
        applies the difference with the real duration.
    """
    media_category = classify_media_type(source_platform)

    # Increment monthly counters
    minutes_used = 0
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
            await quota_usage_db.increment_monthly_usage(
                user_id,
                idempotency_token=idempotency_token,
                **monthly_kwargs,
            )
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
            await quota_usage_db.increment_daily_usage(
                user_id,
                idempotency_token=idempotency_token,
                **daily_kwargs,
            )
        except Exception as e:
            logger.error(
                "Failed to increment daily usage counters for user %s: %s",
                user_id, e,
            )

    return minutes_used


@dataclass
class AudioQuotaGateResult:
    """Outcome of the single audio gate that guards a Deepgram enqueue."""

    allowed: bool
    debited_minutes: int = 0
    provisional: bool = False
    error_code: Optional[str] = None
    message: Optional[str] = None
    http_status: int = 200


def gate_token(job_id: str) -> str:
    """Idempotency token of the submission-time debit for a job."""
    return f"{job_id}:gate"


def settlement_token(job_id: str) -> str:
    """Idempotency token of the post-transcription settlement for a job."""
    return f"{job_id}:settle"


async def gate_audio_submission(
    *,
    user_id: str,
    job_id: str,
    duration_seconds: int = 0,
    source_platform: str = QUOTA_PLATFORM_AUDIO,
) -> AudioQuotaGateResult:
    """
    Single check-and-debit gate for a submission that is about to cost Deepgram
    minutes (task-250 Layer 1).

    Every producer that enqueues on the Deepgram queue calls this immediately
    before sending the message, and forwards `debited_minutes` in the payload so
    the settlement in the transcription worker only applies the delta.

    `duration_seconds <= 0` means the duration could not be established in time.
    The submission is still accepted — refusing a legitimate share because a
    metadata probe timed out is not acceptable — and a provisional single minute
    is debited, which the settlement corrects with Deepgram's own figure.
    """
    check = await check_submission_allowed(
        user_id=user_id,
        source_platform=source_platform,
        duration_seconds=max(0, duration_seconds),
    )
    if not check.allowed:
        return AudioQuotaGateResult(
            allowed=False,
            error_code=check.error_code,
            message=check.message,
            http_status=check.http_status,
        )

    debited = await record_submission(
        user_id=user_id,
        source_platform=source_platform,
        duration_seconds=max(0, duration_seconds),
        estimated_cost_eur=estimate_submission_cost(
            source_platform, max(0, duration_seconds)
        ),
        idempotency_token=gate_token(job_id),
    )

    provisional = duration_seconds <= 0
    logger.info(
        "quota.audio_gate_debited",
        extra={
            "user_id": user_id,
            "job_id": job_id,
            "source_platform": source_platform,
            "duration_seconds": duration_seconds,
            "debited_minutes": debited,
            "provisional": provisional,
        },
    )
    return AudioQuotaGateResult(
        allowed=True,
        debited_minutes=debited,
        provisional=provisional,
    )


async def settle_audio_minutes(
    *,
    user_id: str,
    job_id: str,
    actual_duration_seconds: float,
    already_debited_minutes: int = 0,
) -> int:
    """
    Reconcile the monthly audio counter with the duration the provider actually
    billed (task-250 Layer 2).

    Called from the transcription worker with Deepgram's own `metadata.duration`.
    Only the difference with what the gate already debited is applied, under a
    per-job idempotency token, so a redelivered message cannot debit twice.

    Overrun policy decided by the owner: the true value is stored even when it
    takes the user past their monthly cap — the counter is the truth, the display
    clamps it, and the *next* import is refused naturally. Minutes are never
    refunded, so a delta of zero or less is a no-op.

    Returns the number of minutes actually added (0 when nothing was due or when
    the settlement had already been applied).
    """
    real_minutes = (
        max(1, ceil(actual_duration_seconds / 60))
        if actual_duration_seconds and actual_duration_seconds > 0
        else 0
    )
    if real_minutes <= 0:
        logger.warning(
            "quota.settlement_skipped_no_duration",
            extra={"user_id": user_id, "job_id": job_id},
        )
        return 0

    delta = real_minutes - max(0, already_debited_minutes)
    if delta <= 0:
        logger.info(
            "quota.settlement_no_delta",
            extra={
                "user_id": user_id,
                "job_id": job_id,
                "real_minutes": real_minutes,
                "already_debited_minutes": already_debited_minutes,
            },
        )
        return 0

    try:
        applied = await quota_usage_db.increment_monthly_usage(
            user_id,
            audio_minutes=delta,
            cost_eur=round(delta * _AUDIO_COST_EUR_PER_MINUTE, 4),
            idempotency_token=settlement_token(job_id),
        )
    except Exception as exc:
        # Losing a settlement under-counts one job. Failing the transcription the
        # user already paid for would be worse, so this is logged and swallowed.
        logger.error(
            "quota.settlement_failed",
            extra={
                "user_id": user_id,
                "job_id": job_id,
                "real_minutes": real_minutes,
                "delta_minutes": delta,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
            exc_info=exc,
        )
        return 0

    if not applied:
        logger.info(
            "quota.settlement_already_applied",
            extra={"user_id": user_id, "job_id": job_id, "delta_minutes": delta},
        )
        return 0

    logger.info(
        "quota.settlement_applied",
        extra={
            "user_id": user_id,
            "job_id": job_id,
            "real_minutes": real_minutes,
            "already_debited_minutes": already_debited_minutes,
            "delta_minutes": delta,
        },
    )
    return delta


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
        return round(minutes * _AUDIO_COST_EUR_PER_MINUTE, 4)
    else:
        # Non-audio: flat cost per item (LLM summarization)
        return 0.005  # ~0.005 EUR per text/doc/youtube item
