"""
StripeService V2 — Subscriptions (S/M/L) and minute packs checkout via Stripe Checkout.

Implements:
- Subscription checkout (S/M/L)
- Pack checkout (100/300/600/1200 minutes)
- Webhook handling (checkout.session.completed, invoice.payment_succeeded, customer.subscription.*)
- Idempotency via stripe_events DynamoDB table
"""
from __future__ import annotations
import os
import logging
from typing import Dict, Any, Optional

import stripe

from media_summarizer.utils import database_async
from media_summarizer.utils import minute_db
from media_summarizer.core.models.billing import (
    Subscription, SubscriptionStatus, SubscriptionTier,
    MinuteBucket, MinuteBucketSource
)

logger = logging.getLogger(__name__)


class StripeServiceV2:
    def __init__(self) -> None:
        self.api_key = os.environ.get("STRIPE_API_KEY")
        if not self.api_key:
            raise ValueError("STRIPE_API_KEY environment variable is required")
        stripe.api_key = self.api_key

        # Minutes per subscription tier
        self.tier_minutes = {"S": 240, "M": 840, "L": 1980}

        # Price IDs from env
        self.price_sub = {
            "S": os.environ.get("STRIPE_PRICE_ID_SUB_S"),
            "M": os.environ.get("STRIPE_PRICE_ID_SUB_M"),
            "L": os.environ.get("STRIPE_PRICE_ID_SUB_L"),
        }
        self.price_pack = {
            100: os.environ.get("STRIPE_PRICE_ID_PACK_100"),
            300: os.environ.get("STRIPE_PRICE_ID_PACK_300"),
            600: os.environ.get("STRIPE_PRICE_ID_PACK_600"),
            1200: os.environ.get("STRIPE_PRICE_ID_PACK_1200"),
        }

        # Basic validation
        if not all(self.price_sub.values()):
            logger.warning("Some subscription price IDs are missing (STRIPE_PRICE_ID_SUB_*)")
        if not any(self.price_pack.values()):
            logger.warning("No pack price IDs configured (STRIPE_PRICE_ID_PACK_*)")

    # ---------- Helpers ----------
    def _get_minutes_for_tier(self, tier: str) -> int:
        if tier not in self.tier_minutes:
            raise ValueError("Invalid subscription tier. Expected one of S,M,L")
        return self.tier_minutes[tier]

    def _get_price_for_tier(self, tier: str) -> str:
        pid = self.price_sub.get(tier)
        if not pid:
            raise ValueError(f"Missing price ID for tier {tier}")
        return pid

    def _get_price_for_pack(self, minutes: int) -> str:
        pid = self.price_pack.get(minutes)
        if not pid:
            raise ValueError(f"Missing price ID for pack {minutes}")
        return pid

    def _ensure_customer(self, email: str) -> str:
        # Attempt to reuse existing customer by email
        customers = stripe.Customer.list(email=email, limit=1)
        if customers.data:
            return customers.data[0].id
        c = stripe.Customer.create(email=email)
        return c.id

    # ---------- Public API ----------
    async def create_subscription_checkout_session(
        self,
        user_id: str,
        email: str,
        tier: str,
        success_url: str,
        cancel_url: str,
    ) -> Dict[str, Any]:
        minutes = self._get_minutes_for_tier(tier)
        price_id = self._get_price_for_tier(tier)
        customer_id = self._ensure_customer(email)

        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={
                "user_id": user_id,
                "type": "subscription",
                "tier": tier,
                "minutes_per_period": str(minutes),
            },
            allow_promotion_codes=True,
            payment_method_types=["card"],
        )
        return {"session_id": session.id, "url": session.url}

    async def create_pack_checkout_session(
        self,
        user_id: str,
        email: str,
        minutes: int,
        success_url: str,
        cancel_url: str,
    ) -> Dict[str, Any]:
        price_id = self._get_price_for_pack(minutes)
        customer_id = self._ensure_customer(email)

        session = stripe.checkout.Session.create(
            mode="payment",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={
                "user_id": user_id,
                "type": "pack",
                "minutes": str(minutes),
            },
            payment_intent_data={"metadata": {"user_id": user_id, "type": "pack", "minutes": str(minutes)}},
            payment_method_types=["card"],
        )
        return {"session_id": session.id, "url": session.url}

    # ---------- Webhook Handling ----------
    async def handle_webhook_event(self, event: Dict[str, Any]) -> bool:
        event_id = event.get("id")
        if not event_id:
            logger.error("Stripe event missing id")
            return False

        # Idempotency
        already = await database_async.has_stripe_event(event_id)
        if already:
            return True

        etype = event.get("type")
        obj = event.get("data", {}).get("object", {})

        try:
            if etype == "checkout.session.completed":
                mode = obj.get("mode")
                metadata = obj.get("metadata") or {}
                customer_id = obj.get("customer")
                if mode == "subscription":
                    # Record subscription entry; bucket will be created on invoice.payment_succeeded
                    await self._record_subscription_created(metadata=metadata, customer_id=customer_id, session=obj)
                elif mode == "payment":
                    # Create pack bucket immediately
                    await self._create_pack_bucket(metadata=metadata)

            elif etype == "invoice.payment_succeeded":
                # For subscriptions: credit monthly minutes bucket
                await self._process_invoice_payment_succeeded(obj)

            elif etype in ("customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"):
                await self._sync_subscription_status(obj)

            else:
                logger.info(f"Unhandled Stripe event type: {etype}")

            # Record idempotency after success
            await database_async.record_stripe_event(event_id)
            return True

        except Exception as e:
            logger.error(f"Failed to handle Stripe event {event_id}: {e}")
            return False

    # ---------- Internals ----------
    async def _record_subscription_created(self, metadata: Dict[str, Any], customer_id: Optional[str], session: Dict[str, Any]) -> None:
        try:
            user_id = metadata.get("user_id")
            tier = metadata.get("tier")
            minutes_per_period = int(metadata.get("minutes_per_period")) if metadata.get("minutes_per_period") else self._get_minutes_for_tier(tier)
            stripe_subscription_id = session.get("subscription")
            if not (user_id and tier and stripe_subscription_id):
                raise ValueError("Missing required subscription metadata")

            sub = Subscription(
                id=f"sub_{stripe_subscription_id}",
                user_id=user_id,
                stripe_customer_id=customer_id,
                stripe_subscription_id=stripe_subscription_id,
                tier=SubscriptionTier(tier),
                minutes_per_period=minutes_per_period,
                status=SubscriptionStatus.active,
            )
            await minute_db.create_subscription(sub)
        except Exception as e:
            logger.error(f"_record_subscription_created error: {e}")
            raise

    async def _create_pack_bucket(self, metadata: Dict[str, Any]) -> None:
        try:
            from datetime import datetime, timezone, timedelta
            user_id = metadata.get("user_id")
            minutes = int(metadata.get("minutes")) if metadata.get("minutes") else None
            if not (user_id and minutes):
                raise ValueError("Missing metadata for pack purchase")
            bucket = MinuteBucket(
                id=f"pack_{datetime.now(timezone.utc).timestamp()}_{minutes}",
                user_id=user_id,
                source_type=MinuteBucketSource.pack,
                source_ref=f"pack_{minutes}",
                minutes_total=minutes,
                minutes_remaining=minutes,
                expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            )
            await minute_db.create_minute_bucket(bucket)
        except Exception as e:
            logger.error(f"_create_pack_bucket error: {e}")
            raise

    async def _process_invoice_payment_succeeded(self, invoice: Dict[str, Any]) -> None:
        try:
            from datetime import datetime, timezone
            subscription_id = invoice.get("subscription")
            if not subscription_id:
                return
            # Find subscription record by stripe id; create if missing
            sub = await minute_db.get_subscription_by_stripe_id(subscription_id)
            if not sub:
                # As fallback, look into invoice lines to infer tier minutes
                minutes_per_period = self.tier_minutes.get("S", 240)
                customer_id = invoice.get("customer")
                # user_id unknown; cannot proceed
                logger.warning("Subscription record missing; cannot credit minutes without user mapping")
                return

            # Current invoiced period
            period = invoice.get("lines", {}).get("data", [{}])[0].get("period", {})
            start = period.get("start")
            end = period.get("end")
            ps = datetime.fromtimestamp(start, tz=timezone.utc) if start else None
            pe = datetime.fromtimestamp(end, tz=timezone.utc) if end else None

            # Rollover: credit leftover minutes from previous subscription period and set expiry to end of this period
            try:
                all_buckets = await minute_db.get_minute_buckets_by_user_id(sub.user_id)
                prev_sub_buckets = [
                    b for b in all_buckets
                    if b.source_type == MinuteBucketSource.subscription
                    and b.source_ref == subscription_id
                    and b.period_end is not None
                    and ps is not None
                    and b.period_end < ps
                ]
                if prev_sub_buckets:
                    # pick the most recent previous period
                    prev = sorted(prev_sub_buckets, key=lambda b: b.period_end)[-1]
                    leftover = int(prev.minutes_remaining or 0)
                    if leftover > 0 and pe is not None:
                        rollover_bucket = MinuteBucket(
                            id=f"rollover_{subscription_id}_{int(ps.timestamp())}",
                            user_id=sub.user_id,
                            source_type=MinuteBucketSource.rollover,
                            source_ref=subscription_id,
                            minutes_total=leftover,
                            minutes_remaining=leftover,
                            expires_at=pe,
                        )
                        await minute_db.create_minute_bucket(rollover_bucket)
            except Exception as rr:
                logger.warning(f"Failed to process rollover for subscription {subscription_id}: {rr}")

            # Create monthly bucket for the current period
            bucket = MinuteBucket(
                id=f"sub_{subscription_id}_{end or int(datetime.now(timezone.utc).timestamp())}",
                user_id=sub.user_id,
                source_type=MinuteBucketSource.subscription,
                source_ref=subscription_id,
                minutes_total=sub.minutes_per_period,
                minutes_remaining=sub.minutes_per_period,
                period_start=ps,
                period_end=pe,
            )
            await minute_db.create_minute_bucket(bucket)
        except Exception as e:
            logger.error(f"_process_invoice_payment_succeeded error: {e}")
            raise

    async def _sync_subscription_status(self, subscription_obj: Dict[str, Any]) -> None:
        try:
            stripe_subscription_id = subscription_obj.get("id")
            sub = await minute_db.get_subscription_by_stripe_id(stripe_subscription_id)
            if not sub:
                return
            status = subscription_obj.get("status", "active")
            cancel_at_period_end = bool(subscription_obj.get("cancel_at_period_end"))
            from datetime import datetime, timezone
            cps = subscription_obj.get("current_period_start")
            cpe = subscription_obj.get("current_period_end")
            sub.status = SubscriptionStatus(status) if status in SubscriptionStatus.__members__.keys() else SubscriptionStatus.active
            sub.cancel_at_period_end = cancel_at_period_end
            sub.current_period_start = datetime.fromtimestamp(cps, tz=timezone.utc) if cps else None
            sub.current_period_end = datetime.fromtimestamp(cpe, tz=timezone.utc) if cpe else None
            await minute_db.update_subscription(sub)
        except Exception as e:
            logger.error(f"_sync_subscription_status error: {e}")
            raise
