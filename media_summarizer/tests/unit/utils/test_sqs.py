"""
Unit tests for SQS utilities.

This module contains unit tests for all SQS utility functions,
using mocked aiobotocore operations to test the logic without requiring
actual AWS services.
"""
import pytest
import asyncio
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from media_summarizer.utils import sqs


@pytest.fixture
def mock_sqs_client():
    """Create a mock SQS client."""
    mock_client = AsyncMock()
    return mock_client


@pytest.fixture
def mock_session():
    """Create a mock aiobotocore session."""
    with patch('media_summarizer.utils.sqs.session') as mock_session:
        mock_client = AsyncMock()
        mock_session.create_client.return_value.__aenter__.return_value = mock_client
        yield mock_session, mock_client


class TestGetQueueUrl:
    """Test queue URL generation functionality."""

    def test_get_queue_url_with_endpoint(self):
        """Test queue URL generation with LocalStack endpoint."""
        with patch.dict('os.environ', {'AWS_ENDPOINT_URL': 'http://localhost:4566'}):
            with patch('media_summarizer.utils.sqs.AWS_ENDPOINT_URL', 'http://localhost:4566'):
                result = sqs.get_queue_url("test-queue")
                assert result == "http://localhost:4566/000000000000/test-queue"

    def test_get_queue_url_without_endpoint(self):
        """Test queue URL generation without endpoint (production)."""
        with patch('media_summarizer.utils.sqs.AWS_ENDPOINT_URL', None):
            result = sqs.get_queue_url("test-queue")
            assert result == "test-queue"


class TestSendMessage:
    """Test message sending functionality."""

    @pytest.mark.asyncio
    async def test_send_message_with_dict(self, mock_session):
        """Test sending message with dictionary body."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_message.return_value = {'MessageId': 'test-message-id'}

        message_body = {"type": "test", "data": "value"}
        result = await sqs.send_message(
            queue_name="test-queue",
            message_body=message_body,
            delay_seconds=5
        )

        mock_client.send_message.assert_called_once()
        call_args = mock_client.send_message.call_args[1]

        assert call_args["QueueUrl"] == sqs.get_queue_url("test-queue")
        assert call_args["MessageBody"] == json.dumps(message_body)
        assert call_args["DelaySeconds"] == 5
        assert result == {'MessageId': 'test-message-id'}

    @pytest.mark.asyncio
    async def test_send_message_with_string(self, mock_session):
        """Test sending message with string body."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_message.return_value = {'MessageId': 'test-message-id'}

        message_body = "test message"
        await sqs.send_message(
            queue_name="test-queue",
            message_body=message_body
        )

        call_args = mock_client.send_message.call_args[1]
        assert call_args["MessageBody"] == message_body
        assert call_args["DelaySeconds"] == 0

    @pytest.mark.asyncio
    async def test_send_message_with_attributes(self, mock_session):
        """Test sending message with attributes."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_message.return_value = {'MessageId': 'test-message-id'}

        message_attributes = {
            "Author": {
                "StringValue": "test-user",
                "DataType": "String"
            }
        }

        await sqs.send_message(
            queue_name="test-queue",
            message_body="test message",
            message_attributes=message_attributes
        )

        call_args = mock_client.send_message.call_args[1]
        assert call_args["MessageAttributes"] == message_attributes

    @pytest.mark.asyncio
    async def test_send_message_error(self, mock_session):
        """Test send message with SQS error."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_message.side_effect = Exception("SQS error")

        with pytest.raises(Exception, match="SQS error"):
            await sqs.send_message(
                queue_name="test-queue",
                message_body="test message"
            )


class TestReceiveMessages:
    """Test message receiving functionality."""

    @pytest.mark.asyncio
    async def test_receive_messages_success(self, mock_session):
        """Test successful message receiving."""
        mock_session_obj, mock_client = mock_session
        expected_messages = [
            {
                'MessageId': 'msg-1',
                'Body': 'test message 1',
                'ReceiptHandle': 'receipt-1'
            },
            {
                'MessageId': 'msg-2',
                'Body': 'test message 2',
                'ReceiptHandle': 'receipt-2'
            }
        ]
        mock_client.receive_message.return_value = {'Messages': expected_messages}

        result = await sqs.receive_messages(
            queue_name="test-queue",
            max_messages=2,
            wait_time_seconds=10,
            visibility_timeout=60
        )

        mock_client.receive_message.assert_called_once()
        call_args = mock_client.receive_message.call_args[1]

        assert call_args["QueueUrl"] == sqs.get_queue_url("test-queue")
        assert call_args["MaxNumberOfMessages"] == 2
        assert call_args["WaitTimeSeconds"] == 10
        assert call_args["VisibilityTimeout"] == 60
        assert result == expected_messages

    @pytest.mark.asyncio
    async def test_receive_messages_empty(self, mock_session):
        """Test receiving messages when queue is empty."""
        mock_session_obj, mock_client = mock_session
        mock_client.receive_message.return_value = {}

        result = await sqs.receive_messages(queue_name="test-queue")

        assert result == []

    @pytest.mark.asyncio
    async def test_receive_messages_default_params(self, mock_session):
        """Test receiving messages with default parameters."""
        mock_session_obj, mock_client = mock_session
        mock_client.receive_message.return_value = {'Messages': []}

        await sqs.receive_messages(queue_name="test-queue")

        call_args = mock_client.receive_message.call_args[1]
        assert call_args["MaxNumberOfMessages"] == 1
        assert call_args["WaitTimeSeconds"] == 0
        assert call_args["VisibilityTimeout"] == 30

    @pytest.mark.asyncio
    async def test_receive_messages_error(self, mock_session):
        """Test receive messages with SQS error."""
        mock_session_obj, mock_client = mock_session
        mock_client.receive_message.side_effect = Exception("SQS error")

        with pytest.raises(Exception, match="SQS error"):
            await sqs.receive_messages(queue_name="test-queue")


