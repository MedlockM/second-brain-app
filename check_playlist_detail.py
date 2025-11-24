import asyncio
import sys
sys.path.insert(0, '/app')

from media_summarizer.utils import database_async
from media_summarizer.utils.spotify import ensure_access_token, find_playlist_by_name, list_playlist_episode_items, extract_spotify_episode_metadata, get_episodes_details_map

async def main():
    user = await database_async.get_user_by_id("ed410f59-ce59-40b2-bbe0-62a65cb4b3de")
    access_token = await ensure_access_token(user)
    playlist = await find_playlist_by_name(access_token, "Tosum")
    
    items = await list_playlist_episode_items(access_token, playlist.get("id"))
    
    # Get details
    ids = [ep.get("id") for ep in items if ep.get("id")]
    details_map = await get_episodes_details_map(access_token, ids)
    
    print(f"\n=== First 3 episodes with details ===\n")
    
    for i, ep in enumerate(items[:3], 1):
        ep_id = ep.get("id")
        ep_title, show_title, duration = extract_spotify_episode_metadata(ep)
        
        # Get show from details if missing
        if (not show_title) and ep_id and ep_id in details_map:
            show_title = (details_map[ep_id].get("show") or {}).get("name") or show_title
        
        print(f"{i}. Episode ID: {ep_id}")
        print(f"   Episode Title: {ep_title}")
        print(f"   Show Title: {show_title}")
        print()

if __name__ == "__main__":
    asyncio.run(main())
