from __future__ import annotations

import logging
from typing import Any, Dict, List, Sequence

from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from media_summarizer.utils.logging_config import log_event

logger = logging.getLogger(__name__)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    level = logging.ERROR if exc.status_code >= 500 else logging.WARNING
    log_event(
        logger,
        level,
        "api.request_error",
        str(exc.detail),
        status=exc.status_code,
        error_code=f"HTTP_{exc.status_code}",
        path=str(request.url.path),
        method=request.method,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None) or {},
    )


# A rejected value is echoed back to help the caller fix its request, not to
# reproduce the payload. Past this many characters it stops being a hint.
_MAX_RENDERED_INPUT = 200


def _renderable_value(value: Any) -> Any:
    """Replace anything ``jsonable_encoder`` would choke on by a safe stand-in.

    Two shapes reach here that JSON cannot hold. An exception *object*, which
    Pydantic keeps in ``ctx["error"]`` when a ``field_validator`` rejects a value
    by raising ``ValueError``. And raw ``bytes``, which Pydantic puts in
    ``input`` when a multipart field fails validation: ``jsonable_encoder``
    encodes bytes with a bare ``o.decode()``, so a PDF or a JPEG raises
    ``UnicodeDecodeError`` and the 422 handler dies with a 500.

    Both are flattened recursively, because ``input`` is as often a dict of form
    fields as it is a scalar.
    """
    if isinstance(value, (bytes, bytearray, memoryview)):
        return f"<{len(bytes(value))} bytes>"
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _renderable_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_renderable_value(item) for item in value]
    if isinstance(value, str) and len(value) > _MAX_RENDERED_INPUT:
        return f"{value[:_MAX_RENDERED_INPUT]}… (truncated)"
    return value


def _renderable_errors(errors: Sequence[Any]) -> Any:
    """Make a Pydantic error list renderable as JSON.

    Serialising the list raw turns a 422 into a 500 *inside the handler that was
    supposed to answer 422* — which is what the internal-artifact-type validator
    hit on ``POST /api/artifacts``, and again what a file shared into
    ``POST /api/media/upload`` by a pre-task-345 client hit on 2026-09-04: the
    binary body landed in ``input``, and the 500 hid the one thing the caller
    needed to read, that ``upload_key`` was missing.

    The last resort keeps ``loc``/``msg``/``type`` rather than raising: whatever
    an error carries, an error handler must answer.
    """
    cleaned: List[Dict[str, Any]] = [
        {str(key): _renderable_value(value) for key, value in dict(error).items()}
        for error in errors
    ]
    try:
        return jsonable_encoder(cleaned)
    except Exception as exc:  # pragma: no cover - defensive, see docstring
        log_event(
            logger,
            logging.ERROR,
            "api.validation_error.unrenderable",
            "Validation errors could not be serialised; answering with the bare fields",
            error_type=type(exc).__name__,
            error_code="VALIDATION_ERROR_UNRENDERABLE",
        )
        return [
            {
                "loc": [str(part) for part in (error.get("loc") or ())],
                "msg": str(error.get("msg", "")),
                "type": str(error.get("type", "")),
            }
            for error in (dict(item) for item in errors)
        ]


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    log_event(
        logger,
        logging.WARNING,
        "api.validation_error",
        "Request validation failed",
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        error_code="VALIDATION_ERROR",
        error_type="RequestValidationError",
        path=str(request.url.path),
        method=request.method,
        validation_error_count=len(errors),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": _renderable_errors(errors)},
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log_event(
        logger,
        logging.ERROR,
        "api.request_error",
        "Unhandled exception",
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="INTERNAL_SERVER_ERROR",
        error_type=type(exc).__name__,
        path=str(request.url.path),
        method=request.method,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
