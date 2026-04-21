"""
Async database utilities for DynamoDB operations.

This module provides simple, stateless utility functions for interacting
with DynamoDB tables in the Media Summarizer application using async operations.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import aioboto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from media_summarizer.core.models import User, ProcessingJob, JobStatus, Folder
from media_summarizer.core.models.auth import AuthToken, TokenType
from media_summarizer.utils.logging_config import (
    get_runtime_aws_endpoint_url,
    log_event,
)
# Removed CreditTransaction import (legacy credits system fully deprecated)

logger = logging.getLogger(__name__)

# AWS configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
_IMPORT_TIME_AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")
AWS_ENDPOINT_URL = _IMPORT_TIME_AWS_ENDPOINT_URL

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
USER_FOLDERS_TABLE = os.environ.get("USER_FOLDERS_TABLE", "user_folders")

# Session aioboto3 for async operations (created lazily)
_session = None


def _runtime_aws_endpoint_url() -> Optional[str]:
    configured = AWS_ENDPOINT_URL
    if configured == _IMPORT_TIME_AWS_ENDPOINT_URL:
        configured = os.environ.get("AWS_ENDPOINT_URL", _IMPORT_TIME_AWS_ENDPOINT_URL)
    return get_runtime_aws_endpoint_url(
        configured_value=configured,
        consumer="dynamodb",
    )


def _dynamodb_client_kwargs() -> Dict[str, Any]:
    return {
        "endpoint_url": _runtime_aws_endpoint_url(),
        "region_name": AWS_REGION,
    }


def _log_dynamodb_success(
    operation: str,
    *,
    table: str,
    **fields: Any,
) -> None:
    log_event(
        logger,
        logging.DEBUG,
        "external_call.succeeded",
        f"DynamoDB {operation} completed",
        provider="dynamodb",
        table=table,
        **fields,
    )


def _log_dynamodb_error(
    operation: str,
    exc: Exception,
    *,
    table: str,
    **fields: Any,
) -> None:
    log_event(
        logger,
        logging.ERROR,
        "external_call.failed",
        f"DynamoDB {operation} failed",
        provider="dynamodb",
        table=table,
        error_code=operation.upper(),
        error_type=type(exc).__name__,
        exc_info=exc,
        **fields,
    )


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
        self.endpoint_url = _runtime_aws_endpoint_url()
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
        client = session.client("dynamodb", **_dynamodb_client_kwargs())
        await client.describe_table(TableName=table_name)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return False
        _log_dynamodb_error("describe_table", e, table=table_name)
        raise


# User operations
async def create_user(user: User) -> User:
    """Create a new user in DynamoDB."""
    session = get_session()
    async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
        table = await dynamodb.Table(USERS_TABLE)
        try:
            await table.put_item(
                Item=user.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(id)",
            )
            _log_dynamodb_success("create_user", table=USERS_TABLE, user_id=user.id)
            return user
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ValueError(f"User with ID {user.id} already exists")
            _log_dynamodb_error("create_user", e, table=USERS_TABLE, user_id=user.id)
            raise


async def get_user_by_id(user_id: str) -> Optional[User]:
    """Get a user by ID."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USERS_TABLE)

            response = await table.get_item(Key={"id": user_id})
            if "Item" in response:
                return User.from_dynamodb_item(response["Item"])
            return None
    except ClientError as e:
        _log_dynamodb_error("get_user_by_id", e, table=USERS_TABLE, user_id=user_id)
        raise


async def get_user_by_email(email: str) -> Optional[User]:
    """Get a user by email."""
    session = get_session()
    async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
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
            _log_dynamodb_error(
                "get_user_by_email",
                e,
                table=USERS_TABLE,
                email=email,
            )
            raise


