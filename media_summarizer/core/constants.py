"""
Core constants for the media-summarizer application.

Centralized definitions of application-wide constants to avoid magic numbers
and duplicated values across the codebase.
"""

# ---------------------------------------------------------------------------
# Folder limits
# ---------------------------------------------------------------------------

# Maximum number of folders a single user can create.
# Prevents excessive resource usage and keeps the UI navigable.
MAX_FOLDERS_PER_USER: int = 50

# Default folder name assigned when no explicit folder is specified.
DEFAULT_FOLDER_NAME: str = "Uncategorized"
