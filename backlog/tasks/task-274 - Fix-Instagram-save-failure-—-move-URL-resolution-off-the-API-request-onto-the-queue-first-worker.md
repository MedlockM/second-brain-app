---
id: task-274
title: >-
  Fix Instagram save failure — move URL resolution off the API request onto the
  queue-first worker
status: Done
assignee: []
created_date: '2026-08-17 20:49'
updated_date: '2026-08-17 22:44'
labels:
  - bug
  - ingestion
  - backend
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem

Every Instagram save from the mobile app fails with `Save failed`. Observed on dev on 2026-08-17, 6 attempts out of 6, on several different reels — the reel's size and duration are irrelevant.

The mobile app receives an HTTP 503 from API Gateway (`INTEGRATION_TIMEOUT`, `integrationLatency 30000`) because `POST /api/media/ingest-url` resolves Instagram content **synchronously inside the HTTP request**, and that resolution cannot finish inside the API's time budget. Nothing is persisted: `ProcessingJobSubmissionOrchestrator.submit()` runs only after the resolver returns, so the request dies before a job is ever created — there is not even a `media.ingest.failed` event.

## Two failures in series

**1. Immediate trigger, new on 2026-08-17 — the free primary path went down.** The resolver first tries yt-dlp, which Instagram now refuses from the Lambda IP (`Requested content is not available, rate-limit reached or login required`). Event `instagram.reel.ytdlp_ip_blocked` fired on 6/6 attempts, after ~2.5 s each time. This is the same class of problem as task-145 (TikTok IP-block fallback).

Instagram saves worked on 12 Aug (`media.ingest.created` at 14:54:19 and 14:58:37, ~2 s end to end) precisely because yt-dlp still succeeded then and the Apify fallback was never exercised. That is why the regression looks sudden while no code changed.

**2. Structural cause, latent since June — the fallback cannot fit in the API budget.** Apify runs are confirmed to start ~1 s after each `ytdlp_ip_blocked` log and to **succeed**, but they take 63-100 s (six runs measured on the Apify account on 2026-08-17). The API Lambda times out at 30 s (`lambda_api.tf:91`) and API Gateway HTTP API caps integration at 30 s, which is not configurable. The scraped result therefore always lands 30-70 s after the request is already dead: the run is billed and the payload discarded. The same actor took 6-9 s on 10 June, which is why this fallback was viable when written and is not anymore.

Raising any timeout cannot fix this. Asynchronous resolution is the only viable shape.

## The async path already exists and has never run

`media_summarizer/workers/instagram_ingestion_worker.py` is written for exactly this ("Queue-first Instagram ingestion worker"), the queue and Lambda are provisioned (`sqs.tf:130`, `lambda_workers.tf:38`, `runtime_env.tf:66`), but:

- no producer anywhere sends to `INSTAGRAM_INGESTION_QUEUE` — the only repo hits are the Terraform definition and the consumer itself;
- the log group `/aws/lambda/media-summarizer-worker-instagram_ingestion-dev` has **no log stream at all**: the worker has never been invoked once.

The API took the worker's place by resolving inline and then enqueuing straight to Deepgram (`orchestrators.py` `SOCIAL_VIDEO` + `audio_url` branch).

## Scope

Route Instagram URL ingestion through the queue instead of resolving it in the request: the endpoint accepts, persists the job in its initial state, enqueues, and returns promptly. The worker performs the resolution and hands off to the existing Deepgram push path, preserving what the current inline branch already delivers — caption, comments, `deepgram_mode: "push"`, the quota metering category, and the task-266 title derivation.

Also fix the time budget, which is inconsistent by construction and would otherwise leave the fix broken: the resolver allows itself up to 40 polls x 3 s = 120 s of Apify polling inside a worker whose own timeout is 120 s, on top of up to 30 s of yt-dlp before it. Worst case ~150 s against a 120 s ceiling; the worst case actually measured (99 s + 2.5 s) leaves under 18 s of headroom before the job's final DynamoDB/SQS writes. The polling budget must be bounded by the worker's real remaining time rather than by a poll count that ignores it, and the worker's ceiling must leave room above the measured worst case. The queue's visibility timeout (720 s) and its DLQ with `maxReceiveCount: 3` are already provisioned and should be checked for consistency with whatever ceiling is chosen.

Instagram image posts keep failing with their existing `unsupported_content` reason — no OCR/vision pipeline exists and this task does not add one.

## Notes to the owner

