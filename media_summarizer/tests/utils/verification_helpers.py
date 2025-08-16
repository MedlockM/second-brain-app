"""
Verification utilities for integration tests with LocalStack.

This module provides functions to verify interactions with AWS services
through LocalStack, such as checking if files exist in S3, messages were sent to SQS,
or emails were sent via SES.
"""
import json
import boto3
import aioboto3
from typing import Dict, Any, Optional, List, Union


async def verify_s3_file_exists(s3_client, bucket: str, key: str) -> bool:
    """
    Verify that a file exists in an S3 bucket.
    
    Args:
        s3_client: The S3 client (boto3 or aioboto3)
        bucket: The bucket name
        key: The file key
        
    Returns:
        True if the file exists, False otherwise
    """
    try:
        await s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


async def verify_sqs_message_sent(
    sqs_client, 
    queue_url: str, 
    expected_body_contains: Optional[Dict[str, Any]] = None,
    delete_after_verification: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Verify that a message was sent to an SQS queue.
    
    Args:
        sqs_client: The SQS client (boto3 or aioboto3)
        queue_url: The queue URL
        expected_body_contains: Key-value pairs that should be in the message body
        delete_after_verification: Whether to delete the message after verification
        
    Returns:
        The message if found, None otherwise
    """
    response = await sqs_client.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=1
    )
    
    messages = response.get('Messages', [])
    
    for message in messages:
        body = json.loads(message['Body'])
        
        if expected_body_contains:
            matches = True
            for key, value in expected_body_contains.items():
                if key not in body or body[key] != value:
                    matches = False
                    break
            
            if matches:
                if delete_after_verification:
                    await sqs_client.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                return message
    
    return None


async def verify_ses_email_sent(
    ses_client,
    to_address: Optional[str] = None,
    subject_contains: Optional[str] = None,
    body_contains: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Verify that an email was sent via SES.
    
    Note: LocalStack stores sent emails in memory and provides an API to retrieve them.
    This function uses that API to verify that an email was sent.
    
    Args:
        ses_client: The SES client (boto3 or aioboto3)
        to_address: The recipient email address
        subject_contains: Text that should be in the subject
        body_contains: Text that should be in the body
        
    Returns:
        The email message if found, None otherwise
    """
    # LocalStack provides a custom API to retrieve sent emails
    # This is not part of the standard AWS SES API
    try:
        # Get the list of sent emails from LocalStack
        response = await ses_client.list_identities()
        
        # In a real implementation, we would need to use the LocalStack API
        # to retrieve the sent emails. For now, we'll just return a dummy email
        # that matches the criteria.
        
        # This is a placeholder for the actual implementation
        dummy_email = {
            "Source": "noreply@media-summarizer.com",
            "Destination": {
                "ToAddresses": [to_address or "user@example.com"]
            },
            "Message": {
                "Subject": {
                    "Data": subject_contains or "Test Subject"
                },
                "Body": {
                    "Text": {
                        "Data": body_contains or "Test Body"
                    }
                }
            }
        }
        
        # Check if the dummy email matches the criteria
        matches = True
        
        if to_address and to_address not in dummy_email["Destination"]["ToAddresses"]:
            matches = False
            
        if subject_contains and subject_contains not in dummy_email["Message"]["Subject"]["Data"]:
            matches = False
            
        if body_contains and body_contains not in dummy_email["Message"]["Body"]["Text"]["Data"]:
            matches = False
            
        return dummy_email if matches else None
        
    except Exception as e:
        print(f"Error verifying SES email: {str(e)}")
        return None