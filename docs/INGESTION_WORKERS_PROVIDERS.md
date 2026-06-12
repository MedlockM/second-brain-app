# Ingestion Workers and Providers Reference

Authoritative reference for the ingestion pipeline. Lists each source type's
primary extraction path, fallback chain, terminal failure behavior, and
downstream hand-off.

Last verified against codebase: 2026-06-12 (post task-195 unified artifact-generator consolidation).

---

## Table of Contents

1. [Article](#article)
2. [Podcast](#podcast)
3. [YouTube](#youtube)
4. [Instagram Reel](#instagram-reel)
5. [Instagram Post](#instagram-post)
6. [TikTok](#tiktok)
7. [X (Twitter)](#x-twitter)
8. [Document](#document)
9. [Audio (direct URL / upload)](#audio-direct-url--upload)
10. [RSS Feed Polling](#rss-feed-polling)
11. [Cross-cutting: Deepgram Modes](#cross-cutting-deepgram-modes)
12. [Decision Tree: URL Classification and Routing](#decision-tree-url-classification-and-routing)
13. [References](#references)

---

## Article

**Source type**: `article` (also covers the catch-all `web` fallback)
**Worker file**: `media_summarizer/workers/article_extraction_worker.py`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| trafilatura | `trafilatura.extract()` | Clean text from HTML (no comments, tables, links) | `ARTICLE_EXTRACTION_QUEUE`, `TRANSCRIPT_BUCKET`, `ARTICLE_EXTRACT_TIMEOUT_SECONDS`, `ARTICLE_EXTRACT_MAX_HTML_BYTES`, `ARTICLE_EXTRACT_USER_AGENT` |

Workflow:
1. HTTP GET the normalized URL via `httpx` (streaming, respects `ARTICLE_EXTRACT_MAX_HTML_BYTES`)
2. Validate `Content-Type` is `text/html` or `application/xhtml+xml`
3. Extract clean text with `trafilatura.extract(output_format="txt")`
4. Upload text to S3 as `{job_id}.txt`
5. Publish `episode_completion_status(status=success)` to `EPISODE_COMPLETED_EVENTS_QUEUE`

Ref: `article_extraction_worker.py::_fetch_article_html`, `article_extraction_worker.py::_extract_clean_text`

### Fallback chain

No fallback — failure is terminal.

### Terminal failure mode

- Mark `ProcessingJob` as failed (`error_step="article_extraction"`)
- Publish `episode_completion_status(status=failure)` to `EPISODE_COMPLETED_EVENTS_QUEUE`
- Error codes: `article_fetch_timeout`, `article_http_error`, `article_unsupported_content_type`, `article_extraction_empty`, `article_extraction_failed`

Ref: `article_extraction_worker.py::_mark_job_failed`, `article_extraction_worker.py::_ERROR_MESSAGES`

### Downstream dependencies

Publishes to `EPISODE_COMPLETED_EVENTS_QUEUE` (terminates inline with success/failure event).

---

## Podcast

**Source type**: `podcast`
**Worker file**: `media_summarizer/workers/podcastindex_resolution_worker.py`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| PodcastIndex.org API | `PodcastPlatformResolverRegistry` (Spotify, Apple, Deezer, RSS) | Audio enclosure URL from episode metadata | `PODCASTINDEX_API_KEY`, `PODCASTINDEX_API_SECRET`, `PODCASTINDEX_RESOLUTION_QUEUE`, `PODCASTINDEX_EPISODE_CANDIDATES`, `PODCASTINDEX_MAX_RETRIES` |

Workflow:
1. `podcastindex_resolution_worker` consumes `podcastindex-resolution-queue`
2. Marks the job `EXTRACTING` (was `mark_extracting()` post task-175 — historically `RSS_RESOLVING`)
3. Dispatches via `PodcastPlatformResolverRegistry` based on the source platform:
   - **Spotify**: oEmbed metadata → PodcastIndex `byfeedid` search → episode title fuzzy match
   - **Apple Podcasts**: oEmbed metadata → PodcastIndex `episodes/byitunesid` direct lookup (preferred) with `byfeedid` + title-match fallback when the iTunes-ID lookup misses
   - **Deezer**: Deezer public API metadata → PodcastIndex feed search → episode match
   - **RSS**: Direct feed XML parsing + optional PodcastIndex enrichment
4. Resolved audio URL is enqueued to `deepgram-transcription-queue` with `deepgram_mode="pull"`

Ref: `podcastindex_resolution_worker.py::_resolve_audio_url`, `podcast_platform_resolvers.py::SpotifyPodcastPlatformResolver`, `podcast_platform_resolvers.py::ApplePodcastsPlatformResolver` (line 800 — `byitunesid` path), `podcast_platform_resolvers.py::DeezerPodcastPlatformResolver`, `podcast_platform_resolvers.py::RssPodcastPlatformResolver`

### Fallback chain

| Step | Trigger condition | Action |
|---|---|---|
| 1 (primary) | `feed_url` + `episode_guid` present in message AND RSS `<podcast:transcript>` tag yields valid transcript | Upload pre-existing transcript to S3, publish completion event, skip Deepgram entirely (provider=`podcasting_2.0`) |
| 2 (fallback) | Tag absent / fetch fails / transcript too short / no `feed_url` or `episode_guid` | Enqueue to `deepgram-transcription-queue` with `deepgram_mode="pull"` (Deepgram fetches the audio enclosure URL directly) |

The Podcasting 2.0 short-circuit is implemented in `podcastindex_resolution_worker.py::_try_rss_transcript_short_circuit` (line 140) which calls `utils/rss_transcript.py::fetch_rss_transcript()`. When successful, the completion event carries `"provider": "podcasting_2.0"` in its `transcription_metadata`.

Ref: `podcastindex_resolution_worker.py::_try_rss_transcript_short_circuit` (line 140), `utils/rss_transcript.py::fetch_rss_transcript`

### Terminal failure mode

- Platform resolver returns a non-resolved outcome → worker raises `RuntimeError` containing the error code
- Error codes: `INVALID_PLATFORM_URL`, `EPISODE_NOT_FOUND`, `AUDIO_URL_NOT_FOUND`, `UPSTREAM_LOOKUP_FAILED`, `UNSUPPORTED_PLATFORM` (from `PodcastResolverErrorCode`)
- After SQS max retries (`PODCASTINDEX_WORKER_MAX_RETRIES`, default 3), the job stays in failed state via the base worker's retry handler

Ref: `podcast_resolver_foundation.py::PodcastResolverErrorCode`, `podcastindex_resolution_worker.py::process_message`

### Downstream dependencies

Hands off to `deepgram-transcription-queue` with `deepgram_mode="pull"` (Deepgram fetches the audio host directly — open CDNs like libsyn / simplecast / megaphone / anchor.fm are friendly).

---

## YouTube

**Source type**: `youtube`
**Worker file**: `media_summarizer/workers/youtube_ingestion_worker.py`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| yt-dlp | `yt_dlp.YoutubeDL` with `writesubtitles=True`, `writeautomaticsub=True`, `subtitleslangs=["all"]` | Native + auto-generated subtitle text (VTT / SRT / JSON) from YouTube CDN | `YOUTUBE_INGESTION_QUEUE`, `YTDLP_TIMEOUT_SECONDS`, `TRANSCRIPT_BUCKET` |

Workflow:
1. Extract `video_id` from the normalized URL
2. Run `yt_dlp.YoutubeDL.extract_info(url, download=False)` with subtitle options
3. Collect candidates via `collect_subtitle_candidates(info)` from `utils/ytdlp_helpers.py`
4. If subtitles found: fetch, parse, upload to S3 as `{job_id}.txt`, publish success event with `strategy_used="native_subtitles"`

Ref: `youtube_ingestion_worker.py::_extract_youtube_info`, `youtube_ingestion_worker.py::_fetch_native_subtitles`, `utils/ytdlp_helpers.py::collect_subtitle_candidates`

### Fallback chain

| Step | Trigger condition | Action |
|---|---|---|
| 1 (primary) | yt-dlp extraction succeeds AND subtitles present | Fetch and parse native subtitles, upload transcript to S3 (`strategy_used="native_subtitles"`) |
| 2 | yt-dlp raises with YouTube IP-block / login-wall error (`_is_ip_blocked_youtube_error`) | Apify YouTube Transcript actor (`APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID`, default `scrape-creators~best-youtube-transcripts-scraper`) via `_fetch_apify_transcript()` — synchronous run, read dataset items, prefer `transcript_only_text` field, fall back to joined `transcript[].text` segments (`strategy_used="apify_transcript"`) |
| 3 | yt-dlp succeeded but no subtitles found (`NativeSubtitlesUnavailable`) | Resolve audio URL from yt-dlp info dict via `resolve_direct_media_url(info)`, enqueue to `deepgram-transcription-queue` with `deepgram_mode="push"` (`strategy_used="deepgram_via_ytdlp_url"`) |

The IP-block matcher normalises Unicode `'` (U+2019) to ASCII `'` before substring matching so phrasings like `Sign in to confirm you're not a bot` match alongside the ASCII variant. It does NOT match geo restrictions, deleted videos, rate limits, or generic yt-dlp errors — those propagate as terminal `youtube_*` failures.

Apify call uses dedicated credentials: `APIFY_YOUTUBE_API_TOKEN` (token) and `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID` (actor). The request payload is `{"videoUrls": [<url>]}` — note the camelCase `videoUrls`, not `urls`, and the `~` separator in the actor ID (Apify Console UI shows `/`, but the API requires `~`).

Ref: `youtube_ingestion_worker.py::process_youtube_message`, `youtube_ingestion_worker.py::_fetch_apify_transcript`, `youtube_ingestion_worker.py::_is_ip_blocked_youtube_error`

### Terminal failure mode

- `YouTubeIngestionError` after max retries (`YOUTUBE_WORKER_MAX_RETRIES`, default 3)
- Mark job failed (`error_step="youtube_ingestion"`)
- Publish `episode_completion_status(status=failure)`
- Non-retryable codes: `youtube_unavailable` (deleted/private), `youtube_age_restricted`, `youtube_geo_restricted`, `youtube_apify_failed` (Apify also failed after IP-block), `youtube_subtitle_fetch_failed`
- Retryable codes: `youtube_ytdlp_timeout`, `youtube_apify_failed` with `retryable=True` (Apify network / 5xx)

Ref: `youtube_ingestion_worker.py::YouTubeIngestionError`

### Downstream dependencies

- Native subtitles / Apify transcript success: `EPISODE_COMPLETION_EVENTS_QUEUE` env var, default queue `episode-completion-events` (inline)
- yt-dlp succeeded + no captions: `deepgram-transcription-queue` (push mode, then Deepgram publishes the completion event to its own `EPISODE_COMPLETED_EVENTS_QUEUE` — see drift note in Cross-cutting section)

---

## Instagram Reel

**Source type**: `instagram-reel`
**Worker file**: `media_summarizer/workers/instagram_ingestion_worker.py`
**Resolver**: `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py::InstagramApifyResolver`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| yt-dlp | `yt_dlp.YoutubeDL.extract_info(url, download=False)` | Direct audio URL (best audio-only DASH/HTTPS stream) | `INSTAGRAM_INGESTION_QUEUE`, `YTDLP_TIMEOUT_SECONDS` |

Workflow:
1. `instagram_ingestion_worker` consumes `instagram-ingestion-queue` and marks the job `EXTRACTING`
2. `InstagramApifyResolver.resolve()` strips any sentinel from the URL, classifies the content type, then for Reels/IGTV invokes `_resolve_reel_via_ytdlp(...)` first
3. yt-dlp runs without cookies; on success the resolver picks the best audio stream via `resolve_direct_media_url(info)` and returns a `ResolvedMedia` with `audio_url` populated
4. The worker hands the URL to the Deepgram queue with `deepgram_mode="pull_with_push_fallback"` (Instagram CDN sometimes blocks Deepgram pull, so the worker falls back to push automatically)

Ref: `instagram_apify_resolver.py::InstagramApifyResolver.resolve`, `instagram_apify_resolver.py::_resolve_reel_via_ytdlp`, `utils/ytdlp_helpers.py::resolve_direct_media_url`, `instagram_ingestion_worker.py::process_instagram_message`

### Fallback chain

| Step | Trigger condition | Action |
|---|---|---|
| 1 (primary) | yt-dlp extracts a usable audio stream | Hand off to Deepgram via the `enqueue_deepgram_transcription` helper with `deepgram_mode="pull_with_push_fallback"` |
| 2 | yt-dlp raises with an Instagram login-wall / rate-limit / restricted-content error (`_looks_like_ig_ip_blocked_error`), or any other yt-dlp failure | Catch as internal `_InstagramYtdlpBlocked`, fall back to the Apify Reel Scraper path |
| 3 (Apify fallback) | yt-dlp blocked OR sentinel forces it | `apify~instagram-reel-scraper` (configurable via `APIFY_INSTAGRAM_REEL_ACTOR_ID`) with input `{"username": [<url>], "resultsLimit": 1}` returns reel metadata. Resolver picks `audioUrl` (preferred) or `videoUrl` (fallback) and emits a `ResolvedMedia` with `audio_url` populated |
| 4 (Deepgram handoff) | Either primary or Apify produced an `audio_url` | `enqueue_deepgram_transcription(..., deepgram_mode="pull_with_push_fallback", source_platform="instagram")` |

The yt-dlp "blocked" detector is intentionally permissive — any `DownloadError` or unexpected exception is treated as a soft block so the Apify branch always gets a chance. This mirrors the deliberate simplification: Instagram from Lambda is hostile enough that paying for Apify on uncertain failures is cheaper than triaging dozens of error phrasings.

E2E test seam: a sentinel query param `__e2e_force_ip_block__=1` in the submitted URL skips yt-dlp entirely and routes straight to the Apify branch. Same convention as the TikTok worker — the helper lives in `utils/ingestion_sentinels.py::strip_e2e_force_ip_block_sentinel`.

Ref: `instagram_apify_resolver.py::_looks_like_ig_ip_blocked_error`, `instagram_apify_resolver.py::_resolve_reel`, `utils/ingestion_sentinels.py`

### Terminal failure mode

- `InstagramIngestionError` codes (raised by the worker):
  - `unsupported_content` (`apify_non_retryable:*` from resolver, neither yt-dlp nor Apify produced an `audio_url`)
  - `provider_error` (`apify_retryable:*` from resolver after retries exhausted, or unexpected exception)
  - `invalid_message` (missing job_id / normalized_url / job not found)
- After max retries (`INSTAGRAM_WORKER_MAX_RETRIES`, default 3), the job is marked failed (`error_step="instagram_ingestion"`) and a failure event is published

Ref: `instagram_ingestion_worker.py::InstagramIngestionError`, `instagram_ingestion_worker.py::process_message`

### Downstream dependencies

- yt-dlp or Apify produced an `audio_url`: `deepgram-transcription-queue` (`pull_with_push_fallback`, then Deepgram publishes the completion event)
- All terminal errors: `EPISODE_COMPLETED_EVENTS_QUEUE` env var, default queue `episode-completed-events` (failure event)

---

## Instagram Post

**Source type**: `instagram-post`
**Worker file**: same `instagram_ingestion_worker.py` worker, distinct branch in `InstagramApifyResolver`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| Apify Instagram Post Scraper | `apify~instagram-post-scraper` (configurable via `APIFY_INSTAGRAM_POST_ACTOR_ID`) | Image URLs, caption, comments, post type (single / carousel / video-post) | `APIFY_INSTAGRAM_API_TOKEN`, `APIFY_INSTAGRAM_POST_ACTOR_ID` (+ shared `APIFY_TIMEOUT_*`) |

URL classification scans every path segment for a known indicator (`reel`, `p`, `tv`) so both `/p/<id>/` and `/<username>/p/<id>/` shapes resolve to the same content type.

Workflow split inside the resolver:
- **URL path `/p/...` (image post or carousel)** → returns `MediaType.IMAGE_POST` payload (image URLs + caption). The orchestrator's `IMAGE_POST` branch enqueues to `instagram-image-queue` for OCR/vision processing (out of scope of the V1 transcription pipeline).
- **URL path `/p/...` containing video** → currently treated as `IMAGE_POST` by the post scraper (the V1 pipeline does not split video posts from image posts; video posts surface only via `/reel/...` URLs).

Ref: `instagram_apify_resolver.py::_detect_instagram_content_type`, `instagram_apify_resolver.py::_resolve_post`, `orchestrators.py` (`MediaType.IMAGE_POST` branch)

### Fallback chain

No fallback — failure is terminal. Image posts dispatched to `instagram-image-queue` are processed by the image worker pipeline (not covered here).

### Terminal failure mode

Image-post failures surface from the post-scraper actor (auth, quota, content-type rejection) and are reported as `unsupported_content` / `provider_error` (same `InstagramIngestionError` taxonomy as Reels).

### Downstream dependencies

- Image posts → `instagram-image-queue` (OCR/vision pipeline, not covered here)
- Errors → `EPISODE_COMPLETED_EVENTS_QUEUE` env var, default queue `episode-completed-events` (failure event)

---

## TikTok

**Source type**: `tiktok`
**Worker file**: `media_summarizer/workers/tiktok_ingestion_worker.py`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| yt-dlp | `yt_dlp.YoutubeDL` with `writesubtitles=True`, `subtitleslangs=["all"]` | Native subtitle text (VTT / SRT / JSON) from TikTok CDN | `TIKTOK_INGESTION_QUEUE`, `YTDLP_TIMEOUT_SECONDS`, `TIKTOK_SUBTITLE_FETCH_TIMEOUT_SECONDS`, `TIKTOK_WORKER_MAX_RETRIES` (rate limiter via `tiktok_limiter`) |

Workflow:
1. `tiktok_ingestion_worker` consumes `tiktok-ingestion-queue` and marks the job `EXTRACTING`
2. Strip the `__e2e_force_ip_block__` sentinel via `strip_e2e_force_ip_block_sentinel(...)` (skips yt-dlp and goes straight to Apify when present)
3. Acquire a rate-limit slot via `tiktok_limiter.acquire_tiktok_slot()`
4. Run `yt_dlp.YoutubeDL.extract_info(url, download=False)` with subtitle options
5. Collect `requested_subtitles` + `subtitles` candidates, fetch and parse the best-priority one
6. Upload transcript to S3 as `{job_id}.txt`

Ref: `tiktok_ingestion_worker.py::_extract_tiktok_info`, `tiktok_ingestion_worker.py::_fetch_native_subtitles`, `tiktok_ingestion_worker.py::_parse_caption_payload`, `utils/ingestion_sentinels.py::strip_e2e_force_ip_block_sentinel`

### Fallback chain

| Step | Trigger condition | Action |
|---|---|---|
| 1 | yt-dlp raises with TikTok status `10204` / `"IP address is blocked"` (`_looks_like_ip_blocked_error`), OR sentinel forces it | Apify TikTok Transcript actor (`APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID`, default `scrape-creators~best-tiktok-transcripts-scraper`) via `_fetch_apify_tiktok_dataset()` — POST `{"videos": [<url>]}` to `run-sync-get-dataset-items`, parse the WEBVTT `transcript` field via `_parse_timed_text_payload`, upload as native transcript (`strategy_used="apify_native_transcript"`) |
| 2 | yt-dlp succeeded but `NativeSubtitlesUnavailable` (no captions on the video) | Resolve direct media URL from yt-dlp `info` via `resolve_direct_media_url`, hand off via `enqueue_deepgram_transcription` with `deepgram_mode="pull_with_push_fallback"` (`strategy_used` from `_build_fallback_extraction_metadata`) |

When the Apify actor returns `success=false` or no transcript, the job fails terminally — the new actor does not expose a media URL, so there is no chained Deepgram path from the IP-block branch.

The IP-block matcher accepts both the legacy `10204` token and the modern phrasings (`ip address is blocked`, `ip block`, `geo block`). It does NOT match geo restrictions, deleted videos, rate limits, or generic yt-dlp errors — those propagate as terminal `extractor_failed` / `unsupported_content`.

E2E test seam: a sentinel query param `__e2e_force_ip_block__=1` forces the Apify branch. The shared helper lives in `utils/ingestion_sentinels.py`.

Apify call uses dedicated credentials: `APIFY_TIKTOK_API_TOKEN` (token) and `APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID` (actor). The actor ID separator is `~`, not `/` (Apify Console UI shows `/`, but the API requires `~`).

Ref: `tiktok_ingestion_worker.py::process_tiktok_message`, `tiktok_ingestion_worker.py::_fetch_apify_tiktok_dataset`, `tiktok_ingestion_worker.py::_extract_apify_transcript_text`, `tiktok_ingestion_worker.py::_looks_like_ip_blocked_error`, `utils/ytdlp_helpers.py::resolve_direct_media_url`

### Terminal failure mode

- `TikTokIngestionError` after max retries (`TIKTOK_WORKER_MAX_RETRIES`, default 3)
- Non-retryable codes: `unsupported_content` (private/deleted/live), `apify_actor_failed` with details `apify_no_transcript` (actor ran but returned nothing usable), `apify_actor_failed` with `apify_client_error:*` (actor schema rejection)
- Retryable codes: `rate_limited`, `extractor_failed`, `apify_actor_failed` with `apify_network_error:*` / `apify_server_error:*`

Ref: `tiktok_ingestion_worker.py::_mark_job_failed`, `tiktok_ingestion_worker.py::TikTokIngestionError`

### Downstream dependencies

- Native subtitle success: `EPISODE_COMPLETION_EVENTS_QUEUE` env var, default `episode-completion-events` (inline)
- Apify transcript fallback success: `EPISODE_COMPLETION_EVENTS_QUEUE` (inline)
- yt-dlp succeeded + no captions: `deepgram-transcription-queue` (`pull_with_push_fallback`, then Deepgram publishes the completion event)

---

## X (Twitter)

**Source type**: `x`
**Worker file**: `media_summarizer/workers/x_ingestion_worker.py`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| X API v2 | `GET /tweets/{tweet_id}` with `tweet.fields=...,note_tweet` and `expansions=author_id` | Tweet text (preferring `note_tweet.text` for long-form), author username/name | `X_API_BEARER_TOKEN`, `X_API_BASE_URL`, `X_API_TIMEOUT_SECONDS`, `X_INGESTION_QUEUE`, `X_WORKER_MAX_RETRIES` |

Workflow:
1. Receive message with pre-extracted `tweet_id` (set by `XPostResolver` upstream)
2. Mark job `EXTRACTING` (post task-175)
3. Call X API v2 lookup endpoint, prefer `note_tweet.text` then fall back to `data.text`
4. Upload text to S3 as `{job_id}.txt`
5. Set `podcast_title = "X - @<username>"`, `episode_title` = first line truncated to 120 chars

Ref: `x_ingestion_worker.py::_lookup_post`, `x_ingestion_worker.py::process_x_message`

### Fallback chain

No fallback — failure is terminal. Single provider (X API v2). Video tweets are not handled in V1 (only text content is extracted).

### Terminal failure mode

- `XIngestionError` after max retries (`X_WORKER_MAX_RETRIES`, default 3)
- Non-retryable codes: `x_lookup_not_found` (404), `x_lookup_auth_failed` (401), `x_lookup_forbidden` (403), `x_lookup_credits_depleted` (402), `x_lookup_empty`, `x_lookup_invalid_payload`
- Retryable codes: `x_lookup_timeout`, `x_lookup_failed` (5xx / transport), `x_lookup_rate_limited` (429)

Ref: `x_ingestion_worker.py::_mark_job_failed`, `x_ingestion_worker.py::XIngestionError`

### Downstream dependencies

Publishes to `EPISODE_COMPLETED_EVENTS_QUEUE`. Never enqueues to Deepgram.

---

## Document

**Source type**: `document`
**Worker file**: `media_summarizer/workers/document_parsing/worker.py`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| LlamaParse (cloud API) | `LlamaParseResolver` via `https://api.cloud.llamaindex.ai/api/parsing` | Structured markdown from PDF / DOCX / PPTX / XLSX / images (with OCR) | `LLAMAPARSE_API_KEY`, `LLAMAPARSE_TIMEOUT_SECONDS`, `LLAMAPARSE_POLL_INTERVAL`, `LLAMAPARSE_MAX_POLLS`, `DOCUMENT_BUCKET`, `TRANSCRIPT_BUCKET`, `DOCUMENT_PARSING_QUEUE`, `DOCUMENT_PARSING_VISIBILITY_TIMEOUT` |

Workflow:
1. Download document from `DOCUMENT_BUCKET` (S3) to a temp file
2. Detect format from file extension via `DocumentFormat.from_extension()`
3. Mark job `EXTRACTING` (post task-175 — historically `mark_transcribing`)
4. Upload to LlamaParse, poll for job completion, retrieve markdown result
5. Upload markdown to `TRANSCRIPT_BUCKET` as `{job_id}.md`

E2E test seam: Upload a file with a filename starting with `__e2e_force_llamaparse_failure__` (e.g. `__e2e_force_llamaparse_failure__sample.pdf`) to trigger a simulated rate-limit error in `LlamaParseResolver.parse`, exercising the fallback in E2E tests. This approach avoids Lambda env-var propagation delays and requires no IAM permissions.

Ref: `document_parsing/worker.py::parse_document_with_fallback`, `infrastructure/resolvers/llamaparse_resolver.py::LlamaParseResolver.parse`

### Fallback chain

| Step | Trigger condition | Action |
|---|---|---|
| 1 | LlamaParse returns ANY `ParseError` (rate limit, timeout, API error, auth error, network error) | Fall back to Unstructured API |

Ref: `document_parsing/worker.py::parse_document_with_fallback` (lines 92–152)

**Fallback provider:**

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| Unstructured API (cloud) | `UnstructuredResolver` via `https://api.unstructuredapp.io/general/v0/general` | Structured elements rendered to markdown | `UNSTRUCTURED_API_KEY`, `UNSTRUCTURED_API_URL`, `UNSTRUCTURED_TIMEOUT_SECONDS` |

Ref: `infrastructure/resolvers/unstructured_resolver.py::UnstructuredResolver`

### Terminal failure mode

- Both LlamaParse and Unstructured fail → `ParseError` with combined message (`provider="llamaparse+unstructured"`)
- Mark job failed (`error_step="document_parsing"`)
- Worker raises `RuntimeError` to trigger SQS retry / DLQ
- After max retries (3): job stays failed

Ref: `document_parsing/worker.py::process_document_parsing_message` (lines 230–235)

### Downstream dependencies

- `EPISODE_COMPLETED_EVENTS_QUEUE` (success event with `provider` set to the resolver that succeeded)
- `SEARCH_INDEXING_QUEUE` (best-effort search index update)

---

## Audio (direct URL / upload)

**Source type**: `audio`
**Worker files**:
- `POST /api/media/ingest-url` with `.mp3`/`.m4a`/etc. → `media_summarizer/api/endpoints/media.py:355` enqueues to `deepgram-transcription-queue` directly
- `POST /api/media/upload-audio` (file upload) → S3 staging then enqueue to Deepgram with a pre-signed URL
- `POST /api/v1/podcasts/submit` (user-pasted audio URL) → `media_summarizer/api/endpoints/podcasts.py:255` enqueues to Deepgram
- All consume `media_summarizer/workers/transcription/deepgram_worker.py`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| Deepgram | `nova-3` model via `https://api.deepgram.com/v1/listen` | Full transcript text | `DEEPGRAM_API_KEY`, `DEEPGRAM_API_URL`, `DEEPGRAM_MODEL`, `DEEPGRAM_TIMEOUT_SECONDS`, `DEEPGRAM_TRANSCRIPTION_QUEUE`, `AUDIO_BUCKET`, `TRANSCRIPT_BUCKET` |

Two input modes:
- **Pull mode** (`audio_url`): Deepgram fetches the audio URL itself (`call_deepgram_api`)
- **Push mode** (`audio_s3_key` or downloaded bytes): worker downloads, POSTs raw bytes (`call_deepgram_api_from_bytes`)

Workflow:
1. Worker reads `audio_url` and `audio_s3_key` from the message (and falls back to job state if missing)
2. Reads explicit `deepgram_mode` from the message body, validates against `VALID_DEEPGRAM_MODES = ("pull", "push", "pull_with_push_fallback")`
3. Marks job `TRANSCRIBING`
4. If `audio_s3_key` present → always push (download from S3, post bytes)
5. Else dispatch on `deepgram_mode` (see [Deepgram Modes](#cross-cutting-deepgram-modes))
6. Upload transcript to S3 as `{job_id}.txt`, publish success event with minutes-used computed from `audio_duration_seconds`

Ref: `transcription/deepgram_worker.py::process_deepgram_message`, `transcription/deepgram_worker.py::call_deepgram_api`, `transcription/deepgram_worker.py::call_deepgram_api_from_bytes`

### Fallback chain

Built into Deepgram mode dispatch (only `pull_with_push_fallback` falls back automatically; `pull` and `push` modes do not).

### Terminal failure mode

- `NonRetryableDeepgramError`: immediately publishes failure event (no retry)
  - Causes: empty API key, invalid `audio_url`, RSS/feed URL passed by mistake, empty transcript, HTTP 400/401/403/404/415/422, `RemoteContentError` when producer declared `pull` mode (producer misrouted)
- `RetryableDeepgramError` after max retries (3): publishes failure event
  - Causes: HTTP 429 / 5xx, timeout, transport error
- Test flag: `FORCE_DEEPGRAM_PUSH_MODE=1` simulates a `RemoteContentError` on `pull_with_push_fallback` to exercise the push fallback in E2E

Ref: `transcription/deepgram_worker.py::NonRetryableDeepgramError`, `transcription/deepgram_worker.py::RetryableDeepgramError`, `transcription/deepgram_worker.py::RemoteContentError`

### Downstream dependencies

Publishes to `EPISODE_COMPLETED_EVENTS_QUEUE` (terminates inline with success/failure event).

---

## RSS Feed Polling

**Source type**: feed-derived items (audio enclosure or article link)
**Worker file**: `media_summarizer/workers/rss_feed_poll_worker.py`

The RSS poll worker is the only producer that bypasses the URL classifier — it knows the item type from the feed metadata and routes directly:

| Item type | Target queue | `deepgram_mode` |
|---|---|---|
| Audio enclosure (`item_type=audio` + `audio_url`) | `deepgram-transcription-queue` | `pull` |
| Article (`item_type=article` or no audio URL) | `article-extraction-queue` | n/a |

Self-scheduling: the worker re-enqueues a poll trigger every `RSS_POLL_INTERVAL_SECONDS` (default 3600s, capped at the SQS max delay of 900s per message).

Ref: `rss_feed_poll_worker.py::_route_item_to_pipeline`, `rss_feed_poll_worker.py::_schedule_next_poll`

---

## Cross-cutting: Deepgram Modes

Since task-158, each producer worker / endpoint declares an explicit `deepgram_mode` in the SQS message body sent to `deepgram-transcription-queue`. This eliminates wasted pull-attempt timeouts for sources where Deepgram cannot fetch audio directly (CDN IP-blocking).

The `media_summarizer/utils/deepgram_dispatch.py` helper centralises the SQS payload construction. All workers that hand off to Deepgram should call `enqueue_deepgram_transcription(...)` rather than building the message body inline — the helper enforces the canonical schema (`job_id`, `audio_url`, `deepgram_mode`, `source_platform`, ...) and prevents drift.

### Mode definitions

| Mode | Behavior |
|---|---|
| `pull` | Deepgram fetches the URL itself. A `REMOTE_CONTENT_ERROR` from Deepgram fails loudly (producer misrouted). |
| `push` | Worker downloads audio bytes, POSTs them to Deepgram. Required for CDNs that block Deepgram IPs. |
| `pull_with_push_fallback` | Try pull first; on `RemoteContentError` fall back to push. |

### Producer-to-mode mapping

| Producer worker / call site | `deepgram_mode` | Source |
|---|---|---|
| YouTube ingestion worker (yt-dlp succeeded, no subtitles found) | `push` | `youtube_ingestion_worker.py` |
| TikTok ingestion worker (yt-dlp succeeded, no native captions) | `pull_with_push_fallback` | `tiktok_ingestion_worker.py` (via `enqueue_deepgram_transcription`) |
| Instagram ingestion worker (yt-dlp or Apify produced an `audio_url`) | `pull_with_push_fallback` | `instagram_ingestion_worker.py` (via `enqueue_deepgram_transcription`) |
| Orchestrator: `audio_s3_key` present (staged audio) | `pull` | `orchestrators.py` (`audio_s3_key` branch) |
| Orchestrator: `SOCIAL_VIDEO` with `audio_url` (legacy direct path) | `push` | `orchestrators.py` (`SOCIAL_VIDEO` branch) |
| Orchestrator: generic `audio_url` fallback | `pull_with_push_fallback` | `orchestrators.py` (generic audio_url branch) |
| PodcastIndex resolution worker | `pull` | `podcastindex_resolution_worker.py` |
| RSS feed poll worker (audio item) | `pull` | `rss_feed_poll_worker.py` |
| `POST /api/v1/podcasts/submit` (user-pasted audio URL) | `pull_with_push_fallback` | `api/endpoints/podcasts.py` |
| `POST /api/media/ingest-url` (audio source platform) | `pull_with_push_fallback` | `api/endpoints/media.py` |
| `POST /api/media/upload-audio` (S3 pre-signed URL) | `pull` | `api/endpoints/media.py` |

### Backward compatibility

Messages with no `deepgram_mode` field default to `pull` and trigger a `WARNING` log (`transcription.missing_deepgram_mode`) to flag missed call sites.

Ref: `transcription/deepgram_worker.py::VALID_DEEPGRAM_MODES`, `transcription/deepgram_worker.py::process_deepgram_message`, `utils/deepgram_dispatch.py::enqueue_deepgram_transcription`

### Known drift: completion-events queue name

Two env-var names exist in the codebase for what is logically the same downstream queue: `EPISODE_COMPLETION_EVENTS_QUEUE` (default queue `episode-completion-events`, used by TikTok / YouTube / PodcastIndex workers) and `EPISODE_COMPLETED_EVENTS_QUEUE` (default queue `episode-completed-events`, used by Article / Instagram / X / Document / Deepgram workers). In each environment one of the two values is set so that all producers actually publish to the same SQS queue, but the inconsistency is real and should be unified in a future cleanup task.

---

## Decision Tree: URL Classification and Routing

The `RuleBasedUrlClassifier` in `media_summarizer/core/media_ingestion/adapters/classifiers.py` deterministically routes every ingested URL to the appropriate queue.

### Classification table

| Host pattern | Path condition | MediaFamily | SourcePlatform | resolver_key | Target queue |
|---|---|---|---|---|---|
| `open.spotify.com` | `/episode/*` or `/show/*` | PODCAST | SPOTIFY | `podcast.default` | `podcastindex-resolution-queue` |
| `podcasts.apple.com` | contains `podcast` segment | PODCAST | APPLE_PODCASTS | `podcast.default` | `podcastindex-resolution-queue` |
| `*.deezer.com` | `/show/*` or `/episode/*` | PODCAST | DEEZER | `podcast.default` | `podcastindex-resolution-queue` |
| `*.rss`, `*.xml`, `feeds.*`, `rss.*`, path with `feed` segment | feed-like | PODCAST | RSS | `podcast.default` | `podcastindex-resolution-queue` |
| `youtube.com`, `youtu.be`, `m.*`, `music.*` | `/watch?v=`, `/shorts/`, `/live/`, `/embed/` | YOUTUBE | YOUTUBE | `youtube.default` | `youtube-ingestion-queue` |
| `instagram.com` | `/reel/*`, `/p/*`, `/tv/*` | SOCIAL_VIDEO | INSTAGRAM | `instagram.default` | `instagram-ingestion-queue` (Reel/video) or `instagram-image-queue` (image post, via orchestrator) |
| `x.com`, `twitter.com` | `/{user}/status/{id}`, `/i/status/{id}`, `/i/web/status/{id}` | ARTICLE | X | `x.default` | `x-ingestion-queue` |
| `tiktok.com`, `vm.tiktok.com` | `/@user/video/*` or `/t/*` | SOCIAL_VIDEO | TIKTOK | `tiktok.default` | `tiktok-ingestion-queue` |
| any | path ends with `.mp3/.m4a/.aac/.ogg/.wav/.flac/.opus` | AUDIO | DIRECT_URL | `audio.default` | `deepgram-transcription-queue` |
| any (catch-all) | anything else | ARTICLE | WEB | `article.default` | `article-extraction-queue` |

Ref: `classifiers.py::RuleBasedUrlClassifier.classify`

### ASCII routing diagram

```
                          +-------------------+
                          |  POST /api/media  |
                          |  ingest-url       |
                          +--------+----------+
                                   |
                          +--------v----------+
                          | URL Normalization |
                          +--------+----------+
                                   |
                          +--------v----------+
                          | RuleBasedUrl      |
                          | Classifier        |
                          +--------+----------+
                                   |
   +----------+-----------+--------+----------+--------+--------+----------+
   |          |           |                   |        |        |          |
   v          v           v                   v        v        v          v
[PODCAST] [YOUTUBE]  [INSTAGRAM]            [X]    [TIKTOK]  [AUDIO]   [ARTICLE]
   |          |           |                   |        |        |          |
   v          v           v                   v        v        v          v
podcast-   youtube-   instagram-           x-ingest tiktok-  deepgram-  article-
index-     ingest-    ingest-              -queue   ingest-  transcr-   extract-
queue      queue      queue                         queue    queue      queue
   |          |           |                   |        |        |          |
   v          v           v                   v        v        v          v
[RSS 2.0   [yt-dlp    [yt-dlp →            [X API  [yt-dlp     [Deepgram [Trafilatura]
 short-     native;    Apify Reel           v2]     native;      pull /
 circuit    Apify on   Scraper →                   Apify on      push /
 OR         IP block;  audio_url →                 IP block;     pull_with_
 Deepgram   Deepgram   Deepgram                    Apify         push_
 pull]      push if    pull_with_                  WEBVTT;       fallback]
            no subs]   push_fallback]              yt-dlp→
                                                   Deepgram
                                                   pull_with_
                                                   push_fallback
                                                   if no captions]
```

---

## References

### Source code paths

| Symbol | Path |
|---|---|
| `RuleBasedUrlClassifier` | `media_summarizer/core/media_ingestion/adapters/classifiers.py` |
| `ProcessingJobSubmissionOrchestrator` | `media_summarizer/core/media_ingestion/adapters/orchestrators.py` |
| `PodcastResolver` / `ArticleResolver` / `YouTubeResolver` / `XPostResolver` / `TikTokResolver` / `AudioResolver` / `InstagramResolver` | `media_summarizer/core/media_ingestion/adapters/resolvers.py` |
| `InstagramApifyResolver` | `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py` |
| `LlamaParseResolver` | `media_summarizer/infrastructure/resolvers/llamaparse_resolver.py` |
| `UnstructuredResolver` | `media_summarizer/infrastructure/resolvers/unstructured_resolver.py` |
| `SpotifyPodcastPlatformResolver` / `ApplePodcastsPlatformResolver` / `DeezerPodcastPlatformResolver` / `RssPodcastPlatformResolver` | `media_summarizer/workers/podcast_platform_resolvers.py` |
| `article_extraction_worker` | `media_summarizer/workers/article_extraction_worker.py` |
| `youtube_ingestion_worker` | `media_summarizer/workers/youtube_ingestion_worker.py` |
| `tiktok_ingestion_worker` | `media_summarizer/workers/tiktok_ingestion_worker.py` |
| `instagram_ingestion_worker` | `media_summarizer/workers/instagram_ingestion_worker.py` |
| `x_ingestion_worker` | `media_summarizer/workers/x_ingestion_worker.py` |
| `deepgram_worker` | `media_summarizer/workers/transcription/deepgram_worker.py` |
| `document_parsing/worker` | `media_summarizer/workers/document_parsing/worker.py` |
| `podcastindex_resolution_worker` | `media_summarizer/workers/podcastindex_resolution_worker.py` |
| `rss_feed_poll_worker` | `media_summarizer/workers/rss_feed_poll_worker.py` |
| `rss_transcript` (utility, wired via `podcastindex_resolution_worker._try_rss_transcript_short_circuit`) | `media_summarizer/utils/rss_transcript.py` |
| `tiktok_limiter` | `media_summarizer/utils/tiktok_limiter.py` |
| `ytdlp_helpers` (shared subtitle + media-URL helpers used by YouTube/TikTok/Instagram resolvers) | `media_summarizer/utils/ytdlp_helpers.py` |
| `deepgram_dispatch` (canonical SQS payload builder for Deepgram producers) | `media_summarizer/utils/deepgram_dispatch.py` |
| `ingestion_sentinels` (per-request E2E test seam for forcing the IP-block branch) | `media_summarizer/utils/ingestion_sentinels.py` |

### Artifact generation (unified worker — task-195)

All artifact generation (flashcards, notes, quiz, summary_short, summary_detailed) is handled by a single unified worker consuming one SQS queue (`artifact-generator-queue`). The worker dispatches to per-kind generators via a registry keyed on `MediaArtifactType`.

| Component | Path |
|---|---|
| Unified worker (shared S3 download, LLM call, retries, validation, status transitions) | `media_summarizer/workers/artifact_generator/worker.py` |
| Generator registry | `media_summarizer/workers/artifact_generator/generators/__init__.py` |
| FlashcardsGenerator (prompt + pydantic schema + structured outputs) | `media_summarizer/workers/artifact_generator/generators/flashcards.py` |
| NotesGenerator (prompt + pydantic schema) | `media_summarizer/workers/artifact_generator/generators/notes.py` |
| QuizGenerator (prompt + pydantic schema + structured outputs) | `media_summarizer/workers/artifact_generator/generators/quiz.py` |
| SummaryShortGenerator (prompt + pydantic schema) | `media_summarizer/workers/artifact_generator/generators/summary_short.py` |
| SummaryDetailedGenerator (prompt + pydantic schema) | `media_summarizer/workers/artifact_generator/generators/summary_detailed.py` |

**Models per artifact kind** (validated by task-72 benchmark):
- `flashcards`: `gpt-5.4-nano-2026-03-17`
- `notes`: `gpt-4o-mini-2024-07-18`
- `quiz`: `gpt-5.4-nano-2026-03-17`
- `summary_short`: `gpt-5-nano-2025-08-07`
- `summary_detailed`: `gpt-5.4-nano-2026-03-17`

**Queue**: `artifact-generator-queue` (single queue for all 5 kinds, `visibility_timeout_seconds=1800`, `maxReceiveCount=3`, DLQ: `artifact-generator-dlq`)

**Producer**: `artifact_service.get_artifact_queue()` returns `artifact-generator-queue` for all `MediaArtifactType` values. Messages include `artifact_type` in the body to route to the correct generator.

### Benchmark / decision READMEs

| Task | Topic | Path |
|---|---|---|
| task-90 | Document parsing provider selection (LlamaParse → Unstructured) | `docs/research/task-90-document-parser-benchmark/README.md` |
| task-158 | Deepgram explicit mode routing | (no research README — direct implementation) |
| task-175 | JobStatus vocabulary refactor (drop `RSS_RESOLVING` / `DOWNLOADING`, introduce `EXTRACTING`, drop progress percentage) | `backlog/tasks/task-175 - ...md` |
| task-184 | LlamaParse fallback test seam — replace Lambda env-var toggle with per-request filename sentinel | `backlog/tasks/task-184 - ...md` |
| task-185 | TikTok IP-block fallback test seam — sentinel URL + migration to Apify TikTok transcript actor | `backlog/tasks/task-185 - ...md` |

### Domain models

| Model | Path |
|---|---|
| `JobStatus` enum | `media_summarizer/core/models/processing_job.py` |
| `SourcePlatform` enum | `media_summarizer/core/media_ingestion/domain.py` |
| `MediaFamily` enum | `media_summarizer/core/media_ingestion/domain.py` |
| `MediaType` enum (incl. `IMAGE_POST`) | `media_summarizer/core/media_ingestion/domain.py` |
| `ClassifiedUrl` | `media_summarizer/core/media_ingestion/domain.py` |
| `DocumentFormat` | `media_summarizer/core/ports/document_parser.py` |
| `ParseErrorCode` | `media_summarizer/core/ports/document_parser.py` |
| `PodcastResolverErrorCode` | `media_summarizer/core/media_ingestion/adapters/podcast_resolver_foundation.py` |
