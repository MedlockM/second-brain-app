import asyncio
import sys
sys.path.insert(0, '/app')

from media_summarizer.utils import database_async
from media_summarizer.core.services.tosum_sync import run_tosum_sync_for_user

async def main():
    user = await database_async.get_user_by_id("ed410f59-ce59-40b2-bbe0-62a65cb4b3de")
    if not user:
        print("User not found")
        return
    
    print(f"User: {user.email}")
    print(f"Spotify linked: {bool(user.spotify_refresh_token)}")
    
    result = await run_tosum_sync_for_user(user)
    print(f"\nSync result:")
    import json
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
