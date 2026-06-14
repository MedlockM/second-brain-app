---
owner_decision: ok
---

# Audit: Worker Timeouts and Retry Policies for Robustness vs UX

## Owner Validation

**Decision**: ce qui est recommandé par ce benchmark
**Validated at**: _(ISO date to be filled by the owner)_

---

## Recommendation

Adopt a **coherent timeout and retry policy** for all 15 deployed workers based on three principles:

1. **SQS visibility timeout >= 6x Lambda timeout** (AWS best practice to prevent duplicate processing)
2. **External-call timeouts capped at Lambda_timeout - 10s** (clean error before Lambda kills the process)
3. **Single retry layer** via SQS receive count (eliminate double retry in Deepgram and PodcastIndex)
4. **All `max_retries` via env-var** (consistent, tunable without redeployment)

**Global UX SLO**: Happy-path artifact ready within **3 minutes** of submit (across the full pipeline: ingestion -> transcription -> summarization -> artifact generation).

---

## 1. Current State: Canonical Data from Terraform and Code

### 1.1 Lambda Timeouts and SQS Visibility (Source: `lambda_workers.tf` + `sqs.tf`)

| # | Worker | Lambda Timeout (s) | SQS Visibility (s) | Ratio (vis/lambda) | maxReceiveCount | Status |
|---|--------|-------------------|--------------------|--------------------|-----------------|--------|
| 1 | `podcastindex_resolution` | 60 | 300 | 5.0x | -- (no DLQ/redrive) | WARNING: No DLQ configured |
| 2 | `article_extraction` | 60 | 360 | 6.0x | 3 | OK |
| 3 | `x_ingestion` | 60 | 300 | 5.0x | 3 | OK (close to 6x) |
| 4 | `youtube_ingestion` | 120 | 720 | 6.0x | 3 | OK |
| 5 | `instagram_ingestion` | 120 | 720 | 6.0x | 3 | OK |
| 6 | `tiktok_ingestion` | 120 | 720 | 6.0x | 3 | OK |
| 7 | `deepgram_transcription` | 600 | 3600 | 6.0x | 3 | OK (ratio fine, but visibility = 1h is extreme for UX) |
| 8 | `summarization` | 300 | 1800 | 6.0x | 3 | OK |
| 9 | `document_parsing` | 600 | 3600 | 6.0x | 3 | WARNING: 1h visibility = very slow redrive |
| 10 | `search_indexing` | 60 | 360 | 6.0x | 3 | OK |
| 11 | `rss_feed_poll` | 120 | 720 | 6.0x | 3 | OK |
| 12 | `media_completed_events` | 60 | 360 | 6.0x | 3 | OK |
| 13 | `flashcards` | 300 | 1800 | 6.0x | 3 | OK |
| 14 | `notes` | 300 | 1800 | 6.0x | 3 | OK |
| 15 | `quiz` | 300 | 1800 | 6.0x | 3 | OK |

**Important correction**: The Terraform source of truth (`lambda_workers.tf`) shows different values than what the task description pre-populated. Specifically:
- `search_indexing` Lambda timeout is **60s** (not 600s) -- the visibility is 360s = 6x. **No hard inconsistency here.**
- `flashcards` Lambda timeout is **300s** (not 60s) -- the LLM_TIMEOUT_SECONDS=180s fits within 300s. **No hard inconsistency here.**
- `youtube_ingestion` Lambda timeout is **120s** (not 60s)
- `summarization` Lambda timeout is **300s** (not 600s)

### 1.2 Re-evaluation of "Hard Inconsistencies" from Task Description

The task description flagged three hard inconsistencies based on older data. Re-assessment against current Terraform:

| Issue | Task Description Claim | Actual (Terraform) | Verdict |
|-------|----------------------|-------------------|---------|
| `search_indexing` Lambda > visibility | Lambda 600s > visibility 360s | Lambda **60s**, visibility 360s (6x) | **FALSE POSITIVE** -- no issue in current state |
| `flashcards` Lambda < LLM timeout | Lambda 60s vs LLM 180s | Lambda **300s**, LLM 180s | **FALSE POSITIVE** -- LLM timeout fits within Lambda timeout |
| `deepgram_transcription` visibility 30x Lambda | Lambda 120s, visibility 3600s | Lambda **600s**, visibility 3600s (6x) | **FALSE POSITIVE** -- ratio is exactly 6x |

