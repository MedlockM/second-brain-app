"""
Storage adapter for Media Summarizer.

This adapter provides an interface for interacting with storage services (S3).
It handles file uploads, downloads, and URL generation.
"""
import logging
import os
from typing import Dict, Any, Optional, BinaryIO, Union
import mimetypes

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


class StorageAdapter:
    """
    Adapter for interacting with storage services (S3).
    """
    
    def __init__(self, region_name: Optional[str] = None, endpoint_url: Optional[str] = None):
        """
        Initialize the storage adapter.
        
        Args:
            region_name: AWS region name (optional, defaults to AWS_REGION)
            endpoint_url: AWS endpoint URL (optional, defaults to AWS_ENDPOINT_URL)
        """
        self.region_name = region_name or AWS_REGION
        self.endpoint_url = endpoint_url or AWS_ENDPOINT_URL
        self.session = get_session()
    
    async def upload_file(
        self,
        bucket: str,
        key: str,
        file_path: str,
        metadata: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
        s3_client = None
    ) -> Dict[str, Any]:
        """
        Upload a file to S3.
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            file_path: Path to the file to upload
            metadata: Object metadata (optional)
            content_type: Content type (optional, will be guessed if not provided)
            s3_client: S3 client for testing (optional)
            
        Returns:
            Dict containing the response from S3
            
        Raises:
            FileNotFoundError: If the file does not exist
            ClientError: If there's an error uploading the file
        """
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Guess content type if not provided
        if not content_type:
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                content_type = "application/octet-stream"
        
        # Prepare upload parameters
        upload_params = {
            "Bucket": bucket,
            "Key": key,
            "Filename": file_path,
            "ContentType": content_type
        }
        
        if metadata:
            upload_params["Metadata"] = metadata
        
        # Upload the file
        if s3_client is None:
            async with self.session.create_client(
                "s3", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as s3_client:
                response = await s3_client.upload_file(**upload_params)
                return response or {}
        else:
            # Use provided client (for testing)
            response = await s3_client.upload_file(**upload_params)
            return response or {}
    
    async def upload_fileobj(
        self,
        bucket: str,
        key: str,
        fileobj: BinaryIO,
        metadata: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None,
        s3_client = None
    ) -> Dict[str, Any]:
        """
        Upload a file-like object to S3.
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            fileobj: File-like object to upload
            metadata: Object metadata (optional)
            content_type: Content type (optional)
            s3_client: S3 client for testing (optional)
            
        Returns:
            Dict containing the response from S3
            
        Raises:
            ClientError: If there's an error uploading the file
        """
        # Prepare upload parameters
        upload_params = {
            "Bucket": bucket,
            "Key": key,
            "Body": fileobj
        }
        
        if content_type:
            upload_params["ContentType"] = content_type
        
        if metadata:
            upload_params["Metadata"] = metadata
        
        # Upload the file
        if s3_client is None:
            async with self.session.create_client(
                "s3", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as s3_client:
                response = await s3_client.put_object(**upload_params)
                return response
        else:
            # Use provided client (for testing)
            response = await s3_client.put_object(**upload_params)
            return response
    
    async def download_file(
        self,
        bucket: str,
        key: str,
        file_path: str,
        s3_client = None
    ) -> Dict[str, Any]:
        """
        Download a file from S3.
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            file_path: Path to save the downloaded file
            s3_client: S3 client for testing (optional)
            
        Returns:
            Dict containing the response from S3
            
        Raises:
            ClientError: If there's an error downloading the file
        """
        # Prepare download parameters
        download_params = {
            "Bucket": bucket,
            "Key": key,
            "Filename": file_path
        }
        
        # Download the file
        if s3_client is None:
            async with self.session.create_client(
                "s3", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as s3_client:
                response = await s3_client.download_file(**download_params)
                return response or {}
        else:
            # Use provided client (for testing)
            response = await s3_client.download_file(**download_params)
            return response or {}
    
    async def get_object(
        self,
        bucket: str,
        key: str,
        s3_client = None
    ) -> Dict[str, Any]:
        """
        Get an object from S3.
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            s3_client: S3 client for testing (optional)
            
        Returns:
            Dict containing the object data and metadata
            
        Raises:
            ClientError: If there's an error getting the object
        """
        # Prepare get parameters
        get_params = {
            "Bucket": bucket,
            "Key": key
        }
        
        # Get the object
        if s3_client is None:
            async with self.session.create_client(
                "s3", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as s3_client:
                response = await s3_client.get_object(**get_params)
                return response
        else:
            # Use provided client (for testing)
            response = await s3_client.get_object(**get_params)
            return response
    
    async def delete_object(
        self,
        bucket: str,
        key: str,
        s3_client = None
    ) -> Dict[str, Any]:
        """
        Delete an object from S3.
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            s3_client: S3 client for testing (optional)
            
        Returns:
            Dict containing the response from S3
            
        Raises:
            ClientError: If there's an error deleting the object
        """
        # Prepare delete parameters
        delete_params = {
            "Bucket": bucket,
            "Key": key
        }
        
        # Delete the object
        if s3_client is None:
            async with self.session.create_client(
                "s3", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as s3_client:
                response = await s3_client.delete_object(**delete_params)
                return response
        else:
            # Use provided client (for testing)
            response = await s3_client.delete_object(**delete_params)
            return response
    
    async def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expiration: int = 3600,
        s3_client = None
    ) -> str:
        """
        Generate a presigned URL for an S3 object.
        
        Args:
            bucket: S3 bucket name
            key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)
            s3_client: S3 client for testing (optional)
            
        Returns:
            Presigned URL
            
        Raises:
            ClientError: If there's an error generating the URL
        """
        # Prepare URL parameters
        url_params = {
            "Bucket": bucket,
            "Key": key,
            "ExpiresIn": expiration
        }
        
        # Generate the URL
        if s3_client is None:
            async with self.session.create_client(
                "s3", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as s3_client:
                url = await s3_client.generate_presigned_url(
                    "get_object", Params=url_params
                )
                return url
        else:
            # Use provided client (for testing)
            url = await s3_client.generate_presigned_url(
                "get_object", Params=url_params
            )
            return url
    
    async def list_objects(
        self,
        bucket: str,
        prefix: Optional[str] = None,
        max_keys: int = 1000,
        s3_client = None
    ) -> Dict[str, Any]:
        """
        List objects in an S3 bucket.
        
        Args:
            bucket: S3 bucket name
            prefix: Object key prefix (optional)
            max_keys: Maximum number of keys to return
            s3_client: S3 client for testing (optional)
            
        Returns:
            Dict containing the list of objects
            
        Raises:
            ClientError: If there's an error listing objects
        """
        # Prepare list parameters
        list_params = {
            "Bucket": bucket,
            "MaxKeys": max_keys
        }
        
        if prefix:
            list_params["Prefix"] = prefix
        
        # List objects
        if s3_client is None:
            async with self.session.create_client(
                "s3", region_name=self.region_name, endpoint_url=self.endpoint_url
            ) as s3_client:
                response = await s3_client.list_objects_v2(**list_params)
                return response
        else:
            # Use provided client (for testing)
            response = await s3_client.list_objects_v2(**list_params)
            return response