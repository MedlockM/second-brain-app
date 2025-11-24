import asyncio
import sys
sys.path.insert(0, '/app')

from media_summarizer.utils import database_async
from media_summarizer.utils.spotify import (
    ensure_access_token, find_playlist_by_name, list_playlist_episode_items,
    extract_spotify_episode_metadata
)

async def main():
    user = await database_async.get_user_by_id("ed410f59-ce59-40b2-bbe0-62a65cb4b3de")
    access_token = await ensure_access_token(user)
    playlist = await find_playlist_by_name(access_token, "Tosum")
    
    items = await list_playlist_episode_items(access_token, playlist.get("id"))
    
    print(f"\n=== Exact Spotify titles (first 12) ===\n")
    
    for i, ep in enumerate(items[:12], 1):
        ep_title, show_title, duration = extract_spotify_episode_metadata(ep)
        print(f"{i}. Title repr: {repr(ep_title)}")
        print(f"   Title bytes: {ep_title.encode('utf-8')}")
        print()

if __name__ == "__main__":
    asyncio.run(main())
