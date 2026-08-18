---
id: task-145
title: >-
  Switch social-video IP-block fallback from Apify to residential proxy (V2) —
  TikTok and Instagram
status: To Do
assignee: []
created_date: '2026-06-09 17:48'
updated_date: '2026-08-17 21:04'
labels:
  - backend
  - ingestion
  - tiktok
  - instagram
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

## Instagram is affected by the same IP block (added 2026-08-17)

Instagram now exhibits the exact failure this task anticipates for TikTok, and its scope is extended to cover both platforms. Measured on dev on 2026-08-17:

- yt-dlp is refused from the Lambda IP on **6 attempts out of 6** (`Requested content is not available, rate-limit reached or login required`). On 12 August the same path carried 100% of the working Instagram saves at ~2 s end to end, so the block is recent.
- The Apify fallback therefore carries **every** Instagram save, at 63-100 s per run and one billed run each time. The same actor answered in 6-9 s on 10 June 2026.

The owner decided on 2026-08-17 to keep the residential proxy in V2 for Instagram as well, rather than pull it into V1. What ships in V1 instead is task-274 (resolution moved off the API request onto the queue-first worker, which stops the user-facing `Save failed`) and task-276 (the Apify fallback made non-blocking, per the task-275 benchmark).

Consequence for this task's V2 scope: the proxy work now covers **two** platforms, and the provider-selection step below must confirm whether a single vendor and a single configuration surface serve TikTok and Instagram together. If yes, this stays one task; if the two platforms need different vendors or different handling, split it at activation time.

Note the two layers do not substitute for each other. This task keeps the *free primary path* working, which reduces how often the fallback is reached. It does not make the fallback able to complete — that is task-276. So landing the proxy is not a reason to remove or neglect the Apify fallback: yt-dlp still fails on private content, geo restrictions and format changes, and the fallback stays on the path for those.

## Trigger criteria (when to start)

Pick this up when **any** of the following holds:
- Apify fallback monthly cost exceeds the Webshare break-even point in the README §6 cost table.
- `apify_tiktok_api_calls{outcome=actor_failed|timeout}` rate > 5% over a 30-day window.
- TikTok or Instagram deprecates or breaks the chosen Apify actor and a quick re-vendor is non-trivial.
- The fallback frequency (`tiktok_ip_block_detected_total`, and its Instagram equivalent) trends materially upward, making per-call Apify cost dominant over a flat-rate proxy bandwidth subscription.

Note that the Instagram fallback frequency has *already* reached 100% as of 2026-08-17. That satisfies the last criterion for Instagram on its own; the owner has nonetheless chosen to hold this to V2, because task-274 and task-276 make the fallback path viable without it. Re-examine that call if the Apify cost becomes material or the block spreads.

The dispatcher should leave this task untouched until the owner flips `dispatchable: true`.

## Scope (when activated)

### 1. Provider selection

Re-read `docs/research/task-140-tiktok-extraction/README.md` §3-§4 (proxy comparison) and §6 (cost). Confirm Webshare is still the right vendor or revisit (Decodo, Bright Data) based on current pricing and detection state — and confirm the same vendor covers Instagram, which was not in the original benchmark's scope. If the conclusion changes materially, the owner should drive a new mini-benchmark or `owner_decision: more` on the existing README.

### 2. Configuration surface

Add to `.env.example` and `media_summarizer/core/config.py`:
- `TIKTOK_RESIDENTIAL_PROXY_URL` — full proxy URL with credentials (e.g. `http://user:pass@p.webshare.io:80`).
- `TIKTOK_RESIDENTIAL_PROXY_ENABLED` — boolean kill-switch.
- The Instagram equivalents, or a single shared pair if one vendor serves both — decide this in §1 rather than duplicating by reflex.

Credentials go in the runtime secret, never in a tracked file: a proxy URL carries `user:pass` inline, which makes it the kind of value the repo's secrets rule forbids writing down.

Do not delete `APIFY_TIKTOK_*` yet — keep them in config until §4 is verified in production.

### 3. Worker change

In `media_summarizer/workers/tiktok_ingestion_worker.py`, and in the Instagram resolution path, replace the Apify-on-IP-block branch with:
- On `_is_ip_blocked_error()` / `_InstagramYtdlpBlocked`: retry yt-dlp through the residential proxy. If success → upload + publish.
- On proxied yt-dlp failure: fall back to Apify as today, since a proxy failure is not a reason to lose the save.
- Add `tiktok_proxy_used_total` / `tiktok_proxy_failure_total` and the Instagram equivalents as CloudWatch metrics.

### 4. Apify removal — reassess before doing it

The original plan was to delete the Apify TikTok integration after ≥ 2 weeks of stable proxy operation. Reassess that at activation: the Instagram incident shows the proxy handles the *IP-block* failure mode only, while Apify covers failures a proxy cannot fix. Removing it would leave those cases with no path at all. Decide explicitly, and if Apify stays, drop this section rather than carrying a half-done removal.

If removal is still the call for TikTok specifically: delete `_fetch_apify_tiktok_transcript()` and the `tiktok_ip_blocked_unrecoverable`-via-Apify branch, remove `APIFY_TIKTOK_API_TOKEN` and `APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID` from `.env.example` and `core/config.py`, decommission the secret entries, and remove the `apify_tiktok_*` metrics and alarm.

### 5. ADR update

Update `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`:
- Mark the superseded sections as such for both platforms.
- Add a "social video extraction (V2, post-task-145)" section: yt-dlp primary, residential proxy on IP block, Apify or Deepgram-URL for the remaining failure modes.

## References

- V1: task-144.
- Benchmark: `docs/research/task-140-tiktok-extraction/README.md` (proxy section §3-§4, cost §6).
- Instagram incident, root cause and measurements: task-274. Non-blocking fallback: task-275 (benchmark), task-276 (implementation).
- Workers: `media_summarizer/workers/tiktok_ingestion_worker.py`, `media_summarizer/workers/instagram_ingestion_worker.py`, `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`.
- ADR: `docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md`.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Trigger criterion observed and documented in the task notes before flipping dispatchable: true
- [ ] #2 Provider selection confirms whether one vendor and one configuration surface serve both TikTok and Instagram, or records why the platforms need different handling
- [ ] #3 Residential proxy configuration is exposed in .env.example and media_summarizer/core/config.py, with credentials held in the runtime secret and no proxy URL containing user:pass written into any tracked file
- [ ] #4 The IP-block branch of both the TikTok worker and the Instagram resolution path retries yt-dlp through the residential proxy, with per-platform proxy_used / proxy_failure CloudWatch metrics emitted
- [ ] #5 A proxy failure still falls through to the existing Apify path rather than losing the save

- [ ] #6 The decision on removing the Apify TikTok integration is made explicitly at activation and recorded: either removed in full (code, config keys, secret entries, metrics and alarm) or deliberately kept, with the failure modes a proxy cannot cover as the stated reason
- [ ] #7 docs/ADR/social-video-and-youtube-ingestion-fallback-strategy.md reflects the V2 strategy for both platforms and marks the superseded sections as such
<!-- AC:END -->
