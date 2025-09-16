"""
Unit tests for payment endpoints.

This module contains comprehensive unit tests for the payment API endpoints,
covering all payment processing functionality with mocked dependencies.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
from fastapi import status
import json
from datetime import datetime
from stripe.error import StripeError, InvalidRequestError, CardError

from media_summarizer.api.main import app
from media_summarizer.api.models.payment import (
    PaymentStatus,
    CreditPackageInfo,
    PaymentIntentResponse,
    PaymentConfirmationResponse
)
from media_summarizer.core.services.stripe_service import StripeService
from media_summarizer.core.models.credit_transaction import CreditTransaction


class TestPaymentEndpoints:
    """Base test class for payment endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)

        # Mock authenticated user
        self.mock_user = Mock()
        self.mock_user.id = "user_123"
        self.mock_user.email = "test@example.com"
        self.mock_user.credits = 100

    def mock_current_user(self):
        """Mock the get_current_user dependency."""
        from media_summarizer.api.dependencies.auth import get_current_user

        def get_current_user_override():
            return self.mock_user

        app.dependency_overrides[get_current_user] = get_current_user_override

    def teardown_method(self):
        """Clean up after tests."""
        app.dependency_overrides.clear()


class TestGetCreditPackages(TestPaymentEndpoints):
    """Tests for GET /payments/packages endpoint."""

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    def test_get_credit_packages_success(self, mock_stripe_service_class):
        """Test successful retrieval of credit packages."""
        # Mock StripeService instance
        mock_service = Mock()
        mock_service.get_credit_packages.return_value = {
            "small": {"credits": 50, "price_cents": 999, "name": "Pack Starter"},
            "medium": {"credits": 150, "price_cents": 2499, "name": "Pack Standard"}
        }
        mock_stripe_service_class.return_value = mock_service

        response = self.client.get("/api/v1/payments/packages")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "packages" in data
        assert len(data["packages"]) == 2
        assert data["currency"] == "eur"

        # Check package structure
        small_package = next(p for p in data["packages"] if p["id"] == "small")
        assert small_package["credits"] == 50
        assert small_package["price_cents"] == 999
        assert small_package["price_euro"] == 9.99

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    def test_get_credit_packages_service_error(self, mock_stripe_service_class):
        """Test credit packages endpoint with service error."""
        mock_stripe_service_class.side_effect = Exception("Service error")

        response = self.client.get("/api/v1/payments/packages")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to retrieve credit packages" in response.json()["detail"]


