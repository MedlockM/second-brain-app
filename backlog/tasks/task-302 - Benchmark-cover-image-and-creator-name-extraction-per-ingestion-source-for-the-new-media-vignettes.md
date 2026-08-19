---
id: task-302
title: >-
  Benchmark cover-image and creator-name extraction per ingestion source for the
  new media vignettes
status: To Do
assignee: []
created_date: '2026-08-19 21:08'
labels:
  - benchmark
  - ingestion
  - backend
  - phase-6
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The owner's reference screenshot for the reworked Inbox is built on one tile shape: **a large image extracted from the media, the title, and the creator**. Two of those three do not exist in this codebase.

**The image.** `user_media.thumbnail_url` exists (`media_summarizer/core/models/user_media.py:95`), is already returned by the list endpoint as `media_image` (`api/endpoints/media.py:336`, `MediaSearchItem`), and is already declared in the mobile type (`mobile/src/types/media.ts:190`) — where **no component reads it**. It is populated for **podcasts only**: the single writer is `workers/podcastindex_resolution_worker.py:313` (`job.media_image = resolution.get("episode_image")`), mirrored onto the durable row by `durable_media_service.mirror_job` via the pair `("media_image", "thumbnail_url")` (`:450`). Articles, YouTube videos, TikTok, Instagram, X posts, shared text, uploaded documents, camera photos, gallery photos and audio files store nothing at all.

**The creator.** There is no author/publisher field anywhere — not on `UserMediaRecord`, not in `MediaSearchItem`, not in `MediaItemContract`. Several workers already hold the value and either drop it or misuse it: `infrastructure/resolvers/instagram_apify_resolver.py:447` and `:555` pick the account name (`uploader`, `ownerFullName`) **as the title**, the YouTube worker holds the full yt-dlp info dict (`workers/youtube_ingestion_worker.py:1060`), and the article path imports trafilatura, whose `Document` exposes `author` and `sitename`, then discards them.

This is the same shape of problem as **task-265** (title derivation): per-source metadata that mostly already sits in memory, one shared derivation helper, one existing mirror hook. Read `docs/research/task-265-media-title-derivation/README.md` first — its per-source table, its "the plumbing already exists and is free" finding and its cost section are the model to follow. `task-174` documents each worker's primary path and fallbacks.

## What the research must answer

**1. A per-source table.** For each of the 11 ingestion paths — article, YouTube video, podcast episode, TikTok, Instagram, X post, shared text, uploaded document, camera photo, gallery photo, audio file — state where the cover image comes from, where the creator name comes from (show, channel, site, byline, account), whether the value is already available somewhere in the pipeline (with `file:line`, as task-265 did), and the deterministic fallback when the source genuinely has none. A source that can never have an image must be named as such, not left blank.

**2. Hotlink vs re-host.** Whether we store the third-party URL and let the client fetch it, or download it once into our own S3. Argue it **per source**, not globally: Instagram/TikTok CDN URLs are signed and expire, an article `og:image` may refuse a request carrying no referer, `i.ytimg.com` is stable and public. Cover URL rot, image weight and bandwidth on a scrolling row, whether an existing bucket and key convention fits (`infrastructure/terraform/modules/platform/s3.tf`), added pipeline latency, monthly cost at the volumes of `docs/research/task-65-pricing-v1-benchmark`, and hotlink/copyright correctness.

**3. Client-side rendering.** `mobile/package.json` contains neither `expo-image` nor any image cache: **the app renders no remote image anywhere today**. Recommend what the tile uses (`expo-image` with memory/disk cache, placeholder, `contentFit` — vs React Native's `Image`), the degraded behaviour when a URL 404s or has expired (fall back to the media-type icon, never an empty grey box), and the aspect ratio the tile should crop to.

**4. The creator field.** Its name and type on `UserMediaRecord`, how it reaches the durable row (the `mirror_job` hook like the title, or the submission path), whether one field is enough or the UI needs both a publisher and an author (a podcast has a show and a host; an article has a site and a byline), and whether it should join the Algolia index — `utils/algolia_client.py` sets `searchableAttributes: ["title","transcript"]`, an ordered list, so adding a third field is a ranking decision and not a detail.

**5. Cost and effort per option, then one recommendation** the implementer can follow without re-deciding anything.

## Constraints

- No compatibility layer and no second image field kept "for old rows": nothing is deployed (`AGENTS.md`, "Nothing is deployed yet"). If existing `-dev` rows stay imageless until re-ingested, say so — do not scope a backfill around it.
- Reuse `thumbnail_url` and the existing `mirror_job` pair unless the research shows a concrete reason not to. Inventing a parallel image field alongside it is the failure mode here.
- Research only: this task writes no production code. The paired implementation task depends on it.

## Owner notes (not acceptance criteria)

- The two questions worth your attention when you review the README are (a) hotlink vs re-host, because it is the only one with a recurring cost and a rot risk, and (b) publisher-vs-author, because it decides what the tile's second line says for a podcast.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 docs/research/task-302-<short-description>/README.md exists with owner_decision: pending in its front-matter and an Owner Validation section whose Decision and Validated at fields are empty
- [ ] #2 A per-source table covers all 11 ingestion paths, each with its image source, its creator source, the file:line where the value is already available (or an explicit statement that it is not), and its fallback
- [ ] #3 The hotlink-versus-re-host question is answered per source, with URL expiry, image weight, added latency, monthly cost at the pricing-benchmark volumes and hotlink correctness each argued rather than asserted
- [ ] #4 The README recommends a mobile image component and states the degraded behaviour for a missing, expired or refused image, plus the tile aspect ratio it assumes
- [ ] #5 The creator field is fully specified: attribute name and type on UserMediaRecord, its write path onto the durable row, an explicit answer on publisher-versus-author, and an explicit decision on Algolia searchability
- [ ] #6 A cost and effort comparison of the candidate options ends in a single recommendation stated as what the owner would be validating
- [ ] #7 The README reuses thumbnail_url and the existing mirror_job hook, or states in writing why a different carrier is required
- [ ] #8 No production code, contract or Terraform file is modified by this task
<!-- AC:END -->