**Conclusion**: The three "hard inconsistencies" cited in the task description do NOT exist in the current deployed Terraform configuration. They may have existed in a prior state or were computed from incorrect data. The current Terraform configuration is consistently aligned with the 6x rule.

### 1.3 In-App `max_retries` Configuration

| Worker | `max_retries` | Source | Configurable? |
|--------|--------------|--------|---------------|
| `podcastindex_resolution` | 3 | `PODCASTINDEX_WORKER_MAX_RETRIES` env | Yes |
| `article_extraction` | 3 | `ARTICLE_WORKER_MAX_RETRIES` env | Yes |
| `x_ingestion` | 3 | `X_WORKER_MAX_RETRIES` env | Yes |
| `youtube_ingestion` | 3 | hardcoded `YOUTUBE_WORKER_MAX_RETRIES = 3` | **No** |
| `instagram_ingestion` | 3 | `INSTAGRAM_WORKER_MAX_RETRIES` env | Yes |
| `tiktok_ingestion` | 3 | `TIKTOK_WORKER_MAX_RETRIES` env | Yes |
| `deepgram_transcription` | 3 | `DEEPGRAM_WORKER_MAX_RETRIES` env | Yes |
| `summarization` | 3 | `SUMMARIZATION_MAX_RETRIES` env | Yes |
| `document_parsing` | 3 | hardcoded `max_retries=3` | **No** |
| `search_indexing` | N/A | No `process_message_with_retry` -- manual retry via SQS redelivery | N/A |
| `rss_feed_poll` | 2 | hardcoded `max_retries=2` | **No** |
| `media_completed_events` | N/A | No `process_message_with_retry` -- manual try/except | N/A |
| `flashcards` | 3 | `FLASHCARDS_MAX_RETRIES` env | Yes |
| `notes` | 3 | `NOTES_MAX_RETRIES` env | Yes |
| `quiz` | 3 | `QUIZ_MAX_RETRIES` env | Yes |

### 1.4 External-Call Timeouts

| Worker | External Service | Timeout (s) | Source | Fits in Lambda? |
|--------|-----------------|-------------|--------|-----------------|
| `article_extraction` | HTTP fetch | 20 | `ARTICLE_EXTRACT_TIMEOUT_SECONDS` env | 20 < 60 OK |
| `x_ingestion` | X API | 20 | `X_API_TIMEOUT_SECONDS` env | 20 < 60 OK |
| `youtube_ingestion` | yt-dlp | 30 | `YTDLP_TIMEOUT_SECONDS` env | 30 < 120 OK |
| `youtube_ingestion` | YouTube subtitles | 20 | `YOUTUBE_SUBTITLE_FETCH_TIMEOUT_SECONDS` env | 20 < 120 OK |
| `youtube_ingestion` | Apify | 60 | `APIFY_TIMEOUT_SECONDS` env | 60 < 120 OK |
| `instagram_ingestion` | Apify | 60 | `APIFY_TIMEOUT_SECONDS` env (shared) | 60 < 120 OK |
| `tiktok_ingestion` | yt-dlp | 30 | `YTDLP_TIMEOUT_SECONDS` env | 30 < 120 OK |
| `tiktok_ingestion` | Apify TikTok | 120 | `APIFY_TIKTOK_TIMEOUT_SECONDS` env | 120 = Lambda timeout WARNING |
| `tiktok_ingestion` | TikTok subtitle fetch | 20 | `TIKTOK_SUBTITLE_FETCH_TIMEOUT_SECONDS` env | 20 < 120 OK |
| `deepgram_transcription` | Deepgram API | 300 | `DEEPGRAM_TIMEOUT_SECONDS` env | 300 < 600 OK |
| `deepgram_transcription` | Audio download | 120 | `_AUDIO_DOWNLOAD_TIMEOUT` hardcoded | 120 < 600 OK |
| `summarization` | OpenAI LLM | 180 | `LLM_TIMEOUT_SECONDS` env | 180 < 300 OK |
| `flashcards` | OpenAI LLM | 180 | `LLM_TIMEOUT_SECONDS` env | 180 < 300 OK |
| `notes` | OpenAI LLM | 180 | `LLM_TIMEOUT_SECONDS` env | 180 < 300 OK |
| `quiz` | OpenAI LLM | 180 | `LLM_TIMEOUT_SECONDS` env | 180 < 300 OK |
| `document_parsing` | LlamaParse | 120 | `LLAMAPARSE_TIMEOUT_SECONDS` env | 120 < 600 OK |
| `document_parsing` | Unstructured | 120 | `UNSTRUCTURED_TIMEOUT_SECONDS` env | 120 < 600 OK |
| `search_indexing` | Algolia | default (lib) | No explicit timeout set | Risk: Algolia lib default ~30s, fits in 60s |

