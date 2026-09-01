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
- [ ] #1 GET /api/artifacts/{id}/content lets a client distinguish an artifact still being produced (queued/generating) from one that has terminally failed, without parsing the message text
- [ ] #2 The response returned for a terminally failed artifact no longer tells the caller to try again once generation completes
- [ ] #3 Mobile keeps no polling loop alive against an artifact in failed state, and surfaces a failure state instead
- [ ] #4 From that failure state the user can explicitly trigger a regeneration
- [ ] #5 Any user-facing string added by this task is present in all 11 locale files under mobile/locales/
- [ ] #6 ruff and mypy pass on the changed Python modules; npm run typecheck and ESLint pass on the changed mobile files
<!-- AC:END -->
