"""
Validation helpers for API inputs.

This module includes functions to validate external URLs (e.g., podcast audio URLs)
with security constraints suitable for production environments.
"""
import os
from urllib.parse import urlparse
from typing import Optional

import httpx


ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").lower()
MAX_AUDIO_SIZE_MB = int(os.environ.get("MAX_AUDIO_SIZE_MB", "500"))
DOWNLOAD_TIMEOUT_SECONDS = int(os.environ.get("DOWNLOAD_TIMEOUT_SECONDS", "60"))


async def _head_content_length(url: str, timeout_s: int) -> Optional[int]:
    timeout = httpx.Timeout(timeout_s)
    async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
        try:
            resp = await client.head(url)
            # Some servers may not support HEAD; try GET with minimal range
            if resp.status_code in (405, 403) or "content-length" not in resp.headers:
                headers = {"Range": "bytes=0-0"}
                get_resp = await client.get(url, headers=headers)
                content_length = get_resp.headers.get("content-length") or get_resp.headers.get("Content-Range")
                if content_length and "/" in content_length:
                    # Content-Range: bytes 0-0/123456
                    try:
                        total = int(content_length.split("/")[-1])
                        return total
                    except ValueError:
                        return None
                return int(get_resp.headers.get("content-length")) if get_resp.headers.get("content-length") else None
            return int(resp.headers.get("content-length")) if resp.headers.get("content-length") else None
        except Exception:
            # Network issues: don't expose details here; return None to skip size check
            return None


async def validate_audio_url(url: str) -> None:
    """
    Validate an audio URL against security and size constraints.

    Rules:
    - In production, HTTPS is required
    - If Content-Length is available, it must be <= MAX_AUDIO_SIZE_MB

    Raises:
        ValueError: if validation fails
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL manquante ou invalide")

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Schéma d'URL non valide (http/https requis)")

    if ENVIRONMENT == "production" and parsed.scheme != "https":
        raise ValueError("HTTPS requis en production")

    # Optional size check via HEAD/GET
    size = await _head_content_length(url, DOWNLOAD_TIMEOUT_SECONDS)
    if size is not None:
        max_bytes = MAX_AUDIO_SIZE_MB * 1024 * 1024
        if size > max_bytes:
            raise ValueError(f"Fichier audio trop volumineux (> {MAX_AUDIO_SIZE_MB} MB)")

    # Passed validation
    return None
