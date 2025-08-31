"""
Configuration module for Media Summarizer.

This module provides configuration settings for the application,
including support for test environments and E2E testing.
"""

import os
from typing import Optional


class Settings:
    """Application settings."""

    def __init__(self):
        # Environment
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
        self.DEBUG = os.getenv("DEBUG", "false").lower() == "true"

        # LocalStack configuration
        self.USE_LOCALSTACK = os.getenv("USE_LOCALSTACK", "true").lower() == "true"

        # AWS Configuration
        self.AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self.AWS_ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")

        # Database tables
        self.USERS_TABLE = os.getenv("USERS_TABLE", "users")
        self.MAGIC_LINKS_TABLE = os.getenv("MAGIC_LINKS_TABLE", "magic_links")
        self.TRANSACTIONS_TABLE = os.getenv("TRANSACTIONS_TABLE", "transactions")
        self.PODCASTS_TABLE = os.getenv("PODCASTS_TABLE", "podcasts")
        self.EPISODES_TABLE = os.getenv("EPISODES_TABLE", "episodes")

        # S3 Buckets
        self.AUDIO_BUCKET = os.getenv("AUDIO_BUCKET", "media-files")
        self.TRANSCRIPT_BUCKET = os.getenv("TRANSCRIPT_BUCKET", "transcripts")
        self.SUMMARY_BUCKET = os.getenv("SUMMARY_BUCKET", "summaries")

        # SQS Queues
        self.EMAIL_NOTIFICATION_QUEUE = os.getenv("EMAIL_NOTIFICATION_QUEUE", "email-notification-queue")
        self.DOWNLOAD_QUEUE = os.getenv("DOWNLOAD_QUEUE", "download-queue")
        self.TRANSCRIPTION_QUEUE = os.getenv("TRANSCRIPTION_QUEUE", "transcription-queue")
        self.SUMMARIZATION_QUEUE = os.getenv("SUMMARIZATION_QUEUE", "summarization-queue")

        # Stripe Configuration
        self.STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
        self.STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
        self.STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

        # JWT Configuration
        self.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "default-secret-key-for-development")
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

        # Email Configuration
        self.EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@example.com")
        self.FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

        # OpenAI Configuration
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

        # Podcast Index Configuration
        self.PODCASTINDEXORG_API_KEY = os.getenv("PODCASTINDEXORG_API_KEY", "")
        self.PODCASTINDEXORG_API_SECRET = os.getenv("PODCASTINDEXORG_API_SECRET", "")

        # Test Configuration
        self.TEST_ENVIRONMENT = os.getenv("TEST_ENVIRONMENT", "")
        self.E2E_CLEANUP = os.getenv("E2E_CLEANUP", "true").lower() == "true"
        self.ENABLE_MOCK_PROCESSING = os.getenv("ENABLE_MOCK_PROCESSING", "false").lower() == "true"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT == "development"

    @property
    def is_test(self) -> bool:
        """Check if running in test environment."""
        return self.ENVIRONMENT == "test"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT == "production"

    @property
    def is_e2e_test(self) -> bool:
        """Check if running E2E tests."""
        return self.TEST_ENVIRONMENT == "e2e"


# Global settings instance
settings = Settings()
