---
id: task-266
title: Implement media title derivation per validated benchmark (task-265)
status: Done
assignee: []
created_date: '2026-08-14 02:02'
updated_date: '2026-08-17 19:29'
labels:
  - ingestion
dependencies:
  - task-265
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the media title derivation retained by the owner at the end of task-265.

**Read `docs/research/task-265-media-title-derivation/README.md` first.** The `Decision` field under `Owner Validation` in the front-matter is authoritative — it may differ from the research agent's initial recommendation, and it may reference `complement-response-*.md` files that refine it. Follow what the `Decision` says, not what the comparison matrix concludes. Do not start if `owner_decision` is not `ok`.

## Scope

Replace the current per-source title derivation across the ingestion pipeline with the retained approach. The paths that carry title today, all of which the implementation will touch or delete:

- `media_summarizer/core/media_ingestion/adapters/orchestrators.py:163` — the `f"{platform}:{media_type}"` sentinel.
- `media_summarizer/core/media_ingestion/use_cases.py:140,172` — the `platform:shared_text` / `platform:audio_file` sentinels.
- `media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py` — title currently taken from the account/owner fields.
- `media_summarizer/workers/youtube_ingestion_worker.py`, `tiktok_ingestion_worker.py`, `x_ingestion_worker.py`, `article_extraction_worker.py` — workers that resolve provider metadata but publish no title.
- `media_summarizer/core/services/durable_media_service.py:341-350` — the late-metadata mirror, if the retained approach resolves the title after the initial save.
- `media_summarizer/core/services/search_indexing.py` — the title is an indexed and highlighted Algolia field; if the retained approach lets the title change after indexing, the re-index path must be wired.

The **media detail screen** is not in this task's scope: it derived its header from the URL because `MediaItemContract` carried no title at all, which **task-267** fixes independently. Once both have landed, the detail screen shows whatever this task stores — no extra wiring needed here. If task-267 has not landed yet, do not duplicate its fix.

Nothing is deployed and there are no users (see `AGENTS.md` § "Nothing is deployed yet"): the old per-source logic is **deleted** in the same run, not kept behind a flag or a fallback, and no backfill is scoped for existing dev rows carrying a bad title.

## Owner notes (not acceptance criteria — the implementer cannot do these)

- The fix is only observable end to end after a deploy to `-dev`, which happens on push to `main`. The owner submits one media per source afterwards and checks the title shown in the Inbox, in Search and on the detail screen.
- The Instagram and YouTube cases from the original report are the two to check first: an Instagram reel must no longer be titled with the account name, and no media must ever show a `platform:media_type` string.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The approach recorded in the Decision field of docs/research/task-265-media-title-derivation/README.md is implemented; if the Decision references complement files, their refinements are applied too
- [x] #2 No code path can write a `platform:media_type`-style sentinel as a title any more: the sentinel expressions in orchestrators.py and use_cases.py are gone, replaced by the fallback the Decision specifies
- [x] #3 The per-source title logic the Decision supersedes is deleted, not left behind a flag, a fallback branch or a dead helper — a grep for the removed expressions returns nothing
- [x] #4 Every source listed in the benchmark's coverage table is wired to the retained derivation, and any source the Decision explicitly leaves out is named in the task's Implementation Notes with the reason
- [x] #5 If the retained approach changes a title after the media is indexed, the Algolia re-index path is wired so the indexed title matches the stored one
- [x] #6 ruff and mypy are clean on the backend
- [x] #7 If the retained approach needs infrastructure the pipeline does not have yet (a new queue, an IAM permission, an env var, a Terraform variable), it is provisioned and `terraform validate` is clean; if it needs none, that is stated in the Implementation Notes
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### What was implemented

Owner Decision (`owner_decision: ok`, validated 2026-08-17): **approach A, per-source metadata plumbing, no LLM**, plus three precisions — Instagram takes the beginning of the description, photos take a metadata title if one exists and otherwise the media type followed by the upload date, imported files take their title from the metadata. The recommendation of the research agent (C, the LLM hybrid) was **not** implemented; no model call was added anywhere and no new provider is contacted.

