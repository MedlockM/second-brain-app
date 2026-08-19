"""
Consumption enforcement for the validated V1 model.

One unit is metered: the **minute**. A minute is a minute of media we pay a
transcription provider to process, plus the three flat conversions of the model
(a bought caption set counts 1, five document pages count 1, five sources of a
collection generation count 1). Everything that is not transcription — articles,
web pages, TikToks, Instagram photo posts, single-item AI generations — is
unlimited and debits nothing.

The rule that keeps the accounting honest: **the meter follows the provider call,
not the URL**. An API endpoint only ever *checks*; the debit happens at the place
that spends provider money (the Deepgram gate, the paid caption fetch, the
document parse, the collection generation). That is what makes "the same import
charged twice" and "a transcription nobody charged" unrepresentable rather than
merely fixed.

Three layers protect the margin (see docs/research/task-287-consumption-model):
1. the visible allowance itself — minutes x 0.00664 EUR is always a fraction of
   the tier's net revenue, so no per-user euro ceiling is needed;
2. invisible daily burst guards, which never refuse anything and only tell the
   owner an account is worth a look;
3. the shared provider pools, in `provider_pool_guard` — Apify credit and
   LlamaParse credits are platform-wide and no per-user allowance can protect them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any, Dict, Mapping, Optional, Tuple, TypeGuard

from media_summarizer.core.services import pricing_config_service
from media_summarizer.utils import quota_usage_db

logger = logging.getLogger(__name__)

# Mapping from subscription tier enum (S/M/L) to pricing config tier key
SUBSCRIPTION_TIER_TO_CONFIG: Mapping[str, str] = {
    "S": "text_only",
    "M": "mix",
    "L": "audio_heavy",
}

# The only two refusals the product has. Anything else the enforcer could once
# say (a per-category cap, a daily counter, a per-user euro ceiling) either no
# longer exists or is not a user-visible concept.
ERROR_OUT_OF_MINUTES = "out_of_minutes"
ERROR_ITEM_TOO_LONG = "item_too_long"

# Statuses that keep a subscription entitled.
_ENTITLED_STATUSES = frozenset({"active", "grace_period"})


@dataclass
class QuotaCheckResult:
    """Result of a consumption check."""

    allowed: bool
    error_code: Optional[str] = None  # stable machine-readable code
    message: Optional[str] = None  # product copy, shown to the user as-is
    http_status: int = 200

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


@dataclass
class EntitlementSnapshot:
    """Everything the product needs to know about one user's consumption.

    Single source of the figures the account tile, the paywall banner and every
    refusal message are built from, so the gauge the user reads and the gate that
    refuses them can never disagree.
    """

    user_id: str
    # Pricing config tier key ('text_only' | 'mix' | 'audio_heavy'), None when the
    # user has neither a subscription nor an active trial.
    tier: Optional[str] = None
    subscription_tier: Optional[str] = None  # store-facing enum (S/M/L)
    subscription_status: Optional[str] = None
    auto_renew: Optional[bool] = None
    is_entitled: bool = False
    is_free_trial: bool = False
    minutes_included: int = 0
    minutes_used: int = 0
    max_minutes_per_item: int = 0
    period_key: str = ""
    period_end: Optional[datetime] = None
    warning_threshold_pct: int = 80
    daily_usage: Dict[str, int] = field(default_factory=dict)

    @property
    def minutes_remaining(self) -> int:
        """Minutes left, clamped at 0.

        The counter itself is allowed to overshoot the allowance — a settlement
        stores the duration the provider actually billed, which is the truth —
        but the figure the user reads never goes negative.
        """
        return max(0, self.minutes_included - self.minutes_used)

    @property
    def warning_threshold_reached(self) -> bool:
        """Whether the app should warn that the period is running out."""
        if self.minutes_included <= 0:
            return False
        used_pct = (self.minutes_used / self.minutes_included) * 100
        return used_pct >= self.warning_threshold_pct


# ---------------------------------------------------------------------------
# Conversions (benchmark §3.1)
# ---------------------------------------------------------------------------


def minutes_for_seconds(duration_seconds: float) -> int:
    """Minutes charged for a transcription of `duration_seconds`.

    Rounded up, and never zero for media that exists: a 20-second voice note
    still costs a provider call.
    """
    if not duration_seconds or duration_seconds <= 0:
        return 0
    return max(1, ceil(duration_seconds / 60))


async def _conversion(key: str, fallback: int) -> int:
    config = await pricing_config_service.get_pricing_config()
    value = (config.get("unit_conversion", {}) or {}).get(key, fallback)
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return fallback


async def minutes_for_captions() -> int:
    """Minutes charged for a caption set we pay a provider to fetch.

    One flat provider fee, so one minute whatever the length of the video.
    """
    return await _conversion("captions_minutes", 1)


async def minutes_for_document_pages(page_count: int) -> int:
    """Minutes charged for a parsed document: one per five pages, minimum one."""
    pages_per_minute = await _conversion("document_pages_per_minute", 5)
    return max(1, ceil(max(1, page_count) / pages_per_minute))


async def minutes_for_collection_sources(source_count: int) -> int:
    """Minutes charged for a generation over a collection: one per five sources.

    A generation over a *single item* is free — its LLM cost is already inside
    what the item cost to ingest.
    """
    sources_per_minute = await _conversion("collection_sources_per_minute", 5)
    return max(1, ceil(max(1, source_count) / sources_per_minute))


async def cost_eur_per_minute() -> float:
    """What one minute costs us, from the single place that knows it."""
    config = await pricing_config_service.get_pricing_config()
    providers = config.get("providers", {}) or {}
    transcription = providers.get("transcription", {}) or {}
    try:
        return float(transcription.get("cost_per_minute_eur", 0.00664))
    except (TypeError, ValueError):
        return 0.00664


# ---------------------------------------------------------------------------
# Entitlement and billing period
# ---------------------------------------------------------------------------


# Opening and closing instants of a free trial. The trial is the only period a
# user gets without paying, and it has exactly one of these for its whole life.
TrialWindow = Tuple[datetime, datetime]


def _trial_period_key(window: TrialWindow) -> str:
    """Counter row key of a free trial: `trial:<YYYY-MM-DD of the account creation>`.

    Keyed on the *opening* of the window, not its close, because a trial holds one
    allowance for its whole life: extending `free_trial.duration_days` must move
    the end date without handing out a second helping of minutes, which is exactly
    what re-keying on the close would do. A subscription keys on its close instead
    — there, a new window is precisely what a new allowance means.
    """
    return f"trial:{window[0].strftime('%Y-%m-%d')}"


def _next_month_start(now: datetime) -> datetime:
    """First instant of next month — the reset date of a period with no anniversary."""
    return now.replace(
        year=now.year + 1 if now.month == 12 else now.year,
        month=1 if now.month == 12 else now.month + 1,
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


async def _active_subscription(user_id: str) -> Optional[Any]:
    """The subscription that entitles the user, or None."""
    from media_summarizer.utils import minute_db

    subs = await minute_db.get_subscriptions_by_user_id(user_id)
    if not subs:
        return None

    now = datetime.now(timezone.utc)
    for sub in subs:
        if sub.status.value in _ENTITLED_STATUSES:
            return sub
        # A cancelled subscription still entitles until the period it was paid for
        # actually ends.
        if (
            sub.status.value == "canceled"
            and sub.current_period_end
            and sub.current_period_end > now
        ):
            return sub
    return None


async def _free_trial_window(
    user_id: str, config: Mapping[str, Any]
) -> Optional[TrialWindow]:
    """The one billing window the user's free trial has, or None when there is none.

    A trial is a billing period like a subscription's, except it happens once and
    never renews: it opens at the account's creation instant and closes
    `free_trial.duration_days` later. Both the entitlement test and the date the
    app shows are read from this pair, so what refuses an import and what the
    gauge announces can never disagree.
    """
    free_trial = config.get("free_trial", {}) or {}
    if not free_trial.get("enabled"):
        return None

    from media_summarizer.utils import database_async as db

    user = await db.get_user_by_id(user_id)
    if not user:
        return None

    duration_days = int(free_trial.get("duration_days", 30) or 30)
    return user.created_at, user.created_at + timedelta(days=duration_days)


def _is_free_trial_active(
    window: Optional[TrialWindow], now: datetime
) -> TypeGuard[TrialWindow]:
    """Whether `now` is inside the trial window.

    The comparison is strict on the close instant, which is the same instant
    `period_end` announces: the last day of the trial is entitled, the moment it
    closes is not, and no extra day is granted by counting whole days.
    """
    return window is not None and now < window[1]


async def get_entitlement_snapshot(
    user_id: str,
    *,
    with_usage: bool = True,
) -> EntitlementSnapshot:
    """Resolve tier, allowance and consumption for one user.

    The billing period is never the calendar month: it is the window the user's
    entitlement actually runs on, so the counter row is keyed on the same
    `period_end` the app shows and nothing rolls over. For a subscription that is
    its renewal window, emptying on the anniversary; for a free trial it is the
    single window that opens at the account's creation and closes
    `free_trial.duration_days` later, so one trial grants one allowance and
    crossing a month boundary refills nothing.

    `with_usage=False` skips reading the counter row, for callers that only need
    to know which row to write to.
    """
    config = await pricing_config_service.get_pricing_config()
    tiers = config.get("tiers", {}) or {}
    warning_pct = int(
        (config.get("usage_gauge", {}) or {}).get("warning_threshold_pct", 80) or 80
    )

    subscription = await _active_subscription(user_id)
    now = datetime.now(timezone.utc)
    trial_window = (
        await _free_trial_window(user_id, config) if subscription is None else None
    )

    if subscription is not None:
        subscription_tier = subscription.tier.value
        tier = SUBSCRIPTION_TIER_TO_CONFIG.get(subscription_tier, "mix")
        tier_config = tiers.get(tier, {}) or {}
        period_end = subscription.current_period_end
        period_key = (
            f"sub:{period_end.strftime('%Y-%m-%d')}"
            if period_end
            else now.strftime("%Y-%m")
        )
        snapshot = EntitlementSnapshot(
            user_id=user_id,
            tier=tier,
            subscription_tier=subscription_tier,
            subscription_status=subscription.status.value,
            auto_renew=subscription.auto_renew_status,
            is_entitled=True,
            minutes_included=int(tier_config.get("minutes_per_month", 0) or 0),
            max_minutes_per_item=int(tier_config.get("max_minutes_per_item", 0) or 0),
            period_key=period_key,
            period_end=period_end or _next_month_start(now),
            warning_threshold_pct=warning_pct,
        )
    elif _is_free_trial_active(trial_window, now):
        free_trial = config.get("free_trial", {}) or {}
        tier = str(free_trial.get("tier", "mix"))
        tier_config = tiers.get(tier, {}) or {}
        snapshot = EntitlementSnapshot(
            user_id=user_id,
            tier=tier,
            subscription_tier=None,
            subscription_status="free_trial",
            is_entitled=True,
            is_free_trial=True,
            minutes_included=int(
                free_trial.get("minutes_per_month", tier_config.get("minutes_per_month", 0))
                or 0
            ),
            max_minutes_per_item=int(
                free_trial.get(
                    "max_minutes_per_item", tier_config.get("max_minutes_per_item", 0)
                )
                or 0
            ),
            period_key=_trial_period_key(trial_window),
            period_end=trial_window[1],
            warning_threshold_pct=warning_pct,
        )
    else:
        return EntitlementSnapshot(
            user_id=user_id,
            period_key=now.strftime("%Y-%m"),
            warning_threshold_pct=warning_pct,
        )

    if with_usage:
        usage = await quota_usage_db.get_monthly_usage(user_id, snapshot.period_key)
        snapshot.minutes_used = int(usage.get("minutes_used", 0) or 0)
    return snapshot


async def resolve_period_key(user_id: str) -> str:
    """The counter row key of the user's current billing period."""
    snapshot = await get_entitlement_snapshot(user_id, with_usage=False)
    return snapshot.period_key


