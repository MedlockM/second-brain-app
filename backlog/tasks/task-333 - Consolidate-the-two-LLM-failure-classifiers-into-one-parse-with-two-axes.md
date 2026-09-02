---
id: task-333
title: Consolidate the two LLM failure classifiers into one parse with two axes
status: Done
updated_date: '2026-09-02 10:48'
assignee: []
created_date: '2026-09-01 19:35'
labels:
  - observability
  - translation
  - artifacts
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Observed

`task-327` and `task-330` were implemented in parallel and each created a classifier for the same OpenAI error payload. The two modules differ by one letter:

- `media_summarizer/utils/llm_failure.py` (task-327) — `classify_llm_failure()`, axis *is this worth retrying*: `transient` | `permanent`. Matches ~30 substring markers anywhere in the raw body, then falls back on the status code.
- `media_summarizer/utils/llm_failures.py` (task-330) — `refusal_reason_for_status()`, axis *what must the operator do*: `quota` | `authentication` | `rate_limit` | `None`. Matches 3 billing markers, then maps the status code.

The two axes genuinely do not reduce to one another — an unknown model is permanent without being a provider refusal, a named rate limit is a provider refusal without being permanent — so keeping both classifications is right. What is wrong is that they are **two independent parses of the same bytes**, and `transcript_translation.py:332-340` calls both on the same `(status, body)` pair inside a single `raise`.

### The two parses already disagree

On a 429 whose body names a billing wall in words only the first module knows:

| Body on a 429 | `classify_llm_failure` | `refusal_reason_for_status` |
|---|---|---|
| `credit_balance_exhausted` | `permanent` | `rate_limit` |
| `no credits remaining` | `permanent` | `rate_limit` |
| `billing_hard_limit_reached` | `permanent` | `quota` |
| empty body, no `Retry-After` | `permanent` | `rate_limit` |

The first three rows are a plain marker-list drift: nine billing markers on one side, three on the other. The last row is a deliberate design choice of task-327 (a 429 that names nothing is read as a billing wall) that task-330 never learned. In every one of these cases the pipeline stops retrying because the failure is permanent, while the alarm layer emits `refusal_reason = rate_limit` — the one value that tells the operator to do nothing and wait. The outage that motivated task-330 is precisely the one this mismatch mislabels.

### The retry axis is not read where it would help

`workers/artifact_generator/worker.py:177` reads only `refusal_reason_for_status()`. A quota refusal raises `LlmProviderRefusedError`, `lambda_handlers.py` turns it into `batchItemFailures`, and SQS redelivers the record twice more. The asymmetry task-327 established — never hammer a billing wall — is enforced in the translation path and nowhere else, because the artifact worker has no access to the axis that would tell it.

## Scope

One module, one parse of the body, two attributes out. Nothing here is a migration: `llm_failures.py` is deleted in the same run, no shim, no re-export, no deprecation window — the five importing modules are updated in place.

The classification *values* are a contract with `infrastructure/terraform/modules/platform/llm_alerts.tf`: the `llm.generation_failed` event name, the `FailureKind` values (`provider_refused` | `other`) and the `refusal_reason` values must come out unchanged, or the metric filters silently stop matching. The one value that must change is the bare-429 case, where the two modules contradict each other and task-327's reading wins.

## Owner note

No AC covers the alarms firing — `enable_alarms = false` in every env, so neither LLM alarm exists in AWS. What is checkable from the worktree is that the log event still matches its filter, via `aws logs test-metric-filter` against real CloudWatch, the way task-330 checked it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A single module holds the classification, `media_summarizer/utils/llm_failures.py` no longer exists, and no module re-exports its names for compatibility
- [x] #2 One function parses the provider answer once and returns both axes — the retry kind and the refusal reason — so no caller classifies the same body twice
- [x] #3 The billing, credential and rate-limit markers exist in exactly one list each, and the refusal reason is derived from those same lists rather than from a second shorter set
- [x] #4 A body naming a billing wall on a 429 (`credit_balance_exhausted`, `no credits remaining`) classifies as a quota refusal and not as a rate limit, and a bare 429 with no marker and no `Retry-After` does the same, consistent with the retry axis
- [x] #5 The artifact generator reads the retry axis and stops re-consuming its SQS deliveries on a permanent refusal, the way the translation path already does
- [x] #6 The `llm.generation_failed` event name and every `FailureKind` and `refusal_reason` value the Terraform metric filters read are unchanged
- [x] #7 `aws logs test-metric-filter` against the real CloudWatch confirms both worker event shapes still match the filter patterns in `llm_alerts.tf`
- [x] #8 The surviving module's docstring states what each axis decides and why one cannot be derived from the other, so the next reader does not collapse them again
- [x] #9 `ruff` and `mypy` pass on `media_summarizer`
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### The singular file survives, and it holds everything

`llm_failure.py` (task-327) absorbed the whole content of `llm_failures.py`
(task-330) and the plural file is deleted — no shim, no re-export, no
`__init__` forwarding. The choice of survivor was made by AC#1, but it is also
the right one: the retry axis is persisted verbatim on translation locks
(`translation_idempotence.py` writes `failure_kind = permanent`), so its module
is the one with a data contract behind it.

