"""
Core constants for the media-summarizer application.

Centralized definitions of application-wide constants to avoid magic numbers
and duplicated values across the codebase.
"""

# ---------------------------------------------------------------------------
# Tag limits
# ---------------------------------------------------------------------------

# Maximum number of tags that can be attached to a single media item.
# Keeps the tagging system manageable and prevents abuse.
MAX_TAGS_PER_MEDIA: int = 20

# Default color (hex) applied to newly created tags when no color is chosen.
DEFAULT_TAG_COLOR: str = "#808080"
