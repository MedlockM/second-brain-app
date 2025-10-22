import asyncio
import os
from datetime import datetime, timezone, timedelta

os.environ.setdefault("AWS_ENDPOINT_URL", "http://localhost:4566")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("USERS_TABLE", "users")

from media_summarizer.core.database import database_async

async def setup_user():
    user = await database_async.get_user_by_id("991e0f8f-427b-4f47-9848-148384108282")
    if not user:
        print("User not found")
        return
    
    # Mark email as verified
    user.email_verified_at = datetime.now(timezone.utc)
    
    # Add fake Spotify credentials (for testing)
    user.spotify_user_id = "test_spotify_user"
    user.spotify_access_token = "fake_access_token"
    user.spotify_refresh_token = "fake_refresh_token"
    user.spotify_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    user.spotify_scope = "user-read-playback-position playlist-read-private"
    
    await database_async.update_user(user)
    print(f"User updated: {user.email}")
    print(f"Email verified: {user.email_verified_at}")
    print(f"Spotify linked: {user.spotify_user_id}")

asyncio.run(setup_user())
