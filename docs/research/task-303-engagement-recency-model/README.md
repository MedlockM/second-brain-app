---
owner_decision: ok   # pending | ok | abandoned | redo | more
---

# Benchmark : the engagement-recency model behind the Inbox "Continue learning" row

## Owner Validation

**Decision**: Recommandation
**Validated at**: _(date ISO à remplir par l'owner)_

---

## Recommendation

Build **"Continue learning" as an open-based recency row, stored as one attribute on the
things themselves** — not as a reading-progress model, not as an event log, not as a new
table, not on the device.

Concretely, five decisions:

1. **Semantics: `last_engaged_at` = the last time the user asked this media or this
   collection to produce or show them something.** Exactly two events stamp it: *an
   artifact generation was launched* (`POST /api/artifacts`, including the deduplicated
   `200` path) and *an artifact was opened and its content loaded* (the artifact viewer
   reports it explicitly). Opening a media detail screen does **not** count. Reading the
   transcript does **not** count in v1 — section 2.3 explains why that is a consequence of
   the current tab layout, and names the single change that would make it worth adding.
2. **Storage: server-side**, one nullable ISO-8601 attribute `last_engaged_at`:
   - on `user_media_v1`, plus **one new sparse GSI `engaged-index` (`user_id` HASH,
     `last_engaged_at` RANGE)** with an `INCLUDE` projection carrying the tile fields;
   - on `user_folders_v1`, **with no new index** — the existing hash-only `user-index`
     already returns every folder of a user in a single `Query` with an `ALL` projection,
     and the ordering happens in Python (section 7).
3. **Write path: two explicit server-side writes, never a `GET` side effect.**
   `POST /api/artifacts` stamps the scope it just accepted; a new
   `POST /api/engagements {kind, id}` returning `204` is fired once per screen mount by the
   artifact viewer after the content resolves. Both writes are best-effort (swallow, log,
   never block the user's action — the `quota_enforcer._debit` pattern) and dampened by a
   ~60 s conditional write so a re-open storm is one write, not twenty.
4. **Read path: one dedicated, render-ready endpoint** `GET /api/engagements/recent?limit=12`
   returning a single merged, already-sorted list of media *and* collection entries with the
   fields the tile draws (`title`, `creator_name`, `image_url`, `item_count`,
   `preview_images`). No client-side join against `/api/media`, and no aggregate `/api/home`
   (section 6). A 90-day freshness window is enforced for free as a sort-key range
   condition, so the row empties itself and the section disappears.
5. **Deletion needs no new code at all.** The signal is an attribute of the row it
   describes: deleting the media or the collection deletes the signal, in the same write.
   Nothing is added to the purge cascade, to `delete_all_for_user`, to the folder-deletion
   path, or to the account-deletion inventory. That property is the main reason this shape is
   recommended over a dedicated activity table (section 4).

**Why not the alternatives, in one line each.** *Device-local storage*: the app has no
key/value store today (`expo-secure-store` only), the row would be per-device and would
vanish on every reinstall and every dev-client rebuild, and its only advantage (offline
writes) is worthless for a row whose content is fetched from the server anyway (section 3).
*A dedicated `user_activity` table*: it is the only shape that answers both kinds in a single
`Query`, but that advantage is illusory — the rows hold ids, so the read still needs a
hydration round trip, which lands it at 3-4 sequential calls instead of 2 concurrent ones,
and it re-introduces the exact failure class this repo already paid for once, a store that
can hold pointers to destroyed content (section 4, Option B). *Deriving the row from
`media_artifacts`*: covers generations only, needs a second store for opens anyway, and pays
a new dense GSI on the busiest table (section 4, Option C).

**The one thing the implementer must not miss**: `database_async.update_folder()` writes a
**full `put_item` of `Folder.to_dynamodb_item()`**, so any attribute the `Folder` model does
not round-trip is silently erased the next time a collection is renamed. `Folder` must carry
`last_engaged_at` in the model, in `to_dynamodb_item` and in `from_dynamodb_item`.
`user_media` has no such hazard — invariant I1 makes `create` the module's only `put_item`
(section 7.2).

---

## 1. What is being decided, and what is not

The Inbox rework (task-307) asks for a "Continue learning" row. There is no engagement signal
in the system today: `user_media_v1` records `saved_at` (when the user added the item) and
`updated_at` (when a pipeline last touched the row), and `media_artifacts_v1` records
`created_at` (when an artifact was generated). Nothing records that a human *consumed*
anything. So the row cannot be built without adding a signal, and the shape of that signal is
what this benchmark decides.

Out of scope, per the task: the cover-image and creator-name extraction settled by task-302
(`thumbnail_url`, `creator_name`, presigned cover URLs, `expo-image` cache keys — this
benchmark consumes them, it does not revisit them), and any visual design owned by task-307.

Two constraints from the task are treated as hard: **one store, not two** (nothing is
deployed; there is no transition to stage), and **collections are first-class** — a
media-only answer is a rejected answer.

### 1.1 The state of the code this design has to fit

| Fact | Where | Consequence for this design |
| --- | --- | --- |
| `user_media_v1`: PK `user_id`, SK `media_item_id`; LSIs `saved-at-index`, `folder-index`; GSI `media-key-index`; TTL on `purge_at`; stream `NEW_AND_OLD_IMAGES`; `prevent_destroy` + deletion protection | `infrastructure/terraform/modules/platform/dynamodb_user_media.tf` | A **GSI** can be added in place; an **LSI** cannot (4.1) |
| `user_folders_v1`: PK `id`; single GSI `user-index` = `user_id` HASH only, projection `ALL` | `dynamodb_core_tables.tf` | No server-side ordering of folders is possible today; sorting happens in Python (7.1) |
| `create` is the only `put_item` in the `user_media` store (invariant I1); every other mutation is an attribute-level `update_item` with an allow-list | `media_summarizer/utils/user_media.py` | A new attribute on a library row cannot be clobbered by a metadata refresh |
| `update_folder(folder)` writes `put_item(folder.to_dynamodb_item())` | `media_summarizer/utils/database_async.py:1019` | A new attribute on a folder row **is** clobbered on rename unless the model round-trips it (7.2) |
| `update_attributes` always appends `updated_at = :updated_at` to the SET expression | `media_summarizer/utils/user_media.py:456` | The engagement stamp must **not** go through it: it would bump `updated_at`, which task-302 uses to build the `expo-image` cache key, invalidating every cover on every open |
| `purge_at` / `deleted_at` have a single legal writer, enforced in CI | `scripts/check_purge_at_writers.py` | The read path must filter soft-deleted rows with `attribute_not_exists(deleted_at)`, not with a `":deleted_at"` binding, which the guard's regex would flag |
| `list_library_for_user` reads the **whole** user partition with `ConsistentRead: True`, and `GET /api/folders` already does that too (via `count_media_per_folder`) | `user_media.py:166`, `folder_service.py:121` | A full-partition read for collection counts is an already-accepted cost in this codebase, not a new one |
| The artifact viewer loads content in a mount effect; `ArtifactContentResponse` already carries `scope` and `scope_id` | `mobile/app/artifacts/[artifactId].tsx:141`, `api/endpoints/artifacts.py:473` | The client already knows what to report, with no extra fetch |
| `apiRequest` replays a failed request once after refreshing a 401 | `mobile/src/services/apiClient.ts:16` | Any write must be idempotent under a duplicate delivery (5.4) |
| Reader (transcript) is the **default** tab of the media detail screen | `mobile/app/media/[id].tsx:398` | "Transcript displayed" and "media opened" are the same event today (2.3) |
| `MediaService.listMedia()` sends no `limit`, and the endpoint defaults to `limit = 20` | `mobile/src/services/mediaService.ts:74`, `api/endpoints/media.py:630` | A client-side join against the already-loaded library list is wrong for anything past the 20 newest saves (6.2) |

---

## 2. Question #1 — what counts as "engagement"

This is the question the owner flagged as the one to arbitrate, so it is answered first and in
full. Two families were considered.

### 2.1 The two families

| | **Open-based** (recommended) | **Progress-based** |
| --- | --- | --- |
| Signal | a timestamp, overwritten | a timestamp **and** a position/percentage |
| Written by | a discrete user action (launch a generation, open an artifact) | a scroll/dwell listener, throttled |
| Writes per session | 1-2 | 5-40, depending on the throttle |
| Client work | one `POST` per screen mount | a scroll listener, a denominator, a resume-on-open, a "finished" rule |
| Answers "where was I?" | no | yes |
| Answers "what was I working on?" | yes | yes |
| Failure mode | an entry the user only glanced at | a resume position that jumps (font size, rotation, re-render) |
| Prior art | Spotify *recently played* (a timestamped list, no position) | Readwise Reader (`reading_progress` + `first_opened_at` + `last_opened_at`, and an explicit `PATCH`), Kindle/Pocket |

Readwise Reader is the closest product to this app, and it is worth noting *how* it splits the
two: `reading_progress` is a float the client computes and pushes explicitly, while
`first_opened_at` / `last_opened_at` are separate fields, and `seen` is a separate flag again
([Reader API](https://readwise.io/reader_api)). Even a product that tracks position keeps "I
opened this" as its own, cheaper signal. Spotify's *recently played* is the pure form of what
task-307 asks for: a capped, timestamped list of things you interacted with, with no position
at all
([Web API reference](https://developer.spotify.com/documentation/web-api/reference/get-recently-played)).

**Progress is rejected for v1**, for three reasons that are specific to this app and not to
the general merits of the idea:

- **Most of what this app produces has no meaningful "middle".** The artifacts are short
  structured documents (a 3-5 bullet short summary, a quiz, a set of flashcards). A percentage
  on a five-bullet list is noise, and a resume position on it is worse than none. The one
  genuinely long text is the raw transcript — which is exactly the surface the open-based
  model deliberately does not count (2.3).
- **It needs a stable denominator the app does not have.** Progress needs "position / total",
  and total is content height, which changes with font size, device, orientation and Markdown
  rendering. Storing a scroll offset makes resume wrong on a second device; storing a
  percentage of rendered height makes it wrong after a re-render. Getting this right is a
  project of its own, and it is not what the row needs.
- **It buys nothing the row displays.** "Continue learning" as specced in task-307 renders a
  title, a cover, a creator and (for collections) an item count. There is nowhere to put a
  progress bar yet, and a signal nobody can see is a signal nobody can debug.

### 2.2 The recommended definition, case by case

`last_engaged_at` is stamped by **exactly two events**, on either kind of subject (a media or
a collection):

- **E1 — a generation was launched.** `POST /api/artifacts` accepted a request for this scope.
  Stamped at request time, server-side, including the deduplicated `200` response (the user
  asked; the fact that the answer already existed is an implementation detail they never see).
- **E2 — an artifact was opened and rendered.** `GET /api/artifacts/{id}/content` returned a
  body the viewer actually displayed, and the viewer reported it once.

Every case the task asks about, decided:

| Case | Counts? | Why |
| --- | --- | --- |
| The user opens a media detail screen | **No** | This is the single most consequential "no". A detail-screen open makes the row a *recently tapped* list, which (a) duplicates "Recently added" for anything saved this week, (b) fires on accidental taps and on back-navigation, (c) admits items that have nothing to continue — a media whose processing is still queued has no artifact and no transcript, so the tile would invite the user to resume something that does not exist yet, and (d) multiplies write volume by the ratio of browsing to working, which is the largest factor in the whole design. |
| The user reads the transcript | **No in v1** | See 2.3 — a consequence of the current tab layout, not a judgement about transcripts. |
| A generation is in flight (`queued` / `generating`) | **Yes** | Launching a generation is the strongest intent signal the app has, and the wait is precisely when the user needs a way back. The row makes no readiness claim: the tile links to the media or the collection, whose own screen already renders the artifact's live status. This also gives the row its first entries on a brand-new account, before anything has been opened. |
| The user re-opens the same artifact | **Yes — it moves, it does not duplicate** | One row per subject, timestamp overwritten. Guaranteed structurally: there is exactly one attribute on one item to write, so duplication is not representable. Subject to the 60 s dampener (5.3). |
| A generation fails | The entry stays | The engagement happened. The media's own screen shows the failure and offers the retry. Removing the entry on failure would hide the one place the user can act. |
| A collection artifact is generated or opened | **Yes**, on the collection | `scope="folder"` in the existing artifact contract; identical handling, different subject. |
| The media or collection is deleted | The entry disappears immediately | The attribute is on the deleted row. Soft-deleted rows are filtered on read by `attribute_not_exists(deleted_at)`. |
| A background job touches the row (transcription finishing, a title being derived, a cover being re-hosted) | **No** | These write `updated_at`, never `last_engaged_at`. Keeping the two apart is why the stamp does not go through `update_attributes` (1.1). |

### 2.3 Why the transcript is excluded — and the exact condition to revisit

Not because reading a transcript is not engagement. Because **the app cannot currently
distinguish it from opening the media at all**: `mobile/app/media/[id].tsx:398` initialises
`activeTab` to `"reader"`, so the transcript is what the detail screen shows on arrival. "The
user read the transcript" and "the user tapped the item" are the same event, and counting it is
the *detail-screen open* option rejected above.

Separating them requires a dwell-or-scroll threshold ("the reader was visible for N seconds"
or "the user scrolled past the first screenful") — which is the progress-based model arriving
through the back door, with all of its costs and none of its benefits.

**The condition under which the owner should choose progress instead**: if the transcript
reader becomes a first-class reading surface (its own route, pagination or resume, long-form
typography), then a real `reading_progress` on the media row becomes worth its cost, and this
benchmark's answer to question #1 should be revisited as a whole rather than patched. The
recommended shape survives that change without a rewrite: the same `last_engaged_at` attribute
and the same index keep working, and `reading_progress` becomes an additional attribute
projected into the same index.

---

## 3. Question #2 — device or server

**Server.** Not a close call, and the reasons are specific enough to record so the question is
not reopened later.

| Criterion | Device-local | Server-side |
| --- | --- | --- |
| Dependency cost | The app has **no** key/value store: `mobile/package.json` ships `expo-secure-store` and nothing else — no `AsyncStorage`, no MMKV. A new native dependency, in an Expo SDK 55 app, for a row on one screen. | None. The write is one `fetch`; the read is one endpoint. |
| Cross-device | Wrong by construction. Two devices show two different rows, and neither is "the" answer. | One answer per account. |
| Reinstall / rebuild | Lost. Including on **every simulator reinstall and every dev-client rebuild**, which is the owner's own daily loop: the feature would appear broken during development more often than it works. | Survives. |
| Offline write | Works. | Fails (swallowed). |
| Offline value | **Nil.** Every tile the row renders (title, cover URL, creator, item count) comes from server data the client does not hold. A local timestamp with nothing to point at is not a row. | n/a |
| Write volume seen by the backend | Zero. | ~3 write units per engagement, one extra query per Inbox open (section 8). |
| Debuggability | Invisible: no way to inspect why a user's row looks wrong. | Inspectable with the AWS CLI against `-dev`, like every other invariant in this repo. |

The only criterion device-local wins is offline writes, and it wins it in a case that cannot
render. Note also that the offline argument is weaker than it looks even in principle: the two
events that count (2.2) are *a request to the server* and *a response from the server*, so if
the network is down, neither event happens.

---

## 4. Question #3 — the shape of the server-side signal

Four shapes were compared: three distinct designs plus one variant of the second. The
comparison criteria are the ones the task asks for.

### Option A — an attribute on the subject + one sparse GSI (**recommended**)

```
user_media_v1                     (unchanged keys)
  + last_engaged_at   S   ISO-8601, absent until the first engagement
  + GSI engaged-index : user_id (HASH) / last_engaged_at (RANGE)
      projection INCLUDE [ title, creator_name, thumbnail_url, media_type, deleted_at ]

user_folders_v1                   (unchanged keys, unchanged indexes)
  + last_engaged_at   S   ISO-8601, absent until the first engagement
```

The index is **sparse**: DynamoDB only writes an index entry for items that carry the indexed
key, so it holds one entry per *engaged* item, not one per library row
([Using Global Secondary Indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.html)).
Reading the row is one `Query` on `engaged-index`, `ScanIndexForward=False`, `Limit=cap`, with
a range condition `last_engaged_at > :window_start` that gives the freshness window for free,
and `FilterExpression="attribute_not_exists(deleted_at)"` to drop rows the user has soft-deleted
but the TTL has not yet swept. The `INCLUDE` projection makes the result **render-ready with no
table fetch** — which AWS's own guidance recommends for exactly this case, noting that as long
as index entries stay under 1 KB the extra projected attributes cost nothing
([General guidelines for secondary indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-indexes-general.html):
"as long as the index items are small, you can project more attributes at no extra cost").

### Option B — a dedicated `user_activity` table, one row per (kind, subject)

```
user_activity_v1
  PK user_id      S
  SK subject_key  S    "media#<media_item_id>" | "collection#<folder_id>"
  engaged_at      S
  expires_at      N    TTL, engaged_at + 90d
  LSI engaged-index : user_id (HASH) / engaged_at (RANGE)   -- new table, so an LSI is possible
```

One `Query`, one partition, **strongly consistent**, both kinds interleaved and ordered by the
LSI, and old rows swept for free by TTL (TTL deletes are not charged as write operations,
[How TTL works](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/howitworks-ttl.html)).
No schema change on either `prevent_destroy` table.

Its cost is that the rows hold **ids, not content**. Rendering needs a hydration step:
`BatchGetItem` on `user_media` for the media ids plus a `user-index` query for the folders — and
that step is *sequential* after the activity query, because the keys are its output.
Denormalising the title and cover into the activity row to avoid it is a stale-data trap: a user
can rename a media, a cover can be re-hosted after the fact, and a collection can be renamed,
none of which would update a copy stored elsewhere.

Its second cost is deletion coherence. The table can hold pointers to content that no longer
exists — after a soft delete, after a TTL purge, after a folder deletion, after an account
erasure. Hydration makes those pointers *invisible* (a missing subject drops out of the
response), so the row never resurfaces deleted content; but the rows themselves linger until
TTL, the account-deletion inventory in `core/services/account_deletion_service.py` gains an
entry, and the guarantee moves from *structural* ("there is nothing to leak") to *procedural*
("the filter is correctly written"). This repo has a scar in exactly that spot: the `user_media`
stream cascade, the daily reconciliation and invariants I1/I2 all exist because a write path
once touched rows nobody intended it to touch.

### Option B' — the same table, event-shaped (one row per event)

```
PK user_id / SK "<engaged_at>#<uuid>"     append-only
```

Cheapest write (one `PutItem`, no read-modify-write, no index-key churn), natural descending
order on the sort key, TTL prune. But the read must **de-duplicate**: ten opens of the same
artifact are ten rows, so producing twelve distinct subjects means reading an unbounded number
of rows and collapsing them outside the database. It also grows without bound between TTL
sweeps, and TTL is explicitly best-effort ("typically deletes expired items within a few days",
same page), so the read can never assume the prune has happened. The upside — a genuine event
history for analytics — is not something this project has asked for.

### Option C — derive the row from `media_artifacts_v1` + a separate open store

`media_artifacts_v1` already records every generation with a `created_at` and a `scope_key` of
the form `<user_id>#media#<media_key>` or `<user_id>#folder#<folder_id>`, indexed by
`scope-index` (`scope_key` HASH / `created_at` RANGE). "Recently generated" is therefore
*almost* free — but only per scope: there is no `user_id`-partitioned index, so answering "this
user's most recent generations" needs a **new dense GSI** (`user_id` / `created_at`) on the
table with the highest write rate in the system, and `scope_key` must then be parsed back into a
`media_key`, which is **not** the `media_item_id` the UI navigates with (it is content-addressed
and shared across saves), requiring a `media-key-index` lookup per row. And it still says
nothing about *opens*, so it needs Option A or B alongside it. Two stores for one row: rejected
on the task's own "one store" constraint.

### Comparison

| Criterion | **A — attribute + sparse GSI** | B — activity table (upsert) | B' — activity table (events) | C — derive from artifacts |
| --- | --- | --- | --- | --- |
| Writes per interaction | 1 base `UpdateItem` + 1 index write on the first engagement, 2 (delete + put) on later ones | 1 `PutItem` + 1 LSI write | 1 `PutItem` + 1 LSI write | 0 for generations, but needs A or B for opens |
| Index / table storage | Sparse: 1 entry per engaged item, ~250 B, rounded to 1 KB for billing | 1 row per engaged subject + LSI entry | 1 row **per event**, unbounded until TTL | New **dense** GSI: 1 entry per artifact ever created |
| One query for both kinds? | **No** — 2 queries (media GSI + folders `user-index`), issued **concurrently** | **Yes** for the ids, **no** for the render: +1 `BatchGetItem` +1 folders query, **sequentially** | Same as B, plus read-time de-dup | No |
| DynamoDB calls per Inbox open | **2** (3 when the row contains a collection, 6.4) | 3-4, partly sequential | 3-4 + de-dup | 4+ |
| Render-ready in one hop | **Yes** (`INCLUDE` projection) | No (hydration mandatory) | No | No |
| Read consistency | Eventually consistent (a GSI cannot be read consistently) | **Strongly consistent** | Strongly consistent | Mixed |
| Purge cascade impact | **None.** The signal is an attribute of the row; the row's deletion is the signal's deletion | Orphan rows on soft-delete, TTL purge and folder deletion; invisible thanks to hydration, but present | Same, one per event per subject | Same |
| Account deletion impact | **None.** No new table, no new entry in `_USER_PARTITION_TABLES` | +1 table in the inventory and in the ordered purge | Same | Same |
| Schema churn on protected tables | 1 attribute + 1 online GSI on `user_media`; 1 attribute on `user_folders` | **None** | None | New GSI on `media_artifacts` |
| New Terraform / env / IAM surface | GSI only. No env var. **No IAM change** — `local.table_arns` already wildcards the index ARNs | New table, new env var, new store module, PITR/protection decisions | Same | New GSI |
| Freshness window | Free (sort-key range condition) | Free (LSI range condition) + TTL | TTL only | Filter |
| Row moves instead of duplicating | Structural (one attribute on one item) | Structural (upsert on a fixed SK) | Requires read-time de-dup | n/a |
| Net new code | 1 write helper, 1 endpoint, 1 client call, 3 lines in the `Folder` model | + a store module, + hydration, + deletion wiring in 4 places | Same + de-dup | Highest |

**A is recommended.** The decisive comparison is A against B, and it turns on two points:

- **B's headline advantage does not survive contact with the read path.** "One query answers
  both kinds" is true of the ids and false of the response: because activity rows hold no
  content, B ends up making *more* round trips than A, and its extra ones are sequential where
  A's two are concurrent. A is render-ready in one hop; B never is.
- **A is deletion-proof by construction, B by procedure.** A adds nothing to the cascade,
  nothing to `delete_all_for_user`, nothing to the account-deletion inventory, and creates no
  class of orphan — because there is no separate thing to orphan. Given that this table's entire
  surrounding apparatus (stream cascade, daily reconciliation, the single-writer CI guard)
  exists because deletion coherence broke once, that is worth more than B's strong consistency
  and its untouched schema.

What A concedes, stated plainly: two queries instead of one; an eventually consistent read
(5.5); two index writes per engagement after the first; and the `Folder` model fix of 7.2. All
four are addressed below.

### 4.1 Why a GSI and not an LSI on `user_media`

An LSI would be the natural fit (same partition key, different sort key, strongly consistent
reads) — and it is **impossible**. LSIs can only be created with the table
([Working with Local Secondary Indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/LSI.html)),
which is why `dynamodb_user_media.tf` carries a comment saying exactly that, and the Terraform
provider marks `local_secondary_index` as *"Forces new resource"*
([provider docs](https://raw.githubusercontent.com/hashicorp/terraform-provider-aws/main/website/docs/r/dynamodb_table.html.markdown)).
On a table with `prevent_destroy`, deletion protection and PITR, adding an LSI means recreating
the library. Not an option, and not necessary.

A GSI, by contrast, is an in-place `UpdateTable`: "the table continues to be available while the
index is being built", the index cannot be queried until it is `ACTIVE`, base-table reads
performed during the backfill are not charged, and progress is observable via
`OnlineIndexPercentageProgress`
([Managing global secondary indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.OnlineOps.html)).
Quotas are not a concern: 20 GSIs and 5 LSIs per table; `user_media` uses 1 GSI and 2 LSIs
([General guidelines for secondary indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-indexes-general.html)).

Two Terraform traps to name, since both produce confusing failures:

- The new `attribute { name = "last_engaged_at" type = "S" }` block must be added **at the same
  time as the index that uses it**. The provider documents that attributes must only be declared
  when they are a table or index key, and that "adding attributes not used in these scenarios
  causes an infinite plan loop".
- Only one GSI can be created per `UpdateTable` call. That is a single index here, so it is a
  non-issue — but it means this change cannot be batched with a second new index in the same
  apply later on.

---

## 5. Question #4 — the write trigger

### 5.1 The trigger, precisely

| Event | Who writes | Where |
| --- | --- | --- |
| E1 — generation launched | **The server**, inside the existing handler, after the generation is committed (including the deduplicated `200` path) | `media_summarizer/api/endpoints/artifacts.py`, `create_artifact` (:173) |
| E2 — artifact opened and rendered | **The client**, once per screen mount, after `fetchContent` resolves, via a new `POST /api/engagements` returning `204` | `mobile/app/artifacts/[artifactId].tsx:141`, calling a new endpoint |

E1 needs no client change and no new contract: the handler already knows the user, the scope, the
scope id and the instant.

E2 needs one new endpoint, whose body is `{ "kind": "media" | "collection", "id": "<id>" }`. The
client has both values already — `ArtifactContentResponse` returns `scope` and `scope_id`.
Ownership is validated by the logic already written for this exact purpose,
`artifacts._assert_scope_owned` (:148): a media scope is checked with
`user_media_store.get_user_media`, a folder scope with `database_async.get_folder_by_id` plus a
`user_id` comparison. An unowned or unknown subject is a `404`, and nothing is written.

### 5.2 The `GET` side effect, judged explicitly

The obvious shortcut is to stamp the engagement inside `GET /api/artifacts/{id}/content`: no new
endpoint, no client change, and the server already knows everything. **Rejected**, on four
grounds, in increasing order of how concretely they bite:

1. **HTTP semantics.** `GET` is a safe method: "an application should not allow these requests to
   alter its state"
   ([MDN, Safe (HTTP methods)](https://developer.mozilla.org/en-US/docs/Glossary/Safe/HTTP)). The
   usual and legitimate exception is incidental server-side bookkeeping the client cannot observe
   — a log line, a counter. This is not that: it is user-visible state that reorders a screen the
   user will see next.
2. **The client already replays `GET`s.** `mobile/src/services/apiClient.ts:16` refreshes the
   token and replays the request once on a `401`. A token expiring mid-read would produce two
   engagement writes. The dampener (5.3) makes that harmless, which is precisely the problem: the
   method is being made to carry an intent it cannot express, and the damage is hidden rather
   than avoided.
3. **`expo-router` 55 can render a screen the user never opened.** `router.prefetch()` is
   documented as "Prefetch a screen in the background before navigating to it", and the router
   emits a `PagePreloadedEvent` for a page "rendered as part of a preload (e.g.
   `router.prefetch()`) and is not currently focused", which may be invalidated or unmounted
   without ever gaining focus
   ([expo-router API](https://docs.expo.dev/versions/latest/sdk/router/)). A preloaded artifact
   screen **runs its mount effect** and therefore its content fetch. Any future prefetch — a
   plausible optimisation for exactly this row — would silently start recording engagements for
   artifacts nobody opened. With an explicit `POST` fired from a focused screen, that failure is
   not available.
4. **The endpoint's caller set is not fixed.** A polling loop, a "refresh" button or a share-sheet
   preview reading the same content endpoint would each inflate the signal, and the inflation
   would be invisible.

For fairness, the in-repo precedent that points the other way: `GET /api/folders` calls
`folder_service.ensure_default_folder()` (`folder_service.py:121`), which **creates** a row. That
is a *get-or-create*: idempotent, convergent, and it produces the same state no matter how many
times it runs. A recency stamp is a monotone clock whose value depends on *when* the call
happened — the opposite kind of write. The precedent does not extend.

### 5.3 Throttling

Two layers, deliberately redundant:

- **Client**: one `POST` per screen mount, guarded by a ref set before the request is issued, so a
  re-render or a `useFocusEffect` refetch cannot fire a second one.
- **Server**: a conditional write that acts as a ~60 s dampener — `SET last_engaged_at = :now`
  with
  `ConditionExpression = "attribute_not_exists(last_engaged_at) OR last_engaged_at < :cutoff"`,
  `:cutoff = now - 60s`. A user flipping between two artifacts of the same media produces one
  write per minute per subject instead of one per tap. Note the cost caveat: a write rejected by a
  condition still consumes write capacity, so the dampener saves the **index churn** and the
  ordering noise, not the base write unit. That is the right trade: it is the index delete+put
  pair that costs, and a stable ordering that matters for the row.

The 60 s value is chosen to be shorter than any plausible session boundary and longer than any tap
sequence. It deserves the same treatment as `COVER_URL_EXPIRATION_SECONDS` in
`media_search_service.py`: a named module constant with a comment, not a literal.

### 5.4 Idempotence

The write is an idempotent upsert of one attribute to a value the server computes. Two deliveries
of the same event produce the same state, in either order, because `last_engaged_at` is monotone
in practice and re-writing it with a value milliseconds apart is indistinguishable from writing it
once. No idempotency key, no ledger, no dedup table — which is the main reason the upsert shape
(A, B) is preferable to the event shape (B') for a signal that only ever needs "the latest".

### 5.5 Failure, and the eventual-consistency wrinkle

**Silent failure is correct here, and there is a pattern to copy.** `quota_enforcer._debit`
(`core/services/quota_enforcer.py:636`) swallows its exception, logs a structured event and lets
the user's work proceed. The engagement write must behave the same way:

- `POST /api/engagements` returns `204` even when the underlying write fails (a `4xx` is reserved
  for an unowned or malformed subject), and the client fires it without awaiting it and with an
  empty catch. A failed engagement must never surface an error, never block navigation, never
  delay a render.
- Inside `create_artifact`, the stamp is wrapped so it cannot fail the generation the user actually
  asked for.
- **No retry.** The event will recur the next time the user opens something; a retry queue for a
  decoration is disproportionate. Failures are logged as a structured event
  (`engagement.stamp_failed`) so a systematic breakage is visible in logs, but the metric does
  **not** deserve an alarm: this row degrades to empty, which the UI already handles as "hide the
  section" (task-307 AC #2).

**The wrinkle to accept knowingly**: a GSI is eventually consistent, so an engagement written a
fraction of a second before the Inbox refetches may not yet be in `engaged-index`. The realistic
sequence — launch a generation, navigate back, the Inbox refetches on focus — leaves human-scale
navigation time for a propagation AWS describes as normally sub-second, and the same item is
usually visible in "Recently added" anyway. If this ever shows in practice, the fix is a
client-side optimistic prepend, not a schema change. Option B is the shape that does not have this
wrinkle at all (a single-partition base-table query can be read consistently); it is a real
advantage, and it is outweighed by the two points in section 4.

---

## 6. Question #5 — the read path

### 6.1 The endpoint

```
GET /api/engagements/recent?limit=12          ->  200

{
  "status": "success",
  "items": [
    { "kind": "media", "id": "<media_item_id>", "title": "...",
      "creator_name": "...", "image_url": "https://...", "media_type": "youtube",
      "engaged_at": "2026-08-19T21:04:11Z" },
    { "kind": "collection", "id": "<folder_id>", "title": "Stoicism",
      "item_count": 7, "preview_images": ["https://...", "https://..."],
      "engaged_at": "2026-08-19T18:40:02Z" }
  ]
}
```

One flat, already-sorted, already-capped list. Both kinds share `kind` / `id` / `title` /
`engaged_at`; media entries carry `creator_name`, `image_url` and `media_type` (the task-302
fallback icon needs it); collection entries carry `item_count` and up to four `preview_images`.
Cover URLs are presigned server-side by the existing
`media_search_service._resolve_cover_urls` path, with the same 24 h expiry
(`COVER_URL_EXPIRATION_SECONDS`) — the client must not have to know that a `thumbnail_url` may be
an `s3://` locator.

**Cap: 12**, with `limit` accepted in the range 1 to 20. Rationale: task-307 renders a
horizontally scrolling row; two screens' worth of tiles is generous, and the cap bounds both the
`Query` and the presigning work. It is a server-side default so the row can be re-tuned without
shipping an app build.

**Freshness window: 90 days**, applied as the sort-key range condition, so stale entries cost
nothing to exclude and the row *empties itself* when the user stops using the app for a season —
which is what makes the "no empty section" requirement (task-307 AC #2) implementable:
`items: []` means hide the section.

### 6.2 Why not a client-side join

Rejected on a concrete fact: `MediaService.listMedia()` sends no `limit`, and `search_media`
defaults to `limit = 20`. The Inbox therefore holds **the 20 most recently saved** items. An item
engaged three weeks ago is very likely not among them, so a client-side join would need up to
`cap` extra `GET /api/media/{id}` calls to fill the gaps — 12 sequential round trips on a cold
open, on mobile network, for one row. The join also duplicates the server's ordering and windowing
logic in TypeScript, and it cannot work at all for collections, whose covers and counts are not in
either list.

### 6.3 Why a dedicated endpoint and not an aggregate `/api/home`

An aggregate that returns the daily digest, recently added and continue-learning in one response
would minimise round trips, and is rejected because it couples three independent sections into one
failure domain — directly against task-307 AC #9, which requires each data source to fail
independently, and against the digest's latency profile (it is the slowest of the three). Three
endpoints, three loading states, three failures.

### 6.4 Round trips, counted

Inside the handler, per request:

1. `Query engaged-index` on `user_media` — capped, windowed, projection-only. **1 call.**
2. `Query user-index` on `user_folders` — every folder of the user, `ALL` projection; filter on
   `last_engaged_at` and sort in Python. **1 call.** Issued **concurrently** with (1) via
   `asyncio.gather`.
3. **Only if the merged, capped list contains at least one collection**: one
   `list_library_for_user`-style partition read, which yields both the `item_count` and the four
   newest covers for every collection in the row, in memory, with no per-collection query. **1
   conditional call.** This is the same read `GET /api/folders` already performs on every Inbox
   open today, so it is a known cost, not a new class of one. (The alternative — one `folder-index`
   LSI query per collection entry — is up to 12 queries returning full item images, i.e. more
   payload for less information.)

So: **2 DynamoDB calls when the row is media-only, 3 when a collection appears in it.**

Cold Inbox open after the task-307 rework: five independent HTTP requests — `/api/media`,
`/api/folders`, `/api/digest/daily`, `/api/engagements/recent`, `/api/entitlements/status` —
against two today. All five are fired in parallel by independent hooks; the row adds one, and it is
the cheapest of them.

### 6.5 Collections must not be second-class

If the endpoint returned only `kind`, `id` and `title` for collections, then per task-307 AC #6
every collection tile would render the fallback (an accent surface with the name and the item
count) forever — and it could not even do that, since the count is not in the folder row. Hence
`item_count` and `preview_images` in the contract, both computed from the single conditional
partition read of 6.4. A collection with fewer than four items returns fewer preview images and
the client falls back for the remainder; a collection with none returns `preview_images: []` and
the accent surface is correct.

---

## 7. Question #6 — what changes on `user_folders`

### 7.1 One attribute. No new index.

`user_folders_v1` has exactly one secondary index today, `user-index` = `user_id` HASH only,
projection `ALL`, and `database_async.get_folders_by_user_id` (:997) queries it with a bare
`Key("user_id").eq(user_id)`. There is no sort key, so DynamoDB cannot order or window folders
server-side.

**That is fine, and it stays.** The query already returns *every* folder of the user with every
attribute, which means `last_engaged_at` arrives with it at no additional cost. The recency
endpoint filters on the window and sorts in Python — the same thing `media_search_service` already
does for the library list (a Python-side sort by `(saved_at, media_item_id)`). This is sound
because the collection count per user is bounded by hand-creation (tens, not thousands) and because
`GET /api/folders` already reads them all on every Inbox open *and* additionally sweeps the whole
media partition for counts. One more read of the same small index is not a cost worth an index for.

**The threshold at which this answer changes**: if collections ever become machine-generated or a
user can plausibly hold hundreds, add a sparse GSI `(user_id, last_engaged_at)` mirroring the media
one — a purely additive change, since the attribute is already there. Adding it now would be an
index that "is seldom used" and "contributes to increased storage and I/O costs without improving
performance", which is what AWS's guidance says not to do
([General guidelines for secondary indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-indexes-general.html)).

### 7.2 The clobber hazard that must be fixed in the same change

`database_async.update_folder(folder)` writes **`put_item(Item=folder.to_dynamodb_item())`** — a
full-item overwrite — and `Folder.to_dynamodb_item()` emits a closed set of six or seven
attributes. So **any attribute stored on a folder row that the `Folder` model does not know about
is silently erased the next time the collection is renamed.**

This is the asymmetry with the media table, and it is worth stating because it is invisible at the
call site: `user_media` is immune by invariant I1 ("`create` holds the module's only `put_item`.
Every other mutation is an attribute-level `update_item`"), guarded by an `attribute_not_exists`
condition; `user_folders` has no such invariant.

Required:

- `Folder` gains `last_engaged_at: Optional[datetime]`, round-tripped in **both**
  `to_dynamodb_item()` (omitted when `None`, like `parent_folder_id`, so nothing is written for a
  collection that was never engaged and any future index stays sparse) and `from_dynamodb_item()`.
- The engagement stamp itself is a **targeted `UpdateItem`** on the folder id — never a model put —
  so it cannot race with a rename over the rest of the item.

Residual, accepted: a rename is a read-modify-write, so a stamp landing between its read and its
put is lost. The consequence is that one collection loses its place in the row until the next time
it is opened. A hardening the owner may prefer, since nothing is deployed and there is no migration
to stage: convert `update_folder` into a targeted `UpdateItem` on `name`, `parent_folder_id` and
`updated_at`, which removes the whole class of bug rather than this instance of it.

---

## 8. Cost and effort

### 8.1 Cost

DynamoDB on-demand, at the reference rates published on
[the DynamoDB on-demand pricing page](https://aws.amazon.com/dynamodb/pricing/on-demand/) — write
request units $0.625 per million, read request units $0.125 per million (strongly consistent),
storage $0.25 per GB-month, PITR $0.20 per GB-month. Regional rates differ by a few percent and
change none of the conclusions below.

Per engagement (Option A): 1 base `UpdateItem` on an item well under 1 KB = 1 WRU, plus index
maintenance — 1 WRU the first time an item enters the index, 2 WRU thereafter (a change to an
indexed key is a delete plus a put in the index). So **~3 WRU**, about $0.0000019.

| Scenario | Engagements / month | Write cost | Read cost (1 extra Query per Inbox open, ~1-2 RRU) | Total |
| --- | --- | --- | --- | --- |
| Owner only, heavy dogfooding | ~1 000 | $0.000002 | negligible | **< $0.01** |
| 100 users, 20 engagements each | 2 000 | $0.000004 | 100 x 60 opens x 2 RRU = 12 000 RRU | **< $0.01** |
| 10 000 users, 30 engagements each | 300 000 | $0.0006 | 10 000 x 60 x 2 = 1.2 M RRU = $0.15 | **~ $0.15** |

Index storage is sparse and tiny: 10 000 users x 200 engaged items x ~250 B is about 500 MB, or
$0.12/month plus $0.10 PITR. **Money is not a decision criterion here** — every option costs cents
at any scale this project will see in its first year. The GSI is justified by latency and
predictability (a bounded, capped, windowed query, instead of a partition read whose cost grows
with the library), not by cost.

Options B and B' are within a factor of two of A on every line, in both directions. Anyone choosing
between them on price is choosing at random.

### 8.2 Effort

| Work | A | B / B' | C |
| --- | --- | --- | --- |
| Terraform | 1 `attribute` + 1 `global_secondary_index` on `user_media` (online `UpdateTable`) | new table + PITR/protection/TTL + env wiring in `runtime_env.tf` | new GSI on `media_artifacts` |
| IAM | none (`local.table_arns` already wildcards the table and index ARNs per environment) | none (same wildcard) | none |
| Backend, new | 1 write helper in `utils/user_media.py`, 1 in `database_async.py`, 1 read service, 1 endpoint + response models | + a whole store module, + a hydration step, + de-dup for B' | + `scope_key` parsing + `media_key` to `media_item_id` resolution |
| Backend, touched | `artifacts.create_artifact` (one best-effort call), `Folder` model (3 lines) | `artifacts.create_artifact`, `account_deletion_service` inventory, purge cascade, folder deletion | all of B's, plus more |
| Mobile | 1 service method + 1 fire-and-forget call in the artifact viewer + the row component (task-307) | identical | identical |
| Deletion semantics to re-verify | **none** | soft delete, TTL purge, folder delete, account erase | same |
| Risk | GSI backfill on a live table (non-blocking, reversible: an unused GSI can be dropped) | a fourth store that can point at destroyed content | highest |

A is both the smallest change and the one with the fewest places to be wrong later.

---

## 9. What this recommendation forecloses, and what it leaves open

- **It does not foreclose progress.** `reading_progress` can be added later as another attribute on
  the same row, projected into the same index, without touching the write triggers or the endpoint's
  shape. The trigger to reconsider is named in 2.3.
- **It does not foreclose an event history.** If analytics ever needs "how many times did this user
  open anything last week", that is a different question with a different answer (a stream consumer,
  or a log-derived metric) and it should not be smuggled into a UI row.
- **It does foreclose per-device rows.** Deliberately, per section 3.
- **It leaves the display rules to task-307**: whether an entry with a failed generation is badged,
  how a `queued` generation is shown, and the tile layout are that task's calls. This benchmark only
  guarantees the data is there: `kind`, `id`, `title`, `creator_name`, `image_url`, `media_type`,
  `engaged_at`, `item_count`, `preview_images`.
- **Open question the owner may want to settle now**: whether a *save* should seed
  `last_engaged_at`. The recommendation is **no** — that is what "Recently added" is for, and
  seeding would make the two rows identical for a new user. The consequence is that a brand-new
  account sees no "Continue learning" section until it generates or opens its first artifact, which
  is the correct empty state.

---

## 10. Sources

**DynamoDB modelling and behaviour**

- Using Global Secondary Indexes (sparse indexes, eventual consistency, projections) — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.html
- Managing global secondary indexes, online index operations (table stays available, index not queryable until `ACTIVE`, no charge for backfill reads, one index per `UpdateTable`) — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.OnlineOps.html
- Working with Local Secondary Indexes (created with the table only; 10 GB item-collection limit) — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/LSI.html
- General guidelines for secondary indexes (keep indexes to a minimum; project few attributes; index entries under 1 KB cost nothing extra; every update of a projected attribute costs an index update; 20 GSIs / 5 LSIs per table) — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-indexes-general.html
- How TTL works (best-effort deletion "within a few days", TTL deletes not charged as writes, service-principal marker on stream records) — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/howitworks-ttl.html
- Time to Live overview — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/TTL.html
- Service, account and table quotas — https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/ServiceQuotas.html
- DynamoDB on-demand pricing (WRU, RRU, storage, PITR) — https://aws.amazon.com/dynamodb/pricing/on-demand/
- Terraform AWS provider, `aws_dynamodb_table` (`local_secondary_index` forces a new resource; `global_secondary_index` does not; declaring an unused `attribute` causes an infinite plan loop) — https://raw.githubusercontent.com/hashicorp/terraform-provider-aws/main/website/docs/r/dynamodb_table.html.markdown

**HTTP and client semantics**

- MDN, Safe (HTTP methods) — "an application should not allow these requests to alter its state" — https://developer.mozilla.org/en-US/docs/Glossary/Safe/HTTP
- HTTP Semantics, RFC 9110, safe methods (9.2.1) — https://www.rfc-editor.org/rfc/rfc9110.html
- expo-router API reference — `router.prefetch()` ("Prefetch a screen in the background before navigating to it") and `PagePreloadedEvent` (a page "rendered as part of a preload ... and is not currently focused") — https://docs.expo.dev/versions/latest/sdk/router/

**Product prior art**

- Readwise Reader API — `reading_progress`, `first_opened_at`, `last_opened_at`, `seen`, and the explicit `PATCH` that updates them — https://readwise.io/reader_api
- Spotify Web API, Get Recently Played Tracks — a capped, timestamped interaction list with cursors and no position — https://developer.spotify.com/documentation/web-api/reference/get-recently-played

**In-repo references** (read, not modified)

- `infrastructure/terraform/modules/platform/dynamodb_user_media.tf`, `dynamodb_core_tables.tf`, `runtime_env.tf`, `iam_lambda.tf`
- `media_summarizer/utils/user_media.py` (invariants I1 and I2, `update_attributes`, `mark_deleted`, `delete_all_for_user`), `media_summarizer/utils/database_async.py` (`get_folders_by_user_id`, `update_folder`)
- `media_summarizer/api/endpoints/artifacts.py` (`_assert_scope_owned`, `create_artifact`, `get_artifact_content`), `media_summarizer/api/endpoints/media.py` (`search_media`)
- `media_summarizer/core/services/`: `media_search_service.py`, `folder_service.py`, `account_deletion_service.py`, `media_purge_service.py`, `quota_enforcer.py`
- `media_summarizer/workers/cleanup/media_lifecycle.py` (purge cascade and daily reconciliation)
- `mobile/app/(tabs)/inbox.tsx`, `mobile/app/media/[id].tsx`, `mobile/app/artifacts/[artifactId].tsx`, `mobile/src/services/apiClient.ts`, `mobile/src/services/mediaService.ts`, `mobile/package.json`
- `docs/research/task-218-durable-media-library-persistence/README.md` (invariants, deletion, observability), `docs/research/task-302-media-cover-and-creator/README.md` (the validated cover and creator model)
- `scripts/check_purge_at_writers.py` (CI guard on `purge_at` and `deleted_at` write shapes)
