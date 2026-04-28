---
id: task-27
title: Implement Deezer podcast resolver to PodcastIndex audio URL
status: Done
assignee:
  - '@codex'
created_date: '2026-02-24 11:03'
updated_date: '2026-03-03 22:16'
labels: []
dependencies:
  - task-24
  - task-9
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement Deezer podcast URL resolution to produce a valid audio URL through PodcastIndex mapping.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Deezer episode URLs resolve end-to-end to a valid audio URL.
- [x] #2 Resolver emits stable success/failure outcomes aligned with shared contract.
- [x] #3 Platform-specific edge cases are handled without breaking other podcast resolvers.
- [x] #4 Resolver integration is documented for ingestion routing.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Implement `DeezerPodcastPlatformResolver` in worker platform resolvers with stable outcome/error contract.
2. Resolve Deezer episode metadata from `api.deezer.com/episode/{id}` and map to PodcastIndex via show/episode title candidates.
3. Replace Deezer placeholder resolver in worker registry and export symbol.
4. Harden Deezer URL normalization to support locale-prefixed paths (`/fr/episode/{id}` / `/en/show/{id}`) while keeping canonical output.
5. Update architecture documentation to mark Deezer resolver as implemented for task-27.
6. Run static validation (AST parse + ruff on touched files) and targeted smoke checks for success/failure outcome stability.
7. Update backlog notes, check AC1..4, set status Done once validations are green.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented `DeezerPodcastPlatformResolver` in `media_summarizer/workers/podcast_platform_resolvers.py` using the shared `PodcastPlatformResolver` contract (task-24 foundation).

Resolver flow: require Deezer episode URLs (`episode_id`), fetch metadata from `https://api.deezer.com/episode/{id}`, then map to PodcastIndex via feed search (`search_podcasts`) + episode matching (`best_match_episode`) and return stable `PodcastResolutionOutcome` values.

Stable failure semantics preserved with shared codes: `invalid_platform_url`, `episode_not_found`, `audio_url_not_found`, `upstream_lookup_failed` and retryable behavior for transient upstream errors.

Worker registry wiring updated: replaced Deezer placeholder with concrete resolver in `build_worker_podcast_platform_resolver_registry(...)`; exported `DeezerPodcastPlatformResolver` in module `__all__`.

Hardened centralized Deezer URL normalization in foundation (`_normalize_deezer`) to support locale-prefixed paths (e.g. `/fr/episode/{id}`, `/en/show/{id}`) while canonicalizing to `/episode/{id}` or `/show/{id}`.

Architecture docs updated in `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` to mark Deezer resolver integration as implemented in worker routing.

Validation (targeted, no new automated tests): AST parse on touched python files; `uv run ruff check media_summarizer/workers/podcast_platform_resolvers.py` passed; functional smoke run through `_resolve_audio_url` with real Deezer URL resolved end-to-end to audio URL, locale-prefixed Deezer URL resolved similarly, and Deezer show URL failed deterministically with `code=invalid_platform_url`.
<!-- SECTION:NOTES:END -->
