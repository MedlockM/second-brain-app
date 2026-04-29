"""
Conftest for document parsing worker tests.

Mocks missing modules to avoid import errors when loading the worker
(which transitively imports media_summarizer.utils and base_worker).
"""

import sys
from unittest.mock import MagicMock

# Create mocks for missing modules before any import tries to load them
_MISSING_MODULES = [
    "media_summarizer.utils.podcastindex_limiter",
    "media_summarizer.utils.user_facing_errors",
]

for mod_name in _MISSING_MODULES:
    if mod_name not in sys.modules:
        mock_mod = MagicMock()
        if "user_facing_errors" in mod_name:
            mock_mod.get_user_facing_error_message = MagicMock(return_value="An error occurred")
        sys.modules[mod_name] = mock_mod
