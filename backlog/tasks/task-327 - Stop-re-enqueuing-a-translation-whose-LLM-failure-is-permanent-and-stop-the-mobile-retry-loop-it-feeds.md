---
id: task-327
title: >-
  Stop re-enqueuing a translation whose LLM failure is permanent, and stop the
  mobile retry loop it feeds
status: To Do
assignee: []
created_date: '2026-09-01 16:39'
labels:
  - bug
  - api
  - translation
  - artifacts
  - mobile
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Observed

Android test session on 2026-09-01, `-dev` logs, 16:10-16:16 UTC. The OpenAI account had run out of credit (`insufficient_quota` / `credit_balance_exhausted`, HTTP 429). Measured consequences:

- The `transcript_translation` worker was invoked **25 times for a single document** (`1d084c16-...`), each invocation spending 3 backoff attempts against the LLM: roughly 75 provider calls for a translation that could not possibly succeed.
- Media item `mi_50cba5ddc3984308823a3df15f0c7d4b` became **permanently unusable**: every `POST /api/artifacts` answers `409 sources_not_ready` with "Some sources are still being prepared (transcription or translation in progress). Retry in a moment", while nothing is being prepared any more.
- The lock in `translation_idempotence-dev` stayed at `status=failed` (fingerprint `bc11ff98...`) and is still there.

## Why the current design produces this

This is **not** a regression of task-203 / task-233. It is a case their design does not cover: the **permanently failing** LLM call.

- `reserve_translation` (`media_summarizer/utils/translation_idempotence.py:186`) succeeds by construction on a failed lock: `attribute_not_exists(translation_fingerprint) OR #st = :failed`. That is deliberate (task-233 AC#3: "When a required translation is absent or failed, an artifact request atomically schedules one asynchronous translation") and it is the right call for a transient outage.
- Mobile retries `POST /api/artifacts` **every 3 seconds, bounded to 100 attempts** (task-233, plan step 4).

Put together, under a permanent outage: 100 client retries, each re-reserving a translation, each burning 3 provider calls. Nothing anywhere in the chain separates *retryable* (timeout, 5xx, momentary rate limit) from *terminal* (credit exhausted, revoked key, unknown model).

The docstring at `media_summarizer/core/services/artifact_service.py:526` promises the opposite of what happens: "one whose transcript will never arrive is excluded and recorded, so a single broken media cannot lock a collection out forever". A `failed` translation lock escapes that guarantee, because it is neither in-progress (so it is not excluded) nor treated as terminal.

## Scope

Carry the transient/terminal distinction end to end: classify the provider error in the worker, persist the failure kind on the lock, refuse re-reservation when it is terminal, exclude the source from artifact generation instead of reporting it as pending, and stop the mobile retry once the response says terminal.

The provider's error payload is an input contract we do not control: classification must tolerate its shapes (`type: insufficient_quota`, `code: credit_balance_exhausted`, a bare 429, a 401/403 on a rejected key) without assuming any single field is present.

## Owner notes

- The OpenAI credit has to be topped up for the nominal path to work again; this task only fixes how the system behaves when the provider refuses. Reproducing the terminal case manually is easier with a deliberately invalid API key than by waiting for an exhausted quota.
- Worth a visual check on the app after deploy: a media whose translation failed for good should be usable (artifact generated from the untranslated transcript, or a clear failure state), never stuck behind "Retry in a moment".
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An LLM failure is classified as permanent or transient by the transcript translation worker, and the classification tolerates the provider's error payload shapes (exhausted quota, credit balance, bare 429, rejected key on 401/403) without depending on any single field being present
- [ ] #2 A failure classified as permanent is not retried by the worker's internal backoff: the 3 attempts are reserved for transient failures
- [ ] #3 The translation lock persists the failure kind alongside status=failed, so a reader can tell a terminal failure from a transient one
- [ ] #4 reserve_translation refuses the reservation when the existing lock carries a terminal failure, while a transient failure stays re-reservable as it is today
- [ ] #5 A source whose translation failed terminally is excluded from artifact generation with an excluded_reason, instead of counting as pending, matching the guarantee already stated in the _resolve_scope_sources docstring
- [ ] #6 POST /api/artifacts no longer answers sources_not_ready with 'Retry in a moment' when the only cause is a terminally failed translation: the response lets the client tell that case apart from work still in progress
- [ ] #7 Mobile stops retrying POST /api/artifacts as soon as the response signals a terminal cause, and surfaces a failure state instead of exhausting its 100 attempts
- [ ] #8 Every translation_idempotence-dev lock left at status=failed by this incident is purged, verified with the AWS CLI, so the affected media items are no longer blocked
- [ ] #9 ruff and mypy pass on the changed Python modules; npm run typecheck and ESLint pass on the changed mobile files
<!-- AC:END -->
