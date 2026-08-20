"""
Async database utilities for DynamoDB operations.

This module provides simple, stateless utility functions for interacting
with DynamoDB tables in the Media Summarizer application using async operations.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import aioboto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from media_summarizer.core.models import Folder, JobStatus, ProcessingJob, Tag, User, UserRssFeed
from media_summarizer.core.models.auth import AuthToken, TokenType
from media_summarizer.utils.env import required_env
from media_summarizer.utils.logging_config import log_event

# Removed CreditTransaction import (legacy credits system fully deprecated)

logger = logging.getLogger(__name__)

# AWS region resolution: prefer AWS_REGION (Lambda runtime sets this) and fall
# back to AWS_DEFAULT_REGION (CLI/dev convention). botocore itself only reads
# AWS_DEFAULT_REGION, so we resolve once here and pass region_name=AWS_REGION
# explicitly everywhere a boto/aioboto resource is opened.
AWS_REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
if not AWS_REGION:
    raise RuntimeError("AWS region not configured: set AWS_REGION or AWS_DEFAULT_REGION.")

# Table names, injected by Terraform from
# infrastructure/terraform/modules/platform/runtime_env.tf. No defaults: see
# media_summarizer/utils/env.py.
#
# PODCASTS_TABLE, EPISODES_TABLE and CREDIT_TRANSACTIONS_TABLE used to be
# declared here too. They had no readers left and Terraform never created the
# tables, so they resolved to their hardcoded fallbacks and pointed at nothing.
USERS_TABLE = required_env("USERS_TABLE")
PROCESSING_JOBS_TABLE = required_env("PROCESSING_JOBS_TABLE")
AUTH_TOKENS_TABLE = required_env("AUTH_TOKENS_TABLE")
USER_FOLDERS_TABLE = required_env("USER_FOLDERS_TABLE")
USER_TAGS_TABLE = required_env("USER_TAGS_TABLE")
USER_RSS_FEEDS_TABLE = required_env("USER_RSS_FEEDS_TABLE")

# Session aioboto3 for async operations (created lazily)
_session = None


def _dynamodb_client_kwargs() -> Dict[str, Any]:
    return {"region_name": AWS_REGION}


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
    """Get or create aioboto3 session with current environment variables.

    On Lambda, AWS injects credentials via the standard chain (including
    AWS_SESSION_TOKEN). Passing only access_key_id + secret_access_key without
    the session token yields UnrecognizedClientException, so we let aioboto3
    resolve credentials itself when no explicit static creds are present.
    """
    global _session
    if _session is None:
        kwargs: Dict[str, Any] = {"region_name": AWS_REGION}
        access_key = os.environ.get("AWS_ACCESS_KEY_ID")
        secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY")
        session_token = os.environ.get("AWS_SESSION_TOKEN")
        if access_key and secret_key:
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret_key
            if session_token:
                kwargs["aws_session_token"] = session_token
        _session = aioboto3.Session(**kwargs)
    return _session


def reset_session():
    """Reset the aioboto3 session to pick up new environment variables."""
    global _session
    _session = None


class DynamoDBConnection:
    """Async DynamoDB connection manager."""

    def __init__(self):
        self.region_name = AWS_REGION

    async def get_client(self):
        """Return an async DynamoDB client."""
        session = get_session()
        return session.client("dynamodb", region_name=self.region_name)

    async def get_resource(self):
        """Return an async DynamoDB resource."""
        session = get_session()
        return session.resource("dynamodb", region_name=self.region_name)


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
            response = await table.query(IndexName="email-index", KeyConditionExpression=Key("email").eq(email))
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
            # Mirror immediately so the library row carries last_job_id from the
            # start. Without it, a freshly created item has no way back to its
            # pipeline row until the first status transition.
            await _mirror_job_to_durable_library(job)
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


async def persist_apify_run(job: ProcessingJob) -> ProcessingJob:
    """Persist provider correlation immediately after an Apify run starts."""
    item = job.to_dynamodb_item()
    field_names = (
        "apify_run_id",
        "apify_dataset_id",
        "apify_actor_id",
        "apify_actor_kind",
        "apify_source_platform",
        "apify_state",
        "apify_context",
        "apify_backstop_scheduled",
        "apify_started_at",
        "updated_at",
        "expire_at",
    )
    values = {name: item[name] for name in field_names if name in item}
    names = {f"#a{index}": name for index, name in enumerate(values)}
    expression_values = {f":v{index}": value for index, value in enumerate(values.values())}
    set_parts = [f"#a{index} = :v{index}" for index in range(len(values))]

    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(PROCESSING_JOBS_TABLE)
            await table.update_item(
                Key={"id": job.id},
                UpdateExpression=("SET " + ", ".join(set_parts) + " REMOVE apify_claimed_at, apify_completed_at"),
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=expression_values,
                ConditionExpression="attribute_exists(id)",
            )
        await _mirror_job_to_durable_library(job)
        return job
    except ClientError as exc:
        _log_dynamodb_error(
            "persist_apify_run",
            exc,
            table=PROCESSING_JOBS_TABLE,
            job_id=job.id,
        )
        raise


async def mark_apify_backstop_scheduled(job_id: str, run_id: str) -> Optional[ProcessingJob]:
    """Record that the delayed deadline message is durably queued."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(PROCESSING_JOBS_TABLE)
            try:
                response = await table.update_item(
                    Key={"id": job_id},
                    UpdateExpression="SET apify_backstop_scheduled = :yes, updated_at = :now",
                    ConditionExpression="apify_run_id = :run_id",
                    ExpressionAttributeValues={
                        ":yes": True,
                        ":now": now,
                        ":run_id": run_id,
                    },
                    ReturnValues="ALL_NEW",
                )
            except ClientError as exc:
                if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    return None
                raise
        return ProcessingJob.from_dynamodb_item(response["Attributes"])
    except ClientError as exc:
        _log_dynamodb_error(
            "mark_apify_backstop_scheduled",
            exc,
            table=PROCESSING_JOBS_TABLE,
            job_id=job_id,
        )
        raise


