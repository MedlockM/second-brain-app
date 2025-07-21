"""
Queue adapter for Media Summarizer.

This adapter provides an interface for interacting with message queues (SQS).
It handles message sending, receiving, and error handling.
"""
import json
import logging
import os
from typing import Dict, Any, Optional, List, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")

# Import AWS session
try:
    from aiobotocore.session import get_session
    session = get_session()
except ImportError:
    logger.error("aiobotocore is not installed. Please install it with 'pip install aiobotocore'.")
    raise

# Queue configuration
DEFAULT_QUEUE_PREFIX = os.environ.get("DEFAULT_QUEUE_PREFIX", "media-summarizer-")


class QueueAdapter:
    """
    Adapter for interacting with message queues (SQS).
    """
    
    def __init__(self, region_name: Optional[str] = None, endpoint_url: Optional[str] = None):
        """
        Initialize the queue adapter.
        
        Args:
            region_name: AWS region name (optional, defaults to AWS_REGION)
            endpoint_url: AWS endpoint URL (optional, defaults to AWS_ENDPOINT_URL)
        """
        self.region_name = region_name or AWS_REGION
        self.endpoint_url = endpoint_url or AWS_ENDPOINT_URL
        self.session = get_session()
    
    def get_queue_url(self, queue_name: str) -> str:
        """
        Get the URL for a queue.
        
        Args:
            queue_name: Name of the queue
            
        Returns:
            Queue URL
        """
        # For local development with LocalStack
        if self.endpoint_url:
            return f"{self.endpoint_url}/000000000000/{queue_name}"
        
        # For production AWS
        return queue_name
    
    async def send_message(
        self,
        queue_name: str,
        message_body: Union[Dict[str, Any], str],
        delay_seconds: int = 0,
        message_attributes: Optional[Dict[str, Any]] = None,
        sqs_client = None
    ) -> Dict[str, Any]:
        """
        Send a message to a queue.
        
        Args:
            queue_name: Name of the queue
            message_body: Message body (dict or JSON string)
            delay_seconds: Delay in seconds before the message becomes available
            message_attributes: Message attributes (optional)
            sqs_client: SQS client for testing (optional)
            
        Returns:
            Dict containing the response from SQS
            
        Raises:
            ClientError: If there's an error sending the message
        """
        # Convert dict to JSON string if needed
        if isinstance(message_body, dict):
            message_body = json.dumps(message_body)
        
        queue_url = self.get_queue_url(queue_name)
        
        message_params = {
            "QueueUrl": queue_url,
            "MessageBody": message_body,
            "DelaySeconds": delay_seconds
        }
        
        if message_attributes:
            message_params["MessageAttributes"] = message_attributes
        
        # Send the message
        if sqs_client is None:
            async with self.session.create_client(
                "sqs", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as sqs_client:
                response = await sqs_client.send_message(**message_params)
                return response
        else:
            # Use provided client (for testing)
            response = await sqs_client.send_message(**message_params)
            return response
    
    async def receive_messages(
        self,
        queue_name: str,
        max_messages: int = 1,
        wait_time_seconds: int = 0,
        visibility_timeout: int = 30,
        sqs_client = None
    ) -> List[Dict[str, Any]]:
        """
        Receive messages from a queue.
        
        Args:
            queue_name: Name of the queue
            max_messages: Maximum number of messages to receive (1-10)
            wait_time_seconds: Wait time in seconds (0-20)
            visibility_timeout: Visibility timeout in seconds
            sqs_client: SQS client for testing (optional)
            
        Returns:
            List of messages
            
        Raises:
            ClientError: If there's an error receiving messages
        """
        queue_url = self.get_queue_url(queue_name)
        
        receive_params = {
            "QueueUrl": queue_url,
            "MaxNumberOfMessages": max_messages,
            "WaitTimeSeconds": wait_time_seconds,
            "VisibilityTimeout": visibility_timeout
        }
        
        # Receive messages
        if sqs_client is None:
            async with self.session.create_client(
                "sqs", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as sqs_client:
                response = await sqs_client.receive_message(**receive_params)
                return response.get("Messages", [])
        else:
            # Use provided client (for testing)
            response = await sqs_client.receive_message(**receive_params)
            return response.get("Messages", [])
    
    async def delete_message(
        self,
        queue_name: str,
        receipt_handle: str,
        sqs_client = None
    ) -> Dict[str, Any]:
        """
        Delete a message from a queue.
        
        Args:
            queue_name: Name of the queue
            receipt_handle: Receipt handle of the message to delete
            sqs_client: SQS client for testing (optional)
            
        Returns:
            Dict containing the response from SQS
            
        Raises:
            ClientError: If there's an error deleting the message
        """
        queue_url = self.get_queue_url(queue_name)
        
        delete_params = {
            "QueueUrl": queue_url,
            "ReceiptHandle": receipt_handle
        }
        
        # Delete the message
        if sqs_client is None:
            async with self.session.create_client(
                "sqs", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as sqs_client:
                response = await sqs_client.delete_message(**delete_params)
                return response
        else:
            # Use provided client (for testing)
            response = await sqs_client.delete_message(**delete_params)
            return response
    
    async def purge_queue(
        self,
        queue_name: str,
        sqs_client = None
    ) -> Dict[str, Any]:
        """
        Purge all messages from a queue.
        
        Args:
            queue_name: Name of the queue
            sqs_client: SQS client for testing (optional)
            
        Returns:
            Dict containing the response from SQS
            
        Raises:
            ClientError: If there's an error purging the queue
        """
        queue_url = self.get_queue_url(queue_name)
        
        purge_params = {
            "QueueUrl": queue_url
        }
        
        # Purge the queue
        if sqs_client is None:
            async with self.session.create_client(
                "sqs", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as sqs_client:
                response = await sqs_client.purge_queue(**purge_params)
                return response
        else:
            # Use provided client (for testing)
            response = await sqs_client.purge_queue(**purge_params)
            return response
    
    async def get_queue_attributes(
        self,
        queue_name: str,
        attribute_names: List[str] = ["All"],
        sqs_client = None
    ) -> Dict[str, Any]:
        """
        Get attributes of a queue.
        
        Args:
            queue_name: Name of the queue
            attribute_names: List of attribute names to get
            sqs_client: SQS client for testing (optional)
            
        Returns:
            Dict containing the queue attributes
            
        Raises:
            ClientError: If there's an error getting queue attributes
        """
        queue_url = self.get_queue_url(queue_name)
        
        attribute_params = {
            "QueueUrl": queue_url,
            "AttributeNames": attribute_names
        }
        
        # Get queue attributes
        if sqs_client is None:
            async with self.session.create_client(
                "sqs", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as sqs_client:
                response = await sqs_client.get_queue_attributes(**attribute_params)
                return response.get("Attributes", {})
        else:
            # Use provided client (for testing)
            response = await sqs_client.get_queue_attributes(**attribute_params)
            return response.get("Attributes", {})