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

handler = Mangum(app, lifespan="off")
