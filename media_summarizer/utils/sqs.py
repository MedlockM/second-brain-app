"""
SQS utilities for message queue operations.

This module provides async utility functions for interacting
with Amazon SQS in the Media Summarizer application using aiobotocore.
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


def get_queue_url(queue_name: str) -> str:
    """
    Get the URL for a queue.

    Args:
        queue_name: Name of the queue

    Returns:
        Queue URL
    """
    # For local development with LocalStack
    if AWS_ENDPOINT_URL:
        return f"{AWS_ENDPOINT_URL}/000000000000/{queue_name}"

    # For production AWS
    return queue_name


async def send_message(
    queue_name: str,
    message_body: Union[Dict[str, Any], str],
    delay_seconds: int = 0,
    message_attributes: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Send a message to a queue.

    Args:
        queue_name: Name of the queue
        message_body: Message body (dict or JSON string)
        delay_seconds: Delay in seconds before the message becomes available
        message_attributes: Message attributes (optional)

    Returns:
        Dict containing the response from SQS

    Raises:
        Exception: If there's an error sending the message
    """
    # Convert dict to JSON string if needed
    if isinstance(message_body, dict):
        message_body = json.dumps(message_body)

    queue_url = get_queue_url(queue_name)

    message_params = {
        "QueueUrl": queue_url,
        "MessageBody": message_body,
        "DelaySeconds": delay_seconds
    }

    if message_attributes:
        message_params["MessageAttributes"] = message_attributes

    try:
        async with session.create_client(
            'sqs',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as sqs:
            response = await sqs.send_message(**message_params)
            logger.info(f"Message sent to queue {queue_name}: {response['MessageId']}")
            return response
    except Exception as e:
        logger.error(f"Error sending message to queue {queue_name}: {str(e)}")
        raise


async def receive_messages(
    queue_name: str,
    max_messages: int = 1,
    wait_time_seconds: int = 0,
    visibility_timeout: int = 30
) -> List[Dict[str, Any]]:
    """
    Receive messages from a queue.

    Args:
        queue_name: Name of the queue
        max_messages: Maximum number of messages to receive (1-10)
        wait_time_seconds: Wait time in seconds (0-20)
        visibility_timeout: Visibility timeout in seconds

    Returns:
        List of messages

    Raises:
        Exception: If there's an error receiving messages
    """
    queue_url = get_queue_url(queue_name)

    receive_params = {
        "QueueUrl": queue_url,
        "MaxNumberOfMessages": max_messages,
        "WaitTimeSeconds": wait_time_seconds,
        "VisibilityTimeout": visibility_timeout
    }

    try:
        async with session.create_client(
            'sqs',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as sqs:
            response = await sqs.receive_message(**receive_params)
            messages = response.get("Messages", [])
            logger.info(f"Received {len(messages)} messages from queue {queue_name}")
            return messages
    except Exception as e:
        logger.error(f"Error receiving messages from queue {queue_name}: {str(e)}")
        raise


async def delete_message(queue_name: str, receipt_handle: str) -> Dict[str, Any]:
    """
    Delete a message from a queue.

    Args:
        queue_name: Name of the queue
        receipt_handle: Receipt handle of the message to delete

    Returns:
        Dict containing the response from SQS

    Raises:
        Exception: If there's an error deleting the message
    """
    queue_url = get_queue_url(queue_name)

    delete_params = {
        "QueueUrl": queue_url,
        "ReceiptHandle": receipt_handle
    }

    try:
        async with session.create_client(
            'sqs',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as sqs:
            response = await sqs.delete_message(**delete_params)
            logger.info(f"Message deleted from queue {queue_name}")
            return response
    except Exception as e:
        logger.error(f"Error deleting message from queue {queue_name}: {str(e)}")
        raise


async def purge_queue(queue_name: str) -> Dict[str, Any]:
    """
    Purge all messages from a queue.

    Args:
        queue_name: Name of the queue

    Returns:
        Dict containing the response from SQS

    Raises:
        Exception: If there's an error purging the queue
    """
    queue_url = get_queue_url(queue_name)

    purge_params = {
        "QueueUrl": queue_url
    }

    try:
        async with session.create_client(
            'sqs',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as sqs:
            response = await sqs.purge_queue(**purge_params)
            logger.info(f"Queue {queue_name} purged")
            return response
    except Exception as e:
        logger.error(f"Error purging queue {queue_name}: {str(e)}")
        raise


async def get_queue_attributes(
    queue_name: str,
    attribute_names: List[str] = ["All"]
) -> Dict[str, Any]:
    """
    Get attributes of a queue.

    Args:
        queue_name: Name of the queue
        attribute_names: List of attribute names to get

    Returns:
        Dict containing the queue attributes

    Raises:
        Exception: If there's an error getting queue attributes
    """
    queue_url = get_queue_url(queue_name)

    attribute_params = {
        "QueueUrl": queue_url,
        "AttributeNames": attribute_names
    }

    try:
        async with session.create_client(
            'sqs',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as sqs:
            response = await sqs.get_queue_attributes(**attribute_params)
            attributes = response.get("Attributes", {})
            logger.info(f"Retrieved attributes for queue {queue_name}")
            return attributes
    except Exception as e:
        logger.error(f"Error getting attributes for queue {queue_name}: {str(e)}")
        raise


async def send_messages_batch(
    queue_name: str,
    messages: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Send multiple messages to a queue in batch.

    Args:
        queue_name: Name of the queue
        messages: List of message dictionaries with 'body' and optional 'delay_seconds'

    Returns:
        Dict containing the response from SQS

    Raises:
        Exception: If there's an error sending messages
    """
    queue_url = get_queue_url(queue_name)

    # Prepare batch entries
    entries = []
    for i, msg in enumerate(messages):
        entry = {
            "Id": str(i),
            "MessageBody": json.dumps(msg["body"]) if isinstance(msg["body"], dict) else msg["body"]
        }

        if "delay_seconds" in msg:
            entry["DelaySeconds"] = msg["delay_seconds"]

        if "message_attributes" in msg:
            entry["MessageAttributes"] = msg["message_attributes"]

        entries.append(entry)

    try:
        async with session.create_client(
            'sqs',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as sqs:
            response = await sqs.send_message_batch(
                QueueUrl=queue_url,
                Entries=entries
            )
            successful = len(response.get("Successful", []))
            failed = len(response.get("Failed", []))
            logger.info(f"Batch sent to queue {queue_name}: {successful} successful, {failed} failed")
            return response
    except Exception as e:
        logger.error(f"Error sending batch messages to queue {queue_name}: {str(e)}")
        raise


def get_sync_sqs_client():
    """
    Get synchronous SQS client for base_worker compatibility.

    Returns:
        Synchronous boto3 SQS client
    """
    import boto3
    return boto3.client(
        'sqs',
        region_name=AWS_REGION,
        endpoint_url=AWS_ENDPOINT_URL
    )


async def change_message_visibility(
    queue_name: str,
    receipt_handle: str,
    timeout_seconds: int
) -> Dict[str, Any]:
    """
    Change the visibility timeout of a message currently being processed.

    Args:
        queue_name: Name of the queue
        receipt_handle: Receipt handle of the message
        timeout_seconds: New visibility timeout in seconds (absolute from now)

    Returns:
        Dict containing the response from SQS

    Raises:
        Exception: If there's an error changing the visibility timeout
    """
    queue_url = get_queue_url(queue_name)
    params = {
        "QueueUrl": queue_url,
        "ReceiptHandle": receipt_handle,
        "VisibilityTimeout": timeout_seconds,
    }

    try:
        async with session.create_client(
            'sqs',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as sqs_client:
            response = await sqs_client.change_message_visibility(**params)
            logger.info(
                f"Changed message visibility for queue {queue_name} to {timeout_seconds}s"
            )
            return response
    except Exception as e:
        logger.error(f"Error changing message visibility for queue {queue_name}: {str(e)}")
        raise
