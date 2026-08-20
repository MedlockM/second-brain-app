---
id: task-303
title: >-
  Benchmark the engagement-recency model behind the Inbox "Continue learning"
  row
status: Done
assignee: []
created_date: '2026-08-19 21:08'
updated_date: '2026-08-20 17:40'
labels:
  - benchmark
  - backend
  - api
  - phase-6
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The reworked Inbox opens on a **"Continue learning"** row: the media items **and the collections** for which the user has recently opened an already-generated artifact, or launched a generation. No such signal is recorded anywhere in the system today, and the schema decision it implies is not reversible cheaply — hence a benchmark before implementation.

## What exists today, and what it forecloses

- **Generation is half-recorded already.** `media_artifacts` is an append-only history whose `scope-index` GSI is `(scope_key, created_at)` with `ScanIndexForward=false` (`infrastructure/terraform/modules/platform/dynamodb_core_tables.tf:235-266`), so "what was generated for *this* scope, newest first" is one query. There is **no per-user index across scopes**, so "the user's last N engaged scopes" is not answerable from it.
- **Opening an artifact writes nothing.** It is a client navigation — `mobile/app/media/[id].tsx:859` and `mobile/app/media/collections/[id].tsx:436` both push `/artifacts/<id>` — followed by `GET /api/artifacts/{id}` and `GET /api/artifacts/{id}/content` (`api/endpoints/artifacts.py:418`, `:473`). Generation is `POST /api/artifacts` (`:173`), which already knows the user, the scope and the instant.
- **`user_media` cannot gain a new LSI.** It is `(user_id, media_item_id)` with LSIs `saved-at-index` and `folder-index` and one GSI `media-key-index`; the file states at `:57-59` that local secondary indexes must exist at table creation and can never be added — and the table carries `prevent_destroy`. A new sort dimension therefore means a **GSI**, or another table. `user_folders` has a hash-only `user-index` (`dynamodb_core_tables.tf:443-447`), so collections have no server-side ordering at all today.
- **The mobile app has no local persistence.** `mobile/package.json` has no AsyncStorage and no MMKV; `expo-secure-store` exists but holds credentials. A device-local recents store means adding a dependency, and it is per-device and lost on reinstall.

## What the research must answer

**1. Semantics of the signal.** The owner's definition is artifact-centric: an artifact opened, or a generation launched, on a media or on a collection. Compare it with what the field actually does — Spotify's recently-played, Pocket/Readwise's continue-reading, Netflix's continue-watching all record *consumption*, and several record **progress**, not merely an open — then recommend one. Answer explicitly: does opening a media detail or reading a transcript count? Does an in-flight generation (`status: queued|generating`) belong in the row before it is ready? Does re-opening the same artifact twice move it or leave it?

**2. Where the signal lives.** Device-local versus server-side, argued on cross-device consistency, reinstall/simulator resets, write volume per interaction, offline behaviour, and the dependency a local store would introduce. State a recommendation rather than listing both.

**3. Server-side shape, if that is the recommendation.** Compare at least: (a) a `last_engaged_at` attribute on `user_media` plus a new GSI `(user_id, last_engaged_at)`, with the equivalent on `user_folders`; (b) a dedicated `user_activity` table, upsert-shaped (one row per scope) or event-shaped (one row per interaction) with a TTL and a cap; (c) generations derived from `media_artifacts` with opens tracked separately. For each: writes per interaction, index storage, whether **one** query answers the row for both kinds (media and collection), and behaviour on deletion — the `user_media` stream drives the purge cascade, so an engagement row must never resurface a deleted media or collection, and `delete_all_for_user` must not leave orphans.

**4. The write trigger.** Which HTTP call records an engagement. A side effect on `GET /api/artifacts/{id}/content` is the tempting answer and must be judged as such — a safe method that mutates, falsified by any retry or prefetch — against an explicit `POST`. Cover throttling (one write per scope per session, or per N minutes), idempotence, and the rule that a failed engagement write is invisible to the user and never blocks the read it accompanies.

**5. The read path.** One endpoint returning the row ready to render (kind, id, title, image, creator, ordering) versus the client stitching `/api/media` + `/api/folders` + a recents list. The screen refetches on focus (`mobile/app/(tabs)/inbox.tsx:84-89`) and will also load "Recently added" and the digest count, so count the round-trips a cold open costs. Give the response shape you recommend and the row's length cap.

