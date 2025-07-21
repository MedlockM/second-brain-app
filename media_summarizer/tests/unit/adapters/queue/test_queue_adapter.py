"""
Unit tests for the queue adapter.
"""
import os
import json
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from botocore.exceptions import ClientError

# Set AWS credentials for testing
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"

from media_summarizer.adapters.queue.queue_adapter import QueueAdapter


@pytest.fixture
def mock_sqs_client():
    """Mock SQS client for testing."""
    mock_client = AsyncMock()
    mock_client.send_message = AsyncMock(return_value={"MessageId": "test-message-id"})
    mock_client.receive_message = AsyncMock(return_value={"Messages": [
        {
            "MessageId": "test-message-id",
            "ReceiptHandle": "test-receipt-handle",
            "Body": json.dumps({"key": "value"}),
            "Attributes": {"SentTimestamp": "1234567890"}
        }
    ]})
    mock_client.delete_message = AsyncMock(return_value={})
    mock_client.purge_queue = AsyncMock(return_value={})
    mock_client.get_queue_attributes = AsyncMock(return_value={"Attributes": {
        "ApproximateNumberOfMessages": "10",
        "ApproximateNumberOfMessagesNotVisible": "5"
    }})
    return mock_client


@pytest.fixture
def queue_adapter():
    """Create a QueueAdapter instance for testing."""
    return QueueAdapter(region_name="us-east-1", endpoint_url="http://localhost:4566")


