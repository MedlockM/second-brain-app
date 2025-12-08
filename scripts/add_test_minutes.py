import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

# Add project to path
sys.path.insert(0, '/app')

os.environ.setdefault('AWS_ENDPOINT_URL', 'http://localstack:4566')
os.environ.setdefault('AWS_REGION', 'us-east-1')

from media_summarizer.utils import minute_db
from media_summarizer.models.minute_bucket import MinuteBucket

async def add_minutes():
    user_id = "30424132-e794-4f3f-a859-052aa0c52c1d"
    
    # Create a minute bucket with 100 minutes
    bucket = MinuteBucket(
        user_id=user_id,
        minutes_total=100,
        minutes_remaining=100,
        source="test_pack",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        created_at=datetime.now(timezone.utc)
    )
    
    await minute_db.create_minute_bucket(bucket)
    print(f"✅ Added 100 minutes to user {user_id}")
    print(f"   Bucket ID: {bucket.id}")
    print(f"   Expires: {bucket.expires_at}")

if __name__ == "__main__":
    asyncio.run(add_minutes())
