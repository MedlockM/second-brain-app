---
id: task-333
title: Consolidate the two LLM failure classifiers into one parse with two axes
status: To Do
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
- [ ] #1 A single module holds the classification, `media_summarizer/utils/llm_failures.py` no longer exists, and no module re-exports its names for compatibility
- [ ] #2 One function parses the provider answer once and returns both axes — the retry kind and the refusal reason — so no caller classifies the same body twice
- [ ] #3 The billing, credential and rate-limit markers exist in exactly one list each, and the refusal reason is derived from those same lists rather than from a second shorter set
- [ ] #4 A body naming a billing wall on a 429 (`credit_balance_exhausted`, `no credits remaining`) classifies as a quota refusal and not as a rate limit, and a bare 429 with no marker and no `Retry-After` does the same, consistent with the retry axis
- [ ] #5 The artifact generator reads the retry axis and stops re-consuming its SQS deliveries on a permanent refusal, the way the translation path already does
- [ ] #6 The `llm.generation_failed` event name and every `FailureKind` and `refusal_reason` value the Terraform metric filters read are unchanged
- [ ] #7 `aws logs test-metric-filter` against the real CloudWatch confirms both worker event shapes still match the filter patterns in `llm_alerts.tf`
- [ ] #8 The surviving module's docstring states what each axis decides and why one cannot be derived from the other, so the next reader does not collapse them again
- [ ] #9 `ruff` and `mypy` pass on `media_summarizer`
<!-- AC:END -->
