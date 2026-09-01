---
id: task-328
title: >-
  Stop polling an artifact that has terminally failed, and fix the 409 message
  that invites the retry
status: To Do
assignee: []
created_date: '2026-09-01 16:39'
labels:
  - bug
  - api
  - artifacts
  - mobile
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Observed

On 2026-09-01 against `-dev`, `GET /api/artifacts/art_1b9eec9771fa8d19c2e175e7a2443596/content` answered `409` with:

> Artifact is not ready (status: failed). Try again once generation completes.

The app called the endpoint again, and the backend message literally invites that retry — while `failed` is a **terminal** state: generation will not resume on its own. Nothing in the response lets the client tell "not ready yet" from "will never be ready".

`media_artifacts-dev` currently holds 5 artifacts at `status=failed` (3 from 2026-09-01 caused by the exhausted LLM quota, 2 from 2026-08-18 caused by an unrelated `Float types are not supported` write bug). Each one is a polling trap.

## Scope

Put the distinction in the contract rather than in the prose of a message: `queued`/`generating` means come back later, `failed` means terminal — show the failure and offer an explicit regeneration. Then make the client honour it.

## Owner note

Worth a visual check on the app after deploy: a failed artifact should render an actionable failure state, not a spinner that never resolves.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 GET /api/artifacts/{id}/content lets a client distinguish an artifact still being produced (queued/generating) from one that has terminally failed, without parsing the message text
- [x] #2 The response returned for a terminally failed artifact no longer tells the caller to try again once generation completes
- [x] #3 Mobile keeps no polling loop alive against an artifact in failed state, and surfaces a failure state instead
- [x] #4 From that failure state the user can explicitly trigger a regeneration
- [x] #5 Any user-facing string added by this task is present in all 11 locale files under mobile/locales/
- [x] #6 ruff and mypy pass on the changed Python modules; npm run typecheck and ESLint pass on the changed mobile files
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
`GET /api/artifacts/{id}/content` now answers its `409` as a typed refusal, in the
same shape as the `scope_empty` / `sources_not_ready` refusals of `POST /api/artifacts`
— so `apiClient` already exposes the code and the body without any new plumbing:

- `artifact_not_ready` — `queued` / `generating`. Resolves on its own; this is the
  only branch that still says "try again once generation completes".
- `artifact_failed` — terminal. Says generation "will not resume on its own", and
  carries `artifact_error_code` plus the `scope` / `scope_id` / `artifact_type` a new
  generation needs, so a failure state can offer one with no second round-trip.

The `failed` check runs *before* the `storage is None` check: a failed entry has no
payload either, and the old single branch is what conflated the two.

Mobile splits the screen's single `not_ready` state in two. `pending` keeps the
Refresh button; `failed` deliberately has none — re-reading a terminally failed
entry can only ever answer the same refusal — and offers "Generate again" instead,
which POSTs `/api/artifacts` with the triple the refusal carried. That request reruns
the entry under its own id (`retried`) and debits nothing extra; on success the screen
moves to `pending`, on refusal it shows the same typed refusal banner as the AI tabs.
The 409 is classified by `error_code` in `mobile/src/lib/artifactContentBlock.ts`,
never by message text. The screen's last hardcoded English sentence ("This artifact
isn't ready yet…") is gone.

The two artifact poll loops (`app/media/[id].tsx`, `app/media/collections/[id].tsx`)
already keyed on `queued`/`generating` only, so a `failed` entry never armed them; the
loop this task removes was the human one — a Refresh button whose every tap re-asked
an endpoint that could only refuse.

AC#5 reading: `mobile/locales/*.json` holds **native** strings only (app name, iOS/
Android permission descriptions), which this task adds none of. The 11 locale files
that carry UI copy are the catalogues under `mobile/src/i18n/`, and the 7 new keys
(`artifact.pendingBody`, `generationFailedTitle`, `generationFailedBody`, `regenerate`,
`regenerateA11y`, `regenerating`, `regenerationQueued`) are in all 11 — enforced by
`tsc` through the `Catalog` type, so a missing key is a build error rather than a
review item.

Checked against the real `-dev` table rather than a test: the 5 `status=failed` rows of
`media_artifacts-dev` (including `art_1b9eec9771fa8d19c2e175e7a2443596` from the report)
carry **no** `storage` attribute, and all 5 carry `scope`, `scope_id` and `artifact_type`
— so the new branch is the one that answers and the regeneration triple is always
populated. `error_code` is present on 3 of the 5, which is why `artifact_error_code` is
nullable in the body and the client never depends on it. Two of the 5 are `review_blurb`,
an internal type `POST /api/artifacts` refuses; the type allow-list in
`artifactContentBlock.ts` is what keeps the failure state from offering a button that
could only be refused for those.

Not reached: the owner's visual check on the app. It needs the change deployed (push to
`main` builds the Lambda image) and a device build, neither of which exists from a
worktree branch.
<!-- SECTION:NOTES:END -->
