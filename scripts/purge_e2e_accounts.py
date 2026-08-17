#!/usr/bin/env python3
"""Purge orphaned E2E accounts and every row they own from DynamoDB.

Why this script exists: `database_async.delete_user()` deletes only the `users`
row, so every E2E run since June 2026 left its auth tokens, processing jobs,
artifacts, tags, folders, submissions and usage counters behind (task-246).
This script deletes the children FIRST, then the `users` row, so no orphan can
survive a partial run.

Selection is deliberately conservative and layered:

1. the email must end with `@test.local` (no real account can);
2. the local part must start with `e2e-` or `phase4-test-`;
3. the email must not be in `PROTECTED_EMAILS` -- an explicit exclusion list,
   checked before any prefix logic, that holds the permanent Maestro account
   designated by the `E2E_TEST_USER_EMAIL` secret.

Anything else is reported as kept and never touched.

Safety:
- dry run by default; `--apply` is required to delete anything;
- only the `-dev` and the unsuffixed legacy tables are reachable
  (`ALLOWED_SUFFIXES`) -- staging and prod cannot be addressed at all;
- every row that is about to be deleted is dumped to a JSON file first, in the
  low-level DynamoDB format, so `aws dynamodb put-item --item ...` restores it
  by hand. The unsuffixed `users` table has no PITR: the dump is its only net.

Usage:
    scripts/purge_e2e_accounts.py                      # dry run on -dev
    scripts/purge_e2e_accounts.py --apply              # purge -dev
    scripts/purge_e2e_accounts.py --suffix=            # dry run on legacy
    scripts/purge_e2e_accounts.py --suffix= --apply    # purge legacy

    # Note the `=` in `--suffix=-dev`: a value starting with "-" would
    # otherwise be read as another flag.

Verification (do NOT trust DescribeTable.ItemCount, it lags by ~6 hours):
    aws dynamodb scan --table-name users-dev --select COUNT
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import boto3

# --- Selection rules -------------------------------------------------------

#: Accounts that must survive every purge, whatever the prefix rules say.
#: `e2e-maestro-20260809200952@test.local` is the permanent account of the
#: `E2E_TEST_USER_EMAIL` secret; the six Maestro flows all log in with it.
PROTECTED_EMAILS = frozenset(
    {
        "e2e-maestro-20260809200952@test.local",
    }
)

#: Local-part prefixes of throwaway accounts created by test tooling:
#: - `e2e-*` : any account starting with `e2e-` (covers register, test, and ad-hoc
#:   task-specific accounts like `e2e-task249-`); using a wildcard because
#:   enumerating prefixes made ad-hoc accounts escape (task-259)
#: - `phase4-test-` : the historical Phase 4 validation script
E2E_EMAIL_PREFIXES = ("e2e-", "phase4-test-")

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


def select_accounts(
    users: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split raw `users` rows into (to_purge, to_keep), preserving order."""
    to_purge: list[dict[str, Any]] = []
    to_keep: list[dict[str, Any]] = []
    for item in users:
        email = item.get("email", {}).get("S")
        (to_purge if is_purgeable(email) else to_keep).append(item)
    return to_purge, to_keep


# --- Table topology --------------------------------------------------------
# Mirrors the teardown of tests/e2e/conftest.py, but exhaustively and by
# user_id instead of by API response.

#: (base name, how to find the rows of a user, primary-key attributes)
#: mode "gsi": query the `user-index` GSI on user_id
#: mode "pk" : query the base table, user_id is the partition key
CHILD_TABLES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("auth_tokens", "gsi", ("id",)),
    ("processing_jobs", "gsi", ("id",)),
    ("user_tags", "gsi", ("id",)),
    ("user_folders", "gsi", ("id",)),
    ("user_usage_monthly", "pk", ("user_id", "period")),
)

#: media_artifacts rows are reached through the `scope-index` GSI, whose hash key
#: is `user_id#scope#scope_id` — so both a media's artifacts and a collection's
#: are collected for one user without touching the processing jobs (task-270).
ARTIFACTS_TABLE = "media_artifacts"
ARTIFACTS_INDEX = "scope-index"
ARTIFACTS_KEY = ("artifact_id",)


