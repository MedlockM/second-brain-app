---
id: task-265
title: >-
  Benchmark title derivation strategies for ingested media (per-source metadata
  vs generated titles)
status: To Do
assignee: []
created_date: '2026-08-14 02:02'
labels:
  - benchmark
  - ingestion
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Research task. No implementation.

## Problem

The title is the primary identity of a media item — it is what the Inbox list, the Search results and the media detail screen all show. Today it is derived ad hoc, per source, and the result is wrong or meaningless for several sources. Observed on dev (2026-08-14, Search screen):

- An Instagram reel whose transcript is about Larry Silverstein is titled **"Tinfoil Goy"** — the account name, not the content.
- A YouTube video is titled **"youtube:youtube_video"** — a sentinel string leaking to the UI.
- Uploaded documents are titled **"IMG_8671.png"**, and one carries a raw percent-encoded filename (`…6A…nt%20D…%2…ecurity…`) — a filename is not a title, and it is not even decoded.

Note the one defect that is **out of scope here**: a podcast whose title is correct in the Inbox showed as its Spotify episode id on the detail screen. That is a contract omission, not a derivation problem — the stored title simply never reached that screen. It is handled by **task-267**, independently. Do not re-diagnose it; do count the detail screen among the surfaces that consume the title.

## What the code actually does today (grounding, verify before trusting)

- `media_summarizer/core/media_ingestion/adapters/orchestrators.py:163` — `title = resolved.title or f"{platform}:{media_type}"`. When no resolver supplied a title, this sentinel is written to the durable library row and is never replaced unless a worker later publishes one.
- `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py` (~441-489, ~555-584, ~652) — title is `ownerFullName` / `ownerUsername` / `uploader` / `channel`, i.e. **the author**, falling back to `caption[:100]`. This is the "Tinfoil Goy" case.
- `media_summarizer/workers/youtube_ingestion_worker.py` — never sets a title, although yt-dlp's `info` dict carries one. This is the "youtube:youtube_video" case.
- `media_summarizer/workers/article_extraction_worker.py:379` — passes `title=None` into the extraction metadata, although trafilatura exposes the document title.
- `media_summarizer/workers/podcast_platform_resolvers.py` — podcasts DO get a real episode title (oEmbed, `og:title`, PodcastIndex match). This is the one source that works and it is the reference to compare against.
- `media_summarizer/core/media_ingestion/use_cases.py:140,172` — shared text and shared audio files get `platform:shared_text` / `platform:audio_file` sentinels; these have no upstream metadata at all and are the strongest candidates for a generated title.
- `media_summarizer/core/services/durable_media_service.py:341-350` — the late-metadata mirror: a worker that resolves a title after the initial save can patch it (`("title", "title")`, non-empty values only). Any solution can use this hook; it already exists.
- Uploaded documents and camera captures carry the **filename** as title, undecoded (see the `IMG_8671.png` and `%20`-encoded cases above). Establish from the code which path writes it before proposing anything.

**Where the title is consumed** — the recommendation must work for all of these, not just the Inbox: the Inbox list (`GET /api/media` → `MediaSearchItem`), the media detail screen (`GET /api/media/{id}/status` → `MediaItemContract`, once task-267 lands), the Algolia index and its highlighted search results, and the digest screens.

## Scope of the benchmark

Compare, end to end, the possible approaches to producing a title that describes the *content*, for every source in the pipeline (YouTube, Instagram, TikTok, X, web article, podcast, RSS, WhatsApp shared text, shared audio, uploaded document, OCR image). At minimum:

1. **Fix the metadata extraction per source** — plumb the title each provider already returns (yt-dlp `info["title"]`, trafilatura title / `og:title`, Apify caption vs owner fields, X post text, document filename or embedded title). Cheapest, no new dependency; but bounded by what the provider returns, and it does not solve "no metadata at all" (shared text, audio file, OCR image), nor sources where the provider's title IS the author.
2. **Generate the title from the transcript with an LLM** — the pipeline already calls an LLM for artifacts and translation (see the model retained by task-72 / task-189), so cost, latency and provider are partly known. Evaluate: which stage it runs at, marginal cost per item at the volumes projected in the task-65 pricing benchmark, added latency before a title is visible, and what the user sees in the meantime.
3. **Hybrid / arbitration** — use provider metadata when it is trustworthy and fall back to generation otherwise. The hard part is the arbitration rule: how do you decide a provider title is untrustworthy? Candidate signals: it equals the account/uploader name, it is a sentinel, it is a truncated caption, it is below N characters, it is a bare filename. Say explicitly which signals are cheap and reliable and which are guesswork.
4. Any other approach the research surfaces.

Dimensions to cover for each approach: per-source coverage (which of the sources above it actually fixes), title quality, marginal cost per media item, added latency and where it falls in the pipeline, failure modes, and implementation complexity against the existing code paths listed above.

Also settle these product questions, which shape the implementation:

- **When must the title be final?** The library row is created synchronously at submission, before the transcript exists. Is a provisional title acceptable, and if so what does the user see — and how does the Inbox behave when the title changes under it?
- **What is the fallback when everything fails?** A sentinel like `youtube:youtube_video` must never reach the UI again. Decide between the source URL, the platform label plus a date, or a generic label.
- **Titles are indexed in Algolia** (`media_summarizer/core/services/search_indexing.py`) and highlighted in search results. A title that changes after indexing must be re-indexed; state whether the retained approach needs that and by which path.
- **Is a language constraint needed?** Transcripts are translated to the user's reading language (task-192); state whether the title should follow the transcript language or the user's reading language.

