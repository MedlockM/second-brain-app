#!/usr/bin/env python3
"""
Fetch the latest active EMAIL_VERIFICATION token for a given user email from LocalStack DynamoDB.

Usage:
  uv run python scripts/dev_get_email_verification_token.py --email you@example.com
"""
from __future__ import annotations

import argparse
import asyncio
from typing import Optional

from media_summarizer.core.models.auth import TokenType
from media_summarizer.utils import database_async


async def get_token(email: str) -> Optional[str]:
    user = await database_async.get_user_by_email(email)
    if not user:
        print("User not found")
        return None
    tokens = await database_async.get_auth_tokens_by_user_id(user.id, TokenType.EMAIL_VERIFICATION)
    # pick an active (non-expired, not used) token if available; else latest
    active = [t for t in tokens if t.is_active and not t.is_expired() and t.used_at is None]
    token = active[0].token if active else (tokens[0].token if tokens else None)
    return token


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    token = asyncio.run(get_token(args.email))
    if token:
        print(token)


if __name__ == "__main__":
    main()