---
id: task-195
title: Consolidate flashcards/notes/quiz/summary workers into a single artifact-generator
status: Done
assignee: []
created_date: '2026-06-12 14:45'
labels:
  - refactor
  - backend
  - infrastructure
dependencies:
  - task-193
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Today the artifact generation pipeline has 4 (or 5 once task-193 ships) near-identical workers — `flashcards`, `notes`, `quiz`, `summarization` (and post-task-193: `summary_short`, `summary_detailed`) — each with its own SQS queue, Lambda function, ESM, DLQ, IAM section, file in `media_summarizer/workers/`, and Lambda handler. Their docstrings (e.g. `summarization_worker.py:5`) explicitly state they are "consistent with notes, flashcards, and quiz workers". An audit confirms this:

- All four follow the same skeleton: `_build_<kind>_prompt`, `_strip_code_fences`, `_validate_<kind>_payload`, `_download_transcript`, `_call_llm_for_<kind>`, `process_message`, `poll_queue`, `main`. Diff between any two pairs is ~450 lines of boilerplate per pair (out of ~400 lines per file).
- All read `transcript_s3_key` from S3 → call OpenAI → write a structured JSON artifact via `complete_artifact_generation`.
- All use the canonical `artifact_id` contract from task-123.
- `local.workers` in `lambda_workers.tf` even sets identical `memory_size = 512` and `timeout = 300` for the four (post-task-193: same for the two new summary entries).

The only meaningful per-kind variation is **3 things**: the prompt, the validation schema, the default LLM model. Everything else (S3 download, API call, retry, log context, error mapping, status transitions, handler wiring) is duplicated 4× / 5×.

## Why this matters

- **Maintenance × N**: every cross-cutting change (e.g. switch from raw `aiohttp` to a shared client, add prompt caching, change retry policy, instrument with new metrics) has to be done 4 times, and nothing prevents drift between files (already happened: `notes/worker.py` uses `pydantic.BaseModel` validators while `flashcards/worker.py` does manual dict checks).
- **Surface to maintain**: 4 ESMs, 4 IAM ARN entries, 4 DLQs, 4 handler entries, 4 deploy targets, 4 sets of CloudWatch dashboards/alarms. None of this gives any operational benefit (see "what we don't lose").
- **No real isolation today**: the rationale for separate queues would be priority isolation or differentiated retry policies. Today: same `visibility_timeout_seconds = 1800`, same `maxReceiveCount = 3`, no `reserved_concurrency`. The account-wide Lambda limit (currently 10) means a burst on any one queue starves the others regardless. The "isolation" is cosmetic.

## Proposed design

A single worker `media_summarizer/workers/artifact_generator/worker.py` that:

1. Polls **one** queue: `artifact-generator-queue`.
2. Reads `body.artifact_type` from the SQS message (already populated by `artifact_service.request_artifact_generation`).
3. Dispatches via a registry:

   ```python
   GENERATORS: dict[MediaArtifactType, ArtifactGenerator] = {
       MediaArtifactType.FLASHCARDS:       FlashcardsGenerator(),
       MediaArtifactType.NOTES:            NotesGenerator(),
       MediaArtifactType.QUIZ:             QuizGenerator(),
       MediaArtifactType.SUMMARY_SHORT:    SummaryShortGenerator(),
       MediaArtifactType.SUMMARY_DETAILED: SummaryDetailedGenerator(),
   }
   ```

4. Each `ArtifactGenerator` is a small class (or a tuple of `prompt_fn, validator, default_model`) — ~50 lines each instead of 400. The shared logic (S3 download, API call, retries, logging, status transitions, error mapping) lives in the worker once.

`get_artifact_queue()` in `core/services/artifact_service.py` returns `ARTIFACT_GENERATOR_QUEUE` for all kinds in this set. The producers (`/api/artifacts/generate`, internal callers) don't need to change — they already call `request_artifact_generation(artifact_type=...)` which uses the mapping function.

## Expected gain

| | Before (post-193) | After |
|---|---|---|
| Worker files | 5 (~1900 lines total) | 1 worker + 5 small generators (~600 lines total) |
| SQS queues for artifacts | 5 queues + 5 DLQs | 1 queue + 1 DLQ |
| Lambda functions | 5 | 1 |
| Lambda handlers | 5 | 1 |
| IAM ARN entries (queues) | 5 + 5 | 1 + 1 |
| ESMs polling 24/7 | 5 | 1 |
| Cold-start surface | 5 separate containers warm independently | 1 container, warmer for any artifact request |

## Concurrency: not a regression