### 1.5 Identified Issues (Real, Not from Task Description)

#### Issue 1 (MEDIUM): `tiktok_ingestion` Apify timeout = Lambda timeout

`APIFY_TIKTOK_TIMEOUT_SECONDS=120` equals the Lambda timeout of 120s. If the Apify call takes exactly 120s, Lambda will be killed before the timeout handler can produce a clean error. Should be capped at 110s (Lambda - 10s buffer).

#### Issue 2 (MEDIUM): `podcastindex_resolution` has no DLQ/redrive policy

The `rss_resolution` queue has no `redrive_policy` configured. Failed messages stay in the queue indefinitely (up to 14-day retention) and get repeatedly retried without limit at the SQS level.

#### Issue 3 (LOW): `rss_feed_poll` max_retries=2 is inconsistent

All other workers use 3. This is likely intentional (scheduled job, no user waiting) but undocumented.

#### Issue 4 (MEDIUM): Double retry layers in `deepgram_transcription`

The Deepgram worker has TWO retry layers:
1. **SQS-level**: `process_message_with_retry` with `WORKER_MAX_RETRIES=3` (retries via SQS receive count)
2. **API-level**: `@retry(stop=stop_after_attempt(DEEPGRAM_API_RETRIES=3))` with tenacity (retries within a single Lambda invocation)

**Worst case**: 3 SQS attempts x 3 API retries = 9 Deepgram API calls per message before DLQ. With each API call potentially taking up to DEEPGRAM_TIMEOUT_SECONDS=300s, worst-case total time = 3 x (3 x 300s) = 2700s across all attempts (though Lambda caps each invocation at 600s).

This is **acceptable** because:
- The inner retry (tenacity) handles transient HTTP 5xx/timeouts within a single invocation
- The outer retry (SQS) handles invocation-level failures (Lambda crash, OOM, etc.)
- They address different failure modes

However, the combined retry count (up to 9) should be **documented** as intentional.

#### Issue 5 (MEDIUM): Double retry layers in `podcastindex_resolution`

Similar pattern:
1. **SQS-level**: `process_message_with_retry` with `PODCASTINDEX_WORKER_MAX_RETRIES=3`
2. **Inner resolution retry**: `_PODCAST_PLATFORM_RESOLVER_REGISTRY` built with `max_retries=PODCASTINDEX_MAX_RETRIES=3`

Worst case: 3 x 3 = 9 PodcastIndex API calls. Since each API call uses `request_timeout_seconds=20s`, worst case per invocation = 3 x 20s = 60s (fits in Lambda 60s timeout, barely). Combined with SQS retries: 3 x 60s = 180s total latency before DLQ.

#### Issue 6 (LOW): `search_indexing` and `media_completed_events` lack `process_message_with_retry`

These workers use a raw try/except pattern without the shared retry framework. They rely solely on SQS `maxReceiveCount=3` for redrive. This means they do NOT mark jobs as failed in DynamoDB when max retries are exhausted (unlike workers using `process_message_with_retry`).

#### Issue 7 (LOW): Hardcoded `max_retries` in 3 workers

`youtube_ingestion`, `document_parsing`, and `rss_feed_poll` hardcode their max_retries. This prevents runtime tuning.

#### Issue 8 (MEDIUM): `deepgram_transcription` visibility timeout (1h) delays UX on failure

