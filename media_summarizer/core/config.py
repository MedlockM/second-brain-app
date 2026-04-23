"""
Configuration module for Media Summarizer.

This module provides configuration settings for the application,
including support for test environments and E2E testing.
"""

import os


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
        self.SUMMARY_SHORT_BUCKET = os.getenv("SUMMARY_SHORT_BUCKET", "media-summarizer-summaries-short")
        self.SUMMARY_DETAILED_BUCKET = os.getenv("SUMMARY_DETAILED_BUCKET", "media-summarizer-summaries-detailed")
        self.QUIZ_BUCKET = os.getenv("QUIZ_BUCKET", "media-summarizer-quizzes")
        self.NOTES_BUCKET = os.getenv("NOTES_BUCKET", "media-summarizer-notes")
        self.FLASHCARDS_BUCKET = os.getenv("FLASHCARDS_BUCKET", "media-summarizer-flashcards")

        # SQS Queues
        self.DOWNLOAD_QUEUE = os.getenv("DOWNLOAD_QUEUE", "download-queue")
        self.TRANSCRIPTION_QUEUE = os.getenv("TRANSCRIPTION_QUEUE", "transcription-queue")
        self.DEEPGRAM_TRANSCRIPTION_QUEUE = os.getenv(
            "DEEPGRAM_TRANSCRIPTION_QUEUE", "deepgram-transcription-queue"
        )
        self.YOUTUBE_INGESTION_QUEUE = os.getenv(
            "YOUTUBE_INGESTION_QUEUE", "youtube-ingestion-queue"
        )
        self.TIKTOK_INGESTION_QUEUE = os.getenv(
            "TIKTOK_INGESTION_QUEUE", "tiktok-ingestion-queue"
        )
        self.SUMMARIZATION_QUEUE = os.getenv("SUMMARIZATION_QUEUE", "summarization-queue")
        self.SUMMARY_SHORT_QUEUE = os.getenv("SUMMARY_SHORT_QUEUE", "summary-short-queue")
        self.SUMMARY_DETAILED_QUEUE = os.getenv("SUMMARY_DETAILED_QUEUE", "summary-detailed-queue")
        self.QUIZ_QUEUE = os.getenv("QUIZ_QUEUE", "quiz-queue")
        self.NOTES_QUEUE = os.getenv("NOTES_QUEUE", "notes-queue")
        self.FLASHCARDS_QUEUE = os.getenv("FLASHCARDS_QUEUE", "flashcards-queue")
        self.ARTIFACT_TYPES_ALLOWED = os.getenv(
            "ARTIFACT_TYPES_ALLOWED", "summary,summary_short,summary_detailed,quiz,notes,flashcards"
        )

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

        # Deepgram Configuration
        self.DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
        self.DEEPGRAM_API_URL = os.getenv(
            "DEEPGRAM_API_URL", "https://api.deepgram.com/v1/listen"
        )
        self.DEEPGRAM_MODEL = os.getenv("DEEPGRAM_MODEL", "nova-3")
        self.DEEPGRAM_TIMEOUT_SECONDS = int(
            os.getenv("DEEPGRAM_TIMEOUT_SECONDS", "300")
        )
        self.YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS = float(
            os.getenv("YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS", "20")
        )
        self.YTDLP_TIMEOUT_SECONDS = float(
            os.getenv("YTDLP_TIMEOUT_SECONDS", "30")
        )
        self.GETINSAVER_API_BASE_URL = os.getenv(
            "GETINSAVER_API_BASE_URL", "https://getinsaver.com/api/v1"
        )
        self.GETINSAVER_API_KEY = os.getenv("GETINSAVER_API_KEY", "")
        self.GETINSAVER_TIMEOUT_SECONDS = int(
            os.getenv("GETINSAVER_TIMEOUT_SECONDS", "20")
        )

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
