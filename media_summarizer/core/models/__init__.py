"""
Package pour les modèles de domaine utilisant DynamoDB.
"""

# Import all DynamoDB models
from .user import User
from .processing_job import ProcessingJob, JobStatus
from .auth import AuthToken, TokenType, TokenVerificationResponse, AuthUser, RegisterRequest, LoginRequest, EmailVerificationRequest

# Export all models
__all__ = [
    'User',
    'ProcessingJob',
    'JobStatus',
    'AuthToken',
    'TokenType',
    'TokenVerificationResponse',
    'AuthUser',
    'RegisterRequest',
    'LoginRequest',
    'EmailVerificationRequest'
]
