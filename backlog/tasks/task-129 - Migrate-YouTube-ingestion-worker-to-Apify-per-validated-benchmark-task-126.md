---
id: task-129
title: Migrate YouTube ingestion worker to Apify per validated benchmark (task-126)
status: Done
assignee: []
created_date: '2026-06-09 10:36'
labels:
  - backend
  - ingestion
  - youtube
dependencies:
  - task-126
  - task-127
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

The current YouTube worker (`media_summarizer/workers/youtube_ingestion_worker.py`) uses `youtube-transcript-api` for native captions and `yt-dlp` + Deepgram as audio fallback. Both are systematically blocked from AWS Lambda (`eu-west-3`) because YouTube blacklists cloud-provider IP ranges (Phase 4 e2e confirmed `RequestBlocked`/`IpBlocked` on every URL).

`task-126` benchmarked 10 strategies. The owner's final decision (recorded in `docs/research/task-126-youtube-extraction/README.md` Owner Validation block) is **Apify** rather than the benchmark's primary recommendation (Supadata) — motivated by infra consolidation (Apify is already adopted for Instagram via task-108) and isolation of quotas/billing across two distinct Apify accounts.

This task implements that decision.

## Pre-requisites

1. Read `docs/research/task-126-youtube-extraction/README.md` end to end. The owner's `Decision` field documents which Apify YouTube actor was chosen and the response shape.
2. task-127 merged → `media_summarizer/core/config.py` exposes `APIFY_YOUTUBE_API_TOKEN` and `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID`.
3. Runtime secret payload on AWS dev populated with both `APIFY_YOUTUBE_*` values.

## Scope

### 1. New transcript fetcher

Add `_fetch_apify_transcript(video_id, source_url)` in `youtube_ingestion_worker.py` (or under `media_summarizer/infrastructure/apify/` if helpers are shared — see "Reuse" below).

- Read `APIFY_YOUTUBE_API_TOKEN`, `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID` from `settings` at call time (no module-level reads).
- Replicate the Apify HTTP pattern from `InstagramApifyResolver._run_actor()` (`media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py:693-792`): `POST /v2/acts/{actor_id}/runs` → poll `GET /v2/actor-runs/{runId}` → `GET /v2/datasets/{datasetId}/items`.
- Honor `APIFY_TIMEOUT_SECONDS`, `APIFY_POLL_INTERVAL_SECONDS`, `APIFY_MAX_POLLS`.
- Normalize to the existing dict contract used downstream: `{text, language, language_code, segments_count, source_detail, source_url, fetched_at}` (cf. `_normalize_native_transcript()` lines 159-195). Fuse timed segments into text when present; set `segments_count: 0` and `source_detail: "apify_youtube"` for flat text.

### 2. Orchestration refactor

