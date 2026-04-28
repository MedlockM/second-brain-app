---
id: task-25
title: Implement Spotify podcast resolver to PodcastIndex audio URL
status: Done
assignee:
  - '@codex'
created_date: '2026-02-24 11:03'
updated_date: '2026-03-03 22:01'
labels: []
dependencies:
  - task-24
  - task-9
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement Spotify podcast URL resolution to produce a valid audio URL through PodcastIndex mapping.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Spotify episode URLs resolve end-to-end to a valid audio URL.
- [x] #2 Resolver emits stable success/failure outcomes aligned with shared contract.
- [x] #3 Platform-specific edge cases are handled without breaking other podcast resolvers.
- [x] #4 Resolver integration is documented for ingestion routing.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1) Implement a dedicated `SpotifyPodcastPlatformResolver` in `media_summarizer/workers/podcast_platform_resolvers.py` using the shared `PodcastPlatformResolver` contract.
2) Fetch Spotify episode metadata (episode title + show title) from public Spotify endpoints, with bounded retries and transient error detection compatible with worker policy.
3) Map Spotify metadata to PodcastIndex by searching candidate feeds, loading recent episodes for candidate feeds, and selecting the best match with shared `core/services/podcast_matching.py` helpers.
4) Return stable `PodcastResolutionOutcome` values for success and failures (`resolved` with audio_url, or `failed` with stable `PodcastResolverErrorCode`) without changing API HTTP contract.
5) Register Spotify resolver in `build_worker_podcast_platform_resolver_registry` while keeping Apple/Deezer placeholders unchanged.
6) Update architecture documentation for task-25 integration/routing notes and update backlog task notes + AC checkboxes once validation is complete.
7) Run non-destructive validation (AST parse/import checks for touched modules) and summarize residual risks.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented `SpotifyPodcastPlatformResolver` in `media_summarizer/workers/podcast_platform_resolvers.py` and wired it into `build_worker_podcast_platform_resolver_registry` in place of the Spotify placeholder resolver.

Resolver flow now performs: Spotify episode URL validation (`episode_id` required) -> public Spotify metadata extraction (oEmbed + HTML meta parsing for show/episode context) -> PodcastIndex feed search -> episode matching via `core/services/podcast_matching.py` -> `audio_url` resolution with stable `PodcastResolutionOutcome` semantics.

Stable failure taxonomy is preserved end-to-end with shared codes (`invalid_platform_url`, `episode_not_found`, `audio_url_not_found`, `upstream_lookup_failed`) and worker error propagation format (`code=<podcast_error_code>`) unchanged.

Documented Spotify integration in `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` under worker behavior for task-25, while keeping Apple/Deezer as `platform_not_implemented` placeholders for tasks 26/27.

Validation executed (non-destructive): AST parse OK on touched modules; runtime scenario checks with real Spotify episode URLs confirmed successful worker-level resolution to a valid `audio_url`; failure-path check confirmed deterministic `invalid_platform_url` for Spotify show URLs and `platform_not_implemented` unchanged for Apple resolver path.
<!-- SECTION:NOTES:END -->