## Constraints

- Nothing is deployed, there are no users and no production data (see `AGENTS.md` § "Nothing is deployed yet"). Existing rows carrying a bad title are disposable — **do not scope a backfill or a migration**, and do not preserve the current per-source title logic for compatibility. The retained approach replaces it outright.
- Reuse what exists before adding a provider: the LLM stack retained by task-72, the translation path from task-189/192, and the late-metadata mirror in `durable_media_service`.
- Cost claims must be sourced (official pricing pages) and projected against the volumes used in the task-65 pricing benchmark. No invented quality scores.

## Deliverable

`docs/research/task-265-media-title-derivation/README.md`, with the front-matter carrying `owner_decision: pending`, a comparison matrix, a per-source coverage table, and a single argued recommendation with its trade-offs stated.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A comparison of at least 3 approaches (per-source metadata extraction, LLM generation from the transcript, hybrid with arbitration, plus any other the research surfaces), each with its failure modes and implementation complexity against the existing code paths
- [ ] #2 A per-source coverage table listing every source in the pipeline (YouTube, Instagram, TikTok, X, web article, podcast, RSS, WhatsApp shared text, shared audio, uploaded document, OCR image) and stating, for each approach, whether it produces a content-describing title for that source
- [ ] #3 The current per-source behaviour is documented from the code, with file and line references, and the three observed defects (Instagram title = account name, YouTube title = 'youtube:youtube_video' sentinel, uploaded document title = raw undecoded filename) are traced to their origin
- [ ] #4 Cost and latency of the LLM-based approaches are projected per media item and per month against the volumes used in the task-65 pricing benchmark, sourced from official pricing pages
- [ ] #5 The four product questions are answered explicitly: timing of the final title, fallback when everything fails, Algolia re-indexing of a title that changes, and the language the title follows
- [ ] #6 A single final recommendation is argued with its trade-offs stated, and the README front-matter carries owner_decision: pending
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Research delivered — **mode: initial** (no `docs/research/task-265-*` directory existed, so there was no owner-rejected README and no complement request to integrate).

Deliverable: `docs/research/task-265-media-title-derivation/README.md`, front-matter `owner_decision: pending`.

What it contains:
- **§1** the four title consumers, plus the finding that `title` is the *first* entry of Algolia's `searchableAttributes` (`utils/algolia_client.py:106-109`), so a wrong title pollutes ranking and not just the label.
- **§2** the current per-source behaviour traced from the code with file:line, including the three observed defects: the Instagram author-as-title (`instagram_apify_resolver.py:441-447, 555`, root-caused against the installed yt-dlp extractor and the Apify Instagram schema, which has **no** `title` field at all), the `youtube:youtube_video` sentinel (`orchestrators.py:163` + `info["title"]` never read at `youtube_ingestion_worker.py:1060`), and the raw filename (`localImport.ts:186-197` with no `decodeURIComponent` → `media.py:927/990/1004` → `document_parsing/worker.py:260`). A **fourth latent defect** was surfaced: RSS titles are read (`rss_feed_poll_worker.py:51`) then dropped, and every Deepgram path sends an `episode_title` that nobody reads.
- **§3** the plumbing that already exists (the `mirror_job` hook, and the fact that Algolia is fed from `canonical_job.title` at `episode_completion_status` time).
- **§4-§5** six approaches compared across coverage, quality, cost, latency, failure modes and implementation complexity.
- **§6** the arbitration signals split explicitly into "cheap AND reliable" (8 deterministic rejection rules) and "guesswork" (truncation detection, semantic mismatch, length thresholds, clickbait scoring — all rejected as signals, with reasons).
- **§7** the per-source coverage table for all eleven sources.
- **§8** cost and latency projected per item and per month against task-65's three tier baskets, priced from OpenAI's official pricing page. Notable conclusion: **cost does not discriminate** the options (worst case 2,5 cents/user/month), the argument is quality + latency. No latency figure was invented — the only published measurement for `gpt-5-nano` is at *high* reasoning effort and is documented as non-transferable.
- **§9** the four product questions answered explicitly (provisional title + no-polling Inbox and no processing badge; platform label + date as the stored fallback, with the source URL and "Untitled" both rejected and reasons given; no Algolia re-index needed if the title is written before the completion event; the title follows the source text's language, never `reading_language`).
- **§10-§14** failure modes per approach (LLM headline hallucination cited from arXiv 2407.15975 and 2302.05852), an informative implementation outline, rejected alternatives, out-of-scope observations, and sources with URLs.

Recommendation: approach **C** — metadata-first with a closed list of deterministic distrust rules, `gpt-5-nano` only where metadata is structurally absent, title written to `job.title` before `episode_completion_status`. Approach B (LLM on every item) is documented as the second choice if the owner prefers a smaller code surface.

Out of scope as instructed: the podcast detail-screen defect (task-267) is not re-diagnosed; the detail screen is counted among the title consumers.

**The recommendation awaits owner validation** — the task stays `To Do` and the README front-matter stays `owner_decision: pending`.
<!-- SECTION:NOTES:END -->