async def claim_apify_callback(
    job_id: str,
    run_id: str,
    *,
    lease_seconds: int = 120,
) -> Optional[ProcessingJob]:
    """Acquire one callback continuation, allowing retry after an expired lease."""
    now = datetime.now(timezone.utc)
    claim_before = now - timedelta(seconds=lease_seconds)
    expression_values = {
        ":run_id": run_id,
        ":waiting": "waiting",
        ":processing": "processing",
        ":now": now.isoformat(),
        ":claim_before": claim_before.isoformat(),
        ":completed": JobStatus.COMPLETED.value,
        ":failed": JobStatus.FAILED.value,
        ":cancelled": JobStatus.CANCELLED.value,
    }
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(PROCESSING_JOBS_TABLE)
            try:
                response = await table.update_item(
                    Key={"id": job_id},
                    UpdateExpression=("SET apify_state = :processing, apify_claimed_at = :now, updated_at = :now"),
                    ConditionExpression=(
                        "attribute_exists(id) AND apify_run_id = :run_id AND "
                        "(apify_state = :waiting OR "
                        "(apify_state = :processing AND apify_claimed_at < :claim_before)) "
                        "AND job_status <> :completed AND job_status <> :failed "
                        "AND job_status <> :cancelled"
                    ),
                    ExpressionAttributeValues=expression_values,
                    ReturnValues="ALL_NEW",
                )
            except ClientError as exc:
                if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    return None
                raise
        return ProcessingJob.from_dynamodb_item(response["Attributes"])
    except ClientError as exc:
        _log_dynamodb_error(
            "claim_apify_callback",
            exc,
            table=PROCESSING_JOBS_TABLE,
            job_id=job_id,
        )
        raise