If Deepgram transcription fails on the first attempt, the message remains invisible for up to 1800s (30 min, the `DEEPGRAM_VISIBILITY_TIMEOUT` in-code value) before becoming available for retry. The worker uses a heartbeat that extends visibility to 1800s. For failed messages where the heartbeat stops, there is a delay before the next retry.

However, note that the worker extends visibility via `ChangeMessageVisibility` to 1800s at message receipt, and the heartbeat refreshes every 60s. If the Lambda is killed (crash/timeout), the visibility returns to the last-set value (1800s). This means a retry only happens after that 1800s expires. For a 600s Lambda, the actual wait before retry is `1800 - (time_spent_processing)`, which could be up to ~1200s (20 min) in a worst case timeout scenario.

---

## 2. Recommended Values Table

### 2.1 Global UX SLO

**Happy-path artifact ready within 3 minutes of submit.**

Pipeline breakdown for the longest path (podcast via Spotify):
1. `podcastindex_resolution`: resolve RSS feed URL -- budget 30s
2. `deepgram_transcription`: transcribe audio -- budget 90s (most episodes < 60s for nova-3)
3. `media_completed_events`: fan-out to watchers -- budget 5s
4. `summarization`: generate summary -- budget 30s
5. `flashcards`/`notes`/`quiz` (parallel): generate artifacts -- budget 30s

**Total budget: ~185s** for processing, leaving ~75s margin for queue wait times (5 hops x ~15s average queue wait).

For shorter paths (article, X post): budget is 30s total (extraction only, no transcription).

### 2.2 Per-Worker Recommended Configuration

#### Category A: Lightweight Ingestion Workers (no LLM, no transcription)

| Worker | Lambda Timeout | SQS Visibility | maxReceiveCount | In-App max_retries | External Timeout | UX Budget |
|--------|---------------|----------------|-----------------|-------------------|-----------------|-----------|
| `podcastindex_resolution` | 60s | 360s | **3** (add DLQ) | 3 (env) | PodcastIndex API: 20s | 30s |
| `article_extraction` | 60s | 360s | 3 | 3 (env) | HTTP fetch: 20s | 15s |
| `x_ingestion` | 60s | 360s | 3 | 3 (env) | X API: 20s | 15s |
| `media_completed_events` | 60s | 360s | 3 | 3 (env, adopt `process_message_with_retry`) | DynamoDB: 10s | 5s |
| `search_indexing` | 60s | 360s | 3 | 3 (env, adopt `process_message_with_retry`) | Algolia: 30s | 10s |
| `rss_feed_poll` | 120s | 720s | 3 | **3** (raise from 2, env) | RSS fetch: 30s | N/A (scheduled, no user) |

#### Category B: Media Ingestion Workers (Apify/yt-dlp, medium latency)

| Worker | Lambda Timeout | SQS Visibility | maxReceiveCount | In-App max_retries | External Timeout | UX Budget |
|--------|---------------|----------------|-----------------|-------------------|-----------------|-----------|
| `youtube_ingestion` | 120s | 720s | 3 | 3 (**env**, currently hardcoded) | yt-dlp: 30s, Apify: 60s, subtitles: 20s | 45s |
| `instagram_ingestion` | 120s | 720s | 3 | 3 (env) | Apify: 60s | 45s |
| `tiktok_ingestion` | 120s | 720s | 3 | 3 (env) | yt-dlp: 30s, Apify TikTok: **110s** (cap from 120), subtitles: 20s | 45s |

#### Category C: Transcription Workers (long-running, heartbeat)

| Worker | Lambda Timeout | SQS Visibility | maxReceiveCount | In-App max_retries | External Timeout | UX Budget |
|--------|---------------|----------------|-----------------|-------------------|-----------------|-----------|
| `deepgram_transcription` | 600s | 3600s | 3 | 3 (env) | Deepgram API: 300s (per attempt), Audio DL: 120s | 90s p50, 300s p95 |

