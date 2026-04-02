#!/usr/bin/env python3
"""
Script to add test minutes to a user by email.

Usage:
    python scripts/add_test_minutes.py <email> [minutes]

Examples:
    python scripts/add_test_minutes.py marc.medlockfr@gmail.com
    python scripts/add_test_minutes.py marc.medlockfr@gmail.com 500
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables from .env.dev
load_dotenv(os.path.join(project_root, ".env.dev"))

from media_summarizer.core.models.billing import MinuteBucket, MinuteBucketSource
from media_summarizer.utils import database_async, minute_db


async def add_minutes(email: str, minutes: int = 100):
    """Add minutes to a user by email."""

    print(f"Looking up user with email: {email}")

    # Find user by email
    user = await database_async.get_user_by_email(email)
    if not user:
        print(f"❌ User not found with email: {email}")
        sys.exit(1)

    print(f"✅ Found user: {user.id}")

    # Create a minute bucket
    now = datetime.now(timezone.utc)
    bucket_id = f"mb_{uuid.uuid4().hex[:16]}"
    bucket = MinuteBucket(
        id=bucket_id,
        user_id=user.id,
        source_type=MinuteBucketSource.pack,
        source_ref="test_pack",
        minutes_total=minutes,
        minutes_remaining=minutes,
        expires_at=now + timedelta(days=365),  # 1 year expiry
    )

    await minute_db.create_minute_bucket(bucket)

    print(f"✅ Added {minutes} minutes to user {email}")
    print(f"   User ID: {user.id}")
    print(f"   Bucket ID: {bucket.id}")
    print(f"   Expires: {bucket.expires_at}")

    # Show total available minutes
    from media_summarizer.core.services import minute_pool

    total = await minute_pool.get_total_available_minutes(user.id)
    print(f"\n📊 Total minutes now available: {total}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/add_test_minutes.py <email> [minutes]")
        print(
            "Example: python scripts/add_test_minutes.py marc.medlockfr@gmail.com 100"
        )
        sys.exit(1)

    email = sys.argv[1]
    minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 100

    asyncio.run(add_minutes(email, minutes))


if __name__ == "__main__":
    main()
