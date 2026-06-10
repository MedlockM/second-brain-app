---
id: task-179
title: Update docs/INGESTION_WORKERS_PROVIDERS.md after tasks 176/177/178 land
status: To Do
assignee: []
created_date: '2026-06-10 16:15'
labels:
  - docs
  - ingestion
dependencies:
  - task-176
  - task-177
  - task-178
priority: low
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

`docs/INGESTION_WORKERS_PROVIDERS.md` is the authoritative reference for the ingestion pipeline. Tasks 176, 177, and 178 each modify a major section:

- **task-176**: reconnects the Podcasting 2.0 `<podcast:transcript>` short-circuit as the primary path for podcast ingestion. The Podcast section currently says "No automatic transcript fallback at the podcast layer" — that must change.
- **task-177**: replaces the Apify-only YouTube path with the layered TikTok-style chain (yt-dlp → Apify → Deepgram on yt-dlp URL → Deepgram on Apify URL). The YouTube section currently says "No fallback — failure is terminal".
- **task-178**: adds a 4th fallback (Deepgram on Apify-resolved media URL) to the TikTok worker. The TikTok section's fallback chain table needs a 3rd row.

This task updates the doc to reflect the new code reality once those three tasks have landed.

## Sections to update

### Podcast (post task-176)

- Add a "Primary path" sub-step: "Fetch `<podcast:transcript>` via `fetch_rss_transcript()` BEFORE enqueuing to Deepgram"
- Replace the "No automatic transcript fallback" note with a fallback table:
  | Step | Trigger | Action |
  |---|---|---|
  | 1 | `feed_url` + `episode_guid` present, RSS has `<podcast:transcript>` | Upload pre-existing transcript, skip Deepgram (provider=`podcasting_2.0`) |
  | 2 | Tag absent / fetch fails / payload empty | Fall back to Deepgram pull on the audio enclosure URL (existing behavior) |
- Update the `rss_transcript.py` reference: it's now actively wired (not "currently unused" as the existing doc says)
- Update the routing diagram to show the short-circuit branch

### YouTube (post task-177)

- Rewrite the "Primary path" table — yt-dlp is now primary; Apify is the IP-block fallback
- Add the full fallback chain table (3 levels): yt-dlp captions → Apify transcript → Deepgram on yt-dlp URL OR Apify-resolved URL
- Update the "Downstream dependencies" — YouTube can now hand off to Deepgram (was: "Never enqueues to Deepgram")
- Update the routing diagram's YouTube branch to show the multi-level chain
- Add the new env vars (`YTDLP_TIMEOUT_SECONDS`, etc.) borrowed from the TikTok worker pattern
- Reference the shared helper module created by task-177 (probably `utils/ytdlp_helpers.py`)

### TikTok (post task-178)

- Add a row to the fallback chain table:
  | Step | Trigger | Action |
  |---|---|---|
  | 1 | yt-dlp IP-blocked (status 10204) | Apify TikTok Transcript actor → upload transcript |
  | 1b (NEW) | Apify ran but returned no transcript | Resolve media URL from Apify response → Deepgram push |
  | 2 | yt-dlp succeeded but `NativeSubtitlesUnavailable` | yt-dlp media URL → Deepgram push |
- Document the new `strategy_used="deepgram_via_apify_tiktok_url"` value
- Update terminal failure codes section if task-178 introduces a new code distinguishing "no transcript AND no media URL" from "no transcript only"

### Cross-cutting: Deepgram Modes

- Add a new row to the producer-to-mode mapping for the YouTube worker's new Deepgram-push branch
- Verify the existing TikTok row still says `push` (it does, but the new branch from task-178 uses the same mode)

### Decision Tree / Routing diagram

- The ASCII diagram needs updating for YouTube (now branches to Deepgram in some cases) and Podcast (short-circuit branch)

## How to verify

After updating the doc:
1. Re-grep all sections against the live code paths cited (e.g. `rg "mark_extracting|deepgram_mode" media_summarizer/workers/`)
2. Ensure every fallback step in the doc has a corresponding line:column reference in the worker file
3. Update the "Last verified against codebase" line at the top of the doc to today's date
4. Skim each section once for accuracy — no fabricated env vars, no stale function names

## Out of scope

- Adding new sections for workers not affected by the three predecessor tasks
- Restructuring the doc layout
- Adding sequence diagrams beyond the existing ASCII routing diagram

## References

- `docs/INGESTION_WORKERS_PROVIDERS.md` (target of update)
- task-176 (Podcasting 2.0 short-circuit)
- task-177 (YouTube fallback chain alignment)
- task-178 (TikTok Deepgram-on-Apify-URL fallback)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Podcast section reflects the `<podcast:transcript>` primary path with Deepgram pull as fallback (post task-176)
- [ ] #2 YouTube section rewrites the primary path as yt-dlp + the full 4-level fallback chain (post task-177)
- [ ] #3 TikTok section's fallback chain table has the new "Apify returned no transcript → Deepgram on Apify URL" row (post task-178)
- [ ] #4 Cross-cutting Deepgram Modes section reflects the new producers (YouTube push branch, TikTok-via-Apify push branch)
- [ ] #5 ASCII routing diagram updated for YouTube and Podcast branches
- [ ] #6 "Last verified against codebase" header updated to the date the doc is reviewed
- [ ] #7 No stale references — every cited symbol exists in the code at the cited path
<!-- AC:END -->
