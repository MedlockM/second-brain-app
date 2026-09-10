"""The parsing chain and its meter, shared by every source that OCRs an image.

Owner decision (task-90): **LlamaParse free tier API cloud -> fallback
Unstructured API**. That chain used to live inside
`workers/document_parsing/worker.py`, which made it reachable only by a file the
user had uploaded. Since task-384 a second source needs exactly the same two
providers and exactly the same meter -- the images of an Instagram photo post --
so both functions moved here rather than being imported from one worker into
another: a worker importing a worker would drag `DOCUMENT_BUCKET`,
`DOCUMENT_PARSING_QUEUE` and a whole polling loop into an unrelated Lambda.

What is shared, and why it has to be the same code in both places:

- `parse_document_with_fallback` -- the provider order, the fallback rule and the
  three log events a run leaves behind. An image is an image: a photo taken from
  the gallery and a photo pulled off Instagram's CDN reach LlamaParse through
  this one function.
- `record_document_consumption` -- N pages is N pages. A carousel of four images
  is priced exactly like an upload of four photos (one minute per five pages,
  `quota_enforcer.minutes_for_document_pages`) and burns four pages of the shared
  LlamaParse pool. Two copies of this arithmetic is how the two sources would
  come to charge differently for the same purchase.

The parser instances are module-level and reused across messages. `llamaparse` is
public and typed as its concrete class, because the document cover reads back one
of its artefacts (`fetch_first_page_screenshot`) -- a LlamaParse capability, not a
parsing contract.
"""

from __future__ import annotations

import logging
from typing import Optional

from media_summarizer.core.ports.document_parser import (
    TEXT_FORMATS,
    DocumentFormat,
    DocumentParserPort,
    ParseError,
    ParseResult,
)
from media_summarizer.core.services import provider_pool_guard, quota_enforcer
from media_summarizer.infrastructure.resolvers.llamaparse_resolver import (
    LlamaParseResolver,
)
from media_summarizer.infrastructure.resolvers.plain_text_resolver import (
    PlainTextResolver,
)
from media_summarizer.infrastructure.resolvers.unstructured_resolver import (
    UnstructuredResolver,
)
from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)

#: Primary provider. Public: the document cover fetches the page render this
#: same instance produced while parsing.
llamaparse = LlamaParseResolver()
_unstructured: DocumentParserPort = UnstructuredResolver()
# The text formats never reach either of the two above: a `.txt`, `.md` or `.rtf`
# already holds its own text, so it is decoded here (task-380). No provider call,
# no page, nothing billed.
_plain_text: DocumentParserPort = PlainTextResolver()

#: Formats whose parsed output is OCR of a picture rather than a structured
#: document: their leading heading is body text, not a title (task-266). Declared
#: next to the chain that parses them, because both the document worker (title and
#: cover routing) and the Instagram worker (every image it downloads is one of
#: these) read the same list.
IMAGE_FORMATS: frozenset[DocumentFormat] = frozenset(
    {
        DocumentFormat.IMAGE_JPG,
        DocumentFormat.IMAGE_JPEG,
        DocumentFormat.IMAGE_PNG,
        DocumentFormat.IMAGE_TIFF,
        DocumentFormat.IMAGE_BMP,
        DocumentFormat.IMAGE_HEIF,
    }
)


