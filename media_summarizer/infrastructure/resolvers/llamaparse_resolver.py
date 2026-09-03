"""
LlamaParse resolver -- primary document parsing adapter.

Uses the LlamaParse cloud API (free tier: 10,000 pages/month) to extract
structured markdown from uploaded documents. Supports 130+ formats including
PDF, DOCX, PPTX, XLSX, and images with OCR.

Environment variables:
    LLAMAPARSE_API_KEY: API key for LlamaParse (required)
    LLAMAPARSE_TIMEOUT_SECONDS: Request timeout (default 120)
    LLAMAPARSE_POLL_INTERVAL: Polling interval in seconds (default 2.0)
    LLAMAPARSE_MAX_POLLS: Maximum number of poll attempts (default 60)
    LLAMAPARSE_PAGE_IMAGE_TIMEOUT_SECONDS: Page-image fetch timeout (default 20)
    LLAMAPARSE_PAGE_IMAGE_MAX_BYTES: Page-image size ceiling (default 8 MB)
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

import httpx

from media_summarizer.core.ports.document_parser import (
    DocumentFormat,
    DocumentParserPort,
    ParseError,
    ParseErrorCode,
    ParseResult,
)

logger = logging.getLogger(__name__)

LLAMAPARSE_API_URL = "https://api.cloud.llamaindex.ai/api/parsing"
LLAMAPARSE_API_KEY = os.environ.get("LLAMAPARSE_API_KEY", "")
LLAMAPARSE_TIMEOUT_SECONDS = int(os.environ.get("LLAMAPARSE_TIMEOUT_SECONDS", "120"))
LLAMAPARSE_POLL_INTERVAL = float(os.environ.get("LLAMAPARSE_POLL_INTERVAL", "2.0"))
LLAMAPARSE_MAX_POLLS = int(os.environ.get("LLAMAPARSE_MAX_POLLS", "60"))

# Page-image (cover) fetch, task-344. Two extra GETs on a job that is already
# finished and already billed. A full-page screenshot measured 176 KB and 236 KB
# on task-343 §4.1 and 1.0 MB on a text-dense A4 DOCX during the implementation,
# so the ceiling is set well above the observed range: it exists to keep a
# surprising payload out of a 512 MB worker, not to filter normal pages.
LLAMAPARSE_PAGE_IMAGE_TIMEOUT_SECONDS = float(
    os.environ.get("LLAMAPARSE_PAGE_IMAGE_TIMEOUT_SECONDS", "20")
)
LLAMAPARSE_PAGE_IMAGE_MAX_BYTES = int(
    os.environ.get("LLAMAPARSE_PAGE_IMAGE_MAX_BYTES", str(8 * 1024 * 1024))
)
# The image kind LlamaParse gives a paginated document: one entry per page,
# rendered from the layout. Embedded illustrations carry other types and must
# never be mistaken for a page render -- a logo is not a cover.
_FULL_PAGE_SCREENSHOT_TYPE = "full_page_screenshot"


class LlamaParseResolver(DocumentParserPort):
    """
    Adapter for the LlamaParse cloud API.

    Implements the DocumentParserPort interface. Uploads a file, polls for
    completion, and returns the extracted markdown text.
    """

    def __init__(self, api_key: Optional[str] = None, timeout: Optional[int] = None):
        self._api_key = api_key or LLAMAPARSE_API_KEY
        self._timeout = timeout or LLAMAPARSE_TIMEOUT_SECONDS

    @property
    def provider_name(self) -> str:
        return "llamaparse"

    def supports_format(self, document_format: DocumentFormat) -> bool:
        """LlamaParse supports all DocumentFormat values (130+ formats)."""
        return True

    async def parse(
        self,
        file_path: str,
        file_name: str,
        document_format: DocumentFormat,
    ) -> ParseResult | ParseError:
        """
        Upload a document to LlamaParse and retrieve the parsed markdown.

        The workflow is:
        1. POST /upload with the file
        2. Poll GET /job/{job_id} until status is SUCCESS or ERROR
        3. GET /job/{job_id}/result/markdown to retrieve the content

        E2E test seam: if file_name starts with __e2e_force_llamaparse_failure__,
        return a simulated rate-limit error to exercise the Unstructured fallback path.
        This avoids Lambda env-var races by embedding the signal in the request itself.
        """
        if file_name.startswith("__e2e_force_llamaparse_failure__"):
            logger.info(
                "E2E sentinel detected in filename; returning simulated rate-limit error"
            )
            return ParseError(
                code=ParseErrorCode.RATE_LIMITED,
                message="Simulated LlamaParse failure (E2E test sentinel: __e2e_force_llamaparse_failure__)",
                provider=self.provider_name,
                retryable=True,
            )

        if not self._api_key:
            return ParseError(
                code=ParseErrorCode.AUTHENTICATION_ERROR,
                message="LLAMAPARSE_API_KEY is not configured",
                provider=self.provider_name,
                retryable=False,
            )

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                # Step 1: Upload the file
                job_id = await self._upload_file(client, headers, file_path, file_name)
                if isinstance(job_id, ParseError):
                    return job_id

                # Step 2: Poll for completion
                poll_result = await self._poll_job(client, headers, job_id)
                if isinstance(poll_result, ParseError):
                    return poll_result

                # Step 3: Retrieve markdown result
                return await self._get_result(client, headers, job_id)

        except httpx.TimeoutException:
            return ParseError(
                code=ParseErrorCode.TIMEOUT,
                message=f"LlamaParse request timed out after {self._timeout}s",
                provider=self.provider_name,
                retryable=True,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                return ParseError(
                    code=ParseErrorCode.RATE_LIMITED,
                    message="LlamaParse rate limit exceeded",
                    provider=self.provider_name,
                    retryable=True,
                )
            if e.response.status_code in (401, 403):
                return ParseError(
                    code=ParseErrorCode.AUTHENTICATION_ERROR,
                    message=f"LlamaParse authentication failed: {e.response.status_code}",
                    provider=self.provider_name,
                    retryable=False,
                )
            return ParseError(
                code=ParseErrorCode.API_ERROR,
                message=f"LlamaParse HTTP error: {e.response.status_code} - {e.response.text[:200]}",
                provider=self.provider_name,
                retryable=e.response.status_code >= 500,
            )
        except httpx.ConnectError:
            return ParseError(
                code=ParseErrorCode.NETWORK_ERROR,
                message="Failed to connect to LlamaParse API",
                provider=self.provider_name,
                retryable=True,
            )
        except Exception as e:
            return ParseError(
                code=ParseErrorCode.API_ERROR,
                message=f"Unexpected LlamaParse error: {type(e).__name__}: {str(e)[:200]}",
                provider=self.provider_name,
                retryable=False,
            )

    async def _upload_file(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        file_path: str,
        file_name: str,
    ) -> str | ParseError:
        """Upload file to LlamaParse and return the job ID."""
        upload_url = f"{LLAMAPARSE_API_URL}/upload"

        with open(file_path, "rb") as f:
            files = {"file": (file_name, f, "application/octet-stream")}
            data = {
                "result_type": "markdown",
                "language": "en",
            }
            response = await client.post(
                upload_url,
                headers=headers,
                files=files,
                data=data,
            )

        response.raise_for_status()
        result = response.json()
        job_id = result.get("id")

        if not job_id:
            return ParseError(
                code=ParseErrorCode.API_ERROR,
                message="LlamaParse upload did not return a job ID",
                provider=self.provider_name,
                retryable=True,
            )

        logger.info("LlamaParse upload successful, job_id=%s", job_id)
        return job_id

    async def _poll_job(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        job_id: str,
    ) -> None | ParseError:
        """Poll the job status until completion or failure."""
        status_url = f"{LLAMAPARSE_API_URL}/job/{job_id}"

        for _ in range(LLAMAPARSE_MAX_POLLS):
            response = await client.get(status_url, headers=headers)
            response.raise_for_status()
            result = response.json()
            status = result.get("status", "").upper()

            if status == "SUCCESS":
                return None
            elif status in ("ERROR", "FAILED"):
                error_msg = result.get("error", "Unknown parsing error")
                return ParseError(
                    code=ParseErrorCode.API_ERROR,
                    message=f"LlamaParse job failed: {error_msg}",
                    provider=self.provider_name,
                    retryable=False,
                )

            await asyncio.sleep(LLAMAPARSE_POLL_INTERVAL)

        return ParseError(
            code=ParseErrorCode.TIMEOUT,
            message=f"LlamaParse job {job_id} did not complete within polling limit",
            provider=self.provider_name,
            retryable=True,
        )

    async def _get_result(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        job_id: str,
    ) -> ParseResult | ParseError:
        """Retrieve the markdown result from a completed job."""
        result_url = f"{LLAMAPARSE_API_URL}/job/{job_id}/result/markdown"

        response = await client.get(result_url, headers=headers)
        response.raise_for_status()
        result = response.json()

        markdown = result.get("markdown", "")
        if not markdown or not markdown.strip():
            return ParseError(
                code=ParseErrorCode.EMPTY_RESULT,
                message="LlamaParse returned empty markdown content",
                provider=self.provider_name,
                retryable=False,
            )

        # Extract metadata if available
        metadata = {
            "job_id": job_id,
            "pages": result.get("pages", 0),
        }

        return ParseResult(
            markdown_content=markdown,
            page_count=result.get("pages", 0),
            metadata=metadata,
            provider=self.provider_name,
        )

    async def fetch_first_page_screenshot(self, job_id: str) -> Optional[bytes]:
        """Download the render of page 1 of a finished job. ``None`` if there is none.

        LlamaParse rasterises every page of a paginated document while parsing it
        and keeps the images on the job -- with the exact fields ``_upload_file``
        already sends, no screenshot flag needed (task-343 §4.1). So the cover of
        a PDF, a DOCX or a PPTX is an artefact we have already paid for: two GETs
        on a job that is complete, no new credit, no second parse.

        A spreadsheet has no page to photograph and returns no image in any mode
        or tier (task-343 §4.2); ``None`` here is the normal answer for an XLSX,
        and the caller draws the sheet instead.

        Best-effort like every cover path: this never raises. A missing image, an
        expired result, a non-200 or an oversized payload all return ``None`` and
        the tile keeps its media-type glyph.
        """
        if not job_id or not self._api_key:
            return None

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                timeout=LLAMAPARSE_PAGE_IMAGE_TIMEOUT_SECONDS
            ) as client:
                image_name = await self._first_page_image_name(client, headers, job_id)
                if not image_name:
                    return None
                return await self._download_page_image(
                    client, headers, job_id, image_name
                )
        except Exception as exc:  # noqa: BLE001 - a cover never fails an ingestion
            logger.warning(
                "LlamaParse page screenshot unavailable for job %s: %s",
                job_id,
                type(exc).__name__,
            )
            return None

    async def _first_page_image_name(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        job_id: str,
    ) -> Optional[str]:
        """Name of the page-1 full-page screenshot on a finished job."""
        response = await client.get(
            f"{LLAMAPARSE_API_URL}/job/{job_id}/result/json", headers=headers
        )
        response.raise_for_status()
        pages = response.json().get("pages") or []
        if not isinstance(pages, list) or not pages:
            return None

        first_page = pages[0]
        if not isinstance(first_page, dict):
            return None
        for image in first_page.get("images") or []:
            if not isinstance(image, dict):
                continue
            if image.get("type") != _FULL_PAGE_SCREENSHOT_TYPE:
                continue
            name = str(image.get("name") or "").strip()
            if name:
                return name
        return None

    async def _download_page_image(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        job_id: str,
        image_name: str,
    ) -> Optional[bytes]:
        """Fetch one page image, bounded in size."""
        url = f"{LLAMAPARSE_API_URL}/job/{job_id}/result/image/{image_name}"
        async with client.stream("GET", url, headers=headers) as response:
            response.raise_for_status()
            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > LLAMAPARSE_PAGE_IMAGE_MAX_BYTES:
                    logger.warning(
                        "LlamaParse page image exceeds %s bytes; cover skipped",
                        LLAMAPARSE_PAGE_IMAGE_MAX_BYTES,
                    )
                    return None
                chunks.append(chunk)
        payload = b"".join(chunks)
        return payload or None
