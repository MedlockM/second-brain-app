"""
RevenueCat webhook handler for processing subscription events.

Handles INITIAL_PURCHASE, RENEWAL, CANCELLATION, EXPIRATION,
BILLING_ISSUE_DETECTED, and PRODUCT_CHANGE events from RevenueCat.

Idempotency is enforced via a revenucat_events DynamoDB table.

Every handler resolves *which* subscription the event is about before touching
anything — `_EventSubject` and `_match_subscription` below. A user holds one row
per store and per product, so nothing here may act on "the user's first row", and
an event matching no row is reported at ERROR rather than dropped. The order two
events arrive in must not change the state they leave behind, which is why
CANCELLATION writes its flags whatever the row's status and only RENEWAL is
allowed to bring an expired row back.
"""

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Request, status

from media_summarizer.core.config import settings
from media_summarizer.core.models.billing import (
    Subscription,
    SubscriptionPlatform,
    SubscriptionStatus,
    SubscriptionTier,
)
from media_summarizer.utils import database_async, minute_db
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import log_event

router = APIRouter()
logger = logging.getLogger(__name__)

# RevenueCat entitlement lookup key -> subscription tier.
#
# One entitlement per access level, which is RevenueCat's recommended layout for
# multi-tier apps. The entitlement is stable across stores, platforms and
# billing durations, so shipping a new store product is a dashboard operation
# and never a code change here — unlike the store-product-ID map this replaced,
# which grew one entry per store x platform x duration and dropped purchases
# whenever a product reached a store before the map was updated.
#
# Lookup keys mirror the pricing config tier ids of
# core/services/pricing_config_service.py (`text_only` / `mix` / `audio_heavy`),
# which is also what quota_enforcer.SUBSCRIPTION_TIER_TO_CONFIG maps onto.
# The live layout is documented in docs/REVENUECAT_ENTITLEMENTS.md.
ENTITLEMENT_TIER_MAP: Dict[str, SubscriptionTier] = {
    "tier_text_only": SubscriptionTier.S,
    "tier_mix": SubscriptionTier.M,
    "tier_audio_heavy": SubscriptionTier.L,
}

# Ranking used when an event carries several tier entitlements at once (an
# upgrade whose previous entitlement has not lapsed yet, a grandfathered grant):
# the highest tier wins, which is the safe direction for the user.
_TIER_RANK: Dict[SubscriptionTier, int] = {
    SubscriptionTier.S: 0,
    SubscriptionTier.M: 1,
    SubscriptionTier.L: 2,
}

# Structured log events alarmed by
# infrastructure/terraform/modules/platform/revenucat_alerts.tf.
EVENT_TIER_UNRESOLVED = "revenucat.tier_unresolved"
EVENT_SUBSCRIPTION_UNMATCHED = "revenucat.subscription_unmatched"

REVENUCAT_EVENTS_TABLE = required_env("REVENUCAT_EVENTS_TABLE")


async def _check_idempotency(event_id: str) -> bool:
    """Check if this event has already been processed. Returns True if duplicate."""
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(REVENUCAT_EVENTS_TABLE)
        try:
            response = await table.get_item(Key={"event_id": event_id})
            return "Item" in response
        except Exception as e:
            logger.warning(f"Idempotency check failed for event {event_id}: {e}")
            return False


async def _record_event(event_id: str, event_type: str, user_id: str) -> None:
    """Record a processed event for idempotency."""
    session = database_async.get_session()
    async with session.resource(
        "dynamodb",
        
        region_name=database_async.AWS_REGION,
    ) as dynamodb:
        table = await dynamodb.Table(REVENUCAT_EVENTS_TABLE)
        # TTL: 30 days from now
        ttl = int(time.time()) + (30 * 24 * 60 * 60)
        await table.put_item(
            Item={
                "event_id": event_id,
                "event_type": event_type,
                "user_id": user_id,
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "ttl": ttl,
            }
        )


