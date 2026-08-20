---
id: task-305
title: >-
  Record and expose the engagement signal behind "Continue learning" per
  validated benchmark (task-303)
status: Done
assignee: []
created_date: '2026-08-19 21:09'
updated_date: '2026-08-20 19:20'
labels:
  - backend
  - api
  - mobile
  - phase-6
dependencies:
  - task-303
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Record when a user engages with a media item or a collection — opening an already-generated artifact, or launching a generation — and expose the resulting recency list so the reworked Inbox can render its **"Continue learning"** row.

**Read `docs/research/task-303-*/README.md` first.** The owner's `Decision` field under `Owner Validation` is authoritative — it may differ from the recommendation and may reference complement files, which you must follow too. Everything below is scope, not design. What counts as an engagement, where the signal is stored, which HTTP call records it, the throttle, the read path's shape and the row's cap are all decided in that README. Do not re-decide them, and do not implement the recommendation if the `Decision` says otherwise.

## Scope

- **The write path**, wired at every interaction the README counts as an engagement. The two artifact-open sites are `mobile/app/media/[id].tsx:859` and `mobile/app/media/collections/[id].tsx:436` (both push `/artifacts/<id>`); generation goes through `POST /api/artifacts` (`api/endpoints/artifacts.py:173`), which already knows the user, the scope and the instant. Both media and collection scopes.
- **Storage**, in the shape the README mandates — a new attribute plus GSI, a dedicated table, or whatever it decided — including its Terraform, its TTL if it has one, and its IAM grants for the API Lambda (`infrastructure/terraform/modules/platform/iam_lambda.tf`, `runtime_env.tf` for the table name).
- **The read path**: the endpoint or endpoints the README specifies, returning the row in the order it defines, capped as it defines, covering both kinds in one response if that is what it chose.
- **Deletion coherence**: a deleted media or collection must never reappear in the row. `user_media` streams `NEW_AND_OLD_IMAGES` and already drives a purge cascade (`dynamodb_user_media.tf:93-98`); `delete_all_for_user` (`utils/user_media.py:347`) must not leave engagement rows behind, and neither must the account-deletion path.
- **The mobile client side of the write**, plus the service method for the read. The screens that render the row are a separate task.

## Out of scope

- The Inbox/Home redesign itself, and the tiles' image and creator name (task-302 / its implementation task).
- Any notion of reading progress beyond what the README decided. If it chose an open-based signal, do not build a position tracker on the side.

## Constraints

- **A failed engagement write is invisible.** It never surfaces an error, never blocks or delays opening an artifact, and never retries in a loop. The read it accompanies must succeed regardless.
- **No unthrottled write.** Respect the throttle rule the README sets; an engagement recorded on every render or every scroll is a defect, not a detail.
- If the README chose an explicit `POST`, then `GET /api/artifacts/{id}` and `GET /api/artifacts/{id}/content` stay side-effect-free. Do not add a hidden write to a safe method because it is one line shorter.
- One store only — no local mirror kept "for offline", no dual-write. Nothing is deployed (`AGENTS.md`).
- No automated tests unless the owner asks. `ruff` and `mypy` clean, `terraform validate` and `terraform plan` exit 0 for the `-dev` env.

## Owner notes (not acceptance criteria)

- The Terraform change lands on `main` but is applied by the owner: a new GSI on `user_media` builds in the background, and the row stays empty until the first engagement is recorded after deploy. Expect an empty "Continue learning" section on the first run — that is correct behaviour, not a bug.
- LAUNCH PREREQUISITE, owner-side after merge, deploy and apply: open an artifact on a media and generate one on a collection, then check with the AWS CLI that both appear, newest first, in whatever the read endpoint returns.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The implementation follows the owner's Decision field in docs/research/task-303-*/README.md, and the Implementation Notes state which option was implemented and quote the decision that mandated it
- [x] #2 Every interaction the README counts as an engagement records one, for both the media and the collection scope, from the call sites named in the description
- [x] #3 The storage the README mandates exists in Terraform with its TTL and IAM grants, and terraform validate plus terraform plan exit 0 for the -dev environment
- [x] #4 A read path returns the recency list in the README's order, capped at its stated length, and covers media and collections as the README specifies
- [x] #5 A failed engagement write cannot surface an error, block or delay opening an artifact, or retry in a loop — the accompanying read still succeeds
- [x] #6 The throttle rule from the README is implemented, and no code path records an engagement on render or on scroll
- [x] #7 GET /api/artifacts/{id} and GET /api/artifacts/{id}/content remain free of side effects unless the README explicitly chose the opposite
- [x] #8 A media or collection removed by the user, and every row of a deleted account, leaves no engagement entry that could resurface it — the purge cascade and delete_all_for_user both account for the new storage
- [x] #9 The mobile client records the engagement at the artifact-open sites and exposes a service method for the read path, with cd mobile && npm run typecheck && npm run lint clean
- [x] #10 ruff and mypy are clean on the touched Python, and no local mirror or second store of the signal exists
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### The decision that was implemented

`docs/research/task-303-engagement-recency-model/README.md` carries
`owner_decision: ok` with, under `## Owner Validation`:

> **Decision**: Recommandation

So the implemented shape is the README's **Recommendation — Option A**: *"Continue
learning" as an open-based recency row, stored as one attribute on the things
themselves* — one nullable ISO-8601 `last_engaged_at` on the subject rows, plus one
sparse GSI on `user_media_v1`. No activity table (Option B), no derivation from
`media_artifacts` (Option C), no device-local store.

