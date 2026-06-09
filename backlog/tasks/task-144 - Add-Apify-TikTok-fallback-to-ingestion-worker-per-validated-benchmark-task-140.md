---
id: task-144
title: >-
  Add Apify TikTok fallback to ingestion worker per validated benchmark
  (task-140)
status: Done
assignee: []
created_date: '2026-06-09 17:48'
labels:
  - backend
  - ingestion
  - tiktok
dependencies:
  - task-140
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

`task-140` benchmarked TikTok extraction strategies after Phase 4 e2e revealed that **TikTok's anti-bot rejects yt-dlp from AWS Lambda IPs on a subset of videos** (status `10204`, "Your IP address is blocked from accessing this post"). The block is not systematic — old/low-value videos pass, high-value/recent posts get blocked.

The owner's final decision (recorded in `docs/research/task-140-tiktok-extraction/README.md` Owner Validation block) is **hybrid yt-dlp + Apify TikTok actor as fallback for V1**, then switch the fallback to a residential proxy in V2 (tracked separately in task-145). The owner already populated `APIFY_TIKTOK_API_TOKEN` and `APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID` in `.env.example` and the live `.env`.

This task implements the V1 decision in the existing TikTok worker.

## Pre-requisites

1. Read `docs/research/task-140-tiktok-extraction/README.md` end to end. The owner's `Decision` field documents the V1 strategy and which Apify actor was chosen.
2. `.env.example` already exposes `APIFY_TIKTOK_API_TOKEN` and `APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID` (added during owner validation). Surface both in `media_summarizer/core/config.py` alongside the existing `APIFY_INSTAGRAM_*` / `APIFY_YOUTUBE_*` settings.
3. Runtime secret payload on AWS dev populated with both `APIFY_TIKTOK_*` values.

## Scope

### 1. Detect IP-block precisely

Add a `_is_ip_blocked_error(exc)` helper in `tiktok_ingestion_worker.py` that recognizes the yt-dlp signature for the `10204` IP block:
- error message contains `"IP address is blocked"` (case-insensitive), or
- yt-dlp `ExtractorError` carries `status_code == 10204` in its payload.

Do **not** trigger the Apify fallback on other yt-dlp errors (geo restriction, deleted video, rate limit, parse error). Those keep their existing handling.

### 2. New Apify fetcher

Add `_fetch_apify_tiktok_transcript(video_url)`:
- Read `APIFY_TIKTOK_API_TOKEN`, `APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID` from `settings` at call time (no module-level reads).
- Replicate the Apify HTTP pattern from `InstagramApifyResolver._run_actor()` (`media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py:693-792`): `POST /v2/acts/{actor_id}/runs` → poll `GET /v2/actor-runs/{runId}` → `GET /v2/datasets/{datasetId}/items`.
- Honor `APIFY_TIMEOUT_SECONDS`, `APIFY_POLL_INTERVAL_SECONDS`, `APIFY_MAX_POLLS`.
- Normalize the actor output to the existing TikTok worker contract used downstream by the S3 upload + completion-event publication path. Match the field shape produced by the current native-subtitle path (`text`, `language`, `language_code`, `segments_count`, `source_detail="apify_tiktok"`, `source_url`, `fetched_at`).

If `InstagramApifyResolver._run_actor()` is already extractable into a shared helper at this point (post task-129), reuse it. Otherwise, KISS: copy the `_run_actor` shape inline. Don't refactor for hypothetical future reuse.

### 3. Orchestration refactor

Refactor `process_tiktok_message()` (currently yt-dlp → Deepgram URL fallback):
- **Step 1**: try the existing yt-dlp native-subtitle path. If success → upload to S3, publish completion, done.
- **Step 2 (new)**: on yt-dlp failure, branch on `_is_ip_blocked_error()`:
  - **IP-blocked** → call `_fetch_apify_tiktok_transcript()`. On success, upload + publish. On Apify failure, follow the failure table in §6 of the README.
  - **Any other yt-dlp error** → keep existing behavior (Deepgram URL fallback or graceful failure with the matching `user_message`).
- **Step 3**: if Apify also returns no usable transcript (e.g. private video, actor failed), mark the job failed with the right `user_message` from the README.

The Deepgram-URL fallback path stays intact as the **non-IP-block** failure route. It is independent of the Apify fallback added here.

### 4. Error code mapping

Extend the `TikTokIngestionError` hierarchy with:
- `apify_actor_failed` (non-retryable on auth/config: 401, 403, malformed actor ID).
- `apify_quota_exceeded` (retryable, SQS visibility-timeout backoff: 429).
- `apify_timeout` (retryable up to `TIKTOK_WORKER_MAX_RETRIES`: 5xx + network).
- `tiktok_ip_blocked_unrecoverable` (raised when both yt-dlp and Apify fail on an IP-blocked video — non-retryable, surfaces user message from README §6 "IP blocked (both) after all retries").

Existing codes (`tiktok_unavailable`, rate-limited, etc.) preserved.

### 5. Tests

- Unit tests for `_is_ip_blocked_error()`: exact `10204` match, "IP address is blocked" message, and a non-match (e.g. geo restriction) that must not trigger Apify.
- Unit tests for `_fetch_apify_tiktok_transcript()` mirroring `media_summarizer/tests/test_instagram_apify_resolver.py`: success with timed segments, success with flat text, 401/429/5xx mapping, actor-failed run status, video-unavailable payload.
- Update `tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion` to add a second fixture URL known to be IP-blocked (cf. README §1) so the Apify fallback path is exercised end-to-end. Keep the existing happy-path NatGeo URL.

