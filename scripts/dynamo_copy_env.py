#!/usr/bin/env python3
"""Copy every item of one DynamoDB table into another, in the same account.

Used by step 4 of the dev rename runbook (see infrastructure/terraform/README.md
and docs/research/task-221-terraform-multi-env-isolation/README.md §5.3): the
DynamoDB API has no rename operation and `aws_dynamodb_table.name` is ForceNew,
so the only non-destructive way to move `users` to `users-dev` is to create the
new table, copy the items across, and delete the old table after a soak period.

The script NEVER deletes anything and NEVER touches Terraform state. The source
table is only ever read.

Usage:
    scripts/dynamo_copy_env.py --from users --to users-dev
    scripts/dynamo_copy_env.py --from users --to users-dev --dry-run
    scripts/dynamo_copy_env.py --manifest tables.txt --suffix=-dev

    # tables.txt is one legacy table name per line; --suffix builds the target.
    # Note the `=` in --suffix=-dev: a value starting with "-" is otherwise read
    # as another flag.

Verification (do NOT trust DescribeTable.ItemCount, it lags by ~6 hours):
    aws dynamodb scan --table-name users-dev --select COUNT
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any, Iterator

import boto3
from botocore.exceptions import ClientError

BATCH_SIZE = 25  # BatchWriteItem hard limit
MAX_RETRIES = 8


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


def chunked(items: list[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def write_batch(client: Any, table: str, batch: list[dict[str, Any]]) -> int:
    """Write one batch, retrying unprocessed items with exponential backoff."""
    request = {table: [{"PutRequest": {"Item": item}} for item in batch]}
    written = len(batch)
    attempt = 0

    while request:
        response = client.batch_write_item(RequestItems=request)
        unprocessed = response.get("UnprocessedItems") or {}
        if not unprocessed:
            return written

        attempt += 1
        if attempt > MAX_RETRIES:
            remaining = len(unprocessed.get(table, []))
            raise RuntimeError(
                f"{remaining} item(s) still unprocessed for {table} after "
                f"{MAX_RETRIES} retries; re-run the script (PutItem is idempotent "
                f"on the primary key, so a re-run is safe)."
            )
        time.sleep(min(2**attempt * 0.05, 5.0))
        request = unprocessed

    return written


def table_exists(client: Any, table: str) -> bool:
    try:
        client.describe_table(TableName=table)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceNotFoundException":
            return False
        raise


def copy_table(client: Any, source: str, target: str, *, dry_run: bool) -> int:
    if source == target:
        raise ValueError(f"source and target are identical: {source}")
    if not table_exists(client, source):
        raise RuntimeError(f"source table does not exist: {source}")
    if not dry_run and not table_exists(client, target):
        raise RuntimeError(
            f"target table does not exist: {target}. Run `terraform apply` in the "
            f"environment root first — this script never creates tables."
        )

    print(f"  {source} -> {target}")
    items = list(scan_items(client, source))
    print(f"    scanned {len(items)} item(s)")

    if dry_run:
        print("    dry-run: nothing written")
        return len(items)

    written = 0
    for batch in chunked(items, BATCH_SIZE):
        written += write_batch(client, target, batch)
    print(f"    wrote {written} item(s)")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="source", help="Source (legacy) table name")
    parser.add_argument("--to", dest="target", help="Target (suffixed) table name")
    parser.add_argument(
        "--manifest",
        help="File with one legacy table name per line; combine with --suffix",
    )
    parser.add_argument(
        "--suffix",
        help="Suffix appended to each manifest entry to build the target name (e.g. -dev)",
    )
    parser.add_argument("--region", default=None, help="AWS region (defaults to the CLI/env config)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and report counts without writing anything",
    )
    args = parser.parse_args()

    pairs: list[tuple[str, str]] = []
    if args.manifest:
        if not args.suffix:
            parser.error("--manifest requires --suffix")
        with open(args.manifest, encoding="utf-8") as handle:
            for line in handle:
                name = line.strip()
                if not name or name.startswith("#"):
                    continue
                pairs.append((name, f"{name}{args.suffix}"))
    elif args.source and args.target:
        pairs.append((args.source, args.target))
    else:
        parser.error("provide either --from/--to or --manifest/--suffix")

    client = boto3.client("dynamodb", region_name=args.region)

    print(f"Copying {len(pairs)} table(s){' (DRY RUN)' if args.dry_run else ''}:")
    total = 0
    failures: list[str] = []
    for source, target in pairs:
        try:
            total += copy_table(client, source, target, dry_run=args.dry_run)
        except Exception as exc:  # noqa: BLE001 — report and continue
            print(f"    ERROR: {exc}", file=sys.stderr)
            failures.append(source)

    print(f"\nTotal items handled: {total}")
    if failures:
        print(f"FAILED tables: {', '.join(failures)}", file=sys.stderr)
        return 1

    print(
        "\nVerify each target with a full scan (DescribeTable.ItemCount lags ~6h):\n"
        "  aws dynamodb scan --table-name <target> --select COUNT"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
