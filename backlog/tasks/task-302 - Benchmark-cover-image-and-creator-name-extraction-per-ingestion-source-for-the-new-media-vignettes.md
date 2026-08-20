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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Research delivered — **mode: initial** (no `docs/research/task-302-*` directory existed, so there was no owner-rejected README and no complement request to integrate).

Deliverable: `docs/research/task-302-media-cover-and-creator/README.md`, front-matter `owner_decision: pending`.

What it contains:
- **§1** the four consumers of a cover and a creator. Finding: three of the four (detail screen, digest, Algolia) cannot render an image *even if one existed*, and none can render a creator — so this is not "populate a field", it is "add a field and wire two contracts".
- **§2** the current per-source behaviour from the code. The central finding is that **the creator name is not missing, it is passed as an argument and dropped**: task-266's "the title must never be the author" rule forced every worker to locate the author first, so the value sits in a named variable at the exact line that discards it (`article_extraction_worker.py:271`, `youtube_ingestion_worker.py:1125`, `tiktok_ingestion_worker.py:992`, `instagram_apify_resolver.py:458`/`:551`, `x_ingestion_worker.py:286`). The podcast path is further along still: `podcastindex_resolution_worker.py:129` resolves the show name into `podcast_title`, forwards it to the Deepgram queue at `:355`, and no consumer ever reads it back — the same dead-field pattern task-265 §2.6 found for `episode_title`.
- **§2.3** what each provider actually returns, verified against the *installed* packages rather than assumed: trafilatura 2.0.0 exposes `Document.image` and maps `og:image`/`og:image:url`/`og:image:secure_url`/`twitter:image` onto it; yt-dlp 2026.03.13 asserts `i.ytimg.com` thumbnails across its YouTube test matrix; the two Apify Instagram actors return `displayUrl`, `ownerFullName`, `ownerUsername`.
- **§2.5** **two corrections to this task's own premises**, established before anything was decided. (a) "the app renders no remote image anywhere today" is false — `digest.tsx:299-305` does; what is actually broken is that `DigestMediaItemResponse` (`api/endpoints/digest.py:32-39`) has no `thumbnail_url` while `mobile/src/types/digest.ts:14` declares one, so the digest card has rendered an always-`null` image since it was written. (b) several cited `file:line` refs had moved because task-265/266 shipped in between, and the diagnosis changed shape with them.
- **§4** the per-source table for all **11** ingestion paths, each with its cover source, its creator source, the `file:line` where the value is already in scope (or an explicit "structurally none"), and its fallback. Totals: cover free in 5, one extra request parameter in 1 (X), ours-already in 2 (camera/gallery photos), structurally impossible in 3. Creator free in 6, impossible in 5.
- **§5** hotlink versus re-host **argued per source**, not globally, on URL expiry (Instagram `oh`/`oe` and TikTok `x-expires` are signed and break within hours-to-days; `i.ytimg.com`, podcast artwork and `pbs.twimg.com` are unsigned and stable), image weight (og:image conventions, 80–150 KB typical), added pipeline latency (~0,3–0,6 s per re-hosted item inside workers already spending 20–60 s), monthly cost at task-65's volumes (≈ $0.04/month @100u at M12, i.e. 0,18 % of the 19,0 €/month infra line), and hotlink/copyright correctness stated in both directions. §5.5 compares three serving mechanisms for re-hosted covers and recommends presigned-at-read-time — the only one that needs no new AWS resource type and keeps the user's *private* photos private.
- **§6** the mobile rendering: `expo-image` recommended over React Native's `Image` on three props it does not have (`source.cacheKey`, `recyclingKey`, `cachePolicy`), with the exact source shape, the degraded behaviour for a missing/expired/refused image (the media-type icon `inbox.tsx:396-399` already renders — never an empty grey box, which is precisely what `digest.tsx:306` does today), and the tile ratio **16:9** with its crop costs stated rather than hidden.
- **§7** the creator field fully specified: `creator_name: Optional[str]` on `UserMediaRecord`/`ProcessingJob`/`ResolvedMedia`, capped at 80 chars; write path = one added line in the `mirror_job` tuple at `durable_media_service.py:445-452`, with the SQS-payload alternative rejected on the evidence of task-265 §2.6; **one field with publisher semantics**, not a publisher/author pair, argued source by source; and Algolia searchability answered **yes, in second position** (`["title", "creator_name", "transcript"]`) because the completion event is the only moment it is free to index and this repo has no re-index path.
- **§8** five options (hotlink-all, re-host-all, hybrid, creator-only, unfurl API) compared on coverage, guaranteed breakage, recurring cost, added latency, new dependencies, failure mode — plus an effort breakdown by file — ending in a single recommendation stated as what the owner would be validating.
- **§9-§13** failure modes of the recommended option including its own, an informative implementation outline, rejected alternatives with reasons, out-of-scope observations, and sources with URLs.

Recommendation: approach **C** — read what the pipeline already holds; hotlink the 8 sources whose URL is unsigned and stable; re-host only Instagram, TikTok (signed, expiring URLs) and camera/gallery photos (private, up to 50 MB); carry the image on the existing `job.media_image` → `thumbnail_url` mirror with a two-shape value (`https://…` or `s3://…`) resolved at read time, and the creator on one new mirrored attribute.

Constraints honoured: no compatibility layer and no second image field (the failure mode the task named); no backfill scoped for existing `-dev` rows; research only — no production code, contract or Terraform file modified (AC #8).

**The recommendation awaits owner validation** — the task stays `To Do` and the README front-matter stays `owner_decision: pending`.

Two questions the owner flagged as worth their attention are answered head-on: **hotlink vs re-host** in §5 (the answer is neither globally — it is two populations, and applying one policy to both is what makes it look hard), and **publisher vs author** in §7.3 (one field, publisher-first: in five of six sources the entity the saver recognises is the thing that publishes, not a natural person).
<!-- SECTION:NOTES:END -->