### What was built, per the README's five decisions

1. **Semantics.** Exactly two events stamp the attribute. **E1** — a generation was
   launched: `POST /api/artifacts` stamps the scope it just accepted, on the
   deduplicated `200` path too (`media_summarizer/api/endpoints/artifacts.py`).
   **E2** — an artifact was opened and its content loaded: the artifact viewer
   reports it once per mount. Opening a media detail screen stamps nothing, and the
   transcript reader stamps nothing.
2. **Storage.** `last_engaged_at` on `UserMediaRecord` and on `Folder`, plus the
   sparse `engaged-index` GSI (`user_id` HASH / `last_engaged_at` RANGE,
   `INCLUDE` projection = `title`, `creator_name`, `thumbnail_url`, `media_type`,
   `deleted_at`) in `dynamodb_user_media.tf`. `user_folders_v1` gets the attribute
   and **no** index, as mandated: `user-index` already returns every folder with an
   `ALL` projection, so the folder side is windowed and ordered in Python.
3. **Write path.** Two explicit server-side writes; `POST /api/engagements {kind, id}`
   → `204` for E2. Both go through `engagement_service.stamp`, which swallows and
   logs `engagement.stamp_failed` on the `quota_enforcer._debit` pattern, never
   retries and never raises. Dampened by a 60 s conditional write
   (`attribute_not_exists(last_engaged_at) OR last_engaged_at < :cutoff`), so a
   re-open storm is one write rather than twenty — and, more importantly, one index
   mutation rather than twenty, since changing an indexed key is a delete + put.
4. **Read path.** `GET /api/engagements/recent?limit=12` returns one merged,
   already-sorted, render-ready list of media *and* collection entries with signed
   covers. Server-side default 12, `limit` clamped to 1-20. The 90-day freshness
   window is a sort-key range condition, so the row empties itself and the client
   hides the section.
5. **Deletion.** No new code, by construction: the signal is an attribute of the row
   it describes. Nothing was added to the purge cascade, to `delete_all_for_user`, to
   the folder-deletion path or to the account-deletion inventory; soft-deleted rows
   are excluded on read with `attribute_not_exists(deleted_at)`. Docstrings in
   `utils/user_media.py` record *why* those paths are untouched, so the next reader
   does not conclude a step was forgotten.

The README's **"one thing the implementer must not miss"** is handled:
`database_async.update_folder()` writes a full `put_item` of
`Folder.to_dynamodb_item()`, so `last_engaged_at` now round-trips through the `Folder`
model *and* both serializers — otherwise renaming a collection would silently erase
its engagement clock. The new `database_async.stamp_folder_engagement` is a targeted
`UpdateItem`, not a read-modify-write, so it cannot clobber a concurrent rename
either. Converting `update_folder` itself to a targeted `UpdateItem` (§7.2's optional
hardening) was left alone: it is a behaviour change to an unrelated write path.

### Deliberate details worth knowing

- **Where E2 is reported.** The two sites named in the task description
  (`mobile/app/media/[id].tsx`, `mobile/app/media/collections/[id].tsx`) only
  `router.push('/artifacts/<id>')`. The stamp is fired from the destination of both
  pushes, `mobile/app/artifacts/[artifactId].tsx`, because the README requires the
  artifact to be opened **and its content loaded**, once per screen mount. Stamping
  at the two push sites would record an engagement for an artifact whose content then
  failed to load, and would miss every other route into the viewer. A
  `useRef` guard is set before the request is issued, so a retry after an error does
  not re-report.
- **No hidden write in a safe method.** `GET /api/artifacts/{id}` and
  `GET /api/artifacts/{id}/content` stay side-effect-free, and
  `get_artifact_content`'s docstring now says so and why: the mobile client replays a
  `GET` once after refreshing a 401, and `expo-router` can render a screen the user
  never opened.
- **The stamp does not go through `user_media.update_attributes`.** That helper always
  appends `updated_at`, and `updated_at` is the cache key of the `expo-image` covers —
  stamping through it would invalidate every cover on every artifact open.
- **No TTL, no IAM change, no env var.** Option A's freshness window is a query range
  condition, not an expiry, and `dynamodb_user_media.tf` already forbids a second TTL
  attribute on that table. `local.table_arns` in `runtime_env.tf` already wildcards
  `table/*<suffix>` and `.../index/*`, so the new GSI needs no grant. The index name
  is a module constant, so `.env.example` stays complete.

### Verification

| Command | Exit | Result |
| --- | --- | --- |
| `ruff check .` | 0 | All checks passed |
| `mypy media_summarizer/` | 0 | no issues in 174 source files |
| `python scripts/check_purge_at_writers.py` | 0 | invariant I2 holds |
| `python scripts/check_env_example_complete.py` | 0 | 237 vars declared |
| `terraform validate` (`envs/dev`) | 0 | valid |
| `terraform plan` (`envs/dev`) | 0 | `0 to add, 1 to change, 0 to destroy` — in-place `UpdateTable` on `user_media-dev` |
| `terraform fmt -check -recursive modules/platform` | 0 | formatted |
| `cd mobile && npm run typecheck` | 0 | clean |
| `cd mobile && npm run lint` | 0 | 0 errors (2 pre-existing warnings in untouched files) |

No automated tests were written (project rule). The owner-side checks stay as written
in the description: the GSI backfills in the background after apply, so the row is
legitimately empty until the first engagement is recorded post-deploy.
<!-- SECTION:NOTES:END -->
