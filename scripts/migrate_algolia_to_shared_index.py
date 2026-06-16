#!/usr/bin/env python3
"""
Migration script: per-user Algolia indices -> single shared index.

Iterates over all per-user indices in the Algolia app (matching the pattern
``{prefix}_user_*``), copies each record into the shared index with a
``user_id`` attribute extracted from the index name, then deletes the old
per-user index.

Usage:
    # Dry-run (read-only, logs what would be done):
    python scripts/migrate_algolia_to_shared_index.py --dry-run

    # Apply (performs the migration):
    python scripts/migrate_algolia_to_shared_index.py --apply

Environment variables required:
    ALGOLIA_APP_ID: Algolia Application ID
    ALGOLIA_API_KEY: Algolia Admin API key
    ENVIRONMENT: Target environment (development, staging, production)
    ALGOLIA_INDEX_PREFIX: (optional) Prefix used for old per-user indices (default: "transcripts")

The script is idempotent and resumable: records are saved with deterministic
objectIDs so re-running won't create duplicates. Already-migrated indices
(that have been deleted) are simply skipped.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algoliasearch.search.client import SearchClientSync  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Pattern for per-user index names: {prefix}_user_{user_id}
_USER_INDEX_PATTERN = re.compile(r"^(.+)_user_(.+)$")


def get_algolia_client() -> SearchClientSync:
    """Create an Algolia client from environment variables."""
    app_id = os.environ.get("ALGOLIA_APP_ID", "").strip()
    api_key = os.environ.get("ALGOLIA_API_KEY", "").strip()

    if not app_id or not api_key:
        logger.error("ALGOLIA_APP_ID and ALGOLIA_API_KEY must be set")
        sys.exit(1)

    return SearchClientSync(app_id, api_key)


def get_shared_index_name() -> str:
    """Return the target shared index name."""
    env = os.environ.get("ENVIRONMENT", "development").strip()
    return f"media_items_{env}"


def list_per_user_indices(client: SearchClientSync, prefix: str) -> list:
    """List all per-user indices matching the prefix pattern."""
    response = client.list_indices()
    indices = []

    items = response.items if hasattr(response, "items") else []
    for idx in items:
        name = idx.name if hasattr(idx, "name") else idx.get("name", "")
        match = _USER_INDEX_PATTERN.match(name)
        if match and match.group(1) == prefix:
            user_id = match.group(2)
            entries = idx.entries if hasattr(idx, "entries") else idx.get("entries", 0)
            indices.append({
                "index_name": name,
                "user_id": user_id,
                "entries": entries,
            })

    return indices


def browse_all_records(client: SearchClientSync, index_name: str) -> list:
    """Browse all records from an index using the browse API."""
    records = []
    try:
        results = client.browse_objects(
            index_name=index_name,
            browse_params={"query": ""},
        )
        for hit in results:
            if isinstance(hit, dict):
                records.append(hit)
            else:
                records.append(hit.to_dict() if hasattr(hit, "to_dict") else {})
    except Exception as e:
        logger.error(f"Failed to browse index '{index_name}': {e}")
    return records


def migrate_index(
    client: SearchClientSync,
    source_index: str,
    user_id: str,
    target_index: str,
    dry_run: bool,
) -> int:
    """
    Migrate records from a per-user index to the shared index.

    Adds user_id to each record. Returns number of records migrated.
    """
    records = browse_all_records(client, source_index)
    if not records:
        logger.info(f"  No records found in '{source_index}', skipping")
        return 0

    # Add user_id to each record
    enriched = []
    for record in records:
        record["user_id"] = user_id
        enriched.append(record)

    if dry_run:
        logger.info(
            f"  [DRY-RUN] Would copy {len(enriched)} records from "
            f"'{source_index}' to '{target_index}' with user_id='{user_id}'"
        )
        return len(enriched)

    # Save to shared index in batches of 1000
    batch_size = 1000
    for i in range(0, len(enriched), batch_size):
        batch = enriched[i : i + batch_size]
        client.save_objects(index_name=target_index, objects=batch)
        logger.info(
            f"  Saved batch {i // batch_size + 1} "
            f"({len(batch)} records) to '{target_index}'"
        )

    logger.info(
        f"  Migrated {len(enriched)} records from '{source_index}' to '{target_index}'"
    )
    return len(enriched)


def delete_old_index(
    client: SearchClientSync, index_name: str, dry_run: bool
) -> None:
    """Delete the old per-user index."""
    if dry_run:
        logger.info(f"  [DRY-RUN] Would delete index '{index_name}'")
        return

    try:
        client.delete_index(index_name=index_name)
        logger.info(f"  Deleted index '{index_name}'")
    except Exception as e:
        logger.error(f"  Failed to delete index '{index_name}': {e}")


def configure_shared_index_settings(
    client: SearchClientSync, index_name: str, dry_run: bool
) -> None:
    """Configure the shared index settings for multi-tenant search."""
    settings = {
        "searchableAttributes": [
            "title",
            "transcript",
        ],
        "attributesForFaceting": [
            "filterOnly(user_id)",
            "filterOnly(media_item_id)",
            "filterOnly(source_platform)",
        ],
        "unretrievableAttributes": [
            "user_id",
        ],
        "attributesToRetrieve": [
            "media_item_id",
            "title",
            "source_platform",
            "created_at",
            "chunk_index",
            "transcript",
        ],
        "ranking": [
            "typo",
            "geo",
            "words",
            "filters",
            "proximity",
            "attribute",
            "exact",
            "custom",
        ],
    }

    if dry_run:
        logger.info(f"[DRY-RUN] Would configure settings on '{index_name}'")
        return

    client.set_settings(index_name=index_name, index_settings=settings)
    logger.info(f"Configured settings on shared index '{index_name}'")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate per-user Algolia indices to a single shared index."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Read-only: log what would be done without making changes.",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Execute the migration (copy records, delete old indices).",
    )
    parser.add_argument(
        "--prefix",
        default=os.environ.get("ALGOLIA_INDEX_PREFIX", "transcripts"),
        help="Old per-user index prefix (default: ALGOLIA_INDEX_PREFIX or 'transcripts').",
    )

    args = parser.parse_args()
    dry_run = args.dry_run

    if dry_run:
        logger.info("=== DRY-RUN MODE (no changes will be made) ===")
    else:
        logger.info("=== APPLY MODE (changes will be written) ===")

    client = get_algolia_client()
    target_index = get_shared_index_name()

    logger.info(f"Target shared index: {target_index}")
    logger.info(f"Looking for per-user indices with prefix: {args.prefix}")

    # List all per-user indices
    per_user_indices = list_per_user_indices(client, args.prefix)

    if not per_user_indices:
        logger.info("No per-user indices found. Nothing to migrate.")
        return

    logger.info(f"Found {len(per_user_indices)} per-user indices to migrate:")
    for idx in per_user_indices:
        logger.info(
            f"  - {idx['index_name']} (user_id={idx['user_id']}, "
            f"entries={idx['entries']})"
        )

    # Configure shared index settings first
    configure_shared_index_settings(client, target_index, dry_run)

    # Migrate each index
    total_records = 0
    migrated_count = 0
    failed_count = 0

    for idx in per_user_indices:
        logger.info(f"\nMigrating: {idx['index_name']} (user_id={idx['user_id']})")
        try:
            count = migrate_index(
                client=client,
                source_index=idx["index_name"],
                user_id=idx["user_id"],
                target_index=target_index,
                dry_run=dry_run,
            )
            total_records += count

            if count > 0 or idx["entries"] == 0:
                delete_old_index(client, idx["index_name"], dry_run)
                migrated_count += 1
            else:
                logger.warning(
                    f"  Skipped deletion of '{idx['index_name']}' "
                    f"(no records migrated but index reports {idx['entries']} entries)"
                )
                failed_count += 1

        except Exception as e:
            logger.error(f"  FAILED to migrate '{idx['index_name']}': {e}")
            failed_count += 1

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("MIGRATION SUMMARY")
    logger.info(f"  Indices processed: {len(per_user_indices)}")
    logger.info(f"  Indices migrated:  {migrated_count}")
    logger.info(f"  Indices failed:    {failed_count}")
    logger.info(f"  Total records:     {total_records}")
    logger.info(f"  Target index:      {target_index}")
    if dry_run:
        logger.info("  Mode: DRY-RUN (no changes made)")
    else:
        logger.info("  Mode: APPLY (changes committed)")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
