# Media Ingestion Core Architecture

This document defines the architecture boundaries for the hexagonal media ingestion core introduced in `task-20`.

## Goals

- isolate ingestion use-cases from provider-specific logic
- route resolver selection through one extension point
- allow adding resolvers without changing core orchestration code

## Package layout

`media_summarizer/core/media_ingestion/`

- `domain.py`: core domain models and lifecycle enums
- `ports.py`: abstract ports used by the use-case
- `registry.py`: central resolver registry (single extension point)
- `router.py`: reusable router that combines classifier + registry lookup
- `use_cases.py`: ingestion application flow (`IngestUrlUseCase`)
- `errors.py`: core error taxonomy
- `adapters/`: default classifier/resolvers/orchestrator implementations
- `wiring.py`: default composition helpers

## Dependency rules (must keep)

Allowed:
1. `use_cases.py` depends on `domain`, `ports`, `router`, and shared identity utility.
2. `adapters/*` depend on `ports` and `domain`.
3. `router.py` depends on `ports` + `registry` only.
4. `wiring.py` composes adapters + router + use-case.

Not allowed:
1. `use_cases.py` importing FastAPI, endpoint modules, or request/response framework classes.
2. `registry.py` importing provider-specific SDKs.
3. Resolver-specific code inside `use_cases.py`.

## Core ingestion flow

1. canonicalize URL and derive `media_key`
2. **quota enforcement check** via `quota_enforcer.check_submission_allowed` (hard caps, daily rate limits, max audio duration, cost monitoring block)
3. route URL through `ResolverRouter` (classification + resolver lookup)
4. resolve URL through `ContentResolverPort`
5. submit persistence/pipeline through `SubmissionOrchestratorPort`
6. **record submission** via `quota_enforcer.record_submission` (atomically increment monthly/daily usage counters)

## Quota enforcement (task-110)

All submission entry points (`POST /api/media/ingest-url`, `POST /api/media/upload`, `POST /api/v1/podcasts/submit`, and `media_submission.submit_media_for_user`) call the quota enforcement engine before creating a job.

The engine checks in order:
1. Tier-level audio gating (text_only tier refuses all audio structurally)
2. Max audio duration per import (60 min for Mix, 90 min for Audio-Heavy)
3. Monthly hard caps per media type (audio_minutes, articles, documents, youtube)
4. Daily rate limits per media type
5. Cost monitoring hard block (estimated monthly cost exceeds threshold)

On denial, a stable error code is returned (`tier_quota_exceeded`, `daily_rate_limit`, `audio_too_long`, `cost_hard_block`) that the mobile app can pattern-match for localized display.

Usage counters are stored in DynamoDB tables `user_usage_monthly` (PK: user_id, SK: YYYY-MM) and `user_usage_daily` (PK: user_id, SK: YYYY-MM-DD) with atomic ADD operations.

## URL classification and routing policy (task-21)

Routing is deterministic and based on explicit scheme/host/path rules.

Stable errors:
- `InvalidUrlError`: malformed or host-missing URL input
- `UnsupportedUrlError`: valid URL but unsupported scheme/host/format

Representative examples:

| URL | Result |
| --- | --- |
| `https://open.spotify.com/episode/123` | `podcast.default` (`podcast`, `spotify`) |
| `https://podcasts.apple.com/fr/podcast/foo/id1?i=2` | `podcast.default` (`podcast`, `apple_podcasts`) |
| `https://example.org/feed.xml` | `podcast.default` (`podcast`, `rss`) |
| `https://youtube.com/watch?v=abc123` | `youtube.default` (`youtube`, `youtube`) |
| `https://instagram.com/reel/XYZ` | `instagram.default` (`social_video`, `instagram`) |
| `https://cdn.example.com/audio/episode.mp3` | `audio.default` (`audio`, `direct_url`) |
| `https://example.com/blog/my-article` | `article.default` (`article`, `web`) |
| `ftp://example.com/file.mp3` | `UnsupportedUrlError` (unsupported scheme) |
| `https://localhost/private.mp3` | `UnsupportedUrlError` (unsupported host) |
| `https://youtube.com/watch` | `UnsupportedUrlError` (unsupported YouTube URL format) |
| `https://open.spotify.com/artist/123` | `UnsupportedUrlError` (unsupported Spotify URL format) |
| `not-a-url` | `InvalidUrlError` (invalid URL input) |

## URL safety hardening policy (task-47)

The default classifier enforces safety checks before resolver routing.

Validation hardening:
- reject empty and overly long URLs (max 2048 chars)
- reject malformed URLs and invalid host patterns
- reject URLs embedding user credentials (`https://user:pass@host/...`)
- reject unsupported schemes and forbidden local/private/link-local hosts

Domain blocking policy:
- deny hosts that match blocked domain suffixes
- allow explicit safety overrides through allowlist suffixes
- keep client-facing failures stable with user-safe errors (`UnsupportedUrlError`)