class TestCreatePaymentIntent(TestPaymentEndpoints):
    """Tests for POST /payments/intent endpoint."""

    def setup_method(self):
        """Set up test fixtures."""
        super().setup_method()
        self.mock_current_user()

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_create_payment_intent_success(self, mock_stripe_service_class):
        """Test successful payment intent creation."""
        # Mock StripeService instance
        mock_service = AsyncMock()
        mock_service.create_payment_intent.return_value = {
            "payment_intent_id": "pi_test123",
            "client_secret": "pi_test123_secret",
            "amount": 999,
            "currency": "eur",
            "credits": 50,
            "package": {"id": "small", "name": "Pack Starter"}
        }
        mock_stripe_service_class.return_value = mock_service

        response = self.client.post("/api/v1/payments/intent", json={
            "credits": 50,
            "currency": "eur"
        })

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["payment_intent_id"] == "pi_test123"
        assert data["client_secret"] == "pi_test123_secret"
        assert data["credits"] == 50
        assert data["amount"] == 999

        # Verify service was called correctly
        mock_service.create_payment_intent.assert_called_once_with(
            user_id="user_123",
            email="test@example.com",
            credits=50,
            currency="eur",
            metadata=None
        )

    def test_create_payment_intent_invalid_credits(self):
        """Test payment intent creation with invalid credits."""
        response = self.client.post("/api/v1/payments/intent", json={
            "credits": 999,  # Invalid credit amount
            "currency": "eur"
        })

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_create_payment_intent_invalid_currency(self):
        """Test payment intent creation with invalid currency."""
        response = self.client.post("/api/v1/payments/intent", json={
            "credits": 50,
            "currency": "xyz"  # Invalid currency
        })

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_create_payment_intent_value_error(self, mock_stripe_service_class):
        """Test payment intent creation with value error."""
        mock_service = AsyncMock()
        mock_service.create_payment_intent.side_effect = ValueError("Invalid package")
        mock_stripe_service_class.return_value = mock_service

        response = self.client.post("/api/v1/payments/intent", json={
            "credits": 50,
            "currency": "eur"
        })

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid package" in response.json()["detail"]

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_create_payment_intent_stripe_error(self, mock_stripe_service_class):
        """Test payment intent creation with Stripe error."""
        mock_service = AsyncMock()
        mock_service.create_payment_intent.side_effect = StripeError("Stripe API error")
        mock_stripe_service_class.return_value = mock_service

        response = self.client.post("/api/v1/payments/intent", json={
            "credits": 50,
            "currency": "eur"
        })

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED
        assert "Payment processing error" in response.json()["detail"]

    def test_create_payment_intent_unauthenticated(self):
        """Test payment intent creation without authentication."""
        app.dependency_overrides.clear()  # Remove auth override

        response = self.client.post("/api/v1/payments/intent", json={
            "credits": 50,
            "currency": "eur"
        })

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestConfirmPayment(TestPaymentEndpoints):
    """Tests for POST /payments/confirm endpoint."""

    def setup_method(self):
        """Set up test fixtures."""
        super().setup_method()
        self.mock_current_user()

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_confirm_payment_success(self, mock_stripe_service_class):
        """Test successful payment confirmation."""
        # Mock StripeService instance
        mock_service = AsyncMock()
        mock_service.confirm_payment_intent.return_value = {
            "id": "pi_test123",
            "status": "succeeded",
            "amount": 999,
            "currency": "eur",
            "metadata": {"user_id": "user_123", "credits": "50"}
        }

        mock_transaction = Mock()
        mock_transaction.amount = 50
        mock_transaction.id = "tx_123"
        mock_service.process_successful_payment.return_value = mock_transaction

        mock_stripe_service_class.return_value = mock_service

        response = self.client.post("/api/v1/payments/confirm", json={
            "payment_intent_id": "pi_test123"
        })

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["payment_intent_id"] == "pi_test123"
        assert data["status"] == "succeeded"
        assert data["credits_added"] == 50
        assert data["transaction_id"] == "tx_123"
        assert "successful" in data["message"]

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_confirm_payment_pending(self, mock_stripe_service_class):
        """Test payment confirmation with pending status."""
        mock_service = AsyncMock()
        mock_service.confirm_payment_intent.return_value = {
            "id": "pi_test123",
            "status": "requires_action",
            "amount": 999,
            "currency": "eur",
            "metadata": {"user_id": "user_123", "credits": "50"}
        }
        mock_stripe_service_class.return_value = mock_service

        response = self.client.post("/api/v1/payments/confirm", json={
            "payment_intent_id": "pi_test123"
        })

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "requires_action"
        assert data["credits_added"] is None
        assert data["transaction_id"] is None

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_confirm_payment_wrong_user(self, mock_stripe_service_class):
        """Test payment confirmation for different user."""
        mock_service = AsyncMock()
        mock_service.confirm_payment_intent.return_value = {
            "id": "pi_test123",
            "status": "succeeded",
            "metadata": {"user_id": "different_user", "credits": "50"}
        }
        mock_stripe_service_class.return_value = mock_service

        response = self.client.post("/api/v1/payments/confirm", json={
            "payment_intent_id": "pi_test123"
        })

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "does not belong to current user" in response.json()["detail"]

    def test_confirm_payment_invalid_id_format(self):
        """Test payment confirmation with invalid payment intent ID format."""
        response = self.client.post("/api/v1/payments/confirm", json={
            "payment_intent_id": "invalid_id"
        })

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_confirm_payment_stripe_error(self, mock_stripe_service_class):
        """Test payment confirmation with Stripe error."""
        mock_service = AsyncMock()
        mock_service.confirm_payment_intent.side_effect = StripeError("Payment not found")
        mock_stripe_service_class.return_value = mock_service

        response = self.client.post("/api/v1/payments/confirm", json={
            "payment_intent_id": "pi_test123"
        })

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED


