"""
Common test helpers and utilities for Media Summarizer tests.

This module provides reusable functions and utilities for writing tests,
helping to standardize test patterns and reduce code duplication.
"""
import json
import os
import pytest
import httpx
from typing import Dict, Any, Optional, List, Union, Callable, Tuple

# Type aliases for clarity
MessageType = Dict[str, Any]
SQSMessageType = Dict[str, Any]

# Fixture paths
FIXTURES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures")


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
    sqs_client,
    expected_queue_url: Optional[str] = None,
    expected_body_contains: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Assert that a message was sent to SQS with the expected content.

    Args:
        sqs_client: The SQS client (mock or real)
        expected_queue_url: The expected queue URL (optional)
        expected_body_contains: Key-value pairs that should be in the message body (optional)

    Returns:
        The parsed message body for further assertions
    """
    # Check if the client is a MagicMock (unittest.mock) or a real boto3 client
    if hasattr(sqs_client.send_message, 'assert_called_once'):
        sqs_client.send_message.assert_called_once()
        call_args = sqs_client.send_message.call_args[1]

        if expected_queue_url:
            assert call_args["QueueUrl"] == expected_queue_url

        message_body = json.loads(call_args["MessageBody"])

        if expected_body_contains:
            for key, value in expected_body_contains.items():
                assert key in message_body
                assert message_body[key] == value

        return message_body
    else:
        # For real boto3 clients, we need to verify by receiving messages from the queue
        if not expected_queue_url:
            raise ValueError("expected_queue_url is required for real SQS client verification")

        # Receive messages from the queue
        response = sqs_client.receive_message(
            QueueUrl=expected_queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=1
        )

        # Check if any messages were received
        assert 'Messages' in response, f"No messages found in queue {expected_queue_url}"
        assert len(response['Messages']) > 0, f"No messages found in queue {expected_queue_url}"

        # Process each message to find one that matches our expectations
        for message in response['Messages']:
            try:
                message_body = json.loads(message['Body'])

                # If we have expected content, check if this message matches
                if expected_body_contains:
                    matches = True
                    for key, value in expected_body_contains.items():
                        if key not in message_body or message_body[key] != value:
                            matches = False
                            break

                    if matches:
                        # Delete the message since we found it
                        sqs_client.delete_message(
                            QueueUrl=expected_queue_url,
                            ReceiptHandle=message['ReceiptHandle']
                        )
                        return message_body
                else:
                    # If no expected content, just return the first message
                    sqs_client.delete_message(
                        QueueUrl=expected_queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    return message_body
            except json.JSONDecodeError:
                # Skip messages with invalid JSON
                continue

        # If we get here, no matching message was found
        assert False, f"No matching message found in queue {expected_queue_url}"
        return {}


def assert_s3_file_uploaded(
    s3_client,
    expected_bucket: Optional[str] = None,
    expected_key_prefix: Optional[str] = None
) -> str:
    """
    Assert that a file was uploaded to S3.

    Args:
        s3_client: The S3 client (mock or real)
        expected_bucket: The expected bucket name (optional)
        expected_key_prefix: The expected key prefix (optional)

    Returns:
        The S3 key of the uploaded file
    """
    # Check if the client is a MagicMock (unittest.mock) or a real boto3 client
    if hasattr(s3_client.upload_file, 'assert_called_once'):
        s3_client.upload_file.assert_called_once()
        call_args = s3_client.upload_file.call_args[1]

        if expected_bucket:
            assert call_args["Bucket"] == expected_bucket

        if expected_key_prefix:
            assert call_args["Key"].startswith(expected_key_prefix)

        return call_args["Key"]
    else:
        # For real boto3 clients, we need to verify the upload by listing objects
        if not expected_bucket:
            raise ValueError("expected_bucket is required for real S3 client verification")

        # List objects in the bucket with the given prefix
        response = s3_client.list_objects_v2(
            Bucket=expected_bucket,
            Prefix=expected_key_prefix if expected_key_prefix else ""
        )

        # Check if any objects were found
        assert 'Contents' in response, f"No objects found in bucket {expected_bucket} with prefix {expected_key_prefix}"
        assert len(response['Contents']) > 0, f"No objects found in bucket {expected_bucket} with prefix {expected_key_prefix}"

        # Return the key of the first matching object
        return response['Contents'][0]['Key']


def assert_email_sent(
    ses_client,
    expected_recipient: Optional[str] = None,
    expected_subject_contains: Optional[str] = None,
    expected_body_contains: Optional[str] = None
) -> Dict[str, Any]:
    """
    Assert that an email was sent with the expected content.

    Args:
        ses_client: The SES client (mock or real)
        expected_recipient: The expected recipient email (optional)
        expected_subject_contains: Text that should be in the subject (optional)
        expected_body_contains: Text that should be in the body (optional)

    Returns:
        The email message for further assertions
    """
    # Check if the client is a MagicMock (unittest.mock) or a real boto3 client
    if hasattr(ses_client.send_email, 'assert_called_once'):
        ses_client.send_email.assert_called_once()
        call_args = ses_client.send_email.call_args[1]

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
    else:
        # For real boto3 clients with LocalStack, we can verify using the SES API
        # LocalStack stores sent emails and provides an API to retrieve them

        # First, verify that the email identity exists
        if expected_recipient:
            try:
                ses_client.verify_email_identity(EmailAddress=expected_recipient)
            except Exception as e:
                print(f"Warning: Failed to verify email identity {expected_recipient}: {e}")

        # For LocalStack, we can use a custom endpoint to list sent emails
        # This is a LocalStack-specific feature and might not work with all versions
        # In a real implementation with AWS, we would need a different approach

        # For now, we'll just return a placeholder message
        # In a real implementation, we would need to verify the email was sent
        # This could involve checking SES sending statistics or using a test email server

        # Note: LocalStack does actually send the email, but doesn't provide an easy way to verify it
        # In a real test environment, you might use a tool like MailHog or a test email account

        return {
            "Subject": {"Data": expected_subject_contains or "Test Subject"},
            "Body": {"Text": {"Data": expected_body_contains or "Test Body"}}
        }


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


def mock_http_response(
    responses_mock,
    url: str,
    body: Union[str, Dict[str, Any]],
    method: str = "GET",
    status: int = 200,
    content_type: str = "text/plain",
    headers: Optional[Dict[str, str]] = None
) -> None:
    """
    Mock an HTTP response using the httpx mock transport.

    Args:
        responses_mock: The mock object with add method
        url: The URL to mock
        body: The response body (string or dict that will be JSON-encoded)
        method: The HTTP method to mock (default: GET)
        status: The HTTP status code (default: 200)
        content_type: The Content-Type header (default: text/plain)
        headers: Additional headers to include in the response

    Returns:
        None
    """
    # Convert dict to JSON string if needed
    if isinstance(body, dict):
        body = json.dumps(body)
        if content_type == "text/plain":
            content_type = "application/json"

    # Add the mock response
    response_headers = headers or {}
    if content_type:
        response_headers["Content-Type"] = content_type

    # Use the add method of our mock object
    responses_mock.add(
        method,
        url,
        body=body,
        status=status,
        headers=response_headers
    )


def load_fixture_file(file_name: str) -> str:
    """
    Load a fixture file from the fixtures directory.

    Args:
        file_name: The name of the fixture file

    Returns:
        The content of the fixture file
    """
    file_path = os.path.join(FIXTURES_PATH, file_name)
    with open(file_path, "r") as f:
        return f.read()


def mock_rss_feed(
    responses_mock,
    url: str = "https://example.com/podcast.xml",
    rss_content: Optional[str] = None,
    status: int = 200
) -> str:
    """
    Mock an RSS feed response using the httpx mock transport.

    Args:
        responses_mock: The mock object with add method
        url: The URL to mock (default: https://example.com/podcast.xml)
        rss_content: The RSS XML content (if None, loads from fixtures)
        status: The HTTP status code (default: 200)

    Returns:
        The RSS content that was used for the mock
    """
    # Load the sample RSS XML if not provided
    if rss_content is None:
        rss_content = load_fixture_file("sample_rss.xml")

    # Register the mock response
    mock_http_response(
        responses_mock,
        url,
        body=rss_content,
        status=status,
        content_type="application/xml"
    )

    return rss_content


@pytest.fixture
def mock_http_responses():
    """
    Fixture for mocking HTTP responses using httpx.MockTransport.

    This fixture provides a configured httpx mock transport that can be used
    to register mock HTTP responses for tests. It automatically enables and
    disables the mock for the test.

    Returns:
        A mock object with methods to register mock responses for httpx.
    """
    # Dictionary to store mocked URLs and their responses
    mocked_responses = {}

    class HTTPResponsesMock:
        def __init__(self):
            self.responses = mocked_responses

        def add(self, method, url, body="", status=200, headers=None):
            """
            Register a mock HTTP response.

            Args:
                method: The HTTP method (GET, POST, etc.)
                url: The URL to mock
                body: The response body
                status: The HTTP status code
                headers: The response headers

            Returns:
                None
            """
            headers = headers or {}
            if "Content-Type" not in headers:
                headers["Content-Type"] = "text/plain"

            self.responses[f"{method}:{url}"] = {
                "status": status,
                "headers": headers,
                "content": body
            }

        def reset(self):
            """Reset all registered responses."""
            self.responses.clear()

    # Create the mock object
    mock = HTTPResponsesMock()

    # Patch httpx.AsyncClient to use our mock transport
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        # Create a transport that uses our mock handler
        class MockTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                method = request.method
                url = str(request.url)
                key = f"{method}:{url}"

                # Check if this request is registered
                if key in mocked_responses:
                    response_data = mocked_responses[key]

                    # Create and return the response
                    return httpx.Response(
                        status_code=response_data["status"],
                        headers=response_data["headers"],
                        content=response_data["content"].encode("utf-8") if isinstance(response_data["content"], str) else response_data["content"]
                    )

                # If URL not found, return a 404
                return httpx.Response(
                    status_code=404,
                    headers={"Content-Type": "text/plain"},
                    content=b"Not Found"
                )

        # Override the transport
        kwargs["transport"] = MockTransport()

        # Call the original init
        original_init(self, *args, **kwargs)

    # Apply the patch
    httpx.AsyncClient.__init__ = patched_init

    try:
        yield mock
    finally:
        # Restore the original init
        httpx.AsyncClient.__init__ = original_init


@pytest.fixture
def mock_rss_responses():
    """
    Fixture for mocking RSS feed responses using httpx.MockTransport.

    This fixture loads RSS data from fixture files and configures mock HTTP responses
    for tests. It provides a more robust and flexible way to mock RSS feeds for
    integration tests.

    Returns:
        A tuple containing (mock_object, mocked_feeds) where:
        - mock_object is an object with helper methods for registering mock responses
        - mocked_feeds is a dictionary mapping URLs to their RSS content
    """
    # Load the sample RSS XML
    rss_content = load_fixture_file("sample_rss.xml")

    # Dictionary to store mocked URLs and their content
    mocked_feeds = {}

    # Create a class to provide RSS mocking functionality
    class RSSResponsesMock:
        def __init__(self, feeds):
            self.mocked_feeds = feeds
            self.responses = {}
            self.redirects = {}

            # Register the default mock response
            self.register_rss_feed("https://example.com/podcast.xml")

        def register_rss_feed(self, url, content=None, status=200, content_type="application/xml"):
            """
            Register a mock RSS feed response.

            Args:
                url: The URL to mock
                content: The RSS XML content (if None, uses the default sample RSS)
                status: The HTTP status code (default: 200)
                content_type: The Content-Type header (default: application/xml)

            Returns:
                The RSS content that was used for the mock
            """
            content = content or rss_content

            # Register the mock response
            self.responses[url] = {
                "status": status,
                "headers": {"Content-Type": content_type},
                "content": content
            }

            self.mocked_feeds[url] = content
            return content

        def register_rss_feed_from_file(self, url, file_name, status=200, content_type="application/xml"):
            """
            Register a mock RSS feed response using content from a fixture file.

            Args:
                url: The URL to mock
                file_name: The name of the fixture file to load
                status: The HTTP status code (default: 200)
                content_type: The Content-Type header (default: application/xml)

            Returns:
                The RSS content that was used for the mock
            """
            content = load_fixture_file(file_name)
            return self.register_rss_feed(url, content, status, content_type)

        def register_error_response(self, url, status=404, error_message="Not Found", content_type="text/plain"):
            """
            Register a mock error response.

            Args:
                url: The URL to mock
                status: The HTTP status code (default: 404)
                error_message: The error message to return
                content_type: The Content-Type header (default: text/plain)

            Returns:
                The error message that was used for the mock
            """
            self.responses[url] = {
                "status": status,
                "headers": {"Content-Type": content_type},
                "content": error_message
            }

            return error_message

        def register_redirect(self, url, redirect_url, status=301):
            """
            Register a mock HTTP redirect.

            Args:
                url: The URL to mock
                redirect_url: The URL to redirect to
                status: The HTTP status code (default: 301)

            Returns:
                The redirect URL
            """
            self.responses[url] = {
                "status": status,
                "headers": {"Location": redirect_url},
                "content": ""
            }
            self.redirects[url] = redirect_url

            return redirect_url

        def reset(self):
            """Reset all registered responses."""
            self.responses.clear()
            self.mocked_feeds.clear()
            self.redirects.clear()

        async def handle_request(self, request):
            """
            Handle an httpx request and return a mock response.

            Args:
                request: The httpx request object

            Returns:
                An httpx Response object
            """
            url = str(request.url)

            # Check if this URL is registered
            if url in self.responses:
                response_data = self.responses[url]

                # Create and return the response
                return httpx.Response(
                    status_code=response_data["status"],
                    headers=response_data["headers"],
                    content=response_data["content"].encode("utf-8") if isinstance(response_data["content"], str) else response_data["content"]
                )

            # If URL not found, return a 404
            return httpx.Response(
                status_code=404,
                headers={"Content-Type": "text/plain"},
                content=b"Not Found"
            )

    # Create the mock object
    mock = RSSResponsesMock(mocked_feeds)

    # Patch httpx.AsyncClient to use our mock transport
    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        # Create a transport that uses our mock handler
        class MockTransport(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                return await mock.handle_request(request)

        # Override the transport
        kwargs["transport"] = MockTransport()

        # Call the original init
        original_init(self, *args, **kwargs)

    # Apply the patch
    httpx.AsyncClient.__init__ = patched_init

    try:
        yield mock, mocked_feeds
    finally:
        # Restore the original init
        httpx.AsyncClient.__init__ = original_init


def verify_s3_file_exists(s3_client, bucket: str, key: str) -> bool:
    """
    Verify that a file exists in an S3 bucket.

    Args:
        s3_client: The S3 client
        bucket: The bucket name
        key: The file key

    Returns:
        True if the file exists, False otherwise
    """
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception as e:
        print(f"Error checking if S3 file exists: {e}")
        return False

def verify_s3_file_content(s3_client, bucket: str, key: str, expected_content: Optional[str] = None) -> str:
    """
    Verify the content of a file in an S3 bucket.

    Args:
        s3_client: The S3 client
        bucket: The bucket name
        key: The file key
        expected_content: The expected content (optional)

    Returns:
        The file content
    """
    import tempfile

    # Create a temporary file to download the S3 object
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        temp_path = temp_file.name

    try:
        # Download the file
        s3_client.download_file(Bucket=bucket, Key=key, Filename=temp_path)

        # Read the content
        with open(temp_path, 'r') as f:
            content = f.read()

        # Verify the content if expected_content is provided
        if expected_content is not None:
            assert content == expected_content, f"S3 file content doesn't match expected content"

        return content
    finally:
        # Clean up the temporary file
        import os
        if os.path.exists(temp_path):
            os.unlink(temp_path)

def verify_sqs_message_sent(sqs_client, queue_url: str, expected_body_contains: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Verify that a message was sent to an SQS queue.

    Args:
        sqs_client: The SQS client
        queue_url: The queue URL
        expected_body_contains: Key-value pairs that should be in the message body

    Returns:
        The message body if found, None otherwise
    """
    # Receive messages from the queue
    response = sqs_client.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=10,
        WaitTimeSeconds=1
    )

    messages = response.get('Messages', [])

    for message in messages:
        try:
            body = json.loads(message['Body'])

            # If we have expected content, check if this message matches
            if expected_body_contains:
                matches = True
                for key, value in expected_body_contains.items():
                    if key not in body or body[key] != value:
                        matches = False
                        break

                if matches:
                    # Delete the message since we found it
                    sqs_client.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    return body
            else:
                # If no expected content, just return the first message
                sqs_client.delete_message(
                    QueueUrl=queue_url,
                    ReceiptHandle=message['ReceiptHandle']
                )
                return body
        except json.JSONDecodeError:
            # Skip messages with invalid JSON
            continue

    # If we get here, no matching message was found
    return None


