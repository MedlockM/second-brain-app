"""
User model for the Media Summarizer application using DynamoDB.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
import uuid


class User(BaseModel):
    """User model for storing user information and credits in DynamoDB."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str = Field(..., min_length=1)
    credits: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Optional auth-related fields
    password_hash: Optional[str] = None
    auth_provider: Optional[str] = None  # e.g., "local", "google", "apple"
    provider_id: Optional[str] = None    # e.g., OIDC sub
    email_verified_at: Optional[datetime] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None

    @field_validator('email')
    @classmethod
    def email_must_be_valid(cls, v):
        """Validate that the email is not empty and has basic format."""
        if not v.strip():
            raise ValueError('Email must not be empty')
        if '@' not in v:
            raise ValueError('Email must contain @ symbol')
        return v.lower().strip()

    @field_validator('credits')
    @classmethod
    def credits_must_be_non_negative(cls, v):
        """Validate that credits is non-negative."""
        if v < 0:
            raise ValueError('Credits cannot be negative')
        return v

    def to_dynamodb_item(self) -> Dict[str, Any]:
        """Convert the model to a DynamoDB item."""
        item: Dict[str, Any] = {
            'id': self.id,
            'email': self.email,
            'credits': self.credits,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        # Add optional fields only if present (DynamoDB doesn't accept nulls)
        if self.password_hash is not None:
            item['password_hash'] = self.password_hash
        if self.auth_provider is not None:
            item['auth_provider'] = self.auth_provider
        if self.provider_id is not None:
            item['provider_id'] = self.provider_id
        if self.email_verified_at is not None:
            item['email_verified_at'] = self.email_verified_at.isoformat()
        if self.name is not None:
            item['name'] = self.name
        if self.avatar_url is not None:
            item['avatar_url'] = self.avatar_url
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> 'User':
        """Create a User instance from a DynamoDB item."""
        return cls(
            id=item['id'],
            email=item['email'],
            credits=item['credits'],
            created_at=datetime.fromisoformat(item['created_at']),
            updated_at=datetime.fromisoformat(item['updated_at']),
            password_hash=item.get('password_hash'),
            auth_provider=item.get('auth_provider'),
            provider_id=item.get('provider_id'),
            email_verified_at=(datetime.fromisoformat(item['email_verified_at']) if item.get('email_verified_at') else None),
            name=item.get('name'),
            avatar_url=item.get('avatar_url')
        )

    def update_credits(self, amount: int) -> None:
        """Update user credits and timestamp."""
        self.credits += amount
        self.updated_at = datetime.now(timezone.utc)

        if self.credits < 0:
            raise ValueError('Credits cannot be negative after update')

    def deduct_credits(self, amount: int) -> None:
        """Deduct credits from user account."""
        if amount <= 0:
            raise ValueError('Amount to deduct must be positive')

        if self.credits < amount:
            raise ValueError(f'Insufficient credits. Available: {self.credits}, Required: {amount}')

        self.credits -= amount
        self.updated_at = datetime.now(timezone.utc)

    def add_credits(self, amount: int) -> None:
        """Add credits to user account."""
        if amount <= 0:
            raise ValueError('Amount to add must be positive')

        self.credits += amount
        self.updated_at = datetime.now(timezone.utc)

    def update(self, **kwargs):
        """Update user attributes."""
        for key, value in kwargs.items():
            if hasattr(self, key) and key != 'id':  # Don't allow ID updates
                setattr(self, key, value)
        self.updated_at = datetime.now(timezone.utc)
        return self

    def __repr__(self):
        return f"<User(id='{self.id}', email='{self.email}', credits={self.credits})>"