def _entitlement_ids(event: Dict[str, Any]) -> List[str]:
    """Collect the entitlement identifiers carried by a RevenueCat event.

    `entitlement_ids` (array) is the current payload field; `entitlement_id`
    (string) is documented as deprecated but still always sent, and older
    payload versions carry only that one. Both belong to RevenueCat's input
    contract, which we do not control, so both are read.
    """
    ids: List[str] = []

    raw = event.get("entitlement_ids")
    if isinstance(raw, list):
        ids.extend(str(value) for value in raw if value)
    elif isinstance(raw, str) and raw:
        ids.append(raw)

    single = event.get("entitlement_id")
    if isinstance(single, str) and single:
        ids.append(single)

    deduped: List[str] = []
    for value in ids:
        if value not in deduped:
            deduped.append(value)
    return deduped


def _resolve_tier(event: Dict[str, Any]) -> Optional[SubscriptionTier]:
    """Resolve the subscription tier from the event's entitlement identifiers.

    Returns `None` when the event carries no known tier entitlement, which means
    a store product reached a store without being attached to one of the tier
    entitlements in the RevenueCat dashboard. Callers must report that through
    `_log_tier_unresolved` rather than swallow it.
    """
    tiers = [
        ENTITLEMENT_TIER_MAP[entitlement_id]
        for entitlement_id in _entitlement_ids(event)
        if entitlement_id in ENTITLEMENT_TIER_MAP
    ]
    if not tiers:
        return None
    return max(tiers, key=lambda tier: _TIER_RANK[tier])


def _log_tier_unresolved(event_type: str, event: Dict[str, Any], product_id: str) -> None:
    """Report an event whose tier no entitlement could resolve.

    ERROR and not WARNING on purpose: this is money the user has already been
    charged that the backend is about to ignore, so it has to page instead of
    sitting in a log nobody reads. The product ID and the entitlement IDs are
    both attached because the fix is always "attach that product to its tier
    entitlement in RevenueCat", and those two values name the product and show
    what it resolved to instead.
    """
    log_event(
        logger,
        logging.ERROR,
        EVENT_TIER_UNRESOLVED,
        f"{event_type}: no tier entitlement on the event, subscription tier unresolved",
        revenucat_event_type=event_type,
        revenucat_product_id=product_id or "missing",
        revenucat_entitlement_ids=_entitlement_ids(event) or ["none"],
        app_user_id=event.get("app_user_id", ""),
    )


def _get_platform(store: str) -> Optional[SubscriptionPlatform]:
    """Map RevenueCat store identifier to our platform enum."""
    if store in ("APP_STORE", "MAC_APP_STORE"):
        return SubscriptionPlatform.ios
    elif store in ("PLAY_STORE",):
        return SubscriptionPlatform.android
    return None


def _parse_iso_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse an ISO datetime string from RevenueCat."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _event_datetime(event: Dict[str, Any], field: str) -> Optional[datetime]:
    """Read `field` as a datetime, from either shape RevenueCat may send it in.

    Payload versions carry an ISO string (`expiration_at`) or an epoch in
    milliseconds (`expiration_at_ms`), sometimes both. That is the shape of
    someone else's API, so both are read, ISO first.
    """
    parsed = _parse_iso_date(event.get(field))
    if parsed:
        return parsed
    raw = event.get(f"{field}_ms")
    if raw:
        try:
            return datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc)
        except (ValueError, TypeError):
            return None
    return None


# ---------------------------------------------------------------------------
# Which subscription an event is about
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _EventSubject:
    """The subscription a RevenueCat event describes, as the event names it.

    A user legitimately holds more than one subscription row — one per store, and
    one per product on a store — so every handler has to say *which* row the
    event is about. Reading "the user's first row" is what let an Android
    expiration close an iOS subscription and an Android purchase overwrite an iOS
    row's platform, product and period.

    `product_id` is the product the row carries once the event is applied;
    `previous_product_id` is the one it carried before. The two only differ on
    PRODUCT_CHANGE, the single event whose product is *expected* not to match the
    row yet.
    """

    event_type: str
    app_user_id: str
    store: str
    platform: Optional[SubscriptionPlatform]
    product_id: str
    previous_product_id: str
    store_subscription_id: str


