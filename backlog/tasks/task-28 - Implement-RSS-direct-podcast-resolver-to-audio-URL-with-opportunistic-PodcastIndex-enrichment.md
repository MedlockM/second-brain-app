---
id: task-28
title: >-
  Implement RSS direct podcast resolver to audio URL with opportunistic
  PodcastIndex enrichment
status: Done
assignee:
  - '@codex'
created_date: '2026-02-24 11:03'
updated_date: '2026-03-03 22:43'
labels: []
dependencies:
  - task-24
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement RSS/direct podcast URL resolution to audio URL, with optional PodcastIndex enrichment when available.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 RSS or direct podcast URLs resolve end-to-end to a valid audio URL.
- [x] #2 Resolver works without requiring PodcastIndex in all cases.
- [x] #3 PodcastIndex enrichment is applied opportunistically when available.
- [x] #4 Resolver emits stable outcomes aligned with shared resolver contract.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Rework `RssPodcastPlatformResolver` to resolve audio directly from RSS/Atom feed content (primary path), without requiring PodcastIndex.
2. Add resilient RSS parsing helpers (episode enclosure/title/date/duration/image extraction) and deterministic episode selection.
3. Add opportunistic PodcastIndex enrichment after direct RSS resolution; keep resolver success even when enrichment is unavailable/failing.
4. Preserve stable shared outcome contract (`PodcastResolutionOutcome` + stable error codes) across all success/failure branches.
5. Update architecture documentation to describe task-28 behavior and routing impact.
6. Run targeted static/functional validation and then update Backlog notes + AC + status Done.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented `RssPodcastPlatformResolver` direct-resolution primary path in `media_summarizer/workers/podcast_platform_resolvers.py`: fetch RSS/Atom feed over HTTP, parse XML entries, extract enclosure audio URL + episode metadata, and resolve without requiring PodcastIndex.

Added deterministic RSS parsing helpers and error taxonomy in resolver scope (`_RssFeedInvalidError`, `_RssFeedNoAudioError`) to preserve stable shared outcome codes (`invalid_platform_url`, `audio_url_not_found`, `upstream_lookup_failed`).

Implemented opportunistic PodcastIndex enrichment (`_try_podcastindex_enrichment`) after direct RSS success: enriches `feed_id` and metadata when PodcastIndex credentials/API are available, but never blocks direct RSS resolution when unavailable/failing.

Kept worker contract compatibility: `podcastindex_resolution_worker` continues consuming `PodcastResolutionOutcome`; downstream payload mapping unchanged (`audio_url`, titles, image, duration, feed_id).

Extended URL detection for direct feed hosts in classifier (`media_summarizer/core/media_ingestion/adapters/classifiers.py`): URLs with host prefixes `feeds.` or `rss.` now route to `podcast.default` as `SourcePlatform.RSS` (improves direct feed end-to-end coverage).

Updated architecture documentation section for task-28 in `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` to document primary RSS direct path + optional PodcastIndex enrichment behavior.

Validation (targeted, no new automated tests):
- AST parse OK for touched Python files.
- Ruff checks passed for touched files (`podcast_platform_resolvers.py`, `classifiers.py`).
- Functional smoke checks:
  - With PodcastIndex credentials: `https://changelog.com/podcast/feed` resolves end-to-end with `podcastindex_enriched=True` and `feed_id` populated.
  - Without PodcastIndex credentials: same RSS URL resolves successfully with `podcastindex_enriched=False` (no hard dependency).
  - Direct feed-host URL (no `/feed`/`.xml` hint) `https://feeds.simplecast.com/6b9EvGDp` is classified as podcast/rss and resolves end-to-end to a valid audio URL.
  - Invalid RSS input (`https://changelog.com/podcast`) returns deterministic failure `code=invalid_platform_url`.
<!-- SECTION:NOTES:END -->