def scan_items(client: Any, table: str) -> Iterator[dict[str, Any]]:
    """Yield every item of `table` as a low-level (typed) DynamoDB dict."""
    kwargs: dict[str, Any] = {"TableName": table}
    while True:
        response = client.scan(**kwargs)
        yield from response.get("Items", [])
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return
        kwargs["ExclusiveStartKey"] = last_key


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

    # Artifacts hang off a scope: every media item of the user, plus every folder
    # of the user (a collection artifact belongs to no media item at all).
    scope_keys = [
        f"{user_id}#media#{job.get('id', {}).get('S')}"
        for job in children.get(f"processing_jobs{suffix}", [])
        if job.get("id", {}).get("S")
    ] + [
        f"{user_id}#folder#{folder.get('id', {}).get('S')}"
        for folder in children.get(f"user_folders{suffix}", [])
        if folder.get("id", {}).get("S")
    ]
    artifacts: list[dict[str, Any]] = []
    for scope_key in scope_keys:
        artifacts.extend(
            query_items(
                client,
                f"{ARTIFACTS_TABLE}{suffix}",
                "scope_key",
                scope_key,
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


def write_dump(dump_dir: Path, suffix: str, payload: dict[str, Any]) -> Path:
    dump_dir.mkdir(parents=True, exist_ok=True)
    label = suffix.lstrip("-") or "legacy"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = dump_dir / f"purge-e2e-{label}-{stamp}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suffix",
        default="-dev",
        help=(
            "environment suffix of the tables to sweep: '-dev' (default) or "
            "'' for the unsuffixed legacy tables. Pass as --suffix=-dev."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually delete. Without it the script only reports (dry run).",
    )
    parser.add_argument("--region", default=REGION)
    parser.add_argument(
        "--dump-dir",
        default="tmp/purge-e2e-dumps",
        help="where the pre-deletion JSON dump is written (gitignored).",
    )
    args = parser.parse_args(argv)

    if args.suffix not in ALLOWED_SUFFIXES:
        parser.error(
            f"--suffix must be one of {ALLOWED_SUFFIXES!r} "
            "(staging and prod are out of scope)"
        )

    suffix = args.suffix
    users_table = f"users{suffix}"
    client = boto3.client("dynamodb", region_name=args.region)

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"[purge] {mode} on {users_table} ({args.region})")

    users = list(scan_items(client, users_table))
    to_purge, to_keep = select_accounts(users)
    print(
        f"[purge] {len(users)} accounts: {len(to_purge)} selected, {len(to_keep)} kept"
    )

    for item in to_keep:
        print(f"[purge]   KEEP {item.get('email', {}).get('S')}")

    dump: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "region": args.region,
        "users_table": users_table,
        "applied": args.apply,
        "kept": [item.get("email", {}).get("S") for item in to_keep],
        "accounts": [],
    }

    total_children = 0
    for item in to_purge:
        user_id = item["id"]["S"]
        email = item.get("email", {}).get("S")
        children = collect_children(client, suffix, user_id)
        counts = {table: len(rows) for table, rows in children.items()}
        total_children += sum(counts.values())
        print(f"[purge]   DELETE {email} ({user_id}) children={counts}")
        dump["accounts"].append(
            {
                "email": email,
                "user_id": user_id,
                "user_row": item,
                "children": children,
            }
        )

    dump["total_children"] = total_children
    dump_path = write_dump(Path(args.dump_dir), suffix, dump)
    print(f"[purge] dump written to {dump_path}")

    if not to_purge:
        print("[purge] nothing to delete")
        return 0

    if not args.apply:
        print(
            f"[purge] dry run: would delete {total_children} child rows and "
            f"{len(to_purge)} accounts. Re-run with --apply."
        )
        return 0

    deleted_children = 0
    deleted_users = 0
    for account in dump["accounts"]:
        deleted_children += delete_children(client, suffix, account["children"])
        client.delete_item(TableName=users_table, Key={"id": {"S": account["user_id"]}})
        deleted_users += 1
        print(f"[purge]   deleted {account['email']}")

    print(f"[purge] deleted {deleted_children} child rows and {deleted_users} accounts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
