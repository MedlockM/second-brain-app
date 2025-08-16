#!/usr/bin/env python3
"""
Database initialization CLI script for Media Summarizer.

This script provides command-line utilities for managing the DynamoDB database,
including initialization, health checks, and table management.
"""
import argparse
import asyncio
import logging
import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from media_summarizer.utils.database_async import (
    table_exists,
    USERS_TABLE,
    PODCASTS_TABLE,
    EPISODES_TABLE,
    CREDIT_TRANSACTIONS_TABLE,
    PROCESSING_JOBS_TABLE
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def cmd_init():
    """Initialize the database by creating all required tables."""
    logger.info("Starting database initialization...")
    try:
        # Note: Table creation is now handled by infrastructure setup
        # This function checks if tables exist
        tables = [
            USERS_TABLE,
            PODCASTS_TABLE,
            EPISODES_TABLE,
            CREDIT_TRANSACTIONS_TABLE,
            PROCESSING_JOBS_TABLE
        ]

        all_exist = True
        for table_name in tables:
            if not await table_exists(table_name):
                logger.warning(f"Table {table_name} does not exist")
                all_exist = False

        if all_exist:
            logger.info("✅ All tables exist - database initialization completed!")
        else:
            logger.error("❌ Some tables are missing. Please ensure LocalStack is running with proper table setup.")
            return False

        return True
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {str(e)}")
        return False


async def cmd_health():
    """Check the health of the database connection."""
    logger.info("Checking database health...")
    try:
        # Simple health check by trying to list tables
        from media_summarizer.utils.database_async import DynamoDBConnection

        db = DynamoDBConnection()
        client = await db.get_client()
        response = await client.list_tables()
        tables = response.get('TableNames', [])
        try:
            if hasattr(client, 'close'):
                if asyncio.iscoroutinefunction(client.close):
                    await client.close()
                else:
                    client.close()
        except Exception:
            pass  # Ignore close errors

        logger.info(f"✅ Database is healthy! Found {len(tables)} tables.")
        return True
    except Exception as e:
        logger.error(f"❌ Health check error: {str(e)}")
        return False


async def cmd_status():
    """Check the status of all required tables."""
    logger.info("Checking table status...")

    tables = [
        USERS_TABLE,
        PODCASTS_TABLE,
        EPISODES_TABLE,
        CREDIT_TRANSACTIONS_TABLE,
        PROCESSING_JOBS_TABLE
    ]

    table_status = {}
    all_exist = True

    for table_name in tables:
        try:
            exists = await table_exists(table_name)
            table_status[table_name] = exists
            if not exists:
                all_exist = False
        except Exception as e:
            logger.error(f"Error checking table {table_name}: {str(e)}")
            table_status[table_name] = False
            all_exist = False

    # Print status
    print("\n📊 Table Status Report:")
    print("=" * 50)
    for table_name, exists in table_status.items():
        status = "✅ EXISTS" if exists else "❌ MISSING"
        print(f"{table_name:25} {status}")

    print("=" * 50)
    if all_exist:
        print("✅ All required tables exist!")
        return True
    else:
        print("❌ Some tables are missing. Run 'init' to create them.")
        return False


async def cmd_create():
    """Create all tables (will skip existing ones)."""
    logger.info("Creating all tables...")
    try:
        logger.warning("Table creation is now handled by infrastructure setup.")
        logger.warning("Please ensure LocalStack is running with proper table configuration.")
        logger.info("Use 'status' command to check if tables exist.")
        return True
    except Exception as e:
        logger.error(f"❌ Table creation failed: {str(e)}")
        return False


async def cmd_reset():
    """Reset the database by recreating all tables (WARNING: destructive!)."""
    print("⚠️  WARNING: This will DELETE ALL DATA in the database!")
    print("This operation cannot be undone.")

    confirm = input("Type 'yes' to continue: ").strip().lower()
    if confirm != 'yes':
        print("Operation cancelled.")
        return True

    logger.info("Resetting database...")
    # Note: In a production environment, you would implement table deletion here
    # For LocalStack, it's easier to restart the container
    logger.warning("To reset LocalStack database, restart the LocalStack container:")
    logger.warning("docker-compose down && docker-compose up -d localstack")
    return True


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Media Summarizer Database Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/init_db.py init      # Initialize database
  python scripts/init_db.py health    # Check database health
  python scripts/init_db.py status    # Check table status
  python scripts/init_db.py create    # Create missing tables
  python scripts/init_db.py reset     # Reset database (destructive!)
        """
    )

    parser.add_argument(
        'command',
        choices=['init', 'health', 'status', 'create', 'reset'],
        help='Command to execute'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Check if required environment variables are set
    required_env_vars = ['AWS_ENDPOINT_URL', 'AWS_DEFAULT_REGION']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Make sure LocalStack is running and environment is configured.")
        sys.exit(1)

    # Execute the command
    command_map = {
        'init': cmd_init,
        'health': cmd_health,
        'status': cmd_status,
        'create': cmd_create,
        'reset': cmd_reset
    }

    try:
        success = asyncio.run(command_map[args.command]())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
