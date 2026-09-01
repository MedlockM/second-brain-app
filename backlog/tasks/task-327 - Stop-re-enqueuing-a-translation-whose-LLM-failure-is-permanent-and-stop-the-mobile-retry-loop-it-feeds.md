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
- [x] #1 An LLM failure is classified as permanent or transient by the transcript translation worker, and the classification tolerates the provider's error payload shapes (exhausted quota, credit balance, bare 429, rejected key on 401/403) without depending on any single field being present
- [x] #2 A failure classified as permanent is not retried by the worker's internal backoff: the 3 attempts are reserved for transient failures
- [x] #3 The translation lock persists the failure kind alongside status=failed, so a reader can tell a terminal failure from a transient one
- [x] #4 reserve_translation refuses the reservation when the existing lock carries a terminal failure, while a transient failure stays re-reservable as it is today
- [x] #5 A source whose translation failed terminally is excluded from artifact generation with an excluded_reason, instead of counting as pending, matching the guarantee already stated in the _resolve_scope_sources docstring
- [x] #6 POST /api/artifacts no longer answers sources_not_ready with 'Retry in a moment' when the only cause is a terminally failed translation: the response lets the client tell that case apart from work still in progress
- [x] #7 Mobile stops retrying POST /api/artifacts as soon as the response signals a terminal cause, and surfaces a failure state instead of exhausting its 100 attempts
- [x] #8 Every translation_idempotence-dev lock left at status=failed by this incident is purged, verified with the AWS CLI, so the affected media items are no longer blocked
- [x] #9 ruff and mypy pass on the changed Python modules; npm run typecheck and ESLint pass on the changed mobile files
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### One classifier, read where the provider answers

`media_summarizer/utils/llm_failure.py` is new and holds the whole decision:
`classify_llm_failure(status_code=, body=, retry_after=)` returning
`LLMFailureKind.PERMANENT` or `.TRANSIENT`. It is called from exactly one place,
`_call_translation_llm`, which is the only code that sees the provider's raw
answer; every layer above only forwards the verdict.

The payload is an input contract we do not control, so nothing in the classifier
requires a field to be present:

1. **Substring markers first, on the whole body lowercased.** `insufficient_quota`,
   `credit_balance_exhausted`, `billing_hard_limit_reached`, `invalid_api_key`,
   `no credits remaining`, `context_length_exceeded`… They match whether the
   provider puts them in `error.type`, in `error.code`, or in prose, and they
   match before any status-code reasoning, so a 429 whose body says
   `insufficient_quota` is permanent no matter what the status suggests. The
   incident payload is exactly that shape (a 429 whose body carries both
   `"type": "insufficient_quota"` and "You have no credits remaining").
2. **Status codes.** `400, 401, 402, 403, 404, 422` are permanent — the request
   itself, the key, the account or the model is the problem.
3. **A bare 429** — no marker, no `Retry-After` — is read as **permanent**. The
   pay-wall 429 is the one that repeats forever; a genuine rate limit sends
   `Retry-After` or says so in words (`rate limit reached`, `requests per min`,
   `please try again in`), and those markers keep it transient.
4. **Everything else** (no status at all, 5xx, a `ClientError`, a timeout) is
   transient. The default is the conservative one everywhere in this change: an
   unclassified failure stays re-attemptable.

### The kind travels on the exception, then onto the lock

