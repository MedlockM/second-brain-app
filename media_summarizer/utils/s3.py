"""
S3 utilities for file storage operations.

This module provides async utility functions for interacting
with Amazon S3 in the Media Summarizer application using aiobotocore.
"""

from __future__ import annotations

import logging
import mimetypes
import os
from typing import Any, BinaryIO, Dict, List, Optional

from media_summarizer.utils.database_async import AWS_REGION
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

# Import AWS session
try:
    from aiobotocore.session import get_session

    session = get_session()
except ImportError:
    log_event(
        logger,
        logging.ERROR,
        "external_call.failed",
        "aiobotocore is not installed",
        provider="s3",
        error_code="MISSING_DEPENDENCY",
    )
    raise


def _client_kwargs() -> Dict[str, Any]:
    return {
        "region_name": AWS_REGION,
    }


def _raise_s3_error(
    *,
    operation: str,
    exc: Exception,
    bucket: Optional[str] = None,
    key: Optional[str] = None,
) -> None:
    log_event(
        logger,
        logging.ERROR,
        "external_call.failed",
        f"S3 {operation} failed",
        provider="s3",
        error_code=operation.upper(),
        bucket=bucket,
        key=key,
        error_type=type(exc).__name__,
        exc_info=exc,
    )
    raise Exception(f"Error during S3 {operation}: {str(exc)}") from exc


