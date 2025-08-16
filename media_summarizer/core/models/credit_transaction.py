"""
Credit transaction model for tracking credit purchases, deductions, and refunds using DynamoDB.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
import uuid


class CreditTransaction(BaseModel):
    """Credit transaction model for tracking all credit-related operations in DynamoDB."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(..., min_length=1)
    amount: int = Field(..., description="Positive for purchases/refunds, negative for deductions")
    type: str = Field(..., description="'purchase', 'deduction', 'refund'")
    description: Optional[str] = Field(None, max_length=500)
    job_id: Optional[str] = Field(None, description="Optional, for linking to specific jobs")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator('type')
    @classmethod
    def type_must_be_valid(cls, v):
        """Validate that the transaction type is valid."""
        valid_types = ['purchase', 'deduction', 'refund']
        if v not in valid_types:
            raise ValueError(f'Type must be one of: {valid_types}')
        return v

    @model_validator(mode='after')
    def amount_validation(self):
        """Validate amount based on transaction type."""
        transaction_type = self.type

        if transaction_type == 'deduction' and self.amount >= 0:
            raise ValueError('Deduction amount must be negative')
        elif transaction_type in ['purchase', 'refund'] and self.amount <= 0:
            raise ValueError('Purchase and refund amounts must be positive')

        return self

    @field_validator('user_id')
    @classmethod
    def user_id_must_not_be_empty(cls, v):
        """Validate that user_id is not empty."""
        if not v.strip():
            raise ValueError('User ID must not be empty')
        return v.strip()

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert the model to a DynamoDB item."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': self.amount,
            'type': self.type,
            'description': self.description,
            'job_id': self.job_id,
            'created_at': self.created_at.isoformat()
        }

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> 'CreditTransaction':
        """Create a CreditTransaction instance from a DynamoDB item."""
        return cls(
            id=item['id'],
            user_id=item['user_id'],
            amount=item['amount'],
            type=item['type'],
            description=item.get('description'),
            job_id=item.get('job_id'),
            created_at=datetime.fromisoformat(item['created_at'])
        )

    @classmethod
    def create_purchase(cls, user_id: str, amount: int, description: Optional[str] = None) -> 'CreditTransaction':
        """Create a credit purchase transaction."""
        if amount <= 0:
            raise ValueError('Purchase amount must be positive')

        return cls(
            user_id=user_id,
            amount=amount,
            type='purchase',
            description=description or f'Credit purchase: {amount} credits',
            job_id=None
        )

    @classmethod
    def create_deduction(cls, user_id: str, amount: int, job_id: Optional[str] = None, description: Optional[str] = None) -> 'CreditTransaction':
        """Create a credit deduction transaction."""
        if amount <= 0:
            raise ValueError('Deduction amount must be positive (will be stored as negative)')

        return cls(
            user_id=user_id,
            amount=-amount,  # Store as negative
            type='deduction',
            job_id=job_id,
            description=description or f'Credit deduction for processing: {amount} credits'
        )

    @classmethod
    def create_refund(cls, user_id: str, amount: int, job_id: Optional[str] = None, description: Optional[str] = None) -> 'CreditTransaction':
        """Create a credit refund transaction."""
        if amount <= 0:
            raise ValueError('Refund amount must be positive')

        return cls(
            user_id=user_id,
            amount=amount,
            type='refund',
            job_id=job_id,
            description=description or f'Credit refund: {amount} credits'
        )

    def is_purchase(self) -> bool:
        """Check if this is a purchase transaction."""
        return self.type == 'purchase'

    def is_deduction(self) -> bool:
        """Check if this is a deduction transaction."""
        return self.type == 'deduction'

    def is_refund(self) -> bool:
        """Check if this is a refund transaction."""
        return self.type == 'refund'

    def __repr__(self):
        return f"<CreditTransaction(id='{self.id}', user_id='{self.user_id}', amount={self.amount}, type='{self.type}')>"
