---
id: task-140
title: Benchmark TikTok extraction strategies given Lambda IP blocking by TikTok on some videos
status: Done
assignee: []
created_date: '2026-06-09 17:50'
labels:
  - benchmark
  - backend
  - ingestion
dependencies: []
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

While completing Phase 4 E2E validation, we discovered that **TikTok's anti-bot rejects yt-dlp requests from AWS Lambda IPs on some videos**, with the explicit error:

```
ExtractorError: [TikTok] <video_id>: Your IP address is blocked from accessing this post
```

The block is **not systematic**. An earlier test on `@scout2015/video/6718335390845095173` (a viral cat video from 2019) succeeded — yt-dlp extracted metadata fine. A later test on `@bbc/video/7335731145619360992` (an official BBC News post from 2024) was rejected. The pattern suggests TikTok applies stricter anti-bot heuristics to some videos (probably accounts/posts flagged as high-value content) while leaving others accessible.

This is **the same class of problem as YouTube** (task-126) but with a different shape:
- YouTube: blocks Lambda *systematically* on every video → forced migration to Apify (task-129)
- TikTok: blocks Lambda *sometimes*, depending on the video → unclear whether to migrate to Apify, add a proxy, or accept partial coverage

## Symptom

Reproducible on certain TikTok URLs from a Lambda execution context:

```
ExtractorError: [TikTok] 7335731145619360992: Your IP address is blocked from accessing this post
DownloadError: ERROR: [TikTok] 7335731145619360992: Your IP address is blocked from accessing this post
```

The TikTok ingestion worker catches this and surfaces it as `TikTokIngestionError("DownloadError")`. Job lands in `failed` after the worker retries exhaust.

## What this benchmark must cover

1. **Confirm the scope of the block**:
   - Test 10–20 different TikTok URLs from a Lambda environment in this AWS account/region
   - Categorize: official media accounts, viral content, educational, music, individual creators
   - Quantify: what % of URLs are blocked? Random or predictable? Correlated with account verification, view count, content type, post date?
2. **Inventory candidate strategies** (open-ended — find what's available in 2026):
   - Residential proxies for yt-dlp (Webshare, Decodo, Bright Data, etc.) — same vendors evaluated in task-126
   - Apify TikTok scrapers (do they work where yt-dlp doesn't?)
   - Third-party TikTok scraping APIs (RapidAPI marketplace, ScrapeNinja, etc.)
   - Headless browser approach (Playwright on Lambda — heavy)
   - Client-side delegation: mobile app fetches metadata, sends to backend
   - Hybrid: try yt-dlp first, fall back to Apify or proxy when blocked
3. **For each candidate, evaluate**:
   - Reliability: success rate on the test URL set
   - Coverage: which kinds of videos work?
   - Latency added per request
   - Cost model: per-request, monthly subscription, free tier
   - Operational complexity
   - Legal/ToS exposure
   - Fit with existing pipeline (`media_summarizer/workers/tiktok_ingestion_worker.py`)
4. **Provide a recommendation** with explicit owner trade-offs.
5. **Sketch the migration plan**: code changes, infra, secrets, testing, rollback.

## Constraints

- Must work from AWS Lambda in `eu-west-3`
- Must handle V1 scale (a few hundred TikTok URLs/day initially)
- No user authentication with TikTok (no OAuth)
- Respect TikTok's ToS to a level the owner is comfortable with
- Output must be transcript text usable by downstream artifact workers

## Note on the Deepgram fallback (task-139)

Even if yt-dlp from Lambda succeeds, the Deepgram fallback path may fail because Deepgram's IPs are blocked by TikTok's CDN when Deepgram tries to fetch the media URL. task-139 addresses this orthogonal layer (Lambda-side download + push-mode upload to Deepgram). That fix and the present task are complementary, not alternatives.

## Out of scope

- Implementation of the chosen strategy (separate task gated on owner decision)
- Re-architecting the broader ingestion pipeline
- Other sources (Instagram, X) — they have their own resolvers

## References

- task-126 (sibling: YouTube IP block benchmark)
- task-129 (sibling: YouTube migration to Apify)
- task-139 (sibling: Deepgram fallback CDN 403)
- `media_summarizer/workers/tiktok_ingestion_worker.py:761` (yt-dlp call site)
- `media_summarizer/workers/tiktok_ingestion_worker.py:419` (TikTokIngestionError raise on DownloadError)
- CloudWatch `/aws/lambda/media-summarizer-worker-tiktok_ingestion` 2026-06-09 ~15:50 UTC (failing case)
- CloudWatch (earlier successful case) `/aws/lambda/media-summarizer-worker-tiktok_ingestion` 2026-06-09 ~14:39 UTC for `@scout2015/video/6718335390845095173`
- `tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Empirical confirmation of the block pattern on 10+ TikTok URLs from Lambda; result categorized
- [ ] #2 Candidate strategies enumerated comprehensively in `docs/research/task-140-tiktok-extraction/README.md`
- [ ] #3 Each candidate evaluated against reliability, coverage, latency, cost, operational complexity, legal/ToS posture, and fit
- [ ] #4 Recommendation made with explicit reasoning and owner trade-offs surfaced
- [ ] #5 README front-matter contains `owner_decision: pending` and standard `Owner Validation` block
- [ ] #6 Sketch of migration plan for the recommended strategy
- [ ] #7 README explicitly addresses what happens for TikTok URLs no strategy can handle (graceful failure UX, error messaging, retry semantics)
<!-- AC:END -->

## Implementation Notes

**2026-06-09 — Research agent (initial mode)**

Produced `docs/research/task-140-tiktok-extraction/README.md` containing:

- Front-matter with `owner_decision: pending`
- Analysis of TikTok's multi-layer anti-bot architecture (IP reputation, TLS fingerprinting, JS challenges, device fingerprinting)
- 8 candidate strategies evaluated: (A) Residential proxy for yt-dlp, (B) Apify TikTok scraper, (C) curl_cffi browser impersonation, (D) Bright Data Web Unlocker, (E) TikTok Research API, (F) Headless browser, (G) Client-side delegation, (H) Accept partial coverage
- Each strategy evaluated against: reliability, coverage, latency, cost, operational complexity, legal/ToS, pipeline fit
- Comparative matrix across all criteria
- Recommendation: Hybrid yt-dlp with Webshare residential proxy fallback (try direct first, retry with proxy on IP block)
- Detailed migration plan sketch (5 phases: curl_cffi install, proxy fallback code, infra/secrets, testing, monitoring)
- Graceful failure UX: error classification table, retry semantics, user messaging strategy
- 17 cited sources with URLs

**Recommendation awaits owner validation.**
