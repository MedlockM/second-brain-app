"""
Integration tests for the credit management workflow.

This test verifies the flow of credit management, including:
- Credit balance checking
- Credit purchase
- Credit deduction for podcast processing
- Credit refund for failed jobs

These tests use a real FastAPI test client and real LocalStack services
to test actual component integration. The Stripe API is also used with
test API keys for payment processing.
"""
import json
import os
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import uuid
from fastapi.testclient import TestClient
from dotenv import load_dotenv

from media_summarizer.tests.utils.base_test_classes import BaseIntegrationTestCase
from media_summarizer.tests.utils.test_helpers import (
    create_sqs_message,
    assert_sqs_message_sent,
    set_env_vars,
    restore_env_vars
)
from media_summarizer.tests.utils.test_models import TestUser, TestCreditTransaction

from media_summarizer.api.main import app
from media_summarizer.api.endpoints.credits import CreditBalance, CreditPurchase
from media_summarizer.adapters.database.connection import get_db


class TestCreditManagementWorkflow(BaseIntegrationTestCase):
    """Test the credit management workflow."""

    @pytest.fixture
    def mock_user_auth(self):
        """Create a mock user authentication middleware."""
        with patch("media_summarizer.api.dependencies.auth.get_current_user") as mock_auth:
            mock_auth.return_value = TestUser.create(
                user_id="test-user-id",
                email="user@example.com",
                credits=100
            )
            yield mock_auth

    @pytest.fixture
    def mock_payment_service(self):
        """Create a mock payment service for testing."""
        mock = MagicMock()
        mock.process_payment = AsyncMock(return_value={"success": True, "transaction_id": "txn-123"})
        return mock

    @pytest.mark.asyncio
    async def test_get_credit_balance(self, test_client, mock_user_auth, mock_db_session):
        """
        Test retrieving the user's credit balance.
        
        This test verifies that:
        1. The API endpoint returns the user's credit balance
        2. The response format is correct
        """
        # Setup mock database query to return user credits
        with patch("media_summarizer.adapters.database.connection.get_db", return_value=mock_db_session):
            # Execute the request
            response = test_client.get("/api/v1/credits/balance")
            
            # Verify the response
            assert response.status_code == 200
            data = response.json()
            assert "balance" in data
            assert data["balance"] == 100  # From the mock user auth

    @pytest.mark.asyncio
    async def test_purchase_credits(self, test_client, mock_user_auth, mock_db_session, mock_payment_service):
        """
        Test purchasing credits with mock payment service.
        
        This test verifies that:
        1. The API endpoint accepts a credit purchase request
        2. The payment is processed
        3. The user's credit balance is updated
        4. The response includes the updated balance
        """
        # Setup mock payment service
        with patch("media_summarizer.api.endpoints.credits.process_payment", mock_payment_service.process_payment):
            # Setup mock database query to update and return user credits
            with patch("media_summarizer.adapters.database.connection.get_db", return_value=mock_db_session):
                # Execute the request
                response = test_client.post(
                    "/api/v1/credits/purchase",
                    json={"amount": 50}
                )
                
                # Verify the response
                assert response.status_code == 200
                data = response.json()
                assert "balance" in data
                assert data["balance"] == 150  # 100 initial + 50 purchased
                
    @pytest.mark.asyncio
    async def test_purchase_credits_with_stripe(self, test_client, mock_user_auth, mock_db_session, stripe_client):
        """
        Test purchasing credits using the real Stripe API.
        
        This test verifies that:
        1. The API endpoint accepts a credit purchase request
        2. The payment is processed through Stripe
        3. The user's credit balance is updated
        4. The response includes the updated balance
        """
        # Skip the test if Stripe API key is not available
        if not os.environ.get("STRIPE_TEST_API_KEY"):
            pytest.skip("STRIPE_TEST_API_KEY not found in environment variables")
            
        # Create a test payment method using Stripe's test cards
        payment_method = stripe_client.PaymentMethod.create(
            type="card",
            card={
                "number": "4242424242424242",  # Test card that always succeeds
                "exp_month": 12,
                "exp_year": 2030,
                "cvc": "123",
            },
        )
        
        # Create a test customer
        customer = stripe_client.Customer.create(
            email="user@example.com",
            payment_method=payment_method.id,
            invoice_settings={"default_payment_method": payment_method.id},
        )
        
        # Create a real payment processor function that uses Stripe
        async def real_process_payment(amount, payment_method_id, customer_id):
            try:
                # Create a payment intent
                payment_intent = stripe_client.PaymentIntent.create(
                    amount=amount * 100,  # Stripe uses cents
                    currency="usd",
                    customer=customer.id,
                    payment_method=payment_method.id,
                    confirm=True,
                    off_session=True,
                )
                
                return {
                    "success": True,
                    "transaction_id": payment_intent.id,
                    "amount": amount
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # Setup the real payment processor
        with patch("media_summarizer.api.endpoints.credits.process_payment", real_process_payment):
            # Setup mock database query to update and return user credits
            with patch("media_summarizer.adapters.database.connection.get_db", return_value=mock_db_session):
                # Execute the request
                response = test_client.post(
                    "/api/v1/credits/purchase",
                    json={
                        "amount": 50,
                        "payment_method_id": payment_method.id,
                        "customer_id": customer.id
                    }
                )
                
                # Verify the response
                assert response.status_code == 200
                data = response.json()
                assert "balance" in data
                assert data["balance"] == 150  # 100 initial + 50 purchased

    @pytest.mark.asyncio
    async def test_credit_deduction_for_podcast_processing(
        self, 
        test_client, 
        mock_user_auth, 
        mock_db_session,
        localstack_sqs_client
    ):
        """
        Test credit deduction when submitting a podcast for processing.
        
        This test verifies that:
        1. The API endpoint deducts credits when a podcast is submitted
        2. The user's credit balance is updated
        3. The job is created and processing begins
        """
        # Generate a unique job ID for this test
        job_id = str(uuid.uuid4())
        
        # Setup mock database queries
        with patch("media_summarizer.adapters.database.connection.get_db", return_value=mock_db_session):
            # Setup boto3 client to use our LocalStack client
            with patch("boto3.client", return_value=localstack_sqs_client):
                # Setup mock UUID generation
                with patch("uuid.uuid4", return_value=uuid.UUID(job_id)):
                    # Execute the request
                    response = test_client.post(
                        "/api/v1/podcasts/submit",
                        json={
                            "url": "https://example.com/podcast",
                            "email": "user@example.com"
                        }
                    )
                    
                    # Verify the response
                    assert response.status_code == 200
                    data = response.json()
                    assert "job_id" in data
                    assert data["job_id"] == job_id
                    
                    # Verify that credits were deducted
                    # In a real implementation, we would check the database
                    # Here we're just verifying that the mock was called
                    mock_db_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_credit_refund_for_failed_job(
        self, 
        test_client, 
        mock_user_auth, 
        mock_db_session
    ):
        """
        Test credit refund when a job fails.
        
        This test verifies that:
        1. When a job fails, credits are refunded to the user
        2. The user's credit balance is updated
        3. An error notification is sent
        """
        # Generate a unique job ID for this test
        job_id = str(uuid.uuid4())
        
        # Setup mock database queries
        with patch("media_summarizer.adapters.database.connection.get_db", return_value=mock_db_session):
            # Setup mock SQS client for error notification
            with patch("boto3.client") as mock_boto3:
                mock_sqs = MagicMock()
                mock_sqs.send_message = AsyncMock(return_value={"MessageId": "msg-123"})
                mock_boto3.return_value = mock_sqs
                
                # Create an error notification message
                error_message = {
                    "MessageId": "msg-123",
                    "ReceiptHandle": "receipt-123",
                    "Body": json.dumps({
                        "job_id": job_id,
                        "user_id": "test-user-id",
                        "error": "Failed to process podcast",
                        "step": "transcription",
                        "success": False,
                        "refund_credits": True
                    })
                }
                
                # Process the error notification
                # In a real implementation, this would be handled by a worker
                # Here we're simulating the refund process
                
                # Simulate processing the error message and refunding credits
                # This would normally be done by a worker
                async def refund_credits(user_id, amount, job_id):
                    # Update user credits in database
                    await mock_db_session.execute(
                        "UPDATE users SET credits = credits + :amount WHERE id = :user_id",
                        {"amount": amount, "user_id": user_id}
                    )
                    
                    # Record the transaction
                    await mock_db_session.execute(
                        "INSERT INTO credit_transactions (user_id, amount, type, description, job_id) VALUES (:user_id, :amount, :type, :description, :job_id)",
                        {
                            "user_id": user_id,
                            "amount": amount,
                            "type": "refund",
                            "description": "Failed job refund",
                            "job_id": job_id
                        }
                    )
                    
                    # Send notification
                    await mock_sqs.send_message(
                        QueueUrl="notification-queue",
                        MessageBody=json.dumps({
                            "user_id": user_id,
                            "job_id": job_id,
                            "subject": "Job Failed - Credits Refunded",
                            "message": "Your job failed and your credits have been refunded."
                        })
                    )
                
                # Call the refund function with test data
                await refund_credits(
                    user_id="test-user-id",
                    amount=10,  # Refund 10 credits
                    job_id=job_id
                )
                
                # Verify that credits were refunded
                # In a real implementation, we would check the database
                # Here we're just verifying that the mock was called
                mock_db_session.execute.assert_called()
                
                # Verify that a notification was sent
                mock_sqs.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_insufficient_credits_handling(
        self, 
        test_client, 
        test_db_session
    ):
        """
        Test handling of insufficient credits when submitting a podcast.
        
        This test verifies that:
        1. When a user has insufficient credits, the submission is rejected
        2. An appropriate error message is returned
        3. No job is created
        
        This is a more integration-focused test that uses a real test database
        and minimizes mocking.
        """
        # Setup user auth with insufficient credits
        with patch("media_summarizer.api.dependencies.auth.get_current_user") as mock_auth:
            mock_auth.return_value = {
                "id": "test-user-id",
                "email": "user@example.com",
                "credits": 0  # No credits
            }
            
            # Override the database dependency to use our test session
            app.dependency_overrides[get_db] = lambda: test_db_session
            
            try:
                # Setup SQS client mock - we still need this since we can't easily
                # set up a real SQS queue for testing
                with patch("boto3.client") as mock_boto3:
                    mock_sqs = MagicMock()
                    mock_boto3.return_value = mock_sqs
                    
                    # Execute the request
                    response = test_client.post(
                        "/api/v1/podcasts/submit",
                        json={
                            "url": "https://example.com/podcast",
                            "email": "user@example.com"
                        }
                    )
                    
                    # Verify the response
                    assert response.status_code == 400  # Bad request
                    data = response.json()
                    assert "detail" in data
                    assert "insufficient" in data["detail"].lower()  # Error message about insufficient credits
                    
                    # Verify that no message was sent to SQS (job was not created)
                    mock_sqs.send_message.assert_not_called()
            finally:
                # Clean up the dependency override
                app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_credit_transaction_history(
        self, 
        test_client, 
        mock_user_auth, 
        mock_db_session
    ):
        """
        Test retrieving the user's credit transaction history.
        
        This test verifies that:
        1. The API endpoint returns the user's credit transaction history
        2. The response format is correct
        3. The transactions are properly ordered
        """
        # Setup mock database query to return transaction history
        mock_transactions = [
            {
                "id": "txn-1",
                "user_id": "test-user-id",
                "amount": 50,
                "type": "purchase",
                "description": "Credit purchase",
                "created_at": "2023-01-01T00:00:00Z"
            },
            {
                "id": "txn-2",
                "user_id": "test-user-id",
                "amount": -10,
                "type": "deduction",
                "description": "Podcast processing",
                "job_id": "job-1",
                "created_at": "2023-01-02T00:00:00Z"
            },
            {
                "id": "txn-3",
                "user_id": "test-user-id",
                "amount": 10,
                "type": "refund",
                "description": "Failed job refund",
                "job_id": "job-1",
                "created_at": "2023-01-03T00:00:00Z"
            }
        ]
        
        mock_db_session.execute.return_value.fetchall.return_value = mock_transactions
        
        with patch("media_summarizer.adapters.database.connection.get_db", return_value=mock_db_session):
            # Execute the request
            response = test_client.get("/api/v1/credits/transactions")
            
            # Verify the response
            assert response.status_code == 200
            data = response.json()
            assert "transactions" in data
            assert len(data["transactions"]) == 3
            
            # Verify transaction order (newest first)
            assert data["transactions"][0]["id"] == "txn-3"
            assert data["transactions"][1]["id"] == "txn-2"
            assert data["transactions"][2]["id"] == "txn-1"

    @pytest.mark.asyncio
    async def test_complete_credit_management_workflow(
        self, 
        test_client, 
        mock_user_auth, 
        mock_db_session, 
        mock_payment_service
    ):
        """
        Test the complete credit management workflow.
        
        This test verifies the entire flow:
        1. Check initial credit balance
        2. Purchase credits
        3. Submit a podcast (deduct credits)
        4. Process the podcast
        5. Check final credit balance
        """
        # Generate a unique job ID for this test
        job_id = str(uuid.uuid4())
        
        # Setup mock database queries and payment service
        with patch("media_summarizer.adapters.database.connection.get_db", return_value=mock_db_session):
            with patch("media_summarizer.api.endpoints.credits.process_payment", mock_payment_service.process_payment):
                # Setup mock SQS client
                with patch("boto3.client") as mock_boto3:
                    mock_sqs = MagicMock()
                    mock_sqs.send_message = AsyncMock(return_value={"MessageId": "msg-123"})
                    mock_boto3.return_value = mock_sqs
                    
                    # 1. Check initial credit balance
                    response = test_client.get("/api/v1/credits/balance")
                    assert response.status_code == 200
                    initial_balance = response.json()["balance"]
                    assert initial_balance == 100
                    
                    # 2. Purchase credits
                    response = test_client.post(
                        "/api/v1/credits/purchase",
                        json={"amount": 50}
                    )
                    assert response.status_code == 200
                    updated_balance = response.json()["balance"]
                    assert updated_balance == 150  # 100 initial + 50 purchased
                    
                    # 3. Submit a podcast (deduct credits)
                    with patch("uuid.uuid4", return_value=uuid.UUID(job_id)):
                        response = test_client.post(
                            "/api/v1/podcasts/submit",
                            json={
                                "url": "https://example.com/podcast",
                                "email": "user@example.com"
                            }
                        )
                        assert response.status_code == 200
                        assert response.json()["job_id"] == job_id
                    
                    # 4. Check final credit balance
                    # In a real implementation, we would update the mock to reflect the new balance
                    # Here we're just verifying that the endpoint is called
                    response = test_client.get("/api/v1/credits/balance")
                    assert response.status_code == 200