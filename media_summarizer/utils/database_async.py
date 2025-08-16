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

from media_summarizer.core.models import User, CreditTransaction, ProcessingJob, JobStatus

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
CREDIT_TRANSACTIONS_TABLE = os.environ.get("CREDIT_TRANSACTIONS_TABLE", "credit_transactions")
PROCESSING_JOBS_TABLE = os.environ.get("PROCESSING_JOBS_TABLE", "processing_jobs")

# Session aioboto3 for async operations (created lazily)
_session = None

def get_session():
    """Get or create aioboto3 session with current environment variables."""
    global _session
    if _session is None:
        _session = aioboto3.Session(
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
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
        return get_session().client(
            'dynamodb',
            endpoint_url=self.endpoint_url,
            region_name=self.region_name
        )

    async def get_resource(self):
        """Return an async DynamoDB resource."""
        return get_session().resource(
            'dynamodb',
            endpoint_url=self.endpoint_url,
            region_name=self.region_name
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
        client = await session.client('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aenter__()
        try:
            await client.describe_table(TableName=table_name)
            return True
        finally:
            await session.client('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aexit__(None, None, None)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            return False
        raise


# User operations
async def create_user(user: User) -> User:
    """Create a new user in DynamoDB."""
    session = get_session()
    dynamodb = await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aenter__()
    try:
        table = await dynamodb.Table(USERS_TABLE)
        try:
            await table.put_item(
                Item=user.to_dynamodb_item(),
                ConditionExpression='attribute_not_exists(id)'
            )
            logger.info(f"User created: {user.id}")
            return user
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ValueError(f"User with ID {user.id} already exists")
            logger.error(f"Error creating user: {str(e)}")
            raise
    finally:
        await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aexit__(None, None, None)


async def get_user_by_id(user_id: str) -> Optional[User]:
    """Get a user by ID."""
    session = get_session()
    dynamodb = await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aenter__()
    try:
        table = await dynamodb.Table(USERS_TABLE)
        try:
            response = await table.get_item(Key={'id': user_id})
            if 'Item' in response:
                return User.from_dynamodb_item(response['Item'])
            return None
        except ClientError as e:
            logger.error(f"Error getting user by ID {user_id}: {str(e)}")
            raise
    finally:
        await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aexit__(None, None, None)


async def get_user_by_email(email: str) -> Optional[User]:
    """Get a user by email."""
    session = get_session()
    dynamodb = await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aenter__()
    try:
        table = await dynamodb.Table(USERS_TABLE)
        try:
            response = await table.query(
                IndexName='email-index',
                KeyConditionExpression=Key('email').eq(email)
            )
            items = response.get('Items', [])
            if items:
                return User.from_dynamodb_item(items[0])
            return None
        except ClientError as e:
            logger.error(f"Error getting user by email {email}: {str(e)}")
            raise
    finally:
        await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aexit__(None, None, None)


async def update_user(user: User) -> User:
    """Update a user in DynamoDB."""
    session = get_session()
    dynamodb = await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aenter__()
    try:
        table = await dynamodb.Table(USERS_TABLE)
        try:
            await table.put_item(Item=user.to_dynamodb_item())
            logger.info(f"User updated: {user.id}")
            return user
        except ClientError as e:
            logger.error(f"Error updating user {user.id}: {str(e)}")
            raise
    finally:
        await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aexit__(None, None, None)


async def delete_user(user_id: str) -> bool:
    """Delete a user from DynamoDB."""
    session = get_session()
    dynamodb = await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aenter__()
    try:
        table = await dynamodb.Table(USERS_TABLE)
        try:
            await table.delete_item(Key={'id': user_id})
            logger.info(f"User deleted: {user_id}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting user {user_id}: {str(e)}")
            raise
    finally:
        await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aexit__(None, None, None)


async def update_user_credits(user_id: str, credits: int) -> Optional[User]:
    """Update user credits."""
    session = get_session()
    dynamodb = await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aenter__()
    try:
        table = await dynamodb.Table(USERS_TABLE)
        try:
            response = await table.update_item(
                Key={'id': user_id},
                UpdateExpression='SET credits = :credits',
                ExpressionAttributeValues={':credits': credits},
                ReturnValues='ALL_NEW'
            )
            if 'Attributes' in response:
                return User.from_dynamodb_item(response['Attributes'])
            return None
        except ClientError as e:
            logger.error(f"Error updating user credits for {user_id}: {str(e)}")
            raise
    finally:
        await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aexit__(None, None, None)


# Credit transaction operations
async def create_credit_transaction(transaction: CreditTransaction) -> CreditTransaction:
    """Create a new credit transaction in DynamoDB."""
    session = get_session()
    dynamodb = await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aenter__()
    try:
        table = await dynamodb.Table(CREDIT_TRANSACTIONS_TABLE)
        try:
            await table.put_item(
                Item=transaction.to_dynamodb_item(),
                ConditionExpression='attribute_not_exists(id)'
            )
            logger.info(f"Credit transaction created: {transaction.id}")
            return transaction
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ValueError(f"Credit transaction with ID {transaction.id} already exists")
            logger.error(f"Error creating credit transaction: {str(e)}")
            raise
    finally:
        await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aexit__(None, None, None)


async def get_credit_transaction_by_id(transaction_id: str) -> Optional[CreditTransaction]:
    """Get a credit transaction by ID."""
    session = get_session()
    dynamodb = await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aenter__()
    try:
        table = await dynamodb.Table(CREDIT_TRANSACTIONS_TABLE)
        try:
            response = await table.get_item(Key={'id': transaction_id})
            if 'Item' in response:
                return CreditTransaction.from_dynamodb_item(response['Item'])
            return None
        except ClientError as e:
            logger.error(f"Error getting credit transaction by ID {transaction_id}: {str(e)}")
            raise
    finally:
        await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aexit__(None, None, None)


async def get_credit_transactions_by_user_id(user_id: str) -> List[CreditTransaction]:
    """Get all credit transactions for a user."""
    session = get_session()
    dynamodb = await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aenter__()
    try:
        table = await dynamodb.Table(CREDIT_TRANSACTIONS_TABLE)
        try:
            response = await table.query(
                IndexName='user-index',
                KeyConditionExpression=Key('user_id').eq(user_id)
            )
            items = response.get('Items', [])
            return [CreditTransaction.from_dynamodb_item(item) for item in items]
        except ClientError as e:
            logger.error(f"Error getting credit transactions by user ID {user_id}: {str(e)}")
            raise
    finally:
        await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aexit__(None, None, None)


# Processing job operations
async def create_processing_job(job: ProcessingJob) -> ProcessingJob:
    """Create a new processing job in DynamoDB."""
    session = get_session()
    dynamodb = await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aenter__()
    try:
        table = await dynamodb.Table(PROCESSING_JOBS_TABLE)
        try:
            await table.put_item(
                Item=job.to_dynamodb_item(),
                ConditionExpression='attribute_not_exists(id)'
            )
            logger.info(f"Processing job created: {job.id}")
            return job
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise ValueError(f"Processing job with ID {job.id} already exists")
            logger.error(f"Error creating processing job: {str(e)}")
            raise
    finally:
        await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aexit__(None, None, None)


async def get_processing_job_by_id(job_id: str) -> Optional[ProcessingJob]:
    """Get a processing job by ID."""
    session = get_session()
    dynamodb = await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aenter__()
    try:
        table = await dynamodb.Table(PROCESSING_JOBS_TABLE)
        try:
            response = await table.get_item(Key={'id': job_id})
            if 'Item' in response:
                return ProcessingJob.from_dynamodb_item(response['Item'])
            return None
        except ClientError as e:
            logger.error(f"Error getting processing job by ID {job_id}: {str(e)}")
            raise
    finally:
        await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aexit__(None, None, None)


async def get_processing_jobs_by_user_id(user_id: str) -> List[ProcessingJob]:
    """Get all processing jobs for a user."""
    session = get_session()
    dynamodb = await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aenter__()
    try:
        table = await dynamodb.Table(PROCESSING_JOBS_TABLE)
        try:
            response = await table.query(
                IndexName='user-index',
                KeyConditionExpression=Key('user_id').eq(user_id)
            )
            items = response.get('Items', [])
            return [ProcessingJob.from_dynamodb_item(item) for item in items]
        except ClientError as e:
            logger.error(f"Error getting processing jobs by user ID {user_id}: {str(e)}")
            raise
    finally:
        await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aexit__(None, None, None)


async def get_processing_jobs_by_status(status: JobStatus) -> List[ProcessingJob]:
    """Get all processing jobs with a specific status."""
    session = get_session()
    dynamodb = await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aenter__()
    try:
        table = await dynamodb.Table(PROCESSING_JOBS_TABLE)
        try:
            response = await table.query(
                IndexName='status-index',
                KeyConditionExpression=Key('job_status').eq(status.value)
            )
            items = response.get('Items', [])
            return [ProcessingJob.from_dynamodb_item(item) for item in items]
        except ClientError as e:
            logger.error(f"Error getting processing jobs by status {status}: {str(e)}")
            raise
    finally:
        await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aexit__(None, None, None)


async def update_processing_job(job: ProcessingJob) -> ProcessingJob:
    """Update a processing job in DynamoDB."""
    session = get_session()
    dynamodb = await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aenter__()
    try:
        table = await dynamodb.Table(PROCESSING_JOBS_TABLE)
        try:
            await table.put_item(Item=job.to_dynamodb_item())
            logger.info(f"Processing job updated: {job.id}")
            return job
        except ClientError as e:
            logger.error(f"Error updating processing job {job.id}: {str(e)}")
            raise
    finally:
        await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aexit__(None, None, None)


async def delete_processing_job(job_id: str) -> bool:
    """Delete a processing job from DynamoDB."""
    session = get_session()
    dynamodb = await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aenter__()
    try:
        table = await dynamodb.Table(PROCESSING_JOBS_TABLE)
        try:
            await table.delete_item(Key={'id': job_id})
            logger.info(f"Processing job deleted: {job_id}")
            return True
        except ClientError as e:
            logger.error(f"Error deleting processing job {job_id}: {str(e)}")
            raise
    finally:
        await session.resource('dynamodb', endpoint_url=AWS_ENDPOINT_URL, region_name=AWS_REGION).__aexit__(None, None, None)