def _event_subject(event_type: str, event: Dict[str, Any]) -> _EventSubject:
    """Read the subject of `event`.

    `original_transaction_id` is the store's own identifier for the subscription
    and is stable across renewals, which makes it the sharpest key we can hold.
    `transaction_id` deliberately is not read: it changes on every renewal, so it
    identifies a payment rather than a subscription.
    """
    store = str(event.get("store") or "")
    product_id = str(event.get("product_id") or "")
    new_product_id = str(event.get("new_product_id") or "")
    return _EventSubject(
        event_type=event_type,
        app_user_id=str(event.get("app_user_id") or ""),
        store=store,
        platform=_get_platform(store),
        product_id=new_product_id or product_id,
        previous_product_id=product_id if new_product_id else "",
        store_subscription_id=str(event.get("original_transaction_id") or ""),
    )


def _freshness(row: Subscription) -> Tuple[float, str]:
    """Ordering that makes "the most recently written row" a total order.

    `timestamp()` rather than the datetime itself so a row whose `updated_at` was
    stored without an offset cannot raise against an aware one, and the row id as
    the final term so the answer never depends on the scan order.
    """
    return (row.updated_at.timestamp(), row.id)


def _carries_product(
    row: Subscription, subject: _EventSubject, product_id: str
) -> bool:
    """Whether `row` is this store's row for `product_id`.

    The platform is compared as the row stores it, so a store `_get_platform`
    maps to nothing matches the rows written from that same store (both sides
    `None`) and never the rows of a store we do know.
    """
    return (
        row.platform == subject.platform
        and (row.revenucat_product_id or "") == product_id
    )


def _match_subscription(
    rows: List[Subscription], subject: _EventSubject
) -> Optional[Subscription]:
    """The row `subject` describes, or None when the user holds no such row.

    Keys are tried from the sharpest to the broadest, and none of them is "the
    first row of the user":

    1. the store's own subscription identifier, when the event and the row both
       carry one — exact, and immune to the product changing under it;
    2. the (platform, product) pair, which is what every row can be keyed on;
    3. the *outgoing* product, for a PRODUCT_CHANGE whose row still carries it.

    Should two rows answer the same key — a duplicate left by an earlier import —
    the most recently written one wins, so what the DynamoDB query happens to
    return first decides nothing.
    """
    keys: List[Callable[[Subscription], bool]] = []
    if subject.store_subscription_id:
        keys.append(
            lambda row: row.revenucat_store_subscription_id
            == subject.store_subscription_id
        )
    if subject.product_id:
        keys.append(lambda row: _carries_product(row, subject, subject.product_id))
    if subject.previous_product_id:
        keys.append(
            lambda row: _carries_product(row, subject, subject.previous_product_id)
        )

    for key in keys:
        candidates = [row for row in rows if key(row)]
        if candidates:
            return max(candidates, key=_freshness)
    return None


def _log_subscription_unmatched(subject: _EventSubject, row_count: int) -> None:
    """Report an event that describes none of the user's subscription rows.

    ERROR and not WARNING, for the same reason as `_log_tier_unresolved`: the
    event is a statement about money — a renewal paid, a cancellation, an expiry
    — and dropping it leaves the row asserting something the store no longer
    says. The previous code logged this at WARNING and it is exactly how a
    CANCELLATION arriving after its EXPIRATION was silently lost.

    The store and the product are attached because they *are* the key that found
    nothing, so the two of them plus the user's row count say whether the row was
    never created or was created under another product.
    """
    log_event(
        logger,
        logging.ERROR,
        EVENT_SUBSCRIPTION_UNMATCHED,
        f"{subject.event_type}: no subscription of this user matches the event's "
        "store and product",
        revenucat_event_type=subject.event_type,
        revenucat_product_id=subject.product_id or "missing",
        revenucat_store=subject.store or "missing",
        app_user_id=subject.app_user_id or "missing",
        subscription_row_count=row_count,
    )