Governance and operations knobs:
- `INGEST_URL_BLOCKED_DOMAINS`: comma-separated blocked domain suffixes
- `INGEST_URL_ALLOWED_DOMAINS`: comma-separated allowlist suffixes (override deny)
- built-in blocked defaults exist and can be augmented via env vars

Logging and audit visibility:
- every safety gate decision is logged as `ingestion_url_safety_decision`
- log fields include `decision` (`allow|deny`), `reason`, `scheme`, and `host`
- governance details are documented in `docs/URL_SAFETY_POLICY.md`

## Single extension point for resolvers

Resolvers are registered by key in the registry and selected through `ResolverRouter`.

Current default keys:
- `podcast.default`
- `article.default`
- `youtube.default`
- `instagram.default`
- `tiktok.default`
- `social.default`
- `audio.default`

Adding a resolver does not require changing `IngestUrlUseCase`.

## Podcast resolver foundation (task-24)

Podcast platform resolvers share one internal contract in:
- `core/media_ingestion/adapters/podcast_resolver_foundation.py`

Core building blocks:
- `PodcastPlatformResolver`: single async interface for Spotify/Apple/Deezer/RSS implementations
- `PodcastPlatformResolverRegistry`: deterministic lookup by `SourcePlatform`
- `normalize_podcast_source_url(...)`: centralized podcast URL normalization and identifier extraction
- `PodcastResolutionOutcome`: stable resolver outcome envelope (`resolved | pending | failed`)
- `PodcastResolverErrorCode`: stable internal error taxonomy for podcast resolution semantics
- `build_podcast_resolution_metadata(...)`: standardized metadata payload propagated to downstream runtime

Normalized outcome semantics:
- `resolved`: `audio_url` is available and can be sent directly to transcription
- `pending`: URL accepted, resolution deferred (queue-first flow stays active)
- `failed`: deterministic platform/lookup failure with stable error code and client-safe message

Default ingestion behavior:
- `PodcastResolver` (`podcast.default`) always uses this shared foundation.
- It keeps canonical API behavior unchanged (no new HTTP error codes) and emits standardized metadata:
  - `podcast_resolution_status`
  - `podcast_resolution_error_code`
  - `podcast_resolution_client_message`
  - `podcast_resolution_retryable`
  - `podcast_source_url`
  - `podcast_url_identifiers`

Worker behavior:
- `podcastindex_resolution_worker` resolves through platform resolvers using the same interface.
- RSS path is implemented in a dedicated resolver.
- Spotify is implemented in worker scope (`task-25`) with:
  - Spotify episode metadata extraction from canonical `open.spotify.com/episode/{id}` URLs
  - PodcastIndex feed search + episode matching (`core/services/podcast_matching.py`)
  - stable outcome contract (`resolved` with `audio_url`, or deterministic `failed` codes)
- Apple Podcasts is implemented in worker scope (`task-26`) with:
  - canonical Apple episode URL validation (`?i=` required for episode resolution)
  - PodcastIndex feed discovery by `itunesId` (`show_id`) with search fallback
  - stable outcome contract (`resolved` with `audio_url`, or deterministic `failed` codes)
- Deezer is implemented in worker scope (`task-27`) with:
  - canonical Deezer episode URL validation (`/episode/{id}`; locale-prefixed paths are normalized)
  - Deezer episode metadata lookup (`api.deezer.com/episode/{id}`) then PodcastIndex feed search + episode matching
  - stable outcome contract (`resolved` with `audio_url`, or deterministic `failed` codes)
- RSS direct resolver is implemented in worker scope (`task-28`) with:
  - primary direct RSS/Atom parsing to resolve enclosure `audio_url` without requiring PodcastIndex
  - stable deterministic failure codes when feed parsing fails or no episode enclosure is present
  - opportunistic PodcastIndex enrichment (`feed_id` + metadata) when available, without blocking resolution

## How to add a new resolver

1. Implement `ContentResolverPort` in `core/media_ingestion/adapters/` or another adapter package.
2. Provide a stable `key` value.
3. Register it via `build_default_resolver_registry(extra_resolvers=[...])` or explicit registry wiring.
4. Ensure classifier rules emit the resolver key for matching URLs.
5. Reuse `ResolverRouter` from `build_default_resolver_router(...)` in entrypoints/use-cases.

Only steps 1-5 should be needed; `use_cases.py` and `registry.py` should remain unchanged.

### Add a podcast platform resolver

1. Implement `PodcastPlatformResolver` for the target `SourcePlatform`.
2. Reuse `normalize_podcast_source_url(...)` and consume identifiers from `PodcastUrlDescriptor`.
3. Return only `PodcastResolutionOutcome` (`resolved/pending/failed`) with stable `PodcastResolverErrorCode`.
4. Register resolver in platform registry composition (API deferred registry and/or worker registry).
5. Keep client-facing semantics stable by exposing details through resolver metadata, not HTTP contract changes.
6. Do not modify `IngestUrlUseCase`; podcast routing remains `podcast.default` through existing registry/router.

## Transitional orchestration adapter

