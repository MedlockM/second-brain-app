"""
Infrastructure preflight checks.

Current scope: verify that required S3 buckets exist. Terraform is expected to provision
all buckets in development and production. The app should fail fast if buckets are missing.
"""
from __future__ import annotations

import os
import logging
from typing import List

from aiobotocore.session import get_session

logger = logging.getLogger(__name__)

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


def required_s3_buckets_from_env() -> List[str]:
    """Return the list of required S3 bucket names from environment variables."""
    allowed_artifact_types = {
        chunk.strip().lower()
        for chunk in os.environ.get("ARTIFACT_TYPES_ALLOWED", "summary,quiz,notes").split(",")
        if chunk.strip()
    }
    buckets = [
        os.environ.get("AUDIO_BUCKET", "media-summarizer-audio"),
        os.environ.get("TRANSCRIPT_BUCKET", "media-summarizer-transcriptions"),
        os.environ.get("SUMMARY_BUCKET", "media-summarizer-summaries"),
        os.environ.get("QUIZ_BUCKET", "media-summarizer-quizzes"),
    ]
    if "notes" in allowed_artifact_types:
        buckets.append(os.environ.get("NOTES_BUCKET", "media-summarizer-notes"))
    # Filter out empty values and duplicates while preserving order
    seen = set()
    result: List[str] = []
    for b in buckets:
        b = (b or "").strip()
        if b and b not in seen:
            seen.add(b)
            result.append(b)
    return result


async def s3_preflight_check() -> List[str]:
    """Return a list of missing S3 buckets. Empty list means OK.

    Uses aiobotocore to list buckets and compares with required env-configured names.
    """
    required = required_s3_buckets_from_env()
    if not required:
        logger.warning("No required S3 buckets configured via env; skipping S3 preflight check.")
        return []

    session = get_session()
    async with session.create_client(
        "s3", region_name=AWS_REGION
    ) as s3:
        try:
            resp = await s3.list_buckets()
            existing = {b["Name"] for b in resp.get("Buckets", [])}
            missing = [b for b in required if b not in existing]
            if missing:
                logger.error(
                    "S3 preflight check failed; missing buckets: %s", ", ".join(missing)
                )
            else:
                logger.info("S3 preflight check passed: all required buckets exist.")
            return missing
        except Exception as e:
            logger.error("S3 preflight check error: %s", str(e))
            # On error, treat as failure to be safe
            return required


if __name__ == "__main__":
    import asyncio
    missing_buckets = asyncio.run(s3_preflight_check())
    if missing_buckets:
        print(
            "Missing S3 buckets: " + ", ".join(missing_buckets) +
            ". Provision infrastructure via Terraform (docker-compose terraform service)."
        )
        raise SystemExit(1)
    print("S3 preflight check OK")
    raise SystemExit(0)
