"""Article reader: an HTTP fetch and a trafilatura extraction, behind the port.

The single implementation of `ArticleContentFetcherPort`. It used to live inside
`workers/article_extraction_worker.py`, where only the RSS path could reach it;
task-392 made the API path need the same bytes -- an article whose text changed is
a different media, so the text is read *before* the content identity is settled --
and a second copy of a fetch policy (redirects, content-type gate, size cap,
encoding fallback) is exactly how two paths come to disagree about what a page
says.

`trafilatura` is imported lazily, inside the extraction call. It pulls `lxml`, and
paying that import on every API cold start -- including the requests that never
touch an article -- is what the split image was built to avoid.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

import httpx

from media_summarizer.core.media_ingestion.media_metadata import (
    normalize_cover_url,
    select_creator,
)
from media_summarizer.core.media_ingestion.title_derivation import select_title
from media_summarizer.core.ports.article_content import (
    ArticleContent,
    ArticleContentFetcherPort,
    ArticleFetchError,
    ArticleFetchErrorCode,
)
from media_summarizer.core.services.transcript_formatting import (
    count_paragraphs,
    normalize_transcript_text,
)

logger = logging.getLogger(__name__)

#: The worker's budget. It runs on a 60 s Lambda and can afford a slow publisher.
DEFAULT_ARTICLE_FETCH_TIMEOUT_SECONDS = float(
    os.environ.get("ARTICLE_EXTRACT_TIMEOUT_SECONDS", "20")
)
#: The API's budget, and it is not a preference: API Gateway's HTTP API cuts the
#: request at 30 s and the ceiling is not configurable. A fetch that spends more
#: than this leaves no room for the library write, the reservation and the S3
#: upload that follow it in the same request.
API_ARTICLE_FETCH_TIMEOUT_SECONDS = float(
    os.environ.get("ARTICLE_FETCH_TIMEOUT_SECONDS", "12")
)
DEFAULT_ARTICLE_MAX_HTML_BYTES = max(
    1024, int(os.environ.get("ARTICLE_EXTRACT_MAX_HTML_BYTES", "2000000"))
)
DEFAULT_ARTICLE_USER_AGENT = os.environ.get(
    "ARTICLE_EXTRACT_USER_AGENT",
    "media-summarizer/article-extractor (+https://media-summarizer.local)",
)

_SUPPORTED_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


def _is_supported_content_type(content_type: str) -> bool:
    value = (content_type or "").lower()
    return any(token in value for token in _SUPPORTED_CONTENT_TYPES)


def _word_count(text: str) -> int:
    return len([token for token in text.split() if token.strip()])


class TrafilaturaArticleResolver(ArticleContentFetcherPort):
    """Reads a page over HTTP and extracts its body with trafilatura."""

    def __init__(
        self,
        *,
        timeout_seconds: Optional[float] = None,
        max_html_bytes: Optional[int] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        self._timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else DEFAULT_ARTICLE_FETCH_TIMEOUT_SECONDS
        )
        self._max_html_bytes = max_html_bytes or DEFAULT_ARTICLE_MAX_HTML_BYTES
        self._user_agent = user_agent or DEFAULT_ARTICLE_USER_AGENT

    @property
    def provider_name(self) -> str:
        return "article_extractor"

    async def fetch(self, url: str) -> ArticleContent:
        requested_url = (url or "").strip()
        if not requested_url:
            raise ArticleFetchError(
                ArticleFetchErrorCode.UNEXPECTED_ERROR,
                details="missing_article_url",
            )

        fetched = await self._fetch_html(requested_url)
        html = fetched["html"]
        final_url = fetched.get("final_url") or requested_url
        text = self._extract_clean_text(html)
        title, creator_name, cover_url = self._extract_metadata(
            html, requested_url=final_url
        )

        return ArticleContent(
            text=text,
            requested_url=requested_url,
            final_url=fetched.get("final_url"),
            http_status=fetched.get("http_status"),
            content_type=fetched.get("content_type"),
            title=title,
            creator_name=creator_name,
            cover_url=cover_url,
            language=None,
            char_count=len(text),
            word_count=_word_count(text),
            paragraph_count=count_paragraphs(text),
            provider=self.provider_name,
            extractor="trafilatura",
        )

    async def _fetch_html(self, url: str) -> Dict[str, Any]:
        headers = {
            "User-Agent": self._user_agent,
            "Accept": "text/html,application/xhtml+xml",
        }

        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                follow_redirects=True,
                headers=headers,
            ) as client:
                async with client.stream("GET", url) as response:
                    status_code = response.status_code
                    content_type = (response.headers.get("content-type") or "").strip()
                    final_url = str(response.url)

                    if status_code >= 400:
                        raise ArticleFetchError(
                            ArticleFetchErrorCode.HTTP_ERROR,
                            details="article_http_error",
                            # A 5xx may pass; a 404 or a 403 is the publisher's
                            # answer and will be the same answer next time.
                            retryable=status_code >= 500,
                            http_status=status_code,
                            final_url=final_url,
                        )

                    if not _is_supported_content_type(content_type):
                        raise ArticleFetchError(
                            ArticleFetchErrorCode.NOT_HTML,
                            details="article_unsupported_content_type",
                            content_type=content_type or None,
                            final_url=final_url,
                        )

                    total = 0
                    chunks: list[bytes] = []
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > self._max_html_bytes:
                            raise ArticleFetchError(
                                ArticleFetchErrorCode.PAGE_TOO_LARGE,
                                details="html_too_large",
                                html_bytes_limit=self._max_html_bytes,
                                final_url=final_url,
                            )
                        chunks.append(chunk)

                    encoding = response.encoding or "utf-8"
                    raw_html = b"".join(chunks)
                    try:
                        html = raw_html.decode(encoding, errors="replace")
                    except LookupError:
                        html = raw_html.decode("utf-8", errors="replace")

                    return {
                        "html": html,
                        "http_status": status_code,
                        "content_type": content_type,
                        "final_url": final_url,
                    }
        except ArticleFetchError:
            raise
        except httpx.TimeoutException as exc:
            raise ArticleFetchError(
                ArticleFetchErrorCode.TIMEOUT,
                details="article_fetch_timeout",
                retryable=True,
                exception_type=type(exc).__name__,
                timeout_seconds=self._timeout_seconds,
            ) from exc
        except httpx.HTTPError as exc:
            raise ArticleFetchError(
                ArticleFetchErrorCode.TRANSPORT_ERROR,
                details="article_fetch_transport_error",
                retryable=True,
                exception_type=type(exc).__name__,
            ) from exc
        except Exception as exc:
            raise ArticleFetchError(
                ArticleFetchErrorCode.UNEXPECTED_ERROR,
                details="article_fetch_unexpected_exception",
                exception_type=type(exc).__name__,
            ) from exc

    def _extract_clean_text(self, html: str) -> str:
        """The article body as paragraph-delimited plain text.

        trafilatura already emits blank-line separated paragraphs, so the
        normalizer is effectively a pass-through here -- a useful idempotence
        canary for the shared formatter (task-231 option B). It runs all the same,
        because this string is both what gets stored and what gets fingerprinted
        into the media key: the two must be the same bytes.
        """
        import trafilatura

        try:
            extracted = trafilatura.extract(
                html,
                output_format="txt",
                include_comments=False,
                include_tables=False,
                include_links=False,
            )
        except Exception as exc:
            raise ArticleFetchError(
                ArticleFetchErrorCode.EXTRACTION_FAILED,
                details="trafilatura_error",
                exception_type=type(exc).__name__,
            ) from exc

        text = normalize_transcript_text(extracted, source="article")
        if not text:
            raise ArticleFetchError(
                ArticleFetchErrorCode.EMPTY_TEXT,
                details="empty_text_after_extraction",
            )
        return text

    def _extract_metadata(
        self, html: str, *, requested_url: str
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """``(title, creator_name, cover_url)`` for one page, or ``None`` each.

        One `extract_metadata` call answers all three: trafilatura merges JSON-LD,
        OpenGraph and the `<title>` tag, and its `Document` exposes `image` (mapped
        from `og:image`/`twitter:image`), `sitename` and `author` (task-302 §2.3).
        The site name is the creator, the byline only its fallback -- for an article
        the publisher is what a reader recognises (task-302 §7.3).

        Any parsing failure is swallowed: a missing headline, creator or cover means
        a fallback, never a failed extraction.
        """
        import trafilatura

        try:
            document = trafilatura.extract_metadata(html, default_url=requested_url)
        except Exception:
            return None, None, None
        if document is None:
            return None, None, None

        site_name = getattr(document, "sitename", None)
        title = select_title(
            [getattr(document, "title", None)],
            authors=[getattr(document, "author", None)],
            site_names=[
                site_name,
                getattr(document, "hostname", None),
                requested_url,
            ],
        )
        creator_name = select_creator(
            [site_name, getattr(document, "author", None)],
            title=title,
        )
        cover_url = normalize_cover_url(getattr(document, "image", None))
        return title, creator_name, cover_url


def build_api_article_content_fetcher() -> ArticleContentFetcherPort:
    """The reader used on the API path, with the timeout that fits its 30 s ceiling."""
    return TrafilaturaArticleResolver(
        timeout_seconds=API_ARTICLE_FETCH_TIMEOUT_SECONDS
    )
