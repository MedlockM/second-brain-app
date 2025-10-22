"""
Database utilities for integration testing with DynamoDB.

This module provides utilities for setting up and using DynamoDB tables
for integration testing using LocalStack.
"""

import pytest
from typing import Dict, Any, List
from uuid import uuid4
from datetime import datetime

from media_summarizer.utils.database_async import (
    DynamoDBConnection,
    table_exists,
    USERS_TABLE,
    PODCASTS_TABLE,
    EPISODES_TABLE,
    CREDIT_TRANSACTIONS_TABLE,
    PROCESSING_JOBS_TABLE,
)
from media_summarizer.core.models import (
    User,
    Podcast,
    Episode,
    CreditTransaction,
    ProcessingJob,
    JobStatus,
)


async def create_test_tables():
    """
    Create all DynamoDB tables for testing.
    """
    # Note: Table creation is handled by the infrastructure setup
    # This function is kept for compatibility but tables should exist
    pass


async def clear_all_tables(db_connection: DynamoDBConnection):
    """
    Clear all data from test tables.

    Args:
        db_connection: DynamoDB connection instance
    """
    table_names = [
        USERS_TABLE,
        PODCASTS_TABLE,
        EPISODES_TABLE,
        CREDIT_TRANSACTIONS_TABLE,
        PROCESSING_JOBS_TABLE,
    ]

    async with await db_connection.get_resource() as dynamodb:
        for table_name in table_names:
            table = await dynamodb.Table(table_name)

            # Scan all items and delete them
            try:
                response = await table.scan()
                items = response.get("Items", [])

                for item in items:
                    # Get the primary key for deletion
                    key = {"id": item["id"]}
                    await table.delete_item(Key=key)
            except Exception as e:
                # Table might not exist, which is fine for tests
                pass


async def populate_test_data(db_connection: DynamoDBConnection):
    """
    Populate test tables with sample data.

    Args:
        db_connection: DynamoDB connection instance
    """
    async with await db_connection.get_resource() as dynamodb:
        # Create test users
        users_table = await dynamodb.Table(USERS_TABLE)
        test_users = [
            {
                "id": "test-user-id",
                "email": "user@example.com",
                "credits": 100,
                "created_at": datetime.now().isoformat(),
            },
            {
                "id": "test-user-id-2",
                "email": "user2@example.com",
                "credits": 50,
                "created_at": datetime.now().isoformat(),
            },
        ]

        for user_data in test_users:
            await users_table.put_item(Item=user_data)

        # Create test podcasts
        podcasts_table = await dynamodb.Table(PODCASTS_TABLE)
        test_podcasts = [
            {
                "id": "test-podcast-id",
                "title": "Test Podcast",
                "rss_url": "https://example.com/podcast.rss",
                "created_at": datetime.now().isoformat(),
            }
        ]

        for podcast_data in test_podcasts:
            await podcasts_table.put_item(Item=podcast_data)

        # Create test episodes
        episodes_table = await dynamodb.Table(EPISODES_TABLE)
        test_episodes = [
            {
                "id": "test-episode-id",
                "podcast_id": "test-podcast-id",
                "title": "Test Episode",
                "audio_url": "https://example.com/episode.mp3",
                "duration": 3600,
                "created_at": datetime.now().isoformat(),
            }
        ]

        for episode_data in test_episodes:
            await episodes_table.put_item(Item=episode_data)

        # Create test jobs
        jobs_table = await dynamodb.Table(PROCESSING_JOBS_TABLE)
        test_jobs = [
            {
                "id": "test-job-id",
                "user_id": "test-user-id",
                "user_email": "user@example.com",
                "episode_id": "test-episode-id",
                "status": "completed",
                "retry_count": 0,
                "created_at": datetime.now().isoformat(),
            }
        ]

        for job_data in test_jobs:
            await jobs_table.put_item(Item=job_data)

        # Create test credit transactions
        transactions_table = await dynamodb.Table(CREDIT_TRANSACTIONS_TABLE)
        test_transactions = [
            {
                "id": "test-txn-id",
                "user_id": "test-user-id",
                "amount": 100,
                "type": "purchase",
                "description": "Initial credit purchase",
                "created_at": datetime.now().isoformat(),
            }
        ]

        for transaction_data in test_transactions:
            await transactions_table.put_item(Item=transaction_data)


def create_test_user(
    user_id: str = None, email: str = None, credits: int = 100
) -> User:
    """
    Create a test user instance.

    Args:
        user_id: User ID (auto-generated if not provided)
        email: User email (auto-generated if not provided)
        credits: Initial credits

    Returns:
        User instance
    """
    if user_id is None:
        user_id = str(uuid4())
    if email is None:
        email = f"test-{user_id[:8]}@example.com"

    return User(id=user_id, email=email, credits=credits)


