import asyncio
import sys
sys.path.insert(0, '/app')

from media_summarizer.utils import database_async
from media_summarizer.utils.spotify import ensure_access_token, find_playlist_by_name, list_playlist_episode_items, extract_spotify_episode_metadata

async def main():
    user = await database_async.get_user_by_id("ed410f59-ce59-40b2-bbe0-62a65cb4b3de")
    access_token = await ensure_access_token(user)
    playlist = await find_playlist_by_name(access_token, "Tosum")
    
    if not playlist:
        print("Playlist 'Tosum' not found")
        return
    
    items = await list_playlist_episode_items(access_token, playlist.get("id"))
    
    print(f"\n=== Playlist 'Tosum' ({len(items)} episodes) ===\n")
    
    for i, ep in enumerate(items, 1):
        ep_title, show_title, duration = extract_spotify_episode_metadata(ep)
        print(f"{i}. Show: {show_title}")
        print(f"   Episode: {ep_title}")
        print()

if __name__ == "__main__":
    asyncio.run(main())