async def _matched_subscription(subject: _EventSubject) -> Optional[Subscription]:
    """Load the user's rows and return the one `subject` describes.

    Reports the miss through `_log_subscription_unmatched`, so the five handlers
    that act on an existing row cannot forget to. INITIAL_PURCHASE matches
    without going through here: for it, no match is the normal create case.
    """
    rows = await minute_db.get_subscriptions_by_user_id(subject.app_user_id)
    matched = _match_subscription(rows, subject)
    if matched is None:
        _log_subscription_unmatched(subject, len(rows))
    return matched


def _record_store_identity(row: Subscription, subject: _EventSubject) -> None:
    """Carry the event's store identity onto the row, without erasing what it knows.

    Google Play issues a new purchase token when a subscription is replaced, so
    the identifier is refreshed from every event that carries one — the row keeps
    naming the subscription the store is currently billing. A store that maps to
    no platform leaves the row's platform alone rather than blanking it.
    """
    if subject.store_subscription_id:
        row.revenucat_store_subscription_id = subject.store_subscription_id
    if subject.platform is not None:
        row.platform = subject.platform


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


async def _handle_initial_purchase(event: Dict[str, Any]) -> None:
    """Handle INITIAL_PURCHASE: create the row of this subscription, or re-arm it.

    Update-vs-create follows the matching key and nothing else. An event for a
    subscription the user already holds re-arms that row — a re-purchase after an
    expiry — and anything else is a new row, which is what a user holding a
    subscription on the other store legitimately gets. The matched row keeps its
    id *and its `created_at`*: rebuilding a `Subscription` here without it is how
    the model's `default_factory` used to reset the real creation date on every
    re-purchase.
    """
    subject = _event_subject("INITIAL_PURCHASE", event)
    tier = _resolve_tier(event)
    if not tier:
        # The row we are about to write requires a tier, so there is nothing
        # sane to persist here. The purchase is dropped, loudly.
        _log_tier_unresolved("INITIAL_PURCHASE", event, subject.product_id)
        return

    period_start = _event_datetime(event, "purchased_at")
    period_end = _event_datetime(event, "expiration_at")
    now = datetime.now(timezone.utc)

    rows = await minute_db.get_subscriptions_by_user_id(subject.app_user_id)
    row = _match_subscription(rows, subject)

    if row is not None:
        row.tier = tier
        row.current_period_start = period_start or now
        row.current_period_end = period_end
        row.status = SubscriptionStatus.active
        row.cancel_at_period_end = False
        row.auto_renew_status = True
        row.revenucat_app_user_id = subject.app_user_id
        row.revenucat_product_id = subject.product_id
        _record_store_identity(row, subject)
        row.updated_at = now
        await minute_db.update_subscription(row)
    else:
        await minute_db.create_subscription(
            Subscription(
                id=str(uuid.uuid4()),
                user_id=subject.app_user_id,
                tier=tier,
                current_period_start=period_start or now,
                current_period_end=period_end,
                status=SubscriptionStatus.active,
                cancel_at_period_end=False,
                revenucat_app_user_id=subject.app_user_id,
                revenucat_product_id=subject.product_id,
                revenucat_store_subscription_id=subject.store_subscription_id or None,
                platform=subject.platform,
                auto_renew_status=True,
                created_at=now,
                updated_at=now,
            )
        )

    logger.info(
        f"INITIAL_PURCHASE processed: user={subject.app_user_id}, "
        f"tier={tier.value}, store={subject.store or 'unknown'}, "
        f"action={'updated' if row is not None else 'created'}"
    )


