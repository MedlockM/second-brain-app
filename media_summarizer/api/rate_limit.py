"""
Rate limiting compatibility shim.

In the Lambda-only architecture, rate limiting is handled by API Gateway
throttling (per-route, per-stage). This module provides a no-op limiter
so existing endpoint decorators (@limiter.limit(...)) remain valid without
requiring the slowapi/redis dependencies.
"""

import os


def _normalize_limit(value: str | None, default: str) -> str:
    v = (value or default).strip()
    if "/" not in v:
        v = f"{v}/minute"
    return v


def get_limit_from_env(var_name: str, default: str) -> str:
    """Return a normalized rate limit string from env or default (e.g. "10/minute")."""
    return _normalize_limit(os.environ.get(var_name), default)


class _NoOpLimiter:
    """A limiter that does nothing -- all rate enforcement is at the API Gateway layer."""

    def limit(self, *args, **kwargs):
        """Return a no-op decorator."""
        def decorator(func):
            return func
        return decorator


limiter = _NoOpLimiter()
