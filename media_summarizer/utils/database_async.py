"""
Async database utilities for DynamoDB operations.

This module provides simple, stateless utility functions for interacting
with DynamoDB tables in the Media Summarizer application using async operations.
"""

import logging
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError
import aioboto3
from boto3.dynamodb.conditions import Key, Attr
import os

from media_summarizer.core.models import User, ProcessingJob, JobStatus
from media_summarizer.core.models.auth import AuthToken, TokenType
# Removed CreditTransaction import (legacy credits system fully deprecated)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")

# Table names (can be overridden by environment variables for testing)
USERS_TABLE = os.environ.get("USERS_TABLE", "users")
PODCASTS_TABLE = os.environ.get("PODCASTS_TABLE", "podcasts")
EPISODES_TABLE = os.environ.get("EPISODES_TABLE", "episodes")
CREDIT_TRANSACTIONS_TABLE = os.environ.get(
    "CREDIT_TRANSACTIONS_TABLE", "credit_transactions"
)
PROCESSING_JOBS_TABLE = os.environ.get("PROCESSING_JOBS_TABLE", "processing_jobs")
AUTH_TOKENS_TABLE = os.environ.get("AUTH_TOKENS_TABLE", "auth_tokens")
STRIPE_EVENTS_TABLE = os.environ.get("STRIPE_EVENTS_TABLE", "stripe_events")

# Session aioboto3 for async operations (created lazily)
_session = None


def get_session():
    """Get or create aioboto3 session with current environment variables."""
    global _session
    if _session is None:
        _session = aioboto3.Session(
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        )
    return _session


def reset_session():
    """Reset the aioboto3 session to pick up new environment variables."""
    global _session
    _session = None


class DynamoDBConnection:
    """Async DynamoDB connection manager."""

    def __init__(self):
        self.endpoint_url = AWS_ENDPOINT_URL
        self.region_name = AWS_REGION

    async def get_client(self):
        """Return an async DynamoDB client."""
        session = get_session()
        return session.client(
            "dynamodb", endpoint_url=self.endpoint_url, region_name=self.region_name
        )

    async def get_resource(self):
        """Return an async DynamoDB resource."""
        session = get_session()
        return session.resource(
            "dynamodb", endpoint_url=self.endpoint_url, region_name=self.region_name
        )


async def get_db():
    """
    Dependency to get a DynamoDB connection.
    For use with FastAPI Depends.
    """
    return DynamoDBConnection()


async def table_exists(table_name: str) -> bool:
    """Check if a table exists."""
    try:
        session = get_session()
        client = session.client(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        )
        await client.describe_table(TableName=table_name)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return False
        raise


# User operations
async def create_user(user: User) -> User:
    """Create a new user in DynamoDB."""
    session = get_session()
    async with session.resource(
        "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
    ) as dynamodb:
        table = await dynamodb.Table(USERS_TABLE)
        try:
            await table.put_item(
                Item=user.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(id)",
            )
            logger.info(f"User created: {user.id}")
            return user
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ValueError(f"User with ID {user.id} already exists")
            logger.error(f"Error creating user: {str(e)}")
            raise


async def get_user_by_id(user_id: str) -> Optional[User]:
    """Get a user by ID."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(USERS_TABLE)

            response = await table.get_item(Key={"id": user_id})
            if "Item" in response:
                return User.from_dynamodb_item(response["Item"])
            return None
    except ClientError as e:
        logger.error(f"Error getting user by ID {user_id}: {str(e)}")
        raise


async def get_user_by_email(email: str) -> Optional[User]:
    """Get a user by email."""
    session = get_session()
    async with session.resource(
        "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
    ) as dynamodb:
        table = await dynamodb.Table(USERS_TABLE)
        try:
            response = await table.query(
                IndexName="email-index", KeyConditionExpression=Key("email").eq(email)
            )
            items = response.get("Items", [])
            if items:
                return User.from_dynamodb_item(items[0])
            return None
        except ClientError as e:
            logger.error(f"Error getting user by email {email}: {str(e)}")
            raise


async def update_user(user: User) -> User:
    """Update a user in DynamoDB."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(USERS_TABLE)

            await table.put_item(Item=user.to_dynamodb_item())
            logger.info(f"User updated: {user.id}")
            return user
    except ClientError as e:
        logger.error(f"Error updating user {user.id}: {str(e)}")
        raise