- LAUNCH PREREQUISITE — the end-to-end confirmation needs the deploy: after this merges and `main` is pushed, save one Instagram reel from the app and confirm it appears in the Inbox and reaches a transcript, with a `media.ingest.created` event in the API log group and an invocation in the `instagram_ingestion` worker log group.
- The yt-dlp IP block may lift on its own, since the Lambda egress IP is shared and the limit is Instagram's. If Instagram saves start working again before this task ships, that is luck, not a fix: the fallback stays unreachable from the API and the next block reproduces the outage identically.
- Each failed save attempt currently bills a full Apify actor run whose result is thrown away (6 runs paid on 2026-08-17 for zero saved media). Landing this stops the waste.
- Whether to drop the Apify polling wait entirely — Apify supports run webhooks and `waitForFinish`, which would remove the timeout question rather than widen it — is deliberately out of scope here and belongs to a separate scoping task if the ceiling raised by this task proves insufficient.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 POST /api/media/ingest-url no longer invokes the Instagram resolver: the request path for an Instagram URL performs no Apify or yt-dlp call, and no call site in media_summarizer/api/ reaches InstagramApifyResolver.resolve directly or transitively
- [x] #2 An Instagram URL submitted to the ingestion endpoint results in a persisted processing job plus one message on instagram-ingestion-queue, and the endpoint's response no longer depends on the outcome of provider resolution
- [x] #3 The Instagram ingestion worker is the only place Instagram resolution runs, and it still hands off to the Deepgram push path carrying caption, comments, deepgram_mode push, the quota metering category and the task-266 derived title, matching what the inline branch produced
- [x] #4 The Apify polling budget is bounded by the worker invocation's actual remaining time, so the resolver cannot outlive the Lambda that runs it; no code path can still spend a fixed 120 s polling inside a 120 s worker
- [x] #5 The worker's configured timeout leaves headroom above the 100 s worst case measured on 2026-08-17, and the queue's visibility timeout and maxReceiveCount remain consistent with that timeout
- [x] #6 Instagram image posts still fail with their existing unsupported_content reason and no image post is enqueued to a queue that has no consumer
- [x] #7 A test message deposited on instagram-ingestion-queue-dev with the AWS CLI is picked up by the deployed worker, creating a log stream in /aws/lambda/media-summarizer-worker-instagram_ingestion-dev (note: this consumes one real Apify run)
- [x] #8 ruff and mypy are clean; if infrastructure/terraform is touched, terraform validate and terraform plan exit 0 for the dev env
- [x] #9 No dead code is left behind from the inline path: the superseded API-side Instagram resolution branch is deleted rather than flagged or kept behind a flag
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## What changed

**The API no longer resolves Instagram.** `adapters/resolvers.py::InstagramResolver` was a thin delegate to `InstagramApifyResolver`, dead in the registry (wiring registered the Apify resolver directly). It is now the deferred resolver, shaped exactly like `TikTokResolver`: it classifies, sets `resolution_mode=queued_worker`, and calls no provider. `wiring.py` registers it, which also removed the lazy import that existed only to break the circular dependency the infrastructure resolver introduced into the core.

**The orchestrator routes `instagram.default` to the queue** (`orchestrators.py`, next to the TikTok branch): `mark_extracting()` then one message on `INSTAGRAM_INGESTION_QUEUE`. Outcome status is `EXTRACTING`, same as TikTok, and the outcome metadata carries `instagram_ingestion_enqueued`.

**Two orchestrator branches were deleted, not flagged** — after this change nothing can reach them:
- `MediaType.IMAGE_POST`: only the Instagram post resolver ever produced that media type, and it no longer runs in the API. The handling moved into the worker, which fails the job with `unsupported_content` and the same user-facing reason ("Instagram image posts are not supported yet.").
- `SOCIAL_VIDEO and audio_url`: the only resolvers still producing an `audio_url` are `PodcastResolver` (family `PODCAST`) and `AudioResolver` (family `AUDIO`), so no social video can arrive with one. Verified by grepping every `audio_url=` construction in `adapters/resolvers.py`.

**The worker is now the only Instagram resolution site** and matches what the inline branch delivered: `deepgram_mode="push"` (was `pull_with_push_fallback`), plus `caption`, `comments`, `comments_count`, `resolver_key` and — the one the previous worker code silently dropped — `quota_source_platform="instagram"`. Without it the Deepgram worker settles the job in audio minutes on top of the category the API already debited (`deepgram_worker.py::_settle_audio_quota`). Those five fields were added to `utils/deepgram_dispatch.py::enqueue_deepgram_transcription`. The title is `job.title or message_body["episode_title"]`: the resolver's caption-derived title (task-266) is written to the job just above, and `update_processing_job` mirrors it onto the library row.

