#!/usr/bin/env python3
"""
Script to reset a user's minutes to 0 by deleting all their minute buckets.

Usage:
    python scripts/reset_user_minutes.py <email>

Examples:
    python scripts/reset_user_minutes.py marc.medlockfr@gmail.com
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Load environment variables from .env.dev
load_dotenv(os.path.join(project_root, ".env.dev"))

from media_summarizer.utils import database_async, minute_db


async def reset_minutes(email: str):
    """Reset minutes for a user by email."""

    print(f"Looking up user with email: {email}")

    # Find user by email
    user = await database_async.get_user_by_email(email)
    if not user:
        print(f"❌ User not found with email: {email}")
        sys.exit(1)

    print(f"✅ Found user: {user.id}")

    # Get all minute buckets for the user
    buckets = await minute_db.get_minute_buckets_by_user_id(user.id)

    if not buckets:
        print(f"ℹ️ User already has 0 minutes (no buckets found).")
    else:
        print(f"🗑️ Found {len(buckets)} minute buckets. Deleting...")

        deleted_count = 0
        for bucket in buckets:
            success = await minute_db.delete_minute_bucket(bucket.id)
            if success:
                deleted_count += 1
            else:
                print(f"  ⚠️ Failed to delete bucket {bucket.id}")

        print(f"✅ Successfully deleted {deleted_count} buckets.")

    # Show total available minutes (should be 0)
    from media_summarizer.core.services import minute_pool

    total = await minute_pool.get_total_available_minutes(user.id)
    print(f"\n📊 Total minutes now available: {total}")

    if total == 0:
        print("✨ User minutes successfully reset to 0.")
    else:
        print(
            "⚠️ Warning: Total minutes is still not 0. There might be active subscriptions or other sources."
        )


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/reset_user_minutes.py <email>")
        print("Example: python scripts/reset_user_minutes.py marc.medlockfr@gmail.com")
        sys.exit(1)

    email = sys.argv[1]

    asyncio.run(reset_minutes(email))


if __name__ == "__main__":
    main()
