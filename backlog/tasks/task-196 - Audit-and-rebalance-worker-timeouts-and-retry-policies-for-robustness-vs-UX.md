---
id: task-196
title: Audit and rebalance worker timeouts and retry policies for robustness vs UX
status: Done
assignee: []
created_date: '2026-06-12 15:00'
updated_date: '2026-06-14 21:36'
labels:
  - reliability
  - backend
  - infrastructure
  - scoping
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Each worker today has **three independent timeout knobs** (Lambda timeout, SQS visibility timeout, in-app `max_retries`) plus per-worker external-call timeouts (LLM, Apify, Deepgram, yt-dlp, …). They were set incrementally as features landed, never cross-checked. An audit shows the values are **inconsistent and partially wrong** — some violate the SQS+Lambda timing invariants, some give a poor user experience, some are dangerously generous.

This task audits all 16 workers, lists the failure modes induced by the current values, and proposes a coherent retry/timeout policy per worker class (ingestion, transcription, artifact, event-fanout, scheduled). No implementation in this task — produce the recommendation, owner validates, then implementation tracked separately.

## Why this matters now

User-perceived latency on a happy ingestion = sum of (queue wait + Lambda runtime + LLM call) along the pipeline. With ~5 hops (resolve → transcribe → summarize → 3 artefacts), even small inflations (excess retry on a transient error, oversized visibility timeout that delays redrive) compound into multi-minute waits. Conversely, undersized timeouts cause silent message loss and the worker re-processing the same message N times.

V1 onboarding is imminent; getting this right before users hit it materially.

## Current state — raw data

### Lambda timeout vs SQS visibility timeout (the SQS+Lambda invariant)

**Rule**: SQS visibility timeout MUST be ≥ Lambda timeout, ideally with a buffer (AWS recommends `6 × lambda_timeout` for in-flight retries). Otherwise a slow invocation makes the message reappear on the queue while the Lambda is still processing it → duplicate processing.

| Worker | Lambda timeout | SQS visibility | Ratio | Status |
|---|---|---|---|---|
| `podcastindex_resolution` | (missing) | 300s | — | ⚠ Lambda timeout not visible in audit — verify |
| `article_extraction` | 60s | 360s | 6× | ✅ |
| `x_ingestion` | 60s | 300s | 5× | ✅ |
| `youtube_ingestion` | 60s | 720s | 12× | ⚠ Visibility very long for a 60s Lambda — investigate (or Lambda timeout is too low) |
| `instagram_ingestion` | 120s | 720s | 6× | ✅ |
| `tiktok_ingestion` | 120s | 720s | 6× | ✅ |
| `deepgram_transcription` | 120s | 3600s | 30× | 🔴 Visibility 60 min but Lambda only 120s? Either Lambda is grossly under-provisioned (a long episode would time out at 2 min — confirmed worker has its own concurrency) OR visibility is grossly over-provisioned (60 min = a stuck message takes an hour to retry) |
| `summarization` | 600s | 1800s | 3× | ⚠ Below 6× recommended, Lambda max could exceed visibility on a slow LLM |
| `document_parsing` | 300s | 3600s | 12× | ⚠ 1h visibility for 5min Lambda — slow redrive |
| `search_indexing` | 600s | 360s | **0.6×** | 🔴 **Lambda > visibility** — message reappears on the queue mid-execution → duplicate Algolia writes |
| `rss_feed_poll` | 60s | 720s | 12× | ⚠ Long visibility for short Lambda |
| `media_completed_events` | 120s | 360s | 3× | ⚠ Below 6× |
| `flashcards` | 60s | 1800s | 30× | 🔴 30 min visibility for a 60s Lambda — and a 60s LLM call may not fit (compare to `notes`/`quiz` at 300s Lambda) |
| `notes` | 300s | 1800s | 6× | ✅ |
| `quiz` | 300s | 1800s | 6× | ✅ |

**At least 3 hard inconsistencies** identified above (`search_indexing`, `flashcards`, possibly `deepgram_transcription`) that warrant root-cause investigation before any rebalance.

### `max_retries` — currently inconsistent

