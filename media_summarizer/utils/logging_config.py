from __future__ import annotations

import json
import logging
import os
import re
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_LOG_CONTEXT: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "media_summarizer_log_context",
    default=None,
)
_LOGGING_STATE: Dict[str, Any] = {
    "service": "media-summarizer",
    "env": "dev",
    "version": None,
}
_CONFIGURED_SIGNATURE: Optional[tuple[str, str, Optional[str], int]] = None
_AWS_ENDPOINT_WARNINGS: set[tuple[str, str, str]] = set()

_REDACTED = "[REDACTED]"
_EMAIL_RE = re.compile(r"\b([A-Z0-9._%+\-]+)@([A-Z0-9.\-]+\.[A-Z]{2,})\b", re.I)
_BEARER_RE = re.compile(r"(?i)\b(Bearer)\s+[A-Za-z0-9._~+/=-]+")
_TOKEN_RE = re.compile(r"(?i)\b(Token)\s+[A-Za-z0-9._~+/=-]+")
_COOKIE_PAIR_RE = re.compile(r"(?i)\b([A-Za-z0-9._\-]*cookie[A-Za-z0-9._\-]*)=([^;,\s]+)")
_SENSITIVE_QUERY_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "auth",
    "authorization",
    "code",
    "cookie",
    "password",
    "refresh_token",
    "secret",
    "sig",
    "signature",
    "token",
}
_SENSITIVE_FIELD_NAMES = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "cookies",
    "deepgram_api_key",
    "getinsaver_api_key",
    "jwt",
    "openai_api_key",
    "password",
    "refresh_token",
    "secret",
    "token",
}
_URL_FIELD_NAMES = {
    "audio_url",
    "final_url",
    "normalized_url",
    "requested_url",
    "source_url",
    "url",
}
_EMAIL_FIELD_NAMES = {"email", "user_email"}
_STANDARD_ATTRIBUTES = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}
_SCHEMA_FIELDS = (
    "timestamp",
    "level",
    "service",
    "env",
    "event",
    "message",
    "request_id",
    "user_id",
    "job_id",
    "media_item_id",
    "media_type",
    "source_platform",
    "resolver_key",
    "provider",
    "transcript_source",
    "fallback_strategy",
    "artifact_id",
    "artifact_type",
    "queue",
    "attempt",
    "duration_ms",
    "error_code",
    "error_type",
    "path",
    "method",
    "status",
    "version",
)


def normalize_environment(value: Optional[str] = None) -> str:
    raw = (value or os.environ.get("ENVIRONMENT") or "development").strip().lower()
    aliases = {
        "dev": "dev",
        "development": "dev",
        "local": "dev",
        "test": "test",
        "testing": "test",
        "prod": "prod",
        "production": "prod",
    }
    return aliases.get(raw, "dev")


def _resolve_log_level(env: Optional[str] = None) -> int:
    explicit = (os.environ.get("LOG_LEVEL") or "").strip().upper()
    if explicit:
        return getattr(logging, explicit, logging.INFO)

    normalized_env = normalize_environment(env)
    debug_enabled = os.environ.get("DEBUG", "false").lower() == "true"
    if normalized_env in {"dev", "test"} and debug_enabled:
        return logging.DEBUG
    return logging.INFO


def get_log_context() -> Dict[str, Any]:
    current = _LOG_CONTEXT.get()
    return dict(current or {})


def bind_log_context(**fields: Any) -> Token:
    merged = get_log_context()
    for key, value in fields.items():
        if value is not None:
            merged[key] = value
    return _LOG_CONTEXT.set(merged)


def reset_log_context(token: Token) -> None:
    _LOG_CONTEXT.reset(token)


def clear_log_context() -> None:
    _LOG_CONTEXT.set({})


def _mask_email(value: str) -> str:
    normalized = value.strip()
    if "@" not in normalized:
        return normalized
    local, domain = normalized.split("@", 1)
    if not local:
        return f"***@{domain}"
    if len(local) == 1:
        masked_local = f"{local}***"
    elif len(local) == 2:
        masked_local = f"{local[0]}***"
    else:
        masked_local = f"{local[0]}***{local[-1]}"
    return f"{masked_local}@{domain}"


def _redact_url_string(value: str) -> str:
    candidate = (value or "").strip()
    if not candidate.startswith(("http://", "https://")):
        return candidate
    try:
        split = urlsplit(candidate)
    except ValueError:
        return candidate

    if not split.query:
        return candidate

    redacted_pairs = []
    for key, item in parse_qsl(split.query, keep_blank_values=True):
        if key.lower() in _SENSITIVE_QUERY_KEYS:
            redacted_pairs.append((key, _REDACTED))
        else:
            redacted_pairs.append((key, item))

    return urlunsplit(
        (
            split.scheme,
            split.netloc,
            split.path,
            urlencode(redacted_pairs, doseq=True),
            split.fragment,
        )
    )


