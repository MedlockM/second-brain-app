#!/usr/bin/env python3
"""Delete a single E2E test account and all its data from DynamoDB.

This script is the per-account complement to purge_e2e_accounts.py. It is
designed to be called from test teardowns (tests/e2e/conftest.py) and CI
cleanup steps (.github/workflows/mobile-e2e-maestro.yml), where the email is
known up front.

Selection is deliberately conservative:
1. the email must end with `@test.local` (no real account can);
2. the local part must start with one of `E2E_EMAIL_PREFIXES`;
3. the email must not be in `PROTECTED_EMAILS`.

If the email does not meet these criteria, or if the account does not exist, the
script exits 0 and prints a notice. This allows teardowns to be unconditional:
they never fail the test or CI run.

The script sweeps BOTH the `-dev` tables and the unsuffixed legacy tables (until
task-237 removes them). The deletion order is children first, then the `users`
row, so no orphan can survive a partial run.

Usage:
    scripts/delete_e2e_account.py e2e-test-12345@test.local
    scripts/delete_e2e_account.py --region eu-west-3 e2e-register-67890@test.local

Environment:
    AWS credentials are read from the environment (SDK default chain).
    Required env vars: none (region defaults to eu-west-3).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import boto3

# Add scripts directory to sys.path so we can import from purge_e2e_accounts.py
_scripts_dir = Path(__file__).resolve().parent
if str(_scripts_dir) not in sys.path:
    sys.path.insert(0, str(_scripts_dir))

# Import shared selection rules and table topology from purge_e2e_accounts.py
# to avoid drift. When a child table is added there, this script picks it up
# automatically.
from purge_e2e_accounts import (
    ALLOWED_SUFFIXES,
    E2E_EMAIL_DOMAIN,
    E2E_EMAIL_PREFIXES,
    PROTECTED_EMAILS,
    REGION,
    collect_children,
    delete_children,
    is_purgeable,
    query_items,
)


def find_user_by_email(
    client: Any, suffix: str, email: str
) -> dict[str, Any] | None:
    """Return the user row for `email` in `users{suffix}`, or None if not found."""
    table = f"users{suffix}"
    rows = query_items(client, table, "email", email, index="email-index")
    return rows[0] if rows else None


def delete_account(client: Any, suffix: str, email: str) -> bool:
    """Delete the account and all its data from `users{suffix}` and child tables.

    Returns True if the account was found and deleted, False if it didn't exist.
    """
    user = find_user_by_email(client, suffix, email)
    if not user:
        return False

    user_id = user["id"]["S"]
    children = collect_children(client, suffix, user_id)
    deleted_children = delete_children(client, suffix, children)

    # Delete the user row last.
    client.delete_item(TableName=f"users{suffix}", Key={"id": {"S": user_id}})

    print(
        f"[delete-e2e-account] deleted {email} ({user_id}) from users{suffix} "
        f"and {deleted_children} child rows"
    )
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="email address of the account to delete")
    parser.add_argument("--region", default=REGION)
    args = parser.parse_args(argv)

    email = args.email.strip().lower()

    # Safety check: only delete purgeable accounts.
    if not is_purgeable(email):
        if email in PROTECTED_EMAILS:
            print(
                f"[delete-e2e-account] SKIP {email}: protected account",
                file=sys.stderr,
            )
        elif not email.endswith(E2E_EMAIL_DOMAIN):
            print(
                f"[delete-e2e-account] SKIP {email}: not a @test.local address",
                file=sys.stderr,
            )
        else:
            print(
                f"[delete-e2e-account] SKIP {email}: prefix does not match "
                f"{E2E_EMAIL_PREFIXES}",
                file=sys.stderr,
            )
        return 0

    client = boto3.client("dynamodb", region_name=args.region)
    found_any = False

    # Sweep both -dev and the unsuffixed legacy tables.
    for suffix in ALLOWED_SUFFIXES:
        found = delete_account(client, suffix, email)
        found_any = found_any or found

    if not found_any:
        print(f"[delete-e2e-account] account {email} not found in any table")

    return 0


if __name__ == "__main__":
    sys.exit(main())