- `TranscriptTranslationError` gained a `failure_kind` keyword. `_translate_with_retry`
  reads `getattr(exc, "failure_kind", TRANSIENT)` inside its `except`, and on
  `PERMANENT` logs `translation.permanent_failure` and re-raises immediately —
  no `asyncio.sleep`, no second attempt. The 3-attempt budget now only buys
  retries for failures the next second may fix (AC#2). A missing
  `OPENAI_API_KEY` is permanent for the same reason: three attempts would be
  three identical no-ops.
- `TranslationOutcome.failure_kind` carries it back to the worker, which passes it
  to `mark_translation_failed(..., failure_kind=…)` on both terminal paths. The
  S3-download and unexpected-exception paths deliberately keep the transient
  default: an infrastructure hiccup is not the provider refusing.
- `mark_translation_failed` writes `failure_kind` next to `status=failed` (AC#3),
  and `mark_translation_done` `REMOVE`s it, so no stale kind can survive a
  success.

### The gate, and why it is a cooldown rather than a flat refusal

`reserve_translation`'s ConditionExpression went from
`attribute_not_exists(translation_fingerprint) OR #st = :failed` to that same
clause plus, on the `failed` branch: `attribute_not_exists(failure_kind) OR
failure_kind <> :permanent OR updated_at < :permanent_retry_cutoff` (AC#4). The
`attribute_not_exists` disjunct is not a legacy shim — in DynamoDB a comparison
against a missing attribute is false, so without it a lock whose kind was never
written would become unreservable forever, which is the exact dead end this gate
exists to prevent.

`PERMANENT_FAILURE_RETRY_AFTER_SECONDS = 3600` and `is_terminally_failed(lock)`
(a `TypeGuard`, so callers read `error_message` off it without a redundant
`is not None`) are the Python side of the same predicate: ISO-8601 UTC strings
sort lexicographically, so the reader and the ConditionExpression compare the
same `updated_at < cutoff` and can never disagree.

The cooldown exists because **nothing else in the system ever clears a lock**:
`translation_idempotence_v1` has no TTL (checked in
`infrastructure/terraform/modules/platform/dynamodb_core_tables.tf`), and no code
path deletes a row. A flat refusal would have meant "the owner tops the credit
up, and the couple stays dead until someone deletes a DynamoDB item by hand".
One hour bounds the waste at one provider call per hour per couple — against 75
in six minutes during the incident — and the recovery is automatic.

`mark_translation_in_progress` is deliberately *not* gated: the only way a
message reaches it without a reservation is the owner redriving the DLQ, which is
precisely the manual "try it now" the cooldown otherwise makes them wait for.

### The read paths stop asking

- **`/raw-content`** (`raw_content_service._resolve_translation`) was the main
  feeder: the mobile transcript view polls it every 3 s and each call re-reserved
  the failed lock. It now returns `translation_status: "failed"`,
  `translation_pending: false` on a terminally failed lock, before the
  reservation logic. The mobile screen already stops polling on that status, so
  the 20-attempt poll ends on the first response instead of driving 20 more
  reservations. A *transient* `failed` still falls through to the reservation, as
  before.
- **Artifact scope resolution.** `resolve_or_enqueue_translated_transcript`
  raises the new `TranslationPermanentlyFailedError` instead of reserving, both
  when it reads a terminal lock up front and when a refused reservation turns out
  to be one on re-read (that tail used to fall back to `pending_status = QUEUED`,
  i.e. report "in progress" for something that had already given up).
  `resolve_scope_sources.resolve_one` catches it and returns
  `ArtifactSource(excluded=True, excluded_reason="translation_failed")` (AC#5),
  next to the pre-existing `transcript_unavailable`; both reasons are now named
  constants. The docstring that promised this and did not deliver it was rewritten
  to say which two cases "never arrives" covers.

### The 409 that means "stop", next to the 409 that means "wait"

A scope where *some* sources are excluded for a failed translation and the rest
are readable now just generates on the rest — that was already the point of
excluding rather than aborting. What was missing is the empty case: it would have
surfaced as `scope_empty` ("no source with a usable transcript **yet**"), which is
the same lie in a different sentence. So `enforce_scope_ceilings`, when
`source_count == 0`, raises the new `ArtifactTranslationFailedError` if any
exclusion carries `translation_failed`, and `ArtifactScopeEmptyError` otherwise.

The endpoint answers it `409 {error_code: "translation_failed", failed_count,
failed_titles, terminal: true}` (AC#6), and `sources_not_ready` now carries
`terminal: false`. Two 409s with the opposite instruction share a status, so the
boolean is what lets any client tell them apart without an error-code table.
Documented in `docs/CANONICAL_MEDIA_API_CONTRACT.md`, in the "Typed refusals"
table and the paragraph under it.

### AC#7: the 100-attempt loop the task describes no longer exists

The premise in the description ("Mobile retries `POST /api/artifacts` every 3
seconds, bounded to 100 attempts") is stale — that loop was already replaced by a
single POST plus `describeArtifactRefusal`, and the comment at
`mobile/app/media/[id].tsx:555` records why. Verified: `handleGenerate` in both
`app/media/[id].tsx` and `app/media/collections/[id].tsx` posts once and renders
the refusal. So the mobile half of this AC is the wording — a terminal refusal
must not read like a wait:

- `describeArtifactRefusal` gained `case "translation_failed"`, using
  `failed_count` to pick between a collection sentence and a single-item one.
- Three new i18n keys (`artifacts.refusal.translationFailed`,
  `artifacts.refusal.sourcesTranslationFailed.one/.other`) in all 11 catalogues —
  `en` is the type reference, so a missing one is a `tsc` error. None of them says
  "in a moment"; they all say the retry will not happen on its own.

The other live loop, the raw-content translation poll (3 s × 20), is the one the
`/raw-content` change above terminates on its first response.

### AC#8 — dev locks purged

`aws dynamodb scan --region eu-west-3 --table-name translation_idempotence-dev`
filtered on `status = failed` found exactly 2 items out of 26:

- `bc11ff98…` — the incident lock (`1d084c16-….md` / `fr`), error message
  `translation_failed_after_3_attempts: translation_llm_http_429: … "type":
  "insufficient_quota"`.
- `ce361f0f…` — an older one from 2026-08-02 (`6b480c78-….txt` / `fr`),
  `unexpected: TranslationInProgressError`.

Both deleted with `delete-item --return-values ALL_OLD` (which echoed the
attributes above), then a re-scan on the same filter returned `Count: 0`,
`ScannedCount: 24`.

### AC#9 — checks

- `ruff check` clean and `mypy` clean on the 7 changed Python modules
  (`Success: no issues found in 7 source files`).
- `cd mobile && npm run typecheck` clean, `npx eslint` clean on the 12 changed
  mobile files.

### Not verified here

The deploy is what makes the new behaviour observable, and it happens on push to
`main`, after this branch is merged. The owner's visual check from the description
— a media whose translation failed for good is usable and never stuck behind
"Retry in a moment" — therefore stays a post-deploy step; the easiest way to
reproduce the terminal case is a deliberately invalid `OPENAI_API_KEY`, since the
classifier treats a 401 as permanent without needing an exhausted balance.
<!-- SECTION:NOTES:END -->
