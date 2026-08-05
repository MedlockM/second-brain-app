"""
Bug Reports API endpoints.

Provides intake for user-submitted bug reports with optional file attachment
via presigned S3 upload. Reports are persisted to DynamoDB and routed to a
configurable triage channel (Discord webhook V1).

Architecture decisions (task-128):
- Storage: dedicated S3 bucket (prefix-free) with 90-day lifecycle.
- Upload: presigned PUT URL — binary never transits through this API.
- File limits: 50 MB, 1 attachment max per report.
- MIME validation: whitelist-only server-side check on S3 object after upload.
- Routing: Discord webhook (env var BUG_REPORT_ROUTING_WEBHOOK).
- Auth: required (401). Rate limit: 5 reports/hour/user (429).
- Antivirus: deferred to follow-up (conscious tech debt, see PR description).
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from media_summarizer.api.dependencies.auth import get_current_user
from media_summarizer.core.models.auth import AuthUser
from media_summarizer.core.services.bug_report_service import (
    BugReportService,
)
from media_summarizer.utils import s3 as s3_utils

router = APIRouter()
logger = logging.getLogger(__name__)

# Configuration
BUG_REPORT_BUCKET = os.environ.get("BUG_REPORT_BUCKET", "media-summarizer-bug-reports")
BUG_REPORT_MAX_FILE_SIZE = int(os.environ.get("BUG_REPORT_MAX_FILE_SIZE", str(50 * 1024 * 1024)))  # 50 MB
BUG_REPORT_RATE_LIMIT = int(os.environ.get("BUG_REPORT_RATE_LIMIT_PER_HOUR", "5"))

# Allowed MIME types and extensions
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".mp4", ".mov", ".pdf", ".zip"}
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/heif",
    "video/mp4",
    "video/quicktime",
    "application/pdf",
    "application/zip",
    "application/x-zip-compressed",
}

# In-memory rate limiter (per-process). For production multi-instance use Redis.
# Sufficient for V1 soft-launch single-instance.
_rate_limit_store: dict[str, list[float]] = {}


def _check_rate_limit(user_id: str) -> None:
    """Enforce per-user rate limit of BUG_REPORT_RATE_LIMIT reports per hour."""
    now = time.time()
    window = 3600  # 1 hour
    entries = _rate_limit_store.get(user_id, [])
    # Prune old entries
    entries = [ts for ts in entries if now - ts < window]
    if len(entries) >= BUG_REPORT_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {BUG_REPORT_RATE_LIMIT} bug reports per hour.",
        )
    entries.append(now)
    _rate_limit_store[user_id] = entries


# --- Request/Response Models ---


class RequestUploadUrlRequest(BaseModel):
    """Request body to get a presigned upload URL for an attachment."""
    filename: str = Field(..., description="Original filename including extension")
    content_type: str = Field(..., description="MIME type of the file")
    file_size: int = Field(..., description="File size in bytes", gt=0)


class RequestUploadUrlResponse(BaseModel):
    """Response with presigned upload URL and the S3 key to reference later."""
    upload_url: str = Field(..., description="Presigned S3 PUT URL")
    attachment_key: str = Field(..., description="S3 key to reference in the bug report submission")
    expires_in: int = Field(default=900, description="URL validity in seconds")


class CreateBugReportRequest(BaseModel):
    """Request body to submit a bug report."""
    subject: str = Field(..., min_length=1, max_length=200, description="Short subject line")
    description: str = Field(..., min_length=1, max_length=5000, description="Detailed bug description")
    attachment_key: Optional[str] = Field(default=None, description="S3 key from the presigned upload (if any)")
    source_app_version: Optional[str] = Field(default=None, description="App version string")
    source_platform: Optional[str] = Field(default=None, description="Platform (ios/android)")


class CreateBugReportResponse(BaseModel):
    """Response after successful bug report creation."""
    id: str = Field(..., description="Unique bug report ticket ID")
    status: str = Field(..., description="Initial status of the report")
    message: str = Field(default="Bug report submitted successfully. We'll look into it shortly.")


# --- Endpoints ---


@router.post(
    "/upload-url",
    response_model=RequestUploadUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="Get presigned upload URL for bug report attachment",
)
async def request_upload_url(
    body: RequestUploadUrlRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> RequestUploadUrlResponse:
    """
    Generate a presigned S3 PUT URL for the client to upload an attachment.
    Validates file size and type before issuing the URL.
    """
    # Validate file size
    if body.file_size > BUG_REPORT_MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum of {BUG_REPORT_MAX_FILE_SIZE // (1024 * 1024)} MB.",
        )

    # Validate extension
    filename_lower = body.filename.lower()
    ext = "." + filename_lower.rsplit(".", 1)[-1] if "." in filename_lower else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File type not allowed. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Validate content type
    if body.content_type.lower() not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Content type '{body.content_type}' not allowed.",
        )

    # Generate a unique S3 key
    report_id = str(uuid.uuid4())
    s3_key = f"{current_user.id}/{report_id}/{body.filename}"

    # Generate presigned PUT URL
    try:
        upload_url = await s3_utils.generate_presigned_url(
            bucket=BUG_REPORT_BUCKET,
            key=s3_key,
            expiration=900,  # 15 minutes
            http_method="PUT",
        )
    except Exception as e:
        logger.error(f"Failed to generate presigned URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate upload URL. Please try again.",
        )

    return RequestUploadUrlResponse(
        upload_url=upload_url,
        attachment_key=s3_key,
        expires_in=900,
    )


@router.post(
    "",
    response_model=CreateBugReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a bug report",
)
async def create_bug_report(
    body: CreateBugReportRequest,
    current_user: AuthUser = Depends(get_current_user),
) -> CreateBugReportResponse:
    """
    Create a new bug report. Persists to DynamoDB and routes to Discord.
    Rate limited to 5 reports/hour/user.
    """
    # Rate limit check
    _check_rate_limit(current_user.id)

    # If attachment_key is provided, validate the object exists and check content-type
    if body.attachment_key:
        await _validate_attachment(body.attachment_key, current_user.id)

    # Create the bug report
    service = BugReportService()
    report = await service.create_report(
        user_id=current_user.id,
        subject=body.subject,
        description=body.description,
        attachment_key=body.attachment_key,
        source_app_version=body.source_app_version,
        source_platform=body.source_platform,
    )

    # Route to triage channel (async, non-blocking — failure here doesn't fail the request)
    try:
        await service.route_to_triage(report)
    except Exception as e:
        logger.warning(f"Failed to route bug report {report.id} to triage: {e}")

    return CreateBugReportResponse(
        id=report.id,
        status=report.status.value,
    )


async def _validate_attachment(attachment_key: str, user_id: str) -> None:
    """
    Validate that the attachment exists in S3 and has an allowed content-type.
    Also verifies the key belongs to this user (key starts with user_id/).
    """
    # Security: ensure the key belongs to this user
    if not attachment_key.startswith(f"{user_id}/"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Attachment key does not belong to this user.",
        )

    # Validate extension from the key
    key_lower = attachment_key.lower()
    ext = "." + key_lower.rsplit(".", 1)[-1] if "." in key_lower else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Attachment file type not allowed. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    # Head object to verify it exists and check content-type
    try:
        metadata = await s3_utils.get_object_metadata(BUG_REPORT_BUCKET, attachment_key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Attachment not found. Please upload the file before submitting the report.",
        )

    # Validate content-type from S3 metadata
    content_type = metadata.get("ContentType", "").lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Attachment content type '{content_type}' not allowed after server-side inspection.",
        )