One new pure module holds the whole rule: `media_summarizer/core/media_ingestion/title_derivation.py`.

- `normalize_title_candidate()` — percent-decode, extension strip, `_`/`+`/`-` collapse, trailing ` | Site Name` removal (only when a real headline survives), 120-char cut on a word boundary.
- `is_rejected_title()` — the closed list of *provable* rejections of §6.1: our own `platform:media_type` sentinel shape, title equal to an author field present in the same payload, provider placeholders (`Video by <user>`, `TikTok video #123`), a bare filename, device/OS/messaging naming conventions (`IMG_`, `PXL_`, `Screenshot`, `PTT-`, `20260817-143012`, `photo-<epoch>`, long hex), generic words (`untitled`, `document`, `audio`, `photo`…), title equal to the site name or host. Nothing from §6.2 (truncation detection, length thresholds, semantic or clickbait scoring) is used.
- `first_sentence()` — the title-shaped head of a free-text body: first non-empty line, hashtag/mention runs stripped, first sentence, word-boundary cut. Generalises what X already did well.
- `first_markdown_heading()` — the document's own title as the parser rendered it (LlamaParse emits it as `#`, Unstructured maps `Title` elements to `##`); only the head of the file is scanned, so a heading after body text counts as a section, not a title.
- `fallback_title()` — §9.2: `<human label> — <save date>` (`YouTube video — 17 Aug 2026`, `Photo — 17 Aug 2026`, `Voice note — 17 Aug 2026`). Never the source URL, never `Untitled`, never empty.
- `select_title()` returns the first surviving candidate or `None`; `derive_media_title()` adds the fallback. Workers use `select_title()` so a worker that learns nothing new leaves the stored title alone instead of overwriting it with a freshly dated label.

### Per-source coverage (§7 table, all 11 rows)

| # | Source | Where the title now comes from |
|---|---|---|
| 1 | YouTube | `info["title"]` from the same yt-dlp call that resolves the streams; on the Apify path a new `_apify_item_title()` reads the actor item. Assigned on all three branches (native subtitles, Deepgram fallback, Apify) |
| 2 | Instagram | first sentence of the caption/description, in the resolver (3 sites) **and** finally written to the job by `instagram_ingestion_worker`, which is where the resolver actually runs — before, the caption was resolved, logged and dropped |
| 3 | TikTok | `info["title"]`, which the yt-dlp extractor fills from the clip caption |
| 4 | X | `_build_titles()` re-routed onto the shared helper; the local `_first_line`/`_truncate` pair is deleted |
| 5 | Web article | `trafilatura.extract_metadata()` on the HTML already fetched (JSON-LD + OpenGraph + `<title>`), with `sitename`/`hostname`/`author` fed to the rejection rules; also fills the previously hardcoded `title=None` in the extraction metadata |
| 6 | Podcast | `podcastindex_resolution_worker` and the Podcast Index picker endpoint both go through the shared derivation; the show name is passed as a site name so an episode titled like its show is rejected |
| 7 | RSS | the feed item `<title>`, which was parsed and then dropped from the job |
| 8 | WhatsApp shared text | first sentence of the note itself (the note is the only text there is), else `Shared note — <date>` |
| 9 | Shared audio | cleaned `original_name`, else `Voice note — <date>` — `PTT-20260817-WA0003.opus` is in the rejected class |
| 10 | Uploaded document | cleaned filename at upload (`Grant%20Deed_Security.pdf` → `Grant Deed Security`), upgraded by the parsing worker to the first markdown heading when the file carries one |
| 11 | Camera capture / library photo | cleaned filename when it says something, else `Photo — <date>` |

Sources or paths deliberately **not** upgraded, with the reason:

