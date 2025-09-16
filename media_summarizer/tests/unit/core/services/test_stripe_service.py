"""
Unit tests for the Stripe service.

This module contains comprehensive unit tests for the StripeService class,
covering all payment processing functionality with mocked Stripe API calls.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from decimal import Decimal
import stripe
from stripe.error import StripeError, InvalidRequestError, CardError, SignatureVerificationError

from media_summarizer.core.services.stripe_service import StripeService
from media_summarizer.core.models.credit_transaction import CreditTransaction
from media_summarizer.core.models.user import User


class TestStripeServiceInitialization:
    """Tests for StripeService initialization."""

    @patch.dict("os.environ", {"STRIPE_API_KEY": "sk_test_123"})
    def test_initialization_with_test_key(self):
        """Test successful initialization with test API key."""
        service = StripeService()
        assert service.api_key == "sk_test_123"
        assert stripe.api_key == "sk_test_123"

    @patch.dict("os.environ", {"STRIPE_API_KEY": "sk_live_123"})
    def test_initialization_with_live_key(self):
        """Test successful initialization with live API key."""
        service = StripeService()
        assert service.api_key == "sk_live_123"
        assert stripe.api_key == "sk_live_123"

    @patch.dict("os.environ", {}, clear=True)
    def test_initialization_without_api_key(self):
        """Test initialization failure without API key."""
        with pytest.raises(ValueError, match="STRIPE_API_KEY environment variable is required"):
            StripeService()

    def test_credit_packages_configuration(self):
        """Test that credit packages are properly configured."""
        with patch.dict("os.environ", {"STRIPE_API_KEY": "sk_test_123"}):
            service = StripeService()
            packages = service.get_credit_packages()

            assert "small" in packages
            assert "medium" in packages
            assert "large" in packages
            assert "enterprise" in packages

            # Verify package structure
            small_package = packages["small"]
            assert small_package["credits"] == 50
            assert small_package["price_cents"] == 999
            assert small_package["name"] == "Pack Starter"


class TestStripeCustomerManagement:
    """Tests for Stripe customer management."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch.dict("os.environ", {"STRIPE_API_KEY": "sk_test_123"}):
            self.service = StripeService()

    @pytest.mark.asyncio
    @patch("stripe.Customer.create")
    async def test_create_customer_success(self, mock_create):
        """Test successful customer creation."""
        mock_customer = Mock()
        mock_customer.id = "cus_test123"
        mock_create.return_value = mock_customer

        customer_id = await self.service.create_customer(
            user_id="user_123",
            email="test@example.com",
            name="Test User"
        )

        assert customer_id == "cus_test123"
        mock_create.assert_called_once_with(
            email="test@example.com",
            name="Test User",
            metadata={"user_id": "user_123"}
        )

    @pytest.mark.asyncio
    @patch("stripe.Customer.create")
    async def test_create_customer_stripe_error(self, mock_create):
        """Test customer creation with Stripe error."""
        mock_create.side_effect = StripeError("API Error")

        with pytest.raises(StripeError):
            await self.service.create_customer(
                user_id="user_123",
                email="test@example.com"
            )

    @pytest.mark.asyncio
    @patch("stripe.Customer.list")
    @patch("stripe.Customer.modify")
    async def test_get_existing_customer(self, mock_modify, mock_list):
        """Test getting existing customer by email."""
        mock_customer = Mock()
        mock_customer.id = "cus_existing123"
        mock_customer.metadata = {"user_id": "user_123"}

        mock_list.return_value = Mock(data=[mock_customer])

        customer_id = await self.service.get_or_create_customer(
            user_id="user_123",
            email="test@example.com"
        )

        assert customer_id == "cus_existing123"
        mock_list.assert_called_once_with(email="test@example.com", limit=1)
        mock_modify.assert_not_called()

    @pytest.mark.asyncio
    @patch("stripe.Customer.list")
    @patch("stripe.Customer.create")
    async def test_get_or_create_customer_new(self, mock_create, mock_list):
        """Test creating new customer when none exists."""
        mock_list.return_value = Mock(data=[])
        mock_customer = Mock()
        mock_customer.id = "cus_new123"
        mock_create.return_value = mock_customer

        customer_id = await self.service.get_or_create_customer(
            user_id="user_123",
            email="test@example.com"
        )

        assert customer_id == "cus_new123"
        mock_list.assert_called_once_with(email="test@example.com", limit=1)
        mock_create.assert_called_once()


