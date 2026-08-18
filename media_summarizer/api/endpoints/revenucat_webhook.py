"""
RevenueCat webhook handler for processing subscription events.

Handles INITIAL_PURCHASE, RENEWAL, CANCELLATION, EXPIRATION,
BILLING_ISSUE_DETECTED, and PRODUCT_CHANGE events from RevenueCat.

Idempotency is enforced via a revenucat_events DynamoDB table.
"""

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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

# Structured log event alarmed by
# infrastructure/terraform/modules/platform/revenucat_alerts.tf.
EVENT_TIER_UNRESOLVED = "revenucat.tier_unresolved"

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


async def _handle_initial_purchase(event: Dict[str, Any]) -> None:
    """Handle INITIAL_PURCHASE: create/update subscription."""
    app_user_id = event.get("app_user_id", "")
    product_id = event.get("product_id", "")
    store = event.get("store", "")
    period_end_str = event.get("expiration_at_ms")
    period_start_str = event.get("purchased_at_ms")

    # RevenueCat sends timestamps as ms or ISO strings depending on version
    period_end = _parse_iso_date(event.get("expiration_at"))
    period_start = _parse_iso_date(event.get("purchased_at"))

    # Fallback to ms timestamps
    if not period_end and period_end_str:
        try:
            period_end = datetime.fromtimestamp(int(period_end_str) / 1000, tz=timezone.utc)
        except (ValueError, TypeError):
            pass
    if not period_start and period_start_str:
        try:
            period_start = datetime.fromtimestamp(int(period_start_str) / 1000, tz=timezone.utc)
        except (ValueError, TypeError):
            pass

    tier = _resolve_tier(event)
    if not tier:
        # The row we are about to write requires a tier, so there is nothing
        # sane to persist here. The purchase is dropped, loudly.
        _log_tier_unresolved("INITIAL_PURCHASE", event, product_id)
        return

    platform = _get_platform(store)

    # Look for existing subscription for this user
    existing_subs = await minute_db.get_subscriptions_by_user_id(app_user_id)
    sub_id = None
    for s in existing_subs:
        if s.revenucat_app_user_id == app_user_id or s.user_id == app_user_id:
            sub_id = s.id
            break

    now = datetime.now(timezone.utc)

    if sub_id:
        # Update existing subscription
        sub = Subscription(
            id=sub_id,
            user_id=app_user_id,
            tier=tier,
            current_period_start=period_start or now,
            current_period_end=period_end,
            status=SubscriptionStatus.active,
            cancel_at_period_end=False,
            revenucat_app_user_id=app_user_id,
            revenucat_product_id=product_id,
            platform=platform,
            auto_renew_status=True,
            updated_at=now,
        )
        await minute_db.update_subscription(sub)
    else:
        # Create new subscription
        sub = Subscription(
            id=str(uuid.uuid4()),
            user_id=app_user_id,
            tier=tier,
            current_period_start=period_start or now,
            current_period_end=period_end,
            status=SubscriptionStatus.active,
            cancel_at_period_end=False,
            revenucat_app_user_id=app_user_id,
            revenucat_product_id=product_id,
            platform=platform,
            auto_renew_status=True,
            created_at=now,
            updated_at=now,
        )
        await minute_db.create_subscription(sub)

    logger.info(f"INITIAL_PURCHASE processed: user={app_user_id}, tier={tier.value}")


async def _handle_renewal(event: Dict[str, Any]) -> None:
    """Handle RENEWAL: update subscription period."""
    app_user_id = event.get("app_user_id", "")
    product_id = event.get("product_id", "")

    period_end = _parse_iso_date(event.get("expiration_at"))
    period_start = _parse_iso_date(event.get("purchased_at"))

    # Fallback to ms timestamps
    if not period_end:
        period_end_ms = event.get("expiration_at_ms")
        if period_end_ms:
            try:
                period_end = datetime.fromtimestamp(int(period_end_ms) / 1000, tz=timezone.utc)
            except (ValueError, TypeError):
                pass
    if not period_start:
        period_start_ms = event.get("purchased_at_ms")
        if period_start_ms:
            try:
                period_start = datetime.fromtimestamp(int(period_start_ms) / 1000, tz=timezone.utc)
            except (ValueError, TypeError):
                pass

    # A renewal only extends the period; it never writes the tier. So an
    # unresolvable tier is reported and the renewal still goes through, because
    # refusing to extend a period the user has just paid for would cost them
    # access over a dashboard misconfiguration.
    tier = _resolve_tier(event)
    if not tier:
        _log_tier_unresolved("RENEWAL", event, product_id)

    now = datetime.now(timezone.utc)

    # Update subscription period
    existing_subs = await minute_db.get_subscriptions_by_user_id(app_user_id)
    for s in existing_subs:
        if s.status.value in ("active", "grace_period"):
            s.current_period_start = period_start or now
            s.current_period_end = period_end
            s.status = SubscriptionStatus.active
            s.auto_renew_status = True
            s.updated_at = now
            await minute_db.update_subscription(s)
            break

    logger.info(
        f"RENEWAL processed: user={app_user_id}, "
        f"tier={tier.value if tier else 'unresolved'}"
    )