async def update_user(user: User) -> User:
    """Update a user in DynamoDB."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USERS_TABLE)

            await table.put_item(Item=user.to_dynamodb_item())
            _log_dynamodb_success("update_user", table=USERS_TABLE, user_id=user.id)
            return user
    except ClientError as e:
        _log_dynamodb_error("update_user", e, table=USERS_TABLE, user_id=user.id)
        raise


async def delete_user(user_id: str) -> bool:
    """Delete a user from DynamoDB."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USERS_TABLE)

            await table.delete_item(Key={"id": user_id})
            _log_dynamodb_success("delete_user", table=USERS_TABLE, user_id=user_id)
            return True
    except ClientError as e:
        _log_dynamodb_error("delete_user", e, table=USERS_TABLE, user_id=user_id)
        raise


# (Removed legacy update_user_credits function — credits system deprecated in favor of minutes-based billing.)


# Legacy credit transaction operations removed (minutes-based billing migration complete)


# Processing job operations
async def create_processing_job(job: ProcessingJob) -> ProcessingJob:
    """Create a new processing job in DynamoDB."""
    session = get_session()
    async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
        table = await dynamodb.Table(PROCESSING_JOBS_TABLE)
        try:
            await table.put_item(
                Item=job.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(id)",
            )
            _log_dynamodb_success(
                "create_processing_job",
                table=PROCESSING_JOBS_TABLE,
                job_id=job.id,
            )
            return job
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ValueError(f"Processing job with ID {job.id} already exists")
            _log_dynamodb_error(
                "create_processing_job",
                e,
                table=PROCESSING_JOBS_TABLE,
                job_id=job.id,
            )
            raise


async def get_processing_job_by_id(job_id: str) -> Optional[ProcessingJob]:
    """Get a processing job by ID."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(PROCESSING_JOBS_TABLE)

            response = await table.get_item(Key={"id": job_id})
            if "Item" in response:
                return ProcessingJob.from_dynamodb_item(response["Item"])
            return None
    except ClientError as e:
        _log_dynamodb_error(
            "get_processing_job_by_id",
            e,
            table=PROCESSING_JOBS_TABLE,
            job_id=job_id,
        )
        raise


async def get_processing_jobs_by_user_id(user_id: str) -> List[ProcessingJob]:
    """Get all processing jobs for a user."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(PROCESSING_JOBS_TABLE)

            response = await table.query(
                IndexName="user-index",
                KeyConditionExpression=Key("user_id").eq(user_id),
            )
            items = response.get("Items", [])
            return [ProcessingJob.from_dynamodb_item(item) for item in items]
    except ClientError as e:
        _log_dynamodb_error(
            "get_processing_jobs_by_user_id",
            e,
            table=PROCESSING_JOBS_TABLE,
            user_id=user_id,
        )
        raise


async def get_processing_jobs_by_status(status: JobStatus) -> List[ProcessingJob]:
    """Get all processing jobs with a specific status."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(PROCESSING_JOBS_TABLE)

            response = await table.query(
                IndexName="status-index",
                KeyConditionExpression=Key("job_status").eq(status.value),
            )
            items = response.get("Items", [])
            return [ProcessingJob.from_dynamodb_item(item) for item in items]
    except ClientError as e:
        _log_dynamodb_error(
            "get_processing_jobs_by_status",
            e,
            table=PROCESSING_JOBS_TABLE,
            status=status.value,
        )
        raise


async def update_processing_job(job: ProcessingJob) -> ProcessingJob:
    """Update a processing job in DynamoDB."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(PROCESSING_JOBS_TABLE)

            await table.put_item(Item=job.to_dynamodb_item())
            _log_dynamodb_success(
                "update_processing_job",
                table=PROCESSING_JOBS_TABLE,
                job_id=job.id,
            )
            return job
    except ClientError as e:
        _log_dynamodb_error(
            "update_processing_job",
            e,
            table=PROCESSING_JOBS_TABLE,
            job_id=job.id,
        )
        raise