A common reflex is "won't requests for different artifact kinds block each other in a single queue?" No: SQS+Lambda invokes the function in parallel up to `maximum_concurrency`, each invocation is an isolated container. With `batch_size = 1`, msg₁ (flashcards) and msg₂ (summary) start two independent Lambda invocations simultaneously. The current 5-queue setup gives no real isolation either: same account-level concurrency limit, no reserved concurrency per queue, identical retry/timeout values.

If priority differentiation is ever needed (e.g. summaries should preempt notes), the right tool is **a `priority` field in the message + reserved concurrency** — not separate queues per kind.

## Phasing

Not a single big-bang. Phased so each step is reversible:

1. **Phase 1 — extract**: pull each per-kind variation into a `generators/` module (one small file per kind). Existing workers keep running, but now both call into the same generator object. Goal: prove the abstraction holds, no behaviour change.
2. **Phase 2 — provision**: add `artifact-generator-queue` + `artifact-generator-dlq` + new Lambda + ESM + handler + IAM, alongside the existing 5. Deploy.
3. **Phase 3 — flip producers**: change `get_artifact_queue()` to return the new queue for all 5 artifact types. Deploy. The 5 old workers stop receiving messages but remain wired (zero risk of regression).
4. **Phase 4 — soak**: run for ≥1 week, monitor `NumberOfMessagesSent` on the 5 old queues = 0, and `artifact-generator-queue` healthy.
5. **Phase 5 — remove**: delete the 5 old worker files, packages, queues, DLQs, IAM entries, handlers, ESMs. Add a CI guard in `pr.yml` (mirror task-143 / task-194 pattern).

This phasing means **rollback at any point is trivial**: revert `get_artifact_queue()` and producers fall back to the per-kind queues immediately.

## Out of scope

- Mobile/API contract changes — the wire format (`artifact_type`) is already stable and identical across kinds.
- Refactoring the 4 ingestion video workers (youtube/tiktok/instagram/x) — different problem (extraction variance is real, not boilerplate); track separately if/when a 5th source appears.
- Priority/preemption between artifact kinds — separate task once there's a product reason.

## Pre-conditions

- task-193 deployed and stable (so `summary_short` / `summary_detailed` have proven schemas to fold into the registry).
- Optional but recommended: task-194 done first, so we don't need to migrate the legacy `summary` enum value through the new worker only to delete it shortly after. Alternatively, do task-195 → task-194 — either order works as long as 195 doesn't need to support `summary` (legacy).

## References

- task-72 (benchmark that picked the LLM models — preserve those defaults)
- task-123 (canonical `artifact_id` contract — kept by all generators)
- task-193 / task-194 (the summary_short/summary_detailed activation and legacy removal that frame this refactor)
- `media_summarizer/workers/{flashcards,notes,quiz,summarization,summary}/` (the files to consolidate)
- `media_summarizer/core/services/artifact_service.py:212-221` (`get_artifact_queue` — the single producer-side flip point)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 New module `media_summarizer/workers/artifact_generator/` (worker + per-kind generators) with shared S3 download, LLM call, retries, validation entry point, and status transitions
- [ ] #2 Each kind's prompt + schema validator + default model preserved bit-for-bit from the existing workers (no behaviour change for the LLM output)
- [ ] #3 New SQS queue `artifact-generator-queue` + DLQ provisioned in `sqs.tf` with the same `visibility_timeout_seconds = 1800` and `maxReceiveCount = 3` as the kinds it replaces
- [ ] #4 New Lambda function + ESM provisioned in `lambda_workers.tf` (`memory_size = 512`, `timeout = 300`); deploy-lambda.yml picks it up via dynamic discovery
- [ ] #5 New Lambda handler in `lambda_handlers.py`; IAM updated for the new queue ARN
- [ ] #6 `get_artifact_queue()` returns the new queue for `flashcards`, `notes`, `quiz`, `summary_short`, `summary_detailed` (after Phase 3 flip)
- [ ] #7 End-to-end: requesting each of the 5 artifact kinds for a single media item produces 5 artifacts with the expected schema, written to the right S3 buckets (buckets stay per-kind, only the queue is shared)
- [ ] #8 Soak ≥ 7 days with the 5 old queues at `NumberOfMessagesSent = 0` and the new queue healthy (no DLQ growth, no schema validation regressions)
- [ ] #9 The 5 old worker files/packages, the 5 old queues + DLQs, IAM entries, handlers, and ESMs all removed; `terraform apply` clean
- [ ] #10 CI guard in `pr.yml` fails if `flashcards-queue`, `notes-queue`, `quiz-queue`, `summarization-queue`, `summary-short-queue`, or `summary-detailed-queue` reappears in `media_summarizer/` or `infrastructure/terraform/`
- [ ] #11 Documentation: `docs/INGESTION_WORKERS_PROVIDERS.md` updated to describe the unified artifact-generator and link to per-kind generator files
<!-- AC:END -->