def create_test_podcast(
    podcast_id: str = None, title: str = None, rss_url: str = None
) -> Podcast:
    """
    Create a test podcast instance.

    Args:
        podcast_id: Podcast ID (auto-generated if not provided)
        title: Podcast title
        rss_url: RSS feed URL

    Returns:
        Podcast instance
    """
    if podcast_id is None:
        podcast_id = str(uuid4())
    if title is None:
        title = f"Test Podcast {podcast_id[:8]}"
    if rss_url is None:
        rss_url = f"https://example.com/podcast-{podcast_id[:8]}.rss"

    return Podcast(id=podcast_id, title=title, rss_url=rss_url)


def create_test_episode(
    episode_id: str = None,
    podcast_id: str = None,
    title: str = None,
    audio_url: str = None,
    duration: int = 3600,
) -> Episode:
    """
    Create a test episode instance.

    Args:
        episode_id: Episode ID (auto-generated if not provided)
        podcast_id: Podcast ID (auto-generated if not provided)
        title: Episode title
        audio_url: Audio file URL
        duration: Episode duration in seconds

    Returns:
        Episode instance
    """
    if episode_id is None:
        episode_id = str(uuid4())
    if podcast_id is None:
        podcast_id = str(uuid4())
    if title is None:
        title = f"Test Episode {episode_id[:8]}"
    if audio_url is None:
        audio_url = f"https://example.com/episode-{episode_id[:8]}.mp3"

    return Episode(
        id=episode_id,
        podcast_id=podcast_id,
        title=title,
        audio_url=audio_url,
        duration=duration,
    )


def create_test_credit_transaction(
    transaction_id: str = None,
    user_id: str = None,
    amount: int = 10,
    transaction_type: str = "purchase",
    description: str = None,
) -> CreditTransaction:
    """
    Create a test credit transaction instance.

    Args:
        transaction_id: Transaction ID (auto-generated if not provided)
        user_id: User ID (auto-generated if not provided)
        amount: Transaction amount
        transaction_type: Type of transaction (purchase, deduction, refund)
        description: Transaction description

    Returns:
        CreditTransaction instance
    """
    if transaction_id is None:
        transaction_id = str(uuid4())
    if user_id is None:
        user_id = str(uuid4())
    if description is None:
        description = f"Test {transaction_type} transaction"

    return CreditTransaction(
        id=transaction_id,
        user_id=user_id,
        amount=amount,
        type=transaction_type,
        description=description,
    )


def create_test_processing_job(
    job_id: str = None,
    user_id: str = None,
    user_email: str = None,
    episode_id: str = None,
    status: JobStatus = JobStatus.PENDING,
) -> ProcessingJob:
    """
    Create a test processing job instance.

    Args:
        job_id: Job ID (auto-generated if not provided)
        user_id: User ID (auto-generated if not provided)
        user_email: User email (auto-generated if not provided)
        episode_id: Episode ID (auto-generated if not provided)
        status: Job status

    Returns:
        ProcessingJob instance
    """
    if job_id is None:
        job_id = str(uuid4())
    if user_id is None:
        user_id = str(uuid4())
    if user_email is None:
        user_email = f"test-{user_id[:8]}@example.com"
    if episode_id is None:
        episode_id = str(uuid4())

    return ProcessingJob(
        id=job_id,
        user_id=user_id,
        user_email=user_email,
        episode_id=episode_id,
        status=status,
    )


@pytest.fixture
async def test_db_connection():
    """
    Create a test DynamoDB connection for testing.

    Returns:
        DynamoDBConnection instance
    """
    connection = DynamoDBConnection()

    # Ensure tables exist
    await create_test_tables()

    yield connection

    # Cleanup after test
    await clear_all_tables(connection)


@pytest.fixture
async def populated_test_db(test_db_connection):
    """
    Create a DynamoDB connection with populated test data.

    Args:
        test_db_connection: DynamoDB connection fixture

    Returns:
        DynamoDBConnection instance with test data
    """
    await populate_test_data(test_db_connection)
    yield test_db_connection


@pytest.fixture
def test_user():
    """Create a test user instance."""
    return create_test_user()


@pytest.fixture
def test_podcast():
    """Create a test podcast instance."""
    return create_test_podcast()


@pytest.fixture
def test_episode():
    """Create a test episode instance."""
    return create_test_episode()


@pytest.fixture
def test_credit_transaction():
    """Create a test credit transaction instance."""
    return create_test_credit_transaction()


@pytest.fixture
def test_processing_job():
    """Create a test processing job instance."""
    return create_test_processing_job()
