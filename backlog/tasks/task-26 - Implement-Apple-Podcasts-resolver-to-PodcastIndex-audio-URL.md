---
id: task-26
title: Implement Apple Podcasts resolver to PodcastIndex audio URL
status: Done
assignee:
  - '@codex'
created_date: '2026-02-24 11:03'
updated_date: '2026-03-03 22:09'
labels: []
dependencies:
  - task-24
  - task-9
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement Apple Podcasts URL resolution to produce a valid audio URL through PodcastIndex mapping.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Apple Podcasts episode URLs resolve end-to-end to a valid audio URL.
- [x] #2 Resolver emits stable success/failure outcomes aligned with shared contract.
- [x] #3 Platform-specific edge cases are handled without breaking other podcast resolvers.
- [x] #4 Resolver integration is documented for ingestion routing.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1) Implement `ApplePodcastsPlatformResolver` in `media_summarizer/workers/podcast_platform_resolvers.py` on the shared `PodcastPlatformResolver` interface.
2) Resolve Apple metadata from canonical Apple podcast episode URLs (show/episode context) and keep deterministic validation for malformed/unsupported Apple podcast URLs.
3) Map Apple shows to PodcastIndex feeds with priority on Apple `show_id` (`itunesId`) lookup, then fallback to PodcastIndex search by show title.
4) Resolve target episode/audio via PodcastIndex episodes list and shared matching helper (`core/services/podcast_matching.py`) while preserving stable `PodcastResolutionOutcome`/`PodcastResolverErrorCode` behavior.
5) Register Apple resolver in worker registry; keep Deezer placeholder unchanged for task-27.
6) Update architecture documentation to reflect Apple integration status and routing behavior.
7) Run non-destructive validation (AST/lint/runtime smoke scenarios) and close task-26 with AC updates in Backlog.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented `ApplePodcastsPlatformResolver` in `media_summarizer/workers/podcast_platform_resolvers.py` and registered it in `build_worker_podcast_platform_resolver_registry` in place of the Apple placeholder resolver.

Added Apple-to-PodcastIndex mapping path with deterministic flow: canonical Apple episode URL validation (`episode_id` required) -> Apple metadata extraction from public page/oEmbed -> PodcastIndex feed discovery by iTunes show ID (`show_id`) via new utility `get_podcast_by_itunes_id(...)` with title-search fallback -> episode/audio resolution with stable outcomes.

Introduced new PodcastIndex utility `get_podcast_by_itunes_id` in `media_summarizer/utils/podcast_index.py` using existing limiter/auth request stack and consistent error handling semantics.

Resolver emits stable shared contract outcomes (`resolved`, `failed`) with existing `PodcastResolverErrorCode` values (`invalid_platform_url`, `episode_not_found`, `audio_url_not_found`, `upstream_lookup_failed`) and preserves worker failure propagation format (`code=<podcast_error_code>`).

Documentation updated in `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` to mark Apple implementation status under worker behavior and keep Deezer as pending placeholder for task-27.

Validation performed (non-destructive): AST parse OK on touched Python modules; ruff check OK on `podcast_platform_resolvers.py`; runtime smoke tests confirmed Apple episode URL resolves to valid audio URL and deterministic failure codes remain stable for Apple show URL (`invalid_platform_url`) and Deezer placeholder (`platform_not_implemented`).
<!-- SECTION:NOTES:END -->
