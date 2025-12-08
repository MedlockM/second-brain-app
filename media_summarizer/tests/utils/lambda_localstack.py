"""
Utilities for deploying and testing Lambda functions with LocalStack.
"""
import os
import json
import zipfile
import tempfile
import shutil
import boto3
import pytest
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

# LocalStack configuration
AWS_ENDPOINT_URL = "http://localhost:4566"
AWS_REGION = "us-east-1"
AWS_ACCESS_KEY_ID = "test"
AWS_SECRET_ACCESS_KEY = "test"


class LambdaLocalStackClient:
    """
    Client for deploying and testing Lambda functions in LocalStack.
    """

    def __init__(self):
        self.lambda_client = boto3.client(
            'lambda',
            endpoint_url=AWS_ENDPOINT_URL,
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )
        
        self.sqs_client = boto3.client(
            'sqs',
            endpoint_url=AWS_ENDPOINT_URL,
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )

    def create_lambda_package(self, worker_module: str, function_name: str) -> str:
        """
        Create a deployment package for a Lambda function.
        
        Args:
            worker_module: Python module path (e.g., 'media_summarizer.workers.spotify_sync.worker')
            function_name: Name for the Lambda function
            
        Returns:
            Path to the created zip file
        """
        # Create zip file in a more secure location
        temp_zip = tempfile.NamedTemporaryFile(suffix='.zip', delete=False)
        zip_path = temp_zip.name
        temp_zip.close()
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                package_dir = Path(temp_dir) / "package"
                package_dir.mkdir()
                
                # Copy the entire media_summarizer package
                project_root = Path(__file__).parent.parent.parent.parent
                source_dir = project_root / "media_summarizer"
                dest_dir = package_dir / "media_summarizer"
                
                if not source_dir.exists():
                    raise FileNotFoundError(f"Source directory not found: {source_dir}")
                
                shutil.copytree(
                    source_dir, 
                    dest_dir, 
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.pyo', '.pytest_cache')
                )
                
                # Create the zip file
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
                    for root, dirs, files in os.walk(package_dir):
                        for file in files:
                            file_path = Path(root) / file
                            arcname = file_path.relative_to(package_dir)
                            zipf.write(file_path, arcname)
                
                return zip_path
        except Exception:
            # Clean up on error
            if os.path.exists(zip_path):
                os.unlink(zip_path)
            raise

    def deploy_lambda_function(
        self, 
        function_name: str, 
        handler: str, 
        zip_path: str,
        environment_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Deploy a Lambda function to LocalStack.
        
        Args:
            function_name: Name of the Lambda function
            handler: Handler function (e.g., 'media_summarizer.workers.spotify_sync.worker.lambda_handler')
            zip_path: Path to the deployment package
            environment_vars: Environment variables for the function
            
        Returns:
            Lambda function configuration
        """
        try:
            # Check if function exists
            try:
                self.lambda_client.get_function(FunctionName=function_name)
                # Update existing function
                with open(zip_path, 'rb') as zip_file:
                    response = self.lambda_client.update_function_code(
                        FunctionName=function_name,
                        ZipFile=zip_file.read()
                    )
                logger.info(f"Updated Lambda function: {function_name}")
                return response
            except self.lambda_client.exceptions.ResourceNotFoundException:
                pass
            
            # Create new function
            with open(zip_path, 'rb') as zip_file:
                response = self.lambda_client.create_function(
                    FunctionName=function_name,
                    Runtime='python3.12',
                    Role='arn:aws:iam::000000000000:role/lambda-execution-role',
                    Handler=handler,
                    Code={'ZipFile': zip_file.read()},
                    Timeout=300,
                    Environment={
                        'Variables': environment_vars or {}
                    }
                )
            
            logger.info(f"Created Lambda function: {function_name}")
            return response
            
        except Exception as e:
            logger.error(f"Error deploying Lambda function {function_name}: {e}")
            raise

    def invoke_lambda_function(
        self, 
        function_name: str, 
        payload: Dict[str, Any],
        invocation_type: str = 'RequestResponse'
    ) -> Dict[str, Any]:
        """
        Invoke a Lambda function.
        
        Args:
            function_name: Name of the Lambda function
            payload: Payload to send to the function
            invocation_type: 'RequestResponse' (sync) or 'Event' (async)
            
        Returns:
            Lambda invocation response
        """
        try:
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType=invocation_type,
                Payload=json.dumps(payload)
            )
            
            if invocation_type == 'RequestResponse':
                # Read the response payload
                response_payload = response['Payload'].read()
                if response_payload:
                    response['ResponsePayload'] = json.loads(response_payload)
            
            return response
            
        except Exception as e:
            logger.error(f"Error invoking Lambda function {function_name}: {e}")
            raise

    def create_sqs_event_payload(self, queue_name: str, message_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create an SQS event payload for Lambda testing.
        
        Args:
            queue_name: Name of the SQS queue
            message_body: Message body
            
        Returns:
            SQS event payload for Lambda
        """
        return {
            "Records": [
                {
                    "messageId": "test-message-id",
                    "receiptHandle": "test-receipt-handle",
                    "body": json.dumps(message_body),
                    "attributes": {
                        "ApproximateReceiveCount": "1",
                        "SentTimestamp": "1545082649183",
                        "SenderId": "AIDAIENQZJOLO23YVJ4VO",
                        "ApproximateFirstReceiveTimestamp": "1545082649185"
                    },
                    "messageAttributes": {},
                    "md5OfBody": "test-md5",
                    "eventSource": "aws:sqs",
                    "eventSourceARN": f"arn:aws:sqs:us-east-1:000000000000:{queue_name}",
                    "awsRegion": "us-east-1"
                }
            ]
        }

    def send_sqs_message_and_wait_for_lambda(
        self, 
        queue_name: str, 
        message_body: Dict[str, Any],
        function_name: str,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Send an SQS message and wait for Lambda to process it.
        
        Args:
            queue_name: Name of the SQS queue
            message_body: Message body
            function_name: Lambda function name to monitor
            timeout: Timeout in seconds
            
        Returns:
            Lambda execution result
        """
        # Send message to SQS
        queue_url = f"{AWS_ENDPOINT_URL}/000000000000/{queue_name}"
        self.sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message_body)
        )
        
        # For LocalStack, we need to manually trigger the Lambda
        # since event source mapping might not work perfectly
        sqs_event = self.create_sqs_event_payload(queue_name, message_body)
        return self.invoke_lambda_function(function_name, sqs_event)

    def get_lambda_logs(self, function_name: str) -> List[str]:
        """
        Get logs for a Lambda function (LocalStack specific).
        
        Args:
            function_name: Name of the Lambda function
            
        Returns:
            List of log entries
        """
        # In LocalStack, logs are typically available through CloudWatch Logs
        # For testing purposes, we'll return a placeholder
        return [f"Logs for {function_name} - check LocalStack container logs"]

    def cleanup_lambda_function(self, function_name: str):
        """
        Delete a Lambda function.
        
        Args:
            function_name: Name of the Lambda function to delete
        """
        try:
            self.lambda_client.delete_function(FunctionName=function_name)
            logger.info(f"Deleted Lambda function: {function_name}")
        except self.lambda_client.exceptions.ResourceNotFoundException:
            logger.info(f"Lambda function {function_name} does not exist")
        except Exception as e:
            logger.error(f"Error deleting Lambda function {function_name}: {e}")


# Pytest fixtures
@pytest.fixture
def lambda_localstack_client():
    """Create a Lambda LocalStack client fixture."""
    return LambdaLocalStackClient()


@pytest.fixture
def deployed_spotify_sync_lambda(lambda_localstack_client):
    """Deploy the Spotify Sync Lambda function for testing."""
    function_name = "test-spotify-sync-worker"
    handler = "media_summarizer.workers.spotify_sync.worker.lambda_handler"
    
    # Create deployment package
    zip_path = lambda_localstack_client.create_lambda_package(
        "media_summarizer.workers.spotify_sync.worker",
        function_name
    )
    
    # Environment variables
    env_vars = {
        "AWS_ENDPOINT_URL": AWS_ENDPOINT_URL,
        "AWS_REGION": AWS_REGION,
        "USERS_TABLE": "users",
        "SPOTIFY_FOLLOWS_TABLE": "spotify_playlist_follows",
        "PROCESSING_JOBS_TABLE": "processing_jobs",
        "AUDIO_DOWNLOAD_QUEUE": "audio-download-queue"
    }
    
    # Deploy function
    response = lambda_localstack_client.deploy_lambda_function(
        function_name, handler, zip_path, env_vars
    )
    
    yield {
        "function_name": function_name,
        "handler": handler,
        "response": response
    }
    
    # Cleanup
    lambda_localstack_client.cleanup_lambda_function(function_name)
    
    # Clean up zip file
    if os.path.exists(zip_path):
        os.remove(zip_path)


# Helper functions for testing
def create_test_spotify_sync_message(user_id: str, playlist_ids: List[str]) -> Dict[str, Any]:
    """Create a test message for Spotify sync."""
    return {
        "user_id": user_id,
        "playlist_ids": playlist_ids,
        "source": "test"
    }


def assert_lambda_success(response: Dict[str, Any]):
    """Assert that a Lambda invocation was successful."""
    assert response['StatusCode'] == 200
    assert 'ResponsePayload' in response
    
    payload = response['ResponsePayload']
    assert payload['statusCode'] == 200
    
    body = json.loads(payload['body'])
    assert 'processed' in body
    assert body['processed'] > 0


def assert_lambda_error(response: Dict[str, Any], expected_error: str = None):
    """Assert that a Lambda invocation resulted in an error."""
    assert response['StatusCode'] == 200  # Lambda executed
    
    if 'ResponsePayload' in response:
        payload = response['ResponsePayload']
        if 'errorMessage' in payload:
            if expected_error:
                assert expected_error in payload['errorMessage']
        else:
            # Check if the business logic returned an error
            body = json.loads(payload.get('body', '{}'))
            results = body.get('results', [])
            if results:
                assert any(result.get('status') == 'error' for result in results)