"""
Unstructured API resolver -- fallback document parsing adapter.

Uses the Unstructured cloud API (15,000 free pages initially, then $0.03/page)
as a fallback when LlamaParse is unavailable or rate-limited.

Supports: PDF, DOCX, PPTX, XLSX, images (JPG, PNG, BMP, TIFF, HEIC).

Environment variables:
    UNSTRUCTURED_API_KEY: API key for Unstructured (required)
    UNSTRUCTURED_API_URL: API base URL (default: https://api.unstructuredapp.io)
    UNSTRUCTURED_TIMEOUT_SECONDS: Request timeout (default 120)
"""

from __future__ import annotations

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

UNSTRUCTURED_API_URL = os.environ.get(
    "UNSTRUCTURED_API_URL", "https://api.unstructuredapp.io"
)
UNSTRUCTURED_API_KEY = os.environ.get("UNSTRUCTURED_API_KEY", "")
UNSTRUCTURED_TIMEOUT_SECONDS = int(
    os.environ.get("UNSTRUCTURED_TIMEOUT_SECONDS", "120")
)


class UnstructuredResolver(DocumentParserPort):
    """
    Adapter for the Unstructured cloud API.

    Implements the DocumentParserPort interface. Sends a file to the
    partition endpoint and converts the structured elements into markdown.
    """

    def __init__(self, api_key: Optional[str] = None, timeout: Optional[int] = None):
        self._api_key = api_key or UNSTRUCTURED_API_KEY
        self._timeout = timeout or UNSTRUCTURED_TIMEOUT_SECONDS

    @property
    def provider_name(self) -> str:
        return "unstructured"

    def supports_format(self, document_format: DocumentFormat) -> bool:
        """Unstructured supports all DocumentFormat values (60+ formats)."""
        return True

    async def parse(
        self,
        file_path: str,
        file_name: str,
        document_format: DocumentFormat,
    ) -> ParseResult | ParseError:
        """
        Send a document to the Unstructured partition API and return markdown.

        The API returns a list of structured elements (Title, NarrativeText,
        Table, etc.) which we assemble into clean markdown output.
        """
        if not self._api_key:
            return ParseError(
                code=ParseErrorCode.AUTHENTICATION_ERROR,
                message="UNSTRUCTURED_API_KEY is not configured",
                provider=self.provider_name,
                retryable=False,
            )

        headers = {
            "unstructured-api-key": self._api_key,
            "Accept": "application/json",
        }

        partition_url = f"{UNSTRUCTURED_API_URL}/general/v0/general"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                with open(file_path, "rb") as f:
                    files = {"files": (file_name, f, "application/octet-stream")}
                    data = {
                        "strategy": "hi_res",
                        "output_format": "application/json",
                    }
                    response = await client.post(
                        partition_url,
                        headers=headers,
                        files=files,
                        data=data,
                    )

                response.raise_for_status()
                elements = response.json()

                if not elements:
                    return ParseError(
                        code=ParseErrorCode.EMPTY_RESULT,
                        message="Unstructured returned no elements",
                        provider=self.provider_name,
                        retryable=False,
                    )

                # Convert structured elements to markdown
                markdown = self._elements_to_markdown(elements)

                if not markdown.strip():
                    return ParseError(
                        code=ParseErrorCode.EMPTY_RESULT,
                        message="Unstructured elements produced empty markdown",
                        provider=self.provider_name,
                        retryable=False,
                    )

                # Estimate page count from element metadata
                page_numbers = set()
                for el in elements:
                    meta = el.get("metadata", {})
                    page_num = meta.get("page_number")
                    if page_num is not None:
                        page_numbers.add(page_num)

                return ParseResult(
                    markdown_content=markdown,
                    page_count=len(page_numbers) if page_numbers else 1,
                    metadata={
                        "element_count": len(elements),
                        "strategy": "hi_res",
                    },
                    provider=self.provider_name,
                )

        except httpx.TimeoutException:
            return ParseError(
                code=ParseErrorCode.TIMEOUT,
                message=f"Unstructured request timed out after {self._timeout}s",
                provider=self.provider_name,
                retryable=True,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                return ParseError(
                    code=ParseErrorCode.RATE_LIMITED,
                    message="Unstructured rate limit exceeded",
                    provider=self.provider_name,
                    retryable=True,
                )
            if e.response.status_code in (401, 403):
                return ParseError(
                    code=ParseErrorCode.AUTHENTICATION_ERROR,
                    message=f"Unstructured authentication failed: {e.response.status_code}",
                    provider=self.provider_name,
                    retryable=False,
                )
            return ParseError(
                code=ParseErrorCode.API_ERROR,
                message=f"Unstructured HTTP error: {e.response.status_code} - {e.response.text[:200]}",
                provider=self.provider_name,
                retryable=e.response.status_code >= 500,
            )
        except httpx.ConnectError:
            return ParseError(
                code=ParseErrorCode.NETWORK_ERROR,
                message="Failed to connect to Unstructured API",
                provider=self.provider_name,
                retryable=True,
            )
        except Exception as e:
            return ParseError(
                code=ParseErrorCode.API_ERROR,
                message=f"Unexpected Unstructured error: {type(e).__name__}: {str(e)[:200]}",
                provider=self.provider_name,
                retryable=False,
            )

    @staticmethod
    def _elements_to_markdown(elements: list[dict]) -> str:
        """
        Convert Unstructured API elements to markdown text.

        Element types handled:
        - Title -> ## heading
        - NarrativeText -> paragraph
        - ListItem -> bullet point
        - Table -> preserved as-is (usually HTML table)
        - Image -> [Image] placeholder
        - Others -> plain text
        """
        lines: list[str] = []

        for element in elements:
            el_type = element.get("type", "")
            text = element.get("text", "").strip()

            if not text:
                continue

            if el_type == "Title":
                lines.append(f"\n## {text}\n")
            elif el_type == "Header":
                lines.append(f"\n# {text}\n")
            elif el_type == "NarrativeText":
                lines.append(f"\n{text}\n")
            elif el_type == "ListItem":
                lines.append(f"- {text}")
            elif el_type == "Table":
                # Tables from Unstructured often come as HTML; preserve as-is
                lines.append(f"\n{text}\n")
            elif el_type == "Image":
                lines.append("\n[Image]\n")
            elif el_type == "FigureCaption":
                lines.append(f"*{text}*\n")
            elif el_type == "Formula":
                lines.append(f"\n$$\n{text}\n$$\n")
            else:
                # Default: treat as paragraph
                lines.append(f"\n{text}\n")

        return "\n".join(lines).strip()
