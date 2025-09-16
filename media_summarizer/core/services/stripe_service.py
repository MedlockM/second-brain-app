"""
Stripe service for handling payment processing and credit purchases.

This service provides a comprehensive interface for:
- Creating payment intents for credit purchases
- Managing Stripe customers
- Handling product and price configurations
- Processing webhooks
- Managing payment methods
"""
import os
import logging
from typing import Optional, Dict, Any, List
from decimal import Decimal
import copy
import stripe
from stripe.error import StripeError, SignatureVerificationError

from media_summarizer.core.models.credit_transaction import CreditTransaction
from media_summarizer.utils import database_async

logger = logging.getLogger(__name__)


class StripeService:
    """Service for handling Stripe payment operations."""

    def __init__(self):
        """Initialize the Stripe service with API key."""
        self.api_key = os.environ.get("STRIPE_API_KEY")
        if not self.api_key:
            raise ValueError("STRIPE_API_KEY environment variable is required")

        stripe.api_key = self.api_key

        # Credit packages configuration
        self.credit_packages = {
            "small": {"credits": 50, "price_cents": 999, "name": "Pack Starter"},
            "medium": {"credits": 150, "price_cents": 2499, "name": "Pack Standard"},
            "large": {"credits": 500, "price_cents": 7999, "name": "Pack Premium"},
            "enterprise": {"credits": 1000, "price_cents": 14999, "name": "Pack Entreprise"}
        }

    async def create_customer(self, user_id: str, email: str, name: Optional[str] = None) -> str:
        """
        Create a Stripe customer for a user.

        Args:
            user_id: Internal user ID
            email: User's email address
            name: Optional user name

        Returns:
            Stripe customer ID

        Raises:
            StripeError: If customer creation fails
        """
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name or "",
                metadata={"user_id": user_id}
            )

            logger.info(f"Created Stripe customer {customer.id} for user {user_id}")
            return customer.id

        except StripeError as e:
            logger.error(f"Failed to create Stripe customer for user {user_id}: {e}")
            raise

    async def get_or_create_customer(self, user_id: str, email: str, name: Optional[str] = None) -> str:
        """
        Get existing Stripe customer or create a new one.

        Args:
            user_id: Internal user ID
            email: User's email address
            name: Optional user name

        Returns:
            Stripe customer ID
        """
        try:
            # First, try to find existing customer by email
            customers = stripe.Customer.list(email=email, limit=1)

            if customers.data:
                customer = customers.data[0]
                # Update metadata if needed
                if customer.metadata and customer.metadata.get("user_id") != user_id:
                    stripe.Customer.modify(
                        customer.id,
                        metadata={"user_id": user_id}
                    )
                logger.info(f"Found existing Stripe customer {customer.id} for user {user_id}")
                return customer.id

            # Create new customer if not found
            return await self.create_customer(user_id, email, name)

        except StripeError as e:
            logger.error(f"Failed to get or create Stripe customer for user {user_id}: {e}")
            raise

    def get_credit_packages(self) -> Dict[str, Dict[str, Any]]:
        """Get available credit packages."""
        return copy.deepcopy(self.credit_packages)

    def _get_price_id_for_credits(self, credits: int) -> Optional[str]:
        """
        Return the Stripe Price ID for a given credit amount, if configured via env.

        Expects environment variable STRIPE_PRICE_ID_<CREDITS>, e.g., STRIPE_PRICE_ID_50.
        """
        env_key = f"STRIPE_PRICE_ID_{credits}"
        return os.environ.get(env_key)

    def get_package_by_credits(self, credits: int) -> Optional[Dict[str, Any]]:
        """
        Find a credit package by credit amount.

        Args:
            credits: Number of credits to purchase

        Returns:
            Package configuration or None if not found
        """
        for package_id, package in self.credit_packages.items():
            if package["credits"] == credits:
                return {**package, "id": package_id}
        return None

    async def create_payment_intent(
        self,
        user_id: str,
        email: str,
        credits: int,
        currency: str = "eur",
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe payment intent for credit purchase.

        Args:
            user_id: Internal user ID
            email: User's email address
            credits: Number of credits to purchase
            currency: Payment currency (default: EUR)
            metadata: Additional metadata for the payment

        Returns:
            Dictionary containing payment intent details

        Raises:
            ValueError: If credit package is not found
            StripeError: If payment intent creation fails
        """
        try:
            # Find the appropriate package
            package = self.get_package_by_credits(credits)
            if not package:
                raise ValueError(f"No credit package found for {credits} credits")

            # Get or create Stripe customer
            customer_id = await self.get_or_create_customer(user_id, email)

            # Prepare metadata
            payment_metadata = {
                "user_id": user_id,
                "credits": str(credits),
                "package_id": package["id"],
                "type": "credit_purchase"
            }
            if metadata:
                payment_metadata.update(metadata)

            # Create payment intent
            redirect_policy = os.getenv("STRIPE_REDIRECT_POLICY", "always").lower()
            apm = {"enabled": True}
            if redirect_policy == "never":
                apm["allow_redirects"] = "never"

            payment_intent = stripe.PaymentIntent.create(
                amount=package["price_cents"],
                currency=currency,
                customer=customer_id,
                metadata=payment_metadata,
                description=f"{package['name']} - {credits} crédits",
                automatic_payment_methods=apm
            )

            logger.info(f"Created payment intent {payment_intent.id} for user {user_id} - {credits} credits")

            return {
                "payment_intent_id": payment_intent.id,
                "client_secret": payment_intent.client_secret,
                "amount": package["price_cents"],
                "currency": currency,
                "credits": credits,
                "package": package
            }

        except StripeError as e:
            logger.error(f"Failed to create payment intent for user {user_id}: {e}")
            raise

    async def confirm_payment_intent(self, payment_intent_id: str) -> Dict[str, Any]:
        """
        Confirm a payment intent and return its status.

        Args:
            payment_intent_id: Stripe payment intent ID

        Returns:
            Payment intent status and details

        Raises:
            StripeError: If payment intent retrieval fails
        """
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            return {
                "id": payment_intent.id,
                "status": payment_intent.status,
                "amount": payment_intent.amount,
                "currency": payment_intent.currency,
                "metadata": payment_intent.metadata,
                "client_secret": payment_intent.client_secret
            }

        except StripeError as e:
            logger.error(f"Failed to retrieve payment intent {payment_intent_id}: {e}")
            raise

    async def process_successful_payment(self, payment_intent: Dict[str, Any]) -> Optional[CreditTransaction]:
        """
        Process a successful payment by adding credits to user account.

        Args:
            payment_intent: Payment intent data from Stripe

        Returns:
            Created credit transaction or None if processing fails
        """
        try:
            user_id = payment_intent["metadata"].get("user_id")
            credits = int(payment_intent["metadata"].get("credits", 0))
            package_id = payment_intent["metadata"].get("package_id")

            if not user_id or not credits:
                logger.error(f"Invalid payment metadata: {payment_intent['metadata']}")
                return None

            # Check if user exists
            user = await database_async.get_user_by_id(user_id)
            if not user:
                logger.error(f"User {user_id} not found for payment {payment_intent['id']}")
                return None

            # Create credit transaction
            transaction = CreditTransaction.create_purchase(
                user_id=user_id,
                amount=credits,
                description=f"Achat Stripe - {package_id} ({payment_intent['id']})"
            )

            # Add payment intent ID to transaction metadata
            transaction.description = f"{transaction.description} - PI: {payment_intent['id']}"

            # Save transaction
            await database_async.create_credit_transaction(transaction)

            # Update user credits
            new_credits = user.credits + credits
            await database_async.update_user_credits(user_id, new_credits)

            logger.info(f"Successfully processed payment {payment_intent['id']} - added {credits} credits to user {user_id}")

            return transaction

        except Exception as e:
            logger.error(f"Failed to process successful payment {payment_intent.get('id', 'unknown')}: {e}")
            return None

    async def handle_payment_failed(self, payment_intent: Dict[str, Any]) -> None:
        """
        Handle a failed payment.

        Args:
            payment_intent: Payment intent data from Stripe
        """
        try:
            user_id = payment_intent["metadata"].get("user_id")
            credits = payment_intent["metadata"].get("credits")

            logger.warning(f"Payment failed for user {user_id} - {credits} credits (PI: {payment_intent['id']})")

            # Here you could implement additional logic like:
            # - Sending notification emails
            # - Creating support tickets
            # - Tracking failed payment analytics

        except Exception as e:
            logger.error(f"Failed to handle payment failure: {e}")

    async def create_refund(
        self,
        payment_intent_id: str,
        amount: Optional[int] = None,
        reason: str = "requested_by_customer"
    ) -> Dict[str, Any]:
        """
        Create a refund for a payment.

        Args:
            payment_intent_id: Stripe payment intent ID
            amount: Amount to refund in cents (None for full refund)
            reason: Reason for the refund

        Returns:
            Refund details

        Raises:
            StripeError: If refund creation fails
        """
        try:
            # Get the payment intent to find the charge
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            # Access charges through the API if they exist
            charges = getattr(payment_intent, 'charges', None)
            if not charges or not charges.data:
                raise ValueError(f"No charges found for payment intent {payment_intent_id}")

            charge_id = charges.data[0].id

            refund_params = {
                "charge": charge_id,
                "reason": reason,
                "metadata": {
                    "payment_intent_id": payment_intent_id,
                    "refund_type": "credit_purchase"
                }
            }

            if amount:
                refund_params["amount"] = amount

            refund = stripe.Refund.create(**refund_params)

            logger.info(f"Created refund {refund.id} for payment intent {payment_intent_id}")

            return {
                "refund_id": refund.id,
                "amount": refund.amount,
                "status": refund.status,
                "payment_intent_id": payment_intent_id
            }

        except StripeError as e:
            logger.error(f"Failed to create refund for payment intent {payment_intent_id}: {e}")
            raise

    def construct_webhook_event(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """
        Construct and verify a Stripe webhook event.

        Args:
            payload: Raw webhook payload
            signature: Stripe signature header

        Returns:
            Verified webhook event

        Raises:
            ValueError: If webhook verification fails
        """
        webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
        if not webhook_secret:
            raise ValueError("STRIPE_WEBHOOK_SECRET environment variable is required")

        try:
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            return event

        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            raise
        except SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise ValueError("Invalid signature")

    async def handle_webhook_event(self, event: Dict[str, Any]) -> bool:
        """
        Handle a Stripe webhook event.

        Args:
            event: Stripe webhook event

        Returns:
            True if event was handled successfully, False otherwise
        """
        try:
            event_type = event["type"]
            data = event["data"]["object"]
            event_id = event.get("id")

            logger.info(f"Handling Stripe webhook event: {event_type}")

            # Idempotency: skip if already processed
            if event_id:
                try:
                    if await database_async.has_stripe_event(event_id):
                        logger.info(f"Skipping already-processed Stripe event {event_id}")
                        return True
                except Exception:
                    # If idempotency check fails, proceed but log warning
                    logger.warning(f"Could not check idempotency for event {event_id}")

            handled = False
            if event_type == "payment_intent.succeeded":
                await self.process_successful_payment(data)
                handled = True

            elif event_type == "payment_intent.payment_failed":
                await self.handle_payment_failed(data)
                handled = True

            elif event_type == "checkout.session.completed":
                # Handle Stripe Checkout completion
                await self.process_checkout_session(data)
                handled = True

            elif event_type == "charge.dispute.created":
                # Handle chargeback/dispute
                logger.warning(f"Dispute created for charge: {data.get('id')}")
                handled = True

            else:
                logger.info(f"Unhandled webhook event type: {event_type}")
                handled = True

            # Record event as processed if handled and event_id exists
            if handled and event_id:
                try:
                    await database_async.record_stripe_event(event_id)
                except Exception as e:
                    logger.error(f"Failed to record Stripe event {event_id} as processed: {e}")
            return handled

        except Exception as e:
            logger.error(f"Failed to handle webhook event {event.get('id', 'unknown')}: {e}")
            return False

    async def create_checkout_session(
        self,
        user_id: str,
        email: str,
        credits: int,
        success_url: str,
        cancel_url: str,
        currency: str = "eur",
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe Checkout Session for purchasing a credit package.
        Returns a dict containing session_id and url.
        """
        # price-based checkout requires configured price IDs
        price_id = self._get_price_id_for_credits(credits)
        if not price_id:
            raise ValueError(
                f"Missing Stripe price ID for {credits} credits. Set STRIPE_PRICE_ID_{credits} in environment."
            )

        # Ensure customer exists
        customer_id = await self.get_or_create_customer(user_id, email)

        # Prepare metadata
        session_metadata = {
            "user_id": user_id,
            "credits": str(credits),
            "type": "credit_purchase",
        }
        if metadata:
            session_metadata.update(metadata)

        session = stripe.checkout.Session.create(
            mode="payment",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=session_metadata,
        )

        logger.info(f"Created Checkout Session {session.id} for user {user_id} - {credits} credits")
        return {"session_id": session.id, "url": session.url}

    async def create_customer_portal_session(self, customer_id: str, return_url: str) -> Dict[str, Any]:
        """
        Create a Stripe Billing Portal session for the given customer.
        Returns a dict with url.
        """
        session = stripe.billing_portal.Session.create(customer=customer_id, return_url=return_url)
        logger.info(f"Created Billing Portal session for customer {customer_id}")
        return {"url": session.url}

    async def process_checkout_session(self, session: Dict[str, Any]) -> Optional[CreditTransaction]:
        """
        Process a completed Checkout Session by adding credits to the user.
        """
        try:
            metadata = session.get("metadata") or {}
            user_id = metadata.get("user_id")
            credits_str = metadata.get("credits")
            credits = int(credits_str) if credits_str else 0
            if not user_id or not credits:
                logger.error(f"Invalid checkout session metadata: {metadata}")
                return None

            # Build a payment_intent-like dict to reuse existing processing logic
            payment_intent_stub = {
                "id": session.get("payment_intent") or session.get("id"),
                "metadata": metadata,
            }
            return await self.process_successful_payment(payment_intent_stub)
        except Exception as e:
            logger.error(f"Failed to process checkout session {session.get('id')}: {e}")
            return None

    def get_payment_methods(self, customer_id: str) -> List[Dict[str, Any]]:
        """
        Get payment methods for a customer.

        Args:
            customer_id: Stripe customer ID

        Returns:
            List of payment methods
        """
        try:
            payment_methods = stripe.PaymentMethod.list(
                customer=customer_id,
                type="card"
            )

            return [
                {
                    "id": pm.id,
                    "type": pm.type,
                    "card": {
                        "brand": pm.card.brand,
                        "last4": pm.card.last4,
                        "exp_month": pm.card.exp_month,
                        "exp_year": pm.card.exp_year
                    } if pm.card else None
                }
                for pm in payment_methods.data
            ]

        except StripeError as e:
            logger.error(f"Failed to get payment methods for customer {customer_id}: {e}")
            return []
