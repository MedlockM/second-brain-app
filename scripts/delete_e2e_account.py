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
from typing import Any

import boto3

# --- Selection rules (must match purge_e2e_accounts.py) -------------------

#: Accounts that must survive every purge, whatever the prefix rules say.
PROTECTED_EMAILS = frozenset(
    {
        "e2e-maestro-20260809200952@test.local",
    }
)

#: Local-part prefixes of throwaway accounts created by test tooling.
E2E_EMAIL_PREFIXES = ("e2e-register-", "e2e-test-", "phase4-test-")

#: No real user can hold an address in this domain.
E2E_EMAIL_DOMAIN = "@test.local"

#: Environments this script is allowed to address. Staging and prod are not
#: listed on purpose: a typo must not be able to reach them.
ALLOWED_SUFFIXES = ("-dev", "")

REGION = "eu-west-3"


def is_purgeable(email: str | None) -> bool:
    """True when `email` belongs to a throwaway E2E account safe to delete."""
    if not email:
        return False
    candidate = email.strip().lower()
    if candidate in PROTECTED_EMAILS:
        return False
    if not candidate.endswith(E2E_EMAIL_DOMAIN):
        return False
    local_part = candidate[: -len(E2E_EMAIL_DOMAIN)]
    return local_part.startswith(E2E_EMAIL_PREFIXES)


# --- Table topology (must match purge_e2e_accounts.py) --------------------

#: (base name, how to find the rows of a user, primary-key attributes)
#: mode "gsi": query the `user-index` GSI on user_id
#: mode "pk" : query the base table, user_id is the partition key
CHILD_TABLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("auth_tokens", "gsi", ("id",)),
    ("processing_jobs", "gsi", ("id",)),
    ("user_tags", "gsi", ("id",)),
    ("user_folders", "gsi", ("id",)),
    ("user_media_submissions", "pk", ("user_id", "media_key")),
    ("user_usage_monthly", "pk", ("user_id", "period")),
)

#: media_artifacts carries no user_id: rows are reached through the
#: `media-item-index` GSI, keyed by the processing job id of the media item.
ARTIFACTS_TABLE = "media_artifacts"
ARTIFACTS_INDEX = "media-item-index"
ARTIFACTS_KEY = ("artifact_id",)


def query_items(
    client: Any,
    table: str,
    attribute: str,
    value: str,
    index: str | None = None,
) -> list[dict[str, Any]]:
    """Return every row of `table` (or of `index`) where `attribute` = `value`."""
    kwargs: dict[str, Any] = {
        "TableName": table,
        "KeyConditionExpression": "#a = :v",
        "ExpressionAttributeNames": {"#a": attribute},
        "ExpressionAttributeValues": {":v": {"S": value}},
    }
    if index:
        kwargs["IndexName"] = index
    items: list[dict[str, Any]] = []
    while True:
        response = client.query(**kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return items
        kwargs["ExclusiveStartKey"] = last_key


def find_user_by_email(
    client: Any, suffix: str, email: str
) -> dict[str, Any] | None:
    """Return the user row for `email` in `users{suffix}`, or None if not found."""
    table = f"users{suffix}"
    rows = query_items(client, table, "email", email, index="email-index")
    return rows[0] if rows else None


def collect_children(
    client: Any, suffix: str, user_id: str
) -> dict[str, list[dict[str, Any]]]:
    """Return every child row owned by `user_id`, keyed by physical table name."""
    children: dict[str, list[dict[str, Any]]] = {}

    for base, mode, _keys in CHILD_TABLES:
        table = f"{base}{suffix}"
        if mode == "gsi":
            rows = query_items(client, table, "user_id", user_id, index="user-index")
        else:
            rows = query_items(client, table, "user_id", user_id)
        if rows:
            children[table] = rows

    # Artifacts hang off the media items, i.e. off the processing jobs.
    jobs = children.get(f"processing_jobs{suffix}", [])
    artifacts: list[dict[str, Any]] = []
    for job in jobs:
        media_item_id = job.get("id", {}).get("S")
        if not media_item_id:
            continue
        artifacts.extend(
            query_items(
                client,
                f"{ARTIFACTS_TABLE}{suffix}",
                "media_item_id",
                media_item_id,
                index=ARTIFACTS_INDEX,
            )
        )
    if artifacts:
        children[f"{ARTIFACTS_TABLE}{suffix}"] = artifacts

    return children


def key_of(item: dict[str, Any], attributes: tuple[str, ...]) -> dict[str, Any]:
    return {name: item[name] for name in attributes}


def key_attributes_for(table: str, suffix: str) -> tuple[str, ...]:
    if table == f"{ARTIFACTS_TABLE}{suffix}":
        return ARTIFACTS_KEY
    for base, _mode, keys in CHILD_TABLES:
        if table == f"{base}{suffix}":
            return keys
    raise KeyError(f"no primary key known for table {table}")


def delete_children(
    client: Any, suffix: str, children: dict[str, list[dict[str, Any]]]
) -> int:
    """Delete every collected child row. Children first, always."""
    deleted = 0
    for table, rows in children.items():
        attributes = key_attributes_for(table, suffix)
        for row in rows:
            client.delete_item(TableName=table, Key=key_of(row, attributes))
            deleted += 1
    return deleted


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
