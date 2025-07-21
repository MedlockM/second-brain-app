"""
Unit tests for the storage adapter.
"""
import os
import io
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from botocore.exceptions import ClientError

# Set AWS credentials for testing
os.environ["AWS_ACCESS_KEY_ID"] = "test"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_ENDPOINT_URL"] = "http://localhost:4566"

from media_summarizer.adapters.storage.storage_adapter import StorageAdapter


@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing."""
    mock_client = AsyncMock()
    mock_client.upload_file = AsyncMock(return_value={})
    mock_client.put_object = AsyncMock(return_value={"ETag": "test-etag"})
    mock_client.download_file = AsyncMock(return_value={})
    mock_client.get_object = AsyncMock(return_value={
        "Body": AsyncMock(),
        "ContentType": "application/octet-stream",
        "Metadata": {"key": "value"}
    })
    mock_client.delete_object = AsyncMock(return_value={})
    mock_client.generate_presigned_url = AsyncMock(return_value="https://example.com/presigned-url")
    mock_client.list_objects_v2 = AsyncMock(return_value={
        "Contents": [
            {"Key": "test-key-1", "Size": 1024},
            {"Key": "test-key-2", "Size": 2048}
        ]
    })
    return mock_client


@pytest.fixture
def storage_adapter():
    """Create a StorageAdapter instance for testing."""
    return StorageAdapter(region_name="us-east-1", endpoint_url="http://localhost:4566")


@pytest.fixture
def temp_file():
    """Create a temporary file for testing."""
    file_path = "/tmp/test_file.txt"
    with open(file_path, "w") as f:
        f.write("Test content")
    
    yield file_path
    
    # Clean up
    if os.path.exists(file_path):
        os.remove(file_path)


class TestStorageAdapter:
    """Test cases for the StorageAdapter class."""
    
    @pytest.mark.asyncio
    async def test_init(self):
        """Test StorageAdapter initialization."""
        # Test with default values
        adapter = StorageAdapter()
        assert adapter.region_name == "us-east-1"
        assert adapter.endpoint_url == "http://localhost:4566"
        
        # Test with custom values
        adapter = StorageAdapter(region_name="eu-west-1", endpoint_url="http://custom-endpoint")
        assert adapter.region_name == "eu-west-1"
        assert adapter.endpoint_url == "http://custom-endpoint"
    
    @pytest.mark.asyncio
    async def test_upload_file(self, storage_adapter, mock_s3_client, temp_file):
        """Test uploading a file."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        
        # Execute
        result = await storage_adapter.upload_file(
            bucket, key, temp_file, s3_client=mock_s3_client
        )
        
        # Verify
        mock_s3_client.upload_file.assert_called_once()
        call_args = mock_s3_client.upload_file.call_args[1]
        
        assert call_args["Bucket"] == bucket
        assert call_args["Key"] == key
        assert call_args["Filename"] == temp_file
        assert call_args["ContentType"] == "text/plain"
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_upload_file_with_metadata(self, storage_adapter, mock_s3_client, temp_file):
        """Test uploading a file with metadata."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        metadata = {"key1": "value1", "key2": "value2"}
        
        # Execute
        result = await storage_adapter.upload_file(
            bucket, key, temp_file, metadata=metadata, s3_client=mock_s3_client
        )
        
        # Verify
        mock_s3_client.upload_file.assert_called_once()
        call_args = mock_s3_client.upload_file.call_args[1]
        
        assert call_args["Bucket"] == bucket
        assert call_args["Key"] == key
        assert call_args["Filename"] == temp_file
        assert call_args["Metadata"] == metadata
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_upload_file_with_content_type(self, storage_adapter, mock_s3_client, temp_file):
        """Test uploading a file with custom content type."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        content_type = "application/custom"
        
        # Execute
        result = await storage_adapter.upload_file(
            bucket, key, temp_file, content_type=content_type, s3_client=mock_s3_client
        )
        
        # Verify
        mock_s3_client.upload_file.assert_called_once()
        call_args = mock_s3_client.upload_file.call_args[1]
        
        assert call_args["Bucket"] == bucket
        assert call_args["Key"] == key
        assert call_args["Filename"] == temp_file
        assert call_args["ContentType"] == content_type
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_upload_file_not_found(self, storage_adapter, mock_s3_client):
        """Test uploading a non-existent file."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        file_path = "/tmp/non_existent_file.txt"
        
        # Execute and verify
        with pytest.raises(FileNotFoundError) as excinfo:
            await storage_adapter.upload_file(bucket, key, file_path, s3_client=mock_s3_client)
        
        assert "File not found" in str(excinfo.value)
        mock_s3_client.upload_file.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_upload_file_with_client_error(self, storage_adapter, mock_s3_client, temp_file):
        """Test handling of ClientError during file upload."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        
        # Configure mock to raise ClientError
        error_response = {"Error": {"Code": "NoSuchBucket", "Message": "The specified bucket does not exist."}}
        mock_s3_client.upload_file.side_effect = ClientError(error_response, "upload_file")
        
        # Execute and verify
        with pytest.raises(ClientError) as excinfo:
            await storage_adapter.upload_file(bucket, key, temp_file, s3_client=mock_s3_client)
        
        assert "NoSuchBucket" in str(excinfo.value)
        assert "The specified bucket does not exist." in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_upload_fileobj(self, storage_adapter, mock_s3_client):
        """Test uploading a file-like object."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        fileobj = io.BytesIO(b"Test content")
        
        # Execute
        result = await storage_adapter.upload_fileobj(
            bucket, key, fileobj, s3_client=mock_s3_client
        )
        
        # Verify
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args[1]
        
        assert call_args["Bucket"] == bucket
        assert call_args["Key"] == key
        assert call_args["Body"] == fileobj
        assert result == {"ETag": "test-etag"}
    
    @pytest.mark.asyncio
    async def test_upload_fileobj_with_metadata(self, storage_adapter, mock_s3_client):
        """Test uploading a file-like object with metadata."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        fileobj = io.BytesIO(b"Test content")
        metadata = {"key1": "value1", "key2": "value2"}
        
        # Execute
        result = await storage_adapter.upload_fileobj(
            bucket, key, fileobj, metadata=metadata, s3_client=mock_s3_client
        )
        
        # Verify
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args[1]
        
        assert call_args["Bucket"] == bucket
        assert call_args["Key"] == key
        assert call_args["Body"] == fileobj
        assert call_args["Metadata"] == metadata
        assert result == {"ETag": "test-etag"}
    
    @pytest.mark.asyncio
    async def test_upload_fileobj_with_content_type(self, storage_adapter, mock_s3_client):
        """Test uploading a file-like object with custom content type."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        fileobj = io.BytesIO(b"Test content")
        content_type = "application/custom"
        
        # Execute
        result = await storage_adapter.upload_fileobj(
            bucket, key, fileobj, content_type=content_type, s3_client=mock_s3_client
        )
        
        # Verify
        mock_s3_client.put_object.assert_called_once()
        call_args = mock_s3_client.put_object.call_args[1]
        
        assert call_args["Bucket"] == bucket
        assert call_args["Key"] == key
        assert call_args["Body"] == fileobj
        assert call_args["ContentType"] == content_type
        assert result == {"ETag": "test-etag"}
    
    @pytest.mark.asyncio
    async def test_upload_fileobj_with_client_error(self, storage_adapter, mock_s3_client):
        """Test handling of ClientError during file-like object upload."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        fileobj = io.BytesIO(b"Test content")
        
        # Configure mock to raise ClientError
        error_response = {"Error": {"Code": "NoSuchBucket", "Message": "The specified bucket does not exist."}}
        mock_s3_client.put_object.side_effect = ClientError(error_response, "put_object")
        
        # Execute and verify
        with pytest.raises(ClientError) as excinfo:
            await storage_adapter.upload_fileobj(bucket, key, fileobj, s3_client=mock_s3_client)
        
        assert "NoSuchBucket" in str(excinfo.value)
        assert "The specified bucket does not exist." in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_download_file(self, storage_adapter, mock_s3_client, temp_file):
        """Test downloading a file."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        
        # Execute
        result = await storage_adapter.download_file(
            bucket, key, temp_file, s3_client=mock_s3_client
        )
        
        # Verify
        mock_s3_client.download_file.assert_called_once()
        call_args = mock_s3_client.download_file.call_args[1]
        
        assert call_args["Bucket"] == bucket
        assert call_args["Key"] == key
        assert call_args["Filename"] == temp_file
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_download_file_with_client_error(self, storage_adapter, mock_s3_client, temp_file):
        """Test handling of ClientError during file download."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        
        # Configure mock to raise ClientError
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}}
        mock_s3_client.download_file.side_effect = ClientError(error_response, "download_file")
        
        # Execute and verify
        with pytest.raises(ClientError) as excinfo:
            await storage_adapter.download_file(bucket, key, temp_file, s3_client=mock_s3_client)
        
        assert "NoSuchKey" in str(excinfo.value)
        assert "The specified key does not exist." in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_get_object(self, storage_adapter, mock_s3_client):
        """Test getting an object."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        
        # Execute
        result = await storage_adapter.get_object(
            bucket, key, s3_client=mock_s3_client
        )
        
        # Verify
        mock_s3_client.get_object.assert_called_once()
        call_args = mock_s3_client.get_object.call_args[1]
        
        assert call_args["Bucket"] == bucket
        assert call_args["Key"] == key
        assert "Body" in result
        assert result["ContentType"] == "application/octet-stream"
        assert result["Metadata"] == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_get_object_with_client_error(self, storage_adapter, mock_s3_client):
        """Test handling of ClientError during object retrieval."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        
        # Configure mock to raise ClientError
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, "get_object")
        
        # Execute and verify
        with pytest.raises(ClientError) as excinfo:
            await storage_adapter.get_object(bucket, key, s3_client=mock_s3_client)
        
        assert "NoSuchKey" in str(excinfo.value)
        assert "The specified key does not exist." in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_delete_object(self, storage_adapter, mock_s3_client):
        """Test deleting an object."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        
        # Execute
        result = await storage_adapter.delete_object(
            bucket, key, s3_client=mock_s3_client
        )
        
        # Verify
        mock_s3_client.delete_object.assert_called_once()
        call_args = mock_s3_client.delete_object.call_args[1]
        
        assert call_args["Bucket"] == bucket
        assert call_args["Key"] == key
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_delete_object_with_client_error(self, storage_adapter, mock_s3_client):
        """Test handling of ClientError during object deletion."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        
        # Configure mock to raise ClientError
        error_response = {"Error": {"Code": "NoSuchBucket", "Message": "The specified bucket does not exist."}}
        mock_s3_client.delete_object.side_effect = ClientError(error_response, "delete_object")
        
        # Execute and verify
        with pytest.raises(ClientError) as excinfo:
            await storage_adapter.delete_object(bucket, key, s3_client=mock_s3_client)
        
        assert "NoSuchBucket" in str(excinfo.value)
        assert "The specified bucket does not exist." in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_generate_presigned_url(self, storage_adapter, mock_s3_client):
        """Test generating a presigned URL."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        expiration = 7200  # 2 hours
        
        # Execute
        result = await storage_adapter.generate_presigned_url(
            bucket, key, expiration=expiration, s3_client=mock_s3_client
        )
        
        # Verify
        mock_s3_client.generate_presigned_url.assert_called_once()
        call_args = mock_s3_client.generate_presigned_url.call_args
        
        assert call_args[0][0] == "get_object"
        assert call_args[1]["Params"]["Bucket"] == bucket
        assert call_args[1]["Params"]["Key"] == key
        assert call_args[1]["Params"]["ExpiresIn"] == expiration
        assert result == "https://example.com/presigned-url"
    
    @pytest.mark.asyncio
    async def test_generate_presigned_url_with_client_error(self, storage_adapter, mock_s3_client):
        """Test handling of ClientError during presigned URL generation."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        
        # Configure mock to raise ClientError
        error_response = {"Error": {"Code": "InvalidRequest", "Message": "Invalid request."}}
        mock_s3_client.generate_presigned_url.side_effect = ClientError(error_response, "generate_presigned_url")
        
        # Execute and verify
        with pytest.raises(ClientError) as excinfo:
            await storage_adapter.generate_presigned_url(bucket, key, s3_client=mock_s3_client)
        
        assert "InvalidRequest" in str(excinfo.value)
        assert "Invalid request." in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_list_objects(self, storage_adapter, mock_s3_client):
        """Test listing objects."""
        # Setup
        bucket = "test-bucket"
        
        # Execute
        result = await storage_adapter.list_objects(
            bucket, s3_client=mock_s3_client
        )
        
        # Verify
        mock_s3_client.list_objects_v2.assert_called_once()
        call_args = mock_s3_client.list_objects_v2.call_args[1]
        
        assert call_args["Bucket"] == bucket
        assert call_args["MaxKeys"] == 1000
        assert "Prefix" not in call_args
        assert "Contents" in result
        assert len(result["Contents"]) == 2
        assert result["Contents"][0]["Key"] == "test-key-1"
        assert result["Contents"][1]["Key"] == "test-key-2"
    
    @pytest.mark.asyncio
    async def test_list_objects_with_prefix(self, storage_adapter, mock_s3_client):
        """Test listing objects with a prefix."""
        # Setup
        bucket = "test-bucket"
        prefix = "test-prefix/"
        
        # Execute
        result = await storage_adapter.list_objects(
            bucket, prefix=prefix, s3_client=mock_s3_client
        )
        
        # Verify
        mock_s3_client.list_objects_v2.assert_called_once()
        call_args = mock_s3_client.list_objects_v2.call_args[1]
        
        assert call_args["Bucket"] == bucket
        assert call_args["Prefix"] == prefix
        assert "Contents" in result
    
    @pytest.mark.asyncio
    async def test_list_objects_with_max_keys(self, storage_adapter, mock_s3_client):
        """Test listing objects with max_keys."""
        # Setup
        bucket = "test-bucket"
        max_keys = 50
        
        # Execute
        result = await storage_adapter.list_objects(
            bucket, max_keys=max_keys, s3_client=mock_s3_client
        )
        
        # Verify
        mock_s3_client.list_objects_v2.assert_called_once()
        call_args = mock_s3_client.list_objects_v2.call_args[1]
        
        assert call_args["Bucket"] == bucket
        assert call_args["MaxKeys"] == max_keys
        assert "Contents" in result
    
    @pytest.mark.asyncio
    async def test_list_objects_with_client_error(self, storage_adapter, mock_s3_client):
        """Test handling of ClientError during object listing."""
        # Setup
        bucket = "test-bucket"
        
        # Configure mock to raise ClientError
        error_response = {"Error": {"Code": "NoSuchBucket", "Message": "The specified bucket does not exist."}}
        mock_s3_client.list_objects_v2.side_effect = ClientError(error_response, "list_objects_v2")
        
        # Execute and verify
        with pytest.raises(ClientError) as excinfo:
            await storage_adapter.list_objects(bucket, s3_client=mock_s3_client)
        
        assert "NoSuchBucket" in str(excinfo.value)
        assert "The specified bucket does not exist." in str(excinfo.value)
    
    @pytest.mark.asyncio
    async def test_upload_file_with_session_creation(self, storage_adapter, temp_file):
        """Test uploading a file with session creation."""
        # Setup
        bucket = "test-bucket"
        key = "test-key.txt"
        
        # Execute - Test with session creation
        with patch("media_summarizer.adapters.storage.storage_adapter.session") as mock_session:
            mock_client = AsyncMock()
            mock_client.upload_file = AsyncMock(return_value={})
            mock_session.create_client.return_value.__aenter__.return_value = mock_client
            
            # Execute
            result = await storage_adapter.upload_file(bucket, key, temp_file)
            
            # Verify
            mock_client.upload_file.assert_called_once()
            call_args = mock_client.upload_file.call_args[1]
            
            assert call_args["Bucket"] == bucket
            assert call_args["Key"] == key
            assert call_args["Filename"] == temp_file
            assert call_args["ContentType"] == "text/plain"
            assert result == {}