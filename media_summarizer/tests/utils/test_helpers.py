"""
Common test helpers and utilities for Media Summarizer tests.

This module provides reusable functions and utilities for writing tests,
helping to standardize test patterns and reduce code duplication.
"""
import json
import os
from typing import Dict, Any, Optional, List, Union

# Type aliases for clarity
MessageType = Dict[str, Any]
SQSMessageType = Dict[str, Any]


def create_sqs_message(
    body: Union[Dict[str, Any], str],
    message_id: str = "msg-123",
    receipt_handle: str = "receipt-123"
) -> SQSMessageType:
    """
    Create a mock SQS message for testing.
    
    Args:
        body: The message body (dict or JSON string)
        message_id: The message ID
        receipt_handle: The receipt handle
        
    Returns:
        A mock SQS message
    """
    if isinstance(body, dict):
        body = json.dumps(body)
        
    return {
        "MessageId": message_id,
        "ReceiptHandle": receipt_handle,
        "Body": body,
        "Attributes": {
            "SentTimestamp": "1234567890"
        }
    }


def create_api_auth_headers(user_id: str = "test-user") -> Dict[str, str]:
    """
    Create mock authentication headers for API tests.
    
    Args:
        user_id: The user ID to include in the token
        
    Returns:
        Headers dict with Authorization
    """
    return {
        "Authorization": f"Bearer test-token-{user_id}"
    }


def assert_sqs_message_sent(
    mock_sqs_client,
    expected_queue_url: Optional[str] = None,
    expected_body_contains: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Assert that a message was sent to SQS with the expected content.
    
    Args:
        mock_sqs_client: The mock SQS client
        expected_queue_url: The expected queue URL (optional)
        expected_body_contains: Key-value pairs that should be in the message body (optional)
        
    Returns:
        The parsed message body for further assertions
    """
    mock_sqs_client.send_message.assert_called_once()
    call_args = mock_sqs_client.send_message.call_args[1]
    
    if expected_queue_url:
        assert call_args["QueueUrl"] == expected_queue_url
    
    message_body = json.loads(call_args["MessageBody"])
    
    if expected_body_contains:
        for key, value in expected_body_contains.items():
            assert key in message_body
            assert message_body[key] == value
    
    return message_body


def assert_s3_file_uploaded(
    mock_s3_client,
    expected_bucket: Optional[str] = None,
    expected_key_prefix: Optional[str] = None
) -> str:
    """
    Assert that a file was uploaded to S3.
    
    Args:
        mock_s3_client: The mock S3 client
        expected_bucket: The expected bucket name (optional)
        expected_key_prefix: The expected key prefix (optional)
        
    Returns:
        The S3 key of the uploaded file
    """
    mock_s3_client.upload_file.assert_called_once()
    call_args = mock_s3_client.upload_file.call_args[1]
    
    if expected_bucket:
        assert call_args["Bucket"] == expected_bucket
    
    if expected_key_prefix:
        assert call_args["Key"].startswith(expected_key_prefix)
    
    return call_args["Key"]


def assert_email_sent(
    mock_ses_client,
    expected_recipient: Optional[str] = None,
    expected_subject_contains: Optional[str] = None,
    expected_body_contains: Optional[str] = None
) -> Dict[str, Any]:
    """
    Assert that an email was sent with the expected content.
    
    Args:
        mock_ses_client: The mock SES client
        expected_recipient: The expected recipient email (optional)
        expected_subject_contains: Text that should be in the subject (optional)
        expected_body_contains: Text that should be in the body (optional)
        
    Returns:
        The email message for further assertions
    """
    mock_ses_client.send_email.assert_called_once()
    call_args = mock_ses_client.send_email.call_args[1]
    
    if expected_recipient:
        assert call_args["Destination"]["ToAddresses"][0] == expected_recipient
    
    if expected_subject_contains:
        assert expected_subject_contains in call_args["Message"]["Subject"]["Data"]
    
    if expected_body_contains:
        # Check in text body if available
        if "Text" in call_args["Message"]["Body"]:
            assert expected_body_contains in call_args["Message"]["Body"]["Text"]["Data"]
        
        # HTML body might have different content, so we don't check it here
    
    return call_args["Message"]


def set_env_vars(env_vars: Dict[str, str]) -> Dict[str, Optional[str]]:
    """
    Set environment variables for testing and return the original values.
    
    Args:
        env_vars: Dictionary of environment variables to set
        
    Returns:
        Dictionary of original environment variable values
    """
    original_values = {}
    
    for key, value in env_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value
    
    return original_values


def restore_env_vars(original_values: Dict[str, Optional[str]]):
    """
    Restore environment variables to their original values.
    
    Args:
        original_values: Dictionary of original environment variable values
    """
    for key, value in original_values.items():
        if value is None:
            if key in os.environ:
                del os.environ[key]
        else:
            os.environ[key] = value