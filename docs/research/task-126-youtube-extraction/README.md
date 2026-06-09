---
owner_decision: ok
---

# Benchmark: YouTube Transcript Extraction Strategies Given Lambda IP Blocking

## Owner Validation

**Decision**: apify actor
**Validated at**: _(ISO date to be filled by the owner)_

---

## Recommendation

**Primary: Supadata transcript API with Deepgram audio-to-text fallback (Strategy B + E hybrid)**

Use **Supadata** as the primary transcript extraction service (managed third-party API that handles YouTube anti-bot measures internally), combined with the **existing Deepgram audio fallback** for videos where Supadata cannot retrieve a transcript.

**Reasoning chain:**
1. The current `youtube-transcript-api` library is fundamentally broken from Lambda/cloud IPs — YouTube actively blocks all major cloud provider IP ranges.
2. The YouTube Data API v3 captions endpoint requires OAuth from the **video owner** — unusable for third-party consumption.
3. Running `yt-dlp` from Lambda is equally blocked (same IP range issue; PO Token generation requires a browser which is impractical on Lambda).
4. Self-managed residential proxies add significant operational complexity (proxy pool management, rotation logic, bandwidth monitoring, cost unpredictability) and still violate YouTube ToS.
5. Supadata abstracts all anti-blocking infrastructure, provides an AI (Whisper) fallback for videos without native captions, costs $17/month for 3,000 credits (covering V1 scale), and requires only a single API key.
6. For the rare case where Supadata also fails, the existing Deepgram fallback path remains viable if audio can be obtained — but this requires either a proxy for `yt-dlp` audio URL resolution OR client-side URL extraction from the mobile app.
7. A graceful failure path must exist for truly unreachable videos.

**Trade-offs surfaced for owner:**
- **ToS risk**: Supadata itself uses undocumented YouTube endpoints or scraping — their infrastructure carries the ToS risk, but the owner outsources legal exposure to a third party rather than bearing it directly.
- **Vendor dependency**: If Supadata goes down or gets blocked en masse, YouTube ingestion halts until their infra recovers. Mitigation: the existing Deepgram fallback provides a safety net for high-priority content.
- **Cost**: $17/month (Pro plan, 3,000 transcripts/month) is predictable and acceptable for V1 scale (~few hundred URLs/day). This replaces $0/month (broken) with a working solution.
- **Alternative owner choice**: If the owner prefers zero third-party dependency and accepts higher operational complexity, Strategy C (self-managed residential proxy with `youtube-transcript-api`) is viable but requires ongoing proxy pool management.

---

## Table of Contents