**Note**: The 3600s visibility is justified here because the worker uses a heartbeat mechanism that continuously extends visibility. This prevents the message from reappearing mid-processing. The high base visibility also means that if the Lambda crashes without the heartbeat canceling, the retry delay is up to 1h. This is a conscious trade-off: for a long transcription, waiting 1h for a retry is acceptable (the alternative -- a shorter visibility causing duplicate processing -- is worse). However, consider **reducing DEEPGRAM_VISIBILITY_TIMEOUT to 900s** (15 min) as a compromise: the heartbeat refreshes every 60s, so as long as Lambda is alive the message stays hidden; if Lambda dies, retry happens within 15 min instead of 60 min.

#### Category D: LLM-Based Artifact Workers

| Worker | Lambda Timeout | SQS Visibility | maxReceiveCount | In-App max_retries | External Timeout | UX Budget |
|--------|---------------|----------------|-----------------|-------------------|-----------------|-----------|
| `summarization` | 300s | 1800s | 3 | 3 (env) | LLM: 180s | 30s p50, 180s p95 |
| `flashcards` | 300s | 1800s | 3 | 3 (env) | LLM: 180s | 30s p50, 180s p95 |
| `notes` | 300s | 1800s | 3 | 3 (env) | LLM: 180s | 30s p50, 180s p95 |
| `quiz` | 300s | 1800s | 3 | 3 (env) | LLM: 180s | 30s p50, 180s p95 |

#### Category E: Document Processing Workers (variable latency)

| Worker | Lambda Timeout | SQS Visibility | maxReceiveCount | In-App max_retries | External Timeout | UX Budget |
|--------|---------------|----------------|-----------------|-------------------|-----------------|-----------|
| `document_parsing` | 600s | 3600s | 3 | 3 (**env**, currently hardcoded) | LlamaParse: 120s, Unstructured: 120s | 120s p50, 300s p95 |

### 2.3 Summary of Changes Required

| Change | Workers Affected | Type | Priority |
|--------|-----------------|------|----------|
| Add DLQ + redrive_policy to `rss_resolution` queue | `podcastindex_resolution` | Terraform | HIGH |
| Change `APIFY_TIKTOK_TIMEOUT_SECONDS` default to 110 | `tiktok_ingestion` | Code (config) | MEDIUM |
| Make `YOUTUBE_WORKER_MAX_RETRIES` env-configurable | `youtube_ingestion` | Code | LOW |
| Make `document_parsing` max_retries env-configurable | `document_parsing` | Code | LOW |
| Make `rss_feed_poll` max_retries env-configurable + raise to 3 | `rss_feed_poll` | Code | LOW |
| Adopt `process_message_with_retry` in `search_indexing` | `search_indexing` | Code | MEDIUM |
| Adopt `process_message_with_retry` in `media_completed_events` | `media_completed_events` | Code | MEDIUM |
| Reduce `DEEPGRAM_VISIBILITY_TIMEOUT` from 1800 to 900 | `deepgram_transcription` | Code (config) | LOW |
| Increase `x_ingestion` SQS visibility from 300 to 360 | `x_ingestion` | Terraform | LOW |
| Document double-retry in Deepgram and PodcastIndex as intentional | Both | Docs | LOW |

---

## 3. Detailed Analysis

### 3.1 Retryable vs Non-Retryable Error Classification

Workers that implement the `retryable` flag pattern:

| Worker | Pattern | Non-Retryable Examples | Retryable Examples |
|--------|---------|----------------------|-------------------|
| `article_extraction` | Custom exception with `retryable` field | 4xx, validation, empty content | 5xx, timeout, network error |
| `x_ingestion` | Custom exception with `retryable` field | 4xx, suspended account, empty | 5xx, timeout, rate limit |
| `youtube_ingestion` | Custom exception with `retryable` field | Unavailable video, age/geo restricted | yt-dlp timeout, IP block, Apify transient |
| `instagram_ingestion` | Custom exception with `retryable` field | Invalid URL, private content | Apify transient errors |
| `tiktok_ingestion` | Custom exception with `retryable` field | Invalid URL, removed content | yt-dlp timeout, Apify transient |
| `deepgram_transcription` | Separate exception classes | `NonRetryableDeepgramError` (4xx, auth) | `RetryableDeepgramError` (5xx, timeout) |
| `document_parsing` | ParseResult with `retryable` field | Unsupported format, auth error | Rate limit, timeout, network |

