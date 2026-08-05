"""
Package pour les modèles de domaine utilisant DynamoDB.
"""

# Import all DynamoDB models
from .auth import (
    AuthToken,
    AuthUser,
    LoginRequest,
    RegisterRequest,
    TokenType,
    TokenVerificationResponse,
)
from .billing import (
    Follow,
    Subscription,
    SubscriptionStatus,
    SubscriptionTier,
)
from .digest import (
    DigestMediaItem,
    DigestRecord,
    DigestStatus,
    DigestType,
    UserDigestSettings,
)
from .folder import MAX_FOLDER_DEPTH, UNCATEGORIZED_FOLDER_NAME, Folder
from .processing_job import JobStatus, ProcessingJob
from .review_schedule import CardState, ReviewScheduleRecord, UserReviewSettings
from .rss_feed import FeedStatus, UserRssFeed
from .tag import Tag
from .user import User

# Export all models
__all__ = [
    "User",
    "ProcessingJob",
    "JobStatus",
    "AuthToken",
    "TokenType",
    "TokenVerificationResponse",
    "AuthUser",
    "RegisterRequest",
    "LoginRequest",
    "Subscription",
    "SubscriptionStatus",
    "SubscriptionTier",
    "Follow",
    "Folder",
    "UNCATEGORIZED_FOLDER_NAME",
    "MAX_FOLDER_DEPTH",
    "ReviewScheduleRecord",
    "CardState",
    "UserReviewSettings",
    "UserRssFeed",
    "FeedStatus",
    "Tag",
    "DigestRecord",
    "DigestType",
    "DigestStatus",
    "DigestMediaItem",
    "UserDigestSettings",
]