async def delete_processing_job(job_id: str) -> bool:
    """Delete a processing job from DynamoDB."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(PROCESSING_JOBS_TABLE)

            await table.delete_item(Key={"id": job_id})
            _log_dynamodb_success(
                "delete_processing_job",
                table=PROCESSING_JOBS_TABLE,
                job_id=job_id,
            )
            return True
    except ClientError as e:
        _log_dynamodb_error(
            "delete_processing_job",
            e,
            table=PROCESSING_JOBS_TABLE,
            job_id=job_id,
        )
        raise


# Auth token operations
async def create_auth_token(token: AuthToken) -> AuthToken:
    """Create a new auth token in DynamoDB."""
    session = get_session()
    async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
        table = await dynamodb.Table(AUTH_TOKENS_TABLE)
        try:
            await table.put_item(
                Item=token.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(id)",
            )
            _log_dynamodb_success(
                "create_auth_token",
                table=AUTH_TOKENS_TABLE,
                token_id=token.id,
            )
            return token
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ValueError(f"Auth token with ID {token.id} already exists")
            _log_dynamodb_error(
                "create_auth_token",
                e,
                table=AUTH_TOKENS_TABLE,
                token_id=token.id,
            )
            raise


async def get_auth_token_by_token(token_string: str) -> Optional[AuthToken]:
    """Get an auth token by its token string."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
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
        _log_dynamodb_error(
            "get_auth_token_by_token",
            e,
            table=AUTH_TOKENS_TABLE,
        )
        raise


async def get_auth_token_by_id(token_id: str) -> Optional[AuthToken]:
    """Get an auth token by ID."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(AUTH_TOKENS_TABLE)

            response = await table.get_item(Key={"id": token_id})
            if "Item" in response:
                return AuthToken.from_dynamodb_item(response["Item"])
            return None
    except ClientError as e:
        _log_dynamodb_error(
            "get_auth_token_by_id",
            e,
            table=AUTH_TOKENS_TABLE,
            token_id=token_id,
        )
        raise


async def get_auth_tokens_by_user_id(
    user_id: str, token_type: Optional[TokenType] = None
) -> List[AuthToken]:
    """Get all auth tokens for a user, optionally filtered by type."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
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
        _log_dynamodb_error(
            "get_auth_tokens_by_user_id",
            e,
            table=AUTH_TOKENS_TABLE,
            user_id=user_id,
            token_type=token_type.value if token_type else None,
        )
        raise


async def update_auth_token(token: AuthToken) -> AuthToken:
    """Update an auth token in DynamoDB."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(AUTH_TOKENS_TABLE)

            await table.put_item(Item=token.to_dynamodb_item())
            _log_dynamodb_success(
                "update_auth_token",
                table=AUTH_TOKENS_TABLE,
                token_id=token.id,
            )
            return token
    except ClientError as e:
        _log_dynamodb_error(
            "update_auth_token",
            e,
            table=AUTH_TOKENS_TABLE,
            token_id=token.id,
        )
        raise


async def delete_auth_token(token_id: str) -> bool:
    """Delete an auth token from DynamoDB."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(AUTH_TOKENS_TABLE)

            await table.delete_item(Key={"id": token_id})
            _log_dynamodb_success(
                "delete_auth_token",
                table=AUTH_TOKENS_TABLE,
                token_id=token_id,
            )
            return True
    except ClientError as e:
        _log_dynamodb_error(
            "delete_auth_token",
            e,
            table=AUTH_TOKENS_TABLE,
            token_id=token_id,
        )
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

        _log_dynamodb_success(
            "revoke_user_tokens",
            table=AUTH_TOKENS_TABLE,
            user_id=user_id,
            count=revoked_count,
        )
        return revoked_count
    except Exception as e:
        _log_dynamodb_error(
            "revoke_user_tokens",
            e,
            table=AUTH_TOKENS_TABLE,
            user_id=user_id,
        )
        raise


async def cleanup_expired_tokens() -> int:
    """Clean up expired tokens from the database."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
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

            _log_dynamodb_success(
                "cleanup_expired_tokens",
                table=AUTH_TOKENS_TABLE,
                count=deleted_count,
            )
            return deleted_count
    except ClientError as e:
        _log_dynamodb_error("cleanup_expired_tokens", e, table=AUTH_TOKENS_TABLE)
        raise


# Stripe webhook idempotency helpers
async def has_stripe_event(event_id: str) -> bool:
    """Return True if the Stripe event has already been recorded (processed)."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(STRIPE_EVENTS_TABLE)
            response = await table.get_item(Key={"id": event_id})
            return "Item" in response
    except ClientError as e:
        _log_dynamodb_error(
            "has_stripe_event",
            e,
            table=STRIPE_EVENTS_TABLE,
            event_id=event_id,
        )
        raise