def _sanitize_string(value: str) -> str:
    redacted = _redact_url_string(value)
    redacted = _EMAIL_RE.sub(
        lambda match: _mask_email(f"{match.group(1)}@{match.group(2)}"),
        redacted,
    )
    redacted = _BEARER_RE.sub(r"\1 " + _REDACTED, redacted)
    redacted = _TOKEN_RE.sub(r"\1 " + _REDACTED, redacted)
    redacted = _COOKIE_PAIR_RE.sub(r"\1=" + _REDACTED, redacted)
    return redacted


def sanitize_log_value(value: Any, *, field_name: Optional[str] = None) -> Any:
    normalized_field = (field_name or "").strip().lower()
    if normalized_field in _SENSITIVE_FIELD_NAMES:
        return _REDACTED
    if normalized_field in _EMAIL_FIELD_NAMES and isinstance(value, str):
        return _mask_email(value)
    if normalized_field in _URL_FIELD_NAMES and isinstance(value, str):
        return _redact_url_string(value)

    if isinstance(value, dict):
        return {
            str(key): sanitize_log_value(item, field_name=str(key))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [sanitize_log_value(item, field_name=field_name) for item in value]
    if isinstance(value, str):
        return _sanitize_string(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return _sanitize_string(str(value))


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    message: str,
    *,
    exc_info: Any = None,
    **fields: Any,
) -> None:
    extra = dict(fields)
    extra["event"] = event
    logger.log(level, message, extra=extra, exc_info=exc_info)


def get_runtime_aws_endpoint_url(
    *,
    configured_value: Optional[str] = None,
    consumer: str = "aws",
) -> Optional[str]:
    raw = (
        configured_value
        if configured_value is not None
        else os.environ.get("AWS_ENDPOINT_URL")
    )
    value = (raw or "").strip()
    if not value:
        return None

    env = normalize_environment()
    if env == "dev":
        return value

    warning_key = (consumer, env, value)
    if warning_key not in _AWS_ENDPOINT_WARNINGS:
        _AWS_ENDPOINT_WARNINGS.add(warning_key)
        log_event(
            logging.getLogger(__name__),
            logging.WARNING,
            "runtime.aws_endpoint_ignored",
            "Ignoring AWS endpoint override outside dev",
            provider="aws",
            error_code="AWS_ENDPOINT_URL_IGNORED",
        )
    return None


def should_disable_access_logs(env: Optional[str] = None) -> bool:
    return normalize_environment(env) == "prod"


def get_slow_request_threshold_ms() -> int:
    raw = (os.environ.get("API_SLOW_REQUEST_THRESHOLD_MS") or "3000").strip()
    try:
        return max(100, int(raw))
    except ValueError:
        return 3000


class JsonFormatter(logging.Formatter):
    """Formatter that emits a stable JSON schema for application logs."""

    def format(self, record: logging.LogRecord) -> str:
        context = get_log_context()
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_ATTRIBUTES
        }

        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "service": _LOGGING_STATE["service"],
            "env": _LOGGING_STATE["env"],
            "event": extras.pop("event", None) or context.get("event") or "log.record",
            "message": sanitize_log_value(record.getMessage(), field_name="message"),
            "version": _LOGGING_STATE["version"],
        }

        combined = dict(context)
        combined.update(extras)
        for key, value in combined.items():
            payload[key] = sanitize_log_value(value, field_name=key)

        if record.exc_info:
            if not payload.get("error_type"):
                payload["error_type"] = record.exc_info[0].__name__
            payload["exception"] = sanitize_log_value(
                self.formatException(record.exc_info),
                field_name="exception",
            )

        for field_name in _SCHEMA_FIELDS:
            payload.setdefault(field_name, None)

        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(
    service: str,
    *,
    env: Optional[str] = None,
    version: Optional[str] = None,
) -> None:
    global _CONFIGURED_SIGNATURE

    normalized_env = normalize_environment(env)
    level = _resolve_log_level(normalized_env)
    signature = (service, normalized_env, version, level)
    if _CONFIGURED_SIGNATURE == signature:
        return

    _LOGGING_STATE["service"] = service
    _LOGGING_STATE["env"] = normalized_env
    _LOGGING_STATE["version"] = version

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.setLevel(level)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for existing in list(root_logger.handlers):
        root_logger.removeHandler(existing)
    root_logger.addHandler(handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        target = logging.getLogger(logger_name)
        target.handlers.clear()
        target.propagate = True
        if logger_name == "uvicorn.access" and should_disable_access_logs(normalized_env):
            target.setLevel(logging.WARNING)
        else:
            target.setLevel(level)

    logging.captureWarnings(True)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("aiobotocore").setLevel(logging.WARNING)

    _CONFIGURED_SIGNATURE = signature