| Worker | `max_retries` | Source |
|---|---|---|
| `rss_feed_poll` | hardcoded `2` | `rss_feed_poll_worker.py:226` |
| `document_parsing` | hardcoded `3` | `document_parsing/worker.py:365` |
| `newsletter` | hardcoded `3` | `newsletter/worker.py:327` |
| `youtube_ingestion` | hardcoded `3` | `youtube_ingestion_worker.py:65` |
| `x_ingestion`, `tiktok`, `instagram`, `article` | env-var, default `3` | `*_WORKER_MAX_RETRIES` |
| `flashcards`, `notes`, `quiz`, `summarization`, `summary` | env-var, default `3` | `*_MAX_RETRIES` |
| `podcastindex_resolution` | `PODCASTINDEX_WORKER_MAX_RETRIES` (default 3) AND a separate `PODCASTINDEX_MAX_RETRIES=3` for an internal API loop | `podcastindex_resolution_worker.py:54-56` |

Issues:
- Some are hardcoded, some env-var → impossible to bump retries in one place
- `rss_feed_poll` is the only one at 2 (intentional? scheduled invocation, no user waiting?) — undocumented
- Several workers run **double retry layers**: SQS-level via `process_message_with_retry` + an internal API retry loop (e.g. PodcastIndex). That's `3 × 3 = 9` retries on the worst path, with each potentially blocking up to the Lambda timeout. Compounded latency on a transient failure can be 5+ minutes for the user.
- `maxReceiveCount = 3` on every queue interacts with this: SQS will redrive to DLQ on the 3rd visibility expiration, but `process_message_with_retry` increments based on `ApproximateReceiveCount`. Confirm both are aligned (should be: `max_retries` <= `maxReceiveCount`).

### External call timeouts

| Service | Default timeout | Where |
|---|---|---|
| OpenAI LLM | `LLM_TIMEOUT_SECONDS` env, default `180s` | flashcards, notes, quiz, summarization, summary |
| Audio download (push-mode Deepgram) | `_AUDIO_DOWNLOAD_TIMEOUT = 120s` | `deepgram_worker.py:258` |
| yt-dlp extract | `YTDLP_TIMEOUT_SECONDS` env, default `30s` | youtube_ingestion |
| YouTube subtitle fetch | `YOUTUBE_SUBTITLE_FETCH_TIMEOUT_SECONDS`, default `20s` | youtube_ingestion |
| Apify, Algolia, PodcastIndex, Deepgram | varies / not always set | scattered |

**Issue**: each LLM-using worker reads the same `LLM_TIMEOUT_SECONDS=180s` default but the Lambda timeouts differ (`flashcards` 60s vs `notes` 300s). **A 180s LLM call cannot complete in a 60s Lambda — flashcards will always TimeoutError on slow OpenAI responses**. Either Lambda timeout is wrong, or LLM timeout should be capped per-worker to `lambda_timeout - epsilon`.

## What the audit must produce

For each of the 16 workers, the deliverable is a one-page table with **the validated values** for:

1. **Lambda timeout** (chosen so that the slowest realistic happy path + 20% buffer fits, but no more)
2. **SQS visibility timeout** (= `~6 × lambda_timeout`, AWS recommendation; document if deliberately deviating)
3. **`maxReceiveCount`** (number of redrive attempts before DLQ)
4. **In-app `max_retries`** (must be `≤ maxReceiveCount` to be reachable)
5. **External-call timeouts per provider** (LLM, Apify, Deepgram URL, audio download, yt-dlp, Algolia, …) — capped by Lambda timeout
6. **Whether the failure mode is "retryable"** (transient: 5xx, network) or "non-retryable" (4xx, validation, bad input). Currently mixed: `x_ingestion`, `youtube`, `instagram` use a custom `retryable=True/False` flag on raised exceptions; others rely solely on receive count. Standardize.
7. **User-facing latency target** for the happy path of each worker — the budget that informs all the above

The audit must explicitly identify and resolve:
- 🔴 `search_indexing`: Lambda 600s > visibility 360s — fix
- 🔴 `flashcards`: Lambda 60s vs LLM 180s default — fix (likely raise Lambda to 300s like sibling artefact workers)
- 🔴 `deepgram_transcription`: visibility 3600s vs Lambda 120s — fix (one of the two is wrong by a factor of 30)
- ⚠ Double retry layers in podcastindex (and others?) — flatten or document the worst-case latency
- ⚠ Hardcoded vs env-var inconsistency in `max_retries`

## Methodology