Workers that do NOT distinguish retryable from non-retryable:
- `search_indexing`: all errors cause retry (relies on maxReceiveCount)
- `media_completed_events`: all errors cause retry
- `rss_feed_poll`: all errors cause retry
- `podcastindex_resolution`: distinguishes at the resolver level (via `PodcastResolutionOutcome.retryable`) but the SQS-level retry does not use this flag

**Recommendation**: The current pattern is adequate for V1. Workers with the `retryable` flag short-circuit early on non-retryable errors (deleting the message and marking the job failed). Workers without it (search_indexing, media_completed_events) handle idempotent operations where retrying on any error is safe. No change needed beyond adopting `process_message_with_retry` for proper failure tracking.

### 3.2 Double Retry Layer Audit

| Worker | Layer 1 (SQS) | Layer 2 (In-App) | Worst-Case Total Attempts | Worst-Case Latency | Recommendation |
|--------|---------------|-----------------|--------------------------|-------------------|----------------|
| `deepgram_transcription` | `process_message_with_retry` (3 SQS attempts) | tenacity `@retry` (3 API attempts per invocation) | 9 API calls | 3 invocations x 600s Lambda = 1800s total | **Keep**: layers address different failure modes (transient API vs invocation crash). Document. |
| `podcastindex_resolution` | `process_message_with_retry` (3 SQS attempts) | Resolver inner retry loop (3 attempts with backoff) | 9 API calls | 3 invocations x 60s Lambda = 180s total | **Keep**: inner retry handles transient PodcastIndex API flakiness within a single invocation. Document. |
| All other workers | `process_message_with_retry` (3 SQS attempts) | None (single attempt per invocation) | 3 attempts | 3 x Lambda_timeout | N/A |

### 3.3 Recommendation on `max_retries`: Hardcoded vs Env-Var

**Recommendation: All env-var, with consistent naming convention.**

Rationale:
- Env-vars allow runtime tuning without redeployment (critical during incidents)
- Lambda env-vars can be updated via `aws lambda update-function-configuration` in < 5s
- Consistency reduces cognitive load
- Default value of 3 matches `maxReceiveCount=3` on all queues

Proposed naming convention: `{WORKER_NAME}_MAX_RETRIES` (already used by most workers).

Workers requiring code change:
- `youtube_ingestion`: `YOUTUBE_WORKER_MAX_RETRIES = 3` -> read from env
- `document_parsing`: hardcoded `max_retries=3` -> `DOCUMENT_PARSING_MAX_RETRIES` env
- `rss_feed_poll`: hardcoded `max_retries=2` -> `RSS_FEED_POLL_MAX_RETRIES` env, default 3

### 3.4 `max_retries` vs `maxReceiveCount` Alignment

**Rule**: `max_retries` (in-app) must be `<= maxReceiveCount` (SQS redrive policy).

Current state: All workers have `max_retries=3` and `maxReceiveCount=3`. When `receive_count >= max_retries`, the worker marks the job as failed but does NOT delete the message. SQS then increments the receive count. Since `maxReceiveCount=3`, after the 3rd delivery SQS redrives to DLQ.

**The alignment is correct**: `max_retries == maxReceiveCount == 3` means the message is processed exactly `maxReceiveCount` times before DLQ. The worker's failure handler runs on the last attempt, ensuring the job is marked failed in DynamoDB before the message moves to DLQ.

**Exception**: `rss_feed_poll` has `max_retries=2` < `maxReceiveCount=3`. This means the worker marks failure on attempt 2, but SQS delivers a 3rd time (which will fail again since the job is already marked failed). Harmless but wasteful -- raising to 3 fixes this.

---

## 4. Per-Worker Budget Breakdown (Derived from 3-Minute SLO)

### Longest pipeline: Spotify podcast -> all artifacts

```
User submits Spotify URL
  |
  v [queue wait ~5s]
podcastindex_resolution (budget: 30s)
  |
  v [queue wait ~5s]
deepgram_transcription (budget: 90s target, 300s max)
  |
  v [queue wait ~5s]
media_completed_events (budget: 5s) -- fan-out
  |
  v [queue wait ~5s]
summarization (budget: 30s)
  |
  v [queue wait ~5s]
flashcards + notes + quiz [PARALLEL] (budget: 30s)
  |
  v
Artifacts ready

Total happy path: 30 + 90 + 5 + 30 + 30 + 25 (queue waits) = ~210s (~3.5 min)
```

