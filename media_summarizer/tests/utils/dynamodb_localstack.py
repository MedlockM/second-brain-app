"""
DynamoDB LocalStack client utility for integration tests.

This module provides utilities for setting up and interacting with DynamoDB
running in LocalStack for integration tests, as required by the integration
test strategy.
"""
import os
import pytest
import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any, List, Optional
import logging
import time
import uuid

logger = logging.getLogger(__name__)


class DynamoDBLocalStackClient:
    """
    Client for interacting with DynamoDB running in LocalStack.

    This client provides the same interface as boto3 DynamoDB client
    but is specifically configured for LocalStack integration tests.
    """

    def __init__(self):
        self.client = boto3.client(
            "dynamodb",
            endpoint_url=os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test")
        )

        self.resource = boto3.resource(
            "dynamodb",
            endpoint_url=os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566"),
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test")
        )

        # Standard table definitions used in the application
        self.table_definitions = {
            "users": {
                "TableName": "users",
                "KeySchema": [
                    {"AttributeName": "id", "KeyType": "HASH"}
                ],
                "AttributeDefinitions": [
                    {"AttributeName": "id", "AttributeType": "S"}
                ],
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5
                }
            },
            "credit_transactions": {
                "TableName": "credit_transactions",
                "KeySchema": [
                    {"AttributeName": "id", "KeyType": "HASH"}
                ],
                "AttributeDefinitions": [
                    {"AttributeName": "id", "AttributeType": "S"}
                ],
                "ProvisionedThroughput": {
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5
                }
            },
            "processing_jobs": {
                "TableName": "processing_jobs",
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
            "user_folders": {
                "TableName": "user_folders",
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

    def setup_tables(self):
        """Create all required tables for testing."""
        for table_name, table_def in self.table_definitions.items():
            try:
                self.client.create_table(**table_def)
                logger.info(f"Created table: {table_name}")

                # Wait for table to be active
                waiter = self.client.get_waiter('table_exists')
                waiter.wait(TableName=table_name)

            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceInUseException':
                    logger.info(f"Table {table_name} already exists")
                else:
                    logger.error(f"Error creating table {table_name}: {e}")
                    raise

    def teardown_tables(self):
        """Delete all tables after testing."""
        for table_name in self.table_definitions.keys():
            try:
                self.client.delete_table(TableName=table_name)
                logger.info(f"Deleted table: {table_name}")
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    logger.info(f"Table {table_name} does not exist")
                else:
                    logger.error(f"Error deleting table {table_name}: {e}")

    def clear_tables(self):
        """Clear all data from tables without deleting them."""
        for table_name in self.table_definitions.keys():
            try:
                table = self.resource.Table(table_name)

                # Scan and delete all items
                response = table.scan()
                items = response.get('Items', [])

                for item in items:
                    table.delete_item(Key={'id': item['id']})

                logger.info(f"Cleared table: {table_name}")

            except ClientError as e:
                logger.error(f"Error clearing table {table_name}: {e}")

    def is_available(self) -> bool:
        """Check if DynamoDB LocalStack service is available."""
        try:
            self.client.list_tables()
            return True
        except Exception as e:
            logger.error(f"DynamoDB LocalStack not available: {e}")
            return False

    # Convenience methods for common operations
    def create_user(self, user_id: str, email: str, credits: int = 0, **kwargs) -> Dict[str, Any]:
        """Create a user in the users table."""
        table = self.resource.Table("users")

        user_item = {
            'id': user_id,
            'email': email,
            'credits': credits,
            # Mark users as verified by default for integration tests
            'email_verified_at': kwargs.get('email_verified_at', '2023-01-01T00:00:00Z'),
            'created_at': kwargs.get('created_at', '2023-01-01T00:00:00Z'),
            'updated_at': kwargs.get('updated_at', '2023-01-01T00:00:00Z'),
            **kwargs
        }

        table.put_item(Item=user_item)
        return user_item

    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a user by ID."""
        table = self.resource.Table("users")

        try:
            response = table.get_item(Key={'id': user_id})
            return response.get('Item')
        except ClientError as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return None

    def update_user_credits(self, user_id: str, credits: int) -> bool:
        """Update user credits."""
        table = self.resource.Table("users")

        try:
            table.update_item(
                Key={'id': user_id},
                UpdateExpression='SET credits = :credits, updated_at = :updated_at',
                ExpressionAttributeValues={
                    ':credits': credits,
                    ':updated_at': '2023-01-01T00:00:00Z'
                }
            )
            return True
        except ClientError as e:
            logger.error(f"Error updating user credits {user_id}: {e}")
            return False

    def create_credit_transaction(self, user_id: str, amount: int, transaction_type: str, **kwargs) -> Dict[str, Any]:
        """Create a credit transaction."""
        table = self.resource.Table("credit_transactions")

        transaction_item = {
            'id': str(uuid.uuid4()),
            'user_id': user_id,
            'amount': amount,
            'type': transaction_type,
            'created_at': kwargs.get('created_at', '2023-01-01T00:00:00Z'),
            **kwargs
        }

        table.put_item(Item=transaction_item)
        return transaction_item

    def get_user_transactions(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all credit transactions for a user."""
        table = self.resource.Table("credit_transactions")

        try:
            response = table.scan(
                FilterExpression='user_id = :user_id',
                ExpressionAttributeValues={':user_id': user_id}
            )
            return response.get('Items', [])
        except ClientError as e:
            logger.error(f"Error getting user transactions {user_id}: {e}")
            return []

    def create_podcast_job(self, user_id: str, podcast_url: str, status: str = "pending", **kwargs) -> Dict[str, Any]:
        """Create a podcast job."""
        table = self.resource.Table("processing_jobs")

        job_item = {
            'id': str(uuid.uuid4()),
            'user_id': user_id,
            'podcast_url': podcast_url,
            'status': status,
            'created_at': kwargs.get('created_at', '2023-01-01T00:00:00Z'),
            'updated_at': kwargs.get('updated_at', '2023-01-01T00:00:00Z'),
            **kwargs
        }

        table.put_item(Item=job_item)
        return job_item

    def get_podcast_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a podcast job by ID."""
        table = self.resource.Table("processing_jobs")

        try:
            response = table.get_item(Key={'id': job_id})
            return response.get('Item')
        except ClientError as e:
            logger.error(f"Error getting podcast job {job_id}: {e}")
            return None

    def update_job_status(self, job_id: str, status: str, **kwargs) -> bool:
        """Update job status."""
        table = self.resource.Table("processing_jobs")

        try:
            update_expression = 'SET #status = :status, updated_at = :updated_at'
            expression_values = {
                ':status': status,
                ':updated_at': '2023-01-01T00:00:00Z'
            }
            expression_attribute_names = {'#status': 'status'}

            # Add any additional fields using expression attribute names to avoid reserved keywords
            for key, value in kwargs.items():
                attr_name = f'#{key}'
                attr_value = f':{key}'
                update_expression += f', {attr_name} = {attr_value}'
                expression_values[attr_value] = value
                expression_attribute_names[attr_name] = key

            table.update_item(
                Key={'id': job_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attribute_names,
                ExpressionAttributeValues=expression_values
            )
            return True
        except ClientError as e:
            logger.error(f"Error updating job status {job_id}: {e}")
            return False


# Factory functions for different use cases
def create_dynamodb_localstack_client() -> DynamoDBLocalStackClient:
    """Create a DynamoDB LocalStack client."""
    return DynamoDBLocalStackClient()


# Pytest fixtures
@pytest.fixture
def dynamodb_localstack_client():
    """Create a DynamoDB LocalStack client fixture."""
    client = DynamoDBLocalStackClient()

    # Skip test if LocalStack is not available
    if not client.is_available():
        pytest.skip("DynamoDB LocalStack service not available")

    # Set up tables
    client.setup_tables()

    yield client

    # Clean up
    client.clear_tables()