`ProcessingJobSubmissionOrchestrator` is intentionally transitional:
- it reuses existing persistence/queue/idempotence primitives
- it keeps orchestration behind `SubmissionOrchestratorPort`
- future tasks can replace this adapter without changing use-case logic

## Article connector runtime path (task-29)

`article.default` now follows a queue-first extraction path:

1. URL is classified as `article` and routed to `ArticleResolver`.
2. Resolver returns normalized media payload with extraction mode `queued_worker`.
3. `ProcessingJobSubmissionOrchestrator` enqueues `article-extraction-queue`.
4. `article_extraction_worker` fetches HTML, extracts clean text, uploads transcript to S3 (`{job_id}.txt`), and persists `extraction_metadata` on `ProcessingJob`.
5. Worker publishes unified completion events (`episode_completion_status`) for success/failure, preserving shared completion fan-out behavior.

## YouTube connector runtime path (task-30)

`youtube.default` now follows a queue-first transcript strategy:

1. URL is classified as `youtube` and routed to `YouTubeResolver`.
2. Resolver returns normalized media payload with `extraction_mode=queued_worker` and `transcript_strategy=manual_auto_audio`.
3. `ProcessingJobSubmissionOrchestrator` enqueues `youtube-ingestion-queue`.
4. `youtube_ingestion_worker` extracts the canonical `video_id`, attempts native transcripts in order `manual -> auto`, and uploads successful native transcript text to S3 (`{job_id}.txt`).
5. When no native transcript is available, the worker resolves a remote audio stream URL with `yt-dlp` and reuses `deepgram-transcription-queue` without downloading media locally.
6. Worker metadata keeps the chosen strategy explicit through `transcription_metadata.provider` (`native_transcript` or `deepgram`) and `extraction_metadata.selected_strategy` (`native_transcript` or `audio_fallback`).

## Instagram connector runtime path (task-31, task-108, task-274)

`instagram.default` follows the same queue-first shape as TikTok. Provider work
happens in the worker, never in the HTTP request:

1. URL is classified as `social_video` and routed to `InstagramResolver`, which
   only classifies — it calls no provider. Resolving inline could not work: the
   API request has a hard 30 s ceiling (API Gateway's HTTP API integration
   timeout, not configurable) while yt-dlp plus an Apify run measured at 63-100 s
   needs far more, so every Instagram save timed out with nothing persisted.
2. `ProcessingJobSubmissionOrchestrator` marks the job `extracting` and enqueues
   `instagram-ingestion-queue`.
3. `instagram_ingestion_worker` runs `InstagramApifyResolver`, which detects the
   content type from the URL path (`/reel/` -> reel, `/p/` -> post, `/tv/` -> igtv).
4. For **Reels/IGTV**: yt-dlp first (free); on an Instagram IP block, the Apify
   Reel Scraper returns `audioUrl` (preferred) or `videoUrl`. The worker hands
   the URL to `deepgram-transcription-queue` in `push` mode with
   `quota_source_platform="instagram"`.
5. For **Image posts** (single or carousel): the Apify Post Scraper returns
   `displayUrl`, `images`, `childPosts` and the resolver a `MediaType.IMAGE_POST`
   payload. The worker fails the job with `unsupported_content` — no OCR/vision
   pipeline exists.
6. **Caption**: extracted from the `caption` field of every scraper response,
   persisted in resolved metadata and forwarded to Deepgram. It is also what the
   title is derived from (task-266), which is why the title reaches the library
   row only once the worker has run.
7. The Apify poll loop bounds itself by the invocation's remaining time
   (`utils/invocation_budget.py`), so resolution cannot outlive the Lambda.

## TikTok connector runtime path (task-54)

`tiktok.default` now follows a queue-first extraction path:

1. URL is classified as `social_video` and routed to `TikTokResolver`.
2. Resolver returns normalized media payload with `resolution_mode=queued_worker` and TikTok-specific extractor metadata.
3. `ProcessingJobSubmissionOrchestrator` marks the job as `extracting` and enqueues `tiktok-ingestion-queue`.
4. `tiktok_ingestion_worker` attempts native subtitles via `yt-dlp` first and uploads successful native transcript text to S3 (`{job_id}.txt`).
5. When native subtitles are unavailable, the worker resolves a direct remote media URL and reuses `deepgram-transcription-queue` without downloading or uploading audio artifacts.
6. Worker metadata keeps the chosen strategy explicit through `transcription_metadata.provider` (`native_transcript` or `deepgram`) and `extraction_metadata.selected_strategy` (`native_subtitles` or `direct_media_url_fallback`).

`social.default` remains available only as a generic social-video resolver for non-share-first or future connector cases. The active share-first connectors use dedicated resolver keys (`instagram.default`, `tiktok.default`).

## Relationship to upcoming tasks

- `task-10`: implemented canonical endpoint `POST /api/media/ingest-url` on top of this use-case.
- `task-21`: implemented deterministic classifier policy + centralized reusable router.
- `task-22`: exposes canonical media status reads.
- `task-24+`: introduces platform resolvers while keeping use-case unchanged.
