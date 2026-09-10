"""
Port (interface) for reading a web article's text.

The contract any article reader must implement. Two callers use it, which is the
whole point of it being a port:

- `core/media_ingestion/adapters/resolvers.py::ArticleResolver`, on the API path,
  **before** the content identity is settled -- an article whose text changed is a
  different media, so the text has to be in hand before `media_key` exists
  (task-392);
- `workers/article_extraction_worker.py`, for the items an RSS subscription
  produces, which arrive with their job already created.

One implementation, in `infrastructure/resolvers/trafilatura_article_resolver.py`.
Failures are named by `ArticleFetchErrorCode` and each one maps to the
`MediaFailureCode` the mobile app already renders in the reader's language: this
port adds no new user-facing vocabulary.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from media_summarizer.core.models.failure_codes import MediaFailureCode


class ArticleFetchErrorCode(str, Enum):
    """Stable reasons a page's text could not be read.

    Provider-level vocabulary, deliberately finer than `MediaFailureCode`: the
    logs need to tell "the server answered 503" from "the server answered a PDF",
    while the reader only needs to know whether to retry or to give up.
    """

    HTTP_ERROR = "http_error"
    NOT_HTML = "not_html"
    PAGE_TOO_LARGE = "page_too_large"
    EXTRACTION_FAILED = "extraction_failed"
    EMPTY_TEXT = "empty_text"
    TIMEOUT = "timeout"
    TRANSPORT_ERROR = "transport_error"
    UNEXPECTED_ERROR = "unexpected_error"


#: How each reason reads to the person who saved the link. `NOT_AN_ARTICLE_PAGE`
#: and `ARTICLE_TEXT_NOT_FOUND` are also the two codes the detail screen offers a
#: "request support for this source" action on, which is why a page that answered
#: a PDF and a page whose body we could not find stay distinct here.
MEDIA_FAILURE_CODE_BY_ARTICLE_FETCH_ERROR: Dict[
    ArticleFetchErrorCode, MediaFailureCode
] = {
    ArticleFetchErrorCode.HTTP_ERROR: MediaFailureCode.PROVIDER_UNAVAILABLE,
    ArticleFetchErrorCode.NOT_HTML: MediaFailureCode.NOT_AN_ARTICLE_PAGE,
    ArticleFetchErrorCode.PAGE_TOO_LARGE: MediaFailureCode.ARTICLE_TEXT_NOT_FOUND,
    ArticleFetchErrorCode.EXTRACTION_FAILED: MediaFailureCode.ARTICLE_TEXT_NOT_FOUND,
    ArticleFetchErrorCode.EMPTY_TEXT: MediaFailureCode.ARTICLE_TEXT_NOT_FOUND,
    ArticleFetchErrorCode.TIMEOUT: MediaFailureCode.PROVIDER_TIMED_OUT,
    ArticleFetchErrorCode.TRANSPORT_ERROR: MediaFailureCode.PROVIDER_UNAVAILABLE,
    ArticleFetchErrorCode.UNEXPECTED_ERROR: MediaFailureCode.UNEXPECTED_ERROR,
}


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class ArticleContent:
    """One page, read: its body text and the metadata that came with it.

    `text` is already normalized for storage, which matters beyond tidiness: it is
    the exact string that gets fingerprinted into the media key and the exact
    string uploaded as the transcript. Fingerprinting anything else would make the
    identity depend on a formatting pass nobody can see.
    """

    text: str
    requested_url: str
    final_url: Optional[str] = None
    http_status: Optional[int] = None
    content_type: Optional[str] = None
    fetched_at: str = field(default_factory=_now_iso_utc)
    title: Optional[str] = None
    creator_name: Optional[str] = None
    cover_url: Optional[str] = None
    language: Optional[str] = None
    char_count: int = 0
    word_count: int = 0
    paragraph_count: int = 0
    provider: str = ""
    extractor: str = ""

    def extraction_metadata(self) -> Dict[str, Any]:
        """The `ProcessingJob.extraction_metadata` shape, built in one place."""
        return {
            "extractor": self.extractor or self.provider,
            "extractor_version": "v1",
            "requested_url": self.requested_url,
            "final_url": self.final_url,
            "http_status": self.http_status,
            "content_type": self.content_type,
            "fetched_at": self.fetched_at,
            "char_count": self.char_count,
            "word_count": self.word_count,
            "paragraph_count": self.paragraph_count,
            "language": self.language,
            "title": self.title,
            "last_error_code": None,
        }


class ArticleFetchError(Exception):
    """A page whose text could not be read, with a stable reason.

    `retryable` separates a passing outage (a 503, a timeout, a reset connection)
    from a verdict on the page itself (it is a PDF, it has no body). The API path
    reads it to decide whether to keep the content reservation -- a transient
    failure must not lock a URL out of every later save.
    """

    def __init__(
        self,
        code: ArticleFetchErrorCode,
        *,
        details: str,
        retryable: bool = False,
        **context: Any,
    ) -> None:
        self.code = code
        self.details = details
        self.retryable = retryable
        self.context: Dict[str, Any] = {
            key: value for key, value in context.items() if value is not None
        }
        super().__init__(f"{code.value}: {details}")

    @property
    def media_failure_code(self) -> MediaFailureCode:
        """The code the job is marked failed with, and the reader eventually sees."""
        return MEDIA_FAILURE_CODE_BY_ARTICLE_FETCH_ERROR.get(
            self.code, MediaFailureCode.UNEXPECTED_ERROR
        )

    def error_metadata(self, *, step: str) -> Dict[str, Any]:
        """Diagnostic context for the job row. Written for us, not for a reader."""
        return {
            "step": step,
            "reason": self.details,
            "fetch_error_code": self.code.value,
            "retryable": self.retryable,
            **self.context,
        }


class ArticleContentFetcherPort(ABC):
    """Abstract interface for reading a web article."""

    @abstractmethod
    async def fetch(self, url: str) -> ArticleContent:
        """Read one page and return its body text plus what came with it.

        Raises:
            ArticleFetchError: the page could not be read, with a stable code.
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name of the extraction provider."""
        ...
