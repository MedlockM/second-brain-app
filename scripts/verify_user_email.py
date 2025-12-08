#!/usr/bin/env python3
"""
Script to manually verify a user's email address in the database.
Useful for testing when email service is not configured.
"""
import asyncio
import sys
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, '/home/marc-medlock/Perso/media-summarizer-project-kiro/media-summarizer-project')

from media_summarizer.utils import database_async


async def verify_user_email(email: str):
    """Verify a user's email by setting email_verified_at timestamp."""
    print(f"Looking for user with email: {email}")
    
    user = await database_async.get_user_by_email(email)
    
    if not user:
        print(f"❌ User not found: {email}")
        return False
    
    print(f"✅ Found user: {user.id}")
    print(f"   Email: {user.email}")
    print(f"   Provider: {user.auth_provider}")
    print(f"   Email verified: {user.email_verified_at is not None}")
    
    if user.email_verified_at:
        print(f"   ⚠️  Email already verified at: {user.email_verified_at}")
        return True
    
    # Set email_verified_at to now
    user.email_verified_at = datetime.now(timezone.utc)
    await database_async.update_user(user)
    
    print(f"   ✅ Email verified successfully at: {user.email_verified_at}")
    return True


async def main():
    if len(sys.argv) < 2:
        print("Usage: python verify_user_email.py <email>")
        print("Example: python verify_user_email.py newtest@example.com")
        sys.exit(1)
    
    email = sys.argv[1].lower().strip()
    success = await verify_user_email(email)
    
    if success:
        print("\n✅ Done! User can now log in and make payments.")
    else:
        print("\n❌ Failed to verify user email.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