1. **Measure** before deciding: pull p50/p95/p99 Lambda duration per worker from CloudWatch over the last 30 days. Don't guess durations.
2. **Map** each worker's external dependencies and their realistic worst-case latency (Apify cold start ~30s, Deepgram pull ~10-60s, OpenAI gpt-5 ~60-180s, yt-dlp IP block ~30s diagnose, …).
3. **Set Lambda timeout** = p99 + 20% buffer, capped at the SLO.
4. **Set visibility** = `6 × Lambda timeout` unless there's a documented reason (e.g. push-mode Deepgram needs the long visibility because the message is held while Lambda waits on Deepgram polling).
5. **Set `max_retries`** = `min(maxReceiveCount, 3)` and ensure the SQS-level retry IS the retry — no double-layer (or document why).
6. **Cap external timeouts** at `Lambda_timeout - 5s` so a slow upstream gets a clean error instead of a Lambda-killed half-response.
7. **Define one global UX SLO**: "happy path artefact ready within X minutes of submit". Reverse-engineer the per-worker budgets from this.

## Out of scope

- Implementation of the new values (separate task to apply Terraform + code changes)
- Replacing SQS+Lambda with a different fan-out mechanism (different debate)
- Multi-region failover
- task-195 (worker consolidation) — interacts with this but not blocked: this audit informs the values task-195 will use; task-195 implementation can pull from the validated table

## References

- AWS doc: [SQS visibility timeout vs Lambda timeout](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html)
- `media_summarizer/workers/base_worker.py` (the shared `process_message_with_retry` mechanic)
- `infrastructure/terraform/sqs.tf` and `lambda_workers.tf` (the canonical source of all timeout values)
- task-158 (the deepgram pull/push refactor that introduced explicit modes — context for revisiting deepgram visibility)
- task-143 (queue-name regression — reminder that infra hygiene matters here)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 CloudWatch p50/p95/p99 Lambda duration extracted for each of the 16 workers over the last 30 days; data attached to the task
- [ ] #2 Each external dependency's realistic worst-case latency documented (Apify cold start, Deepgram pull/push, OpenAI per model, yt-dlp, Algolia, PodcastIndex, …)
- [ ] #3 A single per-worker recommendation table produced with: Lambda timeout, SQS visibility, maxReceiveCount, in-app max_retries, external-call timeouts, retryable-vs-not policy, UX latency budget. Each value justified.
- [ ] #4 The 3+ hard inconsistencies flagged above (search_indexing visibility < Lambda, flashcards Lambda < LLM timeout, deepgram visibility 30× Lambda) explicitly resolved with a chosen value and rationale
- [ ] #5 Recommendation on whether `max_retries` should be hardcoded or env-var (one or the other, consistently) with rationale
- [ ] #6 Audit of double retry layers (SQS-level + internal API loops) — list every site, decide flatten or keep
- [ ] #7 A global UX SLO documented (e.g. "happy path summary ready within 3 min of submit") and per-worker budgets derived from it
- [ ] #8 Owner validation on the recommendation table (`owner_decision: ok`)
- [ ] #9 Follow-up implementation task created with the validated values (Terraform + code changes); not done in this task
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
**Mode**: initial

**Deliverable**: `docs/research/task-196-worker-timeouts-audit/README.md`

Comprehensive audit produced covering all 15 deployed workers (the task description mentioned 16, but Terraform shows exactly 15 Lambda functions -- `newsletter` and `summary` workers are not deployed as Lambdas).

Key findings:
1. The three "hard inconsistencies" flagged in the task description (search_indexing Lambda > visibility, flashcards Lambda < LLM, deepgram 30x ratio) do NOT exist in the current Terraform configuration. The Terraform source of truth shows all workers properly aligned with the 6x visibility/Lambda ratio.
2. Real issues identified: missing DLQ for podcastindex_resolution, tiktok Apify timeout = Lambda timeout (no buffer), inconsistent hardcoded max_retries, two workers lacking `process_message_with_retry`, and documented double-retry layers.
3. Recommended tiered UX SLO: 1 min (articles), 3 min (medium content), 5 min (long podcasts).
4. Recommended all `max_retries` be env-var configurable with consistent naming.

**Recommendation awaits owner validation** (owner_decision: pending).
<!-- SECTION:NOTES:END -->