class TestQueueAdapter:
    """Test cases for the QueueAdapter class."""
    
    @pytest.mark.asyncio
    async def test_init(self):
        """Test QueueAdapter initialization."""
        # Test with default values
        adapter = QueueAdapter()
        assert adapter.region_name == "us-east-1"
        assert adapter.endpoint_url == "http://localhost:4566"
        
        # Test with custom values
        adapter = QueueAdapter(region_name="eu-west-1", endpoint_url="http://custom-endpoint")
        assert adapter.region_name == "eu-west-1"
        assert adapter.endpoint_url == "http://custom-endpoint"
    
    def test_get_queue_url(self):
        """Test get_queue_url method."""
        # Test with endpoint URL (LocalStack)
        adapter = QueueAdapter(endpoint_url="http://localhost:4566")
        url = adapter.get_queue_url("test-queue")
        assert url == "http://localhost:4566/000000000000/test-queue"
        
        # Test without endpoint URL (AWS)
        adapter = QueueAdapter(endpoint_url=None)
        url = adapter.get_queue_url("test-queue")
        assert url == "test-queue"
    
    @pytest.mark.asyncio
    async def test_send_message_dict(self, queue_adapter, mock_sqs_client):
        """Test sending a message with dict body."""
        # Setup
        queue_name = "test-queue"
        message_body = {"key": "value"}
        
        # Execute - Test with provided sqs_client
        result = await queue_adapter.send_message(
            queue_name, message_body, sqs_client=mock_sqs_client
        )
        
        # Verify
        mock_sqs_client.send_message.assert_called_once()
        call_args = mock_sqs_client.send_message.call_args[1]
        
        assert call_args["QueueUrl"] == "http://localhost:4566/000000000000/test-queue"
        assert call_args["MessageBody"] == json.dumps(message_body)
        assert call_args["DelaySeconds"] == 0
        assert result == {"MessageId": "test-message-id"}
    
    @pytest.mark.asyncio
    async def test_send_message_string(self, queue_adapter, mock_sqs_client):
        """Test sending a message with string body."""
        # Setup
        queue_name = "test-queue"
        message_body = json.dumps({"key": "value"})
        
        # Execute
        result = await queue_adapter.send_message(
            queue_name, message_body, sqs_client=mock_sqs_client
        )
        
        # Verify
        mock_sqs_client.send_message.assert_called_once()
        call_args = mock_sqs_client.send_message.call_args[1]
        
        assert call_args["QueueUrl"] == "http://localhost:4566/000000000000/test-queue"
        assert call_args["MessageBody"] == message_body
        assert call_args["DelaySeconds"] == 0
        assert result == {"MessageId": "test-message-id"}
    
    @pytest.mark.asyncio
    async def test_send_message_with_delay(self, queue_adapter, mock_sqs_client):
        """Test sending a message with delay."""
        # Setup
        queue_name = "test-queue"
        message_body = {"key": "value"}
        delay_seconds = 60
        
        # Execute
        result = await queue_adapter.send_message(
            queue_name, message_body, delay_seconds=delay_seconds, sqs_client=mock_sqs_client
        )
        
        # Verify
        mock_sqs_client.send_message.assert_called_once()
        call_args = mock_sqs_client.send_message.call_args[1]
        
        assert call_args["QueueUrl"] == "http://localhost:4566/000000000000/test-queue"
        assert call_args["MessageBody"] == json.dumps(message_body)
        assert call_args["DelaySeconds"] == delay_seconds
        assert result == {"MessageId": "test-message-id"}
    
    @pytest.mark.asyncio
    async def test_send_message_with_attributes(self, queue_adapter, mock_sqs_client):
        """Test sending a message with attributes."""
        # Setup
        queue_name = "test-queue"
        message_body = {"key": "value"}
        message_attributes = {
            "AttributeName": {
                "DataType": "String",
                "StringValue": "AttributeValue"
            }
        }
        
        # Execute
        result = await queue_adapter.send_message(
            queue_name, message_body, message_attributes=message_attributes, sqs_client=mock_sqs_client
        )
        
        # Verify
        mock_sqs_client.send_message.assert_called_once()
        call_args = mock_sqs_client.send_message.call_args[1]
        
        assert call_args["QueueUrl"] == "http://localhost:4566/000000000000/test-queue"
        assert call_args["MessageBody"] == json.dumps(message_body)
        assert call_args["MessageAttributes"] == message_attributes
        assert result == {"MessageId": "test-message-id"}
    
    @pytest.mark.asyncio
    async def test_send_message_with_client_error(self, queue_adapter, mock_sqs_client):
        """Test handling of ClientError during message sending."""
        # Setup
        queue_name = "test-queue"
        message_body = {"key": "value"}
        
        # Configure mock to raise ClientError
        error_response = {"Error": {"Code": "QueueDoesNotExist", "Message": "The specified queue does not exist."}}
        mock_sqs_client.send_message.side_effect = ClientError(error_response, "send_message")
        
        # Execute and verify
        with pytest.raises(ClientError) as excinfo:
            await queue_adapter.send_message(queue_name, message_body, sqs_client=mock_sqs_client)
        
        assert "QueueDoesNotExist" in str(excinfo.value)
        assert "The specified queue does not exist." in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_receive_messages(self, queue_adapter, mock_sqs_client):
        """Test receiving messages."""
        # Setup
        queue_name = "test-queue"
        
        # Execute
        result = await queue_adapter.receive_messages(
            queue_name, sqs_client=mock_sqs_client
        )
        
        # Verify
        mock_sqs_client.receive_message.assert_called_once()
        call_args = mock_sqs_client.receive_message.call_args[1]
        
        assert call_args["QueueUrl"] == "http://localhost:4566/000000000000/test-queue"
        assert call_args["MaxNumberOfMessages"] == 1
        assert call_args["WaitTimeSeconds"] == 0
        assert call_args["VisibilityTimeout"] == 30
        assert len(result) == 1
        assert result[0]["MessageId"] == "test-message-id"
        assert result[0]["ReceiptHandle"] == "test-receipt-handle"
        assert json.loads(result[0]["Body"]) == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_receive_messages_with_custom_params(self, queue_adapter, mock_sqs_client):
        """Test receiving messages with custom parameters."""
        # Setup
        queue_name = "test-queue"
        max_messages = 5
        wait_time_seconds = 10
        visibility_timeout = 60
        
        # Execute
        result = await queue_adapter.receive_messages(
            queue_name,
            max_messages=max_messages,
            wait_time_seconds=wait_time_seconds,
            visibility_timeout=visibility_timeout,
            sqs_client=mock_sqs_client
        )
        
        # Verify
        mock_sqs_client.receive_message.assert_called_once()
        call_args = mock_sqs_client.receive_message.call_args[1]
        
        assert call_args["QueueUrl"] == "http://localhost:4566/000000000000/test-queue"
        assert call_args["MaxNumberOfMessages"] == max_messages
        assert call_args["WaitTimeSeconds"] == wait_time_seconds
        assert call_args["VisibilityTimeout"] == visibility_timeout
        assert len(result) == 1
    
    @pytest.mark.asyncio
    async def test_receive_messages_empty_queue(self, queue_adapter, mock_sqs_client):
        """Test receiving messages from an empty queue."""
        # Setup
        queue_name = "test-queue"
        mock_sqs_client.receive_message.return_value = {}  # No messages
        
        # Execute
        result = await queue_adapter.receive_messages(
            queue_name, sqs_client=mock_sqs_client
        )
        
        # Verify
        mock_sqs_client.receive_message.assert_called_once()
        assert result == []  # Empty list
    
    @pytest.mark.asyncio
    async def test_receive_messages_with_client_error(self, queue_adapter, mock_sqs_client):
        """Test handling of ClientError during message receiving."""
        # Setup
        queue_name = "test-queue"
        
        # Configure mock to raise ClientError
        error_response = {"Error": {"Code": "QueueDoesNotExist", "Message": "The specified queue does not exist."}}
        mock_sqs_client.receive_message.side_effect = ClientError(error_response, "receive_message")
        
        # Execute and verify
        with pytest.raises(ClientError) as excinfo:
            await queue_adapter.receive_messages(queue_name, sqs_client=mock_sqs_client)
        
        assert "QueueDoesNotExist" in str(excinfo.value)
        assert "The specified queue does not exist." in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_delete_message(self, queue_adapter, mock_sqs_client):
        """Test deleting a message."""
        # Setup
        queue_name = "test-queue"
        receipt_handle = "test-receipt-handle"
        
        # Execute
        result = await queue_adapter.delete_message(
            queue_name, receipt_handle, sqs_client=mock_sqs_client
        )
        
        # Verify
        mock_sqs_client.delete_message.assert_called_once()
        call_args = mock_sqs_client.delete_message.call_args[1]
        
        assert call_args["QueueUrl"] == "http://localhost:4566/000000000000/test-queue"
        assert call_args["ReceiptHandle"] == receipt_handle
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_delete_message_with_client_error(self, queue_adapter, mock_sqs_client):
        """Test handling of ClientError during message deletion."""
        # Setup
        queue_name = "test-queue"
        receipt_handle = "test-receipt-handle"
        
        # Configure mock to raise ClientError
        error_response = {"Error": {"Code": "ReceiptHandleIsInvalid", "Message": "The receipt handle is invalid."}}
        mock_sqs_client.delete_message.side_effect = ClientError(error_response, "delete_message")
        
        # Execute and verify
        with pytest.raises(ClientError) as excinfo:
            await queue_adapter.delete_message(queue_name, receipt_handle, sqs_client=mock_sqs_client)
        
        assert "ReceiptHandleIsInvalid" in str(excinfo.value)
        assert "The receipt handle is invalid." in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_purge_queue(self, queue_adapter, mock_sqs_client):
        """Test purging a queue."""
        # Setup
        queue_name = "test-queue"
        
        # Execute
        result = await queue_adapter.purge_queue(
            queue_name, sqs_client=mock_sqs_client
        )
        
        # Verify
        mock_sqs_client.purge_queue.assert_called_once()
        call_args = mock_sqs_client.purge_queue.call_args[1]
        
        assert call_args["QueueUrl"] == "http://localhost:4566/000000000000/test-queue"
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_purge_queue_with_client_error(self, queue_adapter, mock_sqs_client):
        """Test handling of ClientError during queue purging."""
        # Setup
        queue_name = "test-queue"
        
        # Configure mock to raise ClientError
        error_response = {"Error": {"Code": "PurgeQueueInProgress", "Message": "Purge already in progress."}}
        mock_sqs_client.purge_queue.side_effect = ClientError(error_response, "purge_queue")
        
        # Execute and verify
        with pytest.raises(ClientError) as excinfo:
            await queue_adapter.purge_queue(queue_name, sqs_client=mock_sqs_client)
        
        assert "PurgeQueueInProgress" in str(excinfo.value)
        assert "Purge already in progress." in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_get_queue_attributes(self, queue_adapter, mock_sqs_client):
        """Test getting queue attributes."""
        # Setup
        queue_name = "test-queue"
        
        # Execute
        result = await queue_adapter.get_queue_attributes(
            queue_name, sqs_client=mock_sqs_client
        )
        
        # Verify
        mock_sqs_client.get_queue_attributes.assert_called_once()
        call_args = mock_sqs_client.get_queue_attributes.call_args[1]
        
        assert call_args["QueueUrl"] == "http://localhost:4566/000000000000/test-queue"
        assert call_args["AttributeNames"] == ["All"]
        assert result == {
            "ApproximateNumberOfMessages": "10",
            "ApproximateNumberOfMessagesNotVisible": "5"
        }
    
    @pytest.mark.asyncio
    async def test_get_queue_attributes_with_specific_attributes(self, queue_adapter, mock_sqs_client):
        """Test getting specific queue attributes."""
        # Setup
        queue_name = "test-queue"
        attribute_names = ["ApproximateNumberOfMessages"]
        
        # Execute
        result = await queue_adapter.get_queue_attributes(
            queue_name, attribute_names=attribute_names, sqs_client=mock_sqs_client
        )
        
        # Verify
        mock_sqs_client.get_queue_attributes.assert_called_once()
        call_args = mock_sqs_client.get_queue_attributes.call_args[1]
        
        assert call_args["QueueUrl"] == "http://localhost:4566/000000000000/test-queue"
        assert call_args["AttributeNames"] == attribute_names
        assert result == {
            "ApproximateNumberOfMessages": "10",
            "ApproximateNumberOfMessagesNotVisible": "5"
        }
    
    @pytest.mark.asyncio
    async def test_get_queue_attributes_with_client_error(self, queue_adapter, mock_sqs_client):
        """Test handling of ClientError during getting queue attributes."""
        # Setup
        queue_name = "test-queue"
        
        # Configure mock to raise ClientError
        error_response = {"Error": {"Code": "QueueDoesNotExist", "Message": "The specified queue does not exist."}}
        mock_sqs_client.get_queue_attributes.side_effect = ClientError(error_response, "get_queue_attributes")
        
        # Execute and verify
        with pytest.raises(ClientError) as excinfo:
            await queue_adapter.get_queue_attributes(queue_name, sqs_client=mock_sqs_client)
        
        assert "QueueDoesNotExist" in str(excinfo.value)
        assert "The specified queue does not exist." in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_send_message_with_session_creation(self, queue_adapter):
        """Test sending a message with session creation."""
        # Setup
        queue_name = "test-queue"
        message_body = {"key": "value"}
        
        # Execute - Test with session creation
        with patch("media_summarizer.adapters.queue.queue_adapter.session") as mock_session:
            mock_client = AsyncMock()
            mock_client.send_message = AsyncMock(return_value={"MessageId": "test-message-id"})
            mock_session.create_client.return_value.__aenter__.return_value = mock_client
            
            # Execute
            result = await queue_adapter.send_message(queue_name, message_body)
            
            # Verify
            mock_client.send_message.assert_called_once()
            call_args = mock_client.send_message.call_args[1]
            
            assert call_args["QueueUrl"] == "http://localhost:4566/000000000000/test-queue"
            assert call_args["MessageBody"] == json.dumps(message_body)
            assert call_args["DelaySeconds"] == 0
            assert result == {"MessageId": "test-message-id"}
    
    @pytest.mark.asyncio
    async def test_receive_messages_with_session_creation(self, queue_adapter):
        """Test receiving messages with session creation."""
        # Setup
        queue_name = "test-queue"
        
        # Execute - Test with session creation
        with patch("media_summarizer.adapters.queue.queue_adapter.session") as mock_session:
            mock_client = AsyncMock()
            mock_client.receive_message = AsyncMock(return_value={"Messages": [
                {
                    "MessageId": "test-message-id",
                    "ReceiptHandle": "test-receipt-handle",
                    "Body": json.dumps({"key": "value"}),
                    "Attributes": {"SentTimestamp": "1234567890"}
                }
            ]})
            mock_session.create_client.return_value.__aenter__.return_value = mock_client
            
            # Execute
            result = await queue_adapter.receive_messages(queue_name)
            
            # Verify
            mock_client.receive_message.assert_called_once()
            call_args = mock_client.receive_message.call_args[1]
            
            assert call_args["QueueUrl"] == "http://localhost:4566/000000000000/test-queue"
            assert len(result) == 1
            assert result[0]["MessageId"] == "test-message-id"