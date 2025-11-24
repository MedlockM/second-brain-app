"""Database operations for Spotify playlist follows."""
from typing import List, Optional
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
import os
from datetime import datetime, timezone

from media_summarizer.core.models.spotify import SpotifyPlaylistFollow
from media_summarizer.utils import database_async

TABLE_NAME = os.environ.get("SPOTIFY_PLAYLIST_FOLLOWS_TABLE", "spotify_playlist_follows")


async def get_follows_by_user(user_id: str) -> List[SpotifyPlaylistFollow]:
    """Get all playlist follows for a user."""
    session = database_async.get_session()
    async with session.resource('dynamodb', endpoint_url=database_async.AWS_ENDPOINT_URL, region_name=database_async.AWS_REGION) as dynamodb:
        table = await dynamodb.Table(TABLE_NAME)
        response = await table.query(
            KeyConditionExpression=Key('user_id').eq(user_id)
        )
        items = response.get('Items', [])
        return [SpotifyPlaylistFollow.from_dynamodb_item(it) for it in items]


async def upsert_follow(follow: SpotifyPlaylistFollow) -> SpotifyPlaylistFollow:
    """Create or update a playlist follow."""
    follow.updated_at = datetime.now(timezone.utc)
    
    session = database_async.get_session()
    async with session.resource('dynamodb', endpoint_url=database_async.AWS_ENDPOINT_URL, region_name=database_async.AWS_REGION) as dynamodb:
        table = await dynamodb.Table(TABLE_NAME)
        await table.put_item(Item=follow.to_dynamodb_item())
        return follow


async def get_follow(user_id: str, playlist_id: str) -> Optional[SpotifyPlaylistFollow]:
    """Get a specific playlist follow."""
    session = database_async.get_session()
    async with session.resource('dynamodb', endpoint_url=database_async.AWS_ENDPOINT_URL, region_name=database_async.AWS_REGION) as dynamodb:
        table = await dynamodb.Table(TABLE_NAME)
        try:
            response = await table.get_item(Key={"user_id": user_id, "playlist_id": playlist_id})
            item = response.get('Item')
            return SpotifyPlaylistFollow.from_dynamodb_item(item) if item else None
        except ClientError:
            return None


async def delete_follow(user_id: str, playlist_id: str) -> bool:
    """Delete a playlist follow."""
    session = database_async.get_session()
    async with session.resource('dynamodb', endpoint_url=database_async.AWS_ENDPOINT_URL, region_name=database_async.AWS_REGION) as dynamodb:
        table = await dynamodb.Table(TABLE_NAME)
        try:
            await table.delete_item(Key={"user_id": user_id, "playlist_id": playlist_id})
            return True
        except ClientError:
            return False
