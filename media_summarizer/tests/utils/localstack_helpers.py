"""
Utilities for setting up and interacting with LocalStack for integration tests.
"""
import os
import pytest
import boto3
import pytest_asyncio
import aioboto3
from unittest.mock import AsyncMock
from typing import List, Dict, Any

# Default AWS configuration for LocalStack
AWS_ENDPOINT_URL = "http://localhost:4566"
AWS_REGION = "us-east-1"
AWS_ACCESS_KEY_ID = "test"
AWS_SECRET_ACCESS_KEY = "test"

# Default resource names
SQS_QUEUES = [
    "audio-download-queue",
    "transcription-queue",
    "summarization-queue",
    "email-notification-queue"
]

S3_BUCKETS = [
    "media-summarizer-audio",
    "media-summarizer-transcriptions",
    "media-summarizer-summaries"
]

# DynamoDB tables
DYNAMODB_TABLES = {
    "users": {
        "KeySchema": [
            {"AttributeName": "id", "KeyType": "HASH"}
        ],
        "AttributeDefinitions": [
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "email", "AttributeType": "S"}
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "email-index",
                "KeySchema": [
                    {"AttributeName": "email", "KeyType": "HASH"}
                ],
                "Projection": {
                    "ProjectionType": "ALL"
                },
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5
                }
            }
        ],
        "ProvisionedThroughput": {
            "ReadCapacityUnits": 5,
            "WriteCapacityUnits": 5
        }
    },
    "credit_transactions": {
        "KeySchema": [
            {"AttributeName": "id", "KeyType": "HASH"}
        ],
        "AttributeDefinitions": [
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"}
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "user-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"}
                ],
                "Projection": {
                    "ProjectionType": "ALL"
                },
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5
                }
            }
        ],
        "ProvisionedThroughput": {
            "ReadCapacityUnits": 5,
            "WriteCapacityUnits": 5
        }
    },
    "processing_jobs": {
        "KeySchema": [
            {"AttributeName": "id", "KeyType": "HASH"}
        ],
        "AttributeDefinitions": [
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "job_status", "AttributeType": "S"}
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "user-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"}
                ],
                "Projection": {
                    "ProjectionType": "ALL"
                },
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5
                }
            },
            {
                "IndexName": "status-index",
                "KeySchema": [
                    {"AttributeName": "job_status", "KeyType": "HASH"}
                ],
                "Projection": {
                    "ProjectionType": "ALL"
                },
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5
                }
            }
        ],
        "ProvisionedThroughput": {
            "ReadCapacityUnits": 5,
            "WriteCapacityUnits": 5
        }
    },
    "auth_tokens": {
        "KeySchema": [
            {"AttributeName": "id", "KeyType": "HASH"}
        ],
        "AttributeDefinitions": [
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "token", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
            {"AttributeName": "token_type", "AttributeType": "S"}
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "token-index",
                "KeySchema": [
                    {"AttributeName": "token", "KeyType": "HASH"}
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
            },
            {
                "IndexName": "user-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"}
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
            },
            {
                "IndexName": "user-type-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"},
                    {"AttributeName": "token_type", "KeyType": "RANGE"}
                ],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
            }
        ],
        "ProvisionedThroughput": {
            "ReadCapacityUnits": 5,
            "WriteCapacityUnits": 5
        }
    },
    "user_folders": {
        "KeySchema": [
            {"AttributeName": "id", "KeyType": "HASH"}
        ],
        "AttributeDefinitions": [
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"}
        ],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "user-index",
                "KeySchema": [
                    {"AttributeName": "user_id", "KeyType": "HASH"}
                ],
                "Projection": {
                    "ProjectionType": "ALL"
                },
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5
                }
            }
        ],
        "ProvisionedThroughput": {
            "ReadCapacityUnits": 5,
            "WriteCapacityUnits": 5
        }
    }
}


