# Ingestion Workers and Providers Reference

Authoritative reference for the ingestion pipeline. Lists each source type's
primary extraction path, fallback chain, terminal failure behavior, and
downstream hand-off.

Last verified against codebase: 2026-06-10.

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
| yt-dlp | `yt_dlp.YoutubeDL` with `writesubtitles=True`, `subtitleslangs=["en", "en-US", "auto"]` | Native subtitle text (VTT / SRT / JSON) from YouTube CDN | `YOUTUBE_INGESTION_QUEUE`, `YTDLP_TIMEOUT_SECONDS`, `TRANSCRIPT_BUCKET` |

Workflow:
1. Extract `video_id` from the normalized URL
2. Run `yt-dlp.extract_info(url, download=False)` with subtitle options (line 219)
3. Collect `requested_subtitles` + `subtitles` candidates via `_fetch_native_subtitles()` (line 295)
4. If subtitles found: fetch, parse, upload to S3 as `{job_id}.txt`, publish success event with `strategy_used="native_subtitles"`

Ref: `youtube_ingestion_worker.py::_extract_youtube_info` (line 213), `youtube_ingestion_worker.py::_fetch_native_subtitles` (line 295)

### Fallback chain

| Step | Trigger condition | Action |
|---|---|---|
| 1 (primary) | yt-dlp extraction succeeds AND subtitles present | Fetch and parse native subtitles, upload transcript to S3 (`strategy_used="native_subtitles"`) |
| 2 | yt-dlp raises with YouTube IP-block / login-wall error (`_is_ip_blocked_error`) | Apify YouTube Transcript actor (`APIFY_YOUTUBE_TRANSCRIPT_ACTOR`) via `_fetch_apify_transcript()` — synchronous run, read dataset items (`strategy_used="apify_transcript"`) |
| 3 | yt-dlp succeeded but no subtitles found (NativeSubtitlesUnavailable) | Resolve audio URL from yt-dlp info dict, enqueue to `deepgram-transcription-queue` with `deepgram_mode="push"` (`strategy_used="deepgram_via_ytdlp_url"`) |

The IP-block detection (`_is_ip_blocked_error`, line 151) is intentionally narrow — it does NOT match geo restrictions, deleted videos, rate limits, or generic yt-dlp errors.

Ref: `youtube_ingestion_worker.py::process_youtube_message` (line 696), `youtube_ingestion_worker.py::_fetch_apify_transcript` (line 334), `youtube_ingestion_worker.py::_is_ip_blocked_error` (line 151)

### Terminal failure mode

- `YouTubeIngestionError` after max retries (`YOUTUBE_WORKER_MAX_RETRIES`, default 3)
- Mark job failed (`error_step="youtube_ingestion"`)
- Publish `episode_completion_status(status=failure)`
- Non-retryable codes: `youtube_unavailable` (deleted/private/age-restricted), `youtube_age_restricted`, `youtube_geo_restricted`, `youtube_apify_failed` (Apify also failed after IP-block)
- Retryable codes: `apify_timeout`, `apify_quota_exceeded` (HTTP 429 from Apify), `youtube_timeout` (yt-dlp timeout)

Ref: `youtube_ingestion_worker.py::YouTubeIngestionError`

### Downstream dependencies

- Native subtitles / Apify transcript success: `EPISODE_COMPLETED_EVENTS_QUEUE` (inline)
- yt-dlp succeeded + no captions: `deepgram-transcription-queue` (push mode, then Deepgram publishes the completion event)

---

## Instagram Reel

