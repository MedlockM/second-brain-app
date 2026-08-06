---
id: task-233
title: Prevent transcript translation self-blocking and artifact request timeouts
status: Done
assignee:
  - codex
created_date: '2026-08-06 01:00'
updated_date: '2026-08-06 01:11'
labels:
  - bug
  - api
  - translation
  - artifacts
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Correct the translation lifecycle regression observed in AWS where the asynchronous translation worker rejects its own in-progress lock and artifact creation falls back to a long synchronous translation, causing API Gateway 503 timeouts.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The asynchronous translation worker can complete the translation it owns without treating its own in-progress state as a competing request.
- [x] #2 Artifact creation never performs a long synchronous transcript translation in the API Lambda.
- [x] #3 When a required translation is absent or failed, an artifact request atomically schedules one asynchronous translation and returns a conflict/pending response until it is ready.
- [x] #4 Concurrent artifact or raw-content requests do not enqueue duplicate translations for the same transcript and target language.
- [x] #5 Once translation is ready, the artifact request can enqueue generation normally and no stale queued artifact record is left by pending requests.
- [x] #6 The fix is validated with targeted static checks and a controlled manual reproduction without adding automated tests.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Give each SQS translation message atomic ownership of the DynamoDB in-progress lock, allowing only that message (and its retries) to execute the LLM translation.
2. Centralize translation reservation and SQS dispatch in a non-blocking service path shared by artifact and raw-content requests.
3. Resolve translated S3 cache hits immediately; otherwise return the existing 409 pending response before any artifact request pointer or record is created.
4. Retry the artifact POST on mobile while translation is pending, then switch to artifact-status polling only after the backend returns an artifact id.
5. Preserve failed/done state integrity, including SQS dispatch failures and done records whose translated S3 object is missing.
6. Validate the lifecycle with targeted compile, Ruff, Mypy, TypeScript, ESLint, diff, and in-memory behavioral checks without adding test files.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Plan approved by the user's explicit request to apply the corrective direction identified in the preceding diagnosis. Existing task-214 is Done; task-233 tracks this regression separately.

Workspace is already dirty with unrelated user changes. Implementation will be limited to translation/artifact files and will preserve all unrelated modifications.

Implementation refinement: the existing mobile 409 branch only sets a local queued state and polls media status, but no artifact record exists yet, so generation would never resume. This client retry is required to complete the original user action after async translation.

## Implementation summary
- Added worker ownership to translation locks. The SQS MessageId now atomically claims queued/failed work; competing messages are skipped, while the owner can pass its own in-progress guard.
- Added a non-blocking resolve-or-enqueue translation path. Artifact requests reuse the translated S3 object or atomically enqueue one translation and return 409 before creating artifact state; no API Lambda performs the long LLM translation.
- Reused the shared dispatcher in raw-content and made enqueue failures transition to failed without emitting a false enqueued event.
- Corrected terminal worker failures so they cannot be marked done when no translated object exists.
- Updated the media screen to retry the artifact POST every 3 seconds after translation-pending 409 responses (bounded to 100 attempts), clear stale timers, and begin artifact polling only once an artifact id exists.

## Validation
- Backend: targeted `compileall`, Ruff, and Mypy passed for all five changed Python modules.
- Mobile: `npm run typecheck` passed; targeted ESLint passed with zero errors and one pre-existing unused-parameter warning in the same screen.
- `git diff --check` passed for the six implementation files.
- Controlled in-memory checks passed for owner/competitor lock behavior, exactly-once reservation and dispatch, translated-cache reuse, terminal failure state, absence of stale artifact records while pending, and normal artifact enqueue once translation is ready.
- No automated test files were added, per project delivery rules.

The corrections are implemented locally only; AWS still requires the normal deployment workflow before the production incident path uses them.
<!-- SECTION:NOTES:END -->