The module now holds, in one place: `LLMFailureKind` (axis 1), the `REFUSAL_*`
values (axis 2), `LLM_GENERATION_FAILED_EVENT` and the two `FAILURE_KIND_*`
alarm-dimension values, the four marker lists, `LlmFailure`,
`LlmProviderRefusedError` and `log_llm_generation_failure()`. Five importing
modules updated in place; `grep -rn llm_failures` returns nothing outside the
backlog history.

### One parse, two axes, four lists

`classify_llm_failure(status_code=, body=, retry_after=)` returns a frozen
`LlmFailure(kind, refusal_reason)`. Both call sites — `_call_translation_llm`
and `_call_llm` — call it exactly once on the `(status, body, Retry-After)` triple
they already had in hand, and the two disagreeing readings of the same bytes are
gone by construction rather than by keeping the two lists in sync.

The markers are split by *what they mean*, and each list decides both axes at
once, which is what makes a second shorter list impossible:

| list | axis 1 | axis 2 |
|---|---|---|
| `_BILLING_MARKERS` | `permanent` | `quota` |
| `_CREDENTIAL_MARKERS` | `permanent` | `authentication` |
| `_UNPROCESSABLE_REQUEST_MARKERS` | `permanent` | `None` |
| `_PACING_MARKERS` (429 only) | `transient` | `rate_limit` |

The billing list went from task-327's ten entries to six, and it matches strictly
more bodies than before: `billing` — task-330's own broad marker, which task-327
never had — was added, and the five wordings it or `quota` already subsume as bare
substrings were dropped (`insufficient_quota`, "exceeded your current quota",
`billing_hard_limit_reached`, `billing_not_active`, "check your plan and
billing"). A list holding both the broad and the narrow form of the same word is
what invites the drift this task exists to remove. `payment_required`,
`credit_balance_exhausted` and the two prose credit wordings stay: no broad marker
covers them.

`_PACING_MARKERS` merges task-327's rate-limit wordings with its
provider-overload ones (`server_error`, `engine_overloaded`, `service
unavailable`). They are consulted only inside the 429 branch, where both mean the
same thing — the moment, not the account — and where task-330 already answered
`rate_limit` for every non-billing 429. Outside a 429 they would change nothing:
a 400 or a 404 is permanent whatever the prose says, and a 5xx falls through to
transient anyway.

### The four rows of the disagreement table

All four now answer the same thing on both axes:

| body on a 429 | before (kind / reason) | after |
|---|---|---|
| `credit_balance_exhausted` | permanent / rate_limit | permanent / quota |
| `no credits remaining` | permanent / rate_limit | permanent / quota |
| `billing_hard_limit_reached` | permanent / quota | permanent / quota |
| empty body, no `Retry-After` | permanent / rate_limit | permanent / quota |

Only the refusal reason moved, and only towards the retry axis, which is the
direction the task's Scope section specified: task-327's reading of a bare 429 as
a billing wall wins. Nothing that was `transient` became `permanent`, so no retry
budget was silently shortened.

### The artifact worker now reads the retry axis (AC#5)

`LlmProviderRefusedError` carries `failure_kind` alongside `refusal_reason`
(keyword-only, no default: the two raise sites state the axis explicitly). In
`process_message`, after the failure event is emitted and the entry is marked
terminal, a `permanent` kind logs `artifact.delivery_acknowledged` and **returns**
instead of re-raising — no `batchItemFailures` entry, so SQS deletes the record
instead of redelivering it twice more and then filling the DLQ with messages
nobody can usefully replay. The default is `transient`, read with `getattr`, so an
`aiohttp` error, a validation error or anything unclassified still gets its three
deliveries.

The new event carries `failure_kind = permanent`, i.e. the *retry* vocabulary, and
is therefore invisible to `LlmGenerationFailures` — confirmed below. The runbook's
"First Response" was rewritten accordingly: on `quota` and `authentication` there
is nothing left in the artifact-generator DLQ to replay, the artifact entries are
`failed` and the generation has to be asked for again once the account is fixed.

### Same event, same values, checked against real CloudWatch (AC#6, AC#7)

`llm.generation_failed`, `provider_refused`/`other`, `quota`/`authentication`/
`rate_limit`: all unchanged, only moved into the surviving module. Only the file
path in `llm_alerts.tf`'s header comment, the runbook and `LOGGING_SYSTEM.md`
changed.

`aws logs test-metric-filter` against real CloudWatch with the exact pattern of
`llm_alerts.tf` (`{ $.event = "llm.generation_failed" }`), on three faithful event
payloads plus one control:

- artifact worker, permanent quota refusal (429): **matches**
- translation worker, quota refusal off `TranslationOutcome`: **matches**
- artifact worker, `failure_kind = other` (a flashcards validation error): **matches**
- the new `artifact.delivery_acknowledged` line: **does not match** — the
  stand-down log cannot pollute the metric or its `FailureKind` dimension

The two filters themselves are still not deployed (`describe-metric-filters
--filter-name-prefix llm-generation-failed` returns `[]`, consistent with
task-330's plan being "2 to add" and never applied), which is why the pattern is
tested directly rather than through the metric.

### Checks

- `ruff check media_summarizer/`: All checks passed.
- `mypy media_summarizer/`: Success, no issues in 178 source files.
- `terraform fmt -check -recursive modules/platform` clean, `terraform validate`
  Success on the `platform` module (comment-only change there).
- No automated tests were added, per the project rule.
<!-- SECTION:NOTES:END -->