def setup_localstack_resources():
    """
    Set up the necessary resources in LocalStack for testing.
    This includes creating SQS queues, S3 buckets, and DynamoDB tables.
    """
    # Create SQS client
    sqs = boto3.client(
        'sqs',
        endpoint_url=AWS_ENDPOINT_URL,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    # Create S3 client
    s3 = boto3.client(
        's3',
        endpoint_url=AWS_ENDPOINT_URL,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    # Create DynamoDB client
    dynamodb = boto3.client(
        'dynamodb',
        endpoint_url=AWS_ENDPOINT_URL,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    # Create SQS queues
    for queue_name in SQS_QUEUES:
        try:
            sqs.create_queue(QueueName=queue_name)
            print(f"Created SQS queue: {queue_name}")
        except Exception as e:
            print(f"Error creating SQS queue {queue_name}: {str(e)}")

    # Create S3 buckets
    for bucket_name in S3_BUCKETS:
        try:
            s3.create_bucket(Bucket=bucket_name)
            print(f"Created S3 bucket: {bucket_name}")
        except Exception as e:
            print(f"Error creating S3 bucket {bucket_name}: {str(e)}")

    # Create DynamoDB tables
    for table_name, table_config in DYNAMODB_TABLES.items():
        try:
            # Check if table already exists
            try:
                dynamodb.describe_table(TableName=table_name)
                print(f"DynamoDB table {table_name} already exists")
                continue
            except dynamodb.exceptions.ResourceNotFoundException:
                pass

            # Create the table
            dynamodb.create_table(
                TableName=table_name,
                **table_config
            )
            print(f"Created DynamoDB table: {table_name}")

            # Wait for the table to be active
            waiter = dynamodb.get_waiter('table_exists')
            waiter.wait(TableName=table_name)

        except Exception as e:
            print(f"Error creating DynamoDB table {table_name}: {str(e)}")

    # Create SES client and verify email identities
    ses = boto3.client(
        'ses',
        endpoint_url=AWS_ENDPOINT_URL,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    # Verify email identities for LocalStack SES
    email_identities = ["noreply@media-summarizer.com", "test@example.com"]
    for email in email_identities:
        try:
            ses.verify_email_identity(EmailAddress=email)
            print(f"Verified SES email identity: {email}")
        except Exception as e:
            print(f"Error verifying SES email identity {email}: {str(e)}")


def clean_localstack_resources():
    """
    Clean up all LocalStack resources.
    This can be used to reset the state between test runs.
    """
    # Create clients
    s3 = boto3.client(
        's3',
        endpoint_url=AWS_ENDPOINT_URL,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    sqs = boto3.client(
        'sqs',
        endpoint_url=AWS_ENDPOINT_URL,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    dynamodb = boto3.client(
        'dynamodb',
        endpoint_url=AWS_ENDPOINT_URL,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )


@pytest.fixture(scope="session")
def setup_localstack():
    """
    Fixture to set up LocalStack resources before running tests.
    """
    # Set environment variables for LocalStack
    os.environ["AWS_ENDPOINT_URL"] = AWS_ENDPOINT_URL
    os.environ["AWS_REGION"] = AWS_REGION
    os.environ["AWS_ACCESS_KEY_ID"] = AWS_ACCESS_KEY_ID
    os.environ["AWS_SECRET_ACCESS_KEY"] = AWS_SECRET_ACCESS_KEY

    # Set up resources
    setup_localstack_resources()

    yield

    # No cleanup needed as LocalStack is ephemeral


def get_sqs_queue_url(queue_name: str) -> str:
    """
    Get the URL for an SQS queue.

    Args:
        queue_name: The name of the queue

    Returns:
        The queue URL
    """
    return f"{AWS_ENDPOINT_URL}/000000000000/{queue_name}"


def send_sqs_message(queue_name: str, message_body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send a message to an SQS queue.

    Args:
        queue_name: The name of the queue
        message_body: The message body as a dictionary

    Returns:
        The response from SQS
    """
    import json

    sqs = boto3.client(
        'sqs',
        endpoint_url=AWS_ENDPOINT_URL,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    queue_url = get_sqs_queue_url(queue_name)

    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message_body)
    )

    return response


def upload_s3_file(bucket_name: str, key: str, file_path: str) -> Dict[str, Any]:
    """
    Upload a file to an S3 bucket.

    Args:
        bucket_name: The name of the bucket
        key: The S3 key for the file
        file_path: The local path to the file

    Returns:
        The response from S3
    """
    s3 = boto3.client(
        's3',
        endpoint_url=AWS_ENDPOINT_URL,
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    response = s3.upload_file(
        Filename=file_path,
        Bucket=bucket_name,
        Key=key
    )

    return response


@pytest.fixture
def localstack_dynamodb_client():
    """
    Create a DynamoDB LocalStack helper client for tests.

    Returns:
        A helper client exposing convenience methods (create_user, get_user, etc.)
    """
    # Import here to avoid circular imports during test discovery
    from media_summarizer.tests.utils.dynamodb_localstack import DynamoDBLocalStackClient

    client = DynamoDBLocalStackClient()
    # Ensure tables exist for tests
    client.setup_tables()

    yield client

    # Clean tables after tests
    try:
        client.clear_tables()
    except Exception as e:
        print(f"Error cleaning up DynamoDB tables: {str(e)}")


@pytest.fixture
def populate_dynamodb_test_data(localstack_dynamodb_client):
    """
    Populate DynamoDB tables with test data.

    Args:
        localstack_dynamodb_client: The DynamoDB client

    Returns:
        A dictionary containing the test data
    """
    # Create test user
    user_id = "test-user-id"
    user_item = {
        'id': {'S': user_id},
        'email': {'S': 'user@example.com'},
        'credits': {'N': '100'}
    }

    # Create test user with no credits
    no_credits_user_id = "no-credits-user-id"
    no_credits_user_item = {
        'id': {'S': no_credits_user_id},
        'email': {'S': 'no-credits@example.com'},
        'credits': {'N': '0'}
    }

    # Create test credit transaction
    transaction_id = "test-txn-id"
    transaction_item = {
        'id': {'S': transaction_id},
        'user_id': {'S': user_id},
        'amount': {'N': '100'},
        'type': {'S': 'purchase'},
        'description': {'S': 'Initial credit purchase'},
        'created_at': {'S': '2023-01-01T00:00:00Z'}
    }

    # Create test job
    job_id = "test-job-id"
    job_item = {
        'id': {'S': job_id},
        'user_id': {'S': user_id},
        'status': {'S': 'completed'},
        'created_at': {'S': '2023-01-01T00:00:00Z'}
    }

    # Put items in tables
    localstack_dynamodb_client.put_item(
        TableName='users',
        Item=user_item
    )

    localstack_dynamodb_client.put_item(
        TableName='users',
        Item=no_credits_user_item
    )

    localstack_dynamodb_client.put_item(
        TableName='credit_transactions',
        Item=transaction_item
    )

    localstack_dynamodb_client.put_item(
        TableName='processing_jobs',
        Item=job_item
    )

    # Return the test data for reference
    return {
        'users': {
            user_id: user_item,
            no_credits_user_id: no_credits_user_item
        },
        'transactions': {
            transaction_id: transaction_item
        },
        'jobs': {
            job_id: job_item
        }
    }

@pytest.fixture(scope="session")
def localstack_session():
    """
    Create a session fixture for LocalStack with proper configuration.

    Returns:
        A boto3 session configured for LocalStack
    """
    import boto3

    # Set environment variables for LocalStack
    os.environ["AWS_ENDPOINT_URL"] = AWS_ENDPOINT_URL
    os.environ["AWS_REGION"] = AWS_REGION
    os.environ["AWS_ACCESS_KEY_ID"] = AWS_ACCESS_KEY_ID
    os.environ["AWS_SECRET_ACCESS_KEY"] = AWS_SECRET_ACCESS_KEY

    # Create a session with LocalStack configuration
    session = boto3.Session(
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    # Set up resources
    setup_localstack_resources()

    yield session


@pytest.fixture
def localstack_s3_client(localstack_session):
    """
    Create an S3 client connected to LocalStack.

    Args:
        localstack_session: The LocalStack session

    Returns:
        A boto3 S3 client
    """
    s3 = localstack_session.client(
        's3',
        endpoint_url=AWS_ENDPOINT_URL
    )

    # Ensure buckets exist
    for bucket_name in S3_BUCKETS:
        try:
            # Check if bucket exists
            try:
                s3.head_bucket(Bucket=bucket_name)
            except s3.exceptions.ClientError:
                # Create the bucket if it doesn't exist
                s3.create_bucket(Bucket=bucket_name)
        except Exception as e:
            print(f"Error ensuring S3 bucket {bucket_name} exists: {str(e)}")

    yield s3

    # Clean up test data after tests
    for bucket_name in S3_BUCKETS:
        try:
            # List all objects in the bucket
            response = s3.list_objects_v2(Bucket=bucket_name)
            if 'Contents' in response:
                # Delete all objects
                objects = [{'Key': obj['Key']} for obj in response['Contents']]
                if objects:
                    s3.delete_objects(
                        Bucket=bucket_name,
                        Delete={'Objects': objects}
                    )
        except Exception as e:
            print(f"Error cleaning up S3 bucket {bucket_name}: {str(e)}")


@pytest.fixture
def localstack_sqs_client(localstack_session):
    """
    Create an SQS client connected to LocalStack.

    Args:
        localstack_session: The LocalStack session

    Returns:
        A boto3 SQS client
    """
    sqs = localstack_session.client(
        'sqs',
        endpoint_url=AWS_ENDPOINT_URL
    )

    # Ensure queues exist
    for queue_name in SQS_QUEUES:
        try:
            # Create the queue (idempotent operation)
            sqs.create_queue(QueueName=queue_name)
        except Exception as e:
            print(f"Error ensuring SQS queue {queue_name} exists: {str(e)}")

    yield sqs

    # Clean up test data after tests
    for queue_name in SQS_QUEUES:
        try:
            # Get queue URL
            queue_url = get_sqs_queue_url(queue_name)

            # Purge the queue
            try:
                sqs.purge_queue(QueueUrl=queue_url)
            except Exception as e:
                print(f"Error purging SQS queue {queue_name}: {str(e)}")
        except Exception as e:
            print(f"Error cleaning up SQS queue {queue_name}: {str(e)}")


@pytest.fixture
def localstack_ses_client(localstack_session):
    """
    Create an SES client connected to LocalStack.

    Args:
        localstack_session: The LocalStack session

    Returns:
        A boto3 SES client
    """
    ses = localstack_session.client(
        'ses',
        endpoint_url=AWS_ENDPOINT_URL
    )

    # Verify email identities
    try:
        ses.verify_email_identity(EmailAddress="noreply@media-summarizer.com")
    except Exception as e:
        print(f"Error verifying email identity: {str(e)}")

    yield ses


@pytest.fixture
def localstack_dynamodb_resource(localstack_session):
    """
    Create a DynamoDB resource connected to LocalStack.

    Args:
        localstack_session: The LocalStack session

    Returns:
        A boto3 DynamoDB resource
    """
    dynamodb = localstack_session.resource(
        'dynamodb',
        endpoint_url=AWS_ENDPOINT_URL
    )

    # Ensure tables exist
    for table_name, table_config in DYNAMODB_TABLES.items():
        try:
            # Check if table exists
            try:
                dynamodb.Table(table_name).table_status
            except dynamodb.meta.client.exceptions.ResourceNotFoundException:
                # Create the table if it doesn't exist
                dynamodb.create_table(
                    TableName=table_name,
                    **table_config
                )
                # Wait for the table to be active
                waiter = dynamodb.meta.client.get_waiter('table_exists')
                waiter.wait(TableName=table_name)
        except Exception as e:
            print(f"Error ensuring DynamoDB table {table_name} exists: {str(e)}")

    yield dynamodb

    # Clean up test data after tests
    for table_name in DYNAMODB_TABLES.keys():
        try:
            table = dynamodb.Table(table_name)

            # Scan all items in the table
            response = table.scan()
            items = response.get('Items', [])

            # Delete all items
            with table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={'id': item['id']})
        except Exception as e:
            print(f"Error cleaning up DynamoDB table {table_name}: {str(e)}")


# Async fixtures for aioboto3
import pytest_asyncio
import aioboto3


@pytest_asyncio.fixture
async def localstack_aioboto3_session():
    """
    Create an aioboto3 session for LocalStack.

    Returns:
        An aioboto3 session configured for LocalStack
    """
    # Set environment variables for LocalStack
    os.environ["AWS_ENDPOINT_URL"] = AWS_ENDPOINT_URL
    os.environ["AWS_REGION"] = AWS_REGION
    os.environ["AWS_ACCESS_KEY_ID"] = AWS_ACCESS_KEY_ID
    os.environ["AWS_SECRET_ACCESS_KEY"] = AWS_SECRET_ACCESS_KEY

    # Create a session with LocalStack configuration
    session = aioboto3.Session(
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )

    yield session


@pytest_asyncio.fixture
async def localstack_aioboto3_s3_client(localstack_aioboto3_session):
    """
    Create an async S3 client connected to LocalStack.

    Args:
        localstack_aioboto3_session: The aioboto3 session

    Returns:
        An async S3 client
    """
    async with localstack_aioboto3_session.client(
        's3',
        endpoint_url=AWS_ENDPOINT_URL
    ) as s3:
        yield s3


@pytest_asyncio.fixture
async def localstack_aioboto3_sqs_client(localstack_aioboto3_session):
    """
    Create an async SQS client connected to LocalStack.

    Args:
        localstack_aioboto3_session: The aioboto3 session

    Returns:
        An async SQS client
    """
    async with localstack_aioboto3_session.client(
        'sqs',
        endpoint_url=AWS_ENDPOINT_URL
    ) as sqs:
        yield sqs


@pytest_asyncio.fixture
async def localstack_aioboto3_dynamodb_resource(localstack_aioboto3_session):
    """
    Create an async DynamoDB resource connected to LocalStack.

    Args:
        localstack_aioboto3_session: The aioboto3 session

    Returns:
        An async DynamoDB resource
    """
    async with localstack_aioboto3_session.resource(
        'dynamodb',
        endpoint_url=AWS_ENDPOINT_URL
    ) as dynamodb:
        yield dynamodb


@pytest_asyncio.fixture
async def localstack_aioboto3_ses_client(localstack_aioboto3_session):
    """
    Create an async SES client connected to LocalStack.

    Args:
        localstack_aioboto3_session: The aioboto3 session

    Returns:
        An async SES client
    """
    async with localstack_aioboto3_session.client(
        'ses',
        endpoint_url=AWS_ENDPOINT_URL
    ) as ses:
        yield ses

class AsyncContextManagerMock:
    """
    A mock for async context managers.

    This class can be used to mock aioboto3 clients that are used with async context managers.
    """
    def __init__(self, mock_obj):
        self.mock_obj = mock_obj

    async def __aenter__(self):
        return self.mock_obj

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def create_aioboto3_mock():
    """
    Create mocks for aioboto3 clients.

    Returns:
        A tuple of (mock_s3, mock_sqs, mock_session_client)
    """
    # Create mock clients
    mock_s3 = AsyncMock()
    mock_s3.download_file = AsyncMock()
    mock_s3.put_object = AsyncMock()

    mock_sqs = AsyncMock()
    mock_sqs.send_message = AsyncMock(return_value={"MessageId": "test-message-id"})
    mock_sqs.receive_message = AsyncMock(return_value={"Messages": []})
    mock_sqs.delete_message = AsyncMock()

    # Create a mock for the aioboto3 Session.client method
    def mock_session_client(service_name, **kwargs):
        if service_name == "s3":
            return AsyncContextManagerMock(mock_s3)
        elif service_name == "sqs":
            return AsyncContextManagerMock(mock_sqs)
        return AsyncContextManagerMock(AsyncMock())

    return mock_s3, mock_sqs, mock_session_client