async def _handle_cancellation(event: Dict[str, Any]) -> None:
    """Handle CANCELLATION: mark subscription as cancelled (still active until period end)."""
    app_user_id = event.get("app_user_id", "")
    now = datetime.now(timezone.utc)

    existing_subs = await minute_db.get_subscriptions_by_user_id(app_user_id)
    for s in existing_subs:
        if s.status.value in ("active", "grace_period"):
            s.cancel_at_period_end = True
            s.auto_renew_status = False
            s.status = SubscriptionStatus.canceled
            s.updated_at = now
            await minute_db.update_subscription(s)
            logger.info(f"CANCELLATION processed: user={app_user_id}")
            return

    logger.warning(f"CANCELLATION: no active subscription found for user={app_user_id}")


async def _handle_expiration(event: Dict[str, Any]) -> None:
    """Handle EXPIRATION: mark subscription as expired, stop crediting minutes."""
    app_user_id = event.get("app_user_id", "")
    now = datetime.now(timezone.utc)

    existing_subs = await minute_db.get_subscriptions_by_user_id(app_user_id)
    for s in existing_subs:
        if s.status.value in ("active", "canceled", "grace_period"):
            s.status = SubscriptionStatus.expired
            s.auto_renew_status = False
            s.updated_at = now
            await minute_db.update_subscription(s)
            logger.info(f"EXPIRATION processed: user={app_user_id}")
            return

    logger.warning(f"EXPIRATION: no relevant subscription found for user={app_user_id}")


async def _handle_billing_issue(event: Dict[str, Any]) -> None:
    """Handle BILLING_ISSUE_DETECTED: flag subscription as grace period."""
    app_user_id = event.get("app_user_id", "")
    now = datetime.now(timezone.utc)

    existing_subs = await minute_db.get_subscriptions_by_user_id(app_user_id)
    for s in existing_subs:
        if s.status.value == "active":
            s.status = SubscriptionStatus.grace_period
            s.updated_at = now
            await minute_db.update_subscription(s)
            logger.info(f"BILLING_ISSUE_DETECTED processed: user={app_user_id}")
            return

    logger.warning(f"BILLING_ISSUE: no active subscription found for user={app_user_id}")


async def _handle_product_change(event: Dict[str, Any]) -> None:
    """Handle PRODUCT_CHANGE: upgrade/downgrade (update tier)."""
    app_user_id = event.get("app_user_id", "")
    new_product_id = event.get("new_product_id") or event.get("product_id", "")
    store = event.get("store", "")

    period_end = _parse_iso_date(event.get("expiration_at"))
    if not period_end:
        period_end_ms = event.get("expiration_at_ms")
        if period_end_ms:
            try:
                period_end = datetime.fromtimestamp(int(period_end_ms) / 1000, tz=timezone.utc)
            except (ValueError, TypeError):
                pass

    # The entitlement IDs describe the subscription as RevenueCat sees it at the
    # time of the event. On App Store and deferred Google Play changes the switch
    # only takes effect at the next renewal, so a downgrade may still report the
    # outgoing tier here; the RENEWAL event that follows carries the new
    # entitlement and settles the tier. `new_product_id` is still recorded on the
    # row for traceability, it is just no longer what the tier is read from.
    new_tier = _resolve_tier(event)
    if not new_tier:
        _log_tier_unresolved("PRODUCT_CHANGE", event, new_product_id)
        return

    now = datetime.now(timezone.utc)
    platform = _get_platform(store)

    existing_subs = await minute_db.get_subscriptions_by_user_id(app_user_id)
    for s in existing_subs:
        if s.status.value in ("active", "grace_period", "canceled"):
            s.tier = new_tier
            s.revenucat_product_id = new_product_id
            s.current_period_end = period_end
            s.status = SubscriptionStatus.active
            s.cancel_at_period_end = False
            s.auto_renew_status = True
            if platform:
                s.platform = platform
            s.updated_at = now
            await minute_db.update_subscription(s)

            logger.info(
                f"PRODUCT_CHANGE processed: user={app_user_id}, new_tier={new_tier.value}"
            )
            return

    logger.warning(f"PRODUCT_CHANGE: no relevant subscription found for user={app_user_id}")


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
