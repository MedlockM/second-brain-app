---
id: task-174
title: >-
  Document primary path and fallbacks for each ingestion worker (per source
  type)
status: Done
assignee: []
created_date: '2026-06-10 08:23'
labels:
  - docs
  - backend
  - ingestion
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

The ingestion pipeline has grown to cover many source types (article, podcast, YouTube, Instagram, TikTok, X, document, audio upload). Each one has its own worker, primary extraction provider, and — for several of them — one or more fallbacks. Today this knowledge is scattered across the workers' source code, the resolver classes, the benchmark READMEs in `docs/research/`, and a few runbooks. There is no single authoritative document an engineer (or future agent) can read to answer "for source X, what does the system try first, and what does it try if that fails?"

Recent architectural decisions made the picture more nuanced:
- **Instagram Reels** (after task migrating to `khadinakbar/video-subtitle-extractor`): native captions only, **no Deepgram fallback**
- **TikTok**: yt-dlp primary, Apify fallback on IP block (task-144 / task-145 / task-149)
- **YouTube**: Apify (`scrape-creators/best-youtube-transcripts-scraper`) primary (task-126 / task-129 / task-132)
- **Document**: LlamaParse primary, Unstructured fallback (task-90 / task-91 / task-151)
- **Deepgram**: explicit `deepgram_mode` per producer since task-158 (no more automatic pull→push)
- **Podcast**: PodcastIndex resolver with iTunes ID matching (task-157)
- **Article**: trafilatura-based extraction
- **X** posts: dedicated worker
- **Audio upload**: direct Deepgram path

## Goal

Produce **one** authoritative reference document — `docs/INGESTION_WORKERS_PROVIDERS.md` — that lists, per source type, the primary extraction path and the documented fallback chain (or explicitly states "no fallback").

The document is not a benchmark and not a runbook. It is a **map of what is wired up right now**, derived from reading the code in `media_summarizer/workers/` and `media_summarizer/infrastructure/resolvers/`. It should let a reader answer two questions in under a minute:
1. For source type X, what provider/library does the system call first?
2. If that provider fails, what (if anything) does the system try next, and at what point does the job hard-fail?

## Required structure

The document must contain:

### Per source type (one section each)
- **Source type** (article, podcast, youtube, instagram-reel, instagram-post, tiktok, x, document, audio)
- **Worker file** — relative path
- **Primary path**: provider/library name, the actor/library identifier, what it extracts (text/audio URL/transcript/images), key env vars
- **Fallback chain**: ordered list (`1. … 2. …`) with the trigger condition for each step (HTTP code, exception type, empty result, etc.). If there is no fallback, write **"No fallback — failure is terminal"** explicitly
- **Terminal failure mode**: what the worker does when everything has failed (DLQ? failure event? job marked failed?)
- **Downstream dependencies**: does the worker hand off to another queue (Deepgram queue, OCR queue, image-post queue) or terminate inline?

### Cross-cutting sections
- **Deepgram modes** (`pull` vs `push` vs `pull_with_push_fallback` since task-158) — which producer worker uses which mode and why
- **Decision tree visualization** — a simple ASCII diagram or markdown table showing, for an incoming URL, how it is classified and which worker handles it
- **References** — for every claim, a link to the source code (path + symbol) and/or the benchmark README that justified the decision

## Method

The author of this task should:
1. Read every worker in `media_summarizer/workers/` (skip `base_worker`, `cleanup_expired_holds_worker`, `search_indexing_worker`, `rss_feed_poll_worker` — those are not ingestion workers)
2. Read every resolver in `media_summarizer/infrastructure/resolvers/` and the resolver adapters in `media_summarizer/core/media_ingestion/adapters/resolvers.py`
3. Cross-reference with the validated benchmark READMEs in `docs/research/` (especially task-107 Instagram, task-126 YouTube, task-140 TikTok, task-90 document parsing)
4. Verify each claim against the **current** code, not the benchmark (the benchmark is the rationale, the code is the truth — when they disagree, the code wins and the doc says so)

## Out of scope
- Writing new benchmarks or proposing architectural changes
- Documenting non-ingestion workers (search indexing, RSS polling, cleanup)
- Documenting the post-transcription pipeline (summarization, artifact generation) — that is a separate concern
- Maintaining the doc going forward — this task delivers v1 only; future updates piggyback on the tasks that change a worker

## Why

Today, an engineer (or an agent) wanting to know "what does TikTok do when yt-dlp fails?" or "is there still a Deepgram fallback for Instagram?" must grep through several files and infer from comments and tests. A single source-of-truth document closes that gap, prevents architectural drift between code and intent, and surfaces inconsistencies (e.g. a worker that silently has no fallback where the team thought there was one).

## References
- `media_summarizer/workers/` — all `*_ingestion_worker.py` files
- `media_summarizer/infrastructure/resolvers/` — every resolver class
- `media_summarizer/core/media_ingestion/adapters/resolvers.py` — wiring
- `docs/research/task-107-instagram-extraction-benchmark/README.md`
- `docs/research/task-126-*` (YouTube benchmark, if present)
- `docs/research/task-140-*` (TikTok benchmark, if present)
- `docs/research/task-90-*` (document parsing benchmark, if present)
- `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` — existing higher-level architecture doc
- task-158 (Deepgram explicit mode routing)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 #1 New file `docs/INGESTION_WORKERS_PROVIDERS.md` exists at the repository root of `docs/`
- [ ] #2 #2 The document covers exactly these source types, each in its own section: article, podcast, youtube, instagram-reel, instagram-post, tiktok, x, document, audio
- [ ] #3 #3 Each section names the worker file (relative path), the primary provider/library with its actor or package identifier, the relevant env vars, and the fallback chain — or the explicit string 'No fallback — failure is terminal' when there is none
- [ ] #4 #4 Each fallback step states its trigger condition (HTTP code, exception type, empty result, ...) verified against the actual `try/except` or `if` in the worker source code
- [ ] #5 #5 A cross-cutting 'Deepgram modes' section maps each producer worker to its `deepgram_mode` value (`pull`, `push`, `pull_with_push_fallback`) and explains why, citing task-158
- [ ] #6 #6 A decision-tree section (ASCII diagram or table) shows how an incoming URL is classified and routed to a worker
- [ ] #7 #7 Every factual claim in the document carries a code reference (`path/to/file.py::symbol`) or a benchmark README link, so a reader can verify it
- [ ] #8 #8 The document is read-and-spot-check-validated by the author: pick one worker per source type, follow its primary path and one fallback through the linked code, and confirm the doc matches
<!-- AC:END -->
