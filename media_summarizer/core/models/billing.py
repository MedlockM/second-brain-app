"""
Pydantic models for minutes-based billing: Subscriptions, Minute Buckets, Minute Usage, and Follows.

These models mirror the DynamoDB storage structure and provide to_dynamodb_item/from_dynamodb_item helpers,
consistent with other models in the codebase.
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SubscriptionStatus(str, Enum):
    active = "active"
    canceled = "canceled"
    incomplete = "incomplete"
    past_due = "past_due"
    unpaid = "unpaid"


class SubscriptionTier(str, Enum):
    S = "S"
    M = "M"
    L = "L"


class Subscription(BaseModel):
    id: str = Field(...)
    user_id: str = Field(...)
    tier: SubscriptionTier = Field(...)
    minutes_per_period: int = Field(..., ge=0)
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    status: SubscriptionStatus = Field(default=SubscriptionStatus.active)
    cancel_at_period_end: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dynamodb_item(self) -> Dict[str, Any]:
        item = {
            "id": self.id,
            "user_id": self.user_id,
            "tier": self.tier.value,
            "minutes_per_period": self.minutes_per_period,
            "status": self.status.value,
            "cancel_at_period_end": self.cancel_at_period_end,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if self.current_period_start:
            item["current_period_start"] = self.current_period_start.isoformat()
        if self.current_period_end:
            item["current_period_end"] = self.current_period_end.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "Subscription":
        cps = item.get("current_period_start")
        cpe = item.get("current_period_end")
        return cls(
            id=item["id"],
            user_id=item["user_id"],
            tier=SubscriptionTier(item["tier"]),
            minutes_per_period=item["minutes_per_period"],
            current_period_start=datetime.fromisoformat(cps) if cps else None,
            current_period_end=datetime.fromisoformat(cpe) if cpe else None,
            status=SubscriptionStatus(item["status"]),
            cancel_at_period_end=bool(item.get("cancel_at_period_end", False)),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )


class MinuteBucketSource(str, Enum):
    subscription = "subscription"
    pack = "pack"
    rollover = "rollover"
    migration = "migration"


class MinuteBucket(BaseModel):
    id: str = Field(...)
    user_id: str = Field(...)
    source_type: MinuteBucketSource = Field(...)
    source_ref: Optional[str] = None
    minutes_total: int = Field(..., ge=0)
    minutes_remaining: int = Field(..., ge=0)
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    expires_at: Optional[datetime] = None  # Used for TTL (packs, rollover)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dynamodb_item(self) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "id": self.id,
            "user_id": self.user_id,
            "source_type": self.source_type.value,
            "source_ref": self.source_ref,
            "minutes_total": self.minutes_total,
            "minutes_remaining": self.minutes_remaining,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if self.period_start:
            item["period_start"] = self.period_start.isoformat()
        if self.period_end:
            item["period_end"] = self.period_end.isoformat()
        if self.expires_at:
            item["expires_at"] = self.expires_at.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "MinuteBucket":
        ps = item.get("period_start")
        pe = item.get("period_end")
        exp = item.get("expires_at")
        return cls(
            id=item["id"],
            user_id=item["user_id"],
            source_type=MinuteBucketSource(item["source_type"]),
            source_ref=item.get("source_ref"),
            minutes_total=item["minutes_total"],
            minutes_remaining=item["minutes_remaining"],
            period_start=datetime.fromisoformat(ps) if ps else None,
            period_end=datetime.fromisoformat(pe) if pe else None,
            expires_at=datetime.fromisoformat(exp) if exp else None,
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )


class MinuteUsageStatus(str, Enum):
    held = "held"
    finalized = "finalized"
    released = "released"
    expired = "expired"
    failed = "failed"


class MinuteUsage(BaseModel):
    id: str = Field(...)
    user_id: str = Field(...)
    job_id: str = Field(...)
    status: MinuteUsageStatus = Field(default=MinuteUsageStatus.held)
    minutes_estimated: int = Field(..., ge=0)
    minutes_used: Optional[int] = Field(default=None, ge=0)
    # Breakdown des buckets: [{"bucket_id": str, "minutes": int}]
    bucket_breakdown: List[Dict[str, Any]] = Field(default_factory=list)
    hold_expires_at: Optional[datetime] = None  # TTL pour les holds
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finalized_at: Optional[datetime] = None

    def to_dynamodb_item(self) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "id": self.id,
            "user_id": self.user_id,
            "job_id": self.job_id,
            "status": self.status.value,
            "minutes_estimated": self.minutes_estimated,
            "minutes_used": self.minutes_used,
            "bucket_breakdown": self.bucket_breakdown,
            "created_at": self.created_at.isoformat(),
        }
        if self.hold_expires_at:
            item["hold_expires_at"] = self.hold_expires_at.isoformat()
        if self.finalized_at:
            item["finalized_at"] = self.finalized_at.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: Dict[str, Any]) -> "MinuteUsage":
        he = item.get("hold_expires_at")
        fa = item.get("finalized_at")
        return cls(
            id=item["id"],
            user_id=item["user_id"],
            job_id=item["job_id"],
            status=MinuteUsageStatus(item["status"]),
            minutes_estimated=item["minutes_estimated"],
            minutes_used=item.get("minutes_used"),
            bucket_breakdown=item.get("bucket_breakdown", []),
            hold_expires_at=datetime.fromisoformat(he) if he else None,
            created_at=datetime.fromisoformat(item["created_at"]),
            finalized_at=datetime.fromisoformat(fa) if fa else None,
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

