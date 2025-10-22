import pytest
pytestmark = pytest.mark.skip("Legacy credits system removed (replaced by minutes)")

"""
Unit tests for the credits endpoints.
"""
import os
import pytest
import pytest_asyncio
import uuid
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

# Set AWS credentials for testing
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"

from media_summarizer.api.main import app
from media_summarizer.api.dependencies.auth import require_verified_email
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.api.endpoints.credits import (
    CreditPurchaseRequest,
    CreditDeductionRequest,
    CreditRefundRequest,
    CreditBalanceResponse,
    CreditTransactionResponse
)
from media_summarizer.core.models import User, CreditTransaction


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)

@pytest.fixture(autouse=True)
def auth_override():
    """Override auth to always provide a verified user for credits endpoints."""
    async def _ov():
        return AuthUser(id="user123", email="test@example.com", credits=100)
    app.dependency_overrides[require_verified_email] = _ov
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_db():
    """Mock database connection for testing."""
    with patch("media_summarizer.api.endpoints.credits.get_db") as mock_get_db:
        mock_connection = AsyncMock()
        mock_get_db.return_value = mock_connection
        yield mock_connection


@pytest.fixture
def sample_user():
    """Create a sample user for testing."""
    return User(
        id="user123",
        email="test@example.com",
        credits=100
    )


@pytest.fixture
def sample_transaction():
    """Create a sample credit transaction for testing."""
    return CreditTransaction.create_purchase(
        user_id="user123",
        amount=50,
        description="Test purchase"
    )


class TestCreditBalance:
    """Test cases for credit balance endpoints."""

    @pytest.mark.asyncio
    async def test_get_user_credits_success(self, client, mock_db, sample_user):
        """Test successful credit balance retrieval."""
        with patch("media_summarizer.api.endpoints.credits.database_async.get_user_by_id") as mock_get_user:
            mock_get_user.return_value = sample_user

            response = client.get("/api/v1/users/user123/credits")

            assert response.status_code == 200
            data = response.json()
            assert data["user_id"] == "user123"
            assert data["credits"] == 100
            assert "last_updated" in data

    @pytest.mark.asyncio
    async def test_get_user_credits_not_found(self, client, mock_db):
        """Test credit balance retrieval for non-existent user."""
        with patch("media_summarizer.api.endpoints.credits.database_async.get_user_by_id") as mock_get_user:
            mock_get_user.return_value = None

            response = client.get("/api/v1/users/nonexistent/credits")

            assert response.status_code == 404
            assert "Utilisateur non trouvé" in response.json()["detail"]


class TestCreditPurchase:
    """Test cases for credit purchase endpoints."""

    @pytest.mark.asyncio
    async def test_purchase_credits_success(self, client, mock_db, sample_user):
        """Test successful credit purchase."""
        updated_user = User(
            id=sample_user.id,
            email=sample_user.email,
            credits=sample_user.credits + 50
        )

        with patch("media_summarizer.api.endpoints.credits.database_async.get_user_by_id") as mock_get_user:
            with patch("media_summarizer.api.endpoints.credits.database_async.create_credit_transaction") as mock_create_tx:
                with patch("media_summarizer.api.endpoints.credits.database_async.update_user_credits") as mock_update_credits:
                    mock_get_user.return_value = sample_user
                    mock_update_credits.return_value = updated_user

                    response = client.post("/api/v1/credits/purchase", json={
                        "user_id": "user123",
                        "amount": 50,
                        "payment_method": "stripe",
                        "description": "Test purchase"
                    })

                    assert response.status_code == 400
                    assert "Direct Stripe purchases are no longer supported" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_purchase_credits_user_not_found(self, client, mock_db):
        """Test credit purchase for non-existent user."""
        with patch("media_summarizer.api.endpoints.credits.database_async.get_user_by_id") as mock_get_user:
            mock_get_user.return_value = None

            response = client.post("/api/v1/credits/purchase", json={
                "user_id": "nonexistent",
                "amount": 50,
                "payment_method": "stripe"
            })

            assert response.status_code == 404
            assert "Utilisateur non trouvé" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_purchase_credits_invalid_amount(self, client):
        """Test credit purchase with invalid amount."""
        response = client.post("/api/v1/credits/purchase", json={
            "user_id": "user123",
            "amount": -10,
            "payment_method": "stripe"
        })

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_purchase_credits_missing_fields(self, client):
        """Test credit purchase with missing required fields."""
        response = client.post("/api/v1/credits/purchase", json={
            "amount": 50
        })

        assert response.status_code == 422  # Validation error