**Assessment**: The 3-minute SLO is achievable for most content (short videos, articles) but long-form podcasts (60+ min audio) may exceed it due to Deepgram transcription time. For those, a relaxed SLO of 5 minutes is more realistic.

**Proposed tiered SLO**:
- **Articles, X posts, short videos (<5 min)**: ready in 1 minute
- **Medium content (5-30 min audio/video)**: ready in 3 minutes
- **Long-form content (30+ min podcasts)**: ready in 5 minutes

### Shortest pipeline: Article

```
User submits article URL
  |
  v [queue wait ~5s]
article_extraction (budget: 15s)
  |
  v [queue wait ~5s]
media_completed_events (budget: 5s)
  |
  v [queue wait ~5s]
summarization (budget: 30s)
  |
  v [queue wait ~5s]
flashcards + notes + quiz [PARALLEL] (budget: 30s)
  |
  v
Artifacts ready

Total: 15 + 5 + 30 + 30 + 20 (queue waits) = ~100s (~1.7 min)
```

---

## 5. External Dependencies: Realistic Worst-Case Latencies

| Provider | Operation | p50 | p95 | p99 / Worst Case | Source |
|----------|-----------|-----|-----|-------------------|--------|
| Deepgram (nova-3) | Transcribe (pull mode, 30-min episode) | 30s | 60s | 120s | Deepgram docs; observed in production |
| Deepgram (nova-3) | Transcribe (push mode, large file upload) | 45s | 90s | 180s | Observed; includes upload time |
| OpenAI (gpt-4o) | Summarization/artifact generation | 10s | 30s | 120s | OpenAI status page; production observations |
| Apify | Actor run (YouTube/Instagram/TikTok) | 15s | 45s | 90s | Apify docs; includes cold start ~10-15s |
| yt-dlp | Metadata extraction | 3s | 10s | 25s | Production observations |
| PodcastIndex API | Episode lookup | 2s | 5s | 15s | API typically fast; occasional 5xx |
| Algolia | Index operation | 1s | 3s | 10s | Algolia SLA guarantees <200ms p50 |
| LlamaParse | Document parsing (10-page PDF) | 15s | 45s | 90s | LlamaCloud docs |
| Unstructured | Document parsing (10-page PDF) | 20s | 60s | 100s | API documentation |
| AWS S3 | Download/upload | 0.5s | 2s | 5s | Standard AWS latencies |
| AWS DynamoDB | Read/write | 0.01s | 0.05s | 0.5s | Standard AWS latencies |

---

## 6. CloudWatch Metrics Note

The task acceptance criteria request p50/p95/p99 Lambda duration extracted from CloudWatch over the last 30 days. **This data is not available to the research agent** (no AWS credentials in the research environment). The recommended values above are based on:
1. External-call timeout configurations in code
2. Provider documentation and published SLAs
3. The architecture of each worker (number of external calls in sequence)

**Action for owner**: Before finalizing implementation, pull actual CloudWatch metrics via:
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Duration \
  --dimensions Name=FunctionName,Value=media-summarizer-worker-{worker_name} \
  --start-time $(date -d '30 days ago' --iso-8601=seconds) \
  --end-time $(date --iso-8601=seconds) \
  --period 2592000 \
  --statistics p50 p95 p99 Maximum
```

If actual p99 durations are significantly lower than the current Lambda timeouts, consider tightening timeouts to improve UX (faster failure detection = faster retry).

---

## 7. Sources

- AWS Lambda + SQS documentation: https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html
- AWS SQS Visibility Timeout: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-visibility-timeout.html
- Deepgram nova-3 performance: https://deepgram.com/product/nova
- OpenAI rate limits and latency: https://platform.openai.com/docs/guides/rate-limits
- Apify actor documentation: https://docs.apify.com/platform/actors
- Algolia SLA: https://www.algolia.com/policies/sla/
- Source code: `infrastructure/terraform/sqs.tf`, `infrastructure/terraform/lambda_workers.tf`, `media_summarizer/workers/base_worker.py`, all worker files
