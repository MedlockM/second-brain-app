"""
AWS service fixtures for tests.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_s3_client():
    """
    Create a mock S3 client for testing.
    
    Returns:
        A mock S3 client with common methods mocked
    """
    mock = MagicMock()
    mock.upload_file = AsyncMock()
    mock.download_file = AsyncMock()
    mock.generate_presigned_url = MagicMock(return_value="https://example.com/presigned-url")
    mock.head_object = AsyncMock(return_value={
        "ContentLength": 1000000,
        "ContentType": "audio/mpeg",
        "Metadata": {"duration": "1800"}
    })
    mock.list_objects_v2 = AsyncMock(return_value={
        "Contents": [
            {"Key": "test-key-1", "Size": 1000000},
            {"Key": "test-key-2", "Size": 2000000}
        ]
    })
    return mock


@pytest.fixture
def mock_sqs_client():
    """
    Create a mock SQS client for testing.
    
    Returns:
        A mock SQS client with common methods mocked
    """
    mock = MagicMock()
    mock.send_message = AsyncMock(return_value={"MessageId": "msg-123"})
    mock.receive_message = AsyncMock(return_value={
        "Messages": [
            {
                "MessageId": "msg-123",
                "ReceiptHandle": "receipt-123",
                "Body": "{}",
                "Attributes": {"SentTimestamp": "1234567890"}
            }
        ]
    })
    mock.delete_message = AsyncMock()
    mock.get_queue_url = AsyncMock(return_value={"QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"})
    mock.create_queue = AsyncMock(return_value={"QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"})
    return mock


@pytest.fixture
def mock_ses_client():
    """
    Create a mock SES client for testing.
    
    Returns:
        A mock SES client with common methods mocked
    """
    mock = MagicMock()
    mock.send_email = AsyncMock(return_value={"MessageId": "msg-123"})
    mock.verify_email_identity = AsyncMock()
    mock.list_identities = AsyncMock(return_value={"Identities": ["test@example.com"]})
    return mock


@pytest.fixture
def mock_dynamodb_client():
    """
    Create a mock DynamoDB client for testing.
    
    Returns:
        A mock DynamoDB client with common methods mocked
    """
    mock = MagicMock()
    mock.put_item = AsyncMock()
    mock.get_item = AsyncMock(return_value={"Item": {"id": {"S": "test-id"}}})
    mock.update_item = AsyncMock()
    mock.delete_item = AsyncMock()
    mock.query = AsyncMock(return_value={"Items": [{"id": {"S": "test-id"}}]})
    mock.scan = AsyncMock(return_value={"Items": [{"id": {"S": "test-id"}}]})
    return mock


# Error Mocks
@pytest.fixture
def mock_s3_client_with_error():
    """
    Create a mock S3 client that generates errors.
    
    Returns:
        A mock S3 client with methods that raise exceptions
    """
    mock = MagicMock()
    mock.upload_file = AsyncMock(side_effect=Exception("S3 upload error"))
    mock.download_file = AsyncMock(side_effect=Exception("S3 download error"))
    mock.generate_presigned_url = MagicMock(side_effect=Exception("S3 presigned URL error"))
    return mock


@pytest.fixture
def mock_sqs_client_with_error():
    """
    Create a mock SQS client that generates errors.
    
    Returns:
        A mock SQS client with methods that raise exceptions
    """
    mock = MagicMock()
    mock.send_message = AsyncMock(side_effect=Exception("SQS send message error"))
    mock.receive_message = AsyncMock(side_effect=Exception("SQS receive message error"))
    mock.delete_message = AsyncMock(side_effect=Exception("SQS delete message error"))
    return mock


@pytest.fixture
def mock_ses_client_with_error():
    """
    Create a mock SES client that generates errors.
    
    Returns:
        A mock SES client with methods that raise exceptions
    """
    mock = MagicMock()
    mock.send_email = AsyncMock(side_effect=Exception("SES send email error"))
    return mock