async def parse_document_with_fallback(
    file_path: str,
    file_name: str,
    document_format: DocumentFormat,
) -> ParseResult | ParseError:
    """
    Attempt parsing with LlamaParse, falling back to Unstructured on failure.

    Fallback triggers:
    - LlamaParse returns a retryable error (rate limit, timeout, network)
    - LlamaParse returns an API error

    Does NOT fallback if:
    - The format itself is unsupported (both services support all our formats)
    - LlamaParse returns a non-retryable auth error and Unstructured also has
      no key configured (both would fail)
    - The format is a text one: it has no provider and therefore no fallback,
      because there is nothing a second provider could read better than the file
      itself.

    Note for callers OCR'ing a picture: "this image carries no text" comes back as
    a `ParseError` with `ParseErrorCode.EMPTY_RESULT`, from both providers -- not
    as a `ParseResult` holding an empty string. A photo of a sunset is therefore
    a *failed* parse here, and it is up to the caller to decide whether that is a
    normal outcome for its source.
    """
    if document_format in TEXT_FORMATS:
        text_result = await _plain_text.parse(file_path, file_name, document_format)
        log_event(
            logger,
            logging.INFO if isinstance(text_result, ParseResult) else logging.WARNING,
            "document_parsing.text_decoded",
            "Text file decoded locally; no parsing provider involved",
            provider="plain_text",
            document_format=document_format.value,
            succeeded=isinstance(text_result, ParseResult),
        )
        return text_result

    # Primary: LlamaParse
    primary_result = await llamaparse.parse(file_path, file_name, document_format)

    if isinstance(primary_result, ParseResult):
        log_event(
            logger,
            logging.INFO,
            "document_parsing.primary_success",
            "Document parsed successfully with LlamaParse",
            provider="llamaparse",
            page_count=primary_result.page_count,
        )
        return primary_result

    # Primary failed -- log and attempt fallback
    log_event(
        logger,
        logging.WARNING,
        "document_parsing.primary_failed",
        "LlamaParse failed, attempting Unstructured fallback",
        provider="llamaparse",
        error_code=primary_result.code.value,
        error_message=primary_result.message,
    )

    # Fallback: Unstructured API
    fallback_result = await _unstructured.parse(file_path, file_name, document_format)

    if isinstance(fallback_result, ParseResult):
        log_event(
            logger,
            logging.INFO,
            "document_parsing.fallback_success",
            "Document parsed successfully with Unstructured (fallback)",
            provider="unstructured",
            page_count=fallback_result.page_count,
        )
        return fallback_result

    # Both failed
    log_event(
        logger,
        logging.ERROR,
        "document_parsing.all_failed",
        "Both LlamaParse and Unstructured failed to parse document",
        primary_error=primary_result.message,
        fallback_error=fallback_result.message,
    )

    # Return the fallback error (most recent) with context about both failures
    return ParseError(
        code=fallback_result.code,
        message=(
            f"All parsers failed. "
            f"LlamaParse: {primary_result.message}. "
            f"Unstructured: {fallback_result.message}"
        ),
        provider="llamaparse+unstructured",
        retryable=primary_result.retryable or fallback_result.retryable,
    )


async def record_document_consumption(
    *,
    user_id: Optional[str],
    job_id: str,
    document_format: DocumentFormat,
    page_count: int,
    provider: str,
    llamaparse_pages: Optional[int] = None,
) -> None:
    """Charge a parsed document and count its pages against the LlamaParse pool.

    Best-effort by contract: the parse is done and already paid for, so a counter
    failure must never fail an import that succeeded. `record_spend` swallows its
    own errors; the user debit is wrapped here for the same reason.

    Both writes are idempotent on the job id -- `quota_enforcer.gate_token(job_id)`
    for the minutes, `llamaparse:<job_id>` for the pool -- so a redelivered SQS
    message or a re-claimed Apify callback cannot debit twice.

    A text file takes the other branch: it has no pages to price and cost no
    provider call, so it is *counted* as an import and charged zero minutes
    rather than rounded up to the single page every other format has (task-380).

    ``llamaparse_pages`` exists for a source parsed one file at a time: an
    Instagram carousel can have some of its images read by LlamaParse and the rest
    by the Unstructured fallback, so the pool count cannot be derived from a
    single provider name. Left to ``None``, the whole page count goes to the pool
    when ``provider`` is LlamaParse and nothing does otherwise -- which is what a
    single uploaded document means.
    """
    if document_format in TEXT_FORMATS:
        if not user_id:
            return
        await quota_enforcer.record_text_file_parse(
            user_id,
            idempotency_token=quota_enforcer.gate_token(job_id),
        )
        log_event(
            logger,
            logging.INFO,
            "quota.text_file_counted",
            "Text file counted as an import; no minutes charged",
            job_id=job_id,
            document_format=document_format.value,
        )
        return

    pages = max(1, int(page_count or 1))
    is_llamaparse = provider.strip().lower() == "llamaparse"
    pool_pages = llamaparse_pages if llamaparse_pages is not None else (pages if is_llamaparse else 0)

    if pool_pages > 0:
        await provider_pool_guard.record_spend(
            provider_pool_guard.POOL_LLAMAPARSE,
            units=pool_pages,
            idempotency_token=f"llamaparse:{job_id}",
        )

    if not user_id:
        log_event(
            logger,
            logging.WARNING,
            "quota.document_debit_skipped_no_user",
            "No user_id on the parsed media; nothing to charge",
            job_id=job_id,
        )
        return

    try:
        minutes = await quota_enforcer.record_document_parse(
            user_id,
            page_count=pages,
            idempotency_token=quota_enforcer.gate_token(job_id),
        )
    except Exception as exc:  # noqa: BLE001 - a meter failure never fails a parse
        log_event(
            logger,
            logging.WARNING,
            "quota.document_debit_failed",
            "Parsed pages could not be charged; the import stands",
            job_id=job_id,
            page_count=pages,
            provider=provider,
            error_type=type(exc).__name__,
        )
        return

    log_event(
        logger,
        logging.INFO,
        "quota.document_debited",
        "Document parse charged to the user's minutes",
        job_id=job_id,
        page_count=pages,
        provider=provider,
        debited_minutes=minutes,
    )