async def upload_file(
    bucket: str,
    key: str,
    file_path: str,
    metadata: Optional[Dict[str, str]] = None,
    content_type: Optional[str] = None,
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
        async with session.create_client("s3", **_client_kwargs()) as s3:
            with open(file_path, "rb") as f:
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
                log_event(
                    logger,
                    logging.DEBUG,
                    "external_call.succeeded",
                    "S3 upload completed",
                    provider="s3",
                    bucket=bucket,
                    key=key,
                )
                return response
    except Exception as e:
        # Do not auto-create buckets. Infra must be provisioned via Terraform.
        if "NoSuchBucket" in str(e):
            msg = (
                f"S3 bucket '{bucket}' does not exist. Provision infrastructure via Terraform before running the app. "
                f"Bucket required for key '{key}'."
            )
            raise RuntimeError(msg) from e
        _raise_s3_error(operation="upload", exc=e, bucket=bucket, key=key)


async def upload_file_object(
    bucket: str,
    key: str,
    file_obj: BinaryIO,
    content_type: Optional[str] = None,
    metadata: Optional[Dict[str, str]] = None,
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
        async with session.create_client("s3", **_client_kwargs()) as s3:
            upload_params = {
                "Bucket": bucket,
                "Key": key,
                "Body": file_obj,
                "ContentType": content_type,
            }
            if metadata:
                upload_params["Metadata"] = metadata

            response = await s3.put_object(**upload_params)
            log_event(
                logger,
                logging.DEBUG,
                "external_call.succeeded",
                "S3 upload completed from file object",
                provider="s3",
                bucket=bucket,
                key=key,
            )
            return response
    except Exception as e:
        _raise_s3_error(operation="upload_object", exc=e, bucket=bucket, key=key)


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

        async with session.create_client("s3", **_client_kwargs()) as s3:
            # Use get_object instead of download_fileobj for async compatibility
            response = await s3.get_object(Bucket=bucket, Key=key)
            with open(file_path, "wb") as f:
                content = await response["Body"].read()
                f.write(content)

        log_event(
            logger,
            logging.DEBUG,
            "external_call.succeeded",
            "S3 download completed",
            provider="s3",
            bucket=bucket,
            key=key,
        )
        return True
    except Exception as e:
        _raise_s3_error(operation="download", exc=e, bucket=bucket, key=key)


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
        async with session.create_client("s3", **_client_kwargs()) as s3:
            response = await s3.get_object(Bucket=bucket, Key=key)
            content = await response["Body"].read()
            log_event(
                logger,
                logging.DEBUG,
                "external_call.succeeded",
                "S3 in-memory download completed",
                provider="s3",
                bucket=bucket,
                key=key,
            )
            return content
    except Exception as e:
        _raise_s3_error(operation="download_memory", exc=e, bucket=bucket, key=key)


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
        async with session.create_client("s3", **_client_kwargs()) as s3:
            response = await s3.get_object(Bucket=bucket, Key=key)
            log_event(
                logger,
                logging.DEBUG,
                "external_call.succeeded",
                "S3 object fetch completed",
                provider="s3",
                bucket=bucket,
                key=key,
            )
            return response
    except Exception as e:
        _raise_s3_error(operation="get_object", exc=e, bucket=bucket, key=key)


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
        async with session.create_client("s3", **_client_kwargs()) as s3:
            response = await s3.delete_object(Bucket=bucket, Key=key)
            log_event(
                logger,
                logging.DEBUG,
                "external_call.succeeded",
                "S3 object deleted",
                provider="s3",
                bucket=bucket,
                key=key,
            )
            return response
    except Exception as e:
        _raise_s3_error(operation="delete_object", exc=e, bucket=bucket, key=key)


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
        async with session.create_client("s3", **_client_kwargs()) as s3:
            await s3.head_object(Bucket=bucket, Key=key)
            return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "404":
            return False
        raise
    except Exception as e:
        # Some tests or callers may raise generic exceptions with a response attribute
        code = None
        try:
            code = getattr(e, "response", {}).get("Error", {}).get("Code")
        except Exception:
            code = None
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


async def generate_presigned_url(
    bucket: str, key: str, expiration: int = 3600, http_method: str = "GET"
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
        async with session.create_client("s3", **_client_kwargs()) as s3:
            # Assume the client provides an async generate_presigned_url and await it
            response = await s3.generate_presigned_url(
                http_method.lower() + "_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expiration,
            )
            log_event(
                logger,
                logging.DEBUG,
                "external_call.succeeded",
                "S3 presigned URL generated",
                provider="s3",
                bucket=bucket,
                key=key,
            )
            return response
    except Exception as e:
        _raise_s3_error(
            operation="generate_presigned_url",
            exc=e,
            bucket=bucket,
            key=key,
        )


async def list_objects(
    bucket: str, prefix: Optional[str] = None, max_keys: int = 1000
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
        async with session.create_client("s3", **_client_kwargs()) as s3:
            list_params = {"Bucket": bucket, "MaxKeys": max_keys}
            if prefix:
                list_params["Prefix"] = prefix

            response = await s3.list_objects_v2(**list_params)
            return response.get("Contents", [])
    except Exception as e:
        _raise_s3_error(operation="list_objects", exc=e, bucket=bucket)


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
        async with session.create_client("s3", **_client_kwargs()) as s3:
            response = await s3.head_object(Bucket=bucket, Key=key)
            log_event(
                logger,
                logging.DEBUG,
                "external_call.succeeded",
                "S3 metadata fetch completed",
                provider="s3",
                bucket=bucket,
                key=key,
            )
            return response
    except Exception as e:
        _raise_s3_error(operation="get_metadata", exc=e, bucket=bucket, key=key)


async def copy_object(
    source_bucket: str,
    source_key: str,
    dest_bucket: str,
    dest_key: str,
    metadata: Optional[Dict[str, str]] = None,
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
        async with session.create_client("s3", **_client_kwargs()) as s3:
            copy_source = {"Bucket": source_bucket, "Key": source_key}
            copy_params = {
                "CopySource": copy_source,
                "Bucket": dest_bucket,
                "Key": dest_key,
            }

            if metadata:
                copy_params["Metadata"] = metadata
                copy_params["MetadataDirective"] = "REPLACE"

            response = await s3.copy_object(**copy_params)
            log_event(
                logger,
                logging.DEBUG,
                "external_call.succeeded",
                "S3 object copy completed",
                provider="s3",
                bucket=dest_bucket,
                key=dest_key,
            )
            return response
    except Exception as e:
        _raise_s3_error(operation="copy_object", exc=e, bucket=dest_bucket, key=dest_key)


async def upload_multipart_file(
    bucket: str,
    key: str,
    file_path: str,
    part_size: int = 8 * 1024 * 1024,  # 8MB
    metadata: Optional[Dict[str, str]] = None,
    content_type: Optional[str] = None,
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
        async with session.create_client("s3", **_client_kwargs()) as s3:
            # Initiate multipart upload
            create_params: Dict[str, Any] = {
                "Bucket": bucket,
                "Key": key,
                "ContentType": content_type,
            }
            if metadata:
                create_params["Metadata"] = metadata

            multipart = await s3.create_multipart_upload(**create_params)
            upload_id = multipart["UploadId"]

            parts = []
            part_number = 1

            try:
                with open(file_path, "rb") as f:
                    while True:
                        data = f.read(part_size)
                        if not data:
                            break

                        part_response = await s3.upload_part(
                            Bucket=bucket,
                            Key=key,
                            PartNumber=part_number,
                            UploadId=upload_id,
                            Body=data,
                        )

                        parts.append(
                            {"ETag": part_response["ETag"], "PartNumber": part_number}
                        )

                        part_number += 1

                # Complete multipart upload
                response = await s3.complete_multipart_upload(
                    Bucket=bucket,
                    Key=key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )

                log_event(
                    logger,
                    logging.DEBUG,
                    "external_call.succeeded",
                    "S3 multipart upload completed",
                    provider="s3",
                    bucket=bucket,
                    key=key,
                )
                return response

            except Exception as inner_e:
                # Abort multipart upload on error
                await s3.abort_multipart_upload(
                    Bucket=bucket, Key=key, UploadId=upload_id
                )
                raise Exception(
                    f"Error during multipart upload: {str(inner_e)}"
                ) from inner_e
    except Exception as e:
        _raise_s3_error(operation="multipart_upload", exc=e, bucket=bucket, key=key)
