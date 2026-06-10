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
10. [Cross-cutting: Deepgram Modes](#cross-cutting-deepgram-modes)
11. [Decision Tree: URL Classification and Routing](#decision-tree-url-classification-and-routing)
12. [References](#references)

---

## Article

**Source type**: `article`  
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

Ref: `article_extraction_worker.py::_fetch_article_html`, `article_extraction_worker.py::_extract_clean_text`

### Fallback chain

No fallback -- failure is terminal.

### Terminal failure mode

- Mark `ProcessingJob` as failed (`error_step="article_extraction"`)
- Publish `episode_completion_status(status=failure)` to `EPISODE_COMPLETION_EVENTS_QUEUE`
- Error codes: `article_fetch_timeout`, `article_http_error`, `article_unsupported_content_type`, `article_extraction_empty`, `article_extraction_failed`

Ref: `article_extraction_worker.py::_mark_job_failed`, `article_extraction_worker.py::_ERROR_MESSAGES`

### Downstream dependencies

Publishes to `EPISODE_COMPLETION_EVENTS_QUEUE` (terminates inline with success event).

---

## Podcast

**Source type**: `podcast`  
**Worker file**: `media_summarizer/workers/podcastindex_resolution_worker.py` (resolution) + `media_summarizer/workers/download_worker.py` (audio download)

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| PodcastIndex API | Platform resolvers (Spotify, Apple, Deezer, RSS) | Audio enclosure URL from episode metadata | `PODCASTINDEX_API_KEY`, `PODCASTINDEX_API_SECRET`, `PODCASTINDEX_RESOLUTION_QUEUE` |
| Podcasting 2.0 RSS transcript | `<podcast:transcript>` tag | Pre-existing transcript text (SRT/VTT/TXT) | (none beyond download worker env) |

Workflow:
1. `podcastindex_resolution_worker` receives from `podcastindex-resolution-queue`
2. Dispatches to the appropriate platform resolver via `PodcastPlatformResolverRegistry`:
   - **Spotify**: oEmbed metadata + PodcastIndex feed search + episode title matching
   - **Apple Podcasts**: oEmbed metadata + PodcastIndex byitunesid lookup + episode matching
   - **Deezer**: Deezer public API metadata + PodcastIndex feed search + episode matching
   - **RSS**: Direct feed XML parsing + optional PodcastIndex enrichment
3. Resolves to an audio enclosure URL
4. Enqueues to `deepgram-transcription-queue`

Ref: `podcastindex_resolution_worker.py::_resolve_audio_url`, `podcast_platform_resolvers.py::SpotifyPodcastPlatformResolver`, `podcast_platform_resolvers.py::ApplePodcastsPlatformResolver`, `podcast_platform_resolvers.py::DeezerPodcastPlatformResolver`, `podcast_platform_resolvers.py::RssPodcastPlatformResolver`

### Fallback chain

| Step | Trigger condition | Action |
|---|---|---|
| 1 (download worker) | `feed_url` + `episode_guid` present in message | Attempt Podcasting 2.0 `<podcast:transcript>` extraction via `rss_transcript.fetch_rss_transcript()`. If found, skip audio download and Deepgram entirely. |
| 2 | RSS transcript absent or fetch fails | Download audio from enclosure URL, upload to S3, enqueue to `deepgram-transcription-queue` |

Ref: `download_worker.py::process_message` (lines 129-248), `media_summarizer/utils/rss_transcript.py`

### Terminal failure mode

- Platform resolver returns `PodcastResolutionOutcome.failed()` with non-retryable error code
- Audio download raises after SQS max retries -> publishes failure event to `EPISODE_COMPLETION_EVENTS_QUEUE`
- Error codes: `INVALID_PLATFORM_URL`, `EPISODE_NOT_FOUND`, `AUDIO_URL_NOT_FOUND`, `UPSTREAM_LOOKUP_FAILED`, `UNSUPPORTED_PLATFORM`

Ref: `podcast_platform_resolvers.py::PodcastResolverErrorCode` (via `podcast_resolver_foundation.py`)

### Downstream dependencies

Hands off to `deepgram-transcription-queue` (Deepgram worker processes audio transcription).

---

## YouTube

**Source type**: `youtube`  
**Worker file**: `media_summarizer/workers/youtube_ingestion_worker.py`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| youtube-transcript-api | `YouTubeTranscriptApi` | Native transcript (manual preferred, auto as second choice) | `YOUTUBE_INGESTION_QUEUE`, `YOUTUBE_TRANSCRIPT_TIMEOUT_SECONDS`, `TRANSCRIPT_BUCKET` |

Workflow:
1. Extract `video_id` from the normalized URL
2. Call `YouTubeTranscriptApi.list(video_id)` to enumerate available transcripts
3. Select: manual transcript preferred over auto-generated
4. Fetch and normalize transcript text (concatenate snippet lines)
5. Upload to S3 as `{job_id}.txt`
6. Publish success event

Ref: `youtube_ingestion_worker.py::_fetch_native_transcript`, `youtube_ingestion_worker.py::_select_transcript`

### Fallback chain

| Step | Trigger condition | Action |
|---|---|---|
| 1 | `NativeTranscriptUnavailable` raised (no transcript found, transcripts disabled, empty transcript) | Fall back to yt-dlp audio URL resolution |
| 2 | yt-dlp resolves a direct audio stream URL | Enqueue job to `deepgram-transcription-queue` with the audio URL |

Trigger exceptions for fallback: `NoTranscriptFound`, `TranscriptsDisabled`, empty native transcript.

Ref: `youtube_ingestion_worker.py::process_youtube_message` (line 624 catch block), `youtube_ingestion_worker.py::_resolve_audio_fallback`

### Terminal failure mode

- `YouTubeIngestionError` with `retryable=False` after max retries (3)
- Mark job failed (`error_step="youtube_ingestion"`)
- Publish `episode_completion_status(status=failure)`
- Non-retryable codes: `youtube_unavailable` (video deleted/private/age-restricted), `youtube_audio_fallback_failed` (no transcribable audio stream)

Ref: `youtube_ingestion_worker.py::_mark_job_failed`

### Downstream dependencies

- On native transcript success: publishes to `EPISODE_COMPLETION_EVENTS_QUEUE` (inline termination)
- On audio fallback: hands off to `deepgram-transcription-queue`

---

## Instagram Reel

**Source type**: `instagram-reel`  
**Worker file**: Resolved inline by `media_summarizer/core/media_ingestion/adapters/resolvers.py::InstagramResolver` + orchestrator routes to `deepgram-transcription-queue`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| GetInSaver API | `getinsaver.com/api/v1/download/instagram` (type=reel) | Direct video/audio download URL | `GETINSAVER_API_BASE_URL`, `GETINSAVER_API_KEY`, `GETINSAVER_TIMEOUT_SECONDS` |

Workflow:
1. `InstagramResolver.resolve()` calls `_resolve_instagram_download_url()` with `type=reel`
2. GetInSaver API returns a download URL for the reel video
3. Orchestrator enqueues to `deepgram-transcription-queue` with the resolved `audio_url`
4. Deepgram worker transcribes using **push mode** (downloads audio bytes, POSTs to Deepgram)

Ref: `resolvers.py::InstagramResolver`, `resolvers.py::_resolve_instagram_download_url`, `orchestrators.py` (line 312-345 social video branch)

### Fallback chain

No fallback -- failure is terminal. The GetInSaver API is the single provider.

Non-retryable conditions: image-only posts, unsupported content type, invalid payload.
Retryable conditions: transport errors, 401/403/429/5xx from provider.

Ref: `resolvers.py::_extract_instagram_download_url`, `resolvers.py::_resolve_instagram_download_url`

### Terminal failure mode

- `NonRetryableProviderResolutionError` or `RetryableProviderResolutionError` propagated up to the ingestion use case
- Job is marked failed at the orchestration layer

### Downstream dependencies

Hands off to `deepgram-transcription-queue` (push mode -- Deepgram worker downloads audio and pushes bytes).

---

## Instagram Post

**Source type**: `instagram-post`  
**Worker file**: Same as Instagram Reel -- `media_summarizer/core/media_ingestion/adapters/resolvers.py::InstagramResolver`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| GetInSaver API | `getinsaver.com/api/v1/download/instagram` (type=post) | Direct video/audio download URL | `GETINSAVER_API_BASE_URL`, `GETINSAVER_API_KEY`, `GETINSAVER_TIMEOUT_SECONDS` |

Workflow: identical to Instagram Reel except `type=post` is sent to the provider.

The resolver rejects image-only posts (`provider_media_type in {"image", "photo"}` triggers `NonRetryableProviderResolutionError`).

Ref: `resolvers.py::_instagram_content_type_from_url` (path `/p/` -> type `post`), `resolvers.py::_extract_instagram_download_url`

### Fallback chain

No fallback -- failure is terminal (same as Reel).

### Terminal failure mode

Same as Instagram Reel.

### Downstream dependencies

Hands off to `deepgram-transcription-queue` (push mode).

---

## TikTok

**Source type**: `tiktok`  
**Worker file**: `media_summarizer/workers/tiktok_ingestion_worker.py`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| yt-dlp | `yt_dlp.YoutubeDL` (with `writesubtitles=True`, `subtitleslangs=["all"]`) | Native subtitle text from TikTok CDN | `TIKTOK_INGESTION_QUEUE`, `YTDLP_TIMEOUT_SECONDS`, `TIKTOK_SUBTITLE_FETCH_TIMEOUT_SECONDS`, `TIKTOK_WORKER_MAX_RETRIES` |

Workflow:
1. Extract TikTok video ID from URL
2. Acquire rate-limit slot via `tiktok_limiter.acquire_tiktok_slot()`
3. Run `yt-dlp extract_info()` with subtitle options
4. Collect subtitle candidates from `requested_subtitles` and `subtitles` fields
5. Fetch and parse subtitles (VTT/SRT/JSON formats supported)
6. Upload transcript to S3 as `{job_id}.txt`

Ref: `tiktok_ingestion_worker.py::_extract_tiktok_info`, `tiktok_ingestion_worker.py::_fetch_native_subtitles`, `tiktok_ingestion_worker.py::_parse_caption_payload`

### Fallback chain

| Step | Trigger condition | Action |
|---|---|---|
| 1 | `NativeSubtitlesUnavailable` (no subtitles found in yt-dlp metadata, or all subtitle fetches fail) | Extract direct media URL from yt-dlp info dict |
| 2 | Direct media URL resolved | Enqueue to `deepgram-transcription-queue` with the audio URL (push mode) |

Ref: `tiktok_ingestion_worker.py::process_tiktok_message` (line 765 catch block), `tiktok_ingestion_worker.py::_resolve_direct_media_url`

### Terminal failure mode

- `TikTokIngestionError` after max retries (3)
- Mark job failed (`error_step="tiktok_ingestion"`)
- Publish `episode_completion_status(status=failure)`
- Non-retryable codes: `unsupported_content` (private/deleted/live), `no_direct_media_url` (no transcribable stream)
- Retryable codes: `rate_limited`, `extractor_failed` (timeout, transient yt-dlp error)

Ref: `tiktok_ingestion_worker.py::_mark_job_failed`, `tiktok_ingestion_worker.py::TikTokIngestionError`

### Downstream dependencies

- On native subtitle success: publishes to `EPISODE_COMPLETION_EVENTS_QUEUE` (inline termination)
- On direct media URL fallback: hands off to `deepgram-transcription-queue` (push mode)

---

## X (Twitter)

**Source type**: `x`  
**Worker file**: `media_summarizer/workers/x_ingestion_worker.py`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| X API v2 | `GET /tweets/{tweet_id}` with expansions | Tweet text content (including note_tweet long-form) | `X_API_BEARER_TOKEN`, `X_API_BASE_URL`, `X_API_TIMEOUT_SECONDS`, `X_INGESTION_QUEUE` |

Workflow:
1. Receive message with pre-extracted `tweet_id` (set by `XPostResolver`)
2. Call X API v2 tweet lookup with `tweet.fields` and `user.fields` expansions
3. Extract text from `note_tweet.text` (long-form) or `data.text` (standard)
4. Upload text to S3 as `{job_id}.txt`
5. Set `podcast_title` = "X - @username", `episode_title` = first line of text

Ref: `x_ingestion_worker.py::_lookup_post`, `x_ingestion_worker.py::process_x_message`

### Fallback chain

No fallback -- failure is terminal. Single provider (X API v2).

### Terminal failure mode

- Mark job failed (`error_step="x_ingestion"`)
- Publish `episode_completion_status(status=failure)`
- Non-retryable codes: `x_lookup_not_found` (404), `x_lookup_auth_failed` (401), `x_lookup_forbidden` (403), `x_lookup_credits_depleted` (402), `x_lookup_empty`, `x_lookup_invalid_payload`
- Retryable codes: `x_lookup_timeout`, `x_lookup_failed` (5xx), `x_lookup_rate_limited` (429)

Ref: `x_ingestion_worker.py::_mark_job_failed`, `x_ingestion_worker.py::XIngestionError`

### Downstream dependencies

Publishes to `EPISODE_COMPLETION_EVENTS_QUEUE` (terminates inline with success event).

---

## Document

**Source type**: `document`  
**Worker file**: `media_summarizer/workers/document_parsing/worker.py`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| LlamaParse (cloud API) | `LlamaParseResolver` via `https://api.cloud.llamaindex.ai/api/parsing` | Structured markdown from uploaded documents (PDF, DOCX, PPTX, XLSX, images w/ OCR) | `LLAMAPARSE_API_KEY`, `LLAMAPARSE_TIMEOUT_SECONDS`, `LLAMAPARSE_POLL_INTERVAL`, `LLAMAPARSE_MAX_POLLS` |

Workflow:
1. Download document from `DOCUMENT_BUCKET` (S3)
2. Detect format from file extension via `DocumentFormat.from_extension()`
3. Upload to LlamaParse, poll for job completion, retrieve markdown result
4. Upload markdown to `TRANSCRIPT_BUCKET` as `{job_id}.md`

Ref: `document_parsing/worker.py::parse_document_with_fallback`, `infrastructure/resolvers/llamaparse_resolver.py::LlamaParseResolver`

### Fallback chain

| Step | Trigger condition | Action |
|---|---|---|
| 1 | LlamaParse returns a `ParseError` (any error: rate limit, timeout, API error, auth error, network error) | Fall back to Unstructured API |

Ref: `document_parsing/worker.py::parse_document_with_fallback` (line 106-128)

**Fallback provider:**

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| Unstructured API (cloud) | `UnstructuredResolver` via `https://api.unstructuredapp.io/general/v0/general` | Structured elements converted to markdown | `UNSTRUCTURED_API_KEY`, `UNSTRUCTURED_API_URL`, `UNSTRUCTURED_TIMEOUT_SECONDS` |

Ref: `infrastructure/resolvers/unstructured_resolver.py::UnstructuredResolver`

### Terminal failure mode

- Both LlamaParse and Unstructured fail -> `ParseError` with combined message
- Mark job failed (`error_step="document_parsing"`)
- Raises `RuntimeError` which triggers retry/DLQ at the SQS level
- After max retries (3): job stays failed

Ref: `document_parsing/worker.py::process_document_parsing_message` (line 230-235)

### Downstream dependencies

- Publishes to `EPISODE_COMPLETION_EVENTS_QUEUE` (success event)
- Publishes to `SEARCH_INDEXING_QUEUE` (search index update)

---

## Audio (direct URL / upload)

**Source type**: `audio`  
**Worker files**:
- Direct audio URL from URL classification: routed via orchestrator to `deepgram-transcription-queue`
- Audio file upload (staged in S3): routed via orchestrator to `deepgram-transcription-queue`
- Podcast audio download: `media_summarizer/workers/download_worker.py`

### Primary path

| Provider/library | Identifier | Extracts | Key env vars |
|---|---|---|---|
| Deepgram | `nova-3` model via `https://api.deepgram.com/v1/listen` | Full transcript text from audio | `DEEPGRAM_API_KEY`, `DEEPGRAM_API_URL`, `DEEPGRAM_MODEL`, `DEEPGRAM_TIMEOUT_SECONDS`, `DEEPGRAM_TRANSCRIPTION_QUEUE` |

Two input modes:
- **Pull mode** (`audio_url`): Deepgram fetches audio from the given URL (`call_deepgram_api`)
- **Push mode** (`audio_s3_key` or downloaded bytes): Worker downloads audio, POSTs raw bytes to Deepgram (`call_deepgram_api_from_bytes`)

Workflow:
1. Deepgram worker receives from `deepgram-transcription-queue`
2. If `audio_url` is present: call Deepgram pre-recorded URL endpoint (pull mode)
3. Else if `audio_s3_key` is present: download from S3, POST bytes (push mode)
4. Parse transcript from Deepgram response (channels[0].alternatives[0].transcript)
5. Upload transcript to S3 as `{job_id}.txt`
6. Publish success event

Ref: `transcription/deepgram_worker.py::process_deepgram_message`, `transcription/deepgram_worker.py::call_deepgram_api`, `transcription/deepgram_worker.py::call_deepgram_api_from_bytes`

### Fallback chain (download worker path)

| Step | Trigger condition | Action |
|---|---|---|
| 1 | `feed_url` + `episode_guid` present | Attempt Podcasting 2.0 RSS transcript. If found, skip audio download entirely. |
| 2 | RSS transcript absent | Download audio from URL, upload to S3, enqueue to Deepgram |

Ref: `download_worker.py::process_message`

### Terminal failure mode

- `NonRetryableDeepgramError`: immediately publishes failure event (no retry)
  - Causes: empty API key, invalid audio URL, RSS/feed URL passed, empty transcript, HTTP 400/401/403/404/415/422
- `RetryableDeepgramError` after max retries (3): publishes failure event
  - Causes: HTTP 429 or 5xx, timeout, transport error
- Download worker: raises on download failure, relies on SQS retry/DLQ

Ref: `transcription/deepgram_worker.py::NonRetryableDeepgramError`, `transcription/deepgram_worker.py::RetryableDeepgramError`

### Downstream dependencies

Publishes to `EPISODE_COMPLETION_EVENTS_QUEUE` (terminates inline with success/failure event).

---

## Cross-cutting: Deepgram Modes

Since task-158, each producer worker declares an explicit `deepgram_mode` in the SQS
message body sent to `deepgram-transcription-queue`. This eliminates wasted pull-attempt
timeouts for sources where Deepgram cannot fetch audio directly (CDN IP-blocking).

### Mode definitions

| Mode | Behavior |
|---|---|
| `pull` | Deepgram fetches the URL itself. A 403 fails loudly (producer misrouted). |
| `push` | Worker downloads audio bytes, POSTs them to Deepgram. For CDNs that block Deepgram. |
| `pull_with_push_fallback` | Try pull first; on `RemoteContentError` fall back to push. |

### Producer-to-mode mapping

| Producer worker / call site | `deepgram_mode` |
|---|---|
| TikTok ingestion worker | `push` |
| Instagram (orchestrator social video path) | `push` |
| PodcastIndex resolution worker | `pull` |
| RSS feed poll worker | `pull` |
| Media submission service (podcast direct) | `pull` |
| Upload-audio endpoint (S3 pre-signed URL) | `pull` |
| Ingest-url endpoint (user-pasted `.mp3`) | `pull_with_push_fallback` |
| Podcasts/submit (user-pasted audio URL) | `pull_with_push_fallback` |
| Orchestrator: staged audio (S3 key present) | `pull` |
| Orchestrator: generic audio_url fallback | `pull_with_push_fallback` |

### Backward compatibility

Messages without `deepgram_mode` default to `pull` with a WARNING log to flag
missed call sites.

Ref: git commit `5977180` (task-158), `transcription/deepgram_worker.py::VALID_DEEPGRAM_MODES`

---

## Decision Tree: URL Classification and Routing

The `RuleBasedUrlClassifier` in `media_summarizer/core/media_ingestion/adapters/classifiers.py`
deterministically routes every ingested URL to the appropriate queue.

### Classification table

| Host pattern | Path condition | MediaFamily | SourcePlatform | resolver_key | Target queue |
|---|---|---|---|---|---|
| `open.spotify.com` | `/episode/*` or `/show/*` | PODCAST | SPOTIFY | `podcast.default` | `podcastindex-resolution-queue` |
| `podcasts.apple.com` | contains `podcast` segment | PODCAST | APPLE_PODCASTS | `podcast.default` | `podcastindex-resolution-queue` |
| `deezer.com` | `/show/*` or `/episode/*` | PODCAST | DEEZER | `podcast.default` | `podcastindex-resolution-queue` |
| `*.rss`, `*.xml`, `feeds.*`, `rss.*` | feed-like path/host | PODCAST | RSS | `podcast.default` | `podcastindex-resolution-queue` |
| `youtube.com`, `youtu.be` | `/watch?v=`, `/shorts/`, `/live/`, `/embed/` | YOUTUBE | YOUTUBE | `youtube.default` | `youtube-ingestion-queue` |
| `instagram.com` | `/reel/*`, `/p/*`, `/tv/*` | SOCIAL_VIDEO | INSTAGRAM | `instagram.default` | `deepgram-transcription-queue` (via resolver) |
| `x.com`, `twitter.com` | `/{user}/status/{id}` | ARTICLE | X | `x.default` | `x-ingestion-queue` |
| `tiktok.com`, `vm.tiktok.com` | `/@user/video/*` or `/t/*` | SOCIAL_VIDEO | TIKTOK | `tiktok.default` | `tiktok-ingestion-queue` |
| any | path ends with `.mp3/.m4a/.aac/.ogg/.wav/.flac/.opus` | AUDIO | DIRECT_URL | `audio.default` | `deepgram-transcription-queue` |
| any (fallback) | anything else | ARTICLE | WEB | `article.default` | `article-extraction-queue` |

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
         +------------+------+----+----+-------+--------+--------+
         |            |      |         |       |        |        |
         v            v      v         v       v        v        v
    [PODCAST]   [YOUTUBE] [INSTAGRAM] [X]  [TIKTOK]  [AUDIO] [ARTICLE]
         |            |      |         |       |        |        |
         v            v      v         v       v        v        v
  podcastindex   youtube  deepgram   x-ingest tiktok  deepgram  article
  -resolution    -ingest  -transcr   -queue   -ingest -transcr  -extract
  -queue         -queue   -queue              -queue  -queue    -queue
         |            |      |         |       |        |        |
         |            |      |         |       |        |        |
         v            v      v         v       v        v        v
   [Deepgram]   [Native] [Deepgram] [X API] [Native] [Deepgram] [Trafilatura]
                  or        push      v2     or push    pull/     extraction
                [Deepgram]                   [Deepgram] push
                 fallback                     fallback
```

---

## References

### Source code paths

| Symbol | Path |
|---|---|
| `RuleBasedUrlClassifier` | `media_summarizer/core/media_ingestion/adapters/classifiers.py` |
| `ProcessingJobSubmissionOrchestrator` | `media_summarizer/core/media_ingestion/adapters/orchestrators.py` |
| `PodcastResolver` | `media_summarizer/core/media_ingestion/adapters/resolvers.py` |
| `ArticleResolver` | `media_summarizer/core/media_ingestion/adapters/resolvers.py` |
| `YouTubeResolver` | `media_summarizer/core/media_ingestion/adapters/resolvers.py` |
| `InstagramResolver` | `media_summarizer/core/media_ingestion/adapters/resolvers.py` |
| `TikTokResolver` | `media_summarizer/core/media_ingestion/adapters/resolvers.py` |
| `XPostResolver` | `media_summarizer/core/media_ingestion/adapters/resolvers.py` |
| `AudioResolver` | `media_summarizer/core/media_ingestion/adapters/resolvers.py` |
| `SpotifyPodcastPlatformResolver` | `media_summarizer/workers/podcast_platform_resolvers.py` |
| `ApplePodcastsPlatformResolver` | `media_summarizer/workers/podcast_platform_resolvers.py` |
| `DeezerPodcastPlatformResolver` | `media_summarizer/workers/podcast_platform_resolvers.py` |
| `RssPodcastPlatformResolver` | `media_summarizer/workers/podcast_platform_resolvers.py` |
| `article_extraction_worker` | `media_summarizer/workers/article_extraction_worker.py` |
| `youtube_ingestion_worker` | `media_summarizer/workers/youtube_ingestion_worker.py` |
| `tiktok_ingestion_worker` | `media_summarizer/workers/tiktok_ingestion_worker.py` |
| `x_ingestion_worker` | `media_summarizer/workers/x_ingestion_worker.py` |
| `download_worker` | `media_summarizer/workers/download_worker.py` |
| `deepgram_worker` | `media_summarizer/workers/transcription/deepgram_worker.py` |
| `document_parsing worker` | `media_summarizer/workers/document_parsing/worker.py` |
| `LlamaParseResolver` | `media_summarizer/infrastructure/resolvers/llamaparse_resolver.py` |
| `UnstructuredResolver` | `media_summarizer/infrastructure/resolvers/unstructured_resolver.py` |
| `podcastindex_resolution_worker` | `media_summarizer/workers/podcastindex_resolution_worker.py` |
| `rss_feed_poll_worker` | `media_summarizer/workers/rss_feed_poll_worker.py` |
| `rss_transcript` | `media_summarizer/utils/rss_transcript.py` |
| `tiktok_limiter` | `media_summarizer/utils/tiktok_limiter.py` |

### Benchmark READMEs

| Task | Topic | Path |
|---|---|---|
| task-90 | Document parsing provider selection | `docs/research/task-90-document-parser-benchmark/README.md` |
| task-158 | Deepgram explicit mode routing (commit `5977180`) | (no research README -- direct implementation task) |

### Domain models

| Model | Path |
|---|---|
| `SourcePlatform` enum | `media_summarizer/core/media_ingestion/domain.py` |
| `MediaFamily` enum | `media_summarizer/core/media_ingestion/domain.py` |
| `ClassifiedUrl` | `media_summarizer/core/media_ingestion/domain.py` |
| `DocumentFormat` | `media_summarizer/core/ports/document_parser.py` |
| `ParseErrorCode` | `media_summarizer/core/ports/document_parser.py` |