# ---------------------------------------------------------------------------
# Copy
# ---------------------------------------------------------------------------


def format_minutes(minutes: int) -> str:
    """Human duration for a minute figure ("45 min", "3 h", "4 h 12 min")."""
    minutes = max(0, int(minutes))
    if minutes < 60:
        return f"{minutes} min"
    hours, rest = divmod(minutes, 60)
    return f"{hours} h" if rest == 0 else f"{hours} h {rest} min"


def format_reset_date(resets_at: Optional[datetime]) -> str:
    """Short reset date ("Sep 12"), or a safe phrase when it is unknown."""
    if resets_at is None:
        return "your next renewal"
    return f"{resets_at.strftime('%b')} {resets_at.day}"


def _out_of_minutes_message(snapshot: EntitlementSnapshot, minutes_needed: int) -> str:
    reset = format_reset_date(snapshot.period_end)
    remaining = snapshot.minutes_remaining
    if remaining <= 0:
        return f"You're out of minutes until {reset}. Upgrade to process this now."
    return (
        f"This import needs {minutes_needed} minutes and you have {remaining} left "
        f"until {reset}. Upgrade to process it now."
    )


def _item_too_long_message(snapshot: EntitlementSnapshot, minutes_needed: int) -> str:
    return (
        f"This is {format_minutes(minutes_needed)} long, over the "
        f"{format_minutes(snapshot.max_minutes_per_item)} a single import can use on "
        "your plan. Split it into shorter parts."
    )


