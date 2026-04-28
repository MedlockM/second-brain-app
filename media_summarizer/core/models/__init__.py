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
    EmailVerificationRequest,
)
from .billing import (
    Subscription,
    SubscriptionStatus,
    SubscriptionTier,
    MinuteBucket,
    MinuteBucketSource,
    MinuteUsage,
    MinuteUsageStatus,
    Follow,
)
from .folder import Folder, UNCATEGORIZED_FOLDER_NAME, MAX_FOLDER_DEPTH
from .tag import Tag

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
    "EmailVerificationRequest",
    "Subscription",
    "SubscriptionStatus",
    "SubscriptionTier",
    "MinuteBucket",
    "MinuteBucketSource",
    "MinuteUsage",
    "MinuteUsageStatus",
    "Follow",
    "Folder",
    "UNCATEGORIZED_FOLDER_NAME",
    "MAX_FOLDER_DEPTH",
    "Tag",
]