class TestCreditPackages:
    """Tests for credit package management."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch.dict("os.environ", {"STRIPE_API_KEY": "sk_test_123"}):
            self.service = StripeService()

    def test_get_credit_packages(self):
        """Test getting credit packages."""
        packages = self.service.get_credit_packages()

        assert isinstance(packages, dict)
        assert len(packages) == 4

        for package_id, package in packages.items():
            assert "credits" in package
            assert "price_cents" in package
            assert "name" in package

    def test_get_package_by_credits_found(self):
        """Test finding package by credit amount."""
        package = self.service.get_package_by_credits(50)

        assert package is not None
        assert package["credits"] == 50
        assert package["id"] == "small"

    def test_get_package_by_credits_not_found(self):
        """Test package lookup with invalid credit amount."""
        package = self.service.get_package_by_credits(999)
        assert package is None


class TestPaymentIntents:
    """Tests for payment intent management."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch.dict("os.environ", {"STRIPE_API_KEY": "sk_test_123"}):
            self.service = StripeService()

    @pytest.mark.asyncio
    @patch.object(StripeService, "get_or_create_customer")
    @patch("stripe.PaymentIntent.create")
    async def test_create_payment_intent_success(self, mock_create, mock_customer):
        """Test successful payment intent creation."""
        mock_customer.return_value = "cus_test123"

        mock_intent = Mock()
        mock_intent.id = "pi_test123"
        mock_intent.client_secret = "pi_test123_secret"
        mock_create.return_value = mock_intent

        result = await self.service.create_payment_intent(
            user_id="user_123",
            email="test@example.com",
            credits=50
        )

        assert result["payment_intent_id"] == "pi_test123"
        assert result["client_secret"] == "pi_test123_secret"
        assert result["credits"] == 50
        assert result["amount"] == 999  # small package price

        mock_create.assert_called_once()
        call_args = mock_create.call_args[1]
        assert call_args["amount"] == 999
        assert call_args["currency"] == "eur"
        assert call_args["customer"] == "cus_test123"
        assert call_args["metadata"]["user_id"] == "user_123"
        assert call_args["metadata"]["credits"] == "50"

    @pytest.mark.asyncio
    async def test_create_payment_intent_invalid_credits(self):
        """Test payment intent creation with invalid credit amount."""
        with pytest.raises(ValueError, match="No credit package found for 999 credits"):
            await self.service.create_payment_intent(
                user_id="user_123",
                email="test@example.com",
                credits=999
            )

    @pytest.mark.asyncio
    @patch.object(StripeService, "get_or_create_customer")
    @patch("stripe.PaymentIntent.create")
    async def test_create_payment_intent_stripe_error(self, mock_create, mock_customer):
        """Test payment intent creation with Stripe error."""
        mock_customer.return_value = "cus_test123"
        mock_create.side_effect = StripeError("Payment failed")

        with pytest.raises(StripeError):
            await self.service.create_payment_intent(
                user_id="user_123",
                email="test@example.com",
                credits=50
            )

    @pytest.mark.asyncio
    @patch("stripe.PaymentIntent.retrieve")
    async def test_confirm_payment_intent_success(self, mock_retrieve):
        """Test successful payment intent confirmation."""
        mock_intent = Mock()
        mock_intent.id = "pi_test123"
        mock_intent.status = "succeeded"
        mock_intent.amount = 999
        mock_intent.currency = "eur"
        mock_intent.metadata = {"user_id": "user_123"}
        mock_intent.client_secret = "pi_test123_secret"
        mock_retrieve.return_value = mock_intent

        result = await self.service.confirm_payment_intent("pi_test123")

        assert result["id"] == "pi_test123"
        assert result["status"] == "succeeded"
        assert result["amount"] == 999
        assert result["metadata"]["user_id"] == "user_123"

    @pytest.mark.asyncio
    @patch("stripe.PaymentIntent.retrieve")
    async def test_confirm_payment_intent_not_found(self, mock_retrieve):
        """Test payment intent confirmation with invalid ID."""
        mock_retrieve.side_effect = InvalidRequestError(
            "No such payment_intent", "payment_intent"
        )

        with pytest.raises(InvalidRequestError):
            await self.service.confirm_payment_intent("pi_invalid")