**Source type**: `instagram-reel`
**Worker file**: `media_summarizer/workers/instagram_ingestion_worker.py`
**Resolver**: `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py::InstagramApifyResolver`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| Apify Video Subtitle Extractor | `khadinakbar~video-subtitle-extractor` (configurable via `APIFY_INSTAGRAM_REEL_ACTOR_ID`) | Native subtitle/caption track for Reels/IGTV (Whisper fallback DISABLED at the actor level) | `APIFY_INSTAGRAM_API_TOKEN`, `APIFY_INSTAGRAM_REEL_ACTOR_ID`, `APIFY_TIMEOUT_SECONDS`, `APIFY_POLL_INTERVAL_SECONDS`, `APIFY_MAX_POLLS`, `INSTAGRAM_TRANSCRIPT_MIN_LENGTH`, `INSTAGRAM_INGESTION_QUEUE` |

Workflow:
1. `instagram_ingestion_worker` consumes `instagram-ingestion-queue`
2. Marks job `EXTRACTING` (post task-175 — historically `mark_downloading`)
3. `InstagramApifyResolver` invokes the subtitle extractor with `useWhisperFallback=false` and `preferredLanguages=["auto"]`
4. If the actor returns a transcript ≥ `INSTAGRAM_TRANSCRIPT_MIN_LENGTH` characters → upload to S3 as `{job_id}.txt`, publish success event with `transcript_source="apify_native"`

Ref: `instagram_ingestion_worker.py::process_instagram_message` (Path A: `if resolved.raw_text`), `instagram_apify_resolver.py::InstagramApifyResolver.resolve`

### Fallback chain

No automatic Deepgram fallback. The resolver explicitly disables Whisper inside the actor and the worker fails when the actor returns no usable transcript:

| Condition | Behavior |
|---|---|
| Actor returns `raw_text` ≥ min length | Path A success — transcript uploaded directly, no Deepgram |
| Actor returns no `raw_text` (silent reel, music-only, captions absent) | `NonRetryableProviderResolutionError` → worker fails with `unsupported_content` |

Note: a separate orchestrator branch (`orchestrators.py:414`, `MediaFamily.SOCIAL_VIDEO with audio_url`) routes Instagram-style messages to Deepgram in push mode. That branch is **not exercised by the queue-first Instagram pipeline** today — it's reachable only when a non-Instagram caller (e.g. shared-content ingestion) populates `audio_url` directly. The live Instagram path stops at the Apify subtitle extractor.

### Terminal failure mode

- `InstagramIngestionError` codes:
  - `unsupported_content` (`apify_non_retryable:*` from resolver, no transcript or image payload)
  - `provider_error` (`apify_retryable:*` from resolver after retries exhausted, or unexpected exception)
  - `invalid_message` (missing job_id / normalized_url / job not found)
- After max retries (`INSTAGRAM_WORKER_MAX_RETRIES`, default 3), the job is marked failed (`error_step="instagram_ingestion"`) and a failure event is published

Ref: `instagram_ingestion_worker.py::InstagramIngestionError`, `instagram_ingestion_worker.py::process_message`

### Downstream dependencies

Publishes to `EPISODE_COMPLETED_EVENTS_QUEUE`. No Deepgram, no separate transcription queue.

---

## Instagram Post

**Source type**: `instagram-post`
**Worker file**: same `instagram_ingestion_worker.py` worker, distinct branch in `InstagramApifyResolver`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| Apify Instagram Post Scraper | `apify~instagram-post-scraper` (configurable via `APIFY_INSTAGRAM_POST_ACTOR_ID`) | Image URLs, caption, comments, post type (single / carousel / video-post) | `APIFY_INSTAGRAM_API_TOKEN`, `APIFY_INSTAGRAM_POST_ACTOR_ID` (+ shared `APIFY_TIMEOUT_*`) |

Workflow split inside the resolver:
- **URL path `/p/...` with no video** → returns `MediaType.IMAGE_POST` payload (image URLs + caption). The orchestrator (`orchestrators.py:374`) then enqueues to `instagram-image-queue` for OCR/vision processing (out of scope of the V1 transcription pipeline).
- **URL path `/p/...` with video** → falls back to the subtitle-extractor flow described in the Reel section above.

Ref: `instagram_apify_resolver.py::_detect_instagram_content_type`, `orchestrators.py:374` (`MediaType.IMAGE_POST` branch)

