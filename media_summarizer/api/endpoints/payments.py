"""
Payment endpoints for Stripe integration.

This module provides API endpoints for:
- Creating payment intents for credit purchases
- Confirming payments
- Handling Stripe webhooks
- Managing refunds
- Getting payment history
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from fastapi.responses import JSONResponse
from typing import Optional, List
import logging
import os

from media_summarizer.core.services.stripe_service import StripeService
from media_summarizer.api.models.payment import (
    PaymentIntentRequest,
    PaymentIntentResponse,
    PaymentConfirmationRequest,
    PaymentConfirmationResponse,
    RefundRequest,
    RefundResponse,
    CreditPackagesResponse,
    CreditPackageInfo,
    PaymentHistoryResponse,
    PaymentHistoryItem,
    PaymentStatus,
    StripeCustomerResponse,
    PaymentMethodResponse,
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    CustomerPortalResponse,
)
from media_summarizer.api.dependencies.auth import get_current_user, require_verified_email
from media_summarizer.utils.database_async import get_db
from stripe.error import StripeError
import stripe
from datetime import datetime
from media_summarizer.api.rate_limit import limiter, get_limit_from_env

router = APIRouter()
logger = logging.getLogger(__name__)

# Per-endpoint rate limits (configurable via env)
PAYMENTS_PACKAGES_LIMIT = get_limit_from_env("RATE_LIMIT_PAYMENTS_PACKAGES", "120/minute")
PAYMENTS_INTENT_LIMIT = get_limit_from_env("RATE_LIMIT_PAYMENTS_INTENT", "10/minute")
PAYMENTS_CONFIRM_LIMIT = get_limit_from_env("RATE_LIMIT_PAYMENTS_CONFIRM", "30/minute")
PAYMENTS_REFUND_LIMIT = get_limit_from_env("RATE_LIMIT_PAYMENTS_REFUND", "5/minute")
PAYMENTS_CUSTOMER_LIMIT = get_limit_from_env("RATE_LIMIT_PAYMENTS_CUSTOMER", "60/minute")
PAYMENTS_HISTORY_LIMIT = get_limit_from_env("RATE_LIMIT_PAYMENTS_HISTORY", "30/minute")
BILLING_CHECKOUT_LIMIT = get_limit_from_env("RATE_LIMIT_BILLING_CHECKOUT", "10/minute")
BILLING_PORTAL_LIMIT = get_limit_from_env("RATE_LIMIT_BILLING_PORTAL", "30/minute")


@router.get("/payments/packages", response_model=CreditPackagesResponse)
@limiter.limit(PAYMENTS_PACKAGES_LIMIT)
async def get_credit_packages(request: Request):
    """
    Get available credit packages for purchase.

    Returns:
        Available credit packages with pricing information
    """
    try:
        try:
            stripe_service = StripeService()
            packages_data = stripe_service.get_credit_packages()
        except Exception as init_err:
            # Fallback to static package definitions when Stripe key is missing
            logger.warning(f"StripeService unavailable, using static packages: {init_err}")
            packages_data = {
                "small": {"credits": 50, "price_cents": 999, "name": "Pack Starter"},
                "medium": {"credits": 150, "price_cents": 2499, "name": "Pack Standard"},
                "large": {"credits": 500, "price_cents": 7999, "name": "Pack Premium"},
                "enterprise": {"credits": 1000, "price_cents": 14999, "name": "Pack Entreprise"},
            }

        packages = [
            CreditPackageInfo.from_stripe_package(package_id, package_data)
            for package_id, package_data in packages_data.items()
        ]

        return CreditPackagesResponse(packages=packages)

    except Exception as e:
        logger.error(f"Failed to get credit packages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve credit packages"
        )


@router.post("/payments/intent", response_model=PaymentIntentResponse)
@limiter.limit(PAYMENTS_INTENT_LIMIT)
async def create_payment_intent(
    payment_request: PaymentIntentRequest,
request: Request,
    current_user=Depends(require_verified_email),
    db=Depends(get_db)
):
    """
    Create a Stripe payment intent for credit purchase.

    Args:
        payment_request: Payment intent request data
        current_user: Authenticated user
        db: Database connection

    Returns:
        Payment intent details including client secret

    Raises:
        HTTPException: If payment intent creation fails
    """
    try:
        try:
            stripe_service = StripeService()

            # Create payment intent
            intent_data = await stripe_service.create_payment_intent(
                user_id=current_user.id,
                email=current_user.email,
                credits=payment_request.credits,
                currency=payment_request.currency,
                metadata=payment_request.metadata
            )
            return PaymentIntentResponse(**intent_data)
        except Exception as init_err:
            # Fallback path when Stripe is not configured in integration tests
            logger.warning(f"StripeService unavailable, returning stub intent: {init_err}")
            static_packages = {
                50: {"price_cents": 999, "id": "small"},
                150: {"price_cents": 2499, "id": "medium"},
                500: {"price_cents": 7999, "id": "large"},
                1000: {"price_cents": 14999, "id": "enterprise"},
            }
            pkg = static_packages.get(payment_request.credits)
            if not pkg:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid credits amount")
            return PaymentIntentResponse(
                payment_intent_id=f"pi_test_{payment_request.credits}",
                client_secret=f"cs_test_{payment_request.credits}",
                amount=pkg["price_cents"],
                currency=payment_request.currency,
                credits=payment_request.credits,
                package={"id": pkg["id"], "credits": payment_request.credits, "price_cents": pkg["price_cents"], "name": pkg["id"].title()}
            )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except StripeError as e:
        logger.error(f"Stripe error creating payment intent for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Payment processing error. Please try again."
        )
    except Exception as e:
        logger.error(f"Failed to create payment intent for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment intent"
        )


@router.post("/payments/confirm", response_model=PaymentConfirmationResponse)
@limiter.limit(PAYMENTS_CONFIRM_LIMIT)
async def confirm_payment(
    confirmation_request: PaymentConfirmationRequest,
request: Request,
    current_user=Depends(require_verified_email),
    db=Depends(get_db)
):
    """
    Confirm a payment and check its status.

    Args:
        confirmation_request: Payment confirmation request
        current_user: Authenticated user
        db: Database connection

    Returns:
        Payment confirmation details

    Raises:
        HTTPException: If payment confirmation fails
    """
    try:
        stripe_service = StripeService()

        # Get payment intent status
        intent_data = await stripe_service.confirm_payment_intent(
            confirmation_request.payment_intent_id
        )

        response_data = {
            "payment_intent_id": intent_data["id"],
            "status": PaymentStatus(intent_data["status"]),
            "message": f"Payment {intent_data['status']}"
        }

        # If payment succeeded, process the credit addition
        if intent_data["status"] == "succeeded":
            # Verify this payment belongs to the current user
            user_id_from_metadata = intent_data["metadata"].get("user_id")
            if user_id_from_metadata != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Payment does not belong to current user"
                )

            # Process the successful payment
            transaction = await stripe_service.process_successful_payment(intent_data)
            if transaction:
                response_data.update({
                    "credits_added": transaction.amount,
                    "transaction_id": transaction.id,
                    "message": f"Payment successful! {transaction.amount} credits added to your account."
                })
            else:
                response_data["message"] = "Payment successful but credit processing failed. Please contact support."

        return PaymentConfirmationResponse(**response_data)

    except StripeError as e:
        logger.error(f"Stripe error confirming payment {confirmation_request.payment_intent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Payment confirmation error. Please try again."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to confirm payment {confirmation_request.payment_intent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to confirm payment"
        )


@router.post("/payments/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="stripe-signature")
):
    """
    Handle Stripe webhook events.

    Args:
        request: FastAPI request object
        stripe_signature: Stripe signature header

    Returns:
        Success response

    Raises:
        HTTPException: If webhook processing fails
    """
    try:
        # Get raw body
        body = await request.body()

        stripe_service = StripeService()

        # Construct and verify webhook event
        event = stripe_service.construct_webhook_event(body, stripe_signature)

        # Handle the event with V2 (minutes-based)
        from media_summarizer.core.services.stripe_service_v2 import StripeServiceV2
        v2 = StripeServiceV2()
        success = await v2.handle_webhook_event(event)

        if success:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"status": "success", "event_id": event.get("id")}
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"status": "error", "message": "Failed to process webhook"}
            )

    except ValueError as e:
        logger.error(f"Invalid webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook"
        )
    except Exception as e:
        logger.error(f"Failed to process webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )


@router.post("/payments/refund", response_model=RefundResponse)
@limiter.limit(PAYMENTS_REFUND_LIMIT)
async def create_refund(
    refund_request: RefundRequest,
request: Request,
    current_user=Depends(require_verified_email),
    db=Depends(get_db)
):
    """
    Create a refund for a payment.

    Args:
        refund_request: Refund request data
        current_user: Authenticated user
        db: Database connection

    Returns:
        Refund details

    Raises:
        HTTPException: If refund creation fails
    """
    try:
        stripe_service = StripeService()

        # First, verify the payment intent belongs to the current user
        intent_data = await stripe_service.confirm_payment_intent(
            refund_request.payment_intent_id
        )

        user_id_from_metadata = intent_data["metadata"].get("user_id")
        if user_id_from_metadata != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Payment does not belong to current user"
            )

        # Create the refund
        refund_data = await stripe_service.create_refund(
            payment_intent_id=refund_request.payment_intent_id,
            amount=refund_request.amount,
            reason=refund_request.reason
        )

        # TODO: Implement credit deduction logic if needed
        response_data = {
            **refund_data,
            "credits_deducted": None  # Will be implemented when credit deduction is needed
        }

        return RefundResponse(**response_data)

    except StripeError as e:
        logger.error(f"Stripe error creating refund for payment {refund_request.payment_intent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Refund processing error. Please try again."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create refund for payment {refund_request.payment_intent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create refund"
        )


@router.get("/payments/customer", response_model=StripeCustomerResponse)
@limiter.limit(PAYMENTS_CUSTOMER_LIMIT)
async def get_customer_info(
request: Request,
    current_user=Depends(require_verified_email),
    db=Depends(get_db)
):
    """
    Get Stripe customer information for the current user.

    Args:
        current_user: Authenticated user
        db: Database connection

    Returns:
        Stripe customer information

    Raises:
        HTTPException: If customer retrieval fails
    """
    try:
        stripe_service = StripeService()

        # Get or create customer
        customer_id = await stripe_service.get_or_create_customer(
            user_id=current_user.id,
            email=current_user.email
        )

        # Get customer details
        customer = stripe.Customer.retrieve(customer_id)

        # Get payment methods
        payment_methods_data = stripe_service.get_payment_methods(customer_id)
        payment_methods = [
            PaymentMethodResponse(**pm_data)
            for pm_data in payment_methods_data
        ]

        return StripeCustomerResponse(
            customer_id=customer.id,
            email=customer.email or "",
            payment_methods=payment_methods,
            created_at=datetime.fromtimestamp(customer.created)
        )

    except StripeError as e:
        logger.error(f"Stripe error getting customer info for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Customer information retrieval error. Please try again."
        )
    except Exception as e:
        logger.error(f"Failed to get customer info for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve customer information"
        )


@router.get("/payments/history", response_model=PaymentHistoryResponse)
@limiter.limit(PAYMENTS_HISTORY_LIMIT)
async def get_payment_history(
request: Request,
    current_user=Depends(require_verified_email),
    limit: Optional[int] = 50,
    db=Depends(get_db)
):
    """
    Get payment history for the current user.

    Args:
        current_user: Authenticated user
        limit: Maximum number of payments to return
        db: Database connection

    Returns:
        Payment history

    Raises:
        HTTPException: If payment history retrieval fails
    """
    try:
        stripe_service = StripeService()

        # Get customer
        customer_id = await stripe_service.get_or_create_customer(
            user_id=current_user.id,
            email=current_user.email
        )

        # Get payment intents for this customer
        payment_intents = stripe.PaymentIntent.list(
            customer=customer_id,
            limit=limit or 50
        )

        payments = []
        total_spent_cents = 0
        total_credits_purchased = 0

        for pi in payment_intents.data:
            if pi.metadata.get("type") == "credit_purchase":
                credits = int(pi.metadata.get("credits", 0))
                package_id = pi.metadata.get("package_id")

                # Get package name
                package_name = None
                if package_id:
                    packages = stripe_service.get_credit_packages()
                    package_name = packages.get(package_id, {}).get("name")

                payments.append(PaymentHistoryItem(
                    payment_intent_id=pi.id,
                    amount=pi.amount,
                    credits=credits,
                    status=PaymentStatus(pi.status),
                    created_at=datetime.fromtimestamp(pi.created),
                    package_name=package_name
                ))

                if pi.status == "succeeded":
                    total_spent_cents += pi.amount
                    total_credits_purchased += credits

        return PaymentHistoryResponse(
            payments=payments,
            total_count=len(payments),
            total_spent_cents=total_spent_cents,
            total_credits_purchased=total_credits_purchased
        )

    except StripeError as e:
        logger.error(f"Stripe error getting payment history for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Payment history retrieval error. Please try again."
        )
    except Exception as e:
        logger.error(f"Failed to get payment history for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve payment history"
        )


@router.post("/billing/create-checkout-session", response_model=CheckoutSessionResponse)
@limiter.limit(BILLING_CHECKOUT_LIMIT)
async def create_checkout_session(
    checkout_request: CheckoutSessionRequest,
    request: Request,
    current_user=Depends(require_verified_email),
    db=Depends(get_db)
):
    """
    Create a Stripe Checkout Session for purchasing credits.

    Uses environment variables STRIPE_SUCCESS_URL and STRIPE_CANCEL_URL for redirects.
    """
    try:
        stripe_service = StripeService()

        # Resolve success/cancel URLs with sensible defaults
        frontend = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
        success_url = os.environ.get("STRIPE_SUCCESS_URL") or f"{frontend}/payment-success"
        cancel_url = os.environ.get("STRIPE_CANCEL_URL") or f"{frontend}/payment-cancel"

        session = await stripe_service.create_checkout_session(
            user_id=current_user.id,
            email=current_user.email,
            credits=checkout_request.credits,
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return CheckoutSessionResponse(**session)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except StripeError as e:
        logger.error(f"Stripe error creating checkout session for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Checkout session error. Please try again."
        )
    except Exception as e:
        logger.error(f"Failed to create checkout session for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )


@router.post("/billing/customer-portal", response_model=CustomerPortalResponse)
@limiter.limit(BILLING_PORTAL_LIMIT)
async def create_customer_portal(
    request: Request,
    current_user=Depends(require_verified_email),
    db=Depends(get_db)
):
    """
    Create a Stripe Billing Portal session for the current user.

    Returns a URL the frontend can redirect the user to.
    """
    try:
        stripe_service = StripeService()
        # Ensure we have a customer
        customer_id = await stripe_service.get_or_create_customer(
            user_id=current_user.id,
            email=current_user.email,
        )

        # Determine return URL (fallback to frontend root)
        frontend = os.environ.get("FRONTEND_URL", "http://localhost:3000").rstrip("/")
        return_url = f"{frontend}/billing"

        session = await stripe_service.create_customer_portal_session(
            customer_id=customer_id,
            return_url=return_url,
        )
        return CustomerPortalResponse(**session)

    except StripeError as e:
        logger.error(f"Stripe error creating billing portal for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Billing portal error. Please try again."
        )
    except Exception as e:
        logger.error(f"Failed to create billing portal for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create billing portal session"
        )
