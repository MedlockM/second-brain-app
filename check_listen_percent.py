import asyncio
import sys
sys.path.insert(0, '/app')

from media_summarizer.utils import database_async
from media_summarizer.utils.spotify import (
    ensure_access_token, find_playlist_by_name, list_playlist_episode_items,
    extract_spotify_episode_metadata, get_episodes_details_map, compute_listen_percent
)

async def main():
    user = await database_async.get_user_by_id("ed410f59-ce59-40b2-bbe0-62a65cb4b3de")
    access_token = await ensure_access_token(user)
    playlist = await find_playlist_by_name(access_token, "Tosum")
    
    items = await list_playlist_episode_items(access_token, playlist.get("id"))
    ids = [ep.get("id") for ep in items if ep.get("id")]
    details_map = await get_episodes_details_map(access_token, ids)
    
    print(f"\n=== Listen percentages ===\n")
    
    for i, ep in enumerate(items[:5], 1):
        ep_id = ep.get("id")
        ep_title, show_title, duration = extract_spotify_episode_metadata(ep)
        
        if (not show_title) and ep_id and ep_id in details_map:
            show_title = (details_map[ep_id].get("show") or {}).get("name") or show_title
        
        # Add resume_point from details
        if ep_id and ep_id in details_map:
            rp = details_map[ep_id].get("resume_point")
            if rp:
                ep["resume_point"] = rp
        
        percent = compute_listen_percent(ep)
        print(f"{i}. {show_title} - {ep_title}")
        print(f"   Listen: {percent}%")
        print()

if __name__ == "__main__":
    asyncio.run(main())