**6. Cost and effort per option, then one recommendation.**

## Constraints

- **Scope boundary with task-302**: that benchmark decides where a tile's image and creator name come from. This one decides only the recency signal and the read path. Do not re-decide metadata extraction here; assume both fields exist on the media row.
- No dual store, no "local cache plus server truth as a transition": nothing is deployed (`AGENTS.md`, "Nothing is deployed yet"). Pick one.
- Whatever is recommended must answer for **collections** too, not only media — half a design that covers media and leaves folders to a follow-up is a rejected answer.
- Research only: this task writes no production code, no Terraform, no endpoint.

## Owner notes (not acceptance criteria)

- The question to arbitrate when reviewing is #1: an "opened an artifact" signal is cheap but shallow, whereas a progress-based signal ("you are 40% through") is what makes a continue-reading row genuinely useful — and it costs a reading-position write path this app does not have.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 docs/research/task-303-<short-description>/README.md exists with owner_decision: pending in its front-matter and an Owner Validation section whose Decision and Validated at fields are empty
- [ ] #2 The README states what counts as an engagement and answers explicitly whether a media-detail open, a transcript read, an in-flight generation and a repeat open each move an entry in the row
- [ ] #3 Device-local versus server-side storage is decided, with cross-device behaviour, reinstall, write volume, offline behaviour and the added mobile dependency each argued
- [ ] #4 At least three server-side shapes are compared on writes per interaction, index storage, whether one query answers the row for both media and collections, and behaviour under the purge cascade and account deletion
- [ ] #5 The write trigger is specified as a concrete HTTP call, with the GET-with-side-effect option explicitly judged, plus throttling, idempotence and the silent-failure rule
- [ ] #6 The read path is specified with the recommended response shape, the row length cap and the number of round-trips a cold Inbox open costs
- [ ] #7 The recommendation covers collections as well as media, and states what changes on user_folders given its hash-only user-index
- [ ] #8 A cost and effort comparison ends in a single recommendation stated as what the owner would be validating
- [ ] #9 No production code, contract or Terraform file is modified by this task
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Mode: **initial** (no `docs/research/task-303-*` directory existed, no prior
`README.owner-rejected-*.md`, no complement request). Research only: no production code, no
contract and no Terraform file was touched.

Deliverable: `docs/research/task-303-engagement-recency-model/README.md`
(`owner_decision: pending`, `Decision` and `Validated at` left empty).

What it recommends, in one line: an **open-based** engagement signal (`last_engaged_at`)
stored **server-side as one attribute on the subject itself** — plus one new sparse GSI
`engaged-index` (`user_id`, `last_engaged_at`) on `user_media_v1`, the same attribute on
`user_folders_v1` with **no new index**, two explicit writes (`POST /api/artifacts` plus a new
`POST /api/engagements`, never a `GET` side effect), and one render-ready
`GET /api/engagements/recent?limit=12` covering media and collections in a single merged list.

Question #1 (the one the owner flagged) is arbitrated in favour of open-based, with the
progress-based alternative analysed and rejected for v1 on three app-specific grounds; the
README names the exact condition under which the owner should choose progress instead (the
transcript becoming a first-class reading surface). A media-detail open and a transcript read
are both excluded, the second because Reader is the default tab at
`mobile/app/media/[id].tsx:398`, which makes "transcript displayed" the same event as "media
opened".

Four storage shapes are compared (attribute + sparse GSI, a dedicated `user_activity` table in
both upsert and event form, and deriving the row from `media_artifacts`) on writes per
interaction, index storage, whether one query answers both kinds, purge-cascade and
account-deletion behaviour, schema churn, and effort.

Two findings the implementation task will need regardless of the option chosen:
- `database_async.update_folder()` is a full `put_item` of `Folder.to_dynamodb_item()`, so any
  new attribute on a folder row is erased on the next rename unless the model round-trips it.
  `user_media` is immune to the equivalent bug by invariant I1.
- The engagement stamp must not go through `user_media.update_attributes`, which always bumps
  `updated_at` — the field task-302 uses to build the `expo-image` cover cache key.

**The recommendation awaits the owner's validation.** The task stays `To Do`; the owner sets
`owner_decision` on the README (`ok` / `abandoned` / `redo` / `more`), which is what unblocks
task-305.
<!-- SECTION:NOTES:END -->
