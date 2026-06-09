---
id: task-145
title: Switch TikTok IP-block fallback from Apify to residential proxy (V2)
status: To Do
assignee: []
created_date: '2026-06-09 17:48'
labels:
  - backend
  - ingestion
  - tiktok
dependencies:
  - task-144
priority: medium
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

`task-140` benchmarked TikTok extraction strategies. The owner picked **yt-dlp + Apify fallback for V1** (task-144) and explicitly deferred the **residential-proxy migration to V2**, to be tracked here. The benchmark's primary recommendation was yt-dlp + Webshare residential proxy — we go through Apify first to get coverage with zero new infra dependency, then revisit once we have hard data on fallback frequency, cost, and reliability.

This task is **not dispatchable**. It is a placeholder to capture the V2 decision and trigger the migration once the V1 has produced enough operational data.

## Trigger criteria (when to start)

Pick this up when **any** of the following holds:
- Apify fallback monthly cost exceeds the Webshare break-even point in the README §6 cost table.
- `apify_tiktok_api_calls{outcome=actor_failed|timeout}` rate > 5% over a 30-day window.
- TikTok deprecates or breaks the chosen Apify actor and a quick re-vendor is non-trivial.
- The fallback frequency (`tiktok_ip_block_detected_total`) trends materially upward, making per-call Apify cost dominant over a flat-rate proxy bandwidth subscription.

The dispatcher should leave this task untouched until the owner flips `dispatchable: true`.

## Scope (when activated)

### 1. Provider selection

Re-read `docs/research/task-140-tiktok-extraction/README.md` §3-§4 (proxy comparison) and `docs/research/task-140-tiktok-extraction/README.md` §6 (cost). Confirm Webshare is still the right vendor or revisit (Decodo, Bright Data) based on current pricing and TikTok detection state. If the conclusion changes materially, the owner should drive a new mini-benchmark or `owner_decision: more` on the existing README.

### 2. Configuration surface

Add to `.env.example` and `media_summarizer/core/config.py`:
- `TIKTOK_RESIDENTIAL_PROXY_URL` — full proxy URL with credentials (e.g. `http://user:pass@p.webshare.io:80`).
- `TIKTOK_RESIDENTIAL_PROXY_ENABLED` — boolean kill-switch.

Do not delete `APIFY_TIKTOK_*` yet — keep them in config until §4 is verified in production.

### 3. Worker change

In `media_summarizer/workers/tiktok_ingestion_worker.py`, replace the Apify branch added in task-144 with:
- On `_is_ip_blocked_error()`: retry yt-dlp with `proxy=settings.TIKTOK_RESIDENTIAL_PROXY_URL`. If success → upload + publish.
- On proxied yt-dlp failure: keep the existing Deepgram-URL fallback if any audio URL is now reachable through the proxy; otherwise fail gracefully with the matching `user_message` from README §6.
- Add `tiktok_proxy_used_total` and `tiktok_proxy_failure_total` CloudWatch metrics.

### 4. Apify removal

Once the proxy path is observed stable in production for ≥ 2 weeks:
- Delete `_fetch_apify_tiktok_transcript()` and `tiktok_ip_blocked_unrecoverable`-via-Apify branch.
- Remove `APIFY_TIKTOK_API_TOKEN` and `APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID` from `.env.example` and `core/config.py`.
- Decommission the Apify actor secret in AWS dev/prod.
- Remove `apify_tiktok_*` CloudWatch metrics and the alarm.

### 5. ADR update

Update `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`:
- Mark the V1 TikTok section (Apify fallback) as superseded.
- Add a "TikTok extraction (V2, post-task-145)" section: yt-dlp primary, residential proxy on IP block, Deepgram-URL on other failures.

## References

- V1: task-144.
- Benchmark: `docs/research/task-140-tiktok-extraction/README.md` (proxy section §3-§4, cost §6).
- Worker: `media_summarizer/workers/tiktok_ingestion_worker.py`.
- ADR: `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Trigger criterion observed and documented in the task notes before flipping `dispatchable: true`
- [ ] #2 `TIKTOK_RESIDENTIAL_PROXY_URL` and `TIKTOK_RESIDENTIAL_PROXY_ENABLED` exposed in `.env.example` and `media_summarizer/core/config.py`
- [ ] #3 TikTok worker IP-block branch routes through the residential proxy instead of Apify, with `tiktok_proxy_used_total` / `tiktok_proxy_failure_total` CloudWatch metrics emitted
- [ ] #4 After ≥ 2 weeks of stable production observation, Apify TikTok integration removed: `_fetch_apify_tiktok_transcript()`, `APIFY_TIKTOK_*` config keys, and `apify_tiktok_*` metrics + alarm all deleted
- [ ] #5 ADR `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md` reflects the V2 strategy (proxy fallback) and marks V1 as superseded
<!-- AC:END -->