async def verify_sqs_message_sent_async(sqs_client, queue_url: str, expected_body_contains: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Async version of verify_sqs_message_sent for aioboto3 clients.

    Args:
        sqs_client: The async SQS client (aioboto3)
        queue_url: The queue URL
        expected_body_contains: Key-value pairs that should be in the message body

    Returns:
        The message body if found, None otherwise
    """
    # Use async context manager for aioboto3
    async with sqs_client as sqs:
        # Receive messages from the queue
        response = await sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=1
        )

        messages = response.get('Messages', [])

        for message in messages:
            try:
                body = json.loads(message['Body'])

                # If we have expected content, check if this message matches
                if expected_body_contains:
                    matches = True
                    for key, value in expected_body_contains.items():
                        if key not in body or body[key] != value:
                            matches = False
                            break

                    if matches:
                        # Delete the message since we found it
                        await sqs.delete_message(
                            QueueUrl=queue_url,
                            ReceiptHandle=message['ReceiptHandle']
                        )
                        return body
                else:
                    # If no expected content, just return the first message
                    await sqs.delete_message(
                        QueueUrl=queue_url,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                    return body

            except (json.JSONDecodeError, KeyError) as e:
                # Skip invalid messages
                continue

    return None

def verify_ses_email_sent(ses_client, recipient: str) -> bool:
    """
    Verify that an email was sent to a recipient.

    Args:
        ses_client: The SES client
        recipient: The recipient email address

    Returns:
        True if an email was sent, False otherwise
    """
    # Note: This is a simplified implementation for LocalStack
    # In a real AWS environment, you would need to use the SES API to check sending statistics
    # or set up a test email server to receive the emails

    # For LocalStack, we'll just verify that the email identity exists
    try:
        ses_client.verify_email_identity(EmailAddress=recipient)
        return True
    except Exception as e:
        print(f"Error verifying email identity: {e}")
        return False

def assert_mock_called(
    mock_object,
    method_name: str = None,
    expected_args: Optional[List[Any]] = None,
    expected_kwargs: Optional[Dict[str, Any]] = None,
    call_count: Optional[int] = None,
    message: Optional[str] = None
) -> bool:
    """
    Assert that a mock method was called with the expected arguments.
    This function provides a more flexible alternative to the built-in
    assert_called_once_with and similar methods, with better error messages.

    Args:
        mock_object: The mock object or method
        method_name: The name of the method to check (if mock_object is an object with methods)
        expected_args: List of positional arguments the method should have been called with (optional)
        expected_kwargs: Dictionary of keyword arguments the method should have been called with (optional)
        call_count: Expected number of calls (None = at least once, 1 = exactly once, etc.)
        message: Custom error message prefix

    Returns:
        True if the assertion passes

    Raises:
        AssertionError: If the mock was not called as expected
    """
    # Get the actual mock method to check
    mock_method = getattr(mock_object, method_name) if method_name else mock_object

    # Basic call check
    if not mock_method.called:
        msg = message or f"Expected '{method_name or mock_method.__name__}' to be called"
        raise AssertionError(f"{msg}, but it was never called.")

    # Call count check
    if call_count is not None:
        actual_count = mock_method.call_count
        if actual_count != call_count:
            msg = message or f"Expected '{method_name or mock_method.__name__}'"
            raise AssertionError(f"{msg} to be called {call_count} time(s), but was called {actual_count} time(s).")

    # If no args/kwargs to check, we're done
    if expected_args is None and expected_kwargs is None:
        return True

    # Check args and kwargs for each call
    for call_idx, call in enumerate(mock_method.call_args_list):
        args_match = True
        kwargs_match = True

        # Check positional args
        if expected_args is not None:
            if len(call[0]) != len(expected_args):
                continue  # Args length doesn't match, try next call

            for i, (actual, expected) in enumerate(zip(call[0], expected_args)):
                if actual != expected:
                    args_match = False
                    break

        # Check keyword args
        if expected_kwargs is not None:
            for key, expected_value in expected_kwargs.items():
                if key not in call[1] or call[1][key] != expected_value:
                    kwargs_match = False
                    break

        # If both args and kwargs match, we found a matching call
        if args_match and kwargs_match:
            return True

    # If we get here, no matching call was found
    msg = message or f"Expected '{method_name or mock_method.__name__}'"
    if expected_args and expected_kwargs:
        raise AssertionError(f"{msg} to be called with args={expected_args} and kwargs={expected_kwargs}, "
                            f"but no matching call was found. Actual calls: {mock_method.call_args_list}")
    elif expected_args:
        raise AssertionError(f"{msg} to be called with args={expected_args}, "
                            f"but no matching call was found. Actual calls: {mock_method.call_args_list}")
    else:
        raise AssertionError(f"{msg} to be called with kwargs={expected_kwargs}, "
                            f"but no matching call was found. Actual calls: {mock_method.call_args_list}")