async def _handle_renewal(event: Dict[str, Any]) -> None:
    """Handle RENEWAL: extend the matched row's period and settle its tier.

    The tier is *written* here, not only logged. A downgrade on the App Store and
    a deferred one on Google Play only take effect at the next renewal, so
    PRODUCT_CHANGE can do no more than record the intent and this event is the
    one carrying the entitlement the user now pays for. While that assignment was
    missing, a user who downgraded kept the outgoing tier's allowance forever.

    An unresolvable tier still extends the period and leaves the tier alone:
    refusing a period the user has just paid for would cost them access over a
    dashboard misconfiguration.
    """
    subject = _event_subject("RENEWAL", event)
    tier = _resolve_tier(event)
    if not tier:
        _log_tier_unresolved("RENEWAL", event, subject.product_id)

    row = await _matched_subscription(subject)
    if row is None:
        return

    now = datetime.now(timezone.utc)
    if tier:
        row.tier = tier
    if subject.product_id:
        row.revenucat_product_id = subject.product_id
    row.current_period_start = _event_datetime(event, "purchased_at") or now
    row.current_period_end = _event_datetime(event, "expiration_at")
    # A renewal is money moving for a new period, so it is the one event allowed
    # to bring a row back from `expired` — a user re-subscribing to the product
    # they had is reported this way.
    row.status = SubscriptionStatus.active
    row.cancel_at_period_end = False
    row.auto_renew_status = True
    _record_store_identity(row, subject)
    row.updated_at = now
    await minute_db.update_subscription(row)

    logger.info(
        f"RENEWAL processed: user={subject.app_user_id}, "
        f"tier={tier.value if tier else 'unresolved'}"
    )


async def _handle_cancellation(event: Dict[str, Any]) -> None:
    """Handle CANCELLATION: record that the subscription will not renew.

    « This will not renew » is true whenever the event arrives. RevenueCat sends
    CANCELLATION and EXPIRATION within milliseconds of each other and promises no
    order, so the flags are written unconditionally and only `status` is guarded:
    an already `expired` row keeps that status instead of being resurrected as
    `canceled`. The row therefore ends in the same state whichever of the two
    lands first, which is what the previous version got wrong — it required the
    row to still be `active`, so an EXPIRATION arriving first turned the
    cancellation into a silent no-op.
    """
    subject = _event_subject("CANCELLATION", event)
    row = await _matched_subscription(subject)
    if row is None:
        return

    row.cancel_at_period_end = True
    row.auto_renew_status = False
    if row.status is not SubscriptionStatus.expired:
        row.status = SubscriptionStatus.canceled
    _record_store_identity(row, subject)
    row.updated_at = datetime.now(timezone.utc)
    await minute_db.update_subscription(row)

    logger.info(
        f"CANCELLATION processed: user={subject.app_user_id}, status={row.status.value}"
    )


async def _handle_expiration(event: Dict[str, Any]) -> None:
    """Handle EXPIRATION: close the matched subscription, stop crediting minutes.

    `cancel_at_period_end` is deliberately not touched: it is CANCELLATION's
    field, and leaving it alone is half of why the two events commute.
    """
    subject = _event_subject("EXPIRATION", event)
    row = await _matched_subscription(subject)
    if row is None:
        return

    row.status = SubscriptionStatus.expired
    row.auto_renew_status = False
    _record_store_identity(row, subject)
    row.updated_at = datetime.now(timezone.utc)
    await minute_db.update_subscription(row)

    logger.info(f"EXPIRATION processed: user={subject.app_user_id}")


async def _handle_billing_issue(event: Dict[str, Any]) -> None:
    """Handle BILLING_ISSUE_DETECTED: flag the matched subscription as grace period.

    Only a row that is still `active` moves: a payment failure reported against a
    row that has already expired or been cancelled must not hand access back.
    """
    subject = _event_subject("BILLING_ISSUE_DETECTED", event)
    row = await _matched_subscription(subject)
    if row is None:
        return

    if row.status is SubscriptionStatus.active:
        row.status = SubscriptionStatus.grace_period
    _record_store_identity(row, subject)
    row.updated_at = datetime.now(timezone.utc)
    await minute_db.update_subscription(row)

    logger.info(
        f"BILLING_ISSUE_DETECTED processed: user={subject.app_user_id}, "
        f"status={row.status.value}"
    )


