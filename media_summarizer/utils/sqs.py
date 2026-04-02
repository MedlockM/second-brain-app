"""
SQS utilities for message queue operations.

This module provides async utility functions for interacting
with Amazon SQS in the Media Summarizer application using aiobotocore.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Union

from media_summarizer.utils.logging_config import (
    get_runtime_aws_endpoint_url,
    log_event,
)

logger = logging.getLogger(__name__)

# AWS configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
_IMPORT_TIME_AWS_ENDPOINT_URL = os.environ.get("AWS_ENDPOINT_URL")
AWS_ENDPOINT_URL = _IMPORT_TIME_AWS_ENDPOINT_URL

# Import AWS session
try:
    from aiobotocore.session import get_session

    session = get_session()
except ImportError:
    log_event(
        logger,
        logging.ERROR,
        "external_call.failed",
        "aiobotocore is not installed",
        provider="sqs",
        error_code="MISSING_DEPENDENCY",
    )
    raise


_QUEUE_URL_CACHE: Dict[str, str] = {}


def _runtime_aws_endpoint_url() -> Optional[str]:
    configured = AWS_ENDPOINT_URL
    if configured == _IMPORT_TIME_AWS_ENDPOINT_URL:
        configured = os.environ.get("AWS_ENDPOINT_URL", _IMPORT_TIME_AWS_ENDPOINT_URL)
    return get_runtime_aws_endpoint_url(configured_value=configured, consumer="sqs")


def get_queue_url(queue_name: str) -> str:
    """
    Get the URL for a queue.

    Args:
        queue_name: Name of the queue

    Returns:
        Queue URL
    """
    # For local development with LocalStack
    runtime_endpoint = _runtime_aws_endpoint_url()
    if runtime_endpoint:
        # Prefer host-style SQS endpoint (http://sqs.<region>.localhost:4566) for compatibility with SDKs
        try:
            from urllib.parse import urlparse
            parsed = urlparse(runtime_endpoint)
            host = parsed.hostname or "localhost"
            port = parsed.port or 4566
            scheme = parsed.scheme or "http"
            if host in ("localhost", "127.0.0.1"):
                return f"{scheme}://sqs.{AWS_REGION}.{host}:{port}/000000000000/{queue_name}"
            else:
                # Fallback to path-style when using non-local hostnames
                return f"{runtime_endpoint}/000000000000/{queue_name}"
        except Exception:
            return f"{runtime_endpoint}/000000000000/{queue_name}"

    # For AWS, resolve the full QueueUrl via the API (cached per process)
    if queue_name in _QUEUE_URL_CACHE:
        return _QUEUE_URL_CACHE[queue_name]

    import boto3

    sqs_client = boto3.client("sqs", region_name=AWS_REGION)
    response = sqs_client.get_queue_url(QueueName=queue_name)
    queue_url = response["QueueUrl"]
    _QUEUE_URL_CACHE[queue_name] = queue_url
    return queue_url


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
        runtime_endpoint = _runtime_aws_endpoint_url()
        async with session.create_client(
            'sqs',
            region_name=AWS_REGION,
            endpoint_url=runtime_endpoint
        ) as sqs:
            response = await sqs.send_message(**message_params)
            log_event(
                logger,
                logging.DEBUG,
                "external_call.succeeded",
                "SQS message sent",
                provider="sqs",
                queue=queue_name,
            )
            return response
    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            "external_call.failed",
            "Failed to send SQS message",
            provider="sqs",
            queue=queue_name,
            error_type=type(e).__name__,
            error_code="SQS_SEND_FAILED",
        )
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
        "VisibilityTimeout": visibility_timeout,
        "AttributeNames": ["ApproximateReceiveCount"],
    }

    try:
        runtime_endpoint = _runtime_aws_endpoint_url()
        async with session.create_client(
            'sqs',
            region_name=AWS_REGION,
            endpoint_url=runtime_endpoint
        ) as sqs:
            response = await sqs.receive_message(**receive_params)
            messages = response.get("Messages", [])
            return messages
    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            "external_call.failed",
            "Failed to receive SQS messages",
            provider="sqs",
            queue=queue_name,
            error_type=type(e).__name__,
            error_code="SQS_RECEIVE_FAILED",
        )
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
        runtime_endpoint = _runtime_aws_endpoint_url()
        async with session.create_client(
            'sqs',
            region_name=AWS_REGION,
            endpoint_url=runtime_endpoint
        ) as sqs:
            response = await sqs.delete_message(**delete_params)
            return response
    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            "external_call.failed",
            "Failed to delete SQS message",
            provider="sqs",
            queue=queue_name,
            error_type=type(e).__name__,
            error_code="SQS_DELETE_FAILED",
        )
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
        runtime_endpoint = _runtime_aws_endpoint_url()
        async with session.create_client(
            'sqs',
            region_name=AWS_REGION,
            endpoint_url=runtime_endpoint
        ) as sqs:
            response = await sqs.purge_queue(**purge_params)
            return response
    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            "external_call.failed",
            "Failed to purge SQS queue",
            provider="sqs",
            queue=queue_name,
            error_type=type(e).__name__,
            error_code="SQS_PURGE_FAILED",
        )
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
        runtime_endpoint = _runtime_aws_endpoint_url()
        async with session.create_client(
            'sqs',
            region_name=AWS_REGION,
            endpoint_url=runtime_endpoint
        ) as sqs:
            response = await sqs.get_queue_attributes(**attribute_params)
            attributes = response.get("Attributes", {})
            return attributes
    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            "external_call.failed",
            "Failed to get SQS attributes",
            provider="sqs",
            queue=queue_name,
            error_type=type(e).__name__,
            error_code="SQS_ATTRIBUTES_FAILED",
        )
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
        runtime_endpoint = _runtime_aws_endpoint_url()
        async with session.create_client(
            'sqs',
            region_name=AWS_REGION,
            endpoint_url=runtime_endpoint
        ) as sqs:
            response = await sqs.send_message_batch(
                QueueUrl=queue_url,
                Entries=entries
            )
            if response.get("Failed"):
                log_event(
                    logger,
                    logging.WARNING,
                    "external_call.failed",
                    "Some SQS batch entries failed",
                    provider="sqs",
                    queue=queue_name,
                    error_code="SQS_BATCH_PARTIAL_FAILURE",
                )
            return response
    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            "external_call.failed",
            "Failed to send SQS batch",
            provider="sqs",
            queue=queue_name,
            error_type=type(e).__name__,
            error_code="SQS_BATCH_FAILED",
        )
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
        endpoint_url=_runtime_aws_endpoint_url()
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
        runtime_endpoint = _runtime_aws_endpoint_url()
        async with session.create_client(
            'sqs',
            region_name=AWS_REGION,
            endpoint_url=runtime_endpoint
        ) as sqs_client:
            response = await sqs_client.change_message_visibility(**params)
            return response
    except Exception as e:
        log_event(
            logger,
            logging.ERROR,
            "external_call.failed",
            "Failed to change SQS message visibility",
            provider="sqs",
            queue=queue_name,
            error_type=type(e).__name__,
            error_code="SQS_VISIBILITY_FAILED",
        )
        raise
