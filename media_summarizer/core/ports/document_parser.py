"""
Port (interface) for document parsing services.

Defines the contract that any document parser resolver must implement.
This follows hexagonal architecture: the core domain depends only on this
interface, and concrete implementations (LlamaParse, Unstructured) live
in infrastructure/resolvers/.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DocumentFormat(str, Enum):
    """Supported document formats for parsing.

    Three regimes behind one enum, and the worker routes on them:

    - the office formats, parsed by LlamaParse with Unstructured as a fallback;
    - the image formats, OCR'd by the same providers;
    - the **text formats** (task-380), which have no provider at all: a `.txt`,
      `.md` or `.rtf` file already *is* its own text, so it is decoded in the
      worker (`PlainTextResolver`) and paginates nothing.
    """

    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    XLSX = "xlsx"
    TEXT_TXT = "txt"
    TEXT_MD = "md"
    TEXT_RTF = "rtf"
    IMAGE_JPG = "jpg"
    IMAGE_JPEG = "jpeg"
    IMAGE_PNG = "png"
    IMAGE_TIFF = "tiff"
    IMAGE_BMP = "bmp"
    IMAGE_HEIF = "heif"

    @classmethod
    def from_extension(cls, ext: str) -> Optional["DocumentFormat"]:
        """Resolve a file extension (without dot) to a DocumentFormat."""
        ext_lower = ext.lower().lstrip(".")
        mapping = {
            "pdf": cls.PDF,
            "docx": cls.DOCX,
            "pptx": cls.PPTX,
            "xlsx": cls.XLSX,
            "txt": cls.TEXT_TXT,
            # `.text` and `.markdown` are the long spellings of the same bytes;
            # a note exported by an Android app can carry either.
            "text": cls.TEXT_TXT,
            "md": cls.TEXT_MD,
            "markdown": cls.TEXT_MD,
            "rtf": cls.TEXT_RTF,
            "jpg": cls.IMAGE_JPG,
            "jpeg": cls.IMAGE_JPEG,
            "png": cls.IMAGE_PNG,
            "tiff": cls.IMAGE_TIFF,
            "tif": cls.IMAGE_TIFF,
            "bmp": cls.IMAGE_BMP,
            "heif": cls.IMAGE_HEIF,
            "heic": cls.IMAGE_HEIF,
        }
        return mapping.get(ext_lower)

    @classmethod
    def supported_extensions(cls) -> set[str]:
        """Return the set of all supported file extensions (without dot)."""
        return {
            "pdf", "docx", "pptx", "xlsx",
            "txt", "text", "md", "markdown", "rtf",
            "jpg", "jpeg", "png", "tiff", "tif", "bmp", "heif", "heic",
        }


#: The formats no provider is called for (task-380). Declared next to the enum,
#: not inside the adapter that decodes them: the API reads it to price an upload
#: at zero and the worker reads it to route, and a second copy of the list is
#: exactly how those two would come to disagree.
TEXT_FORMATS: frozenset[DocumentFormat] = frozenset(
    {
        DocumentFormat.TEXT_TXT,
        DocumentFormat.TEXT_MD,
        DocumentFormat.TEXT_RTF,
    }
)


def is_text_format(file_name: str) -> bool:
    """Whether this file name is one of the text formats, extension being all we have."""
    ext = file_name.rsplit(".", 1)[-1] if "." in file_name else ""
    document_format = DocumentFormat.from_extension(ext)
    return document_format is not None and document_format in TEXT_FORMATS


class ParseErrorCode(str, Enum):
    """Stable error codes for document parsing failures."""

    UNSUPPORTED_FORMAT = "unsupported_format"
    RATE_LIMITED = "rate_limited"
    API_ERROR = "api_error"
    TIMEOUT = "timeout"
    EMPTY_RESULT = "empty_result"
    FILE_TOO_LARGE = "file_too_large"
    AUTHENTICATION_ERROR = "authentication_error"
    NETWORK_ERROR = "network_error"
    INVALID_FILE = "invalid_file"


@dataclass
class ParseResult:
    """Result of a successful document parse."""

    markdown_content: str
    page_count: int = 0
    metadata: dict = field(default_factory=dict)
    provider: str = ""


@dataclass
class ParseError:
    """Result of a failed document parse."""

    code: ParseErrorCode
    message: str
    provider: str = ""
    retryable: bool = False


class DocumentParserPort(ABC):
    """Abstract interface for document parsing services."""

    @abstractmethod
    async def parse(
        self,
        file_path: str,
        file_name: str,
        document_format: DocumentFormat,
    ) -> ParseResult | ParseError:
        """
        Parse a document file and extract structured text as markdown.

        Args:
            file_path: Local filesystem path to the document file.
            file_name: Original filename (used for format hints to the API).
            document_format: The detected format of the document.

        Returns:
            ParseResult on success, ParseError on failure.
        """
        ...

    @abstractmethod
    def supports_format(self, document_format: DocumentFormat) -> bool:
        """Check whether this parser supports the given format."""
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name of the parsing provider."""
        ...