async def _handle_product_change(event: Dict[str, Any]) -> None:
    """Handle PRODUCT_CHANGE: point the matched row at the new product.

    The one event whose product is expected to differ from the row's, so it is
    matched on the incoming product first (a redelivery, where the row already
    moved) and on the outgoing one second.

    The entitlement IDs describe the subscription as RevenueCat sees it at the
    time of the event. On App Store and deferred Google Play changes the switch
    only takes effect at the next renewal, so a downgrade may still report the
    outgoing tier here; the RENEWAL event that follows carries the new entitlement
    and settles the tier — see `_handle_renewal`, which does assign it.
    """
    subject = _event_subject("PRODUCT_CHANGE", event)
    new_tier = _resolve_tier(event)
    if not new_tier:
        _log_tier_unresolved("PRODUCT_CHANGE", event, subject.product_id)
        return

    row = await _matched_subscription(subject)
    if row is None:
        return

    period_end = _event_datetime(event, "expiration_at")
    row.tier = new_tier
    row.revenucat_product_id = subject.product_id
    if period_end:
        row.current_period_end = period_end
    # A product change is not a payment for a new period, so unlike a renewal it
    # never revives an expired row.
    if row.status is not SubscriptionStatus.expired:
        row.status = SubscriptionStatus.active
        row.cancel_at_period_end = False
        row.auto_renew_status = True
    _record_store_identity(row, subject)
    row.updated_at = datetime.now(timezone.utc)
    await minute_db.update_subscription(row)

    logger.info(
        f"PRODUCT_CHANGE processed: user={subject.app_user_id}, "
        f"new_tier={new_tier.value}"
    )


# Event type dispatcher
EVENT_HANDLERS = {
    "INITIAL_PURCHASE": _handle_initial_purchase,
    "RENEWAL": _handle_renewal,
    "CANCELLATION": _handle_cancellation,
    "EXPIRATION": _handle_expiration,
    "BILLING_ISSUE_DETECTED": _handle_billing_issue,
    "PRODUCT_CHANGE": _handle_product_change,
}


@router.post("/webhooks/revenucat")
async def handle_revenucat_webhook(request: Request):
    """
    Handle incoming RevenueCat webhook events.

    Verifies authenticity via Authorization header (shared secret),
    enforces idempotency via event_id, and dispatches to the appropriate handler.
    """
    # Verify webhook authenticity
    auth_header = request.headers.get("Authorization", "")
    expected_secret = settings.REVENUCAT_WEBHOOK_SECRET

    if not expected_secret:
        logger.error("REVENUCAT_WEBHOOK_SECRET not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured",
        )

    # RevenueCat sends: Authorization: Bearer <secret>
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else auth_header
    if token != expected_secret:
        logger.warning("RevenueCat webhook: invalid authorization")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization",
        )

    # Parse the webhook payload
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    # RevenueCat webhook payload structure:
    # { "api_version": "1.0", "event": { "type": "...", ... } }
    event = body.get("event", {})
    event_type = event.get("type", "")
    event_id = event.get("id", "")

    if not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing event type",
        )

    if not event_id:
        # Generate a synthetic ID if RevenueCat omits it (shouldn't happen)
        event_id = f"synthetic-{uuid.uuid4()}"

    # Idempotency check
    if await _check_idempotency(event_id):
        logger.info(f"Duplicate event {event_id} ({event_type}), skipping")
        return {"status": "ok", "message": "duplicate event ignored"}

    # Dispatch to handler
    handler = EVENT_HANDLERS.get(event_type)
    if handler:
        try:
            await handler(event)
        except Exception as e:
            logger.error(f"Error handling {event_type} event {event_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process event: {event_type}",
            )
    else:
        logger.info(f"Unhandled RevenueCat event type: {event_type}, ignoring")

    # Record event as processed (after successful handling)
    app_user_id = event.get("app_user_id", "unknown")
    await _record_event(event_id, event_type, app_user_id)

    return {"status": "ok"}