class TestDeleteMessage:
    """Test message deletion functionality."""

    @pytest.mark.asyncio
    async def test_delete_message_success(self, mock_session):
        """Test successful message deletion."""
        mock_session_obj, mock_client = mock_session
        expected_response = {}
        mock_client.delete_message.return_value = expected_response

        result = await sqs.delete_message(
            queue_name="test-queue",
            receipt_handle="test-receipt-handle"
        )

        mock_client.delete_message.assert_called_once()
        call_args = mock_client.delete_message.call_args[1]

        assert call_args["QueueUrl"] == sqs.get_queue_url("test-queue")
        assert call_args["ReceiptHandle"] == "test-receipt-handle"
        assert result == expected_response

    @pytest.mark.asyncio
    async def test_delete_message_error(self, mock_session):
        """Test delete message with SQS error."""
        mock_session_obj, mock_client = mock_session
        mock_client.delete_message.side_effect = Exception("SQS error")

        with pytest.raises(Exception, match="SQS error"):
            await sqs.delete_message(
                queue_name="test-queue",
                receipt_handle="test-receipt-handle"
            )


class TestPurgeQueue:
    """Test queue purging functionality."""

    @pytest.mark.asyncio
    async def test_purge_queue_success(self, mock_session):
        """Test successful queue purging."""
        mock_session_obj, mock_client = mock_session
        expected_response = {}
        mock_client.purge_queue.return_value = expected_response

        result = await sqs.purge_queue(queue_name="test-queue")

        mock_client.purge_queue.assert_called_once()
        call_args = mock_client.purge_queue.call_args[1]

        assert call_args["QueueUrl"] == sqs.get_queue_url("test-queue")
        assert result == expected_response

    @pytest.mark.asyncio
    async def test_purge_queue_error(self, mock_session):
        """Test purge queue with SQS error."""
        mock_session_obj, mock_client = mock_session
        mock_client.purge_queue.side_effect = Exception("SQS error")

        with pytest.raises(Exception, match="SQS error"):
            await sqs.purge_queue(queue_name="test-queue")


class TestGetQueueAttributes:
    """Test queue attributes functionality."""

    @pytest.mark.asyncio
    async def test_get_queue_attributes_success(self, mock_session):
        """Test successful queue attributes retrieval."""
        mock_session_obj, mock_client = mock_session
        expected_attributes = {
            "QueueArn": "arn:aws:sqs:us-east-1:123456789012:test-queue",
            "ApproximateNumberOfMessages": "5",
            "ApproximateNumberOfMessagesNotVisible": "2"
        }
        mock_client.get_queue_attributes.return_value = {'Attributes': expected_attributes}

        result = await sqs.get_queue_attributes(
            queue_name="test-queue",
            attribute_names=["QueueArn", "ApproximateNumberOfMessages"]
        )

        mock_client.get_queue_attributes.assert_called_once()
        call_args = mock_client.get_queue_attributes.call_args[1]

        assert call_args["QueueUrl"] == sqs.get_queue_url("test-queue")
        assert call_args["AttributeNames"] == ["QueueArn", "ApproximateNumberOfMessages"]
        assert result == expected_attributes

    @pytest.mark.asyncio
    async def test_get_queue_attributes_default(self, mock_session):
        """Test queue attributes with default parameters."""
        mock_session_obj, mock_client = mock_session
        mock_client.get_queue_attributes.return_value = {'Attributes': {}}

        await sqs.get_queue_attributes(queue_name="test-queue")

        call_args = mock_client.get_queue_attributes.call_args[1]
        assert call_args["AttributeNames"] == ["All"]

    @pytest.mark.asyncio
    async def test_get_queue_attributes_empty_response(self, mock_session):
        """Test queue attributes with empty response."""
        mock_session_obj, mock_client = mock_session
        mock_client.get_queue_attributes.return_value = {}

        result = await sqs.get_queue_attributes(queue_name="test-queue")

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_queue_attributes_error(self, mock_session):
        """Test get queue attributes with SQS error."""
        mock_session_obj, mock_client = mock_session
        mock_client.get_queue_attributes.side_effect = Exception("SQS error")

        with pytest.raises(Exception, match="SQS error"):
            await sqs.get_queue_attributes(queue_name="test-queue")