async def record_stripe_event(event_id: str) -> bool:
    """Record a processed Stripe event. Returns True if new, False if already exists."""
    from datetime import datetime, timezone

    session = get_session()
    async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
        table = await dynamodb.Table(STRIPE_EVENTS_TABLE)
        try:
            await table.put_item(
                Item={
                    "id": event_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                ConditionExpression="attribute_not_exists(id)",
            )
            _log_dynamodb_success(
                "record_stripe_event",
                table=STRIPE_EVENTS_TABLE,
                event_id=event_id,
            )
            return True
        except ClientError as e:
            if e.response["Error"].get("Code") == "ConditionalCheckFailedException":
                _log_dynamodb_success(
                    "record_stripe_event_duplicate",
                    table=STRIPE_EVENTS_TABLE,
                    event_id=event_id,
                )
                return False
            _log_dynamodb_error(
                "record_stripe_event",
                e,
                table=STRIPE_EVENTS_TABLE,
                event_id=event_id,
            )
            raise


# ---------- Folder operations ----------

async def create_folder(folder: Folder) -> Folder:
    """Create a new folder in DynamoDB."""
    session = get_session()
    async with session.resource(
        "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
    ) as dynamodb:
        table = await dynamodb.Table(USER_FOLDERS_TABLE)
        try:
            await table.put_item(
                Item=folder.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(id)",
            )
            logger.info(f"Folder created: {folder.id} for user {folder.user_id}")
            return folder
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ValueError(f"Folder with ID {folder.id} already exists")
            logger.error(f"Error creating folder: {str(e)}")
            raise


async def get_folder_by_id(folder_id: str) -> Optional[Folder]:
    """Get a folder by ID."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(USER_FOLDERS_TABLE)
            response = await table.get_item(Key={"id": folder_id})
            if "Item" in response:
                return Folder.from_dynamodb_item(response["Item"])
            return None
    except ClientError as e:
        logger.error(f"Error getting folder by ID {folder_id}: {str(e)}")
        raise


async def get_folders_by_user_id(user_id: str) -> List[Folder]:
    """Get all folders for a user."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(USER_FOLDERS_TABLE)
            response = await table.query(
                IndexName="user-index",
                KeyConditionExpression=Key("user_id").eq(user_id),
            )
            items = response.get("Items", [])
            return [Folder.from_dynamodb_item(item) for item in items]
    except ClientError as e:
        logger.error(f"Error getting folders for user {user_id}: {str(e)}")
        raise


async def update_folder(folder: Folder) -> Folder:
    """Update a folder in DynamoDB."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(USER_FOLDERS_TABLE)
            await table.put_item(Item=folder.to_dynamodb_item())
            logger.info(f"Folder updated: {folder.id}")
            return folder
    except ClientError as e:
        logger.error(f"Error updating folder {folder.id}: {str(e)}")
        raise


async def delete_folder(folder_id: str) -> bool:
    """Delete a folder from DynamoDB."""
    try:
        session = get_session()
        async with session.resource(
            "dynamodb", endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION
        ) as dynamodb:
            table = await dynamodb.Table(USER_FOLDERS_TABLE)
            await table.delete_item(Key={"id": folder_id})
            logger.info(f"Folder deleted: {folder_id}")
            return True
    except ClientError as e:
        logger.error(f"Error deleting folder {folder_id}: {str(e)}")
        raise


async def get_processing_jobs_by_folder_id(
    user_id: str, folder_id: str
) -> List[ProcessingJob]:
    """Get all processing jobs in a specific folder for a user."""
    try:
        # We query by user first, then filter by folder_id
        jobs = await get_processing_jobs_by_user_id(user_id)
        return [job for job in jobs if getattr(job, "folder_id", None) == folder_id]
    except Exception as e:
        logger.error(
            f"Error getting jobs by folder {folder_id} for user {user_id}: {str(e)}"
        )
        raise