async def complete_apify_callback(job: ProcessingJob) -> bool:
    """Persist callback output only while this run still owns the job."""
    job.apify_state = "processed"
    job.apify_completed_at = datetime.now(timezone.utc)
    job.touch()
    item = job.to_dynamodb_item()
    set_parts: List[str] = []
    names: Dict[str, str] = {}
    values: Dict[str, Any] = {
        ":expected_run": job.apify_run_id,
        ":processing": "processing",
        ":completed": JobStatus.COMPLETED.value,
        ":failed": JobStatus.FAILED.value,
        ":cancelled": JobStatus.CANCELLED.value,
    }
    for index, (key, value) in enumerate(item.items()):
        if key == "id":
            continue
        name_ref = f"#a{index}"
        value_ref = f":v{index}"
        names[name_ref] = key
        values[value_ref] = value
        set_parts.append(f"{name_ref} = {value_ref}")

    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(PROCESSING_JOBS_TABLE)
            try:
                await table.update_item(
                    Key={"id": job.id},
                    UpdateExpression="SET " + ", ".join(set_parts),
                    ConditionExpression=(
                        "apify_run_id = :expected_run AND "
                        "apify_state = :processing AND "
                        "job_status <> :completed AND job_status <> :failed AND "
                        "job_status <> :cancelled"
                    ),
                    ExpressionAttributeNames=names,
                    ExpressionAttributeValues=values,
                )
            except ClientError as exc:
                if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    return False
                raise
        await _mirror_job_to_durable_library(job)
        return True
    except ClientError as exc:
        _log_dynamodb_error(
            "complete_apify_callback",
            exc,
            table=PROCESSING_JOBS_TABLE,
            job_id=job.id,
        )
        raise


