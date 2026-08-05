---
owner_decision: pending
---

# Benchmark : durable canonical media-library persistence model, independent of processing-job retention

> Task: `task-218` — research only, no implementation.
> Paired implementation tasks: `task-219` (durable persistence foundation), `task-220` (migrate library / Search / folders).
> Evidence base: repository code at commit `3a41cc4`, Terraform in `infrastructure/terraform/`, and a live inspection of the AWS **dev** account `125313707865` in `eu-west-3` performed on 2026-08-05.

## Owner Validation

**Decision**: _(à remplir par l'owner après relecture — texte libre décrivant la décision finale : accept recommandation X, reject parce que Y, accept with modifications Z, OU, si redo, les consignes précises de correction à intégrer au prochain passage)_
**Validated at**: _(date ISO à remplir par l'owner)_

---

## Recommendation

**Adopt Option A — a dedicated durable `user_media` table that is the single source of truth for a user's saved library — and demote `processing_jobs` to purely operational state that stays free to expire.**

Because the library is *actively losing data right now* (see §1.4: the owner's own account has 5 folders and 6 submission records but only **1** surviving processing job), the rollout is split in two:

| Phase | Action | Why |
|---|---|---|
| **Phase 0 — same-day hotfix** | Disable TTL on the `processing_jobs` table (`infrastructure/terraform/dynamodb_core_tables.tf:62-66`). One-line infra change, no code, no migration. | Stops further destruction of the library while the real fix is built. This is Option C used **only as a freeze**, never as the end state. |
| **Phases 1-4 — the real fix** | Introduce `user_media` (Option A), dual-write, backfill from all surviving sources, flip reads, then **re-enable** the `processing_jobs` TTL. | Satisfies AC #4: job cleanup is preserved, but job retention no longer governs library retention. |

Canonical shape of the durable record (details in §4):

```
Table user_media
  PK  user_id        (S)
  SK  media_item_id  (S)   -- "mi_" + sha256(f"{user_id}|{media_key}")[:32]  (deterministic => race-free idempotency, no index needed)
  attrs
    media_key            (S)  canonical content identity, mkey_v1_<sha256>
    title, source_url, source_platform, media_type, duration_seconds, thumbnail_url
    folder_id            (S)  exactly one, defaults to the user's "Uncategorized" folder
    tag_ids              (L)  zero..N user tag ids
    saved_at, updated_at (N/S)
    processing_status    (S)  DENORMALISED snapshot, nullable — library renders without it
    last_job_id          (S)  NULLABLE POINTER, may dangle, never required for a read
    deleted_at, purge_at      set ONLY by the explicit delete use case
  No TTL driven by processing. `purge_at` is the only TTL attribute and only a user-initiated
  deletion may ever write it.
```

Rejected as end states: **Option B** (promote `user_media_submissions` to authoritative) — the table's only reader is dead code, its writer is best-effort, and its rows already contain dangling job pointers, so it must be backfilled anyway and its "it already exists" advantage evaporates (§3.2). **Option C** (permanently remove/lengthen the job TTL) — explicitly violates AC #4, keeps operational and user-owned data in one aggregate rewritten wholesale on every status change, and leaves the `media_item_id == processing_job.id` conflation intact (§3.3). **Option D3** (relational store for the library) — correct modelling but a new operational surface and a monthly cost floor an order of magnitude above DynamoDB at this scale (§3.5).

Two findings outside the strict scope of the question but material to the recommendation, because they mean **the data already lost is unrecoverable**:

1. The archival safety net is fiction. The deployed `media-summarizer-job-archiver` Lambda is a **462-byte no-op placeholder**; it was invoked **144 times** (69 in June, 75 in July) with 0 errors and wrote **0 objects** to the archives bucket (§1.5).
2. **Point-in-time recovery is disabled** on `processing_jobs` and `user_folders` (§1.5).

---

## Table of contents

1. [The current failure mode, with evidence](#1-the-current-failure-mode-with-evidence) — AC #1
2. [The canonical entity model](#2-the-canonical-entity-model) — AC #5
3. [Options compared](#3-options-compared) — AC #2, AC #3
4. [The recommended design in detail](#4-the-recommended-design-in-detail) — AC #4
5. [Deployment and migration strategy](#5-deployment-and-migration-strategy) — AC #6
6. [Retention, deletion, archival, backup, observability](#6-retention-deletion-archival-backup-observability) — AC #7
7. [Side findings worth their own tasks](#7-side-findings-worth-their-own-tasks)
8. [Open questions for the owner](#8-open-questions-for-the-owner)
9. [Sources](#9-sources)
10. [Acceptance-criteria coverage map](#10-acceptance-criteria-coverage-map)

---

## 1. The current failure mode, with evidence

### 1.1 Every library read path resolves through `processing_jobs`

`media_item_id` is not an identifier of a media item. It is literally the primary key of a processing job, and the whole library is read through it.

| Read path | File:line | What it does |
|---|---|---|
| Library list / Search | `media_summarizer/core/services/media_search_service.py:89` | `all_jobs = await database_async.get_processing_jobs_by_user_id(user_id)` — the library **is** the job table |
| Search result projection | `media_summarizer/core/services/media_search_service.py` (`_job_to_search_result`) | returns `"media_item_id": job.id` |
| Media detail | `media_summarizer/api/endpoints/media.py:1292` | `job = await database_async.get_processing_job_by_id(media_item_id)`; `None` → **404 `MEDIA_NOT_FOUND`** (lines 1294-1303); `job.user_id != current_user.id` → 403 (lines 1305-1314) |
| Raw content | `media_summarizer/api/endpoints/media.py:1463` | identical job lookup and identical 404 |
| Artifact access (all types) | `media_summarizer/api/endpoints/artifacts.py:55` | `_get_job_for_user()` resolves the job first; no job → 404 "Media item not found", even though the artifact rows and S3 objects still exist |
| Folder contents / counts | `media_summarizer/utils/database_async.py:736` + `:742-743` | `get_processing_jobs_by_folder_id` fetches all of the user's **jobs** and filters in memory on `job.folder_id` |
| Folder deletion reassignment | `media_summarizer/core/services/folder_service.py:236-242` | iterates jobs, sets `job.folder_id`, `job.touch()`, `update_processing_job(job)` |
| Tag deletion / tag set | `media_summarizer/core/services/tag_service.py` (`delete_tag`, `set_media_tags`) | strips or writes `job.tag_ids` across the user's jobs |
| Organization mutations | `media_summarizer/api/endpoints/media.py:1359` (`patch_media`), `:1388` (`patch_media_tags`) | mutate the job row |

The user-owned organization data is stored *as attributes of the ephemeral job*:

```python
# media_summarizer/core/models/processing_job.py:70-71
folder_id: Optional[str] = None          # Folder this media belongs to (user_folders table)
tag_ids: List[str] = Field(default_factory=list)  # User tag IDs associated with this media
```

### 1.2 …and `processing_jobs` is a TTL table whose clock is reset by processing, not by the user

```hcl
# infrastructure/terraform/dynamodb_core_tables.tf:62-66  (resource processing_jobs, lines 32-77)
ttl {
  attribute_name = "expire_at"
  enabled        = true
}
# and lines just below:
stream_enabled   = true
stream_view_type = "OLD_IMAGE"
```

```python
# media_summarizer/core/models/processing_job.py:91
expire_at: Optional[int] = None  # TTL timestamp for DynamoDB auto-deletion

# media_summarizer/core/models/processing_job.py:250 (inside update_status)
# media_summarizer/core/models/processing_job.py:361 (inside update)
self.expire_at = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
```

So the retention clock is *"30 days since the pipeline last touched this job"*. A media item the user saved, filed in a folder, tagged and never re-processed is deleted 30 days after ingestion finished — together with its title, source URL, folder membership, tags and ownership. AWS deletes expired items "within a few days of their expiration time" and removes them from every GSI/LSI on deletion ([AWS TTL docs](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html)), which is why the disappearance looks gradual and non-deterministic rather than exactly at day 30.

Aggravating detail: `database_async.update_processing_job` (`media_summarizer/utils/database_async.py:360`) performs a **full `put_item(Item=job.to_dynamodb_item())`**. Every worker status write rewrites the whole row, including `folder_id` and `tag_ids`, and re-stamps `expire_at`. A user moving a media into a folder while a worker writes a status transition is a lost update by construction.

### 1.3 What survives versus what dies

| Store | TTL? | Fate |
|---|---|---|
| `processing_jobs` | **YES**, `expire_at` | deleted → library entry, title, source, folder membership, tags, ownership all gone |
| `user_folders` (`dynamodb_core_tables.tf:358-383`) | no | **survives** — empty folders remain visible |
| `user_tags` (`:325-350`) | no | **survives** — tags remain, filter matches nothing |
| `user_media_submissions` (`:148-168`, PK `user_id`, SK `media_key`) | no | **survives**, but only holds `job_id` pointers that now dangle |
| `media_idempotence` (`:130-145`) | no | **survives**, `media_key` → dead `job_id` |
| `media_artifacts` (`:171-216`, GSI `media-item-index`) | no | **survives** as orphans keyed by a `media_item_id` nothing resolves |
| S3 artifact buckets (transcripts, quizzes, …) | no lifecycle rule | **survive** as unreachable objects |
| Algolia index (`media_summarizer/core/services/search_indexing.py`) | no | **survives** — search can return hits whose detail endpoint 404s |

This is exactly the reported symptom: **folders persist while media disappears**, and the divergence is asymmetric because only one of the eight stores has a TTL.

### 1.4 Live AWS dev evidence (eu-west-3, account 125313707865, 2026-08-05)

Owner account `4cd1abcb-c041-44bd-a241-a363217203bf` (`marc.medlock@live.fr`):

| Observation | Value |
|---|---|
| `user_folders` rows for this user | **5** — `Uncategorized` (default), `Test collection`, `Road trip Australia`, `LLM inference`, `GitHub` |
| `user_media_submissions` rows for this user | **6** |
| `processing_jobs` rows returned by GSI `user-index` for this user | **1** — "Jesus Morales", `6b480c78-…`, `expire_at = 1788301872` → **2026-09-01T22:31:12Z** (i.e. this last one is scheduled to disappear too) |
| `user_media_submissions.job_id` values that resolve to an existing job | **1 of 6** — **5 dangling references** |
| `media_idempotence` rows for this user's media | **6**, all stuck at `status: "reserved"`, pointing at mostly-dead jobs |
| `media_artifacts` rows table-wide | **150** rows across **20 distinct `media_item_id`s** (15 of them with a complete set of 4 artifacts) |
| `processing_jobs` rows table-wide | **7** |
| Confirmed orphan artifact groups | `6892a465-…`, `1d9b7c55-…`, `daaf4187-…` (the latter a `ready` quiz artifact in `media-summarizer-quiz-…-dev`) |
| `media_artifacts` rows with **no** `media_item_id` attribute at all | **83 of 150** |
| The 6 other surviving jobs | stale `pending` stubs from 2026-06-08/09 with **no `expire_at` at all** — they survive only because `update_status()` never ran on them |

Read that last row together with §1.2: the only jobs that survived are the ones that **failed to start**. Every job that completed successfully was stamped with `expire_at` and has since been deleted. The TTL is currently selecting *against* successfully processed media.

The 20-vs-7 gap between artifact groups and jobs is the size of the loss: at least 13 fully processed media items still have their artifacts in DynamoDB and S3, and are unreachable because `artifacts.py:55` cannot resolve a job.

### 1.5 The recovery net does not exist

`infrastructure/terraform/archiving.tf` wires a DynamoDB-Streams consumer to archive rows removed from `processing_jobs`:

```hcl
# infrastructure/terraform/archiving.tf:105  (resource aws_lambda_function.job_archiver)
filename = "job_archiver.zip" # Placeholder, will be built by CI/CD
# lines 133-147: event source mapping filtered to eventName = ["REMOVE"]
```

The CI/CD build never happened. `infrastructure/terraform/job_archiver.zip` is **477 bytes** and contains a 462-byte no-op:

```python
"""Placeholder job_archiver Lambda. To be replaced by real code in CI/CD pipeline."""
def lambda_handler(event, context):
    records = event.get("Records", [])
    return {"statusCode": 200,
            "body": json.dumps({"received": len(records), "archived": 0, "placeholder": True})}
```

The real archiver exists in the repo and was never deployed: `media_summarizer/workers/cleanup/job_archiver.py` (91 lines) writes `YYYY/MM/DD/<job_id>.json` with a `deletion_type` of `TTL` or `MANUAL`. The deployed function's `CodeSize` matches the committed placeholder zip byte for byte.

Live consequences:

- Archives bucket: **0 objects**.
- `media-summarizer-job-archiver` invocations: **144** (69 June + 75 July), **0 errors**. It returned HTTP 200 for every deletion it silently discarded. Nothing alarmed, because "0 errors" was the only signal being watched.
- `describe-continuous-backups`: **PITR DISABLED** on `processing_jobs` and on `user_folders`.

Since TTL deletions are ordinary stream `REMOVE` events distinguishable only by `userIdentity.type = "Service"` / `principalId = "dynamodb.amazonaws.com"` ([AWS: working with expired items](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/howitworks-ttl.html)), and nobody consumed them, the deleted rows are gone with no restore path within the 35-day PITR window either. **Recovery must therefore be reconstructive** (§5.3), not a restore.

### 1.6 Secondary damage caused by the same conflation

1. **Deduplication poisoning.** `ProcessingJobSubmissionOrchestrator.submit()` (`media_summarizer/core/media_ingestion/adapters/orchestrators.py`) short-circuits on `already_processed(media_key)` and `_build_duplicate_outcome` returns `media_item_id = existing_job_id`. When that job has been TTL-deleted, re-submitting the *same* URL returns a `media_item_id` that immediately 404s — the user cannot even repair their own library by re-saving. All 6 live `media_idempotence` rows are in this state.
2. **Non-transactional ownership write.** In the same `submit()`, the reservation (`reserve_or_skip`, line ~198), the job creation (line ~212), the folder/tag application (lines ~216-222) and `mark_user_media_submission` (lines ~224-247) are four independent writes, and the last one is wrapped in a `try/except` that only logs a WARNING. Ownership can therefore be missing entirely — consistent with 6 submission rows for 20 artifact groups.
3. **Dead reader.** `media_summarizer/utils/user_media_submissions.py:31` `has_user_already_submitted()` resolves `job_id` through `get_processing_job_by_id` (line 72) and returns `False` ("allow retry") when the job is missing. Grep confirms **zero callers**: the table is written but never read. Its guard `ConditionExpression="attribute_not_exists(user_id)"` (line 114) is the only part of it worth keeping conceptually.
4. **Search/library divergence.** Algolia records (`{media_item_id}_chunk_{i}`, filtered by `user_id`) have no TTL, so Search keeps surfacing media the library no longer has.
5. **No account-deletion cascade.** `DELETE /api/users/{user_id}` (`media_summarizer/api/endpoints/users.py`) calls only `database_async.delete_user(user_id)`. Folders, tags, jobs, artifacts, S3 objects and Algolia records are all left behind. Today the TTL is accidentally doing part of the GDPR erasure work; removing the TTL makes this pre-existing gap explicit and it must be closed in the same effort (AC #7).

---

## 2. The canonical entity model

AC #5. The single sentence that resolves the whole problem:

> **A saved media item is a durable, user-owned entity. A processing job is a disposable unit of work performed on it. Today they are the same DynamoDB row, and that is the bug.**

### 2.1 Entities and cardinalities

```
User (1) ──── (N) SavedMedia            [user_media]  DURABLE, AUTHORITATIVE
                    │
                    │ media_key (content identity, global, N users may save the same content)
                    ├──── (0..N) ProcessingJob   [processing_jobs]  EPHEMERAL, expirable
                    ├──── (0..N) Artifact        [media_artifacts + S3]  durable, FK = media_item_id
                    ├──── (1)    Folder          [user_folders]  membership stored ON SavedMedia
                    ├──── (0..N) Tag             [user_tags]     membership stored ON SavedMedia
                    └──── (0..N) SearchDocument  [Algolia]  DERIVED, rebuildable, never authoritative

UserSubmission (the act of saving) ── (N) ──> (1) SavedMedia    event/log, not authoritative
```

| Entity | Identity | Authoritative for | Lifetime |
|---|---|---|---|
| **SavedMedia** | `(user_id, media_item_id)` | existence in the library, ownership, title, source attribution, folder membership, tags, last known processing status | until the user deletes it or the account is deleted |
| **CanonicalMedia** | `media_key` (`mkey_v1_<sha256>`) | content identity for dedup and artifact reuse | forever (global, user-agnostic) |
| **UserSubmission** | `(user_id, media_key, submitted_at)` | the fact that a save was requested, with its options | log-grade; may be retained short-term or dropped |
| **ProcessingJob** | `job_id` | processing status, step timings, errors, retries | operational; **expirable by TTL** |
| **Artifact** | `artifact_id`, FK `media_item_id` | the produced asset and its status | as long as its SavedMedia lives |
| **Folder** | `folder_id` | folder name, parent, hierarchy — **never a membership list** | until deleted (children reassigned) |
| **Tag** | `tag_id` | tag name/colour — **never a membership list** | until deleted (references stripped) |
| **SearchDocument** | `{media_item_id}_chunk_{i}` | nothing | derived; must be reconcilable from SavedMedia |

Membership deliberately lives on the media item and not on the folder/tag (no adjacency-list duplication, cf. [AWS many-to-many / adjacency-list guidance](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-adjacency-graphs.html)): one media has exactly one folder and N tags, folder/tag counts are computed by aggregating a user's media, and there is exactly one place to write when a media moves.

### 2.2 Update boundaries — who may write what

This is the rule that prevents the recurrence of the current bug.

| Attribute group on `user_media` | Only writer | Mechanism |
|---|---|---|
| `folder_id`, `tag_ids`, `title`, `deleted_at`, `purge_at` | **API use cases** (`folder_service`, `tag_service`, `patch_media`, delete use case) | attribute-level `UpdateItem` |
| `processing_status`, `last_job_id`, artifact roll-ups | **processing pipeline / workers** | attribute-level `UpdateItem` |
| `user_id`, `media_item_id`, `media_key`, `saved_at` | **the create path only**, once | idempotent `PutItem` with `attribute_not_exists(media_item_id)` |
| everything on `processing_jobs` | **processing pipeline only** | unchanged |

Three hard invariants:

- **I1 — No `PutItem` on `user_media` except the idempotent create.** All later writes are attribute-level `UpdateItem`. This directly removes the `database_async.py:360` full-row-rewrite class of lost update.
- **I2 — Only the explicit user-deletion use case may write a TTL attribute (`purge_at`) on `user_media`.** No worker, no status transition, no `touch()`. Contrast `processing_job.py:250` and `:361`, where a TTL stamp is a side effect of a status write — that is precisely how retention leaked from operations into user data.
- **I3 — A read of the library must never require a `processing_jobs` row.** `last_job_id` and `processing_status` are nullable; absence renders as "no processing information", never as 404.

---

## 3. Options compared

AC #2 requires the three named options; AC #3 fixes the nine evaluation dimensions. Two additional options (D2, D3) and one rejected sub-pattern (D4) are included for completeness.

### 3.1 Option A — dedicated durable `user_media` record (RECOMMENDED)

New table owning the library; `processing_jobs` keeps its TTL and becomes operational-only; `media_item_id` is minted by the media aggregate and carried by the job as a foreign key, inverting today's dependency.

- Source-of-truth clarity: **excellent** — one table, one purpose, name says what it is.
- Ownership/dedup: **excellent** — `media_item_id = "mi_" + sha256(user_id|media_key)[:32]` is deterministic, so a repeat save is the *same* item with no index lookup and no race (idempotent `PutItem` + `attribute_not_exists`). Ownership is enforced *structurally* by the partition key: a user physically cannot query another user's partition.
- Folder/tag persistence: **excellent** — attributes on a TTL-free record.
- Lifecycle updates: **excellent** — disjoint writer sets (§2.2), attribute-level updates.
- Query patterns: `Query(user_id)` for the library, `GetItem(user_id, media_item_id)` for detail (strongly consistent, no GSI). Folder/tag/status filtering in memory over the user's partition, which is exactly what `media_search_service.py:89` and `database_async.py:742-743` already do today; task-220 becomes a mechanical substitution rather than a redesign.
- Cost: negligible (§3.8).
- Operational complexity: one new Terraform table + PITR, one feature flag, one backfill script.
- Failure recovery: durable rows + PITR + `media_key` makes reprocessing safely re-derivable; the item survives any pipeline failure.
- Cons: a new table; a backfill; a transitional dual-write; `media_key` must be available at create time (it is — `media_key` is computed before reservation in the ingestion orchestrator).

### 3.2 Option B — extend the existing `user_media_submissions` persistence

Promote the existing `(user_id, media_key)` table (`dynamodb_core_tables.tf:148-168`, no TTL) to the authoritative library record by adding title/folder/tags/status.

- Genuine advantages: the table already exists, already has the right partition key, already has **no TTL**, and its 6 live rows already survived the deletion event.
- Source-of-truth clarity: **poor** — the name means "an event: this user submitted this media"; overloading it as "this user owns this media item" is exactly the kind of semantic conflation that produced the current bug. A rename is a new table in practice.
- Ownership/dedup: good on paper (`ConditionExpression="attribute_not_exists(user_id)"`, `user_media_submissions.py:114`) but the writer is **best-effort** (`try/except` + WARNING in `orchestrators.py:224-247`) and the reader is **dead code with zero callers** that returns "allow retry" when the job is missing (`:31`, `:72`). Both must be rewritten.
- Query patterns: **worse than A.** SK is `media_key`, so the canonical `GET /api/media/{media_item_id}` needs a **new GSI on `media_item_id`** — an eventually consistent hop on the hottest read path, versus a strongly consistent `GetItem` in Option A.
- Migration: **not smaller than A.** Existing rows carry no title, folder, tags or status, and 5 of 6 `job_id` pointers dangle. The same backfill is required, plus a legacy-id reconciliation, plus dangling pointers promoted into an authoritative table.
- Failure recovery: the table's history of silent write failures is now the library's history.
- Verdict: **rejected as end state.** Its only real edge is "no new table", which Terraform makes near-free, while it permanently costs clarity and one extra index on the hot path. Its rows are however a **valuable backfill source** (§5.3).

### 3.3 Option C — remove or lengthen the `processing_jobs` TTL

Delete the `ttl {}` block (`dynamodb_core_tables.tf:62-66`) or push `timedelta(days=30)` (`processing_job.py:250`, `:361`) to years.

- Effort: one line, no migration, effective immediately. **This is why it is the Phase 0 freeze.**
- Source-of-truth clarity: **bad** — the library remains "whatever rows happen to be in the job table", and `media_item_id` remains `processing_job.id`.
- Explicitly violates **AC #4**: job retention *is* library retention. Any future need to prune jobs (cost, PII in error payloads, replaying the pipeline, a bulk cleanup script, a reprocessing migration that recreates jobs) puts the library back at risk. The failure recurs the first time someone reasons about jobs as jobs.
- Lifecycle updates: unchanged and unsafe — full-row `put_item` (`database_async.py:360`) keeps overwriting `folder_id`/`tag_ids` from worker context.
- Growth: the library read path (`media_search_service.py:89` loads *all* of a user's jobs) keeps dragging step timings, error traces and retry history through memory forever, and those payloads are unbounded. Item size grows monotonically with the number of retries.
- Operational: the 6 stale `pending` stubs from June never get cleaned; `archiving.tf` becomes dead infrastructure; job-level PII/error retention becomes unbounded, which is a compliance question of its own.
- Failure recovery: none added.
- Verdict: **mandatory as a temporary freeze, unacceptable as the end state.** TTL is re-enabled in Phase 4 once nothing user-facing reads jobs.

### 3.4 Option D2 — rely on the stream archiver plus restore-on-read

Deploy the real `job_archiver` (§1.5) and rehydrate from S3/Glacier when a read misses.

- Rejected: an archive is a recovery mechanism, not a source of truth. Restoring from GLACIER_IR on a library read is latency-hostile, the objects expire after 365 days (`archiving.tf`), and the pattern makes "is this media in my library?" a probabilistic question. The archiver must nonetheless be fixed (§7) as a safety net for Option A's Phase 4.

### 3.5 Option D3 — relational store for the library (Aurora Serverless v2 / RDS Postgres)

- Real advantages: foreign keys make dangling `job_id` and orphan artifacts *impossible*, `ON DELETE` cascades solve account deletion in one statement, folder counts and tag filters are trivial joins, and folder hierarchy is a recursive CTE instead of `MAX_FOLDER_DEPTH` walking code in `folder_service.py`.
- Rejected for now: a new operational surface (VPC placement, Lambda connection pooling / RDS Proxy, schema migration tooling), a monthly cost floor an order of magnitude above DynamoDB at this scale, and it would require migrating four existing tables to be coherent. Keep as a documented future option if the organization model grows (many-to-many folders, shared libraries, cross-user collections).

### 3.6 Option D4 — store membership on folders/tags (adjacency list)

Rejected sub-pattern: keeping a `media_ids` list on `user_folders`/`user_tags` duplicates membership in two places and reintroduces divergence (the very shape of the current bug, transposed). Membership stays on the media item (§2.1).

### 3.7 Comparison matrix

Scores: ++ strong / + adequate / o neutral / - weak / -- disqualifying.

| AC #3 dimension | A: dedicated `user_media` | B: extend `user_media_submissions` | C: remove/alter job TTL | D3: relational |
|---|---|---|---|---|
| Source-of-truth clarity | **++** one table, one meaning | - semantic overload of an event ledger | **--** library = job table, id conflation persists | ++ |
| Ownership semantics | ++ enforced by partition key | + same PK, but historically best-effort writes | - ownership lives on an expirable row | ++ FK-enforced |
| Deduplication semantics | ++ deterministic id, race-free, index-free | + conditional put, needs the dead reader rewritten | -- dedup resolves to a dead job id (§1.6.1) | ++ unique constraint |
| Folder / tag persistence | ++ TTL-free attributes | ++ TTL-free attributes | - survives only while the job survives | ++ |
| Lifecycle update safety | ++ disjoint writers, attribute-level updates | + achievable, needs the same discipline | -- full-row `put_item` overwrites user data | ++ transactions |
| Query patterns | ++ `GetItem` detail + `Query` list, no GSI | o hot path needs a new GSI on `media_item_id` | + unchanged (already all-in-memory) | ++ joins/aggregates |
| Cost | ++ single-digit $/month at projected scale | ++ same | ++ lowest today, grows with job payloads | - monthly floor + ops |
| Operational complexity | + one table, one flag, one backfill | + no new table, but same backfill + a GSI | ++ one line | -- new datastore |
| Failure recovery | ++ durable + PITR + re-derivable via `media_key` | + durable, but inherits silent-write history | -- no recovery, archiver is a no-op | ++ |
| **Satisfies AC #4** | **YES** | YES | **NO** | YES |

### 3.8 Cost model

Published on-demand rates ([AWS DynamoDB on-demand pricing](https://aws.amazon.com/dynamodb/pricing/on-demand/), us-east-1; Paris is typically a few percent higher, and the pricing page does not list eu-west-3 inline): $0.625 per million write request units, $0.125 per million read request units, $0.25 per GB-month storage, $0.20 per GB-month PITR. All core tables are already `PAY_PER_REQUEST`.

| Scenario | Items | Storage | Writes | Reads | Monthly |
|---|---|---|---|---|---|
| Dev today | ~20 media | < 1 MB | trivial | trivial | **$0.00** (25 GB / 25 WCU-RCU free tier) |
| 1 000 users × 100 media | 100 k × ~1.5 KB | 0.15 GB | 200 k WRU one-off ≈ $0.13 | 10 k library opens × ~19 RRU ≈ 0.2 M RRU | **≈ $0.10** |
| 10 000 users × 300 media | 3 M × ~1.5 KB | 4.5 GB → $1.13 | backfill 6 M WRU ≈ $3.75 one-off; steady state < $1 | 100 k opens × ~57 RRU = 5.7 M RRU ≈ $0.71 | **≈ $2-3** (+ $0.90 PITR) |

The durable library is, at any realistic scale for this product, a rounding error. Cost is not a discriminator between A and B; it only argues against D3.

---

## 4. The recommended design in detail

### 4.1 Table definition

```hcl
# infrastructure/terraform/dynamodb_core_tables.tf (new resource; physical name follows the
# existing convention in that file, injected into the runtime as USER_MEDIA_TABLE)
billing_mode = "PAY_PER_REQUEST"
hash_key     = "user_id"
range_key    = "media_item_id"

ttl { attribute_name = "purge_at", enabled = true }   # user-initiated deletion ONLY (invariant I2)
point_in_time_recovery { enabled = true }             # unlike processing_jobs / user_folders today
stream_enabled   = true
stream_view_type = "NEW_AND_OLD_IMAGES"               # audit + search reconciliation
```

No GSI and no LSI are required for the current access patterns. If a single user's library ever exceeds roughly a thousand items, add an LSI `user_id + saved_at` for paginated recency and an LSI `user_id + "<folder_id>#<saved_at>"` for folder contents — LSIs must be declared at table creation, so **declare them now even if unused**, since they are free when empty and cannot be added later. (An LSI keeps reads strongly consistent, which matters for read-after-save; it caps an item collection at 10 GB per `user_id`, i.e. millions of media per user — not a practical limit here.)

### 4.2 Attributes

| Attribute | Type | Notes |
|---|---|---|
| `user_id` | S | PK. Structural tenant isolation. |
| `media_item_id` | S | SK. `"mi_" + sha256(f"{user_id}\|{media_key}").hexdigest()[:32]` for new saves; **legacy ids preserved verbatim** for migrated rows (the id is opaque and never parsed). |
| `media_key` | S | `mkey_v1_<sha256>`; links to `media_idempotence` and cross-user artifact reuse. |
| `title`, `source_url`, `source_platform`, `media_type`, `duration_seconds`, `thumbnail_url`, `language` | S/N | library display + source attribution. |
| `folder_id` | S | exactly one; defaults to the user's `Uncategorized` folder (`folder_service.ensure_default_folder`). |
| `tag_ids` | L(S) | zero..N. |
| `saved_at`, `updated_at` | N/S | ordering. |
| `processing_status` | S, nullable | denormalised snapshot of the last known job state. Nullable by contract (task-220 AC #6). |
| `last_job_id` | S, nullable | pointer for debugging only; **may dangle**; never dereferenced on a read path (invariant I3). |
| `artifact_status` | M, optional | `{artifact_type: {status, artifact_id}}` roll-up so the library renders availability without a job. |
| `deleted_at`, `purge_at` | S/N | soft delete then purge; written only by the delete use case. |
| `schema_version` | N | forward migrations. |

### 4.3 Write path (idempotent save)

```
compute media_key
media_item_id = "mi_" + sha256(user_id|media_key)[:32]
PutItem user_media  ConditionExpression = attribute_not_exists(media_item_id)
    on success  -> new library entry, folder = requested or Uncategorized, tags = requested
    on ConditionalCheckFailed -> ALREADY SAVED: GetItem and return the existing record
                                 (do NOT overwrite folder_id / tag_ids / title)
then (operational, may fail without losing the library entry):
    media_idempotence reserve_or_skip(media_key)
    if content already processed globally -> attach existing artifacts to THIS user's media_item_id,
        set processing_status = ready         # never return another user's or a dead job's id
    else create processing_job(media_item_id=<durable id>, user_id=...) and enqueue
```

Three properties this buys, mapping to task-219 AC #2/#6/#7:

- The library entry is created **first** and **atomically**; every downstream step is best-effort without risking user-visible data (the inverse of `orchestrators.py:224-247` today).
- Concurrent duplicate submits converge on one item with **no** index read and **no** transaction: the deterministic key makes the conditional put the whole concurrency control.
- The duplicate short-circuit resolves to *the requesting user's own* durable id, fixing §1.6.1. `TransactWriteItems` is deliberately **not** needed here; it would double write cost and add `TransactionCanceledException` handling for no correctness gain ([AWS transactions doc](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html)).

### 4.4 Read paths after the change

| Endpoint | Before | After |
|---|---|---|
| `GET /api/media` + Search | `get_processing_jobs_by_user_id` (`media_search_service.py:89`) | `Query(user_id)` on `user_media`, filter/sort in memory (same shape as today) |
| `GET /api/media/{media_item_id}` | `get_processing_job_by_id` (`media.py:1292`) | `GetItem(user_id, media_item_id)` — strongly consistent, ownership implied by the key |
| `GET /api/media/{id}/raw-content` | `media.py:1463` | same `GetItem` gate |
| `GET /api/artifacts/...` | `_get_job_for_user` (`artifacts.py:55`) | `_get_media_for_user` against `user_media`; artifacts resolve by `media_item_id` through the existing `media-item-index` GSI |
| folder contents / counts | `get_processing_jobs_by_folder_id` (`database_async.py:736`) | aggregate `user_media` by `folder_id` |
| `PATCH` folder / tags | mutate the job | attribute-level `UpdateItem` on `user_media` |
| processing state | the job row itself | `processing_status` on the record, optionally enriched by a job lookup **if it still exists** |

The canonical contract (`docs/CANONICAL_MEDIA_API_CONTRACT.md`, frozen) is unaffected: `media_item_id` stays an opaque string, response shapes are unchanged, no `/api/v1` media endpoint is introduced (task-220 AC #9). The only contract-visible change is that processing fields become explicitly optional.

### 4.5 How AC #4 is satisfied

| Concern | Mechanism |
|---|---|
| Job cleanup preserved | `processing_jobs` TTL is re-enabled in Phase 4 (30-90 days, owner's choice), plus the real archiver deployed. |
| Job retention cannot control library retention | The only pointer from library to job is the nullable `last_job_id`, and invariant I3 forbids dereferencing it on a read path. |
| Library retention driven by the user only | The single TTL attribute on `user_media` is `purge_at`, writable only by the deletion use case (invariant I2). |
| Regression-proofing | A CI/lint check that `user_media` write helpers expose no way to set `purge_at` outside the delete use case, plus the reconciliation alarm in §6.5. |

---

## 5. Deployment and migration strategy

AC #6. Per `AGENTS.md`, the project is **pre-production: no backward compatibility is required and obsolete code is removed rather than deprecated.** The phasing below therefore exists for *data-safety* reasons, not for API compatibility.

### 5.1 Phase 0 — freeze the bleeding (deploy first, independently)

1. Disable `ttl` on `processing_jobs` (`dynamodb_core_tables.tf:62-66`) and apply. DynamoDB stops deleting immediately, whatever `expire_at` values rows already carry. Note that already-expired-but-not-yet-swept items remain readable and billed until deletion, so disabling TTL can even *recover* rows that expired within the last few days ([AWS: working with expired items](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/howitworks-ttl.html)) — apply this before anything else.
2. Enable PITR on `processing_jobs`, `user_folders`, `user_tags`, `media_artifacts`, `user_media_submissions` so that from here on there is a 35-day restore window ([AWS PITR](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery.html)).
3. Snapshot the current state (on-demand backup + `Scan` export to S3) *before* any migration writes.

Phase 0 is reversible by re-applying the previous Terraform and carries no code risk.

### 5.2 Phase 1 — introduce the durable record (dual-write)

Create the table with PITR and streams; deploy code that creates/updates `user_media` on every save behind an env flag (`DURABLE_MEDIA_ENABLED`), while reads still come from `processing_jobs`. Failures of the durable write are logged and alarmed, not swallowed. Rollback: set the flag off; the table is additive and orphaned rows are harmless.

### 5.3 Phase 2 — backfill and reconstruct

Idempotent, re-runnable, `--dry-run` first, emitting a per-row report. Sources in descending order of richness; a later source never overwrites a field already set by an earlier one:

| # | Source | Recovers | Live dev volume |
|---|---|---|---|
| 1 | surviving `processing_jobs` | everything: title, source, `folder_id`, `tag_ids`, status, ownership | 7 rows (1 real + 6 stale `pending` stubs) |
| 2 | `user_media_submissions` | `user_id` + `media_key` + submitted_at → proves ownership even where the job is gone | 6 rows for the owner, **5 with dangling `job_id`** |
| 3 | `media_artifacts` + GSI `media-item-index` | the `media_item_id` of media whose job is gone, and which artifacts already exist | 150 rows / **20 distinct ids**, 15 complete sets |
| 4 | Algolia index records | often the **only** surviving copy of the title, plus `user_id` and `media_item_id` | to be enumerated per user at migration time |
| 5 | S3 artifact buckets (key prefixes) | last-resort existence proof | no lifecycle rule, all objects intact |

Rules:

- **Legacy ids are preserved.** A migrated row keeps `media_item_id = <the id the artifacts and Algolia objects already use>`, so `media_artifacts.media_item_id`, Algolia `objectID`s (`{media_item_id}_chunk_{i}`), mobile caches and deep links all stay valid. **No rewrite of artifacts or Algolia records is required.** Only *new* saves use the deterministic id; mixed id formats are safe because the id is opaque.
- **Dangling `user_media_submissions` references are not repaired, they are superseded.** Each row becomes a `user_media` row keyed by the artifact-derived id when one exists, otherwise by the deterministic id computed from `(user_id, media_key)`; `last_job_id` is left null. The table and `media_summarizer/utils/user_media_submissions.py` (dead reader, §1.6.3) are then deleted in Phase 3.
- **Unresolvable rows are quarantined, never guessed.** The **83 of 150** `media_artifacts` rows with no `media_item_id` attribute, and any artifact group whose `user_id` cannot be established from sources 2-4, go to a report for manual owner review. Ownership is never inferred from a single-user dev environment.
- **`media_idempotence` is repaired**: rows stuck at `reserved` whose job no longer exists are advanced to `processed` when a complete artifact set exists, otherwise reset so the media can legitimately be re-ingested (fixes §1.6.1).
- Idempotency: every write is a conditional `PutItem`/`UpdateItem`; re-running converges. The backfill never deletes or mutates `processing_jobs`, `media_artifacts` or S3.

### 5.4 Phase 3 — flip reads (task-220)

Switch the seven read paths in §4.4, then remove the obsolete code outright (pre-prod policy): `ProcessingJob.folder_id` / `tag_ids` (`processing_job.py:70-71`), `get_processing_jobs_by_folder_id` (`database_async.py:736`), the `user_media_submissions` table and module, and the job-based ownership gate in `artifacts.py:55`. Replace the full-row `put_item` in `update_processing_job` (`database_async.py:360`) with attribute-level updates. Rollback within the phase = flip `DURABLE_MEDIA_ENABLED` off; jobs are still present because TTL is off until Phase 4.

Exit gate (task-219 AC #10, task-220 AC #10-11): in AWS dev, delete a processing job by hand and prove list, Search, folder count, folder open, folder move, tag filter, media detail and artifact access all still work. The `marc.medlock@live.fr` account is the named regression case: after Phase 2 its 5 folders must again contain the recovered media, and after the manual job deletion they must stay populated.

### 5.5 Phase 4 — restore job hygiene

Only once nothing user-facing reads `processing_jobs`: re-enable the TTL (owner-chosen window, 30-90 days), replace `infrastructure/terraform/job_archiver.zip` with a real build of `media_summarizer/workers/cleanup/job_archiver.py`, and alarm on "REMOVE events > 0 while archived objects == 0" so the §1.5 silent failure cannot repeat. Also purge the 6 stale `pending` stubs from June.

### 5.6 Rollback summary

| Phase | Rollback | Data risk |
|---|---|---|
| 0 | re-apply previous Terraform | none (re-enabling TTL would resume deletions — do not) |
| 1 | flag off | none, table additive |
| 2 | delete the backfilled rows (identifiable by `schema_version` + a `backfilled_from` attribute) | none: read-only against all legacy stores |
| 3 | flag off, revert deploy | none while Phase 4 has not run |
| 4 | disable TTL again | rows deleted after re-enabling are archived to S3 if and only if the real archiver is verified first |

**Ordering constraint:** Phase 4 must not be applied before Phase 3's exit gate passes, and Phase 3 must not be applied before Phase 2's report shows zero unresolved *owned* media.

---

## 6. Retention, deletion, archival, backup, observability

AC #7.

### 6.1 Retention

| Data | Retention | Trigger |
|---|---|---|
| `user_media` | **indefinite** | user deletion or account deletion only |
| `processing_jobs` | 30-90 days after the last status transition (Phase 4) | TTL on `expire_at` |
| `media_artifacts` + S3 objects | lifetime of their `user_media` row | cascade on media deletion |
| Algolia documents | lifetime of their `user_media` row | cascade + periodic reconciliation |
| `media_idempotence` | indefinite (global content ledger, no user data) | — |
| Job archives in S3 | GLACIER_IR at day 0, expire at 365 days (`archiving.tf`) | existing lifecycle rule |
| `user_media_submissions` | table deleted in Phase 3 | — |

### 6.2 User-initiated deletion

Soft delete then purge: set `deleted_at` and `purge_at = now + 30 days`; the item is excluded from all reads immediately, and DynamoDB TTL removes it later. A stream consumer on the `REMOVE` event then cascades to `media_artifacts` rows, S3 objects and Algolia documents. Because `media_item_id` is deterministic for new saves, re-saving the same URL after a purge resurrects the same id — **the purge cascade must therefore be complete**, or stale artifacts from a previous life would reattach. This is an explicit test case for task-219.

### 6.3 Account deletion (currently missing — see §1.6.5)

`DELETE /api/users/{user_id}` must become a cascade, in this order: enumerate `user_media` by partition → delete artifacts via `media-item-index` and their S3 objects → Algolia `deleteBy` on `user_id` → delete `user_media`, `user_folders`, `user_tags`, the user's `processing_jobs` → finally the user row. The operation must be idempotent and resumable, and must emit a completion record for erasure evidence. `media_idempotence` rows stay (content-level, no personal data) but any `job_id` or user pointer in them is cleared.

### 6.4 Archival and backup

- **PITR enabled on `user_media`, `user_folders`, `user_tags`, `media_artifacts`** (35-day continuous window; a restore creates a *new* table and TTL settings are not carried over, so the runbook must re-apply TTL configuration after any restore) — [AWS PITR](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery.html).
- An AWS Backup plan (weekly on-demand backup, 90-day retention) for a window longer than PITR.
- A monthly `ExportTableToPointInTime` of `user_media` to S3 as a cheap cold copy and as the input to any future re-model.
- The real `job_archiver` deployed, so job history remains inspectable for post-mortems after TTL returns.
- A documented restore runbook, exercised once in dev: restore `user_media` to a new table, verify counts, swap the `USER_MEDIA_TABLE` env var.

### 6.5 Observability

| Signal | Alarm |
|---|---|
| `durable_media_write_failed` (structured log + metric) | any occurrence — a save whose library row failed is the bug class we are removing |
| Divergence: `count(distinct media_artifacts.media_item_id)` vs `count(user_media)` | daily reconciliation job; alarm on drift > 0 (this is the metric that would have caught the current incident in June) |
| `TimeToLiveDeletedItemCount` on `user_media` | alarm on **any** value not explained by a user deletion (invariant I2 tripwire) |
| Archiver: stream `REMOVE` events processed vs objects written to the archives bucket | alarm when events > 0 and objects == 0 (the exact §1.5 blind spot) |
| Archives bucket object count | alarm on 0 for 24 h while jobs are expiring |
| Algolia orphans: documents whose `media_item_id` has no `user_media` row | weekly sweep, auto-delete + count metric |
| Dangling pointers: `user_media.last_job_id` referencing a missing job | informational gauge only — expected and harmless by design (invariant I3) |
| Per-user library size | gauge; triggers the LSI/pagination work described in §4.1 |
| Account-deletion cascade completion | alarm on incomplete cascades |

The meta-lesson from §1.5 is that success metrics ("0 errors") were monitored while outcome metrics ("objects archived") were not. Every alarm above is deliberately an *outcome* metric.

---

## 7. Side findings worth their own tasks

Not part of task-218's question, but discovered while gathering the evidence and each independently harmful:

1. **The deployed `job_archiver` is a 462-byte no-op** that discarded 144 deletion events (§1.5). The real implementation is in the repo, unshipped.
2. **PITR is disabled** on `processing_jobs` and `user_folders`.
3. **No account-deletion cascade** (§1.6.5) — a GDPR erasure gap today, masked by the TTL.
4. **83 of 150 `media_artifacts` rows have no `media_item_id`** — a separate write-path defect to investigate; these rows are unattributable.
5. **All 6 `media_idempotence` rows are stuck at `reserved`**, so successful processing never advances the global ledger; dedup therefore both mis-fires and points at dead jobs.
6. **6 stale `pending` jobs from 2026-06-08/09 carry no `expire_at`** — jobs that never started are never cleaned, while jobs that succeeded are deleted. The TTL is inverted with respect to value.
7. **`media_summarizer/utils/user_media_submissions.py` is dead code** (zero callers) writing a table nobody reads.
8. **`update_processing_job` rewrites the entire row** (`database_async.py:360`), a lost-update generator for concurrent user and worker writes.

## 8. Open questions for the owner

1. **Job TTL window for Phase 4**: 30, 60 or 90 days after the last status transition? (Recommendation: 90 days, since jobs are the only debugging trail once the library no longer depends on them.)
2. **Soft-delete grace period**: 30 days before purge, or immediate hard delete with cascade? (Recommendation: 30 days, it makes accidental deletion recoverable without a restore.)
3. **Deterministic vs random `media_item_id` for new saves**: deterministic removes the race and the index (§4.3) at the cost of id reuse after a purge. Accept, or prefer a random id plus an LSI on `media_key`?
4. **Backfill scope**: reconstruct only the owner's account (fast, low risk) or all users in dev? How aggressive should Algolia-derived title recovery be?
5. **Cross-user artifact reuse**: when two users save the same `media_key`, share the S3 object and duplicate the lightweight `media_artifacts` row per user (recommended, simple ownership), or share the row itself (cheaper, but ownership becomes many-to-many)?
6. Whether findings §7.1-§7.8 should become separate backlog tasks or be folded into task-219/task-220.

## 9. Sources

Codebase and infrastructure (this repository, commit `3a41cc4`):

- `infrastructure/terraform/dynamodb_core_tables.tf` — `processing_jobs` 32-77 (TTL 62-66), `media_idempotence` 130-145, `user_media_submissions` 148-168, `media_artifacts` 171-216, `user_tags` 325-350, `user_folders` 358-383
- `infrastructure/terraform/archiving.tf` — 105 (placeholder Lambda), 133-147 (`REMOVE` event filter); `infrastructure/terraform/job_archiver.zip` (477 bytes)
- `media_summarizer/core/models/processing_job.py` — 70-71, 91, 250, 361
- `media_summarizer/core/services/media_search_service.py` — 89 and `_apply_filters` / `_job_to_search_result`
- `media_summarizer/utils/database_async.py` — 314-317, 360, 736, 742-743
- `media_summarizer/api/endpoints/media.py` — 434, 1292, 1294-1303, 1305-1314, 1359, 1388, 1463
- `media_summarizer/api/endpoints/artifacts.py` — 55
- `media_summarizer/api/endpoints/users.py` — `DELETE /{user_id}`
- `media_summarizer/core/media_ingestion/adapters/orchestrators.py` — `submit()` ~198, ~212, ~216-222, ~224-247
- `media_summarizer/utils/user_media_submissions.py` — 31, 72, 114; `media_summarizer/utils/media_idempotence.py`
- `media_summarizer/core/services/folder_service.py` — 236-242, 266-304; `media_summarizer/core/services/tag_service.py`
- `media_summarizer/core/services/search_indexing.py`; `media_summarizer/workers/cleanup/job_archiver.py`
- `docs/CANONICAL_MEDIA_API_CONTRACT.md` (frozen contract); `AGENTS.md` (pre-production policy)

Live AWS dev inspection, 2026-08-05, account `125313707865`, region `eu-west-3`: `dynamodb query/scan/get-item` on the six core tables, `dynamodb describe-table` and `describe-continuous-backups`, `s3api list-objects-v2` on the archives bucket, `lambda get-function` on `media-summarizer-job-archiver`, and CloudWatch `Invocations`/`Errors` for June and July 2026.

External documentation:

- AWS — Expiring items by using DynamoDB Time to Live (TTL): https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html
- AWS — Working with expired items and TTL (deletion delay, still readable/billable until swept, `userIdentity.type = "Service"` in Streams): https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/howitworks-ttl.html
- AWS — Point-in-time recovery for DynamoDB: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/PointInTimeRecovery.html
- AWS — Amazon DynamoDB Transactions: how it works (`TransactWriteItems` limits, `ClientRequestToken` idempotency, 2x capacity): https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html
- AWS — Best practices for managing many-to-many relationships (adjacency lists, materialised graphs): https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-adjacency-graphs.html
- AWS — DynamoDB Streams and change data capture: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Streams.html
- AWS — DynamoDB on-demand pricing: https://aws.amazon.com/dynamodb/pricing/on-demand/
- Alex DeBrie — The What, Why, and When of Single-Table Design with DynamoDB (and when *not* to use it: prefer flexibility over efficiency for evolving applications): https://www.alexdebrie.com/posts/dynamodb-single-table/
- Martin Fowler — DDD_Aggregate (aggregate boundaries and transactional consistency, the framing used in §2.2): https://martinfowler.com/bliki/DDD_Aggregate.html

## 10. Acceptance-criteria coverage map

| AC | Where |
|---|---|
| #1 failure mode documented with evidence | §1 in full — §1.1 read paths with file:line, §1.2 TTL config, §1.3 survives-vs-dies, §1.4 live AWS numbers, §1.5 no recovery, §1.6 secondary damage |
| #2 three named options compared | §3.1 (A), §3.2 (B), §3.3 (C), plus §3.4/§3.5/§3.6 for completeness, matrix in §3.7 |
| #3 nine evaluation dimensions per option | §3.1-§3.6 prose + §3.7 matrix + §3.8 cost model |
| #4 job cleanup preserved, retention decoupled | §4.5, and the Phase 0 / Phase 4 split in the Recommendation and §5.1/§5.5 |
| #5 canonical relationships defined | §2.1 entities and cardinalities, §2.2 update boundaries and invariants I1-I3 |
| #6 deployment and migration strategy | §5.1-§5.6 (surviving records, dangling submissions, idempotent writes, rollback, pre-prod policy) |
| #7 retention/deletion/account-deletion/archival/backup/observability | §6.1-§6.5 |
| #8 clear recommendation + Owner Validation with `owner_decision: pending` | front-matter, `## Owner Validation`, `## Recommendation` |
