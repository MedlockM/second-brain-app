"""Strict environment-variable access for AWS resource names.

Every DynamoDB table, SQS queue and S3 bucket name used to be read as
``os.environ.get("USERS_TABLE", "users")``. The hardcoded fallback was the name
of the *dev* resource, so a Lambda deployed with a missing or misspelled
environment variable silently read and wrote dev data instead of failing.

With one environment that was merely fragile. With ``dev``, ``staging`` and
``prod`` sharing an AWS account (task-237) it is a cross-environment data
corruption bug waiting to happen: a staging worker missing ``USERS_TABLE``
would have written straight into the dev ``users`` table, and a prod worker
would have read dev summaries.

Resource names therefore have no defaults any more. Terraform injects all of
them from ``infrastructure/terraform/modules/platform/runtime_env.tf``, which
is the single source of truth, and this module makes a missing one an immediate,
loud failure.
"""

from __future__ import annotations

import os

__all__ = ["required_env"]


def required_env(name: str) -> str:
    """Return the value of ``name``, raising if it is unset or blank.

    Args:
        name: Environment variable holding an AWS resource name.

    Raises:
        RuntimeError: The variable is unset or empty. There is deliberately no
            fallback: guessing a resource name is how one environment ends up
            writing into another's tables.
    """
    value = os.environ.get(name)
    if value is None or not value.strip():
        raise RuntimeError(
            f"Required environment variable {name} is not set. AWS resource "
            f"names are environment-specific and have no default. Terraform "
            f"injects them from infrastructure/terraform/modules/platform/"
            f"runtime_env.tf; for local runs copy the value from .env.example."
        )
    return value.strip()
