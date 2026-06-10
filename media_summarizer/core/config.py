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

        # AWS Configuration
        self.AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-3")

        # Database tables
        self.USERS_TABLE = os.getenv("USERS_TABLE", "users")
        self.TRANSACTIONS_TABLE = os.getenv("TRANSACTIONS_TABLE", "transactions")
        self.PODCASTS_TABLE = os.getenv("PODCASTS_TABLE", "podcasts")
        self.EPISODES_TABLE = os.getenv("EPISODES_TABLE", "episodes")

        # S3 Buckets
        self.AUDIO_BUCKET = os.getenv("AUDIO_BUCKET", "media-summarizer-audio")
        self.TRANSCRIPT_BUCKET = os.getenv("TRANSCRIPT_BUCKET", "media-summarizer-transcripts")
        self.SUMMARY_BUCKET = os.getenv("SUMMARY_BUCKET", "media-summarizer-summaries")
        self.SUMMARY_SHORT_BUCKET = os.getenv("SUMMARY_SHORT_BUCKET", "media-summarizer-summary-short")
        self.SUMMARY_DETAILED_BUCKET = os.getenv("SUMMARY_DETAILED_BUCKET", "media-summarizer-summary-detailed")
        self.QUIZ_BUCKET = os.getenv("QUIZ_BUCKET", "media-summarizer-quiz")
        self.NOTES_BUCKET = os.getenv("NOTES_BUCKET", "media-summarizer-notes")
        self.FLASHCARDS_BUCKET = os.getenv("FLASHCARDS_BUCKET", "media-summarizer-flashcards")

        # SQS Queues
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
        self.NEWSLETTER_INGESTION_QUEUE = os.getenv(
            "NEWSLETTER_INGESTION_QUEUE", "newsletter-ingestion-queue"
        )
        self.ARTIFACT_TYPES_ALLOWED = os.getenv(
            "ARTIFACT_TYPES_ALLOWED", "summary,summary_short,summary_detailed,quiz,notes,flashcards"
        )


        # JWT Configuration
        self.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "default-secret-key-for-development")
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

        # Frontend Configuration
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
        self.APIFY_INSTAGRAM_API_TOKEN = os.getenv("APIFY_INSTAGRAM_API_TOKEN", "")
        self.APIFY_YOUTUBE_API_TOKEN = os.getenv("APIFY_YOUTUBE_API_TOKEN", "")
        self.APIFY_INSTAGRAM_REEL_ACTOR_ID = os.getenv(
            "APIFY_INSTAGRAM_REEL_ACTOR_ID", "khadinakbar~video-subtitle-extractor"
        )
        self.APIFY_INSTAGRAM_POST_ACTOR_ID = os.getenv(
            "APIFY_INSTAGRAM_POST_ACTOR_ID", "apify~instagram-post-scraper"
        )
        self.APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID = os.getenv(
            "APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID",
            "scrape-creators~best-youtube-transcripts-scraper",
        )
        self.APIFY_TIMEOUT_SECONDS = int(
            os.getenv("APIFY_TIMEOUT_SECONDS", "60")
        )
        self.APIFY_POLL_INTERVAL_SECONDS = float(
            os.getenv("APIFY_POLL_INTERVAL_SECONDS", "3")
        )
        self.APIFY_MAX_POLLS = int(
            os.getenv("APIFY_MAX_POLLS", "40")
        )

        # Document Parsing Configuration
        self.LLAMAPARSE_API_KEY = os.getenv("LLAMAPARSE_API_KEY", "")
        self.LLAMAPARSE_TIMEOUT_SECONDS = int(os.getenv("LLAMAPARSE_TIMEOUT_SECONDS", "120"))
        self.UNSTRUCTURED_API_KEY = os.getenv("UNSTRUCTURED_API_KEY", "")
        self.UNSTRUCTURED_API_URL = os.getenv(
            "UNSTRUCTURED_API_URL", "https://api.unstructuredapp.io"
        )
        self.UNSTRUCTURED_TIMEOUT_SECONDS = int(os.getenv("UNSTRUCTURED_TIMEOUT_SECONDS", "120"))
        self.DOCUMENT_BUCKET = os.getenv("DOCUMENT_BUCKET", "media-summarizer-documents")
        self.DOCUMENT_PARSING_QUEUE = os.getenv("DOCUMENT_PARSING_QUEUE", "document-parsing-queue")

        # Podcast Index Configuration
        self.PODCASTINDEXORG_API_KEY = os.getenv("PODCASTINDEXORG_API_KEY", "")
        self.PODCASTINDEXORG_API_SECRET = os.getenv("PODCASTINDEXORG_API_SECRET", "")

        # Algolia Configuration (Search)
        self.ALGOLIA_APP_ID = os.getenv("ALGOLIA_APP_ID", "")
        self.ALGOLIA_API_KEY = os.getenv("ALGOLIA_API_KEY", "")
        self.ALGOLIA_INDEX_NAME = os.getenv("ALGOLIA_INDEX_NAME", "transcripts")
        self.SEARCH_INDEXING_QUEUE = os.getenv("SEARCH_INDEXING_QUEUE", "search-indexing-queue")

        # Pricing Configuration
        self.PRICING_CONFIG_TABLE = os.getenv("PRICING_CONFIG_TABLE", "pricing_config")
        self.PRICING_ADMIN_SECRET = os.getenv("PRICING_ADMIN_SECRET", "")

        # RevenueCat Configuration
        self.REVENUCAT_API_KEY = os.getenv("REVENUCAT_API_KEY", "")
        self.REVENUCAT_WEBHOOK_SECRET = os.getenv("REVENUCAT_WEBHOOK_SECRET", "")
        self.REVENUCAT_PROJECT_ID = os.getenv("REVENUCAT_PROJECT_ID", "")
        self.REVENUCAT_EVENTS_TABLE = os.getenv("REVENUCAT_EVENTS_TABLE", "revenucat_events")

        # Apify TikTok Configuration
        self.APIFY_TIKTOK_API_TOKEN = os.getenv("APIFY_TIKTOK_API_TOKEN", "")
        self.APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID = os.getenv(
            "APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID", ""
        )
        self.APIFY_TIKTOK_TIMEOUT_SECONDS = float(
            os.getenv("APIFY_TIKTOK_TIMEOUT_SECONDS", "60")
        )
        self.APIFY_TIKTOK_POLL_INTERVAL_SECONDS = float(
            os.getenv("APIFY_TIKTOK_POLL_INTERVAL_SECONDS", "3")
        )
        self.APIFY_TIKTOK_MAX_POLLS = int(
            os.getenv("APIFY_TIKTOK_MAX_POLLS", "40")
        )

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
