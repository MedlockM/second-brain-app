---
id: task-274
title: >-
  Fix Instagram save failure — move URL resolution off the API request onto the
  queue-first worker
status: To Do
assignee: []
created_date: '2026-08-17 20:49'
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
- [ ] #1 POST /api/media/ingest-url no longer invokes the Instagram resolver: the request path for an Instagram URL performs no Apify or yt-dlp call, and no call site in media_summarizer/api/ reaches InstagramApifyResolver.resolve directly or transitively
- [ ] #2 An Instagram URL submitted to the ingestion endpoint results in a persisted processing job plus one message on instagram-ingestion-queue, and the endpoint's response no longer depends on the outcome of provider resolution
- [ ] #3 The Instagram ingestion worker is the only place Instagram resolution runs, and it still hands off to the Deepgram push path carrying caption, comments, deepgram_mode push, the quota metering category and the task-266 derived title, matching what the inline branch produced
- [ ] #4 The Apify polling budget is bounded by the worker invocation's actual remaining time, so the resolver cannot outlive the Lambda that runs it; no code path can still spend a fixed 120 s polling inside a 120 s worker
- [ ] #5 The worker's configured timeout leaves headroom above the 100 s worst case measured on 2026-08-17, and the queue's visibility timeout and maxReceiveCount remain consistent with that timeout
- [ ] #6 Instagram image posts still fail with their existing unsupported_content reason and no image post is enqueued to a queue that has no consumer
- [ ] #7 A test message deposited on instagram-ingestion-queue-dev with the AWS CLI is picked up by the deployed worker, creating a log stream in /aws/lambda/media-summarizer-worker-instagram_ingestion-dev (note: this consumes one real Apify run)
- [ ] #8 ruff and mypy are clean; if infrastructure/terraform is touched, terraform validate and terraform plan exit 0 for the dev env
- [ ] #9 No dead code is left behind from the inline path: the superseded API-side Instagram resolution branch is deleted rather than flagged or kept behind a flag
<!-- AC:END -->