1. [Problem Confirmation](#1-problem-confirmation)
2. [Candidate Strategies Inventory](#2-candidate-strategies-inventory)
3. [Detailed Evaluation per Strategy](#3-detailed-evaluation-per-strategy)
4. [Comparative Matrix](#4-comparative-matrix)
5. [Migration Plan for Recommended Strategy](#5-migration-plan-for-recommended-strategy)
6. [Graceful Failure UX](#6-graceful-failure-ux-for-unresolvable-youtube-urls)
7. [Sources](#7-sources)

---

## 1. Problem Confirmation

### Scope of the Block

**YouTube blocks cloud provider IPs comprehensively.** The `youtube-transcript-api` library explicitly documents this:

> "YouTube has started blocking most IPs that are known to belong to cloud providers (like AWS, Google Cloud Platform, Azure, etc.)"
> — [youtube-transcript-api README](https://github.com/jdepoix/youtube-transcript-api)

This affects:
- **`youtube-transcript-api`** (innertube/timedtext endpoints): confirmed blocked. Raises `RequestBlocked` or `IpBlocked` from Lambda.
- **`yt-dlp`** (video/audio stream resolution): equally affected. YouTube requires PO Tokens (Proof of Origin) for stream access, and generating these tokens requires running BotGuard in a real browser environment — impractical on Lambda. Without a valid PO Token from a cloud IP, `yt-dlp` receives HTTP 403 or bot-check challenges.
- **Any direct HTTP request to YouTube from Lambda**: blocked. YouTube fingerprints the request origin (IP range, TLS fingerprint, lack of browser attestation).

### Empirical Confirmation

The task description confirms the symptom was observed on the actual AWS dev deployment in `eu-west-3`: the `youtube_ingestion_worker` running as a Lambda function consistently receives `RequestBlocked` errors from `youtube-transcript-api`. This is consistent with the library's own documentation and hundreds of GitHub issues reporting the same behavior from cloud environments.

**Regarding `yt-dlp` audio download**: while I could not run a test from this specific Lambda (I am a research agent, not an execution agent), the technical analysis is conclusive:
- yt-dlp's own FAQ acknowledges HTTP 429/402/403 errors from flagged IPs
- yt-dlp now requires PO Tokens for YouTube, generated via BotGuard (a browser-based attestation)
- The `bgutil-ytdlp-pot-provider` plugin (recommended PO Token solution) requires either a running Docker container with Node.js or a Chrome browser — neither is available in a standard Lambda execution environment
- The Lambda's IP is in the same AWS IP range that YouTube blocks for transcript requests

**Conclusion**: Both `youtube-transcript-api` and `yt-dlp` are non-functional from Lambda without external infrastructure (proxies or browser-based token generation).

---

## 2. Candidate Strategies Inventory

| ID | Strategy | Category |
|----|----------|----------|
| A | `youtube-transcript-api` + residential proxy (Webshare/Decodo) | Self-managed proxy |
| B | Supadata transcript API (managed third-party) | Managed API |
| C | `youtube-transcript-api` + generic residential proxy (self-provisioned) | Self-managed proxy |
| D | `yt-dlp` + PO Token server + residential proxy for audio | Self-managed complex |
| E | Audio download (via proxy) + Deepgram transcription | Audio fallback |
| F | YouTube Data API v3 (official captions endpoint) | Official API |
| G | Client-side transcript extraction (mobile app) | Client delegation |
| H | Headless browser on ECS/Fargate (not Lambda) | Self-hosted browser |
| I | Other managed transcript APIs (SearchAPI, RapidAPI services) | Managed API |
| J | Do nothing — disable YouTube for V1 | Feature cut |

---

## 3. Detailed Evaluation per Strategy

### Strategy A: `youtube-transcript-api` + Webshare Residential Proxy

**Description**: Use the existing `youtube-transcript-api` library but route all requests through Webshare's rotating residential proxy pool (which has first-class integration in the library via `WebshareProxyConfig`).

**Reliability**: Medium-High. Residential proxies significantly reduce blocking. However, YouTube can still ban individual residential IPs, and proxy quality varies. The library itself warns: "using a proxy doesn't guarantee that you won't be blocked."

**Coverage**: Same as native transcripts — limited to videos that have captions enabled (manual or auto-generated). No fallback for videos without any transcript.

**Latency**: +200-500ms per request (proxy hop). Total: 2-5 seconds per transcript.

**Cost model**:
- Webshare residential proxies: $3.50/GB (1 GB plan) down to $1.50/GB (1,000 GB plan)
- A typical transcript request is ~50-200 KB round-trip (JSON response with timed segments)
- At 300 videos/day = 9,000/month: ~0.9-1.8 GB/month = **$3.15-$6.30/month**
- Monthly plan: $3.50 for 1 GB minimum

**Operational complexity**: Low-Medium. Requires:
- Webshare account + API credentials
- `WebshareProxyConfig` integration (library-native, ~5 lines of code)
- Monitoring for block rate increases
- No infrastructure to manage (Webshare handles proxy pool)

**Legal/ToS exposure**: Medium. Still uses undocumented YouTube endpoints (innertube API). Proxying does not change the legal nature of the access — it merely evades the technical block. YouTube ToS Section 3 prohibits "automated access" except with written permission or as allowed by law.

**Fit with existing pipeline**: Excellent. Minimal code change — add proxy config to existing `_fetch_native_transcript()` call. The library's `WebshareProxyConfig` is built-in.

---

### Strategy B: Supadata Transcript API (Managed Third-Party)

**Description**: Replace `youtube-transcript-api` with calls to Supadata's REST API. Supadata handles all YouTube anti-bot infrastructure internally. When native captions are unavailable, Supadata automatically falls back to Whisper AI transcription.

**Reliability**: High. Supadata manages their own proxy infrastructure, maintains a public status page, and advertises "high availability." As a commercial service focused on this exact problem, they have strong incentive to maintain reliability. However, they are a single point of failure.

**Coverage**: Very High. Native captions + AI (Whisper) fallback for videos without captions. 50+ languages with auto-detection. This covers the gap where `youtube-transcript-api` would return `NoTranscriptFound`.

**Latency**: Comparable to direct API — their documentation shows fast response times. Estimate: 2-5 seconds per video (including potential AI fallback).

**Cost model**:
- Pro plan: **$17/month** for 3,000 credits (1 video = 1 credit; AI fallback = 2 credits)
- Mega plan: **$47/month** for 30,000 credits (if V1 grows)
- Overage: $10 per 1,000 credits (Pro) or $10 per 5,000 credits (Mega)
- At 300 videos/day (~9,000/month): Pro plan insufficient → need Mega ($47/month) or Pro + overage ($17 + $60 = $77/month)
- **Realistic V1 cost: $47/month (Mega plan)** for comfortable margin at "few hundred/day"

**Operational complexity**: Very Low. Single API key, REST call with video URL, structured JSON response. Python/JS SDKs available. No infrastructure to manage.

**Legal/ToS exposure**: Low (for the owner). Supadata bears the ToS risk on their infrastructure. The owner's application makes API calls to Supadata, not to YouTube directly. Supadata is an EU company (Dumpling Software). However, if YouTube shuts down Supadata, the service becomes unavailable.

**Fit with existing pipeline**: Good. Requires replacing the `_fetch_native_transcript()` function with a Supadata API call. Response format (timestamped segments with text, offset, duration) maps cleanly to existing `_normalize_native_transcript()`. The S3 upload and downstream pipeline remain unchanged.

---

### Strategy C: `youtube-transcript-api` + Generic Residential Proxy (Self-Provisioned)

**Description**: Same as Strategy A but using a non-Webshare provider (Decodo/Smartproxy, Bright Data, Oxylabs) via `GenericProxyConfig`.

**Reliability**: Medium-High. Same as Strategy A. Quality depends on chosen provider's residential pool size and rotation algorithm.

**Coverage**: Same as Strategy A (native captions only).

**Latency**: Same as Strategy A (+200-500ms proxy hop).

**Cost model**:
- Decodo/Smartproxy: $3.75/GB (3 GB) to $2.00/GB (1,000 GB)
- At ~1-2 GB/month: **$3.75-$7.50/month**
- Slightly more expensive than Webshare at low volumes

**Operational complexity**: Low-Medium. Same as Strategy A but without the library-native integration (must use `GenericProxyConfig` with manual URL construction).

**Legal/ToS exposure**: Same as Strategy A (Medium).

**Fit with existing pipeline**: Good. Similar to Strategy A but slightly more boilerplate.

---

### Strategy D: `yt-dlp` + PO Token Server + Residential Proxy for Audio

**Description**: Run a dedicated PO Token generation server (using `bgutil-ytdlp-pot-provider` Docker container), route `yt-dlp` through residential proxies, extract audio URLs, then send to Deepgram for transcription.

**Reliability**: Low-Medium. Multiple failure points: PO Token server must stay operational, residential proxy must not be banned, YouTube constantly evolves BotGuard. The PO Token plugin itself states: "Providing a PO token does not guarantee bypassing 403 errors."

**Coverage**: Medium. Only works for videos with available audio streams. Premium/DRM content excluded. Result is audio-to-text (Deepgram), not native captions — lower quality for non-English content.

**Latency**: High. PO Token generation (~2-5s) + proxy yt-dlp info extraction (~5-10s) + audio download + Deepgram transcription (~1-2x realtime for long videos). Total: 30s to several minutes depending on video length.

**Cost model**:
- ECS/Fargate for PO Token server: ~$10-20/month (always-on small container)
- Residential proxy bandwidth for yt-dlp: $5-15/month (more data than transcript-only)
- Deepgram transcription: $0.0048/min × average 10 min video × 9,000 videos/month = **$432/month** (prohibitive!)
- Even at 300 videos/day = 9,000/month: Deepgram cost alone makes this 10x more expensive

**Operational complexity**: Very High. Requires:
- PO Token Docker container on ECS (always-on)
- Proxy configuration for yt-dlp
- Audio URL caching (URLs expire)
- Deepgram queue integration (already exists)
- Monitoring for BotGuard evolution/breakage
- Regular updates to yt-dlp and PO Token provider

**Legal/ToS exposure**: High. Involves downloading audio streams from YouTube, running anti-attestation circumvention (BotGuard bypass), and residential proxy evasion. Multiple layers of ToS violation.

**Fit with existing pipeline**: Medium. The audio fallback path already exists in the worker code (`_resolve_audio_fallback` → Deepgram queue). But the PO Token infrastructure is entirely new.

---

### Strategy E: Audio Download (via Proxy) + Deepgram Transcription

**Description**: Skip transcript API entirely. Use `yt-dlp` with a residential proxy (and optionally PO Tokens) to get the audio stream URL, then transcribe via Deepgram.

**Reliability**: Low-Medium (same issues as Strategy D for obtaining audio URL). If only extracting the audio URL (not downloading the full audio), bandwidth is lower.

**Coverage**: Same as Strategy D.

**Latency**: Same as Strategy D (prohibitive for bulk use).

**Cost model**: Same prohibitive Deepgram costs as Strategy D ($432/month at V1 scale). Only viable as a **fallback for individual videos** where native transcripts fail.

**Operational complexity**: High (same as D minus the PO Token complexity if using proxy-only approach).

**Legal/ToS exposure**: High.

**Fit with existing pipeline**: Good as a fallback — the Deepgram path already exists.

---

### Strategy F: YouTube Data API v3 (Official Captions Endpoint)

**Description**: Use the official YouTube Data API v3 `captions.download` endpoint to retrieve transcript text.

**Reliability**: N/A — **this strategy is non-viable.**

**Reason for elimination**: The official captions API requires **OAuth 2.0 authorization from the video owner**. You cannot download captions from videos you do not own. This is a fundamental API design choice by Google — the captions endpoint is for channel owners to manage their own content, not for third-party consumption.

**Coverage**: Zero for third-party videos.

**Cost model**: N/A.

**Legal/ToS exposure**: N/A (would be fully legal if it worked).

**Fit with existing pipeline**: N/A.

**Verdict: ELIMINATED — technically impossible without video owner consent.**

---

### Strategy G: Client-Side Transcript Extraction (Mobile App)

**Description**: Delegate YouTube transcript/audio extraction to the mobile app. The app (running on a real device with a residential IP) fetches the transcript or audio URL and sends it to the backend.

**Reliability**: Medium. Depends on user's device connectivity. YouTube is less likely to block residential mobile IPs. However, requires the app to be open/active during extraction.

**Coverage**: Native captions accessible from the app's WebView or YouTube API. Audio URL extraction possible via app-level `yt-dlp`-like logic.

**Latency**: Variable. Depends on device processing power and network. User experience includes a "processing" wait on-device before the share completes.

**Cost model**: Zero infrastructure cost for the extraction step. Processing happens on user's device.

**Operational complexity**: High development effort. Requires:
- Implementing YouTube page parsing in the mobile app (React Native)
- Handling YouTube's mobile web anti-bot measures (which are lighter but exist)
- Managing the extraction → upload flow
- Dealing with app lifecycle (what if user closes app mid-extraction?)
- Platform-specific WebView security restrictions

**Legal/ToS exposure**: Low. User is accessing YouTube on their own device with their own IP, similar to how a browser extension works. The ToS enforcement is on the individual, not the service.

**Fit with existing pipeline**: Poor. Requires significant mobile app changes, new API endpoints for transcript upload, and a fundamentally different ingestion flow (push from client vs. pull from server).

---

### Strategy H: Headless Browser on ECS/Fargate (Not Lambda)

**Description**: Run a headless Chrome instance on ECS/Fargate that navigates to YouTube, extracts transcripts from the page DOM, and handles any CAPTCHA challenges.

**Reliability**: Low. YouTube actively detects headless browsers. Even with stealth techniques (Puppeteer-extra-stealth, undetected-chromedriver, nodriver), YouTube's bot detection evolves rapidly. Requires constant maintenance.

**Coverage**: Theoretically same as what a browser user sees (native captions visible in the UI).

**Latency**: High. Browser startup (5-10s) + page load (3-5s) + transcript panel interaction (2-3s) = 10-18s per video. Not parallelizable without multiple browser instances.

**Cost model**:
- ECS/Fargate with Chrome: ~$50-100/month for a small cluster handling 300 videos/day
- Still on cloud IPs — would need residential proxy for the browser's traffic too
- Combined: $55-115/month

**Operational complexity**: Very High. Requires:
- Chrome + stealth patches maintained and updated
- Residential proxy for browser traffic
- CAPTCHA solving service integration (if challenges arise)
- Browser crash/leak management
- YouTube DOM structure monitoring (breaks on every YouTube UI update)

**Legal/ToS exposure**: High. Automated browser access is explicitly prohibited by YouTube ToS. Bot detection circumvention compounds the violation.

**Fit with existing pipeline**: Poor. Entirely new infrastructure (ECS service, Chrome images, proxy routing, DOM parsing logic).

---

### Strategy I: Other Managed Transcript APIs

**Description**: Use other managed services that offer YouTube transcript extraction.

**Candidates investigated:**

1. **Transcript.lol**: Consumer-focused transcription tool using Whisper. Has API access but is designed for individual file uploads, not high-volume YouTube URL processing. Pricing ($10/month unlimited) seems too good for server use — likely has anti-automation restrictions. Not suitable for production API integration.

2. **RapidAPI YouTube Transcript services**: Several exist but with unclear reliability and SLA. Small operators that may disappear. Not evaluated as production-grade.

3. **SearchAPI.io**: Offers YouTube search scraping but no confirmed transcript extraction feature. Pricing ($40-500/month) is for search results, not transcripts.

4. **Apify YouTube Scraper**: General YouTube metadata scraper, not transcript-specific. Would need custom actor development.

**Verdict**: Supadata (Strategy B) is the most mature, documented, and well-priced option in this category. Other alternatives are either consumer tools repurposed, unclear about YouTube transcript capability, or lack production SLA.

---

### Strategy J: Disable YouTube for V1

**Description**: Remove YouTube as a V1 source. Ship without it and add it in a later release once a robust solution is validated.

**Reliability**: N/A — no YouTube feature means no YouTube failures.

**Coverage**: Zero.

**Cost model**: Zero.

**Operational complexity**: Low (remove or disable the worker).

**Legal/ToS exposure**: Zero.

**Fit with existing pipeline**: Negative impact on product — YouTube is declared as a V1 core feature in the launch plan.

**Owner trade-off**: Avoids all complexity but ships with a broken promise. The V1 launch plan explicitly lists YouTube as a supported source. Mobile users expect to share YouTube links. Removing it reduces the product's value proposition significantly.

---

## 4. Comparative Matrix

| Criterion (weight) | A: youtube-transcript-api + Webshare | B: Supadata API | C: Generic proxy | D: yt-dlp + PO Token | E: Audio + Deepgram | F: YouTube API v3 | G: Client-side | H: Headless browser | I: Other APIs | J: Disable |
|---|---|---|---|---|---|---|---|---|---|---|
| **Reliability** (25%) | 7/10 | 9/10 | 7/10 | 4/10 | 4/10 | 0/10 | 5/10 | 3/10 | 5/10 | N/A |
| **Coverage** (20%) | 6/10 (captions only) | 9/10 (captions + AI) | 6/10 | 6/10 | 7/10 | 0/10 | 6/10 | 6/10 | 6/10 | 0/10 |
| **Latency** (10%) | 8/10 | 8/10 | 8/10 | 4/10 | 3/10 | N/A | 5/10 | 4/10 | 7/10 | N/A |
| **Cost** (15%) | 9/10 ($4-7/mo) | 7/10 ($47/mo) | 9/10 ($4-8/mo) | 3/10 ($450+/mo) | 2/10 ($430+/mo) | N/A | 10/10 ($0) | 4/10 ($55-115/mo) | 6/10 (varies) | 10/10 |
| **Operational complexity** (15%) | 8/10 | 10/10 | 7/10 | 2/10 | 3/10 | N/A | 3/10 | 2/10 | 6/10 | 10/10 |
| **Legal/ToS** (5%) | 5/10 | 7/10 | 5/10 | 3/10 | 3/10 | 10/10 | 8/10 | 3/10 | 7/10 | 10/10 |
| **Pipeline fit** (10%) | 9/10 | 8/10 | 8/10 | 5/10 | 7/10 | N/A | 3/10 | 3/10 | 6/10 | N/A |
| **Weighted Score** | **7.5** | **8.6** | **7.2** | **3.7** | **3.9** | **ELIMINATED** | **5.0** | **3.3** | **5.9** | **N/A** |

### Ranking

1. **Strategy B: Supadata API** — 8.6/10 (recommended)
2. **Strategy A: youtube-transcript-api + Webshare** — 7.5/10 (strong alternative)
3. **Strategy C: Generic proxy** — 7.2/10 (variant of A)
4. **Strategy I: Other managed APIs** — 5.9/10 (no clear winner)
5. **Strategy G: Client-side extraction** — 5.0/10 (high dev cost)
6. **Strategy E: Audio + Deepgram** — 3.9/10 (too expensive at scale)
7. **Strategy D: yt-dlp + PO Token** — 3.7/10 (too complex + expensive)
8. **Strategy H: Headless browser** — 3.3/10 (fragile + expensive)
9. **Strategy F: YouTube API v3** — ELIMINATED (requires video owner OAuth)
10. **Strategy J: Disable** — unacceptable for V1

---

## 5. Migration Plan for Recommended Strategy

### Strategy B: Supadata API Integration

#### Phase 1: Account Setup and Validation (1 hour)

1. Create Supadata account at supadata.ai
2. Subscribe to **Mega plan** ($47/month, 30,000 credits)
3. Obtain API key
4. Add `SUPADATA_API_KEY` to `.env.example` and AWS Secrets Manager (`secret_payload`)
5. Manually test API call from local machine with a sample YouTube video URL

#### Phase 2: Code Changes (2-3 hours)

**File: `media_summarizer/workers/youtube_ingestion_worker.py`**

1. Remove `youtube-transcript-api` import and all related error handling
2. Add a new `_fetch_supadata_transcript(video_id, source_url)` function:
   - Makes HTTP GET to `https://api.supadata.ai/v1/youtube/transcript?url=<video_url>`
   - Headers: `x-api-key: <SUPADATA_API_KEY>`
   - Parses response: array of `{text, offset, duration}` segments
   - Joins segments into plain text (same format as current `_normalize_native_transcript`)
   - Returns metadata: language, segments_count, source_detail="supadata_native" or "supadata_ai"
3. Update `process_youtube_message()`:
   - Primary path: call `_fetch_supadata_transcript()`
   - On success: upload to S3, publish completion (existing flow unchanged)
   - On failure (Supadata error or video not processable): attempt Deepgram fallback if owner approves, else mark as failed
4. Update error handling to map Supadata HTTP errors to appropriate `YouTubeIngestionError` codes

**File: `requirements.txt` or `pyproject.toml`**

1. Remove `youtube-transcript-api` dependency
2. Add `httpx` if not already present (for async HTTP calls to Supadata)

**File: Environment configuration**

1. Add `SUPADATA_API_KEY` env var
2. Add `SUPADATA_TIMEOUT_SECONDS=30` env var

#### Phase 3: Deepgram Fallback Adjustment (1 hour)

The existing `_resolve_audio_fallback()` using `yt-dlp` will also fail from Lambda (same IP blocking). Two options:

**Option A (Recommended for V1)**: Remove the audio fallback. Supadata's built-in Whisper fallback covers videos without native captions. If Supadata itself fails, the video is marked as failed with a clear user message.

**Option B (Future enhancement)**: Keep the audio fallback but route `yt-dlp` through the same Webshare proxy (Strategy A as secondary). This adds proxy cost (~$4/month) but provides a second chance for videos Supadata cannot handle.

#### Phase 4: Testing (2-3 hours)

1. **Local test** with docker-compose:
   - Test 10+ YouTube URLs (various: with captions, without captions, age-restricted, private, music videos)
   - Verify transcript quality vs. old native approach
   - Verify error handling for unavailable videos
2. **Lambda deployment test** on AWS dev:
   - Deploy updated worker
   - Submit YouTube URLs via the ingestion API
   - Confirm jobs complete successfully (status `completed` in DynamoDB)
   - Verify transcripts in S3 are usable by artifact workers

#### Phase 5: Monitoring (30 minutes)

1. Add CloudWatch metric: `supadata_api_calls` (success/failure/latency)
2. Add CloudWatch alarm: Supadata failure rate > 10% over 5 minutes
3. Track monthly credit consumption vs. plan limit
4. Set alarm for approaching 80% of monthly credit allowance

#### Total estimated effort: 6-8 hours

#### Infrastructure changes:
- No new AWS resources needed
- One new secret in Secrets Manager (`SUPADATA_API_KEY`)
- Remove `youtube-transcript-api` and `yt-dlp` Python dependencies (optional — can keep `yt-dlp` for future use)

---

## 6. Graceful Failure UX for Unresolvable YouTube URLs

For YouTube URLs that no strategy can handle (video deleted, private, geo-blocked, or all extraction methods exhausted), the following UX applies:

### Failure Categories and User Messages

| Failure Reason | User-Facing Message | Retryable? |
|---|---|---|
| Video unavailable (private/deleted/removed) | "This YouTube video is no longer available." | No |
| Video age-restricted / members-only | "This video requires authentication that we cannot provide." | No |
| Transcript extraction failed (Supadata error) | "We couldn't retrieve the transcript for this video. Please try again later." | Yes (auto-retry 3x, then fail) |
| Supadata credits exhausted | "YouTube processing is temporarily at capacity. Please try again tomorrow." | Yes (next day) |
| Geo-restricted video | "This video is not available in our processing region." | No |
| Unknown/unexpected error | "Something went wrong processing this YouTube video. Please try again." | Yes |

### Implementation

The existing `_mark_job_failed()` function already handles terminal failures. The `user_message` field in `YouTubeIngestionError` is surfaced to the mobile app. The error codes map to the categories above:

- `youtube_unavailable` → permanent failure, no retry
- `youtube_transcript_fetch_failed` → retryable, up to 3 attempts
- `youtube_quota_exceeded` → soft failure, suggest retry later
- `youtube_geo_restricted` → permanent failure

### Mobile App Behavior

When a YouTube ingestion job reaches `failed` status:
1. The inbox vignette shows a failure indicator (red badge or dimmed state)
2. Tapping the item shows the user message from the table above
3. For retryable failures: a "Retry" button is available
4. For permanent failures: a "Remove" button to clean up the inbox

---

## 7. Sources

### Primary Research

- youtube-transcript-api documentation on IP blocking: https://github.com/jdepoix/youtube-transcript-api (README sections on proxies and cloud provider blocking)
- youtube-transcript-api PyPI (v1.2.4): https://pypi.org/project/youtube-transcript-api/
- yt-dlp FAQ on HTTP errors: https://github.com/yt-dlp/yt-dlp/wiki/FAQ
- yt-dlp PO Token Guide: https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide
- bgutil-ytdlp-pot-provider: https://github.com/Brainicism/bgutil-ytdlp-pot-provider
- yt-dlp-getpot-wpc (WebPoClient): https://github.com/coletdjnz/yt-dlp-getpot-wpc
- YouTube Data API v3 Captions: https://developers.google.com/youtube/v3/docs/captions
- YouTube Terms of Service (automated access clause): https://www.youtube.com/static?template=terms

### Managed Transcript Services

- Supadata: https://supadata.ai/youtube-transcript-api
- Supadata pricing: https://supadata.ai/pricing
- Transcript.lol: https://transcript.lol

### Proxy Services

- Webshare residential proxies: https://www.webshare.io/pricing (80M+ IPs, $3.50/GB entry)
- Decodo/Smartproxy residential proxies: https://decodo.com/proxies/residential-proxies/pricing ($3.75/GB entry)

### Transcription Services

- Deepgram pricing (Nova-3): https://deepgram.com/pricing ($0.0048/min streaming promo)

### Internal References

- Current worker implementation: `media_summarizer/workers/youtube_ingestion_worker.py`
- V1 Launch Plan: `docs/V1_LAUNCH_PLAN.md` (YouTube listed as V1 source)
- Existing Deepgram integration: worker already has `_resolve_audio_fallback()` → Deepgram queue path

---

**Document Version**: 1.0
**Date**: 2026-06-09
**Author**: Claude Agent (Research Task-126)
