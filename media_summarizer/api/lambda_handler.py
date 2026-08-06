"""
AWS Lambda handler for the FastAPI API via Mangum ASGI adapter.

This module is the CMD entrypoint for the API Lambda container image.
It loads runtime secrets from Secrets Manager at init time (cold start)
and exposes a `handler` callable for Lambda to invoke.
"""

import json
import os

import boto3

# Load secrets from Secrets Manager at module level (runs once per cold start).
# This injects all keys from the consolidated secret as environment variables
# so the existing os.getenv(...) pattern throughout the codebase works unchanged.
_secret_name = os.environ.get("RUNTIME_SECRET_NAME", "")
if _secret_name:
    _client = boto3.client("secretsmanager")
    _resp = _client.get_secret_value(SecretId=_secret_name)
    _secrets = json.loads(_resp["SecretString"])
    for _key, _value in _secrets.items():
        os.environ.setdefault(_key, str(_value))

# Import the app after secrets are loaded so config reads see the env vars.
from mangum import Mangum  # noqa: E402

from media_summarizer.api.main import app  # noqa: E402

_asgi_handler = Mangum(app, lifespan="off")
_WARMUP_SOURCE = "media-summarizer.api-warmup"
_HEALTH_PATH = "/api/v1/health/"


def _health_check_event() -> dict:
    """Build the same API Gateway v2 event shape used by public requests."""
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": _HEALTH_PATH,
        "rawQueryString": "",
        "headers": {},
        "requestContext": {
            "http": {
                "method": "GET",
                "path": _HEALTH_PATH,
                "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1",
            },
            "requestId": "scheduled-api-health-check",
            "routeKey": "$default",
            "stage": "$default",
        },
        "isBase64Encoded": False,
    }


def _run_scheduled_health_check(context):
    """Warm the API and fail the invocation when its health route is unhealthy."""
    response = _asgi_handler(_health_check_event(), context)
    status_code = int(response.get("statusCode", 500))
    try:
        body = json.loads(response.get("body") or "{}")
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("API warm-up returned a non-JSON health response") from exc

    if status_code != 200 or body.get("status") != "healthy":
        raise RuntimeError(
            f"API warm-up health check failed: status_code={status_code}, "
            f"health_status={body.get('status', 'missing')}"
        )
    return response


def handler(event, context):
    """Dispatch API Gateway requests and validate scheduled warm invocations."""
    if event.get("source") == _WARMUP_SOURCE:
        return _run_scheduled_health_check(context)
    return _asgi_handler(event, context)