async def delete_user(user_id: str) -> bool:
    """Delete a user from DynamoDB."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(USERS_TABLE)

            await table.delete_item(Key={"id": user_id})
            logger.info(f"User deleted: {user_id}")
            return True
    except ClientError as e:
        logger.error(f"Error deleting user {user_id}: {str(e)}")
        raise


# (Removed legacy update_user_credits function — credits system deprecated in favor of minutes-based billing.)


# Legacy credit transaction operations removed (minutes-based billing migration complete)


# Processing job operations
async def create_processing_job(job: ProcessingJob) -> ProcessingJob:
    """Create a new processing job in DynamoDB."""
    session = get_session()
    async with session.resource(
        "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
    ) as dynamodb:
        table = await dynamodb.Table(PROCESSING_JOBS_TABLE)
        try:
            await table.put_item(
                Item=job.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(id)",
            )
            logger.info(f"Processing job created: {job.id}")
            return job
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ValueError(f"Processing job with ID {job.id} already exists")
            logger.error(f"Error creating processing job: {str(e)}")
            raise


async def get_processing_job_by_id(job_id: str) -> Optional[ProcessingJob]:
    """Get a processing job by ID."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(PROCESSING_JOBS_TABLE)

            response = await table.get_item(Key={"id": job_id})
            if "Item" in response:
                return ProcessingJob.from_dynamodb_item(response["Item"])
            return None
    except ClientError as e:
        logger.error(f"Error getting processing job by ID {job_id}: {str(e)}")
        raise


async def get_processing_jobs_by_user_id(user_id: str) -> List[ProcessingJob]:
    """Get all processing jobs for a user."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(PROCESSING_JOBS_TABLE)

            response = await table.query(
                IndexName="user-index",
                KeyConditionExpression=Key("user_id").eq(user_id),
            )
            items = response.get("Items", [])
            return [ProcessingJob.from_dynamodb_item(item) for item in items]
    except ClientError as e:
        logger.error(f"Error getting processing jobs by user ID {user_id}: {str(e)}")
        raise


async def get_processing_jobs_by_status(status: JobStatus) -> List[ProcessingJob]:
    """Get all processing jobs with a specific status."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(PROCESSING_JOBS_TABLE)

            response = await table.query(
                IndexName="status-index",
                KeyConditionExpression=Key("job_status").eq(status.value),
            )
            items = response.get("Items", [])
            return [ProcessingJob.from_dynamodb_item(item) for item in items]
    except ClientError as e:
        logger.error(f"Error getting processing jobs by status {status}: {str(e)}")
        raise


async def update_processing_job(job: ProcessingJob) -> ProcessingJob:
    """Update a processing job in DynamoDB."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(PROCESSING_JOBS_TABLE)

            await table.put_item(Item=job.to_dynamodb_item())
            logger.info(f"Processing job updated: {job.id}")
            return job
    except ClientError as e:
        logger.error(f"Error updating processing job {job.id}: {str(e)}")
        raise


async def delete_processing_job(job_id: str) -> bool:
    """Delete a processing job from DynamoDB."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(PROCESSING_JOBS_TABLE)

            await table.delete_item(Key={"id": job_id})
            logger.info(f"Processing job deleted: {job_id}")
            return True
    except ClientError as e:
        logger.error(f"Error deleting processing job {job_id}: {str(e)}")
        raise


# Auth token operations
async def create_auth_token(token: AuthToken) -> AuthToken:
    """Create a new auth token in DynamoDB."""
    session = get_session()
    async with session.resource(
        "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
    ) as dynamodb:
        table = await dynamodb.Table(AUTH_TOKENS_TABLE)
        try:
            await table.put_item(
                Item=token.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(id)",
            )
            logger.info(f"Auth token created: {token.id}")
            return token
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ValueError(f"Auth token with ID {token.id} already exists")
            logger.error(f"Error creating auth token: {str(e)}")
            raise


async def get_auth_token_by_token(token_string: str) -> Optional[AuthToken]:
    """Get an auth token by its token string."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(AUTH_TOKENS_TABLE)

            response = await table.query(
                IndexName="token-index",
                KeyConditionExpression=Key("token").eq(token_string),
            )
            items = response.get("Items", [])
            if items:
                return AuthToken.from_dynamodb_item(items[0])
            return None
    except ClientError as e:
        logger.error(f"Error getting auth token by token string: {str(e)}")
        raise


async def get_auth_token_by_id(token_id: str) -> Optional[AuthToken]:
    """Get an auth token by ID."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(AUTH_TOKENS_TABLE)

            response = await table.get_item(Key={"id": token_id})
            if "Item" in response:
                return AuthToken.from_dynamodb_item(response["Item"])
            return None
    except ClientError as e:
        logger.error(f"Error getting auth token by ID {token_id}: {str(e)}")
        raise