class TestSendMessagesBatch:
    """Test batch message sending functionality."""

    @pytest.mark.asyncio
    async def test_send_messages_batch_success(self, mock_session):
        """Test successful batch message sending."""
        mock_session_obj, mock_client = mock_session
        expected_response = {
            'Successful': [
                {'Id': '0', 'MessageId': 'msg-1'},
                {'Id': '1', 'MessageId': 'msg-2'}
            ],
            'Failed': []
        }
        mock_client.send_message_batch.return_value = expected_response

        messages = [
            {'body': {'type': 'test1'}, 'delay_seconds': 5},
            {'body': 'test message 2', 'message_attributes': {'key': 'value'}}
        ]

        result = await sqs.send_messages_batch(
            queue_name="test-queue",
            messages=messages
        )

        mock_client.send_message_batch.assert_called_once()
        call_args = mock_client.send_message_batch.call_args[1]

        assert call_args["QueueUrl"] == sqs.get_queue_url("test-queue")

        # Verify entries structure
        entries = call_args["Entries"]
        assert len(entries) == 2

        # First entry
        assert entries[0]["Id"] == "0"
        assert entries[0]["MessageBody"] == json.dumps({'type': 'test1'})
        assert entries[0]["DelaySeconds"] == 5

        # Second entry
        assert entries[1]["Id"] == "1"
        assert entries[1]["MessageBody"] == 'test message 2'
        assert entries[1]["MessageAttributes"] == {'key': 'value'}

        assert result == expected_response

    @pytest.mark.asyncio
    async def test_send_messages_batch_with_failures(self, mock_session):
        """Test batch message sending with some failures."""
        mock_session_obj, mock_client = mock_session
        expected_response = {
            'Successful': [{'Id': '0', 'MessageId': 'msg-1'}],
            'Failed': [{'Id': '1', 'Code': 'InvalidParameterValue'}]
        }
        mock_client.send_message_batch.return_value = expected_response

        messages = [
            {'body': 'message 1'},
            {'body': 'message 2'}
        ]

        result = await sqs.send_messages_batch(
            queue_name="test-queue",
            messages=messages
        )

        assert result == expected_response

    @pytest.mark.asyncio
    async def test_send_messages_batch_error(self, mock_session):
        """Test batch message sending with SQS error."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_message_batch.side_effect = Exception("SQS error")

        messages = [{'body': 'test message'}]

        with pytest.raises(Exception, match="SQS error"):
            await sqs.send_messages_batch(
                queue_name="test-queue",
                messages=messages
            )


class TestChangeMessageVisibility:
    """Test change_message_visibility functionality."""

    @pytest.mark.asyncio
    async def test_change_message_visibility_success(self, mock_session):
        mock_session_obj, mock_client = mock_session
        mock_client.change_message_visibility.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

        result = await sqs.change_message_visibility(
            queue_name="test-queue",
            receipt_handle="rh-123",
            timeout_seconds=600,
        )

        mock_client.change_message_visibility.assert_called_once()
        call_args = mock_client.change_message_visibility.call_args[1]
        assert call_args["QueueUrl"] == sqs.get_queue_url("test-queue")
        assert call_args["ReceiptHandle"] == "rh-123"
        assert call_args["VisibilityTimeout"] == 600
        assert result["ResponseMetadata"]["HTTPStatusCode"] == 200

    @pytest.mark.asyncio
    async def test_change_message_visibility_error(self, mock_session):
        mock_session_obj, mock_client = mock_session
        mock_client.change_message_visibility.side_effect = Exception("SQS error")

        with pytest.raises(Exception, match="SQS error"):
            await sqs.change_message_visibility(
                queue_name="test-queue",
                receipt_handle="rh-123",
                timeout_seconds=600,
            )


class TestGetSyncSqsClient:
    """Test synchronous SQS client functionality."""

    def test_get_sync_sqs_client(self):
        """Test getting synchronous SQS client."""
        with patch('boto3.client') as mock_boto3_client:
            mock_client = Mock()
            mock_boto3_client.return_value = mock_client

            result = sqs.get_sync_sqs_client()

            mock_boto3_client.assert_called_once_with(
                'sqs',
                region_name=sqs.AWS_REGION,
                endpoint_url=sqs.AWS_ENDPOINT_URL
            )
            assert result == mock_client


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_session_creation_error(self):
        """Test handling of session creation errors."""
        with patch('media_summarizer.utils.sqs.session') as mock_session:
            mock_session.create_client.side_effect = Exception("Session error")

            with pytest.raises(Exception, match="Session error"):
                await sqs.send_message("queue", "message")

    @pytest.mark.asyncio
    async def test_generic_exception_handling(self, mock_session):
        """Test handling of generic exceptions."""
        mock_session_obj, mock_client = mock_session
        mock_client.send_message.side_effect = Exception("Network error")

        with pytest.raises(Exception, match="Network error"):
            await sqs.send_message("queue", "message")
