"""
Payment models for Stripe integration.

This module contains Pydantic models for handling payment-related requests and responses
in the Media Summarizer API.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class PaymentStatus(str, Enum):
    """Payment status enumeration."""
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    REFUNDED = "refunded"
    REQUIRES_ACTION = "requires_action"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    REQUIRES_PAYMENT_METHOD = "requires_payment_method"
    PROCESSING = "processing"


class CreditPackage(str, Enum):
    """Available credit packages."""
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    ENTERPRISE = "enterprise"


class PaymentIntentRequest(BaseModel):
    """Request model for creating a payment intent."""
    credits: int = Field(..., gt=0, description="Number of credits to purchase")
    currency: str = Field(default="eur", description="Payment currency")
    metadata: Optional[Dict[str, str]] = Field(default=None, description="Additional metadata")

    @field_validator('credits')
    @classmethod
    def validate_credits(cls, v):
        """Validate that credits amount corresponds to available packages."""
        valid_amounts = [50, 150, 500, 1000]  # Must match StripeService.credit_packages
        if v not in valid_amounts:
            raise ValueError(f'Credits must be one of: {valid_amounts}')
        return v

    @field_validator('currency')
    @classmethod
    def validate_currency(cls, v):
        """Validate currency code."""
        supported_currencies = ['eur', 'usd']
        if v.lower() not in supported_currencies:
            raise ValueError(f'Currency must be one of: {supported_currencies}')
        return v.lower()


class PaymentIntentResponse(BaseModel):
    """Response model for payment intent creation."""
    payment_intent_id: str = Field(..., description="Stripe payment intent ID")
    client_secret: str = Field(..., description="Client secret for frontend processing")
    amount: int = Field(..., description="Amount in cents")
    currency: str = Field(..., description="Payment currency")
    credits: int = Field(..., description="Number of credits to be purchased")
    package: Dict[str, Any] = Field(..., description="Credit package details")


class PaymentConfirmationRequest(BaseModel):
    """Request model for confirming a payment."""
    payment_intent_id: str = Field(..., description="Stripe payment intent ID")

    @field_validator('payment_intent_id')
    @classmethod
    def validate_payment_intent_id(cls, v):
        """Validate payment intent ID format."""
        if not v.startswith('pi_'):
            raise ValueError('Invalid payment intent ID format')
        return v


class PaymentConfirmationResponse(BaseModel):
    """Response model for payment confirmation."""
    payment_intent_id: str = Field(..., description="Stripe payment intent ID")
    status: PaymentStatus = Field(..., description="Payment status")
    credits_added: Optional[int] = Field(None, description="Credits added to account")
    transaction_id: Optional[str] = Field(None, description="Credit transaction ID")
    message: str = Field(..., description="Status message")


class RefundRequest(BaseModel):
    """Request model for creating a refund."""
    payment_intent_id: str = Field(..., description="Stripe payment intent ID")
    amount: Optional[int] = Field(None, description="Amount to refund in cents (full refund if None)")
    reason: str = Field(default="requested_by_customer", description="Reason for refund")

    @field_validator('payment_intent_id')
    @classmethod
    def validate_payment_intent_id(cls, v):
        """Validate payment intent ID format."""
        if not v.startswith('pi_'):
            raise ValueError('Invalid payment intent ID format')
        return v

    @field_validator('reason')
    @classmethod
    def validate_reason(cls, v):
        """Validate refund reason."""
        valid_reasons = [
            "duplicate", "fraudulent", "requested_by_customer",
            "expired_uncaptured_charge", "product_unsatisfactory",
            "product_not_received", "unrecognized", "credit_not_processed"
        ]
        if v not in valid_reasons:
            raise ValueError(f'Reason must be one of: {valid_reasons}')
        return v


class RefundResponse(BaseModel):
    """Response model for refund creation."""
    refund_id: str = Field(..., description="Stripe refund ID")
    amount: int = Field(..., description="Refunded amount in cents")
    status: str = Field(..., description="Refund status")
    payment_intent_id: str = Field(..., description="Original payment intent ID")
    credits_deducted: Optional[int] = Field(None, description="Credits deducted from account")


class PaymentMethodResponse(BaseModel):
    """Response model for payment methods."""
    id: str = Field(..., description="Payment method ID")
    type: str = Field(..., description="Payment method type")
    card: Optional[Dict[str, Any]] = Field(None, description="Card details if applicable")


class WebhookEventRequest(BaseModel):
    """Request model for webhook events."""
    event_type: str = Field(..., description="Stripe webhook event type")
    event_id: str = Field(..., description="Stripe event ID")
    data: Dict[str, Any] = Field(..., description="Event data")


class CreditPackageInfo(BaseModel):
    """Information about a credit package."""
    id: str = Field(..., description="Package ID")
    name: str = Field(..., description="Package name")
    credits: int = Field(..., description="Number of credits")
    price_cents: int = Field(..., description="Price in cents")
    price_euro: float = Field(..., description="Price in euros")
    savings_percent: Optional[float] = Field(None, description="Savings percentage compared to base price")

    @classmethod
    def from_stripe_package(cls, package_id: str, package_data: Dict[str, Any]) -> "CreditPackageInfo":
        """Create CreditPackageInfo from Stripe service package data."""
        price_euro = package_data["price_cents"] / 100

        # Calculate savings compared to a base rate (e.g., 2 cents per credit)
        base_price_per_credit = 2  # cents
        actual_price_per_credit = package_data["price_cents"] / package_data["credits"]
        savings_percent = max(0, (base_price_per_credit - actual_price_per_credit) / base_price_per_credit * 100)

        return cls(
            id=package_id,
            name=package_data["name"],
            credits=package_data["credits"],
            price_cents=package_data["price_cents"],
            price_euro=price_euro,
            savings_percent=round(savings_percent, 1) if savings_percent > 0 else None
        )


class CreditPackagesResponse(BaseModel):
    """Response model for available credit packages."""
    packages: List[CreditPackageInfo] = Field(..., description="Available credit packages")
    currency: str = Field(default="eur", description="Currency for prices")


class PaymentHistoryItem(BaseModel):
    """Individual payment history item."""
    payment_intent_id: str = Field(..., description="Stripe payment intent ID")
    amount: int = Field(..., description="Amount paid in cents")
    credits: int = Field(..., description="Credits purchased")
    status: PaymentStatus = Field(..., description="Payment status")
    created_at: datetime = Field(..., description="Payment creation date")
    package_name: Optional[str] = Field(None, description="Package name")


class PaymentHistoryResponse(BaseModel):
    """Response model for payment history."""
    payments: List[PaymentHistoryItem] = Field(..., description="Payment history")
    total_count: int = Field(..., description="Total number of payments")
    total_spent_cents: int = Field(..., description="Total amount spent in cents")
    total_credits_purchased: int = Field(..., description="Total credits purchased")


class StripeCustomerResponse(BaseModel):
    """Response model for Stripe customer information."""
    customer_id: str = Field(..., description="Stripe customer ID")
    email: str = Field(..., description="Customer email")
    payment_methods: List[PaymentMethodResponse] = Field(..., description="Available payment methods")
    created_at: datetime = Field(..., description="Customer creation date")


class CheckoutSessionRequest(BaseModel):
    """Request model for creating a Stripe Checkout Session."""
    credits: int = Field(..., gt=0, description="Number of credits to purchase")

    @field_validator('credits')
    @classmethod
    def validate_credits(cls, v):
        """Validate that credits amount corresponds to available packages."""
        valid_amounts = [50, 150, 500, 1000]  # Must match StripeService.credit_packages
        if v not in valid_amounts:
            raise ValueError(f'Credits must be one of: {valid_amounts}')
        return v


class CheckoutSessionResponse(BaseModel):
    """Response model for Stripe Checkout Session creation."""
    session_id: str = Field(..., description="Stripe Checkout Session ID")
    url: str = Field(..., description="URL to redirect the user to")


class CustomerPortalResponse(BaseModel):
    """Response model for Stripe Billing Customer Portal."""
    url: str = Field(..., description="URL to redirect the user to")