**The polling budget is now expressed in remaining time, not in poll counts.** New `utils/invocation_budget.py`: the Lambda handler publishes `context.get_remaining_time_in_millis()` once per record, and `_run_actor` in the Instagram resolver derives a monotonic deadline from it (minus `APIFY_POLL_RESERVE_SECONDS`, default 15, kept for the job's terminal write and the Deepgram send). Every Apify HTTP call is clamped to it and the poll loop stops before crossing it, emitting `instagram.apify.poll_budget_exhausted` and a retryable error so SQS redelivers instead of the Lambda being killed mid-poll. `APIFY_MAX_POLLS` survives only as the cap of last resort when no deadline is published (local polling loop, scripts). The budget module is generic and now feeds every worker handler, not just this one.

**Infrastructure**: worker timeout 120 s -> 300 s, queue visibility timeout 720 s -> 1800 s (6x, the ratio AWS documents for an SQS event source mapping — below it a message can be redelivered while the first invocation is still resolving, which on this queue means paying a second Apify run for the same reel). `maxReceiveCount` stays 3. IAM already granted `sqs:SendMessage` on this queue to both the API and worker roles, and `INSTAGRAM_INGESTION_QUEUE` was already in `local.lambda_environment`, so no policy or env change was needed.

**Docs**: `INGESTION_WORKERS_PROVIDERS.md` and `MEDIA_INGESTION_CORE_ARCHITECTURE.md` both described the API resolving inline, `pull_with_push_fallback`, an Apify Comment Scraper dropped by task-173, and image posts being dispatched to `instagram-image-queue` — a queue Terraform never created. All four corrected. The `SOCIAL_VIDEO` row was removed from the deepgram-mode table with its branch.

## How each criterion was checked

- **#1** — AST walk over `media_summarizer/`, BFS from every module under `media_summarizer/api/`: **0** import paths reach `infrastructure.resolvers.instagram_apify_resolver`, and its only importer in the whole package is `workers/instagram_ingestion_worker.py`.
- **#2** — the wiring is verified statically (single `instagram.default` branch, one `sqs.send_message`, response built from the outcome and never from a provider result). Observing the request/queue pair at runtime needs the deployed image, so that half belongs to the owner's post-deploy check below, not to this run.
- **#7** — done live, and it is the first time this worker has ever been invoked. The log group had **zero** streams; a probe message deposited with `aws sqs send-message` on `instagram-ingestion-queue-dev` was picked up ~20 s later and created stream `2026/08/17/[$LATEST]073f5522…`, which logs `transcription.failed / error_code=invalid_message`. The probe deliberately carried **no** `job_id`, so the worker returned at its first guard: no Apify run was spent, no DynamoDB write, no failure event published. Queue and DLQ both back to 0 messages. What this proves is what the AC asked — the event source mapping is `Enabled` and delivers, and the Lambda wakes up; it does not exercise the resolver.
- **#8** — `ruff check` clean, `mypy` clean on 166 files, `terraform validate` Success and `terraform plan` exit 0 on `envs/dev`, showing exactly the two intended in-place updates (worker `timeout 120 -> 300`, queue `visibility_timeout_seconds 720 -> 1800`). The plan's third item, a `revenucat.tier_unresolved` metric filter to add, is pre-existing drift unrelated to this task.

## Notes to the owner

- **LAUNCH PREREQUISITE, unchanged**: after this merges and `main` is pushed, save one Instagram reel from the app and confirm `media.ingest.created` in the API log group, an invocation in the `instagram_ingestion` worker log group, and a transcript. The Terraform values above only take effect on your next `apply` — dev still reports `VisibilityTimeout: 720` today.
- **A terminal failure now blocks the same reel for everyone.** This is a real consequence of the queue-first shape, worth knowing before the E2E run. Before, a resolution failure raised inside the request, so no job and no idempotence row were created and the user could just retry. Now the reservation is taken at submit time and no worker releases it — and `already_processed()` returns the row whatever its status, so `failed` short-circuits a resubmission exactly like `processed`. TikTok and YouTube have behaved this way since they went queue-first; task-279 and task-280 are the tasks that fix the class, so this was not papered over here with an Instagram-only release.
- **`caption`, `comments` and `comments_count` are carried because AC #3 asks for them, but nothing reads them.** Grep shows no consumer in the Deepgram worker or anywhere downstream; the Instagram resolver has not populated `comments` since task-173 dropped the Comment Scraper, so the value is always `[]`. They now travel identically to how the inline branch sent them. If you would rather drop the three fields, it is a two-line deletion in `deepgram_dispatch.py` and one call site.
- **One dead branch was left in place on purpose**: `orchestrators.py`'s `raw_text is not None and media_family == SOCIAL_VIDEO` (the Apify native-transcript bypass, task-112). No resolver produces `raw_text` with that family any more, so it is unreachable — but it was already unreachable before this task and belongs to a different feature, so deleting it here would have widened the diff beyond Instagram. Worth its own one-line cleanup task.
- **The E2E test budget moved**: `tests/e2e/test_fallback_chains.py::test_instagram_apify_fallback` went from 120 s to 300 s. The sentinel now travels through the queue to the worker, so the wait covers the queue hop plus a 63-100 s Apify run; 120 s would have failed on a correct pipeline.
- **`APIFY_POLL_RESERVE_SECONDS`** is a new optional env var (default 15). It needs no entry in the runtime secret; set it only if the terminal writes ever turn out to need more room.
<!-- SECTION:NOTES:END -->
