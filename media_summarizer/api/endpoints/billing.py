"""
Billing endpoints for minutes-based monetization (subscriptions + packs checkout).
"""
import os
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import require_verified_email
from media_summarizer.api.models.payment import CheckoutSessionResponse
from media_summarizer.api.rate_limit import limiter, get_limit_from_env
from media_summarizer.core.services.stripe_service_v2 import StripeServiceV2

router = APIRouter()
logger = logging.getLogger(__name__)

BILLING_SUBS_CHECKOUT_LIMIT = get_limit_from_env("RATE_LIMIT_BILLING_SUBS_CHECKOUT", "10/minute")
BILLING_PACKS_CHECKOUT_LIMIT = get_limit_from_env("RATE_LIMIT_BILLING_PACKS_CHECKOUT", "20/minute")




def _resolve_redirect_urls() -> tuple[str, str]:
    frontend = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    success_url = os.environ.get("STRIPE_SUCCESS_URL") or f"{frontend}/payment-success"
    cancel_url = os.environ.get("STRIPE_CANCEL_URL") or f"{frontend}/payment-cancel"
    return success_url, cancel_url


@router.post("/billing/subscriptions/checkout", response_model=CheckoutSessionResponse)
@limiter.limit(BILLING_SUBS_CHECKOUT_LIMIT)
async def create_subscription_checkout(
    tier: str = Body(..., embed=True, description="Subscription tier: S, M or L"),
    request: Request = None,
    current_user=Depends(require_verified_email),
):
    try:
        service = StripeServiceV2()
        success_url, cancel_url = _resolve_redirect_urls()
        session = await service.create_subscription_checkout_session(
            user_id=current_user.id,
            email=current_user.email,
            tier=tier,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return CheckoutSessionResponse(**session)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create subscription checkout: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create checkout session")


@router.post("/billing/packs/checkout", response_model=CheckoutSessionResponse)
@limiter.limit(BILLING_PACKS_CHECKOUT_LIMIT)
async def create_pack_checkout(
    minutes: int = Body(..., embed=True, description="Pack minutes: 100|300|600|1200"),
    request: Request = None,
    current_user=Depends(require_verified_email),
):
    try:
        service = StripeServiceV2()
        success_url, cancel_url = _resolve_redirect_urls()
        session = await service.create_pack_checkout_session(
            user_id=current_user.id,
            email=current_user.email,
            minutes=minutes,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return CheckoutSessionResponse(**session)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create pack checkout: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create checkout session")


@router.get("/billing/me")
async def get_billing_me(
    request: Request,
    current_user=Depends(require_verified_email),
):
    """Return a summary of the user's minutes pool and subscription state."""
    try:
        from media_summarizer.utils import minute_db
        from media_summarizer.core.models.billing import MinuteBucketSource
        from datetime import datetime, timezone

        # Subscriptions
        subs = await minute_db.get_subscriptions_by_user_id(current_user.id)
        active_sub = None
        if subs:
            # pick the first with status active, else the most recent
            for s in subs:
                if str(s.status) == "active" or s.status.value == "active":
                    active_sub = s
                    break
            if not active_sub:
                active_sub = subs[0]

        # Buckets aggregation
        buckets = await minute_db.get_minute_buckets_by_user_id(current_user.id)
        now = datetime.now(timezone.utc)
        totals = {"rollover": 0, "subscription": 0, "packs": 0}
        total_free = 0
        for b in buckets:
            mr = int(b.minutes_remaining or 0)
            total_free += mr
            if b.source_type == MinuteBucketSource.rollover:
                totals["rollover"] += mr
            elif b.source_type == MinuteBucketSource.subscription:
                totals["subscription"] += mr
            elif b.source_type == MinuteBucketSource.pack:
                totals["packs"] += mr

        resp = {
            "subscription": None,
            "minutes": {
                "total_free": total_free,
                "by_source": totals,
            },
            "buckets_count": len(buckets),
        }
        if active_sub:
            resp["subscription"] = {
                "status": active_sub.status.value,
                "tier": active_sub.tier.value,
                "minutes_per_period": active_sub.minutes_per_period,
                "cancel_at_period_end": active_sub.cancel_at_period_end,
                "current_period_start": active_sub.current_period_start.isoformat() if active_sub.current_period_start else None,
                "current_period_end": active_sub.current_period_end.isoformat() if active_sub.current_period_end else None,
            }
        return resp
    except Exception as e:
        logger.error(f"Failed to compute billing summary for user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve billing summary")


@router.get("/billing/history")
async def get_billing_history(
    request: Request,
    current_user=Depends(require_verified_email),
):
    """Return billing history (subscriptions and minute pack purchases)."""
    try:
        from media_summarizer.utils import minute_db
        from media_summarizer.core.models.billing import MinuteBucketSource
        from datetime import datetime

        # Load data
        subs = await minute_db.get_subscriptions_by_user_id(current_user.id)
        buckets = await minute_db.get_minute_buckets_by_user_id(current_user.id)

        # Format subscriptions (high-level)
        subscriptions = []
        for s in subs:
            subscriptions.append({
                "id": s.id,
                "tier": s.tier.value,
                "status": s.status.value,
                "minutes_per_period": s.minutes_per_period,
                "cancel_at_period_end": s.cancel_at_period_end,
                "current_period_start": s.current_period_start.isoformat() if s.current_period_start else None,
                "current_period_end": s.current_period_end.isoformat() if s.current_period_end else None,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
            })

        # Build event list from minute buckets (subscriptions and packs)
        events = []
        packs_count = 0
        subs_periods_count = 0
        for b in buckets:
            base = {
                "id": b.id,
                "minutes_total": int(b.minutes_total or 0),
                "minutes_remaining": int(b.minutes_remaining or 0),
                "created_at": b.created_at.isoformat(),
                "updated_at": b.updated_at.isoformat(),
                "expires_at": b.expires_at.isoformat() if b.expires_at else None,
                "source_ref": b.source_ref,
            }
            if b.source_type == MinuteBucketSource.pack:
                packs_count += 1
                events.append({
                    **base,
                    "type": "pack_purchase",
                })
            elif b.source_type == MinuteBucketSource.subscription:
                subs_periods_count += 1
                events.append({
                    **base,
                    "type": "subscription_bucket",
                    "period_start": b.period_start.isoformat() if b.period_start else None,
                    "period_end": b.period_end.isoformat() if b.period_end else None,
                })
            else:
                # Include rollover/migration as generic bucket entries
                events.append({
                    **base,
                    "type": b.source_type.value,
                })

        # Sort events by created_at desc
        def _parse_dt(dt_str: str | None) -> float:
            try:
                return datetime.fromisoformat(dt_str).timestamp() if dt_str else 0.0
            except Exception:
                return 0.0
        events.sort(key=lambda e: _parse_dt(e.get("created_at")), reverse=True)

        return {
            "subscriptions": subscriptions,
            "events": events,
            "counts": {
                "total_buckets": len(buckets),
                "pack_purchases": packs_count,
                "subscription_periods": subs_periods_count,
            },
        }
    except Exception as e:
        logger.error(f"Failed to compute billing history for user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve billing history")


@router.post("/billing/subscriptions/cancel")
async def cancel_subscription(
    request: Request,
    current_user=Depends(require_verified_email),
):
    """Cancel the user's active subscription at the end of the current billing period."""
    try:
        from media_summarizer.utils import minute_db
        import stripe
        
        # Get user's active subscription
        subs = await minute_db.get_subscriptions_by_user_id(current_user.id)
        active_sub = None
        for s in subs:
            if str(s.status) == "active" or s.status.value == "active":
                active_sub = s
                break
        
        if not active_sub:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active subscription found")
        
        if not active_sub.stripe_subscription_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid subscription state")
        
        # Cancel subscription at period end via Stripe
        stripe.api_key = os.environ.get("STRIPE_API_KEY")
        updated_subscription = stripe.Subscription.modify(
            active_sub.stripe_subscription_id,
            cancel_at_period_end=True
        )
        
        # Update local record
        active_sub.cancel_at_period_end = True
        await minute_db.update_subscription(active_sub)
        
        return {
            "status": "success",
            "message": "Subscription will be cancelled at the end of the billing period",
            "subscription": {
                "id": active_sub.id,
                "tier": active_sub.tier.value,
                "cancel_at_period_end": True,
                "current_period_end": active_sub.current_period_end.isoformat() if active_sub.current_period_end else None,
            }
        }
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error during subscription cancellation: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to cancel subscription: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to cancel subscription for user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to cancel subscription")


@router.post("/billing/portal")
async def create_customer_portal_session(
    request: Request,
    current_user=Depends(require_verified_email),
):
    """Create a Stripe Customer Portal session for managing payment methods."""
    try:
        from media_summarizer.utils import minute_db
        import stripe
        
        # Get user's subscription to find their Stripe customer ID
        subs = await minute_db.get_subscriptions_by_user_id(current_user.id)
        customer_id = None
        
        # Look for any subscription with a customer ID
        for s in subs:
            if s.stripe_customer_id:
                customer_id = s.stripe_customer_id
                break
        
        if not customer_id:
            # Try to find or create customer by email
            stripe.api_key = os.environ.get("STRIPE_API_KEY")
            customers = stripe.Customer.list(email=current_user.email, limit=1)
            if customers.data:
                customer_id = customers.data[0].id
            else:
                # Create new customer
                customer = stripe.Customer.create(email=current_user.email)
                customer_id = customer.id
        
        # Create portal session
        frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{frontend_url}/dashboard",
        )
        
        return {"url": session.url}
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error during portal session creation: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create portal session: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to create portal session for user {current_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create portal session")


@router.post("/payments/webhook")
async def payments_webhook(request: Request):
    """
    Stripe webhook endpoint (V2 minutes-based).
    """
    try:
        # Read raw body
        body = await request.body()
        signature = request.headers.get("stripe-signature")
        if not signature:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Stripe signature header")

        # Verify and construct event using Stripe SDK directly
        import stripe
        webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
        if not webhook_secret:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook secret not configured")

        event = stripe.Webhook.construct_event(payload=body, sig_header=signature, secret=webhook_secret)

        # Delegate to V2 service
        service = StripeServiceV2()
        ok = await service.handle_webhook_event(event)
        if ok:
            return {"status": "success", "event_id": event.get("id")}
        return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"status": "error"})

    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid signature")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook processing failed")
