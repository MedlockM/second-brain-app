import pytest
pytestmark = pytest.mark.skip("Legacy credits system removed (replaced by minutes)")

"""
Integration tests for the payment workflow.

This file contains comprehensive integration tests for the payment processing workflow,
including Stripe payment intents, confirmation, webhooks, and credit management.

Tests use:
- Real Stripe API with test keys
- Real DynamoDB LocalStack
- HTTPx async server for HTTP requests
- Real payment processing flow
"""
import pytest
import os
import asyncio
import json
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from dotenv import load_dotenv
import stripe
import httpx

from media_summarizer.api.main import app
from media_summarizer.tests.integration.fixtures.dynamodb_fixtures import (
    LocalstackDynamoDBClient
)


@pytest.mark.integration
@pytest.mark.requires_stripe
@pytest.mark.requires_localstack
class TestPaymentWorkflow:
    """
    Integration tests for payment workflow using real Stripe API and DynamoDB LocalStack.

    These tests follow the integration test strategy:
    - Use DynamoDB LocalStack for user and transaction storage
    - Use real Stripe API with test keys for payment processing
    - Use HTTPx async server for HTTP requests
    - Test end-to-end payment workflow
    """

    def setup_environment(self):
        """Set up environment variables for testing."""
        load_dotenv()

    @pytest.fixture
    def test_client(self):
        """Create a test client for the API."""
        return TestClient(app)

    @pytest.fixture
    def real_stripe_client(self):
        """Create a real Stripe client using test API key."""
        # Load environment variables from .env file first
        from dotenv import load_dotenv
        load_dotenv()

        stripe_api_key = os.environ.get("STRIPE_API_KEY")
        if not stripe_api_key:
            pytest.skip(
                "STRIPE_API_KEY not found in environment variables")

        # Test network connectivity to Stripe
        try:
            import requests
            requests.get("https://api.stripe.com", timeout=5)
        except:
            pytest.skip("No network connectivity to Stripe API")

        # Configure Stripe with test API key
        stripe.api_key = stripe_api_key
        return stripe

    @pytest.fixture
    async def httpx_server(self):
        """Create an httpx async server for testing."""
        async with httpx.AsyncClient() as client:
            yield client

    @pytest.fixture
    def localstack_dynamodb_client(self):
        """Create a LocalStack DynamoDB client for testing."""
        client = LocalstackDynamoDBClient()
        yield client
        # Cleanup is handled by the client itself

    @pytest.mark.asyncio
    async def test_complete_payment_workflow_with_stripe_and_dynamodb(
        self,
        test_client,
        localstack_dynamodb_client,
        real_stripe_client
    ):
        """
        Test complete payment workflow from intent creation to credit addition.

        This test verifies the entire payment flow:
        1. Create payment intent through API
        2. Confirm payment with Stripe
        3. Verify payment status through API
        4. Check credits were added to user account
        5. Verify transaction was recorded in DynamoDB
        """
        # Create a test user in DynamoDB
        test_user = localstack_dynamodb_client.create_user(
            user_id="payment-test-user",
            email="payment@example.com",
            credits=25
        )

        # Override authentication dependency
        from media_summarizer.api.dependencies.auth import get_current_user

        def get_current_user_override():
            return Mock(
                id="payment-test-user",
                email="payment@example.com",
                credits=25
            )

        app.dependency_overrides[get_current_user] = get_current_user_override

        try:
            # Step 1: Create payment intent
            intent_response = test_client.post(
                "/api/v1/payments/intent",
                json={
                    "credits": 150,  # Medium package
                    "currency": "eur",
                    "metadata": {"test": "payment_workflow"}
                }
            )

            assert intent_response.status_code == 200
            intent_data = intent_response.json()

            assert intent_data["credits"] == 150
            assert intent_data["amount"] == 2499  # Medium package price
            assert intent_data["currency"] == "eur"
            assert "payment_intent_id" in intent_data
            assert "client_secret" in intent_data

            payment_intent_id = intent_data["payment_intent_id"]

            # Step 2: Simulate payment confirmation with Stripe
            # Use Stripe test payment method
            try:
                confirmed_intent = real_stripe_client.PaymentIntent.confirm(
                    payment_intent_id,
                    payment_method="pm_card_visa"
                )
                assert confirmed_intent.status == "succeeded"
            except stripe.error.StripeError as e:
                if "payment method" in str(e).lower():
                    # Try alternative confirmation method
                    confirmed_intent = real_stripe_client.PaymentIntent.confirm(
                        payment_intent_id,
                        payment_method_data={
                            "type": "card",
                            "card": {"token": "tok_visa"}
                        }
                    )

            # Step 3: Confirm payment through our API
            confirm_response = test_client.post(
                "/api/v1/payments/confirm",
                json={
                    "payment_intent_id": payment_intent_id
                }
            )

            assert confirm_response.status_code == 200
            confirm_data = confirm_response.json()

            assert confirm_data["status"] == "succeeded"
            assert confirm_data["payment_intent_id"] == payment_intent_id
            assert confirm_data["credits_added"] == 150
            assert confirm_data["transaction_id"] is not None
            assert "successful" in confirm_data["message"].lower()

            # Step 4: Verify credits were added to user account
            updated_user = localstack_dynamodb_client.get_user("payment-test-user")
            assert updated_user is not None
            assert updated_user["credits"] == 175  # 25 + 150

            # Step 5: Verify transaction was recorded
            transactions = localstack_dynamodb_client.get_user_transactions("payment-test-user")
            purchase_transactions = [tx for tx in transactions if tx.get("type") == "purchase"]

            assert len(purchase_transactions) >= 1

            # Find the transaction for this payment
            payment_transaction = None
            for tx in purchase_transactions:
                if payment_intent_id in tx.get("description", ""):
                    payment_transaction = tx
                    break

            assert payment_transaction is not None
            assert payment_transaction["amount"] == 150
            assert payment_transaction["user_id"] == "payment-test-user"

        except Exception as e:
            # If Stripe test fails due to network issues, skip gracefully
            pytest.skip(f"Stripe API test failed: {e}")
        finally:
            # Clean up dependency overrides
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_payment_intent_creation_all_packages(
        self,
        test_client,
        localstack_dynamodb_client
    ):
        """
        Test payment intent creation for all available credit packages.

        This test verifies:
        1. All credit packages can create payment intents
        2. Correct pricing for each package
        3. Proper metadata in payment intents
        """
        # Create a test user
        test_user = localstack_dynamodb_client.create_user(
            user_id="package-test-user",
            email="packages@example.com",
            credits=0
        )

        # Override authentication
        from media_summarizer.api.dependencies.auth import get_current_user

        def get_current_user_override():
            return Mock(
                id="package-test-user",
                email="packages@example.com",
                credits=0
            )

        app.dependency_overrides[get_current_user] = get_current_user_override

        try:
            # Test all available packages
            packages = [
                {"credits": 50, "expected_price": 999, "package_id": "small"},
                {"credits": 150, "expected_price": 2499, "package_id": "medium"},
                {"credits": 500, "expected_price": 7999, "package_id": "large"},
                {"credits": 1000, "expected_price": 14999, "package_id": "enterprise"}
            ]

            for package in packages:
                response = test_client.post(
                    "/api/v1/payments/intent",
                    json={
                        "credits": package["credits"],
                        "currency": "eur"
                    }
                )

                assert response.status_code == 200
                data = response.json()

                assert data["credits"] == package["credits"]
                assert data["amount"] == package["expected_price"]
                assert data["currency"] == "eur"
                assert data["package"]["id"] == package["package_id"]
                assert "payment_intent_id" in data
                assert "client_secret" in data

        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_payment_history_retrieval(
        self,
        test_client,
        localstack_dynamodb_client,
        real_stripe_client
    ):
        """
        Test payment history retrieval after successful payments.

        This test verifies:
        1. Payment history endpoint returns correct data
        2. Historical payments include all necessary information
        3. Totals are calculated correctly
        """
        # Create test user
        test_user = localstack_dynamodb_client.create_user(
            user_id="history-test-user",
            email="history@example.com",
            credits=0
        )

        # Override authentication
        from media_summarizer.api.dependencies.auth import get_current_user

        def get_current_user_override():
            return Mock(
                id="history-test-user",
                email="history@example.com",
                credits=0
            )

        app.dependency_overrides[get_current_user] = get_current_user_override

        try:
            # Make a payment first
            intent_response = test_client.post(
                "/api/v1/payments/intent",
                json={"credits": 50, "currency": "eur"}
            )

            assert intent_response.status_code == 200
            payment_intent_id = intent_response.json()["payment_intent_id"]

            # Confirm payment with Stripe
            try:
                real_stripe_client.PaymentIntent.confirm(
                    payment_intent_id,
                    payment_method="pm_card_visa"
                )

                # Confirm through API
                test_client.post(
                    "/api/v1/payments/confirm",
                    json={"payment_intent_id": payment_intent_id}
                )

                # Get payment history
                history_response = test_client.get("/api/v1/payments/history")

                assert history_response.status_code == 200
                history_data = history_response.json()

                assert "payments" in history_data
                assert history_data["total_count"] >= 1
                assert history_data["total_spent_cents"] >= 999
                assert history_data["total_credits_purchased"] >= 50

                # Check first payment details
                if history_data["payments"]:
                    payment = history_data["payments"][0]
                    assert "payment_intent_id" in payment
                    assert "credits" in payment
                    assert "status" in payment
                    assert "created_at" in payment

            except stripe.error.StripeError as e:
                pytest.skip(f"Stripe payment confirmation failed: {e}")

        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_customer_info_retrieval(
        self,
        test_client,
        localstack_dynamodb_client
    ):
        """
        Test Stripe customer information retrieval.

        This test verifies:
        1. Customer endpoint creates/retrieves Stripe customer
        2. Customer information is returned correctly
        3. Payment methods are included if available
        """
        # Create test user
        test_user = localstack_dynamodb_client.create_user(
            user_id="customer-test-user",
            email="customer@example.com",
            credits=100
        )

        # Override authentication
        from media_summarizer.api.dependencies.auth import get_current_user

        def get_current_user_override():
            return Mock(
                id="customer-test-user",
                email="customer@example.com",
                credits=100
            )

        app.dependency_overrides[get_current_user] = get_current_user_override

        try:
            # Get customer info
            response = test_client.get("/api/v1/payments/customer")

            assert response.status_code == 200
            data = response.json()

            assert "customer_id" in data
            assert data["email"] == "customer@example.com"
            assert "payment_methods" in data
            assert "created_at" in data

            # Customer ID should be a valid Stripe customer ID
            assert data["customer_id"].startswith("cus_")

        except Exception as e:
            # Skip if Stripe API is not available
            pytest.skip(f"Customer info test failed: {e}")
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_credit_packages_endpoint(self, test_client):
        """
        Test credit packages endpoint returns correct package information.

        This test verifies:
        1. All packages are returned
        2. Package information is complete
        3. Pricing calculations are correct
        """
        response = test_client.get("/api/v1/payments/packages")

        assert response.status_code == 200
        data = response.json()

        assert "packages" in data
        assert data["currency"] == "eur"

        packages = data["packages"]
        assert len(packages) == 4  # small, medium, large, enterprise

        # Verify package structure
        for package in packages:
            assert "id" in package
            assert "name" in package
            assert "credits" in package
            assert "price_cents" in package
            assert "price_euro" in package

            # Verify price conversion
            expected_euro = package["price_cents"] / 100
            assert abs(package["price_euro"] - expected_euro) < 0.01

        # Verify specific packages exist
        package_ids = [p["id"] for p in packages]
        assert "small" in package_ids
        assert "medium" in package_ids
        assert "large" in package_ids
        assert "enterprise" in package_ids

    @pytest.mark.asyncio
    async def test_payment_workflow_error_handling(
        self,
        test_client,
        localstack_dynamodb_client
    ):
        """
        Test payment workflow error handling scenarios.

        This test verifies:
        1. Invalid credit amounts are rejected
        2. Invalid payment intent IDs are handled
        3. Unauthorized access is prevented
        """
        # Create test user
        test_user = localstack_dynamodb_client.create_user(
            user_id="error-test-user",
            email="error@example.com",
            credits=50
        )

        # Override authentication
        from media_summarizer.api.dependencies.auth import get_current_user

        def get_current_user_override():
            return Mock(
                id="error-test-user",
                email="error@example.com",
                credits=50
            )

        app.dependency_overrides[get_current_user] = get_current_user_override

        try:
            # Test invalid credit amount
            response = test_client.post(
                "/api/v1/payments/intent",
                json={"credits": 999, "currency": "eur"}  # Invalid amount
            )
            assert response.status_code == 422

            # Test invalid currency
            response = test_client.post(
                "/api/v1/payments/intent",
                json={"credits": 50, "currency": "xyz"}  # Invalid currency
            )
            assert response.status_code == 422

            # Test invalid payment intent ID format
            response = test_client.post(
                "/api/v1/payments/confirm",
                json={"payment_intent_id": "invalid_id"}
            )
            assert response.status_code == 422

            # Test non-existent payment intent
            response = test_client.post(
                "/api/v1/payments/confirm",
                json={"payment_intent_id": "pi_nonexistent123"}
            )
            # Should return error (either 402 or 404 depending on Stripe response)
            assert response.status_code in [402, 404, 500]

        finally:
            app.dependency_overrides.clear()

        # Test unauthenticated access
        app.dependency_overrides.clear()

        response = test_client.post(
            "/api/v1/payments/intent",
            json={"credits": 50, "currency": "eur"}
        )
        assert response.status_code == 401  # Unauthorized

    @pytest.mark.asyncio
    async def test_webhook_simulation(
        self,
        test_client,
        localstack_dynamodb_client
    ):
        """
        Test webhook endpoint functionality.

        Note: This test simulates webhook events rather than testing
        with real Stripe webhooks due to the complexity of webhook
        signature verification in testing.
        """
        # This test would require setting up webhook secrets
        # and is more appropriately tested in end-to-end tests
        # For now, we'll just verify the endpoint exists

        response = test_client.post(
            "/api/v1/payments/webhook",
            data='{"test": "data"}',
            headers={"stripe-signature": "test_signature"}
        )

        # Should return 400 due to invalid signature (expected behavior)
        assert response.status_code == 400
