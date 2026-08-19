---
id: task-305
title: >-
  Record and expose the engagement signal behind "Continue learning" per
  validated benchmark (task-303)
status: To Do
assignee: []
created_date: '2026-08-19 21:09'
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
- [ ] #1 The implementation follows the owner's Decision field in docs/research/task-303-*/README.md, and the Implementation Notes state which option was implemented and quote the decision that mandated it
- [ ] #2 Every interaction the README counts as an engagement records one, for both the media and the collection scope, from the call sites named in the description
- [ ] #3 The storage the README mandates exists in Terraform with its TTL and IAM grants, and terraform validate plus terraform plan exit 0 for the -dev environment
- [ ] #4 A read path returns the recency list in the README's order, capped at its stated length, and covers media and collections as the README specifies
- [ ] #5 A failed engagement write cannot surface an error, block or delay opening an artifact, or retry in a loop — the accompanying read still succeeds
- [ ] #6 The throttle rule from the README is implemented, and no code path records an engagement on render or on scroll
- [ ] #7 GET /api/artifacts/{id} and GET /api/artifacts/{id}/content remain free of side effects unless the README explicitly chose the opposite
- [ ] #8 A media or collection removed by the user, and every row of a deleted account, leaves no engagement entry that could resurface it — the purge cascade and delete_all_for_user both account for the new storage
- [ ] #9 The mobile client records the engagement at the artifact-open sites and exposes a service method for the read path, with cd mobile && npm run typecheck && npm run lint clean
- [ ] #10 ruff and mypy are clean on the touched Python, and no local mirror or second store of the signal exists
<!-- AC:END -->