class TestPaymentProcessing:
    """Tests for payment processing logic."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch.dict("os.environ", {"STRIPE_API_KEY": "sk_test_123"}):
            self.service = StripeService()

    @pytest.mark.asyncio
    @patch("media_summarizer.utils.database_async.get_user_by_id")
    @patch("media_summarizer.utils.database_async.create_credit_transaction")
    @patch("media_summarizer.utils.database_async.update_user_credits")
    async def test_process_successful_payment(self, mock_update, mock_create_tx, mock_get_user):
        """Test processing a successful payment."""
        # Mock user
        mock_user = Mock()
        mock_user.id = "user_123"
        mock_user.credits = 100
        mock_get_user.return_value = mock_user

        # Mock payment intent
        payment_intent = {
            "id": "pi_test123",
            "metadata": {
                "user_id": "user_123",
                "credits": "50",
                "package_id": "small"
            }
        }

        result = await self.service.process_successful_payment(payment_intent)

        assert result is not None
        assert isinstance(result, CreditTransaction)
        assert result.user_id == "user_123"
        assert result.amount == 50
        assert result.type == "purchase"

        mock_get_user.assert_called_once_with("user_123")
        mock_create_tx.assert_called_once()
        mock_update.assert_called_once_with("user_123", 150)  # 100 + 50

    @pytest.mark.asyncio
    async def test_process_successful_payment_invalid_metadata(self):
        """Test processing payment with invalid metadata."""
        payment_intent = {
            "id": "pi_test123",
            "metadata": {}
        }

        result = await self.service.process_successful_payment(payment_intent)
        assert result is None

    @pytest.mark.asyncio
    @patch("media_summarizer.utils.database_async.get_user_by_id")
    async def test_process_successful_payment_user_not_found(self, mock_get_user):
        """Test processing payment for non-existent user."""
        mock_get_user.return_value = None

        payment_intent = {
            "id": "pi_test123",
            "metadata": {
                "user_id": "user_nonexistent",
                "credits": "50",
                "package_id": "small"
            }
        }

        result = await self.service.process_successful_payment(payment_intent)
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_payment_failed(self):
        """Test handling payment failure."""
        payment_intent = {
            "id": "pi_failed123",
            "metadata": {
                "user_id": "user_123",
                "credits": "50"
            }
        }

        # Should not raise an exception
        await self.service.handle_payment_failed(payment_intent)


class TestRefunds:
    """Tests for refund processing."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch.dict("os.environ", {"STRIPE_API_KEY": "sk_test_123"}):
            self.service = StripeService()

    @pytest.mark.asyncio
    @patch("stripe.PaymentIntent.retrieve")
    @patch("stripe.Refund.create")
    async def test_create_refund_success(self, mock_create, mock_retrieve):
        """Test successful refund creation."""
        # Mock payment intent with charge
        mock_charge = Mock()
        mock_charge.id = "ch_test123"

        mock_intent = Mock()
        mock_intent.charges = Mock(data=[mock_charge])
        mock_retrieve.return_value = mock_intent

        # Mock refund
        mock_refund = Mock()
        mock_refund.id = "re_test123"
        mock_refund.amount = 999
        mock_refund.status = "succeeded"
        mock_create.return_value = mock_refund

        result = await self.service.create_refund("pi_test123")

        assert result["refund_id"] == "re_test123"
        assert result["amount"] == 999
        assert result["status"] == "succeeded"
        assert result["payment_intent_id"] == "pi_test123"

        mock_create.assert_called_once()
        call_args = mock_create.call_args[1]
        assert call_args["charge"] == "ch_test123"
        assert call_args["reason"] == "requested_by_customer"

    @pytest.mark.asyncio
    @patch("stripe.PaymentIntent.retrieve")
    async def test_create_refund_no_charges(self, mock_retrieve):
        """Test refund creation for payment intent without charges."""
        mock_intent = Mock()
        mock_intent.charges = Mock(data=[])
        mock_retrieve.return_value = mock_intent

        with pytest.raises(ValueError, match="No charges found for payment intent"):
            await self.service.create_refund("pi_test123")

    @pytest.mark.asyncio
    @patch("stripe.PaymentIntent.retrieve")
    @patch("stripe.Refund.create")
    async def test_create_partial_refund(self, mock_create, mock_retrieve):
        """Test partial refund creation."""
        mock_charge = Mock()
        mock_charge.id = "ch_test123"

        mock_intent = Mock()
        mock_intent.charges = Mock(data=[mock_charge])
        mock_retrieve.return_value = mock_intent

        mock_refund = Mock()
        mock_refund.id = "re_test123"
        mock_refund.amount = 500
        mock_refund.status = "succeeded"
        mock_create.return_value = mock_refund

        result = await self.service.create_refund("pi_test123", amount=500)

        assert result["amount"] == 500

        call_args = mock_create.call_args[1]
        assert call_args["amount"] == 500