async def expire_apify_run(
    job_id: str,
    run_id: str,
    *,
    error_message: str,
    error_step: str,
) -> Optional[ProcessingJob]:
    """Atomically fail an unclaimed run when its delayed backstop fires."""
    job = await get_processing_job_by_id(job_id)
    if not job or job.apify_run_id != run_id or job.apify_state not in {"waiting", "processing"}:
        return None
    if job.is_terminal_state():
        return None

    job.apify_state = "expired"
    job.apify_completed_at = datetime.now(timezone.utc)
    job.mark_failed(error_message=error_message, error_step=error_step)
    item = job.to_dynamodb_item()
    set_parts: List[str] = []
    names: Dict[str, str] = {}
    values: Dict[str, Any] = {
        ":expected_run": run_id,
        ":waiting": "waiting",
        ":processing": "processing",
        ":completed": JobStatus.COMPLETED.value,
        ":failed": JobStatus.FAILED.value,
        ":cancelled": JobStatus.CANCELLED.value,
    }
    for index, (key, value) in enumerate(item.items()):
        if key == "id":
            continue
        name_ref = f"#a{index}"
        value_ref = f":v{index}"
        names[name_ref] = key
        values[value_ref] = value
        set_parts.append(f"{name_ref} = {value_ref}")

    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(PROCESSING_JOBS_TABLE)
            try:
                await table.update_item(
                    Key={"id": job_id},
                    UpdateExpression="SET " + ", ".join(set_parts),
                    ConditionExpression=(
                        "apify_run_id = :expected_run AND "
                        "(apify_state = :waiting OR apify_state = :processing) AND "
                        "job_status <> :completed AND job_status <> :failed AND "
                        "job_status <> :cancelled"
                    ),
                    ExpressionAttributeNames=names,
                    ExpressionAttributeValues=values,
                )
            except ClientError as exc:
                if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                    return None
                raise
        await _mirror_job_to_durable_library(job)
        return job
    except ClientError as exc:
        _log_dynamodb_error(
            "expire_apify_run",
            exc,
            table=PROCESSING_JOBS_TABLE,
            job_id=job_id,
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


async def _mirror_job_to_durable_library(job: ProcessingJob) -> None:
    """Refresh the durable library row's denormalised snapshot (task-240).

    Hooked here rather than at each of the ~15 worker call sites, because a status
    transition that forgets to mirror is invisible: the library row would keep
    saying "pending" forever and the metadata the workers resolve late (a YouTube
    title, an audio duration) would never reach the durable record.

    Strictly best-effort and never raising: the durable row is a *denormalisation*
    of state that has already been committed to processing_jobs one line above.
    A failure here is logged as the alarmed durable_media.write_failed event by
    the service, so it is reported without turning a cosmetic staleness into a
    pipeline failure.

    Imported lazily: the service depends on this module, so a top-level import
    would be circular.
    """
    try:
        from media_summarizer.core.services.durable_media_service import mirror_job

        await mirror_job(job)
    except Exception as exc:  # noqa: BLE001 - best-effort by contract
        logger.warning("Durable library mirror skipped for job %s: %s", job.id, exc)


async def update_processing_job(job: ProcessingJob) -> ProcessingJob:
    """Patch an existing processing job in DynamoDB.

    Attribute-level ``UpdateItem`` guarded by ``attribute_exists(id)``, not the
    full-row ``PutItem`` this used to be (task-220). Two reasons:

    - **A job row is allowed to disappear.** ``processing_jobs`` is operational
      state with a TTL, so a late worker write must not resurrect a half-populated
      row that the library would then have to reconcile with.
    - **A rewrite clobbers.** Concurrent workers touching different attributes of
      the same job each carried a full snapshot; the last writer won and silently
      reverted the others.

    A write against a job that no longer exists is a no-op, logged, and *still*
    mirrors onto the durable library row: the user's item keeps moving forward even
    when its pipeline row is gone.
    """
    item = job.to_dynamodb_item()
    set_parts: List[str] = []
    expr_names: Dict[str, str] = {}
    expr_values: Dict[str, Any] = {}
    for index, (key, value) in enumerate(item.items()):
        if key == "id":
            continue
        name_ref = f"#a{index}"
        value_ref = f":v{index}"
        expr_names[name_ref] = key
        expr_values[value_ref] = value
        set_parts.append(f"{name_ref} = {value_ref}")

    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(PROCESSING_JOBS_TABLE)

            try:
                await table.update_item(
                    Key={"id": job.id},
                    UpdateExpression="SET " + ", ".join(set_parts),
                    ExpressionAttributeNames=expr_names,
                    ExpressionAttributeValues=expr_values,
                    ConditionExpression="attribute_exists(id)",
                )
                _log_dynamodb_success(
                    "update_processing_job",
                    table=PROCESSING_JOBS_TABLE,
                    job_id=job.id,
                )
            except ClientError as e:
                if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                    raise
                logger.warning(
                    "Processing job %s no longer exists; skipped operational update and mirrored the durable library row only",
                    job.id,
                )

            await _mirror_job_to_durable_library(job)
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


async def get_auth_tokens_by_user_id(user_id: str, token_type: Optional[TokenType] = None) -> List[AuthToken]:
    """Get all auth tokens for a user, optionally filtered by type.

    Fully paginated: with a sliding one-year refresh, a long-lived account keeps
    thousands of rotated rows, and a single query page (1 MB) stops well short of
    them. Account deletion iterates this list, so a truncated read would leave
    sessions behind.
    """
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(AUTH_TOKENS_TABLE)

            if token_type:
                query_kwargs: Dict[str, Any] = {
                    "IndexName": "user-type-index",
                    "KeyConditionExpression": Key("user_id").eq(user_id)
                    & Key("token_type").eq(token_type.value),
                }
            else:
                query_kwargs = {
                    "IndexName": "user-index",
                    "KeyConditionExpression": Key("user_id").eq(user_id),
                }

            tokens: List[AuthToken] = []
            while True:
                response = await table.query(**query_kwargs)
                tokens.extend(
                    AuthToken.from_dynamodb_item(item)
                    for item in response.get("Items", [])
                )
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                query_kwargs["ExclusiveStartKey"] = last_key

            return tokens
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


async def revoke_refresh_token_lineage(user_id: str, lineage_id: str) -> int:
    """Revoke the refresh tokens of one device session, and only that one.

    A lineage holds at most one live token — its head — because each rotation
    deactivates its predecessor; the loop still covers the whole lineage so a
    logout racing a refresh cannot leave the successor usable. Every other device
    of the account keeps its own lineage, hence its session.
    """
    try:
        tokens = await get_auth_tokens_by_user_id(user_id, TokenType.REFRESH_TOKEN)
        revoked_count = 0

        for token in tokens:
            if token.lineage_id == lineage_id and token.is_active:
                token.revoke()
                await update_auth_token(token)
                revoked_count += 1

        _log_dynamodb_success(
            "revoke_refresh_token_lineage",
            table=AUTH_TOKENS_TABLE,
            user_id=user_id,
            lineage_id=lineage_id,
            count=revoked_count,
        )
        return revoked_count
    except Exception as e:
        _log_dynamodb_error(
            "revoke_refresh_token_lineage",
            e,
            table=AUTH_TOKENS_TABLE,
            user_id=user_id,
            lineage_id=lineage_id,
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


# ---------- Folder operations ----------


async def create_folder(folder: Folder) -> Folder:
    """Create a new folder in DynamoDB."""
    session = get_session()
    async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
        table = await dynamodb.Table(USER_FOLDERS_TABLE)
        try:
            await table.put_item(
                Item=folder.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(id)",
            )
            _log_dynamodb_success(
                "create_folder",
                table=USER_FOLDERS_TABLE,
                folder_id=folder.id,
                user_id=folder.user_id,
            )
            return folder
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ValueError(f"Folder with ID {folder.id} already exists")
            _log_dynamodb_error(
                "create_folder",
                e,
                table=USER_FOLDERS_TABLE,
                folder_id=folder.id,
            )
            raise


async def get_folder_by_id(folder_id: str) -> Optional[Folder]:
    """Get a folder by ID."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_FOLDERS_TABLE)
            response = await table.get_item(Key={"id": folder_id})
            if "Item" in response:
                return Folder.from_dynamodb_item(response["Item"])
            return None
    except ClientError as e:
        _log_dynamodb_error(
            "get_folder_by_id",
            e,
            table=USER_FOLDERS_TABLE,
            folder_id=folder_id,
        )
        raise


async def get_folders_by_user_id(user_id: str) -> List[Folder]:
    """Get all folders for a user."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_FOLDERS_TABLE)
            response = await table.query(
                IndexName="user-index",
                KeyConditionExpression=Key("user_id").eq(user_id),
            )
            items = response.get("Items", [])
            return [Folder.from_dynamodb_item(item) for item in items]
    except ClientError as e:
        _log_dynamodb_error(
            "get_folders_by_user_id",
            e,
            table=USER_FOLDERS_TABLE,
            user_id=user_id,
        )
        raise


async def stamp_folder_engagement(
    folder_id: str,
    *,
    user_id: str,
    dampener_seconds: int,
    now: Optional[datetime] = None,
) -> bool:
    """Record that the user just engaged with one collection (task-303).

    A targeted ``UpdateItem`` on the single attribute, never a model ``put_item``:
    :func:`update_folder` rewrites the whole item, so stamping through it would race
    a concurrent rename over the rest of the row.

    Ownership travels in the condition rather than in a preceding read, so a folder
    id belonging to somebody else simply writes nothing. The dampener is the same
    conditional shape the media stamp uses, and for the same reason: a user flipping
    between two artifacts of the same collection should produce one write per
    minute, not one per tap.

    Returns:
        True when the stamp landed, False when the condition refused it (unknown
        folder, another user's folder, or an engagement younger than the dampener).
    """
    moment = now or datetime.now(timezone.utc)
    cutoff = moment - timedelta(seconds=dampener_seconds)
    session = get_session()
    async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
        table = await dynamodb.Table(USER_FOLDERS_TABLE)
        try:
            await table.update_item(
                Key={"id": folder_id},
                UpdateExpression="SET last_engaged_at = :now",
                ExpressionAttributeNames={"#owner": "user_id"},
                ExpressionAttributeValues={
                    ":now": moment.isoformat(),
                    ":cutoff": cutoff.isoformat(),
                    ":owner": user_id,
                },
                ConditionExpression=(
                    "attribute_exists(id) AND #owner = :owner "
                    "AND (attribute_not_exists(last_engaged_at) "
                    "OR last_engaged_at < :cutoff)"
                ),
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            _log_dynamodb_error(
                "stamp_folder_engagement",
                e,
                table=USER_FOLDERS_TABLE,
                folder_id=folder_id,
            )
            raise


async def update_folder(folder: Folder) -> Folder:
    """Update a folder in DynamoDB.

    A full ``put_item`` of the model, which is why every attribute stored on a
    folder row has to round-trip through ``Folder`` -- ``last_engaged_at`` included.
    An attribute the model does not know about is erased here, silently, the next
    time the collection is renamed.
    """
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_FOLDERS_TABLE)
            await table.put_item(Item=folder.to_dynamodb_item())
            _log_dynamodb_success(
                "update_folder",
                table=USER_FOLDERS_TABLE,
                folder_id=folder.id,
            )
            return folder
    except ClientError as e:
        _log_dynamodb_error(
            "update_folder",
            e,
            table=USER_FOLDERS_TABLE,
            folder_id=folder.id,
        )
        raise


async def delete_folder(folder_id: str) -> bool:
    """Delete a folder from DynamoDB."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_FOLDERS_TABLE)
            await table.delete_item(Key={"id": folder_id})
            _log_dynamodb_success(
                "delete_folder",
                table=USER_FOLDERS_TABLE,
                folder_id=folder_id,
            )
            return True
    except ClientError as e:
        _log_dynamodb_error(
            "delete_folder",
            e,
            table=USER_FOLDERS_TABLE,
            folder_id=folder_id,
        )
        raise


# ---------- Tag operations ----------


async def create_tag(tag: Tag) -> Tag:
    """Create a new tag in DynamoDB."""
    session = get_session()
    async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
        table = await dynamodb.Table(USER_TAGS_TABLE)
        try:
            await table.put_item(
                Item=tag.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(id)",
            )
            _log_dynamodb_success(
                "create_tag",
                table=USER_TAGS_TABLE,
                tag_id=tag.id,
                user_id=tag.user_id,
            )
            return tag
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ValueError(f"Tag with ID {tag.id} already exists")
            _log_dynamodb_error(
                "create_tag",
                e,
                table=USER_TAGS_TABLE,
                tag_id=tag.id,
            )
            raise


async def get_tag_by_id(tag_id: str) -> Optional[Tag]:
    """Get a tag by ID."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_TAGS_TABLE)
            response = await table.get_item(Key={"id": tag_id})
            if "Item" in response:
                return Tag.from_dynamodb_item(response["Item"])
            return None
    except ClientError as e:
        _log_dynamodb_error(
            "get_tag_by_id",
            e,
            table=USER_TAGS_TABLE,
            tag_id=tag_id,
        )
        raise


async def get_tags_by_user_id(user_id: str) -> List[Tag]:
    """Get all tags for a user."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_TAGS_TABLE)
            response = await table.query(
                IndexName="user-index",
                KeyConditionExpression=Key("user_id").eq(user_id),
            )
            items = response.get("Items", [])
            return [Tag.from_dynamodb_item(item) for item in items]
    except ClientError as e:
        _log_dynamodb_error(
            "get_tags_by_user_id",
            e,
            table=USER_TAGS_TABLE,
            user_id=user_id,
        )
        raise


async def update_tag(tag: Tag) -> Tag:
    """Update a tag in DynamoDB."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_TAGS_TABLE)
            await table.put_item(Item=tag.to_dynamodb_item())
            _log_dynamodb_success(
                "update_tag",
                table=USER_TAGS_TABLE,
                tag_id=tag.id,
            )
            return tag
    except ClientError as e:
        _log_dynamodb_error(
            "update_tag",
            e,
            table=USER_TAGS_TABLE,
            tag_id=tag.id,
        )
        raise


async def delete_tag(tag_id: str) -> bool:
    """Delete a tag from DynamoDB."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_TAGS_TABLE)
            await table.delete_item(Key={"id": tag_id})
            _log_dynamodb_success(
                "delete_tag",
                table=USER_TAGS_TABLE,
                tag_id=tag_id,
            )
            return True
    except ClientError as e:
        _log_dynamodb_error(
            "delete_tag",
            e,
            table=USER_TAGS_TABLE,
            tag_id=tag_id,
        )
        raise


# ─────────────────────────────────────────────────────────────────────────────
# RSS Feed operations
# ─────────────────────────────────────────────────────────────────────────────


async def create_rss_feed(feed: UserRssFeed) -> UserRssFeed:
    """Create a new RSS feed subscription in DynamoDB."""
    session = get_session()
    async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
        table = await dynamodb.Table(USER_RSS_FEEDS_TABLE)
        try:
            await table.put_item(
                Item=feed.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(id)",
            )
            _log_dynamodb_success(
                "create_rss_feed",
                table=USER_RSS_FEEDS_TABLE,
                feed_id=feed.id,
                user_id=feed.user_id,
            )
            return feed
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ValueError(f"RSS feed with ID {feed.id} already exists")
            _log_dynamodb_error(
                "create_rss_feed",
                e,
                table=USER_RSS_FEEDS_TABLE,
                feed_id=feed.id,
            )
            raise


async def get_rss_feed_by_id(feed_id: str) -> Optional[UserRssFeed]:
    """Get an RSS feed subscription by ID."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_RSS_FEEDS_TABLE)
            response = await table.get_item(Key={"id": feed_id})
            if "Item" in response:
                return UserRssFeed.from_dynamodb_item(response["Item"])
            return None
    except ClientError as e:
        _log_dynamodb_error(
            "get_rss_feed_by_id",
            e,
            table=USER_RSS_FEEDS_TABLE,
            feed_id=feed_id,
        )
        raise


async def get_rss_feeds_by_user_id(user_id: str) -> List[UserRssFeed]:
    """Get all RSS feed subscriptions for a user."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_RSS_FEEDS_TABLE)
            response = await table.query(
                IndexName="user-index",
                KeyConditionExpression=Key("user_id").eq(user_id),
            )
            items = response.get("Items", [])
            return [UserRssFeed.from_dynamodb_item(item) for item in items]
    except ClientError as e:
        _log_dynamodb_error(
            "get_rss_feeds_by_user_id",
            e,
            table=USER_RSS_FEEDS_TABLE,
            user_id=user_id,
        )
        raise


async def get_active_rss_feeds() -> List[UserRssFeed]:
    """Get all active RSS feed subscriptions (for polling worker).

    Uses a GSI on status to efficiently retrieve only active feeds.
    Falls back to a full scan with filter if the index does not exist.
    """
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_RSS_FEEDS_TABLE)
            try:
                response = await table.query(
                    IndexName="status-index",
                    KeyConditionExpression=Key("status").eq("active"),
                )
            except ClientError as idx_err:
                if idx_err.response["Error"]["Code"] == "ValidationException":
                    # Fallback: scan with filter
                    from boto3.dynamodb.conditions import Attr

                    response = await table.scan(
                        FilterExpression=Attr("status").eq("active"),
                    )
                else:
                    raise
            items = response.get("Items", [])
            return [UserRssFeed.from_dynamodb_item(item) for item in items]
    except ClientError as e:
        _log_dynamodb_error(
            "get_active_rss_feeds",
            e,
            table=USER_RSS_FEEDS_TABLE,
        )
        raise


async def update_rss_feed(feed: UserRssFeed) -> UserRssFeed:
    """Update an RSS feed subscription in DynamoDB."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_RSS_FEEDS_TABLE)
            await table.put_item(Item=feed.to_dynamodb_item())
            _log_dynamodb_success(
                "update_rss_feed",
                table=USER_RSS_FEEDS_TABLE,
                feed_id=feed.id,
            )
            return feed
    except ClientError as e:
        _log_dynamodb_error(
            "update_rss_feed",
            e,
            table=USER_RSS_FEEDS_TABLE,
            feed_id=feed.id,
        )
        raise


async def delete_rss_feed(feed_id: str) -> bool:
    """Delete an RSS feed subscription from DynamoDB."""
    try:
        session = get_session()
        async with session.resource("dynamodb", **_dynamodb_client_kwargs()) as dynamodb:
            table = await dynamodb.Table(USER_RSS_FEEDS_TABLE)
            await table.delete_item(Key={"id": feed_id})
            _log_dynamodb_success(
                "delete_rss_feed",
                table=USER_RSS_FEEDS_TABLE,
                feed_id=feed_id,
            )
            return True
    except ClientError as e:
        _log_dynamodb_error(
            "delete_rss_feed",
            e,
            table=USER_RSS_FEEDS_TABLE,
            feed_id=feed_id,
        )
        raise