# Named "audio and video" until task-299: without a plan `evaluate_submission`
# refuses *every* import, an article included, so singling out the metered paths
# promised a free tier that has never existed. Reading is unlimited *within* a
# plan, which is what the paywall says.
_NO_PLAN_MESSAGE = "Your plan has ended. Subscribe to keep saving to your library."


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


async def check_submission_allowed(
    user_id: str,
    *,
    minutes_needed: int = 0,
) -> QuotaCheckResult:
    """Check whether a submission may proceed.

    `minutes_needed` is what the submission will cost *if it is transcribed*:
    0 for a path that spends no provider minutes (an article, a TikTok), or when
    the duration is not known yet. A path with an unknown duration is accepted
    here and checked again by the transcription gate, which is the only place
    that knows the real length.

    Fails open on purpose: if the entitlement or the counters cannot be read, the
    entitlement is *unknown*, not absent. Locking a paying subscriber out because
    a DynamoDB call failed is worse than letting one submission through. A
    successful read that shows no plan still refuses.
    """
    try:
        snapshot = await get_entitlement_snapshot(user_id)
        result = evaluate_submission(snapshot, minutes_needed=minutes_needed)
        await _note_burst_guards(snapshot, minutes_needed=minutes_needed)
        return result
    except Exception as exc:
        logger.error(
            "quota.check_failed_open",
            extra={
                "user_id": user_id,
                "minutes_needed": minutes_needed,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
            exc_info=exc,
        )
        return QuotaCheckResult.ok()


def evaluate_submission(
    snapshot: EntitlementSnapshot,
    *,
    minutes_needed: int = 0,
) -> QuotaCheckResult:
    """Pure decision over a snapshot. No I/O, so every caller reads the same rules."""
    if not snapshot.is_entitled:
        return QuotaCheckResult.denied(
            error_code=ERROR_OUT_OF_MINUTES,
            message=_NO_PLAN_MESSAGE,
            http_status=403,
        )

    if minutes_needed <= 0:
        # Nothing to charge: reading is unlimited on every tier.
        return QuotaCheckResult.ok()

    if (
        snapshot.max_minutes_per_item > 0
        and minutes_needed > snapshot.max_minutes_per_item
    ):
        return QuotaCheckResult.denied(
            error_code=ERROR_ITEM_TOO_LONG,
            message=_item_too_long_message(snapshot, minutes_needed),
            http_status=413,
        )

    if minutes_needed > snapshot.minutes_remaining:
        return QuotaCheckResult.denied(
            error_code=ERROR_OUT_OF_MINUTES,
            message=_out_of_minutes_message(snapshot, minutes_needed),
            http_status=403,
        )

    return QuotaCheckResult.ok()


async def check_generation_allowed(
    user_id: str,
    *,
    scope: str,
    source_count: int,
) -> QuotaCheckResult:
    """Gate an AI generation.

    A generation over a single item is free: its LLM cost is already inside what
    the item cost to ingest. A generation over a collection is the only AI action
    whose cost scales with the content behind it, so it converts to minutes at one
    per five sources.

    Fails open like `check_submission_allowed`.
    """
    try:
        snapshot = await get_entitlement_snapshot(user_id)
        minutes_needed = (
            await minutes_for_collection_sources(source_count)
            if scope == "folder"
            else 0
        )
        result = evaluate_submission(snapshot, minutes_needed=minutes_needed)
        await _note_burst_guards(snapshot, minutes_needed=minutes_needed, generations=1)
        return result
    except Exception as exc:
        logger.error(
            "quota.generation_check_failed_open",
            extra={
                "user_id": user_id,
                "scope": scope,
                "source_count": source_count,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
            exc_info=exc,
        )
        return QuotaCheckResult.ok()


# ---------------------------------------------------------------------------
# Safety-net layer 2: invisible burst guards
# ---------------------------------------------------------------------------


async def _note_burst_guards(
    snapshot: EntitlementSnapshot,
    *,
    minutes_needed: int = 0,
    documents: int = 0,
    document_pages: int = 0,
    generations: int = 0,
) -> None:
    """Log — never refuse — when one account moves faster than any real user.

    These guards exist so a scripted account cannot burn a month of Lambda,
    LlamaParse pages or SQS traffic in an afternoon while staying inside its
    minute allowance. Every size sits an order of magnitude above the heaviest
    measured usage, so tripping one is a signal for the owner, not a limit the
    product talks about.
    """
    try:
        config = await pricing_config_service.get_pricing_config()
        guards = config.get("burst_guards", {}) or {}
        if not guards:
            return

        daily = await quota_usage_db.get_daily_usage(snapshot.user_id)
        snapshot.daily_usage = daily

        projected = {
            "minutes_per_day": daily.get("minutes", 0) + max(0, minutes_needed),
            "items_per_day": daily.get("items", 0) + 1,
            "documents_per_day": daily.get("documents", 0) + max(0, documents),
            "document_pages_per_day": daily.get("document_pages", 0)
            + max(0, document_pages),
            "generations_per_day": daily.get("generations", 0) + max(0, generations),
        }

        for guard_name, projected_value in projected.items():
            limit = int(guards.get(guard_name, 0) or 0)
            if limit > 0 and projected_value > limit:
                logger.warning(
                    "quota.burst_guard_tripped",
                    extra={
                        "user_id": snapshot.user_id,
                        "tier": snapshot.tier,
                        "guard": guard_name,
                        "limit": limit,
                        "projected": projected_value,
                    },
                )
    except Exception as exc:
        # A guard is an observation. It must never be the reason a submission fails.
        logger.warning(
            "quota.burst_guard_check_failed",
            extra={
                "user_id": snapshot.user_id,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )


# ---------------------------------------------------------------------------
# Debits — one per kind of provider spend
# ---------------------------------------------------------------------------


def gate_token(job_id: str) -> str:
    """Idempotency token of the submission-time debit for a job."""
    return f"{job_id}:gate"


def settlement_token(job_id: str) -> str:
    """Idempotency token of the post-transcription settlement for a job."""
    return f"{job_id}:settle"


def item_token(job_id: str) -> str:
    """Idempotency token of the daily item count for a submission.

    Distinct from `gate_token` because both writes land in the same daily row: a
    submission that debits minutes at the API would otherwise see its item count
    swallowed as an already-applied token.
    """
    return f"{job_id}:item"


async def _debit(
    user_id: str,
    *,
    minutes: int,
    idempotency_token: str,
    kind: str,
    documents: int = 0,
    document_pages: int = 0,
    generations: int = 0,
    items: int = 0,
) -> int:
    """Charge `minutes` once for `idempotency_token` and feed the burst counters.

    Best-effort by design: the provider has already been (or is about to be)
    billed, so a counter write failing must never fail the work the user is
    waiting for. Losing a debit under-counts one item; refusing the item the user
    already paid for is worse.

    Returns the minutes actually debited (0 when the token had already been
    applied, or when the write failed).
    """
    minutes = max(0, int(minutes))
    try:
        applied = True
        if minutes > 0:
            unit_cost = await cost_eur_per_minute()
            applied = await quota_usage_db.increment_monthly_usage(
                user_id,
                await resolve_period_key(user_id),
                minutes=minutes,
                cost_eur=round(minutes * unit_cost, 4),
                idempotency_token=idempotency_token,
            )

        await quota_usage_db.increment_daily_usage(
            user_id,
            minutes=minutes,
            items=items,
            documents=documents,
            document_pages=document_pages,
            generations=generations,
            idempotency_token=idempotency_token,
        )
    except Exception as exc:
        logger.error(
            "quota.debit_failed",
            extra={
                "user_id": user_id,
                "kind": kind,
                "minutes": minutes,
                "idempotency_token": idempotency_token,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
            exc_info=exc,
        )
        return 0

    if not applied:
        logger.info(
            "quota.debit_already_applied",
            extra={
                "user_id": user_id,
                "kind": kind,
                "idempotency_token": idempotency_token,
            },
        )
        return 0

    logger.info(
        "quota.debited",
        extra={
            "user_id": user_id,
            "kind": kind,
            "minutes": minutes,
            "idempotency_token": idempotency_token,
        },
    )
    return minutes


async def record_transcription_minutes(
    user_id: str,
    *,
    minutes: int,
    idempotency_token: str,
) -> int:
    """Charge minutes of transcription we are about to pay a provider for."""
    return await _debit(
        user_id,
        minutes=minutes,
        idempotency_token=idempotency_token,
        kind="transcription",
    )


async def record_captions_purchase(user_id: str, *, idempotency_token: str) -> int:
    """Charge the flat unit of a caption set bought from a provider.

    Called where the transcript actually came back, so a video whose captions we
    got for free (or that failed) costs nothing.
    """
    return await _debit(
        user_id,
        minutes=await minutes_for_captions(),
        idempotency_token=idempotency_token,
        kind="captions",
    )


async def record_document_parse(
    user_id: str,
    *,
    page_count: int,
    idempotency_token: str,
) -> int:
    """Charge a parsed document at one minute per five pages, minimum one."""
    pages = max(1, int(page_count or 1))
    return await _debit(
        user_id,
        minutes=await minutes_for_document_pages(pages),
        idempotency_token=idempotency_token,
        kind="document",
        documents=1,
        document_pages=pages,
    )


async def record_generation(
    user_id: str,
    *,
    scope: str,
    source_count: int,
    idempotency_token: str,
) -> int:
    """Charge one AI generation: nothing over a single item, minutes over a collection."""
    minutes = (
        await minutes_for_collection_sources(source_count) if scope == "folder" else 0
    )
    return await _debit(
        user_id,
        minutes=minutes,
        idempotency_token=idempotency_token,
        kind=f"generation:{scope}",
        generations=1,
    )


async def record_submitted_item(user_id: str, *, idempotency_token: str) -> None:
    """Count one accepted submission against the daily item guard.

    Minutes are never charged here: they are charged where the provider call is
    made, which for a link is a worker, minutes later. This is the only place the
    daily item counter moves, so a submission is counted exactly once whatever
    path it later takes -- including the free paths (articles, web pages, clips
    with captions) that never reach a debit at all, which is precisely what this
    invisible guard is there to bound.
    """
    await _debit(
        user_id,
        minutes=0,
        idempotency_token=idempotency_token,
        kind="submitted_item",
        items=1,
    )


async def record_observed_cost(
    user_id: str,
    *,
    cost_eur: float,
    idempotency_token: str,
) -> None:
    """Store a measured provider cost against the period, for observability.

    Nothing reads `cost_eur_estimated` to allow or refuse anything — the minute
    allowance is what bounds spend. This is here so the owner can compare the
    model's assumptions with the real invoice.
    """
    if cost_eur <= 0:
        return
    try:
        await quota_usage_db.increment_monthly_usage(
            user_id,
            await resolve_period_key(user_id),
            cost_eur=cost_eur,
            idempotency_token=idempotency_token,
        )
    except Exception as exc:
        logger.warning(
            "quota.cost_record_failed",
            extra={
                "user_id": user_id,
                "idempotency_token": idempotency_token,
                "error": str(exc),
                "error_type": type(exc).__name__,
            },
        )


# ---------------------------------------------------------------------------
# Transcription gate and settlement
# ---------------------------------------------------------------------------


@dataclass
class TranscriptionGateResult:
    """Outcome of the single gate that guards a transcription enqueue."""

    allowed: bool
    debited_minutes: int = 0
    provisional: bool = False
    error_code: Optional[str] = None
    message: Optional[str] = None
    http_status: int = 200


async def gate_transcription(
    *,
    user_id: str,
    job_id: str,
    duration_seconds: float = 0,
    debit: bool = True,
) -> TranscriptionGateResult:
    """Check and debit, immediately before a transcription is enqueued.

    Every producer that puts a message on the transcription queue calls this and
    forwards `debited_minutes` in the payload, so the settlement in the worker
    only applies the delta with the duration the provider actually billed.

    `duration_seconds <= 0` means the duration could not be established in time.
    The submission is still accepted — refusing a legitimate share because a
    metadata probe timed out is not acceptable — and a provisional single minute
    is debited, which the settlement corrects.

    `debit=False` charges nothing while still running the check, for a save the
    caller established is free (the user already holds this content). The two
    halves are separable on purpose: the debit measures what the user consumed,
    the check protects the provider bill.
    """
    minutes_needed = minutes_for_seconds(duration_seconds) or 1
    check = await check_submission_allowed(user_id, minutes_needed=minutes_needed)
    if not check.allowed:
        return TranscriptionGateResult(
            allowed=False,
            error_code=check.error_code,
            message=check.message,
            http_status=check.http_status,
        )

    if not debit:
        return TranscriptionGateResult(allowed=True, debited_minutes=0)

    debited = await record_transcription_minutes(
        user_id,
        minutes=minutes_needed,
        idempotency_token=gate_token(job_id),
    )
    provisional = duration_seconds <= 0
    logger.info(
        "quota.transcription_gate_debited",
        extra={
            "user_id": user_id,
            "job_id": job_id,
            "duration_seconds": duration_seconds,
            "debited_minutes": debited,
            "provisional": provisional,
        },
    )
    return TranscriptionGateResult(
        allowed=True,
        debited_minutes=debited,
        provisional=provisional,
    )


async def settle_transcription_minutes(
    *,
    user_id: str,
    job_id: str,
    actual_duration_seconds: float,
    already_debited_minutes: int = 0,
) -> int:
    """Reconcile the counter with the duration the provider actually billed.

    Called from the transcription worker with the provider's own duration. Only
    the difference with what the gate debited is applied, under a per-job token,
    so a redelivered message cannot debit twice.

    Overrun policy: the true value is stored even when it takes the user past
    their allowance — the counter is the truth, the display clamps it, and the
    *next* import is refused naturally. Minutes are never refunded, so a delta of
    zero or less is a no-op.
    """
    real_minutes = minutes_for_seconds(actual_duration_seconds)
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

    applied = await _debit(
        user_id,
        minutes=delta,
        idempotency_token=settlement_token(job_id),
        kind="settlement",
    )
    if applied:
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
    return applied
