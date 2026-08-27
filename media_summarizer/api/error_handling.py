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


def _renderable_errors(errors: Sequence[Any]) -> Any:
    """Make a Pydantic error list renderable as JSON.

    When a ``field_validator`` rejects a value by raising ``ValueError``, Pydantic
    keeps the exception *object* in ``ctx["error"]``. ``json.dumps`` cannot render
    it, so serialising the list raw turns a 422 into a 500 inside the handler that
    was supposed to answer 422 — which is exactly what the internal-artifact-type
    validator hit on ``POST /api/artifacts``.
    """
    cleaned: List[Dict[str, Any]] = []
    for error in errors:
        item = dict(error)
        ctx = item.get("ctx")
        if isinstance(ctx, dict):
            item["ctx"] = {
                key: str(value) if isinstance(value, BaseException) else value
                for key, value in ctx.items()
            }
        cleaned.append(item)
    return jsonable_encoder(cleaned)


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