### Fallback chain

For videos: same as Instagram Reel (no Deepgram fallback). For image posts: dispatched to `instagram-image-queue` — image worker pipeline is not part of this document.

### Terminal failure mode

Same as Instagram Reel for video paths. Image-post failures surface from the post-scraper actor (auth, quota, content-type rejection).

### Downstream dependencies

- Video posts → `EPISODE_COMPLETED_EVENTS_QUEUE` (success) or job failure
- Image posts → `instagram-image-queue` (OCR/vision pipeline, not covered here)

---

## TikTok

**Source type**: `tiktok`
**Worker file**: `media_summarizer/workers/tiktok_ingestion_worker.py`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| yt-dlp | `yt_dlp.YoutubeDL` with `writesubtitles=True`, `subtitleslangs=["all"]` | Native subtitle text (VTT / SRT / JSON) from TikTok CDN | `TIKTOK_INGESTION_QUEUE`, `YTDLP_TIMEOUT_SECONDS`, `TIKTOK_SUBTITLE_FETCH_TIMEOUT_SECONDS`, `TIKTOK_WORKER_MAX_RETRIES` (rate limiter via `tiktok_limiter`) |

Workflow:
1. Marks job `EXTRACTING` (post task-175 — historically `mark_downloading`)
2. Acquire rate-limit slot via `tiktok_limiter.acquire_tiktok_slot()`
3. Run `yt-dlp.extract_info(url, download=False)` with subtitle options
4. Collect `requested_subtitles` + `subtitles` candidates, fetch and parse the best-priority one
5. Upload transcript to S3 as `{job_id}.txt`

Ref: `tiktok_ingestion_worker.py::_extract_tiktok_info`, `tiktok_ingestion_worker.py::_fetch_native_subtitles`, `tiktok_ingestion_worker.py::_parse_caption_payload`

### Fallback chain

| Step | Trigger condition | Action |
|---|---|---|
| 1 | yt-dlp raises with TikTok status `10204` / `"IP address is blocked"` (Lambda-IP block) | Apify TikTok Transcript actor (`APIFY_TIKTOK_TRANSCRIPT_ACTOR_ID`) — start run, poll, read dataset, upload as native transcript (`strategy_used="apify_transcript"`) |
| 1b | Apify ran but returned no transcript (empty dataset or transcript too short) | Resolve media URL from Apify response, enqueue to `deepgram-transcription-queue` with `deepgram_mode="push"` (`strategy_used="deepgram_via_apify_tiktok_url"`) |
| 2 | yt-dlp succeeded but `NativeSubtitlesUnavailable` (no captions on the video) | Resolve direct media URL from yt-dlp `info`, enqueue to `deepgram-transcription-queue` with `deepgram_mode="push"` (`strategy_used="direct_media_url_fallback"`) |

The IP-block detection is intentionally narrow (`_is_ip_blocked_error`) — it does NOT match geo restrictions, deleted videos, rate limits, or generic yt-dlp errors, those propagate as-is.

Ref: `tiktok_ingestion_worker.py::process_tiktok_message` (lines 1098–1205), `tiktok_ingestion_worker.py::_fetch_apify_tiktok_dataset` (line 604), `tiktok_ingestion_worker.py::_resolve_direct_media_url`

### Terminal failure mode

- `TikTokIngestionError` after max retries (`TIKTOK_WORKER_MAX_RETRIES`, default 3)
- Non-retryable codes: `unsupported_content` (private/deleted/live), `no_direct_media_url`, `tiktok_ip_blocked_unrecoverable` (yt-dlp IP-blocked AND Apify also failed), `apify_actor_failed` (with `retryable=False` for explicit actor failure)
- Retryable codes: `rate_limited`, `extractor_failed`, `apify_timeout`, `apify_quota_exceeded`

Ref: `tiktok_ingestion_worker.py::_mark_job_failed`, `tiktok_ingestion_worker.py::TikTokIngestionError`