class TestCreditDeduction:
    """Test cases for credit deduction endpoints."""

    @pytest.mark.asyncio
    async def test_deduct_credits_success(self, client, mock_db, sample_user):
        """Test successful credit deduction."""
        updated_user = User(
            id=sample_user.id,
            email=sample_user.email,
            credits=sample_user.credits - 20
        )

        with patch("media_summarizer.api.endpoints.credits.database_async.get_user_by_id") as mock_get_user:
            with patch("media_summarizer.api.endpoints.credits.database_async.create_credit_transaction") as mock_create_tx:
                with patch("media_summarizer.api.endpoints.credits.database_async.update_user_credits") as mock_update_credits:
                    mock_get_user.return_value = sample_user
                    mock_update_credits.return_value = updated_user

                    response = client.post("/api/v1/credits/deduct", json={
                        "user_id": "user123",
                        "amount": 20,
                        "job_id": "job456",
                        "description": "Processing fee"
                    })

                    assert response.status_code == 200
                    data = response.json()
                    assert data["user_id"] == "user123"
                    assert data["credits"] == 80
                    mock_create_tx.assert_called_once()

    @pytest.mark.asyncio
    async def test_deduct_credits_insufficient_balance(self, client, mock_db, sample_user):
        """Test credit deduction with insufficient balance."""
        with patch("media_summarizer.api.endpoints.credits.database_async.get_user_by_id") as mock_get_user:
            mock_get_user.return_value = sample_user

            response = client.post("/api/v1/credits/deduct", json={
                "user_id": "user123",
                "amount": 150,  # More than available
                "description": "Too much"
            })

            assert response.status_code == 400
            assert "Crédits insuffisants" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_deduct_credits_user_not_found(self, client, mock_db):
        """Test credit deduction for non-existent user."""
        with patch("media_summarizer.api.endpoints.credits.database_async.get_user_by_id") as mock_get_user:
            mock_get_user.return_value = None

            response = client.post("/api/v1/credits/deduct", json={
                "user_id": "nonexistent",
                "amount": 20
            })

            assert response.status_code == 404
            assert "Utilisateur non trouvé" in response.json()["detail"]


class TestCreditRefund:
    """Test cases for credit refund endpoints."""

    @pytest.mark.asyncio
    async def test_refund_credits_success(self, client, mock_db, sample_user):
        """Test successful credit refund."""
        updated_user = User(
            id=sample_user.id,
            email=sample_user.email,
            credits=sample_user.credits + 30
        )

        with patch("media_summarizer.api.endpoints.credits.database_async.get_user_by_id") as mock_get_user:
            with patch("media_summarizer.api.endpoints.credits.database_async.create_credit_transaction") as mock_create_tx:
                with patch("media_summarizer.api.endpoints.credits.database_async.update_user_credits") as mock_update_credits:
                    mock_get_user.return_value = sample_user
                    mock_update_credits.return_value = updated_user

                    response = client.post("/api/v1/credits/refund", json={
                        "user_id": "user123",
                        "amount": 30,
                        "job_id": "job456",
                        "reason": "Job failed"
                    })

                    assert response.status_code == 200
                    data = response.json()
                    assert data["user_id"] == "user123"
                    assert data["credits"] == 130
                    mock_create_tx.assert_called_once()

    @pytest.mark.asyncio
    async def test_refund_credits_user_not_found(self, client, mock_db):
        """Test credit refund for non-existent user."""
        with patch("media_summarizer.api.endpoints.credits.database_async.get_user_by_id") as mock_get_user:
            mock_get_user.return_value = None

            response = client.post("/api/v1/credits/refund", json={
                "user_id": "nonexistent",
                "amount": 30,
                "reason": "Failed job"
            })

            assert response.status_code == 404
            assert "Utilisateur non trouvé" in response.json()["detail"]


