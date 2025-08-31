"""
Unit tests for S3 utilities.

This module contains unit tests for all S3 utility functions,
using mocked aiobotocore operations to test the logic without requiring
actual AWS services.
"""
import pytest
import asyncio
import os
import tempfile
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from io import BytesIO

from media_summarizer.utils import s3


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client."""
    mock_client = AsyncMock()
    return mock_client


@pytest.fixture
def mock_session():
    """Create a mock aiobotocore session."""
    with patch('media_summarizer.utils.s3.session') as mock_session:
        mock_client = AsyncMock()
        mock_session.create_client.return_value.__aenter__.return_value = mock_client
        yield mock_session, mock_client


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test content")
        temp_file_path = f.name

    yield temp_file_path

    # Cleanup
    if os.path.exists(temp_file_path):
        os.unlink(temp_file_path)


class TestUploadFile:
    """Test file upload functionality."""

    @pytest.mark.asyncio
    async def test_upload_file_success(self, mock_session, temp_file):
        """Test successful file upload."""
        mock_session_obj, mock_client = mock_session
        mock_client.put_object.return_value = {'ETag': '"test-etag"'}

        result = await s3.upload_file(
            bucket="test-bucket",
            key="test-key",
            file_path=temp_file
        )

        mock_client.put_object.assert_called_once()
        call_args = mock_client.put_object.call_args[1]
        assert call_args["Bucket"] == "test-bucket"
        assert call_args["Key"] == "test-key"
        assert call_args["ContentType"] == "application/octet-stream"
        assert result == {'ETag': '"test-etag"'}

    @pytest.mark.asyncio
    async def test_upload_file_with_metadata(self, mock_session, temp_file):
        """Test file upload with metadata."""
        mock_session_obj, mock_client = mock_session
        mock_client.put_object.return_value = {'ETag': '"test-etag"'}

        metadata = {"creator": "test", "version": "1.0"}
        await s3.upload_file(
            bucket="test-bucket",
            key="test-key",
            file_path=temp_file,
            metadata=metadata,
            content_type="text/plain"
        )

        call_args = mock_client.put_object.call_args[1]
        assert call_args["Metadata"] == metadata
        assert call_args["ContentType"] == "text/plain"

    @pytest.mark.asyncio
    async def test_upload_file_not_found(self, mock_session):
        """Test upload with non-existent file."""
        mock_session_obj, mock_client = mock_session

        with pytest.raises(FileNotFoundError, match="File not found: /nonexistent/file.txt"):
            await s3.upload_file(
                bucket="test-bucket",
                key="test-key",
                file_path="/nonexistent/file.txt"
            )

    @pytest.mark.asyncio
    async def test_upload_file_s3_error(self, mock_session, temp_file):
        """Test upload with S3 error."""
        mock_session_obj, mock_client = mock_session
        mock_client.put_object.side_effect = Exception("S3 error")

        with pytest.raises(Exception, match="S3 error"):
            await s3.upload_file(
                bucket="test-bucket",
                key="test-key",
                file_path=temp_file
            )


class TestUploadFileObject:
    """Test file object upload functionality."""

    @pytest.mark.asyncio
    async def test_upload_file_object_success(self, mock_session):
        """Test successful file object upload."""
        mock_session_obj, mock_client = mock_session
        mock_client.put_object.return_value = {'ETag': '"test-etag"'}

        file_obj = BytesIO(b"test content")
        result = await s3.upload_file_object(
            bucket="test-bucket",
            key="test-key",
            file_obj=file_obj,
            content_type="text/plain"
        )

        mock_client.put_object.assert_called_once()
        call_args = mock_client.put_object.call_args[1]
        assert call_args["Bucket"] == "test-bucket"
        assert call_args["Key"] == "test-key"
        assert call_args["Body"] == file_obj
        assert call_args["ContentType"] == "text/plain"
        assert result == {'ETag': '"test-etag"'}

    @pytest.mark.asyncio
    async def test_upload_file_object_with_metadata(self, mock_session):
        """Test file object upload with metadata."""
        mock_session_obj, mock_client = mock_session
        mock_client.put_object.return_value = {'ETag': '"test-etag"'}

        file_obj = BytesIO(b"test content")
        metadata = {"creator": "test"}

        await s3.upload_file_object(
            bucket="test-bucket",
            key="test-key",
            file_obj=file_obj,
            metadata=metadata
        )

        call_args = mock_client.put_object.call_args[1]
        assert call_args["Metadata"] == metadata


class TestDownloadFile:
    """Test file download functionality."""

    @pytest.mark.asyncio
    async def test_download_file_success(self, mock_session, tmp_path):
        """Test successful file download."""
        mock_session_obj, mock_client = mock_session

        # Mock the response with Body that has read() method
        mock_body = AsyncMock()
        mock_body.read.return_value = b"test content"
        mock_response = {"Body": mock_body}
        mock_client.get_object.return_value = mock_response

        download_path = tmp_path / "downloaded_file.txt"
        result = await s3.download_file(
            bucket="test-bucket",
            key="test-key",
            file_path=str(download_path)
        )

        mock_client.get_object.assert_called_once_with(Bucket="test-bucket", Key="test-key")
        assert result is True
        assert download_path.read_bytes() == b"test content"

    @pytest.mark.asyncio
    async def test_download_file_creates_directory(self, mock_session, tmp_path):
        """Test download creates parent directories."""
        mock_session_obj, mock_client = mock_session

        # Mock the response with Body that has read() method
        mock_body = AsyncMock()
        mock_body.read.return_value = b"test content"
        mock_response = {"Body": mock_body}
        mock_client.get_object.return_value = mock_response

        download_path = tmp_path / "new_dir" / "downloaded_file.txt"
        await s3.download_file(
            bucket="test-bucket",
            key="test-key",
            file_path=str(download_path)
        )

        assert download_path.parent.exists()

    @pytest.mark.asyncio
    async def test_download_file_s3_error(self, mock_session, tmp_path):
        """Test download with S3 error."""
        mock_session_obj, mock_client = mock_session
        mock_client.get_object.side_effect = Exception("S3 error")

        download_path = tmp_path / "downloaded_file.txt"
        with pytest.raises(Exception, match="S3 error"):
            await s3.download_file(
                bucket="test-bucket",
                key="test-key",
                file_path=str(download_path)
            )


class TestDownloadFileToMemory:
    """Test file download to memory functionality."""

    @pytest.mark.asyncio
    async def test_download_file_to_memory_success(self, mock_session):
        """Test successful file download to memory."""
        mock_session_obj, mock_client = mock_session

        mock_response = {
            'Body': AsyncMock()
        }
        mock_response['Body'].read.return_value = b"test content"
        mock_client.get_object.return_value = mock_response

        result = await s3.download_file_to_memory(
            bucket="test-bucket",
            key="test-key"
        )

        mock_client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test-key"
        )
        assert result == b"test content"

    @pytest.mark.asyncio
    async def test_download_file_to_memory_s3_error(self, mock_session):
        """Test download to memory with S3 error."""
        mock_session_obj, mock_client = mock_session
        mock_client.get_object.side_effect = Exception("S3 error")

        with pytest.raises(Exception, match="S3 error"):
            await s3.download_file_to_memory(
                bucket="test-bucket",
                key="test-key"
            )


class TestGetObject:
    """Test get object functionality."""

    @pytest.mark.asyncio
    async def test_get_object_success(self, mock_session):
        """Test successful get object."""
        mock_session_obj, mock_client = mock_session
        expected_response = {
            'Body': b"test content",
            'ContentType': 'text/plain'
        }
        mock_client.get_object.return_value = expected_response

        result = await s3.get_object(
            bucket="test-bucket",
            key="test-key"
        )

        mock_client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test-key"
        )
        assert result == expected_response


class TestDeleteObject:
    """Test delete object functionality."""

    @pytest.mark.asyncio
    async def test_delete_object_success(self, mock_session):
        """Test successful object deletion."""
        mock_session_obj, mock_client = mock_session
        expected_response = {'DeleteMarker': True}
        mock_client.delete_object.return_value = expected_response

        result = await s3.delete_object(
            bucket="test-bucket",
            key="test-key"
        )

        mock_client.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test-key"
        )
        assert result == expected_response


class TestObjectExists:
    """Test object existence check functionality."""

    @pytest.mark.asyncio
    async def test_object_exists_true(self, mock_session):
        """Test object exists returns True."""
        mock_session_obj, mock_client = mock_session
        mock_client.head_object.return_value = {'ContentLength': 100}

        result = await s3.object_exists(
            bucket="test-bucket",
            key="test-key"
        )

        mock_client.head_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test-key"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_object_exists_false_404(self, mock_session):
        """Test object exists returns False for 404."""
        mock_session_obj, mock_client = mock_session

        error = Exception("Not Found")
        error.response = {'Error': {'Code': '404'}}
        mock_client.head_object.side_effect = error

        result = await s3.object_exists(
            bucket="test-bucket",
            key="test-key"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_object_exists_other_error(self, mock_session):
        """Test object exists with other error."""
        mock_session_obj, mock_client = mock_session

        error = Exception("Access Denied")
        error.response = {'Error': {'Code': '403'}}
        mock_client.head_object.side_effect = error

        with pytest.raises(Exception, match="Access Denied"):
            await s3.object_exists(
                bucket="test-bucket",
                key="test-key"
            )


class TestGeneratePresignedUrl:
    """Test presigned URL generation functionality."""

    @pytest.mark.asyncio
    async def test_generate_presigned_url_success(self, mock_session):
        """Test successful presigned URL generation."""
        mock_session_obj, mock_client = mock_session
        expected_url = "https://test-bucket.s3.amazonaws.com/test-key?signature=abc123"
        # Make sure the mock returns a string, not a coroutine
        mock_client.generate_presigned_url = Mock(return_value=expected_url)

        result = await s3.generate_presigned_url(
            bucket="test-bucket",
            key="test-key",
            expiration=7200,
            http_method="PUT"
        )

        mock_client.generate_presigned_url.assert_called_once_with(
            'put_object',
            Params={'Bucket': 'test-bucket', 'Key': 'test-key'},
            ExpiresIn=7200
        )
        assert result == expected_url

    @pytest.mark.asyncio
    async def test_generate_presigned_url_default_params(self, mock_session):
        """Test presigned URL generation with default parameters."""
        mock_session_obj, mock_client = mock_session
        mock_client.generate_presigned_url = Mock(return_value="https://example.com")

        await s3.generate_presigned_url(
            bucket="test-bucket",
            key="test-key"
        )

        mock_client.generate_presigned_url.assert_called_once_with(
            'get_object',
            Params={'Bucket': 'test-bucket', 'Key': 'test-key'},
            ExpiresIn=3600
        )


class TestListObjects:
    """Test list objects functionality."""

    @pytest.mark.asyncio
    async def test_list_objects_success(self, mock_session):
        """Test successful object listing."""
        mock_session_obj, mock_client = mock_session
        expected_objects = [
            {'Key': 'file1.txt', 'Size': 100},
            {'Key': 'file2.txt', 'Size': 200}
        ]
        mock_client.list_objects_v2.return_value = {'Contents': expected_objects}

        result = await s3.list_objects(
            bucket="test-bucket",
            prefix="folder/",
            max_keys=500
        )

        mock_client.list_objects_v2.assert_called_once_with(
            Bucket="test-bucket",
            MaxKeys=500,
            Prefix="folder/"
        )
        assert result == expected_objects

    @pytest.mark.asyncio
    async def test_list_objects_no_prefix(self, mock_session):
        """Test object listing without prefix."""
        mock_session_obj, mock_client = mock_session
        mock_client.list_objects_v2.return_value = {'Contents': []}

        await s3.list_objects(bucket="test-bucket")

        call_args = mock_client.list_objects_v2.call_args[1]
        assert 'Prefix' not in call_args
        assert call_args['MaxKeys'] == 1000

    @pytest.mark.asyncio
    async def test_list_objects_empty_result(self, mock_session):
        """Test object listing with empty result."""
        mock_session_obj, mock_client = mock_session
        mock_client.list_objects_v2.return_value = {}

        result = await s3.list_objects(bucket="test-bucket")

        assert result == []


class TestGetObjectMetadata:
    """Test get object metadata functionality."""

    @pytest.mark.asyncio
    async def test_get_object_metadata_success(self, mock_session):
        """Test successful metadata retrieval."""
        mock_session_obj, mock_client = mock_session
        expected_metadata = {
            'ContentLength': 100,
            'ContentType': 'text/plain',
            'Metadata': {'creator': 'test'}
        }
        mock_client.head_object.return_value = expected_metadata

        result = await s3.get_object_metadata(
            bucket="test-bucket",
            key="test-key"
        )

        mock_client.head_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="test-key"
        )
        assert result == expected_metadata


class TestCopyObject:
    """Test copy object functionality."""

    @pytest.mark.asyncio
    async def test_copy_object_success(self, mock_session):
        """Test successful object copy."""
        mock_session_obj, mock_client = mock_session
        expected_response = {'CopyObjectResult': {'ETag': '"test-etag"'}}
        mock_client.copy_object.return_value = expected_response

        result = await s3.copy_object(
            source_bucket="source-bucket",
            source_key="source-key",
            dest_bucket="dest-bucket",
            dest_key="dest-key"
        )

        mock_client.copy_object.assert_called_once_with(
            CopySource={'Bucket': 'source-bucket', 'Key': 'source-key'},
            Bucket="dest-bucket",
            Key="dest-key"
        )
        assert result == expected_response

    @pytest.mark.asyncio
    async def test_copy_object_with_metadata(self, mock_session):
        """Test object copy with new metadata."""
        mock_session_obj, mock_client = mock_session
        mock_client.copy_object.return_value = {}

        metadata = {'version': '2.0'}
        await s3.copy_object(
            source_bucket="source-bucket",
            source_key="source-key",
            dest_bucket="dest-bucket",
            dest_key="dest-key",
            metadata=metadata
        )

        call_args = mock_client.copy_object.call_args[1]
        assert call_args['Metadata'] == metadata
        assert call_args['MetadataDirective'] == 'REPLACE'


class TestUploadMultipartFile:
    """Test multipart upload functionality."""

    @pytest.mark.asyncio
    async def test_upload_multipart_file_success(self, mock_session, temp_file):
        """Test successful multipart upload."""
        mock_session_obj, mock_client = mock_session

        # Mock multipart upload responses
        mock_client.create_multipart_upload.return_value = {'UploadId': 'test-upload-id'}
        mock_client.upload_part.return_value = {'ETag': '"part-etag"'}
        mock_client.complete_multipart_upload.return_value = {'ETag': '"final-etag"'}

        # Create a file larger than part_size for testing
        with open(temp_file, 'wb') as f:
            f.write(b'x' * 1024)  # 1KB file

        result = await s3.upload_multipart_file(
            bucket="test-bucket",
            key="test-key",
            file_path=temp_file,
            part_size=512  # Small part size to trigger multipart
        )

        # Verify multipart upload was initiated
        mock_client.create_multipart_upload.assert_called_once()
        create_args = mock_client.create_multipart_upload.call_args[1]
        assert create_args['Bucket'] == 'test-bucket'
        assert create_args['Key'] == 'test-key'

        # Verify parts were uploaded
        assert mock_client.upload_part.call_count >= 1

        # Verify multipart upload was completed
        mock_client.complete_multipart_upload.assert_called_once()
        complete_args = mock_client.complete_multipart_upload.call_args[1]
        assert complete_args['UploadId'] == 'test-upload-id'

        assert result == {'ETag': '"final-etag"'}

    @pytest.mark.asyncio
    async def test_upload_multipart_file_abort_on_error(self, mock_session, temp_file):
        """Test multipart upload abort on error."""
        mock_session_obj, mock_client = mock_session

        mock_client.create_multipart_upload.return_value = {'UploadId': 'test-upload-id'}
        mock_client.upload_part.side_effect = Exception("Upload failed")
        mock_client.abort_multipart_upload.return_value = {}

        with pytest.raises(Exception, match="Upload failed"):
            await s3.upload_multipart_file(
                bucket="test-bucket",
                key="test-key",
                file_path=temp_file,
                part_size=512
            )

        # Verify abort was called
        mock_client.abort_multipart_upload.assert_called_once_with(
            Bucket="test-bucket",
            Key="test-key",
            UploadId="test-upload-id"
        )

    @pytest.mark.asyncio
    async def test_upload_multipart_file_not_found(self, mock_session):
        """Test multipart upload with non-existent file."""
        mock_session_obj, mock_client = mock_session

        with pytest.raises(FileNotFoundError, match="File not found: /nonexistent/file.txt"):
            await s3.upload_multipart_file(
                bucket="test-bucket",
                key="test-key",
                file_path="/nonexistent/file.txt"
            )


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_session_creation_error(self):
        """Test handling of session creation errors."""
        with patch('media_summarizer.utils.s3.session') as mock_session:
            mock_session.create_client.side_effect = Exception("Session error")

            # Mock file existence to bypass file check
            with patch('os.path.exists', return_value=True):
                with pytest.raises(Exception, match="Session error"):
                    await s3.upload_file("bucket", "key", "file.txt")

    @pytest.mark.asyncio
    async def test_generic_exception_handling(self, mock_session, temp_file):
        """Test handling of generic exceptions."""
        mock_session_obj, mock_client = mock_session
        mock_client.put_object.side_effect = Exception("Network error")

        with pytest.raises(Exception, match="Network error"):
            await s3.upload_file("bucket", "key", temp_file)