### Downstream dependencies

- Native subtitle success: `EPISODE_COMPLETED_EVENTS_QUEUE` (inline)
- Apify transcript fallback success: `EPISODE_COMPLETED_EVENTS_QUEUE` (inline)
- Apify ran + no transcript → Deepgram on Apify media URL: `deepgram-transcription-queue` (push mode, `strategy_used="deepgram_via_apify_tiktok_url"`)
- yt-dlp succeeded + no captions: `deepgram-transcription-queue` (push mode, then Deepgram publishes the completion event)

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

### Mode definitions

| Mode | Behavior |
|---|---|
| `pull` | Deepgram fetches the URL itself. A `REMOTE_CONTENT_ERROR` from Deepgram fails loudly (producer misrouted). |
| `push` | Worker downloads audio bytes, POSTs them to Deepgram. Required for CDNs that block Deepgram IPs. |
| `pull_with_push_fallback` | Try pull first; on `RemoteContentError` fall back to push. |

### Producer-to-mode mapping

| Producer worker / call site | `deepgram_mode` | Source |
|---|---|---|
| YouTube ingestion worker (yt-dlp succeeded, no subtitles found) | `push` | `youtube_ingestion_worker.py:783` |
| TikTok ingestion worker (yt-dlp succeeded, no native captions) | `push` | `tiktok_ingestion_worker.py:1195` |
| TikTok ingestion worker (Apify ran, no transcript → Deepgram on Apify URL) | `push` | `tiktok_ingestion_worker.py:1212` |
| Instagram orchestrator branch (`SOCIAL_VIDEO` with `audio_url`) | `push` | `orchestrators.py:435` |
| Orchestrator: `audio_s3_key` present (staged audio) | `pull` | `orchestrators.py:357` |
| Orchestrator: generic `audio_url` fallback | `pull_with_push_fallback` | `orchestrators.py:465` |
| PodcastIndex resolution worker | `pull` | `podcastindex_resolution_worker.py:186` |
| RSS feed poll worker (audio item) | `pull` | `rss_feed_poll_worker.py:85` |
| `POST /api/v1/podcasts/submit` (user-pasted audio URL) | `pull_with_push_fallback` | `api/endpoints/podcasts.py:263` |
| `POST /api/media/ingest-url` (audio source platform) | `pull_with_push_fallback` | `api/endpoints/media.py:358` |
| `POST /api/media/upload-audio` (S3 pre-signed URL) | `pull` | `api/endpoints/media.py:705` |

### Backward compatibility

Messages with no `deepgram_mode` field default to `pull` and trigger a `WARNING` log (`transcription.missing_deepgram_mode`) to flag missed call sites.

Ref: `transcription/deepgram_worker.py::VALID_DEEPGRAM_MODES`, `transcription/deepgram_worker.py::process_deepgram_message`

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
[RSS 2.0   [yt-dlp    [Apify subtitle      [X API  [yt-dlp     [Deepgram [Trafilatura]
 short-     native;    extractor;           v2]     native;      pull /
 circuit    Apify on   no fallback;               Apify on       push /
 OR         IP block;  fail if no                 IP block;      pull_with_
 Deepgram   Deepgram   transcript]                Apify→         push_
 pull]      push if                               Deepgram       fallback]
            no subs]                              push if no
                                                  transcript;
                                                  yt-dlp→
                                                  Deepgram
                                                  push if no
                                                  captions]
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

### Benchmark / decision READMEs

| Task | Topic | Path |
|---|---|---|
| task-90 | Document parsing provider selection (LlamaParse → Unstructured) | `docs/research/task-90-document-parser-benchmark/README.md` |
| task-158 | Deepgram explicit mode routing | (no research README — direct implementation) |
| task-175 | JobStatus vocabulary refactor (drop `RSS_RESOLVING` / `DOWNLOADING`, introduce `EXTRACTING`, drop progress percentage) | `backlog/tasks/task-175 - ...md` |

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
