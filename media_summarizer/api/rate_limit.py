"""
Centralized rate limiting configuration and helpers.
"""
import os
from slowapi import Limiter
from slowapi.util import get_remote_address


def _normalize_limit(value: str | None, default: str) -> str:
    v = (value or default).strip()
    if "/" not in v:
        # Interpret lone numeric as per-minute
        v = f"{v}/minute"
    return v


# Global limiter instance with env-driven default
DEFAULT_RATE = _normalize_limit(os.environ.get("RATE_LIMIT_PER_MINUTE", "60/minute"), "60/minute")
limiter = Limiter(key_func=get_remote_address, default_limits=[DEFAULT_RATE])


def get_limit_from_env(var_name: str, default: str) -> str:
    """Return a normalized rate limit string from env or default (e.g. "10/minute")."""
    return _normalize_limit(os.environ.get(var_name), default)

