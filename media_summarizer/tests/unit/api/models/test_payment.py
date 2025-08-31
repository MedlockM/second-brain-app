"""
Unit tests for payment models.

This module contains comprehensive unit tests for all payment-related Pydantic models,
covering validation, serialization, and edge cases.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError

from media_summarizer.api.models.payment import (
    PaymentStatus,
    CreditPackage,
    PaymentIntentRequest,
    PaymentIntentResponse,
    PaymentConfirmationRequest,
    PaymentConfirmationResponse,
    RefundRequest,
    RefundResponse,
    PaymentMethodResponse,
    WebhookEventRequest,
    CreditPackageInfo,
    CreditPackagesResponse,
    PaymentHistoryItem,
    PaymentHistoryResponse,
    StripeCustomerResponse
)


class TestPaymentEnums:
    """Tests for payment-related enums."""

    def test_payment_status_enum(self):
        """Test PaymentStatus enum values."""
        assert PaymentStatus.PENDING == "pending"
        assert PaymentStatus.SUCCEEDED == "succeeded"
        assert PaymentStatus.FAILED == "failed"
        assert PaymentStatus.CANCELED == "canceled"
        assert PaymentStatus.REFUNDED == "refunded"

    def test_credit_package_enum(self):
        """Test CreditPackage enum values."""
        assert CreditPackage.SMALL == "small"
        assert CreditPackage.MEDIUM == "medium"
        assert CreditPackage.LARGE == "large"
        assert CreditPackage.ENTERPRISE == "enterprise"


class TestPaymentIntentRequest:
    """Tests for PaymentIntentRequest model."""

    def test_valid_payment_intent_request(self):
        """Test creating a valid payment intent request."""
        request = PaymentIntentRequest(
            credits=50,
            currency="eur",
            metadata={"order_id": "12345"}
        )

        assert request.credits == 50
        assert request.currency == "eur"
        assert request.metadata == {"order_id": "12345"}

    def test_payment_intent_request_defaults(self):
        """Test default values for payment intent request."""
        request = PaymentIntentRequest(credits=150)

        assert request.credits == 150
        assert request.currency == "eur"
        assert request.metadata is None

    def test_invalid_credits_amount(self):
        """Test validation of invalid credit amounts."""
        with pytest.raises(ValidationError) as exc_info:
            PaymentIntentRequest(credits=999)  # Invalid amount

        errors = exc_info.value.errors()
        assert any("Credits must be one of" in error["msg"] for error in errors)

    def test_zero_credits_validation(self):
        """Test validation rejects zero credits."""
        with pytest.raises(ValidationError) as exc_info:
            PaymentIntentRequest(credits=0)

        errors = exc_info.value.errors()
        assert any("greater than 0" in error["msg"] for error in errors)

    def test_negative_credits_validation(self):
        """Test validation rejects negative credits."""
        with pytest.raises(ValidationError) as exc_info:
            PaymentIntentRequest(credits=-10)

        errors = exc_info.value.errors()
        assert any("greater than 0" in error["msg"] for error in errors)

    def test_invalid_currency(self):
        """Test validation of invalid currency."""
        with pytest.raises(ValidationError) as exc_info:
            PaymentIntentRequest(credits=50, currency="xyz")

        errors = exc_info.value.errors()
        assert any("Currency must be one of" in error["msg"] for error in errors)

    def test_currency_case_normalization(self):
        """Test currency is normalized to lowercase."""
        request = PaymentIntentRequest(credits=50, currency="EUR")
        assert request.currency == "eur"

    def test_all_valid_credit_amounts(self):
        """Test all valid credit amounts are accepted."""
        valid_amounts = [50, 150, 500, 1000]

        for amount in valid_amounts:
            request = PaymentIntentRequest(credits=amount)
            assert request.credits == amount


class TestPaymentIntentResponse:
    """Tests for PaymentIntentResponse model."""

    def test_valid_payment_intent_response(self):
        """Test creating a valid payment intent response."""
        response = PaymentIntentResponse(
            payment_intent_id="pi_test123",
            client_secret="pi_test123_secret",
            amount=999,
            currency="eur",
            credits=50,
            package={"id": "small", "name": "Pack Starter"}
        )

        assert response.payment_intent_id == "pi_test123"
        assert response.client_secret == "pi_test123_secret"
        assert response.amount == 999
        assert response.currency == "eur"
        assert response.credits == 50
        assert response.package["id"] == "small"


class TestPaymentConfirmationRequest:
    """Tests for PaymentConfirmationRequest model."""

    def test_valid_payment_confirmation_request(self):
        """Test creating a valid payment confirmation request."""
        request = PaymentConfirmationRequest(
            payment_intent_id="pi_test123"
        )

        assert request.payment_intent_id == "pi_test123"

    def test_invalid_payment_intent_id_format(self):
        """Test validation of invalid payment intent ID format."""
        with pytest.raises(ValidationError) as exc_info:
            PaymentConfirmationRequest(payment_intent_id="invalid_id")

        errors = exc_info.value.errors()
        assert any("Invalid payment intent ID format" in error["msg"] for error in errors)

    def test_valid_payment_intent_id_format(self):
        """Test valid payment intent ID formats are accepted."""
        valid_ids = [
            "pi_1234567890",
            "pi_test_1234567890",
            "pi_abcdefghij"
        ]

        for valid_id in valid_ids:
            request = PaymentConfirmationRequest(payment_intent_id=valid_id)
            assert request.payment_intent_id == valid_id


class TestPaymentConfirmationResponse:
    """Tests for PaymentConfirmationResponse model."""

    def test_payment_confirmation_response_success(self):
        """Test payment confirmation response for successful payment."""
        response = PaymentConfirmationResponse(
            payment_intent_id="pi_test123",
            status=PaymentStatus.SUCCEEDED,
            credits_added=50,
            transaction_id="tx_123",
            message="Payment successful!"
        )

        assert response.payment_intent_id == "pi_test123"
        assert response.status == PaymentStatus.SUCCEEDED
        assert response.credits_added == 50
        assert response.transaction_id == "tx_123"
        assert response.message == "Payment successful!"

    def test_payment_confirmation_response_pending(self):
        """Test payment confirmation response for pending payment."""
        response = PaymentConfirmationResponse(
            payment_intent_id="pi_test123",
            status=PaymentStatus.PENDING,
            message="Payment is being processed"
        )

        assert response.status == PaymentStatus.PENDING
        assert response.credits_added is None
        assert response.transaction_id is None


class TestRefundRequest:
    """Tests for RefundRequest model."""

    def test_valid_refund_request(self):
        """Test creating a valid refund request."""
        request = RefundRequest(
            payment_intent_id="pi_test123",
            amount=500,
            reason="requested_by_customer"
        )

        assert request.payment_intent_id == "pi_test123"
        assert request.amount == 500
        assert request.reason == "requested_by_customer"

    def test_refund_request_defaults(self):
        """Test default values for refund request."""
        request = RefundRequest(payment_intent_id="pi_test123")

        assert request.amount is None
        assert request.reason == "requested_by_customer"

    def test_invalid_payment_intent_id_in_refund(self):
        """Test validation of invalid payment intent ID in refund request."""
        with pytest.raises(ValidationError) as exc_info:
            RefundRequest(payment_intent_id="invalid_id")

        errors = exc_info.value.errors()
        assert any("Invalid payment intent ID format" in error["msg"] for error in errors)

    def test_invalid_refund_reason(self):
        """Test validation of invalid refund reason."""
        with pytest.raises(ValidationError) as exc_info:
            RefundRequest(
                payment_intent_id="pi_test123",
                reason="invalid_reason"
            )

        errors = exc_info.value.errors()
        assert any("Reason must be one of" in error["msg"] for error in errors)

    def test_all_valid_refund_reasons(self):
        """Test all valid refund reasons are accepted."""
        valid_reasons = [
            "duplicate",
            "fraudulent",
            "requested_by_customer",
            "expired_uncaptured_charge",
            "product_unsatisfactory",
            "product_not_received",
            "unrecognized",
            "credit_not_processed"
        ]

        for reason in valid_reasons:
            request = RefundRequest(
                payment_intent_id="pi_test123",
                reason=reason
            )
            assert request.reason == reason


class TestCreditPackageInfo:
    """Tests for CreditPackageInfo model."""

    def test_credit_package_info_creation(self):
        """Test creating credit package info."""
        package = CreditPackageInfo(
            id="small",
            name="Pack Starter",
            credits=50,
            price_cents=999,
            price_euro=9.99,
            savings_percent=15.5
        )

        assert package.id == "small"
        assert package.name == "Pack Starter"
        assert package.credits == 50
        assert package.price_cents == 999
        assert package.price_euro == 9.99
        assert package.savings_percent == 15.5

    def test_credit_package_info_without_savings(self):
        """Test creating credit package info without savings."""
        package = CreditPackageInfo(
            id="small",
            name="Pack Starter",
            credits=50,
            price_cents=999,
            price_euro=9.99
        )

        assert package.savings_percent is None

    def test_from_stripe_package_method(self):
        """Test creating CreditPackageInfo from Stripe package data."""
        package_data = {
            "credits": 50,
            "price_cents": 999,
            "name": "Pack Starter"
        }

        package = CreditPackageInfo.from_stripe_package("small", package_data)

        assert package.id == "small"
        assert package.name == "Pack Starter"
        assert package.credits == 50
        assert package.price_cents == 999
        assert package.price_euro == 9.99

    def test_from_stripe_package_savings_calculation(self):
        """Test savings calculation in from_stripe_package method."""
        # Package with better rate than base (2 cents per credit)
        package_data = {
            "credits": 100,
            "price_cents": 150,  # 1.5 cents per credit
            "name": "Discounted Pack"
        }

        package = CreditPackageInfo.from_stripe_package("discount", package_data)

        assert package.savings_percent == 25.0  # 25% savings

    def test_from_stripe_package_no_savings(self):
        """Test no savings when price is at or above base rate."""
        package_data = {
            "credits": 50,
            "price_cents": 100,  # 2 cents per credit (base rate)
            "name": "Base Pack"
        }

        package = CreditPackageInfo.from_stripe_package("base", package_data)

        assert package.savings_percent is None


class TestPaymentMethodResponse:
    """Tests for PaymentMethodResponse model."""

    def test_payment_method_response_with_card(self):
        """Test payment method response with card details."""
        response = PaymentMethodResponse(
            id="pm_test123",
            type="card",
            card={
                "brand": "visa",
                "last4": "4242",
                "exp_month": 12,
                "exp_year": 2025
            }
        )

        assert response.id == "pm_test123"
        assert response.type == "card"
        assert response.card["brand"] == "visa"
        assert response.card["last4"] == "4242"

    def test_payment_method_response_without_card(self):
        """Test payment method response without card details."""
        response = PaymentMethodResponse(
            id="pm_bank123",
            type="ach_debit"
        )

        assert response.id == "pm_bank123"
        assert response.type == "ach_debit"
        assert response.card is None


class TestPaymentHistoryItem:
    """Tests for PaymentHistoryItem model."""

    def test_payment_history_item_complete(self):
        """Test payment history item with all fields."""
        now = datetime.now()
        item = PaymentHistoryItem(
            payment_intent_id="pi_test123",
            amount=999,
            credits=50,
            status=PaymentStatus.SUCCEEDED,
            created_at=now,
            package_name="Pack Starter"
        )

        assert item.payment_intent_id == "pi_test123"
        assert item.amount == 999
        assert item.credits == 50
        assert item.status == PaymentStatus.SUCCEEDED
        assert item.created_at == now
        assert item.package_name == "Pack Starter"

    def test_payment_history_item_minimal(self):
        """Test payment history item with minimal fields."""
        now = datetime.now()
        item = PaymentHistoryItem(
            payment_intent_id="pi_test123",
            amount=999,
            credits=50,
            status=PaymentStatus.SUCCEEDED,
            created_at=now
        )

        assert item.package_name is None


class TestPaymentHistoryResponse:
    """Tests for PaymentHistoryResponse model."""

    def test_payment_history_response(self):
        """Test payment history response."""
        now = datetime.now()
        payments = [
            PaymentHistoryItem(
                payment_intent_id="pi_test123",
                amount=999,
                credits=50,
                status=PaymentStatus.SUCCEEDED,
                created_at=now
            )
        ]

        response = PaymentHistoryResponse(
            payments=payments,
            total_count=1,
            total_spent_cents=999,
            total_credits_purchased=50
        )

        assert len(response.payments) == 1
        assert response.total_count == 1
        assert response.total_spent_cents == 999
        assert response.total_credits_purchased == 50

    def test_empty_payment_history_response(self):
        """Test empty payment history response."""
        response = PaymentHistoryResponse(
            payments=[],
            total_count=0,
            total_spent_cents=0,
            total_credits_purchased=0
        )

        assert len(response.payments) == 0
        assert response.total_count == 0
        assert response.total_spent_cents == 0
        assert response.total_credits_purchased == 0


class TestCreditPackagesResponse:
    """Tests for CreditPackagesResponse model."""

    def test_credit_packages_response(self):
        """Test credit packages response."""
        packages = [
            CreditPackageInfo(
                id="small",
                name="Pack Starter",
                credits=50,
                price_cents=999,
                price_euro=9.99
            )
        ]

        response = CreditPackagesResponse(packages=packages)

        assert len(response.packages) == 1
        assert response.currency == "eur"
        assert response.packages[0].id == "small"

    def test_credit_packages_response_custom_currency(self):
        """Test credit packages response with custom currency."""
        response = CreditPackagesResponse(
            packages=[],
            currency="usd"
        )

        assert response.currency == "usd"


class TestStripeCustomerResponse:
    """Tests for StripeCustomerResponse model."""

    def test_stripe_customer_response(self):
        """Test Stripe customer response."""
        now = datetime.now()
        payment_methods = [
            PaymentMethodResponse(
                id="pm_test123",
                type="card",
                card={"brand": "visa", "last4": "4242"}
            )
        ]

        response = StripeCustomerResponse(
            customer_id="cus_test123",
            email="test@example.com",
            payment_methods=payment_methods,
            created_at=now
        )

        assert response.customer_id == "cus_test123"
        assert response.email == "test@example.com"
        assert len(response.payment_methods) == 1
        assert response.created_at == now

    def test_stripe_customer_response_no_payment_methods(self):
        """Test Stripe customer response without payment methods."""
        now = datetime.now()

        response = StripeCustomerResponse(
            customer_id="cus_test123",
            email="test@example.com",
            payment_methods=[],
            created_at=now
        )

        assert len(response.payment_methods) == 0


class TestWebhookEventRequest:
    """Tests for WebhookEventRequest model."""

    def test_webhook_event_request(self):
        """Test webhook event request."""
        request = WebhookEventRequest(
            event_type="payment_intent.succeeded",
            event_id="evt_test123",
            data={"object": {"id": "pi_test123"}}
        )

        assert request.event_type == "payment_intent.succeeded"
        assert request.event_id == "evt_test123"
        assert request.data["object"]["id"] == "pi_test123"


class TestRefundResponse:
    """Tests for RefundResponse model."""

    def test_refund_response_complete(self):
        """Test refund response with all fields."""
        response = RefundResponse(
            refund_id="re_test123",
            amount=999,
            status="succeeded",
            payment_intent_id="pi_test123",
            credits_deducted=50
        )

        assert response.refund_id == "re_test123"
        assert response.amount == 999
        assert response.status == "succeeded"
        assert response.payment_intent_id == "pi_test123"
        assert response.credits_deducted == 50

    def test_refund_response_minimal(self):
        """Test refund response without credit deduction."""
        response = RefundResponse(
            refund_id="re_test123",
            amount=999,
            status="succeeded",
            payment_intent_id="pi_test123"
        )

        assert response.credits_deducted is None


class TestModelSerialization:
    """Tests for model serialization and deserialization."""

    def test_payment_intent_request_json_serialization(self):
        """Test PaymentIntentRequest JSON serialization."""
        request = PaymentIntentRequest(
            credits=50,
            currency="eur",
            metadata={"test": "value"}
        )

        json_data = request.model_dump()

        assert json_data["credits"] == 50
        assert json_data["currency"] == "eur"
        assert json_data["metadata"]["test"] == "value"

    def test_payment_confirmation_response_json_serialization(self):
        """Test PaymentConfirmationResponse JSON serialization."""
        response = PaymentConfirmationResponse(
            payment_intent_id="pi_test123",
            status=PaymentStatus.SUCCEEDED,
            credits_added=50,
            transaction_id="tx_123",
            message="Success"
        )

        json_data = response.model_dump()

        assert json_data["payment_intent_id"] == "pi_test123"
        assert json_data["status"] == "succeeded"
        assert json_data["credits_added"] == 50

    def test_credit_package_info_json_serialization(self):
        """Test CreditPackageInfo JSON serialization."""
        package = CreditPackageInfo(
            id="small",
            name="Pack Starter",
            credits=50,
            price_cents=999,
            price_euro=9.99,
            savings_percent=15.5
        )

        json_data = package.model_dump()

        assert json_data["id"] == "small"
        assert json_data["price_euro"] == 9.99
        assert json_data["savings_percent"] == 15.5
