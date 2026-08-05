"""
Package pour les modèles de domaine utilisant DynamoDB.
"""

# Import all DynamoDB models
from .user import User
from .processing_job import ProcessingJob, JobStatus
from .auth import (
    AuthToken,
    TokenType,
    TokenVerificationResponse,
    AuthUser,
    RegisterRequest,
    LoginRequest,
)
from .billing import (
    Subscription,
    SubscriptionStatus,
    SubscriptionTier,
    Follow,
)
from .folder import Folder, UNCATEGORIZED_FOLDER_NAME, MAX_FOLDER_DEPTH
from .review_schedule import ReviewScheduleRecord, CardState, UserReviewSettings
from .rss_feed import UserRssFeed, FeedStatus
from .tag import Tag
from .digest import (
    DigestRecord,
    DigestType,
    DigestStatus,
    DigestMediaItem,
    UserDigestSettings,
)

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