class TestWebhooks:
    """Tests for webhook handling."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch.dict("os.environ", {"STRIPE_API_KEY": "sk_test_123"}):
            self.service = StripeService()

    @patch.dict("os.environ", {"STRIPE_WEBHOOK_SECRET": "whsec_test123"})
    @patch("stripe.Webhook.construct_event")
    def test_construct_webhook_event_success(self, mock_construct):
        """Test successful webhook event construction."""
        mock_event = {"id": "evt_test123", "type": "payment_intent.succeeded"}
        mock_construct.return_value = mock_event

        payload = b'{"test": "data"}'
        signature = "test_signature"

        result = self.service.construct_webhook_event(payload, signature)

        assert result == mock_event
        mock_construct.assert_called_once_with(
            payload, signature, "whsec_test123"
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_construct_webhook_event_no_secret(self):
        """Test webhook construction without secret."""
        with pytest.raises(ValueError, match="STRIPE_WEBHOOK_SECRET environment variable is required"):
            self.service.construct_webhook_event(b"payload", "signature")

    @patch.dict("os.environ", {"STRIPE_WEBHOOK_SECRET": "whsec_test123"})
    @patch("stripe.Webhook.construct_event")
    def test_construct_webhook_event_invalid_signature(self, mock_construct):
        """Test webhook construction with invalid signature."""
        mock_construct.side_effect = SignatureVerificationError(
            "Invalid signature", "sig_header"
        )

        with pytest.raises(ValueError, match="Invalid signature"):
            self.service.construct_webhook_event(b"payload", "invalid_signature")

    @pytest.mark.asyncio
    @patch.object(StripeService, "process_successful_payment")
    async def test_handle_webhook_payment_succeeded(self, mock_process):
        """Test handling payment_intent.succeeded webhook."""
        mock_process.return_value = Mock()

        event = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test123",
                    "metadata": {"user_id": "user_123"}
                }
            }
        }

        result = await self.service.handle_webhook_event(event)

        assert result is True
        mock_process.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(StripeService, "handle_payment_failed")
    async def test_handle_webhook_payment_failed(self, mock_handle):
        """Test handling payment_intent.payment_failed webhook."""
        event = {
            "type": "payment_intent.payment_failed",
            "data": {
                "object": {
                    "id": "pi_test123",
                    "metadata": {"user_id": "user_123"}
                }
            }
        }

        result = await self.service.handle_webhook_event(event)

        assert result is True
        mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_webhook_unhandled_event(self):
        """Test handling unhandled webhook event type."""
        event = {
            "type": "customer.created",
            "data": {"object": {"id": "cus_test123"}}
        }

        result = await self.service.handle_webhook_event(event)
        assert result is True  # Should return True for unhandled events


class TestPaymentMethods:
    """Tests for payment method management."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch.dict("os.environ", {"STRIPE_API_KEY": "sk_test_123"}):
            self.service = StripeService()

    @patch("stripe.PaymentMethod.list")
    def test_get_payment_methods_success(self, mock_list):
        """Test successful payment method retrieval."""
        mock_pm = Mock()
        mock_pm.id = "pm_test123"
        mock_pm.type = "card"
        mock_pm.card = Mock()
        mock_pm.card.brand = "visa"
        mock_pm.card.last4 = "4242"
        mock_pm.card.exp_month = 12
        mock_pm.card.exp_year = 2025

        mock_list.return_value = Mock(data=[mock_pm])

        result = self.service.get_payment_methods("cus_test123")

        assert len(result) == 1
        assert result[0]["id"] == "pm_test123"
        assert result[0]["type"] == "card"
        assert result[0]["card"]["brand"] == "visa"
        assert result[0]["card"]["last4"] == "4242"

    @patch("stripe.PaymentMethod.list")
    def test_get_payment_methods_stripe_error(self, mock_list):
        """Test payment method retrieval with Stripe error."""
        mock_list.side_effect = StripeError("API Error")

        result = self.service.get_payment_methods("cus_test123")
        assert result == []


