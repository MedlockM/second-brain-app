"""
Pydantic models for Subscriptions and Follows.

These models mirror the DynamoDB storage structure and provide to_dynamodb_item/from_dynamodb_item helpers,
consistent with other models in the codebase.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SubscriptionStatus(str, Enum):
    active = "active"
    canceled = "canceled"
    incomplete = "incomplete"
    past_due = "past_due"
    unpaid = "unpaid"
    expired = "expired"
    grace_period = "grace_period"


class SubscriptionPlatform(str, Enum):
    ios = "ios"
    android = "android"


class SubscriptionTier(str, Enum):
    S = "S"
    M = "M"
    L = "L"


class Subscription(BaseModel):
    id: str = Field(...)
    user_id: str = Field(...)
    tier: SubscriptionTier = Field(...)
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    status: SubscriptionStatus = Field(default=SubscriptionStatus.active)
    cancel_at_period_end: bool = Field(default=False)
    # RevenueCat-specific fields
    revenucat_app_user_id: Optional[str] = None
    revenucat_product_id: Optional[str] = None
    # The store's own identifier for this subscription, which is RevenueCat's
    # `original_transaction_id`. It is what lets a webhook event name the row it
    # describes instead of the handler guessing. Optional because a store does
    # not always send one and because a row written before the field existed
    # carries none: matching then falls back to the (platform, product) pair.
    revenucat_store_subscription_id: Optional[str] = None
    platform: Optional[SubscriptionPlatform] = None
    auto_renew_status: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dynamodb_item(self) -> Dict[str, Any]:
        item = {
            "id": self.id,
            "user_id": self.user_id,
            "tier": self.tier.value,
            "status": self.status.value,
            "cancel_at_period_end": self.cancel_at_period_end,
            "auto_renew_status": self.auto_renew_status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if self.current_period_start:
            item["current_period_start"] = self.current_period_start.isoformat()
        if self.current_period_end:
            item["current_period_end"] = self.current_period_end.isoformat()
        if self.revenucat_app_user_id:
            item["revenucat_app_user_id"] = self.revenucat_app_user_id
        if self.revenucat_product_id:
            item["revenucat_product_id"] = self.revenucat_product_id
        if self.revenucat_store_subscription_id:
            item["revenucat_store_subscription_id"] = self.revenucat_store_subscription_id
        if self.platform:
            item["platform"] = self.platform.value
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "Subscription":
        cps = item.get("current_period_start")
        cpe = item.get("current_period_end")
        platform_val = item.get("platform")
        return cls(
            id=item["id"],
            user_id=item["user_id"],
            tier=SubscriptionTier(item["tier"]),
            current_period_start=datetime.fromisoformat(cps) if cps else None,
            current_period_end=datetime.fromisoformat(cpe) if cpe else None,
            status=SubscriptionStatus(item["status"]),
            cancel_at_period_end=bool(item.get("cancel_at_period_end", False)),
            revenucat_app_user_id=item.get("revenucat_app_user_id"),
            revenucat_product_id=item.get("revenucat_product_id"),
            revenucat_store_subscription_id=item.get("revenucat_store_subscription_id"),
            platform=SubscriptionPlatform(platform_val) if platform_val else None,
            auto_renew_status=bool(item.get("auto_renew_status", True)),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )


class Follow(BaseModel):
    user_id: str = Field(...)
    feed_id: str = Field(...)
    forecast_minutes: int = Field(default=0, ge=0)
    reserved_minutes: int = Field(default=0, ge=0)
    history_pointer: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dynamodb_item(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "feed_id": self.feed_id,
            "forecast_minutes": self.forecast_minutes,
            "reserved_minutes": self.reserved_minutes,
            "history_pointer": self.history_pointer,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "Follow":
        return cls(
            user_id=item["user_id"],
            feed_id=item["feed_id"],
            forecast_minutes=item.get("forecast_minutes", 0),
            reserved_minutes=item.get("reserved_minutes", 0),
            history_pointer=item.get("history_pointer"),
            created_at=datetime.fromisoformat(item["created_at"]) if item.get("created_at") else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(item["updated_at"]) if item.get("updated_at") else datetime.now(timezone.utc),
        )

