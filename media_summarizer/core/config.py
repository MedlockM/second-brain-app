"""
Configuration module for Media Summarizer.

Holds provider credentials, tunables and environment flags.

It deliberately holds NO AWS resource names. Table, queue and bucket names are
read through ``media_summarizer.utils.required_env`` at the point of use, so that
a missing name fails loudly instead of silently falling back to the dev
resource — which, with dev/staging/prod in one account, would mean one
environment writing into another's data (task-237).
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

        self.ARTIFACT_TYPES_ALLOWED = os.getenv(
            "ARTIFACT_TYPES_ALLOWED", "summary_short,summary_detailed,quiz,notes,flashcards"
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
        # task-216: the actor must accept a `language` input so the transcript
        # can be requested in the user's reading_language.
        self.APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID = os.getenv(
            "APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID", "starvibe~youtube-video-transcript"
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

        # Podcast Index Configuration
        self.PODCASTINDEXORG_API_KEY = os.getenv("PODCASTINDEXORG_API_KEY", "")
        self.PODCASTINDEXORG_API_SECRET = os.getenv("PODCASTINDEXORG_API_SECRET", "")

        # Algolia Configuration (Search)
        self.ALGOLIA_APP_ID = os.getenv("ALGOLIA_APP_ID", "")
        self.ALGOLIA_API_KEY = os.getenv("ALGOLIA_API_KEY", "")
        self.ALGOLIA_SEARCH_API_KEY = os.getenv("ALGOLIA_SEARCH_API_KEY", "")

        # Pricing Configuration
        self.PRICING_ADMIN_SECRET = os.getenv("PRICING_ADMIN_SECRET", "")

        # RevenueCat Configuration
        self.REVENUCAT_API_KEY = os.getenv("REVENUCAT_API_KEY", "")
        self.REVENUCAT_WEBHOOK_SECRET = os.getenv("REVENUCAT_WEBHOOK_SECRET", "")
        self.REVENUCAT_PROJECT_ID = os.getenv("REVENUCAT_PROJECT_ID", "")

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