- **Camera photos have no metadata title read from the image.** No dependency-free EXIF/XMP/IPTC reader exists in the runtime (`pyproject.toml` has no Pillow, no pypdf, no exifread) and `ParseResult` exposes no title field, so there is nothing to read without adding a dependency — which approach A explicitly avoids. Per the owner's own rule, those land on `Photo — <date>`. The first markdown heading is deliberately **not** used for image formats: for a photo it is OCR'd body text, not a title the file carries.
- **TikTok Apify fallback branch** (`_process_apify_fallback`): the transcript actor's dataset item carries only `success` and `transcript` — no caption field — so a clip whose yt-dlp path was IP-blocked keeps the `TikTok video — <date>` label.
- **Instagram image posts**: still hard-failed upstream at `orchestrators.py`, so they never reach a title. The resolver path is wired anyway, ready for the day they land.
- **RSS items still get no durable library row.** That is §13 observation 2 of the benchmark, explicitly outside its scope; the title now reaches the job (and through it the digest and the search index), but the mirror has no row to write to. Creating library rows for polled feed items is its own task.
- **The dead `episode_title`/`podcast_title` fields on the Deepgram queue** were left in place (§13 observation 3). They now receive `job.title` first instead of the stale submission-time value, but removing them is a separate cleanup.

### AC #5 — no Algolia re-index path is needed

Verified branch by branch: every producer writes `job.title` **before** `mark_completed()` / before enqueueing Deepgram, so by the time `media_completed_worker` handles the `episode_completion_status` event and re-reads the canonical job from DynamoDB, the title it sends to the indexer (`canonical_job.title`) is already final. The title is therefore correct on the **first** indexing pass and never changes afterwards, which is exactly the §9.3 conclusion. `search_indexing.py` is untouched: adding a re-index path would be dead code.

### AC #7 — no infrastructure needed

Approach A adds no provider, no model call, no queue, no IAM permission, no environment variable and no Terraform variable. `terraform/` is untouched by this change. One queue message field was **removed** (`media_title` on the document-parsing message, which only ever duplicated `file_name`); SQS payload shapes need no infrastructure change.

### Client-side fallbacks deleted

The rule is server-side and single, so the four divergent client inventions are gone: the source-URL fallback in `mobile/app/(tabs)/inbox.tsx` and `mobile/src/components/MediaListCard.tsx` (it duplicated the domain line rendered right under the title), the `"Untitled"` fallback in `mobile/app/(tabs)/search.tsx`, the URL-then-`"Untitled"` chain in `mobile/app/media/[id].tsx`, and the `item.title || item.source_platform` fallback in `mobile/app/(tabs)/digest.tsx`. The detail screen's *projection* of the title (task-267) was left as it is; only its invented fallback, whose comment referred to the inbox fallback deleted here, was removed.

### Checks run

- `ruff check media_summarizer/` — clean.
- `mypy media_summarizer/` — clean (165 files).
- Grep for the superseded expressions (`f"{...source_platform.value}:{...}"`, `:shared_text"`, `:audio_file"`, `caption[:100]`, `_first_line`, `_truncate(`, `media_title`, `"Untitled"`, `"Episode inconnu"`) — nothing left outside the new module's own rejection lists.
- The derivation module was exercised by hand on the real defect cases from the benchmark (`youtube:youtube_video`, `Video by <user>`, an account name equal to the title, `IMG_4821.HEIC`, `Grant%20Deed_Security.pdf`, `PTT-20260817-WA0003.opus`, `Headline | The Economist`, `Le Monde` on lemonde.fr, `TikTok video #7412`) and behaves as specified. **No automated tests were added** — this project forbids them unless explicitly requested.
- `mobile/` has no `node_modules` in the worktree, so `tsc --noEmit` could not be run; the five mobile edits are one-line expression changes rendered inside `<Text>` children.

### Out of reach from this worktree

Nothing observable end to end: the deploy happens on push to `main`, long after this run. The two checks from the owner notes — an Instagram reel no longer titled with the account name, and no media ever showing a `platform:media_type` string — need the `-dev` deploy and one submission per source.
<!-- SECTION:NOTES:END -->
