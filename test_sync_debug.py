import asyncio
import sys
import logging
sys.path.insert(0, '/app')

# Enable DEBUG logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("media_summarizer.core.services.tosum_sync")
logger.setLevel(logging.DEBUG)

from media_summarizer.utils import database_async
from media_summarizer.core.services.tosum_sync import run_tosum_sync_for_user

async def main():
    user = await database_async.get_user_by_id("ed410f59-ce59-40b2-bbe0-62a65cb4b3de")
    if not user:
        print("User not found")
        return
    
    print(f"User: {user.email}")
    result = await run_tosum_sync_for_user(user)
    print(f"\nSync result:")
    import json
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
