"""media_summarizer package.

Loads environment variables from a local .env file (if present) at import time
so every submodule that calls os.getenv() / os.environ.get() sees the same
values. In production (Lambda, ECS), real environment variables already exist
and override=False keeps them authoritative.
"""

from dotenv import load_dotenv

load_dotenv(override=False)