class TestStripeWebhook(TestPaymentEndpoints):
    """Tests for POST /payments/webhook endpoint."""

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_webhook_success(self, mock_stripe_service_class):
        """Test successful webhook processing."""
        mock_service = Mock()
        mock_service.construct_webhook_event.return_value = {
            "id": "evt_test123",
            "type": "payment_intent.succeeded"
        }
        mock_service.handle_webhook_event = AsyncMock(return_value=True)
        mock_stripe_service_class.return_value = mock_service

        response = self.client.post(
            "/api/v1/payments/webhook",
            content='{"test": "data"}',
            headers={"stripe-signature": "test_signature"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "success"

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_webhook_invalid_signature(self, mock_stripe_service_class):
        """Test webhook with invalid signature."""
        mock_service = Mock()
        mock_service.construct_webhook_event.side_effect = ValueError("Invalid signature")
        mock_stripe_service_class.return_value = mock_service

        response = self.client.post(
            "/api/v1/payments/webhook",
            content='{"test": "data"}',
            headers={"stripe-signature": "invalid_signature"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_webhook_processing_failure(self, mock_stripe_service_class):
        """Test webhook processing failure."""
        mock_service = Mock()
        mock_service.construct_webhook_event.return_value = {"id": "evt_test123"}
        mock_service.handle_webhook_event = AsyncMock(return_value=False)
        mock_stripe_service_class.return_value = mock_service

        response = self.client.post(
            "/api/v1/payments/webhook",
            content='{"test": "data"}',
            headers={"stripe-signature": "test_signature"}
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


class TestCreateRefund(TestPaymentEndpoints):
    """Tests for POST /payments/refund endpoint."""

    def setup_method(self):
        """Set up test fixtures."""
        super().setup_method()
        self.mock_current_user()

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_create_refund_success(self, mock_stripe_service_class):
        """Test successful refund creation."""
        mock_service = AsyncMock()
        mock_service.confirm_payment_intent.return_value = {
            "id": "pi_test123",
            "metadata": {"user_id": "user_123", "credits": "50"}
        }
        mock_service.create_refund.return_value = {
            "refund_id": "re_test123",
            "amount": 999,
            "status": "succeeded",
            "payment_intent_id": "pi_test123"
        }
        mock_stripe_service_class.return_value = mock_service

        response = self.client.post("/api/v1/payments/refund", json={
            "payment_intent_id": "pi_test123",
            "reason": "requested_by_customer"
        })

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["refund_id"] == "re_test123"
        assert data["amount"] == 999
        assert data["status"] == "succeeded"

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_create_refund_wrong_user(self, mock_stripe_service_class):
        """Test refund creation for payment of different user."""
        mock_service = AsyncMock()
        mock_service.confirm_payment_intent.return_value = {
            "id": "pi_test123",
            "metadata": {"user_id": "different_user", "credits": "50"}
        }
        mock_stripe_service_class.return_value = mock_service

        response = self.client.post("/api/v1/payments/refund", json={
            "payment_intent_id": "pi_test123",
            "reason": "requested_by_customer"
        })

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_refund_invalid_reason(self):
        """Test refund creation with invalid reason."""
        response = self.client.post("/api/v1/payments/refund", json={
            "payment_intent_id": "pi_test123",
            "reason": "invalid_reason"
        })

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestGetCustomerInfo(TestPaymentEndpoints):
    """Tests for GET /payments/customer endpoint."""

    def setup_method(self):
        """Set up test fixtures."""
        super().setup_method()
        self.mock_current_user()

    @patch('stripe.Customer.retrieve')
    @patch('media_summarizer.api.endpoints.payments.StripeService')
    def test_get_customer_info_success(self, mock_stripe_service_class, mock_retrieve):
        """Test successful customer info retrieval."""
        mock_service = Mock()
        mock_service.get_or_create_customer = AsyncMock(return_value="cus_test123")
        mock_service.get_payment_methods.return_value = [
            {
                "id": "pm_test123",
                "type": "card",
                "card": {"brand": "visa", "last4": "4242", "exp_month": 12, "exp_year": 2025}
            }
        ]
        mock_stripe_service_class.return_value = mock_service

        mock_customer = Mock()
        mock_customer.id = "cus_test123"
        mock_customer.email = "test@example.com"
        mock_customer.created = 1640995200  # Unix timestamp
        mock_retrieve.return_value = mock_customer

        response = self.client.get("/api/v1/payments/customer")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["customer_id"] == "cus_test123"
        assert data["email"] == "test@example.com"
        assert len(data["payment_methods"]) == 1

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    def test_get_customer_info_stripe_error(self, mock_stripe_service_class):
        """Test customer info retrieval with Stripe error."""
        mock_service = Mock()
        mock_service.get_or_create_customer = AsyncMock(side_effect=StripeError("Customer error"))
        mock_stripe_service_class.return_value = mock_service

        response = self.client.get("/api/v1/payments/customer")

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED


class TestGetPaymentHistory(TestPaymentEndpoints):
    """Tests for GET /payments/history endpoint."""

    def setup_method(self):
        """Set up test fixtures."""
        super().setup_method()
        self.mock_current_user()

    @patch('stripe.PaymentIntent.list')
    @patch('media_summarizer.api.endpoints.payments.StripeService')
    def test_get_payment_history_success(self, mock_stripe_service_class, mock_list):
        """Test successful payment history retrieval."""
        mock_service = Mock()
        mock_service.get_or_create_customer = AsyncMock(return_value="cus_test123")
        mock_service.get_credit_packages.return_value = {
            "small": {"name": "Pack Starter"}
        }
        mock_stripe_service_class.return_value = mock_service

        mock_payment = Mock()
        mock_payment.id = "pi_test123"
        mock_payment.amount = 999
        mock_payment.status = "succeeded"
        mock_payment.created = 1640995200  # Unix timestamp
        mock_payment.metadata = {
            "type": "credit_purchase",
            "credits": "50",
            "package_id": "small"
        }

        mock_list.return_value = Mock(data=[mock_payment])

        response = self.client.get("/api/v1/payments/history")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data["payments"]) == 1
        assert data["total_count"] == 1
        assert data["total_spent_cents"] == 999
        assert data["total_credits_purchased"] == 50

        payment = data["payments"][0]
        assert payment["payment_intent_id"] == "pi_test123"
        assert payment["credits"] == 50
        assert payment["status"] == "succeeded"

    @patch('stripe.PaymentIntent.list')
    @patch('media_summarizer.api.endpoints.payments.StripeService')
    def test_get_payment_history_with_limit(self, mock_stripe_service_class, mock_list):
        """Test payment history retrieval with limit."""
        mock_service = Mock()
        mock_service.get_or_create_customer = AsyncMock(return_value="cus_test123")
        mock_stripe_service_class.return_value = mock_service

        mock_list.return_value = Mock(data=[])

        response = self.client.get("/api/v1/payments/history?limit=10")

        assert response.status_code == status.HTTP_200_OK
        mock_list.assert_called_once_with(customer="cus_test123", limit=10)

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    def test_get_payment_history_stripe_error(self, mock_stripe_service_class):
        """Test payment history retrieval with Stripe error."""
        mock_service = Mock()
        mock_service.get_or_create_customer = AsyncMock(side_effect=StripeError("History error"))
        mock_stripe_service_class.return_value = mock_service

        response = self.client.get("/api/v1/payments/history")

        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED


class TestCheckoutSession(TestPaymentEndpoints):
    """Tests for POST /billing/create-checkout-session endpoint."""

    def setup_method(self):
        super().setup_method()
        self.mock_current_user()

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_create_checkout_session_success(self, mock_stripe_service_class):
        mock_service = AsyncMock()
        mock_service.create_checkout_session.return_value = {
            "session_id": "cs_test_123",
            "url": "https://checkout.stripe.com/test/cs_test_123"
        }
        mock_stripe_service_class.return_value = mock_service

        response = self.client.post(
            "/api/v1/billing/create-checkout-session",
            json={"credits": 50}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session_id"] == "cs_test_123"
        assert data["url"].startswith("https://")

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_create_checkout_session_value_error(self, mock_stripe_service_class):
        mock_service = AsyncMock()
        mock_service.create_checkout_session.side_effect = ValueError("Missing price ID")
        mock_stripe_service_class.return_value = mock_service

        response = self.client.post(
            "/api/v1/billing/create-checkout-session",
            json={"credits": 50}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Missing price ID" in response.json()["detail"]

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_create_checkout_session_stripe_error(self, mock_stripe_service_class):
        mock_service = AsyncMock()
        mock_service.create_checkout_session.side_effect = StripeError("Stripe down")
        mock_stripe_service_class.return_value = mock_service

        response = self.client.post(
            "/api/v1/billing/create-checkout-session",
            json={"credits": 50}
        )
        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED

    def test_create_checkout_session_unauthenticated(self):
        app.dependency_overrides.clear()
        response = self.client.post(
            "/api/v1/billing/create-checkout-session",
            json={"credits": 50}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCustomerPortal(TestPaymentEndpoints):
    """Tests for POST /billing/customer-portal endpoint."""

    def setup_method(self):
        super().setup_method()
        self.mock_current_user()

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_create_customer_portal_success(self, mock_stripe_service_class):
        mock_service = AsyncMock()
        mock_service.get_or_create_customer.return_value = "cus_test_123"
        mock_service.create_customer_portal_session.return_value = {"url": "https://billing.stripe.com/p/session_123"}
        mock_stripe_service_class.return_value = mock_service

        response = self.client.post("/api/v1/billing/customer-portal")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["url"].startswith("https://")

    @patch('media_summarizer.api.endpoints.payments.StripeService')
    async def test_create_customer_portal_stripe_error(self, mock_stripe_service_class):
        mock_service = AsyncMock()
        mock_service.get_or_create_customer.side_effect = StripeError("Customer error")
        mock_stripe_service_class.return_value = mock_service

        response = self.client.post("/api/v1/billing/customer-portal")
        assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED
