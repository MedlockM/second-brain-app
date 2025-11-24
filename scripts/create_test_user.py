#!/usr/bin/env python3
"""
Script pour créer un utilisateur test dans DynamoDB Local.
Usage: python create_test_user.py
"""
import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from media_summarizer.core.models.user import User
from media_summarizer.core.security import hash_password
from media_summarizer.utils import database_async
import asyncio


async def create_test_user():
    """Create a test user in DynamoDB."""
    
    # Test user credentials
    test_email = "test@example.com"
    test_password = "Test@1234"
    
    print(f"Creating test user: {test_email}")
    
    # Check if user already exists
    existing_user = await database_async.get_user_by_email(test_email)
    if existing_user:
        print(f"User {test_email} already exists!")
        print(f"User ID: {existing_user.id}")
        print(f"Email verified: {existing_user.email_verified_at is not None}")
        return existing_user
    
    # Create new user
    password_hashed = hash_password(test_password)
    
    user = User(
        email=test_email,
        password_hash=password_hashed,
        auth_provider="local",
        email_verified_at=datetime.now(timezone.utc),  # Mark as verified
        name="Test User"
    )
    
    # Save to DynamoDB
    created_user = await database_async.create_user(user)
    
    print(f"✅ Test user created successfully!")
    print(f"   Email: {created_user.email}")
    print(f"   Password: {test_password}")
    print(f"   User ID: {created_user.id}")
    print(f"   Email verified: {created_user.email_verified_at is not None}")
    print(f"\nYou can now login with:")
    print(f"   Email: {test_email}")
    print(f"   Password: {test_password}")
    
    return created_user


if __name__ == "__main__":
    asyncio.run(create_test_user())
