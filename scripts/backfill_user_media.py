#!/usr/bin/env python3
"""Reconstruct the durable ``user_media`` library from every surviving source.

Phase 2 of the task-218 benchmark (§5.3), task-241. The library used to live on
``processing_jobs``, a TTL table, so every successfully processed media was
deleted 30 days after ingestion together with its title, source, folder and
ownership. Phase 0 froze the TTL and Phase 1 (task-240) created the durable
``user_media`` table; this script rebuilds the rows that were already lost.

Recovery is *reconstructive*, not a restore: the stream archiver was a no-op
placeholder and PITR was disabled, so the deleted rows are gone. What survives is
scattered across five stores, and this script merges them in **descending order of
richness** — a later source never overwrites a field an earlier one already set:

    1  processing_jobs           title, source, folder_id, tag_ids, status, owner
    2  user_media_submissions    owner + media_key + submitted_at, even when the
                                 job it points at has been deleted
       (media_idempotence)       auxiliary index ONLY: recovers the media_key of a
                                 dangling job id. It holds no user_id, so it can
                                 never establish ownership.
    3  media_artifacts           which media_item_ids have surviving content
    4  Algolia                   often the only surviving copy of the title, plus
                                 user_id and media_item_id
    5  S3 key prefixes           last-resort existence proof

Four rules from the benchmark are load-bearing and implemented literally:

- **Legacy ids are preserved.** A reconstructed row keeps the ``media_item_id``
  that the artifacts, the Algolia ``objectID``s (``{media_item_id}_chunk_{i}``),
  the mobile caches and the deep links already use. Nothing is rewritten outside
  ``user_media``; only *new* saves use the deterministic ``mi_`` id, and mixing
  both formats is safe because the id is opaque.
- **Dangling submissions are superseded, not repaired.** A submission whose job is
  gone becomes a library row keyed by the artifact-derived id when one exists,
  otherwise by the deterministic id, with ``last_job_id`` left null.
- **Unresolvable rows are quarantined, never guessed.** Ownership is never
  inferred from the fact that dev has one real user. Everything unresolvable goes
  to a report for manual owner review.
- **Nothing outside user_media and media_idempotence is ever written.**
  ``processing_jobs``, ``media_artifacts`` and S3 are opened read-only: this
  script contains no put/update/delete call against any of them.

Idempotence: rows are created with a conditional ``PutItem`` and enriched with an
attribute-level ``UpdateItem`` that only fills attributes that are *missing*. A
second run therefore converges to no-ops and can never create a duplicate,
because candidates are keyed by ``(user_id, media_key)`` and an existing row for
that pair is reused whatever its id.

Rollback: rows created here carry ``backfilled_from``; delete exactly those.
Rows that already existed and were only enriched carry ``backfill_enriched_from``
instead — deliberately a different attribute, so a rollback cannot delete a row a
real user save created.

Usage:
    scripts/backfill_user_media.py                    # dry run on -dev
    scripts/backfill_user_media.py --dry-run          # same, explicit
    scripts/backfill_user_media.py --apply            # write
    scripts/backfill_user_media.py --user-id <uuid>   # one account only
    scripts/backfill_user_media.py --no-algolia       # skip source 4
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from media_summarizer.core.models.processing_job import JobStatus  # noqa: E402
from media_summarizer.core.models.user_media import (  # noqa: E402
    UserMediaRecord,
    UserMediaStatus,
    build_folder_sort_key,
    build_media_item_id,
)

REGION = "eu-west-3"

#: Environments this script may address. prod is absent on purpose: it does not
#: exist yet, and a typo must not be able to reach it.
ALLOWED_SUFFIXES = ("-dev", "-staging")

# --- Source labels, in descending order of richness (§5.3) ------------------

SRC_JOBS = "processing_jobs"
SRC_SUBMISSIONS = "user_media_submissions"
SRC_IDEMPOTENCE = "media_idempotence"
SRC_ARTIFACTS = "media_artifacts"
SRC_ALGOLIA = "algolia"
SRC_S3 = "s3"

SOURCE_ORDER = (
    SRC_JOBS,
    SRC_SUBMISSIONS,
    SRC_IDEMPOTENCE,
    SRC_ARTIFACTS,
    SRC_ALGOLIA,
    SRC_S3,
)

#: Same projection as ``durable_media_service._JOB_STATUS_TO_LIBRARY_STATUS``.
#: Duplicated rather than imported because that module pulls in the async
#: database layer, which resolves a dozen table names at import time.
JOB_STATUS_TO_LIBRARY_STATUS = {
    JobStatus.PENDING.value: UserMediaStatus.PENDING,
    JobStatus.EXTRACTING.value: UserMediaStatus.PROCESSING,
    JobStatus.TRANSCRIBING.value: UserMediaStatus.PROCESSING,
    JobStatus.SUMMARIZING.value: UserMediaStatus.PROCESSING,
    JobStatus.COMPLETED.value: UserMediaStatus.READY,
    JobStatus.FAILED.value: UserMediaStatus.FAILED,
    JobStatus.CANCELLED.value: UserMediaStatus.FAILED,
}

#: Buckets scanned for source 5. The base names mirror
#: ``infrastructure/terraform/modules/platform/runtime_env.tf``.
S3_BUCKET_BASENAMES = (
    "transcripts",
    "summaries",
    "summary-short",
    "summary-detailed",
    "notes",
    "flashcards",
    "quiz",
    "documents",
    "audio",
)

#: The bucket whose objects prove the *transcript* survived. Everything
#: downstream can be regenerated from it, so its presence is what makes an
#: idempotence row legitimately "processed".
TRANSCRIPT_BUCKET_BASENAME = "transcripts"

#: Key prefixes in the artifact buckets that are not named after a media item.
NON_MEDIA_S3_PREFIXES = ("shared-audio",)

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_DETERMINISTIC_ID_RE = re.compile(r"^mi_[0-9a-f]{32}$")

#: Attributes an enrichment pass may fill on a row that already exists. Identity
#: and ordering attributes are absent: rewriting saved_at would reorder the
#: library, and rewriting the keys is meaningless.
ENRICHABLE_ATTRS = (
    "title",
    "source_url",
    "source_platform",
    "media_type",
    "duration_seconds",
    "thumbnail_url",
    "language",
    "folder_id",
    "tag_ids",
    "processing_status",
    "last_job_id",
)


def looks_like_media_item_id(value: str) -> bool:
    """Whether ``value`` has the shape of a legacy (uuid) or durable (mi_) id."""
    return bool(_UUID_RE.match(value) or _DETERMINISTIC_ID_RE.match(value))


def _as_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(Decimal(str(value)))
    except Exception:  # noqa: BLE001 - a malformed number is simply no information
        return None


def _as_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _clean(value: Any) -> Any:
    """Normalize a DynamoDB / Algolia value, treating blanks as absent."""
    if value is None:
        return None
    if isinstance(value, Enum):
        # Checked before str: UserMediaStatus is a str enum, and stripping it
        # would silently downgrade it to a plain string.
        return value
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    if isinstance(value, (list, tuple)):
        return list(value) or None
    return value


# ---------------------------------------------------------------------------
# Candidate model
# ---------------------------------------------------------------------------


@dataclass
class Candidate:
    """One library row under reconstruction, keyed by ``(user_id, media_key)``."""

    user_id: str
    media_key: str
    media_item_id: str = ""
    id_origin: str = ""
    values: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, str] = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def touch(self, source: str) -> None:
        if source not in self.sources:
            self.sources.append(source)

    def set(self, key: str, value: Any, source: str) -> None:
        """Set ``key`` if and only if no richer source already provided it."""
        value = _clean(value)
        if value is None:
            return
        self.touch(source)
        if _clean(self.values.get(key)) is not None:
            return
        self.values[key] = value
        self.provenance[key] = source

    def ordered_sources(self) -> List[str]:
        return [s for s in SOURCE_ORDER if s in self.sources]

    def backfilled_from(self) -> str:
        return ",".join(self.ordered_sources())


@dataclass
class Quarantine:
    """An entry the owner must review by hand. Never written to user_media."""

    reason: str
    media_item_id: Optional[str] = None
    user_id: Optional[str] = None
    media_key: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Source loading
# ---------------------------------------------------------------------------


def scan_table(resource: Any, name: str) -> List[Dict[str, Any]]:
    table = resource.Table(name)
    items: List[Dict[str, Any]] = []
    kwargs: Dict[str, Any] = {}
    while True:
        response = table.scan(**kwargs)
        items.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return items
        kwargs["ExclusiveStartKey"] = last_key


def list_s3_media_ids(
    s3: Any, account_id: str, suffix: str
) -> Dict[str, Set[str]]:
    """Source 5: map every media_item_id visible in S3 to the buckets holding it."""
    found: Dict[str, Set[str]] = defaultdict(set)
    for basename in S3_BUCKET_BASENAMES:
        bucket = f"media-summarizer-{basename}-{account_id}{suffix}"
        paginator = s3.get_paginator("list_objects_v2")
        try:
            for page in paginator.paginate(Bucket=bucket):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    head = key.split("/")[0]
                    if head in NON_MEDIA_S3_PREFIXES:
                        continue
                    candidate = head.split(".")[0]
                    if looks_like_media_item_id(candidate):
                        found[candidate].add(basename)
        except ClientError as exc:
            print(f"[backfill] WARN cannot list s3://{bucket}: {exc}")
    return found


def load_algolia(index_name: str, secret_id: str, region: str) -> Dict[str, Dict[str, Any]]:
    """Source 4: one entry per media_item_id present in the shared index."""
    from algoliasearch.search.client import SearchClientSync

    client_secrets = boto3.client("secretsmanager", region_name=region)
    raw = client_secrets.get_secret_value(SecretId=secret_id)["SecretString"]
    secret = json.loads(raw)
    app_id = (secret.get("ALGOLIA_APP_ID") or os.environ.get("ALGOLIA_APP_ID") or "").strip()
    api_key = (secret.get("ALGOLIA_API_KEY") or os.environ.get("ALGOLIA_API_KEY") or "").strip()
    if not app_id or not api_key:
        raise RuntimeError(f"{secret_id} holds no Algolia credentials")

    client = SearchClientSync(app_id, api_key)
    records: Dict[str, Dict[str, Any]] = {}
    cursor: Optional[str] = None
    while True:
        params: Dict[str, Any] = {
            "attributesToRetrieve": [
                "media_item_id",
                "user_id",
                "title",
                "source_platform",
                "created_at",
            ],
            "hitsPerPage": 1000,
        }
        if cursor:
            params["cursor"] = cursor
        response = client.browse(index_name=index_name, browse_params=params)
        for hit in response.hits:
            payload = hit.to_dict() if hasattr(hit, "to_dict") else dict(hit)
            media_item_id = payload.get("media_item_id") or str(
                payload.get("objectID", "")
            ).rsplit("_chunk_", 1)[0]
            if not media_item_id:
                continue
            entry = records.setdefault(
                media_item_id, {"chunks": 0, "media_item_id": media_item_id}
            )
            entry["chunks"] += 1
            for key in ("user_id", "title", "source_platform", "created_at"):
                if not entry.get(key) and payload.get(key):
                    entry[key] = payload[key]
        cursor = getattr(response, "cursor", None)
        if not cursor:
            return records


# ---------------------------------------------------------------------------
# Reconstruction
# ---------------------------------------------------------------------------


class Backfill:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.suffix = args.suffix
        self.env = self.suffix.lstrip("-") or "legacy"
        self.region = args.region
        self.apply = args.apply
        self.session = boto3.Session(region_name=self.region)
        self.dynamodb = self.session.resource("dynamodb", region_name=self.region)
        self.dynamodb_client = self.session.client("dynamodb", region_name=self.region)
        self.account_id = self.session.client("sts").get_caller_identity()["Account"]

        self.candidates: Dict[Tuple[str, str], Candidate] = {}
        self.quarantine: List[Quarantine] = []
        self.row_reports: List[Dict[str, Any]] = []
        self.idempotence_reports: List[Dict[str, Any]] = []
        self.counters: Dict[str, int] = defaultdict(int)

    # -- table names --------------------------------------------------------

    def table(self, base: str) -> str:
        return f"{base}{self.suffix}"

    # -- loading -----------------------------------------------------------

    def load(self) -> None:
        print(f"[backfill] loading sources from {self.env} ({self.region})")
        self.jobs = scan_table(self.dynamodb, self.table("processing_jobs"))
        self.submissions = scan_table(self.dynamodb, self.table("user_media_submissions"))
        self.artifacts = scan_table(self.dynamodb, self.table("media_artifacts"))
        self.idempotence = scan_table(self.dynamodb, self.table("media_idempotence"))
        self.folders = scan_table(self.dynamodb, self.table("user_folders"))
        self.users = scan_table(self.dynamodb, self.table("users"))
        self.existing_rows = scan_table(self.dynamodb, self.table("user_media"))

        self.known_user_ids = {u["id"] for u in self.users if u.get("id")}
        self.default_folder_by_user = {
            f["user_id"]: f["id"]
            for f in self.folders
            if f.get("user_id") and f.get("id") and f.get("is_default") in (True, "true")
        }
        self.job_by_id = {j["id"]: j for j in self.jobs if j.get("id")}

        # Artifact groups: only rows that actually carry a media_item_id. The
        # others are request_pointer index rows and go to quarantine.
        self.artifact_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.artifacts_without_media_item_id: List[Dict[str, Any]] = []
        for artifact in self.artifacts:
            media_item_id = _clean(artifact.get("media_item_id"))
            if media_item_id:
                self.artifact_groups[media_item_id].append(artifact)
            else:
                self.artifacts_without_media_item_id.append(artifact)

        # media_idempotence inverted: dangling job id -> media_key. Auxiliary
        # only; this table carries no user_id and can never prove ownership.
        self.media_key_by_job_id = {
            row["job_id"]: row["media_key"]
            for row in self.idempotence
            if _clean(row.get("job_id")) and _clean(row.get("media_key"))
        }

        self.submission_by_job_id = {
            s["job_id"]: s for s in self.submissions if _clean(s.get("job_id"))
        }

        # Existing durable rows, indexed both ways so a re-run converges and
        # never creates a second row for content already in the library.
        self.existing_by_media_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.existing_by_id: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for row in self.existing_rows:
            user_id = _clean(row.get("user_id"))
            media_item_id = _clean(row.get("media_item_id"))
            media_key = _clean(row.get("media_key"))
            if user_id and media_item_id:
                self.existing_by_id[(user_id, media_item_id)] = row
            if user_id and media_key:
                self.existing_by_media_key[(user_id, media_key)] = row

        if self.args.no_s3:
            self.s3_ids: Dict[str, Set[str]] = {}
            print("[backfill] source 5 (S3) skipped by --no-s3")
        else:
            self.s3_ids = list_s3_media_ids(
                self.session.client("s3", region_name=self.region),
                self.account_id,
                self.suffix,
            )

        self.algolia: Dict[str, Dict[str, Any]] = {}
        if self.args.no_algolia:
            print("[backfill] source 4 (Algolia) skipped by --no-algolia")
        else:
            index_name = self.args.algolia_index or f"media_items_{self.env}"
            secret_id = self.args.runtime_secret or f"media-summarizer-runtime-{self.env}"
            try:
                self.algolia = load_algolia(index_name, secret_id, self.region)
            except Exception as exc:  # noqa: BLE001 - a missing source is degraded, not fatal
                print(f"[backfill] WARN source 4 (Algolia {index_name}) unavailable: {exc}")

        print(
            f"[backfill] jobs={len(self.jobs)} submissions={len(self.submissions)} "
            f"artifacts={len(self.artifacts)} "
            f"(groups={len(self.artifact_groups)}, "
            f"without_media_item_id={len(self.artifacts_without_media_item_id)}) "
            f"idempotence={len(self.idempotence)} algolia={len(self.algolia)} "
            f"s3_ids={len(self.s3_ids)} existing_user_media={len(self.existing_rows)}"
        )

    # -- helpers -----------------------------------------------------------

    def wanted_user(self, user_id: Optional[str]) -> bool:
        if not user_id:
            return False
        return not self.args.user_id or user_id == self.args.user_id

    def has_legacy_footprint(self, media_item_id: str) -> bool:
        """Whether artifacts, Algolia or S3 already reference this id."""
        return (
            media_item_id in self.artifact_groups
            or media_item_id in self.algolia
            or media_item_id in self.s3_ids
        )

    def content_survives(self, media_item_id: str) -> bool:
        """Whether anything of the media's content is still reachable.

        Either a ready artifact row, or the transcript object every artifact can
        be regenerated from. Used both to set ``processing_status`` and to decide
        whether an orphaned ``reserved`` idempotence row deserves ``processed``.
        """
        for artifact in self.artifact_groups.get(media_item_id, []):
            if _clean(artifact.get("status")) == "ready":
                return True
        return TRANSCRIPT_BUCKET_BASENAME in self.s3_ids.get(media_item_id, set())

    def candidate_for(self, user_id: str, media_key: str) -> Candidate:
        key = (user_id, media_key)
        candidate = self.candidates.get(key)
        if candidate is None:
            candidate = Candidate(user_id=user_id, media_key=media_key)
            self.candidates[key] = candidate
        return candidate

    def assign_id(self, candidate: Candidate, preferred: Optional[str], origin: str) -> None:
        """Fix the row's ``media_item_id`` once, on the richest evidence available.

        Priority: an existing library row for this content (so a re-run and the
        live dual-write can never produce a duplicate) > a legacy id the
        artifacts / Algolia / S3 already use (so deep links keep resolving) > the
        deterministic id a new save would compute.
        """
        if candidate.media_item_id:
            return
        existing = self.existing_by_media_key.get((candidate.user_id, candidate.media_key))
        if existing:
            candidate.media_item_id = existing["media_item_id"]
            candidate.id_origin = "existing_row"
            if preferred and preferred != candidate.media_item_id and self.has_legacy_footprint(preferred):
                candidate.notes.append(
                    f"legacy_id_conflict: artifacts/search reference {preferred} but the "
                    f"library already holds this content under {candidate.media_item_id}"
                )
            return
        if preferred:
            candidate.media_item_id = preferred
            candidate.id_origin = origin
            return
        candidate.media_item_id = build_media_item_id(candidate.user_id, candidate.media_key)
        candidate.id_origin = "deterministic"

    # -- reconstruction, sources 1 to 5 in order ---------------------------

    def collect(self) -> None:
        self._collect_jobs()
        self._collect_submissions()
        self._collect_artifact_groups()
        self._collect_algolia_only()
        self._collect_s3_only()
        self._finalize_candidates()

    def _collect_jobs(self) -> None:
        """Source 1. The richest source: everything the library needs."""
        for job in self.jobs:
            job_id = _clean(job.get("id"))
            user_id = _clean(job.get("user_id"))
            media_key = _clean(job.get("media_key"))
            if not self.wanted_user(user_id):
                continue
            if not media_key:
                # The ledger is the last place a dead job's content identity may
                # survive. Consulting it is a lookup, not a guess.
                media_key = _clean(self.media_key_by_job_id.get(job_id or ""))
            if not user_id or user_id not in self.known_user_ids or not media_key:
                # No owner account -> nothing could ever read the row. No
                # media_key -> the row has no content identity, cannot be keyed,
                # deduplicated or matched to the ledger. Neither is ever invented.
                self.quarantine.append(
                    Quarantine(
                        reason="owner_account_missing"
                        if user_id not in self.known_user_ids
                        else "job_without_media_key",
                        media_item_id=job_id,
                        user_id=user_id,
                        media_key=media_key,
                        detail={
                            "job_status": _clean(job.get("job_status")),
                            "created_at": _clean(job.get("created_at")),
                            "title": _clean(job.get("title")),
                            "source_url": _clean(job.get("source_url")),
                            "owner_account_exists": user_id in self.known_user_ids,
                            "has_media_key": bool(media_key),
                        },
                    )
                )
                continue

            candidate = self.candidate_for(user_id, media_key)
            # The legacy id is the job id: that is what artifacts, Algolia,
            # mobile caches and deep links use today.
            self.assign_id(candidate, job_id, "legacy_job")
            candidate.touch(SRC_JOBS)
            candidate.set("title", job.get("title"), SRC_JOBS)
            candidate.set("source_url", job.get("source_url"), SRC_JOBS)
            candidate.set("source_platform", job.get("source_platform"), SRC_JOBS)
            candidate.set("media_type", job.get("media_type"), SRC_JOBS)
            candidate.set("thumbnail_url", job.get("media_image"), SRC_JOBS)
            candidate.set("folder_id", job.get("folder_id"), SRC_JOBS)
            candidate.set("tag_ids", job.get("tag_ids"), SRC_JOBS)
            candidate.set("saved_at", _as_dt(job.get("created_at")), SRC_JOBS)
            # The job still exists, so the pointer is legitimately set here. It
            # is still allowed to dangle later: nothing reads it.
            candidate.set("last_job_id", job_id, SRC_JOBS)
            status = JOB_STATUS_TO_LIBRARY_STATUS.get(_clean(job.get("job_status")) or "")
            if status is not None:
                candidate.set("processing_status", status, SRC_JOBS)
            metadata = job.get("extraction_metadata") or {}
            if isinstance(metadata, dict):
                duration = _as_int(metadata.get("audio_duration_seconds"))
                if duration:
                    candidate.set("duration_seconds", duration, SRC_JOBS)

    def _collect_submissions(self) -> None:
        """Source 2. Proves ownership even when the job has been deleted."""
        for submission in self.submissions:
            user_id = _clean(submission.get("user_id"))
            media_key = _clean(submission.get("media_key"))
            job_id = _clean(submission.get("job_id"))
            if not self.wanted_user(user_id) or not media_key:
                continue

            candidate = self.candidate_for(user_id, media_key)
            job_alive = bool(job_id and job_id in self.job_by_id)
            if not candidate.media_item_id:
                # Dangling reference: superseded, never repaired. The row is
                # keyed by the artifact-derived id when the dead job id still has
                # a footprint, otherwise by the deterministic id. last_job_id is
                # deliberately left null.
                preferred = job_id if job_id and self.has_legacy_footprint(job_id) else None
                self.assign_id(candidate, preferred, "legacy_dangling_job")
                if job_id and not job_alive:
                    candidate.notes.append(f"dangling_job_id={job_id} (job no longer exists)")
            candidate.touch(SRC_SUBMISSIONS)
            candidate.set("saved_at", _as_dt(submission.get("submitted_at")), SRC_SUBMISSIONS)

    def _collect_artifact_groups(self) -> None:
        """Source 3. Recovers ids and content evidence; never ownership by itself."""
        for media_item_id, artifacts in sorted(self.artifact_groups.items()):
            owner = self._resolve_owner(media_item_id)
            media_key = self._resolve_media_key(media_item_id)
            if owner and media_key and self.wanted_user(owner):
                candidate = self.candidate_for(owner, media_key)
                self.assign_id(candidate, media_item_id, "legacy_artifacts")
                candidate.touch(SRC_ARTIFACTS)
                if candidate.media_item_id == media_item_id:
                    ready = [a for a in artifacts if _clean(a.get("status")) == "ready"]
                    if ready:
                        candidate.set("processing_status", UserMediaStatus.READY, SRC_ARTIFACTS)
                    oldest = min(
                        (d for d in (_as_dt(a.get("created_at")) for a in artifacts) if d),
                        default=None,
                    )
                    candidate.set("saved_at", oldest, SRC_ARTIFACTS)
                continue

            if self.args.user_id and owner and owner != self.args.user_id:
                continue
            self.quarantine.append(
                Quarantine(
                    reason="artifacts_without_resolvable_owner"
                    if not owner
                    else "artifacts_without_media_key",
                    media_item_id=media_item_id,
                    user_id=owner,
                    media_key=media_key,
                    detail={
                        "artifact_count": len(artifacts),
                        "artifact_types": sorted(
                            {str(_clean(a.get("artifact_type"))) for a in artifacts}
                        ),
                        "s3_buckets": sorted(self.s3_ids.get(media_item_id, set())),
                        "in_algolia": media_item_id in self.algolia,
                        "owner_account_exists": bool(owner) and owner in self.known_user_ids,
                    },
                )
            )

    def _collect_algolia_only(self) -> None:
        """Source 4. Often the only surviving title, and it carries the user_id."""
        for media_item_id, record in sorted(self.algolia.items()):
            owner = self._resolve_owner(media_item_id)
            media_key = self._resolve_media_key(media_item_id)
            if not owner or not media_key:
                if not self.args.user_id or owner == self.args.user_id:
                    self.quarantine.append(
                        Quarantine(
                            reason="search_record_without_resolvable_owner"
                            if not owner
                            else "search_record_without_media_key",
                            media_item_id=media_item_id,
                            user_id=owner,
                            media_key=media_key,
                            detail={
                                "title": record.get("title"),
                                "source_platform": record.get("source_platform"),
                                "chunks": record.get("chunks"),
                                "has_artifacts": media_item_id in self.artifact_groups,
                                "s3_buckets": sorted(self.s3_ids.get(media_item_id, set())),
                                "owner_account_exists": bool(owner)
                                and owner in self.known_user_ids,
                            },
                        )
                    )
                continue
            if not self.wanted_user(owner):
                continue
            candidate = self.candidate_for(owner, media_key)
            self.assign_id(candidate, media_item_id, "legacy_algolia")
            candidate.touch(SRC_ALGOLIA)
            if candidate.media_item_id != media_item_id:
                continue
            candidate.set("title", record.get("title"), SRC_ALGOLIA)
            candidate.set("source_platform", record.get("source_platform"), SRC_ALGOLIA)
            created_at = _as_int(record.get("created_at"))
            if created_at:
                candidate.set(
                    "saved_at",
                    datetime.fromtimestamp(created_at, tz=timezone.utc),
                    SRC_ALGOLIA,
                )

    def _collect_s3_only(self) -> None:
        """Source 5. Existence proof only: no owner, no content identity."""
        claimed = {c.media_item_id for c in self.candidates.values()}
        for media_item_id, buckets in sorted(self.s3_ids.items()):
            if media_item_id in claimed:
                continue
            if media_item_id in self.artifact_groups or media_item_id in self.algolia:
                # Already reported by source 3 or 4 with richer evidence.
                continue
            owner = self._resolve_owner(media_item_id)
            if owner and self.args.user_id and owner != self.args.user_id:
                continue
            self.quarantine.append(
                Quarantine(
                    reason="s3_objects_without_resolvable_owner",
                    media_item_id=media_item_id,
                    user_id=owner,
                    media_key=self._resolve_media_key(media_item_id),
                    detail={"s3_buckets": sorted(buckets)},
                )
            )

    def _resolve_owner(self, media_item_id: str) -> Optional[str]:
        """Establish ownership of a legacy id from sources 1, 2 and 4 only.

        Ownership is never inferred from the environment having a single real
        user, and never from an artifact or an S3 object, which carry no user_id.
        """
        job = self.job_by_id.get(media_item_id)
        if job and _clean(job.get("user_id")):
            return _clean(job["user_id"])
        submission = self.submission_by_job_id.get(media_item_id)
        if submission and _clean(submission.get("user_id")):
            return _clean(submission["user_id"])
        record = self.algolia.get(media_item_id)
        if record and _clean(record.get("user_id")):
            return _clean(record["user_id"])
        return None

    def _resolve_media_key(self, media_item_id: str) -> Optional[str]:
        job = self.job_by_id.get(media_item_id)
        if job and _clean(job.get("media_key")):
            return _clean(job["media_key"])
        submission = self.submission_by_job_id.get(media_item_id)
        if submission and _clean(submission.get("media_key")):
            return _clean(submission["media_key"])
        # Auxiliary index: the idempotence ledger still maps this dead job id to
        # the content identity. It proves nothing about ownership.
        return _clean(self.media_key_by_job_id.get(media_item_id))

    def _finalize_candidates(self) -> None:
        """Fill the gaps no source could, and drop what must not be written."""
        for key in sorted(self.candidates):
            candidate = self.candidates[key]
            media_item_id = candidate.media_item_id

            if candidate.user_id not in self.known_user_ids:
                # The account was deleted (E2E throwaways, task-246). Writing a
                # library row for it would resurrect rows nothing can ever read.
                self.quarantine.append(
                    Quarantine(
                        reason="owner_account_missing",
                        media_item_id=media_item_id,
                        user_id=candidate.user_id,
                        media_key=candidate.media_key,
                        detail={
                            "title": candidate.values.get("title"),
                            "sources": candidate.ordered_sources(),
                        },
                    )
                )
                del self.candidates[key]
                continue

            if media_item_id in self.s3_ids:
                # Source 5 contributed no field, only the proof that objects for
                # this id exist. Recorded so backfilled_from stays truthful.
                candidate.touch(SRC_S3)

            if not candidate.values.get("folder_id"):
                default_folder = self.default_folder_by_user.get(candidate.user_id)
                if default_folder:
                    candidate.set("folder_id", default_folder, "default_folder")
                else:
                    candidate.notes.append(
                        "no folder: the user has no default folder to fall back on"
                    )

            if not candidate.values.get("processing_status"):
                if self.content_survives(media_item_id):
                    candidate.set("processing_status", UserMediaStatus.READY, SRC_ARTIFACTS)
                else:
                    # No job, no artifact, no transcript: the content is gone.
                    # processing_status stays null rather than claiming a failure
                    # that never happened -- it is nullable by contract.
                    candidate.notes.append(
                        "content_lost: no surviving job, artifact or transcript"
                    )

            if not candidate.values.get("saved_at"):
                candidate.notes.append("saved_at unknown, defaulted to now")

    # -- writing -----------------------------------------------------------

    def build_record(self, candidate: Candidate) -> UserMediaRecord:
        now = datetime.now(timezone.utc)
        saved_at = candidate.values.get("saved_at") or now
        # UserMediaStatus is a str enum, so Candidate.set stored it as a plain
        # string. Coerce it back rather than trusting isinstance.
        raw_status = candidate.values.get("processing_status")
        status = UserMediaStatus(raw_status) if raw_status else None
        return UserMediaRecord(
            user_id=candidate.user_id,
            media_item_id=candidate.media_item_id,
            media_key=candidate.media_key,
            title=candidate.values.get("title"),
            source_url=candidate.values.get("source_url"),
            source_platform=candidate.values.get("source_platform"),
            media_type=candidate.values.get("media_type"),
            duration_seconds=candidate.values.get("duration_seconds"),
            thumbnail_url=candidate.values.get("thumbnail_url"),
            language=candidate.values.get("language"),
            folder_id=candidate.values.get("folder_id"),
            tag_ids=[str(t) for t in (candidate.values.get("tag_ids") or [])],
            saved_at=saved_at,
            updated_at=now,
            processing_status=status,
            last_job_id=candidate.values.get("last_job_id"),
            backfilled_from=candidate.backfilled_from(),
        )

    def write_candidates(self) -> None:
        table = self.dynamodb.Table(self.table("user_media"))
        for key in sorted(self.candidates):
            candidate = self.candidates[key]
            record = self.build_record(candidate)
            existing = self.existing_by_id.get((candidate.user_id, candidate.media_item_id))
            report: Dict[str, Any] = {
                "user_id": candidate.user_id,
                "media_item_id": candidate.media_item_id,
                "media_key": candidate.media_key,
                "id_origin": candidate.id_origin,
                "sources": candidate.ordered_sources(),
                "provenance": candidate.provenance,
                "values": {
                    k: (v.value if isinstance(v, UserMediaStatus) else v)
                    for k, v in candidate.values.items()
                },
                "notes": candidate.notes,
            }

            if existing is None:
                # None means "the conditional put won, or would have in a dry
                # run"; a dict means a concurrent writer got there first and the
                # row must be enriched rather than overwritten.
                existing = self._create(table, candidate, record)
                if existing is None:
                    self.counters["created"] += 1
                    report["action"] = "CREATE"
                    self._print_row(report, record)
                    self.row_reports.append(report)
                    continue
                report["notes"] = candidate.notes + [
                    "row appeared between the scan and the write, enriched instead"
                ]

            filled = self._enrich(table, candidate, record, existing)
            report["action"] = "UPDATE" if filled else "NOOP"
            report["filled"] = sorted(filled)
            self.counters["updated" if filled else "unchanged"] += 1
            self._print_row(report, record)
            self.row_reports.append(report)

    def _create(
        self, table: Any, candidate: Candidate, record: UserMediaRecord
    ) -> Optional[Dict[str, Any]]:
        """Conditionally create the row. Returns the winner's row if it lost.

        The conditional ``PutItem`` is the whole concurrency control (§4.3): the
        backfill and the live dual-write can run at the same time, and whoever
        arrives second must not clobber the first.
        """
        if not self.apply:
            return None
        try:
            table.put_item(
                Item=record.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(media_item_id)",
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
            return (
                table.get_item(
                    Key={
                        "user_id": candidate.user_id,
                        "media_item_id": candidate.media_item_id,
                    },
                    ConsistentRead=True,
                ).get("Item")
                or {}
            )
        return None

    def _enrich(
        self,
        table: Any,
        candidate: Candidate,
        record: UserMediaRecord,
        existing: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fill only the attributes the stored row is missing.

        Never overwrites: the stored value may come from a richer source, or from
        a user action (a folder move) that must win over anything reconstructed.
        """
        desired = record.to_dynamodb_item()
        filled: Dict[str, Any] = {}
        for attr in ENRICHABLE_ATTRS:
            if attr not in desired:
                continue
            current = existing.get(attr)
            if attr == "tag_ids":
                if current:
                    continue
                if not desired[attr]:
                    continue
            elif _clean(current) is not None:
                continue
            filled[attr] = desired[attr]

        if not filled:
            return {}

        if "folder_id" in filled:
            # The folder LSI range key must follow the folder, or the row stays
            # queryable under "no folder" forever.
            saved_at = _as_dt(existing.get("saved_at")) or record.saved_at
            filled["folder_sort_key"] = build_folder_sort_key(filled["folder_id"], saved_at)

        # A different attribute from `backfilled_from` on purpose: this row was
        # not created by the backfill, so the rollback must not delete it.
        filled["backfill_enriched_from"] = candidate.backfilled_from()
        filled["backfill_enriched_at"] = datetime.now(timezone.utc).isoformat()

        if not self.apply:
            return filled

        pairs = list(filled.items())
        table.update_item(
            Key={"user_id": candidate.user_id, "media_item_id": candidate.media_item_id},
            UpdateExpression="SET "
            + ", ".join(f"#a{i} = :v{i}" for i in range(len(pairs)))
            + ", updated_at = :now",
            ExpressionAttributeNames={f"#a{i}": attr for i, (attr, _) in enumerate(pairs)},
            ExpressionAttributeValues={
                **{f":v{i}": value for i, (_, value) in enumerate(pairs)},
                ":now": datetime.now(timezone.utc).isoformat(),
            },
            ConditionExpression="attribute_exists(media_item_id)",
        )
        return filled

    def _print_row(self, report: Dict[str, Any], record: UserMediaRecord) -> None:
        title = report["values"].get("title")
        line = (
            f"[backfill]   {report['action']:<6} user={report['user_id']} "
            f"media_item_id={report['media_item_id']} "
            f"id_origin={report['id_origin']} "
            f"sources={','.join(report['sources'])} "
            f"title={title!r} folder={report['values'].get('folder_id')} "
            f"status={report['values'].get('processing_status')}"
        )
        if report.get("filled"):
            line += f" filled={','.join(report['filled'])}"
        print(line)
        for note in report["notes"]:
            print(f"[backfill]          note: {note}")

    # -- media_idempotence repair -----------------------------------------

    def repair_idempotence(self) -> None:
        """Unstick the ledger rows whose job was deleted under them.

        A row frozen at ``reserved`` pointing at a dead job is what makes
        re-submitting the same URL return a media_item_id that 404s (§1.6.1): the
        user cannot even repair their own library by re-saving. Two outcomes:

        - the content demonstrably survives **and** the library now holds a row
          for it -> ``processed``, so the duplicate short-circuit resolves to
          something the user can actually open;
        - otherwise -> the reservation is released (the row is deleted, exactly as
          ``media_idempotence.release_reservation`` does), so the media can be
          legitimately re-ingested.

        The library-row condition is stricter than "a complete artifact set
        exists" on purpose. ``_build_duplicate_outcome`` returns the ledger's
        ``job_id`` as the ``media_item_id``, so marking a row ``processed`` while
        no library row carries that id would hand the user a media that 404s --
        the §1.6.1 failure this whole epic is about. A quarantined media is
        therefore released rather than sealed.

        The conditional delete is scoped to ``status = reserved``: a row a live
        submission has meanwhile advanced is never touched.
        """
        table = self.dynamodb.Table(self.table("media_idempotence"))
        ids_by_media_key: Dict[str, Set[str]] = defaultdict(set)
        for candidate in self.candidates.values():
            ids_by_media_key[candidate.media_key].add(candidate.media_item_id)
        # Rows the live dual-write already created also count as "in the library".
        for (_, media_key), row in self.existing_by_media_key.items():
            ids_by_media_key[media_key].add(row["media_item_id"])

        for row in sorted(self.idempotence, key=lambda r: str(r.get("media_key"))):
            media_key = _clean(row.get("media_key"))
            job_id = _clean(row.get("job_id"))
            status = _clean(row.get("status"))
            if not media_key:
                continue

            entry: Dict[str, Any] = {
                "media_key": media_key,
                "job_id": job_id,
                "status_before": status,
            }
            if status != "reserved":
                entry["action"] = "SKIP"
                entry["why"] = f"status is {status}, not a stuck reservation"
                self._log_idempotence(entry)
                continue
            if job_id and job_id in self.job_by_id:
                entry["action"] = "KEEP"
                entry["why"] = "the job still exists, the reservation is legitimate"
                self.counters["idempotence_kept"] += 1
                self._log_idempotence(entry)
                continue

            library_ids = set(ids_by_media_key.get(media_key, set()))
            related_ids = set(library_ids)
            if job_id:
                related_ids.add(job_id)
            surviving = sorted(i for i in related_ids if self.content_survives(i))
            entry["media_item_ids"] = sorted(related_ids)
            entry["library_media_item_ids"] = sorted(library_ids)
            entry["surviving_content"] = surviving

            # Both writes below are scoped to the exact row that was read: a
            # submission that re-reserved this media_key in the meantime owns a
            # different job_id and must be left strictly alone. Same guard as
            # media_idempotence.release_reservation.
            guard = "#st = :reserved AND job_id = :job"
            guard_names = {"#st": "status"}
            guard_values = {":reserved": "reserved", ":job": job_id or ""}

            if surviving and library_ids:
                entry["action"] = "PROCESSED"
                entry["why"] = (
                    f"artifacts/transcript survive for {surviving} and the library "
                    f"holds {sorted(library_ids)}"
                )
                self.counters["idempotence_processed"] += 1
                if self.apply:
                    self._guarded(
                        entry,
                        lambda: table.update_item(
                            Key={"media_key": media_key},
                            UpdateExpression=(
                                "SET #st = :processed, updated_at = :now, "
                                "repaired_by = :task"
                            ),
                            ExpressionAttributeNames=guard_names,
                            ExpressionAttributeValues={
                                **guard_values,
                                ":processed": "processed",
                                ":now": datetime.now(timezone.utc).isoformat(),
                                ":task": "task-241",
                            },
                            ConditionExpression=guard,
                        ),
                    )
            else:
                entry["action"] = "RESET"
                entry["why"] = (
                    "no library row could be rebuilt for this content"
                    if surviving
                    else "no surviving content"
                ) + ": released so the media can be re-ingested"
                self.counters["idempotence_reset"] += 1
                if self.apply:
                    self._guarded(
                        entry,
                        lambda: table.delete_item(
                            Key={"media_key": media_key},
                            ConditionExpression=guard,
                            ExpressionAttributeNames=guard_names,
                            ExpressionAttributeValues=guard_values,
                        ),
                    )
            self._log_idempotence(entry)

    @staticmethod
    def _guarded(entry: Dict[str, Any], write: Any) -> None:
        """Run a conditional ledger write, downgrading a lost race to a report."""
        try:
            write()
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != (
                "ConditionalCheckFailedException"
            ):
                raise
            entry["action"] = "SKIP_RACE"
            entry["why"] = "the ledger row changed under the backfill, left untouched"

    def _log_idempotence(self, entry: Dict[str, Any]) -> None:
        self.idempotence_reports.append(entry)
        if entry["action"] == "SKIP":
            return
        print(
            f"[idem]   {entry['action']:<9} media_key={entry['media_key']} "
            f"job_id={entry['job_id']} -- {entry['why']}"
        )

    # -- reporting ---------------------------------------------------------

    # -- rollback ----------------------------------------------------------

    def load_for_rollback(self) -> None:
        """Read only the target table: a rollback needs no source at all."""
        self.idempotence = []
        self.existing_rows = scan_table(self.dynamodb, self.table("user_media"))
        print(f"[rollback] {len(self.existing_rows)} rows in {self.table('user_media')}")

    def rollback(self) -> Dict[str, Any]:
        """Undo the backfill: delete exactly the rows it created.

        §5.6 of the benchmark: reconstructed rows are identifiable by
        ``backfilled_from``, which a live save never writes, so the rollback is a
        targeted delete and not a guess.

        Rows the backfill only *enriched* are reported, not deleted: they were
        created by a real user save and deleting them would destroy data the
        backfill never owned. Their filled attributes are listed in the run's
        JSON report, which is what an operator needs to strip them by hand.
        """
        table = self.dynamodb.Table(self.table("user_media"))
        created = [r for r in self.existing_rows if _clean(r.get("backfilled_from"))]
        enriched = [
            r
            for r in self.existing_rows
            if _clean(r.get("backfill_enriched_from")) and not _clean(r.get("backfilled_from"))
        ]

        for row in created:
            print(
                f"[rollback] DELETE user={row['user_id']} "
                f"media_item_id={row['media_item_id']} "
                f"backfilled_from={row.get('backfilled_from')}"
            )
            if self.apply:
                table.delete_item(
                    Key={
                        "user_id": row["user_id"],
                        "media_item_id": row["media_item_id"],
                    },
                    # Never delete a row a live save created, even if the scan
                    # snapshot is stale.
                    ConditionExpression="attribute_exists(backfilled_from)",
                )
        for row in enriched:
            print(
                f"[rollback] KEEP   user={row['user_id']} "
                f"media_item_id={row['media_item_id']} "
                f"enriched_from={row.get('backfill_enriched_from')} "
                "-- created by a real save, strip its filled attributes by hand"
            )

        print("")
        print(f"[rollback] {'APPLY' if self.apply else 'DRY RUN'} on {self.table('user_media')}")
        print(f"[rollback] rows deleted (created by the backfill): {len(created)}")
        print(f"[rollback] rows kept (only enriched)             : {len(enriched)}")
        print(f"[rollback] rows untouched                        : "
              f"{len(self.existing_rows) - len(created) - len(enriched)}")
        print("[rollback] media_idempotence is NOT rolled back: released "
              "reservations are gone and repaired ones are legitimately processed.")
        return {"deleted": len(created), "kept_enriched": len(enriched)}

    def snapshot_before_write(self) -> Optional[Path]:
        """Dump the mutable tables before touching them.

        ``repair_idempotence`` deletes ledger rows. That deletion is the only
        destructive operation in this script, so the pre-image is written to disk
        *before* it happens: a run interrupted halfway must still leave a way to
        reconstruct what was there.
        """
        if not self.apply:
            return None
        report_dir = Path(self.args.report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = report_dir / f"pre-apply-snapshot-{self.env}-{stamp}.json"
        path.write_text(
            json.dumps(
                {
                    "taken_at": datetime.now(timezone.utc).isoformat(),
                    "environment": self.env,
                    "media_idempotence": self.idempotence,
                    "user_media": self.existing_rows,
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
        )
        print(f"[backfill] pre-apply snapshot written to {path}")
        return path

    def summarize(self) -> Dict[str, Any]:
        by_user: Dict[str, int] = defaultdict(int)
        by_folder: Dict[str, int] = defaultdict(int)
        rebuilt_without_content = 0
        for candidate in self.candidates.values():
            by_user[candidate.user_id] += 1
            by_folder[str(candidate.values.get("folder_id"))] += 1
            if any(n.startswith("content_lost") for n in candidate.notes):
                rebuilt_without_content += 1

        quarantine_by_reason: Dict[str, int] = defaultdict(int)
        for entry in self.quarantine:
            quarantine_by_reason[entry.reason] += 1

        # A media may be quarantined by several sources at once (no owner in the
        # artifacts *and* no media_key in the search index). Count media, not
        # findings. A media whose content is gone as well as its ownership is
        # counted as definitively lost: there is nothing left to attach.
        quarantined_ids = {e.media_item_id for e in self.quarantine if e.media_item_id}
        recoverable_ids = {i for i in quarantined_ids if self.content_survives(i)}
        lost_ids = quarantined_ids - recoverable_ids

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "environment": self.env,
            "region": self.region,
            "applied": self.apply,
            "user_filter": self.args.user_id,
            "sources": {
                "processing_jobs": len(self.jobs),
                "user_media_submissions": len(self.submissions),
                "media_artifacts": len(self.artifacts),
                "media_artifacts_groups": len(self.artifact_groups),
                "media_artifacts_without_media_item_id": len(
                    self.artifacts_without_media_item_id
                ),
                "media_idempotence": len(self.idempotence),
                "algolia_media_items": len(self.algolia),
                "s3_media_ids": len(self.s3_ids),
                "user_media_before": len(self.existing_rows),
            },
            "recovered": len(self.candidates),
            "recovered_created": self.counters["created"],
            "recovered_enriched": self.counters["updated"],
            "recovered_unchanged": self.counters["unchanged"],
            "recovered_by_user": dict(by_user),
            "recovered_by_folder": dict(by_folder),
            "recovered_without_surviving_content": rebuilt_without_content,
            "quarantined": len(recoverable_ids),
            "definitively_lost": len(lost_ids),
            "quarantine_findings": len(self.quarantine),
            "quarantined_by_reason": dict(quarantine_by_reason),
            "non_media_index_rows_reported": len(self.artifacts_without_media_item_id),
            "idempotence": {
                "rows": len(self.idempotence),
                "kept": self.counters["idempotence_kept"],
                "advanced_to_processed": self.counters["idempotence_processed"],
                "reset": self.counters["idempotence_reset"],
            },
        }

    def write_reports(self, summary: Dict[str, Any]) -> Tuple[Path, Path]:
        report_dir = Path(self.args.report_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        mode = "apply" if self.apply else "dryrun"

        json_path = report_dir / f"backfill-{self.env}-{mode}-{stamp}.json"
        json_path.write_text(
            json.dumps(
                {
                    "summary": summary,
                    "rows": self.row_reports,
                    "idempotence": self.idempotence_reports,
                    "quarantine": [
                        {
                            "reason": q.reason,
                            "media_item_id": q.media_item_id,
                            "user_id": q.user_id,
                            "media_key": q.media_key,
                            **q.detail,
                        }
                        for q in self.quarantine
                    ],
                    "artifact_rows_without_media_item_id": [
                        {
                            "artifact_id": _clean(a.get("artifact_id")),
                            "item_type": _clean(a.get("item_type")),
                            "status": _clean(a.get("status")),
                            "active_artifact_id": _clean(a.get("active_artifact_id")),
                            "created_at": _clean(a.get("created_at")),
                        }
                        for a in self.artifacts_without_media_item_id
                    ],
                },
                indent=2,
                sort_keys=True,
                default=str,
            )
        )

        md_path = report_dir / f"quarantine-{self.env}-{mode}-{stamp}.md"
        md_path.write_text(self._render_quarantine_markdown(summary))
        return json_path, md_path

    def _render_quarantine_markdown(self, summary: Dict[str, Any]) -> str:
        lines = [
            f"# user_media backfill — owner review ({self.env})",
            "",
            f"Generated {summary['generated_at']} — mode "
            f"**{'APPLY' if self.apply else 'DRY RUN'}**, region {self.region}.",
            "",
            "Nothing below was written to `user_media`. Ownership is never inferred,",
            "so each entry needs a human decision: attach it to an account, or accept",
            "the loss.",
            "",
            "## Counts",
            "",
            f"- media recovered into `user_media`: **{summary['recovered']}**",
            f"- media quarantined (content survives, owner unknown): "
            f"**{summary['quarantined']}**",
            f"- media definitively lost (no owner, no content): "
            f"**{summary['definitively_lost']}**",
            f"- non-media index rows reported: "
            f"**{summary['non_media_index_rows_reported']}**",
            "",
            f"{summary['quarantine_findings']} findings below, by reason:",
            "",
        ]
        for reason, count in sorted(summary["quarantined_by_reason"].items()):
            lines.append(f"- `{reason}`: {count}")
        lines.append("")

        by_reason: Dict[str, List[Quarantine]] = defaultdict(list)
        for entry in self.quarantine:
            by_reason[entry.reason].append(entry)

        for reason in sorted(by_reason):
            lines += [f"## {reason}", ""]
            lines.append("| media_item_id | user_id | media_key | evidence |")
            lines.append("|---|---|---|---|")
            for entry in sorted(by_reason[reason], key=lambda e: str(e.media_item_id)):
                evidence = ", ".join(
                    f"{k}={v}" for k, v in sorted(entry.detail.items()) if v not in (None, [], {})
                )
                lines.append(
                    f"| `{entry.media_item_id or '-'}` | `{entry.user_id or '-'}` | "
                    f"`{(entry.media_key or '-')[:24]}` | {evidence} |"
                )
            lines.append("")

        if self.artifacts_without_media_item_id:
            lines += [
                "## artifact_rows_without_media_item_id",
                "",
                f"{len(self.artifacts_without_media_item_id)} rows of "
                f"`media_artifacts{self.suffix}` carry no `media_item_id`. Every one of "
                "them is an `item_type` listed below — index rows, not media. They are "
                "reported, not written, and never deleted.",
                "",
            ]
            kinds: Dict[str, int] = defaultdict(int)
            for artifact in self.artifacts_without_media_item_id:
                kinds[str(_clean(artifact.get("item_type")))] += 1
            for kind, count in sorted(kinds.items()):
                lines.append(f"- `{kind}`: {count}")
            lines.append("")

        return "\n".join(lines)


def print_summary(summary: Dict[str, Any]) -> None:
    print("")
    print("[backfill] ==================== SUMMARY ====================")
    print(f"[backfill] mode                : {'APPLY' if summary['applied'] else 'DRY RUN'}")
    print(f"[backfill] environment        : {summary['environment']}")
    print(f"[backfill] media RECOVERED    : {summary['recovered']}")
    print(
        f"[backfill]   created={summary['recovered_created']} "
        f"enriched={summary['recovered_enriched']} "
        f"unchanged={summary['recovered_unchanged']}"
    )
    for user_id, count in sorted(summary["recovered_by_user"].items()):
        print(f"[backfill]   user {user_id}: {count}")
    print(
        f"[backfill] media QUARANTINED  : {summary['quarantined']} "
        "(content survives, owner needs manual review)"
    )
    print(
        f"[backfill] media DEFINITIVELY LOST: {summary['definitively_lost']} "
        "(no owner and no surviving content: nothing left to attach)"
    )
    print(f"[backfill] quarantine findings: {summary['quarantine_findings']}")
    for reason, count in sorted(summary["quarantined_by_reason"].items()):
        print(f"[backfill]   {reason}: {count}")
    print(
        f"[backfill] non-media index rows: "
        f"{summary['non_media_index_rows_reported']} "
        "(media_artifacts request pointers, reported not written)"
    )
    idem = summary["idempotence"]
    print(
        f"[backfill] media_idempotence   : {idem['rows']} rows -> "
        f"kept={idem['kept']} processed={idem['advanced_to_processed']} "
        f"reset={idem['reset']}"
    )
    print("[backfill] =================================================")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--suffix",
        default="-dev",
        help="environment suffix of the tables to read and write. Pass as --suffix=-dev.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually write user_media and repair media_idempotence.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report only, write nothing. This is the default.",
    )
    parser.add_argument("--region", default=REGION)
    parser.add_argument(
        "--user-id",
        default=None,
        help="restrict the run to a single account (recovery of one library).",
    )
    parser.add_argument(
        "--report-dir",
        default="tmp/backfill-user-media",
        help="where the JSON and quarantine reports are written (gitignored).",
    )
    parser.add_argument("--no-algolia", action="store_true", help="skip source 4.")
    parser.add_argument("--no-s3", action="store_true", help="skip source 5.")
    parser.add_argument("--algolia-index", default=None)
    parser.add_argument("--runtime-secret", default=None)
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="delete the rows this backfill created (identified by backfilled_from) "
        "and nothing else. Honors --dry-run/--apply.",
    )
    args = parser.parse_args(argv)

    if args.apply and args.dry_run:
        parser.error("--apply and --dry-run are mutually exclusive")
    if args.suffix not in ALLOWED_SUFFIXES:
        parser.error(
            f"--suffix must be one of {ALLOWED_SUFFIXES!r}. prod is deliberately "
            "unreachable from this script."
        )

    backfill = Backfill(args)

    if args.rollback:
        print(
            f"[rollback] {'APPLY' if args.apply else 'DRY RUN'} on user_media{args.suffix}"
        )
        backfill.load_for_rollback()
        backfill.snapshot_before_write()
        backfill.rollback()
        if not args.apply:
            print("[rollback] dry run: nothing was deleted. Re-run with --apply.")
        return 0

    print(f"[backfill] {'APPLY' if args.apply else 'DRY RUN'} on user_media{args.suffix}")
    backfill.load()
    backfill.collect()
    backfill.snapshot_before_write()
    backfill.write_candidates()
    backfill.repair_idempotence()
    summary = backfill.summarize()
    json_path, md_path = backfill.write_reports(summary)
    print_summary(summary)
    print(f"[backfill] per-row report : {json_path}")
    print(f"[backfill] owner review   : {md_path}")
    if not args.apply:
        print("[backfill] dry run: nothing was written. Re-run with --apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
