"""
S3 utilities for file storage operations.

This module provides async utility functions for interacting
with Amazon S3 in the Media Summarizer application using aiobotocore.
"""
import logging
import os
from typing import Dict, Any, Optional, BinaryIO, Union, List
import mimetypes
import base64
import binascii
import asyncio

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


async def upload_file(
    bucket: str,
    key: str,
    file_path: str,
    metadata: Optional[Dict[str, str]] = None,
    content_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Upload a file to S3.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        file_path: Path to the file to upload
        metadata: Object metadata (optional)
        content_type: Content type (optional, will be guessed if not provided)

    Returns:
        Dict containing the response from S3

    Raises:
        FileNotFoundError: If the file does not exist
        Exception: If there's an error uploading the file
    """
    # Check if file exists
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Guess content type if not provided
    if not content_type:
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = "application/octet-stream"

    try:
        # Fallback to boto3 for LocalStack to avoid known checksum issues in aiobotocore with S3 v3 provider
        if AWS_ENDPOINT_URL:
            import boto3  # Local import to avoid heavy dependency at module import
            with open(file_path, 'rb') as f:
                file_bytes = f.read()

            def _put_object_sync():
                s3_client = boto3.client(
                    's3',
                    region_name=AWS_REGION,
                    endpoint_url=AWS_ENDPOINT_URL,
                    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID', 'test'),
                    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY', 'test'),
                )
                return s3_client.put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=file_bytes,
                    ContentType=content_type,
                    **({"Metadata": metadata} if metadata else {})
                )

            response = await asyncio.to_thread(_put_object_sync)
            logger.info(f"File uploaded to S3 (boto3 fallback): s3://{bucket}/{key}")
            return response

        # Default path: use aiobotocore
        async with session.create_client(
            's3',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as s3:
            with open(file_path, 'rb') as f:
                # Read into memory to provide as raw bytes (workaround for LocalStack S3 v3 checksum handling)
                file_bytes = f.read()

                upload_params = {
                    "Bucket": bucket,
                    "Key": key,
                    "Body": file_bytes,
                    "ContentType": content_type,
                }
                if metadata:
                    upload_params["Metadata"] = metadata

                response = await s3.put_object(**upload_params)
                logger.info(f"File uploaded to S3: s3://{bucket}/{key}")
                return response
    except Exception as e:
        logger.error(f"Error uploading file to S3: {str(e)}")
        # Do not auto-create buckets. Infra must be provisioned via Terraform.
        if "NoSuchBucket" in str(e):
            msg = (
                f"S3 bucket '{bucket}' does not exist. Provision infrastructure via Terraform before running the app. "
                f"Bucket required for key '{key}'."
            )
            raise RuntimeError(msg) from e
        raise Exception(f"Error uploading file to S3: {str(e)}") from e


async def upload_file_object(
    bucket: str,
    key: str,
    file_obj: BinaryIO,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Upload a file-like object to S3.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        file_obj: File-like object to upload
        content_type: Content type (optional)
        metadata: Object metadata (optional)

    Returns:
        Dict containing the response from S3

    Raises:
        Exception: If there's an error uploading the file
    """
    if not content_type:
        content_type = "application/octet-stream"

    try:
        async with session.create_client(
            's3',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as s3:
            upload_params = {
                "Bucket": bucket,
                "Key": key,
                "Body": file_obj,
                "ContentType": content_type
            }
            if metadata:
                upload_params["Metadata"] = metadata

            response = await s3.put_object(**upload_params)
            logger.info(f"File object uploaded to S3: s3://{bucket}/{key}")
            return response
    except Exception as e:
        logger.error(f"Error uploading file object to S3: {str(e)}")
        raise Exception(f"Error uploading file object to S3: {str(e)}") from e


async def download_file(bucket: str, key: str, file_path: str) -> bool:
    """
    Download a file from S3.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        file_path: Path where to save the downloaded file

    Returns:
        True if successful

    Raises:
        Exception: If there's an error downloading the file
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        async with session.create_client(
            's3',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as s3:
            # Use get_object instead of download_fileobj for async compatibility
            response = await s3.get_object(Bucket=bucket, Key=key)
            with open(file_path, 'wb') as f:
                content = await response['Body'].read()
                f.write(content)

        logger.info(f"File downloaded from S3: s3://{bucket}/{key} -> {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error downloading file from S3: {str(e)}")
        raise Exception(f"Error downloading file from S3: {str(e)}") from e


async def download_file_to_memory(bucket: str, key: str) -> bytes:
    """
    Download a file from S3 to memory.

    Args:
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        File content as bytes

    Raises:
        Exception: If there's an error downloading the file
    """
    try:
        async with session.create_client(
            's3',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as s3:
            response = await s3.get_object(Bucket=bucket, Key=key)
            content = await response['Body'].read()
            logger.info(f"File downloaded to memory from S3: s3://{bucket}/{key}")
            return content
    except Exception as e:
        logger.error(f"Error downloading file to memory from S3: {str(e)}")
        raise Exception(f"Error downloading file to memory from S3: {str(e)}") from e


async def get_object(bucket: str, key: str) -> Dict[str, Any]:
    """
    Get an object from S3.

    Args:
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        Dict containing the object response

    Raises:
        Exception: If there's an error getting the object
    """
    try:
        async with session.create_client(
            's3',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as s3:
            response = await s3.get_object(Bucket=bucket, Key=key)
            logger.info(f"Object retrieved from S3: s3://{bucket}/{key}")
            return response
    except Exception as e:
        logger.error(f"Error getting object from S3: {str(e)}")
        raise Exception(f"Error getting object from S3: {str(e)}") from e


async def delete_object(bucket: str, key: str) -> Dict[str, Any]:
    """
    Delete an object from S3.

    Args:
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        Dict containing the response from S3

    Raises:
        Exception: If there's an error deleting the object
    """
    try:
        async with session.create_client(
            's3',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as s3:
            response = await s3.delete_object(Bucket=bucket, Key=key)
            logger.info(f"Object deleted from S3: s3://{bucket}/{key}")
            return response
    except Exception as e:
        logger.error(f"Error deleting object from S3: {str(e)}")
        raise Exception(f"Error deleting object from S3: {str(e)}") from e


async def object_exists(bucket: str, key: str) -> bool:
    """
    Check if an object exists in S3.

    Args:
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        True if the object exists, False otherwise
    """
    from botocore.exceptions import ClientError
    try:
        async with session.create_client(
            's3',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as s3:
            await s3.head_object(Bucket=bucket, Key=key)
            return True
    except ClientError as e:
        if e.response.get('Error', {}).get('Code') == '404':
            return False
        raise
    except Exception as e:
        # Some tests or callers may raise generic exceptions with a response attribute
        code = None
        try:
            code = getattr(e, 'response', {}).get('Error', {}).get('Code')
        except Exception:
            code = None
        if code in ('404', 'NoSuchKey', 'NotFound'):
            return False
        raise


async def generate_presigned_url(
    bucket: str,
    key: str,
    expiration: int = 3600,
    http_method: str = 'GET'
) -> str:
    """
    Generate a presigned URL for an S3 object.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        expiration: URL expiration time in seconds (default: 1 hour)
        http_method: HTTP method (GET, PUT, etc.)

    Returns:
        Presigned URL

    Raises:
        Exception: If there's an error generating the URL
    """
    try:
        async with session.create_client(
            's3',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as s3:
            # Note: generate_presigned_url is synchronous, don't await it
            response = s3.generate_presigned_url(
                http_method.lower() + '_object',
                Params={'Bucket': bucket, 'Key': key},
                ExpiresIn=expiration
            )
            logger.info(f"Presigned URL generated for s3://{bucket}/{key}")
            return response
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        raise Exception(f"Error generating presigned URL: {str(e)}") from e


async def list_objects(
    bucket: str,
    prefix: Optional[str] = None,
    max_keys: int = 1000
) -> List[Dict[str, Any]]:
    """
    List objects in an S3 bucket.

    Args:
        bucket: S3 bucket name
        prefix: Object key prefix to filter by (optional)
        max_keys: Maximum number of keys to return

    Returns:
        List of object metadata

    Raises:
        Exception: If there's an error listing objects
    """
    try:
        async with session.create_client(
            's3',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as s3:
            list_params = {
                'Bucket': bucket,
                'MaxKeys': max_keys
            }
            if prefix:
                list_params['Prefix'] = prefix

            response = await s3.list_objects_v2(**list_params)
            objects = response.get('Contents', [])
            logger.info(f"Listed {len(objects)} objects from s3://{bucket}")
            return objects
    except Exception as e:
        logger.error(f"Error listing objects from S3: {str(e)}")
        raise Exception(f"Error listing objects from S3: {str(e)}") from e


async def get_object_metadata(bucket: str, key: str) -> Dict[str, Any]:
    """
    Get metadata for an S3 object.

    Args:
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        Dict containing object metadata

    Raises:
        Exception: If there's an error getting metadata
    """
    try:
        async with session.create_client(
            's3',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as s3:
            response = await s3.head_object(Bucket=bucket, Key=key)
            logger.info(f"Retrieved metadata for s3://{bucket}/{key}")
            return response
    except Exception as e:
        logger.error(f"Error getting object metadata: {str(e)}")
        raise Exception(f"Error getting object metadata: {str(e)}") from e


async def copy_object(
    source_bucket: str,
    source_key: str,
    dest_bucket: str,
    dest_key: str,
    metadata: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Copy an object from one S3 location to another.

    Args:
        source_bucket: Source bucket name
        source_key: Source object key
        dest_bucket: Destination bucket name
        dest_key: Destination object key
        metadata: New metadata for the copied object (optional)

    Returns:
        Dict containing the response from S3

    Raises:
        Exception: If there's an error copying the object
    """
    try:
        async with session.create_client(
            's3',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as s3:
            copy_source = {'Bucket': source_bucket, 'Key': source_key}
            copy_params = {
                'CopySource': copy_source,
                'Bucket': dest_bucket,
                'Key': dest_key
            }

            if metadata:
                copy_params['Metadata'] = metadata
                copy_params['MetadataDirective'] = 'REPLACE'

            response = await s3.copy_object(**copy_params)
            logger.info(f"Object copied from s3://{source_bucket}/{source_key} to s3://{dest_bucket}/{dest_key}")
            return response
    except Exception as e:
        logger.error(f"Error copying object: {str(e)}")
        raise Exception(f"Error copying object: {str(e)}") from e


async def upload_multipart_file(
    bucket: str,
    key: str,
    file_path: str,
    part_size: int = 8 * 1024 * 1024,  # 8MB
    metadata: Optional[Dict[str, str]] = None,
    content_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Upload a large file to S3 using multipart upload.

    Args:
        bucket: S3 bucket name
        key: S3 object key
        file_path: Path to the file to upload
        part_size: Size of each part in bytes (default: 8MB)
        metadata: Object metadata (optional)
        content_type: Content type (optional)

    Returns:
        Dict containing the response from S3

    Raises:
        Exception: If there's an error uploading the file
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if not content_type:
        content_type, _ = mimetypes.guess_type(file_path)
        if not content_type:
            content_type = "application/octet-stream"

    try:
        async with session.create_client(
            's3',
            region_name=AWS_REGION,
            endpoint_url=AWS_ENDPOINT_URL
        ) as s3:
            # Initiate multipart upload
            create_params: Dict[str, Any] = {
                'Bucket': bucket,
                'Key': key,
                'ContentType': content_type
            }
            if metadata:
                create_params['Metadata'] = metadata

            multipart = await s3.create_multipart_upload(**create_params)
            upload_id = multipart['UploadId']

            parts = []
            part_number = 1

            try:
                with open(file_path, 'rb') as f:
                    while True:
                        data = f.read(part_size)
                        if not data:
                            break

                        part_response = await s3.upload_part(
                            Bucket=bucket,
                            Key=key,
                            PartNumber=part_number,
                            UploadId=upload_id,
                            Body=data
                        )

                        parts.append({
                            'ETag': part_response['ETag'],
                            'PartNumber': part_number
                        })

                        part_number += 1

                # Complete multipart upload
                response = await s3.complete_multipart_upload(
                    Bucket=bucket,
                    Key=key,
                    UploadId=upload_id,
                    MultipartUpload={'Parts': parts}
                )

                logger.info(f"Multipart file uploaded to S3: s3://{bucket}/{key} ({len(parts)} parts)")
                return response

            except Exception as inner_e:
                # Abort multipart upload on error
                await s3.abort_multipart_upload(
                    Bucket=bucket,
                    Key=key,
                    UploadId=upload_id
                )
                raise Exception(f"Error during multipart upload: {str(inner_e)}") from inner_e
    except Exception as e:
        logger.error(f"Error uploading multipart file to S3: {str(e)}")
        raise Exception(f"Error uploading multipart file to S3: {str(e)}") from e