class TestStripeServiceEdgeCases:
    """Tests for edge cases and error scenarios in StripeService."""

    def setup_method(self):
        """Set up test fixtures."""
        with patch.dict("os.environ", {"STRIPE_API_KEY": "sk_test_123"}):
            self.service = StripeService()

    @pytest.mark.asyncio
    @patch("stripe.Customer.list")
    @patch("stripe.Customer.modify")
    async def test_get_or_create_customer_update_metadata(self, mock_modify, mock_list):
        """Test updating metadata for existing customer with different user_id."""
        mock_customer = Mock()
        mock_customer.id = "cus_existing123"
        mock_customer.metadata = {"user_id": "old_user_123"}  # Different user ID

        mock_list.return_value = Mock(data=[mock_customer])

        customer_id = await self.service.get_or_create_customer(
            user_id="new_user_123",
            email="test@example.com"
        )

        assert customer_id == "cus_existing123"
        mock_modify.assert_called_once_with(
            "cus_existing123",
            metadata={"user_id": "new_user_123"}
        )

    @pytest.mark.asyncio
    @patch("stripe.Customer.list")
    async def test_get_or_create_customer_list_error(self, mock_list):
        """Test handling error when listing customers."""
        mock_list.side_effect = StripeError("List error")

        with pytest.raises(StripeError):
            await self.service.get_or_create_customer(
                user_id="user_123",
                email="test@example.com"
            )

    def test_get_package_by_credits_multiple_packages(self):
        """Test package lookup with all valid credit amounts."""
        valid_amounts = [50, 150, 500, 1000]

        for amount in valid_amounts:
            package = self.service.get_package_by_credits(amount)
            assert package is not None
            assert package["credits"] == amount
            assert "id" in package

    @pytest.mark.asyncio
    @patch.object(StripeService, "get_or_create_customer")
    @patch("stripe.PaymentIntent.create")
    async def test_create_payment_intent_with_metadata(self, mock_create, mock_customer):
        """Test payment intent creation with custom metadata."""
        mock_customer.return_value = "cus_test123"

        mock_intent = Mock()
        mock_intent.id = "pi_test123"
        mock_intent.client_secret = "pi_test123_secret"
        mock_create.return_value = mock_intent

        custom_metadata = {"order_id": "12345", "source": "web"}

        result = await self.service.create_payment_intent(
            user_id="user_123",
            email="test@example.com",
            credits=50,
            metadata=custom_metadata
        )

        # Verify metadata was merged correctly
        call_args = mock_create.call_args[1]
        assert call_args["metadata"]["order_id"] == "12345"
        assert call_args["metadata"]["source"] == "web"
        assert call_args["metadata"]["user_id"] == "user_123"
        assert call_args["metadata"]["credits"] == "50"

    @pytest.mark.asyncio
    @patch("media_summarizer.utils.database_async.get_user_by_id")
    @patch("media_summarizer.utils.database_async.create_credit_transaction")
    @patch("media_summarizer.utils.database_async.update_user_credits")
    async def test_process_successful_payment_database_error(self, mock_update, mock_create_tx, mock_get_user):
        """Test handling database error during payment processing."""
        # Mock user
        mock_user = Mock()
        mock_user.id = "user_123"
        mock_user.credits = 100
        mock_get_user.return_value = mock_user

        # Mock database error
        mock_create_tx.side_effect = Exception("Database error")

        payment_intent = {
            "id": "pi_test123",
            "metadata": {
                "user_id": "user_123",
                "credits": "50",
                "package_id": "small"
            }
        }

        result = await self.service.process_successful_payment(payment_intent)
        assert result is None  # Should return None on error

    @pytest.mark.asyncio
    async def test_handle_payment_failed_with_exception(self):
        """Test handling payment failure with malformed data."""
        payment_intent = {
            "id": "pi_test123",
            "metadata": None  # Malformed metadata
        }

        # Should not raise an exception
        await self.service.handle_payment_failed(payment_intent)

    @pytest.mark.asyncio
    @patch("stripe.PaymentIntent.retrieve")
    async def test_create_refund_payment_intent_not_found(self, mock_retrieve):
        """Test refund creation when payment intent doesn't exist."""
        mock_retrieve.side_effect = InvalidRequestError(
            "No such payment_intent", "payment_intent"
        )

        with pytest.raises(InvalidRequestError):
            await self.service.create_refund("pi_nonexistent")

    @pytest.mark.asyncio
    @patch("stripe.PaymentIntent.retrieve")
    @patch("stripe.Refund.create")
    async def test_create_refund_create_error(self, mock_create, mock_retrieve):
        """Test handling error during refund creation."""
        mock_charge = Mock()
        mock_charge.id = "ch_test123"

        mock_intent = Mock()
        mock_intent.charges = Mock(data=[mock_charge])
        mock_retrieve.return_value = mock_intent

        mock_create.side_effect = StripeError("Refund failed")

        with pytest.raises(StripeError):
            await self.service.create_refund("pi_test123")

    @pytest.mark.asyncio
    async def test_handle_webhook_event_exception_handling(self):
        """Test webhook handling with malformed event data."""
        malformed_event = {
            "type": "payment_intent.succeeded",
            "data": {}  # Missing object
        }

        result = await self.service.handle_webhook_event(malformed_event)
        assert result is False  # Should return False on error

    @pytest.mark.asyncio
    @patch.object(StripeService, "process_successful_payment")
    async def test_handle_webhook_processing_exception(self, mock_process):
        """Test webhook handling when processing raises exception."""
        mock_process.side_effect = Exception("Processing error")

        event = {
            "type": "payment_intent.succeeded",
            "data": {
                "object": {"id": "pi_test123"}
            }
        }

        result = await self.service.handle_webhook_event(event)
        assert result is False

    @patch("stripe.PaymentMethod.list")
    def test_get_payment_methods_empty_result(self, mock_list):
        """Test payment method retrieval with no methods."""
        mock_list.return_value = Mock(data=[])

        result = self.service.get_payment_methods("cus_test123")
        assert result == []

    @patch("stripe.PaymentMethod.list")
    def test_get_payment_methods_with_non_card_methods(self, mock_list):
        """Test payment method retrieval filtering for card methods only."""
        mock_pm_card = Mock()
        mock_pm_card.id = "pm_card123"
        mock_pm_card.type = "card"
        mock_pm_card.card = Mock()
        mock_pm_card.card.brand = "visa"
        mock_pm_card.card.last4 = "4242"
        mock_pm_card.card.exp_month = 12
        mock_pm_card.card.exp_year = 2025

        mock_pm_bank = Mock()
        mock_pm_bank.id = "pm_bank123"
        mock_pm_bank.type = "ach_debit"
        mock_pm_bank.card = None

        mock_list.return_value = Mock(data=[mock_pm_card, mock_pm_bank])

        result = self.service.get_payment_methods("cus_test123")

        # Should only include card methods
        assert len(result) == 2  # Both are returned, but non-card has card=None
        card_method = next(pm for pm in result if pm["id"] == "pm_card123")
        assert card_method["card"] is not None

        bank_method = next(pm for pm in result if pm["id"] == "pm_bank123")
        assert bank_method["card"] is None

    def test_credit_packages_immutability(self):
        """Test that returned credit packages are a copy and don't affect original."""
        packages1 = self.service.get_credit_packages()
        packages2 = self.service.get_credit_packages()

        # Modify one copy
        packages1["small"]["credits"] = 999

        # Original should be unchanged
        assert packages2["small"]["credits"] == 50
        assert self.service.credit_packages["small"]["credits"] == 50