async def get_auth_tokens_by_user_id(
    user_id: str, token_type: Optional[TokenType] = None
) -> List[AuthToken]:
    """Get all auth tokens for a user, optionally filtered by type."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(AUTH_TOKENS_TABLE)

            if token_type:
                response = await table.query(
                    IndexName="user-type-index",
                    KeyConditionExpression=Key("user_id").eq(user_id)
                    & Key("token_type").eq(token_type.value),
                )
            else:
                response = await table.query(
                    IndexName="user-index",
                    KeyConditionExpression=Key("user_id").eq(user_id),
                )

            items = response.get("Items", [])
            return [AuthToken.from_dynamodb_item(item) for item in items]
    except ClientError as e:
        logger.error(f"Error getting auth tokens by user ID {user_id}: {str(e)}")
        raise


async def update_auth_token(token: AuthToken) -> AuthToken:
    """Update an auth token in DynamoDB."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(AUTH_TOKENS_TABLE)

            await table.put_item(Item=token.to_dynamodb_item())
            logger.info(f"Auth token updated: {token.id}")
            return token
    except ClientError as e:
        logger.error(f"Error updating auth token {token.id}: {str(e)}")
        raise


async def delete_auth_token(token_id: str) -> bool:
    """Delete an auth token from DynamoDB."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(AUTH_TOKENS_TABLE)

            await table.delete_item(Key={"id": token_id})
            logger.info(f"Auth token deleted: {token_id}")
            return True
    except ClientError as e:
        logger.error(f"Error deleting auth token {token_id}: {str(e)}")
        raise


async def revoke_user_tokens(
    user_id: str, token_type: Optional[TokenType] = None
) -> int:
    """Revoke all tokens for a user, optionally filtered by type."""
    try:
        tokens = await get_auth_tokens_by_user_id(user_id, token_type)
        revoked_count = 0

        for token in tokens:
            if token.is_active:
                token.revoke()
                await update_auth_token(token)
                revoked_count += 1

        logger.info(f"Revoked {revoked_count} tokens for user {user_id}")
        return revoked_count
    except Exception as e:
        logger.error(f"Error revoking tokens for user {user_id}: {str(e)}")
        raise


async def cleanup_expired_tokens() -> int:
    """Clean up expired tokens from the database."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(AUTH_TOKENS_TABLE)

            # Scan for expired tokens
            response = await table.scan()
            items = response.get("Items", [])

            deleted_count = 0
            for item in items:
                token = AuthToken.from_dynamodb_item(item)
                if token.is_expired():
                    await delete_auth_token(token.id)
                    deleted_count += 1

            logger.info(f"Cleaned up {deleted_count} expired tokens")
            return deleted_count
    except ClientError as e:
        logger.error(f"Error cleaning up expired tokens: {str(e)}")
        raise


# Stripe webhook idempotency helpers
async def has_stripe_event(event_id: str) -> bool:
    """Return True if the Stripe event has already been recorded (processed)."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(STRIPE_EVENTS_TABLE)
            response = await table.get_item(Key={"id": event_id})
            return "Item" in response
    except ClientError as e:
        logger.error(f"Error checking stripe event {event_id}: {str(e)}")
        raise


async def record_stripe_event(event_id: str) -> bool:
    """Record a processed Stripe event. Returns True if new, False if already exists."""
    from datetime import datetime, timezone

    session = get_session()
    async with session.resource(
        "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
    ) as dynamodb:
        table = await dynamodb.Table(STRIPE_EVENTS_TABLE)
        try:
            await table.put_item(
                Item={
                    "id": event_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                ConditionExpression="attribute_not_exists(id)",
            )
            logger.info(f"Recorded Stripe event {event_id} for idempotency")
            return True
        except ClientError as e:
            if e.response["Error"].get("Code") == "ConditionalCheckFailedException":
                logger.info(f"Stripe event {event_id} already recorded")
                return False
            logger.error(f"Error recording stripe event {event_id}: {str(e)}")
            raise