### 6. Observability

Add CloudWatch metrics under `infrastructure/observability/`:
- `apify_tiktok_api_calls{outcome}` with `outcome ∈ {success, actor_failed, quota_exceeded, timeout, unavailable}`.
- `apify_tiktok_credits_consumed` (1 per call default; actual cost from actor payload when present).
- Alarm: failure rate > 10% over 5 minutes → warn channel.
- A separate counter `tiktok_ip_block_detected_total` so the V2 migration (task-145) has hard data on how often the fallback fires.

### 7. ADR update

Update `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md` (or the TikTok-specific ADR if one exists):
- Mark the previous TikTok section (yt-dlp → Deepgram URL) as superseded.
- Add a "TikTok extraction (V1, post-task-140)" section: yt-dlp primary, Apify fallback only on IP block, Deepgram URL fallback for non-IP-block yt-dlp failures. Reference the owner's decision in `docs/research/task-140-tiktok-extraction/README.md` and the V2 follow-up task-145.

## Constraints

- Pre-production, **no backwards compatibility**: hard-code the new orchestration; no feature flag.
- **No hardcoded actor ID** — everything reads from `APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID`. The owner's `Decision` field is the single source of truth for which actor to use.
- Output contract unchanged — artifact workers (summarization, notes, flashcards, quiz) consume transcripts via S3 only and must keep working without code changes.
- Keep yt-dlp as primary. Don't widen the Apify fallback to non-IP-block errors — that's not the V1 decision.

## Verification

1. `pytest media_summarizer/tests/ -v` passes (especially the new TikTok worker unit tests).
2. AWS dev e2e: submit 5 TikTok URLs covering both branches — 3 expected to pass via yt-dlp (NatGeo, CNN, an old viral video), 2 expected to be IP-blocked and recover via Apify (a recent BBC News post and another high-value account). Verify CloudWatch logs (`tiktok_ip_block_detected_total` ticks for the 2 blocked, `apify_tiktok_api_calls{outcome=success}` ticks twice), DynamoDB `completed`, S3 transcript object.
3. `pytest tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion -v` passes including the new IP-blocked fixture.
4. CloudWatch metrics + alarm provisioned.
5. ADR reflects the new V1 strategy and references task-140 + task-145.

## References

- Worker: `media_summarizer/workers/tiktok_ingestion_worker.py` — error class line 104; `process_tiktok_message()` near the bottom; existing yt-dlp native-subtitle and Deepgram-URL paths to preserve.
- Apify HTTP reference: `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py:693-792`.
- Config: `media_summarizer/core/config.py` already wires `APIFY_INSTAGRAM_*` / `APIFY_YOUTUBE_*`; add `APIFY_TIKTOK_API_TOKEN` and `APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID` next to them.
- E2E fixture: `tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion` (NatGeo URL).
- Infra: `infrastructure/terraform/lambda_workers.tf` (`tiktok_ingestion`), `infrastructure/terraform/sqs.tf` (`aws_sqs_queue.tiktok_ingestion`).
- ADR: `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`.
- Owner's decision + chosen actor: `docs/research/task-140-tiktok-extraction/README.md` (Owner Validation block).
- V2 follow-up (residential proxy migration): task-145.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `APIFY_TIKTOK_API_TOKEN` and `APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID` exposed in `media_summarizer/core/config.py`
- [ ] #2 `_is_ip_blocked_error(exc)` exists and returns true only for yt-dlp `status 10204` / 'IP address is blocked', false for any other yt-dlp error
- [ ] #3 `_fetch_apify_tiktok_transcript()` exists and returns the worker's normalized transcript contract (`text`, `language`, `language_code`, `segments_count`, `source_detail='apify_tiktok'`, `source_url`, `fetched_at`)
- [ ] #4 `process_tiktok_message()` orchestrates yt-dlp primary → Apify only on IP block → Deepgram URL fallback otherwise → graceful failure with the right `user_message`; Deepgram-URL path remains intact for non-IP-block errors
- [ ] #5 `TikTokIngestionError` hierarchy gained `apify_actor_failed`, `apify_quota_exceeded`, `apify_timeout`, `tiktok_ip_blocked_unrecoverable` with correct retryable flags; existing codes preserved
- [ ] #6 Unit tests cover `_is_ip_blocked_error()` (positive, negative, malformed) and `_fetch_apify_tiktok_transcript()` (timed-segments success, flat-text success, 401/429/5xx mapping, actor-failed run, video-unavailable payload)
- [ ] #7 `tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion` covers both a happy-path URL (yt-dlp success) and a known IP-blocked URL (Apify fallback) and passes against AWS dev
- [ ] #8 5 representative TikTok URLs (3 yt-dlp-success, 2 IP-blocked) ingest successfully on AWS dev `eu-west-3`, verified through CloudWatch logs + DynamoDB job status + S3 transcript object
- [ ] #9 CloudWatch metrics `apify_tiktok_api_calls{outcome}`, `apify_tiktok_credits_consumed`, and `tiktok_ip_block_detected_total` emitted, plus a >10%/5min failure-rate alarm provisioned
- [ ] #10 ADR `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md` reflects the new TikTok V1 strategy (yt-dlp primary + Apify on IP block + Deepgram on other failures), references `docs/research/task-140-tiktok-extraction/README.md` and forward-references task-145 (V2 residential-proxy migration)
<!-- AC:END -->