class TestCreditTransactions:
    """Test cases for credit transaction endpoints."""

    @pytest.mark.asyncio
    async def test_get_user_credit_transactions_success(self, client, mock_db, sample_user, sample_transaction):
        """Test successful retrieval of user credit transactions."""
        transactions = [sample_transaction]

        with patch("media_summarizer.api.endpoints.credits.database_async.get_user_by_id") as mock_get_user:
            with patch("media_summarizer.api.endpoints.credits.database_async.get_credit_transactions_by_user_id") as mock_get_transactions:
                mock_get_user.return_value = sample_user
                mock_get_transactions.return_value = transactions

                response = client.get("/api/v1/users/user123/credits/transactions")

                assert response.status_code == 200
                data = response.json()
                assert len(data) == 1
                assert data[0]["user_id"] == "user123"
                assert data[0]["amount"] == 50
                assert data[0]["type"] == "purchase"

    @pytest.mark.asyncio
    async def test_get_user_credit_transactions_user_not_found(self, client, mock_db):
        """Test credit transactions retrieval for non-existent user."""
        with patch("media_summarizer.api.endpoints.credits.database_async.get_user_by_id") as mock_get_user:
            mock_get_user.return_value = None

            response = client.get("/api/v1/users/nonexistent/credits/transactions")

            assert response.status_code == 404
            assert "Utilisateur non trouvé" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_credit_transaction_success(self, client, mock_db, sample_transaction):
        """Test successful retrieval of a specific credit transaction."""
        with patch("media_summarizer.api.endpoints.credits.database_async.get_credit_transaction_by_id") as mock_get_transaction:
            mock_get_transaction.return_value = sample_transaction

            response = client.get(f"/api/v1/credits/transactions/{sample_transaction.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == sample_transaction.id
            assert data["user_id"] == "user123"
            assert data["amount"] == 50

    @pytest.mark.asyncio
    async def test_get_credit_transaction_not_found(self, client, mock_db):
        """Test retrieval of non-existent credit transaction."""
        with patch("media_summarizer.api.endpoints.credits.database_async.get_credit_transaction_by_id") as mock_get_transaction:
            mock_get_transaction.return_value = None

            response = client.get("/api/v1/credits/transactions/txn123")

            assert response.status_code == 404
            assert "Transaction non trouvée" in response.json()["detail"]


class TestModelValidation:
    """Test cases for Pydantic model validation."""

    def test_credit_purchase_request_validation(self):
        """Test CreditPurchaseRequest validation."""
        # Valid request
        valid_request = CreditPurchaseRequest(
            user_id="user123",
            amount=50,
            payment_method="stripe",
            description="Test purchase"
        )
        assert valid_request.amount == 50

        # Invalid amount (negative)
        with pytest.raises(ValueError):
            CreditPurchaseRequest(
                user_id="user123",
                amount=-10,
                payment_method="stripe"
            )

        # Invalid amount (zero)
        with pytest.raises(ValueError):
            CreditPurchaseRequest(
                user_id="user123",
                amount=0,
                payment_method="stripe"
            )

    def test_credit_deduction_request_validation(self):
        """Test CreditDeductionRequest validation."""
        # Valid request
        valid_request = CreditDeductionRequest(
            user_id="user123",
            amount=20,
            job_id="job456",
            description="Processing fee"
        )
        assert valid_request.amount == 20

        # Invalid amount
        with pytest.raises(ValueError):
            CreditDeductionRequest(
                user_id="user123",
                amount=-5
            )

    def test_credit_refund_request_validation(self):
        """Test CreditRefundRequest validation."""
        # Valid request
        valid_request = CreditRefundRequest(
            user_id="user123",
            amount=30,
            reason="Job failed"
        )
        assert valid_request.amount == 30

        # Invalid amount
        with pytest.raises(ValueError):
            CreditRefundRequest(
                user_id="user123",
                amount=0,
                reason="Invalid"
            )

    def test_credit_balance_response_from_user(self, sample_user):
        """Test CreditBalanceResponse.from_user method."""
        response = CreditBalanceResponse.from_user(sample_user)

        assert response.user_id == sample_user.id
        assert response.credits == sample_user.credits
        assert response.last_updated == sample_user.updated_at.isoformat()

    def test_credit_transaction_response_from_transaction(self, sample_transaction):
        """Test CreditTransactionResponse.from_transaction method."""
        response = CreditTransactionResponse.from_transaction(sample_transaction)

        assert response.id == sample_transaction.id
        assert response.user_id == sample_transaction.user_id
        assert response.amount == sample_transaction.amount
        assert response.type == sample_transaction.type
        assert response.created_at == sample_transaction.created_at.isoformat()