Refactor `process_youtube_message()` (lines 592-689):
- Step 1: call `_fetch_apify_transcript()` (replacing `_fetch_native_transcript()`).
- Step 2: on Apify failure, fall back to Deepgram **only** if the Apify actor exposes a usable audio URL (the owner's `Decision` field documents whether/how). Skip the broken `yt-dlp` step. If no audio URL is available, mark the job failed with the matching `user_message` from the failure table in §6 of the README.
- Step 3: keep S3 upload + completion-event publication unchanged.

### 3. Dead code removal

- Delete `_fetch_native_transcript()`, `_select_transcript()` and the `youtube_transcript_api` imports (lines ~23-35, ~217-292). Keep `_normalize_native_transcript()` only if still useful as a normalization helper for the Apify response.
- Inspect `_resolve_audio_fallback()` (lines ~300-442). If the Apify actor is now the sole audio-URL source, delete the `yt-dlp` extraction code; keep only the Deepgram-enqueue plumbing. Remove the `import yt_dlp` if unused.
- Remove `youtube-transcript-api` from `pyproject.toml`. Remove `yt-dlp` only if `grep -r "yt_dlp\|yt-dlp" media_summarizer/ tests/` returns no remaining usage. Run `uv lock`.

### 4. Error code mapping

Update `YouTubeIngestionError` hierarchy (lines 84-103):
- Add `apify_actor_failed` (non-retryable on auth/config errors).
- Add `apify_quota_exceeded` (retryable, SQS visibility timeout backoff).
- Add `apify_timeout` (retryable up to `YOUTUBE_WORKER_MAX_RETRIES`).
- Map: 401/403 → `apify_actor_failed`; 429 → `apify_quota_exceeded`; 5xx + network → `apify_timeout`.
- Keep `youtube_unavailable`, `youtube_geo_restricted`, `youtube_age_restricted` for actor-emitted signals.

### 5. Tests

- `tests/e2e/test_phase4_other_sources.py:44-57`: remove the `xfail` marker on `test_youtube_ingestion`.
- Add unit tests for `_fetch_apify_transcript()` mirroring the style of `media_summarizer/tests/test_instagram_apify_resolver.py`: success with timed segments, success with flat text, 401/429/5xx mapping, actor-failed run status, video-unavailable payload.

### 6. Observability

In `infrastructure/observability/`:
- CloudWatch metric `apify_youtube_api_calls{outcome}` with `outcome ∈ {success, actor_failed, quota_exceeded, timeout, unavailable}`.
- CloudWatch metric `apify_youtube_credits_consumed` (1 per call default; actual cost from actor payload when present).
- Alarm: failure rate > 10% over 5 minutes → warn channel.

### 7. ADR update

Update `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`:
- Mark the previous YouTube section (native `youtube-transcript-api` → `yt-dlp` audio → Deepgram) as superseded.
- Add a "YouTube extraction (V1, post-task-126)" section: Apify primary, Deepgram fallback only when the actor exposes an audio URL. Reference the owner's decision in `docs/research/task-126-youtube-extraction/README.md`.

## Reuse vs duplication

`InstagramApifyResolver._run_actor()` already implements the Apify HTTP plumbing. Two acceptable approaches:
- **Inline**: copy the `_run_actor` shape into a `_run_apify_actor()` helper at the top of `youtube_ingestion_worker.py` parameterized by token, actor_id, input.
- **Shared**: extract into `media_summarizer/infrastructure/apify/_run_actor.py` and have both resolvers consume it.

KISS prevails; pick whichever is simpler at implementation time.

## Constraints

- Pre-production, **no backwards compatibility**: hard delete the `youtube-transcript-api` paths, no feature flag.
- **No hardcoded actor ID** — everything reads from `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID`. The owner's `Decision` field is the single source of truth for which actor.
- Output contract unchanged — artifact workers (summarization, notes, flashcards, quiz) consume transcripts via S3 only and must keep working without code changes.

## Verification

1. `pytest media_summarizer/tests/ -v` passes.
2. `uv lock --check` clean.
3. AWS dev e2e: submit 5 YouTube URLs (EN-with-captions, non-EN-with-captions, no-captions, >30min, age-restricted). Verify CloudWatch logs (no `IpBlocked`/`RequestBlocked`), DynamoDB `completed`, S3 transcript object.
4. `pytest tests/e2e/test_phase4_other_sources.py::test_youtube_ingestion -v` passes (no longer xfailed).
5. `grep -rn "youtube_transcript_api\|youtube-transcript-api" media_summarizer/ tests/ pyproject.toml` empty. `grep -rn "yt_dlp\|yt-dlp" media_summarizer/ tests/ pyproject.toml` empty (or only justified entries with a comment).
6. CloudWatch metrics ticking; alarm provisioned.

## References

- Worker: `media_summarizer/workers/youtube_ingestion_worker.py` — native fetch (to delete) lines 217-292; normalization 159-195; audio fallback (to refactor) 300-442; orchestrator 592-689; errors 84-103.
- Apify HTTP reference: `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py:693-792`.
- Config (post-task-127): `APIFY_YOUTUBE_API_TOKEN`, `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID`, `APIFY_TIMEOUT_SECONDS`, `APIFY_POLL_INTERVAL_SECONDS`, `APIFY_MAX_POLLS`.
- E2E xfail: `tests/e2e/test_phase4_other_sources.py:44-57`.
- Infra: `infrastructure/terraform/lambda_workers.tf` (worker `youtube_ingestion`), `infrastructure/terraform/sqs.tf` (`aws_sqs_queue.youtube_ingestion`).
- ADR: `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`.
- Owner's decision + chosen actor: `docs/research/task-126-youtube-extraction/README.md` (Owner Validation block).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `youtube-transcript-api` is fully removed from the repo (no imports, no `pyproject.toml` entry); `yt-dlp` is also removed if no longer used
- [ ] #2 `_fetch_apify_transcript()` exists and returns the contract `{text, language, language_code, segments_count, source_detail, source_url, fetched_at}` consumed by the existing S3-upload + completion-event flow
- [ ] #3 `process_youtube_message()` orchestrates Apify-first → Deepgram fallback only when the actor exposes an audio URL → graceful failure with the right `user_message` otherwise
- [ ] #4 `YouTubeIngestionError` hierarchy gained `apify_actor_failed`, `apify_quota_exceeded`, `apify_timeout` with correct retryable flags; existing codes preserved
- [ ] #5 Unit tests for `_fetch_apify_transcript()` cover success (timed segments, flat text), 401/429/5xx error mapping, actor-failed run status, and video-unavailable payload
- [ ] #6 `tests/e2e/test_phase4_other_sources.py::test_youtube_ingestion` no longer carries the `xfail` marker and passes against AWS dev
- [ ] #7 5 representative YouTube URLs (EN-with-captions, non-EN-with-captions, no-captions, >30min, age-restricted) ingest successfully on AWS dev `eu-west-3`, verified through CloudWatch logs + DynamoDB job status + S3 transcript object
- [ ] #8 CloudWatch metrics `apify_youtube_api_calls{outcome}` and `apify_youtube_credits_consumed` emitted, plus a >10%/5min failure-rate alarm provisioned
- [ ] #9 ADR `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md` reflects the new Apify-primary strategy and references the owner's decision in `docs/research/task-126-youtube-extraction/README.md`
<!-- AC:END -->
