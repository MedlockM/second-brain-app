---
id: task-176
title: Reconnect Podcasting 2.0 <podcast:transcript> short-circuit as primary path for podcast ingestion
status: To Do
assignee: []
created_date: '2026-06-10 16:00'
labels:
  - backend
  - ingestion
  - performance
dependencies: []
priority: medium
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

The Podcasting 2.0 namespace defines `<podcast:transcript>` tags inside RSS feeds — a publisher-provided, pre-existing transcript (SRT / VTT / TXT) that we can fetch directly without paying Deepgram a single second of audio. The codebase already has the helper `media_summarizer/utils/rss_transcript.py::fetch_rss_transcript()` ready to use, but as of 2026-06-10 it has **no live caller** in the ingestion pipeline. Every podcast episode therefore goes through the audio enclosure → Deepgram pull path even when a perfectly good transcript was already available in the feed.

Goal: make `<podcast:transcript>` the **primary path** for podcast ingestion, with the current PodcastIndex audio-resolution + Deepgram pull as the fallback when the feed has no transcript or the transcript fetch fails.

## Architecture change

### Before (today)

```
podcast URL
  → podcastindex_resolution_worker
     → resolve audio enclosure URL (PodcastIndex API)
     → enqueue to deepgram-transcription-queue (mode=pull)
        → Deepgram transcribes the audio
```

### After (this task)

```
podcast URL
  → podcastindex_resolution_worker
     → resolve {audio_url, feed_url, episode_guid} via PodcastIndex API
     → IF feed_url + episode_guid present:
        → fetch_rss_transcript(feed_url, episode_guid)
        → IF transcript found and non-empty:
           → upload transcript to S3 as {job_id}.txt (or .vtt/.srt as appropriate)
           → mark job completed, publish success event with provider="podcasting_2.0"
           → SHORT-CIRCUIT (skip Deepgram entirely, 0 cost, ~1s latency)
     → ELSE (no transcript, fetch failed, malformed payload):
        → fall back to current path: enqueue to deepgram-transcription-queue (mode=pull)
```

## Implementation notes

1. **`media_summarizer/workers/podcastindex_resolution_worker.py`** — modify `process_message()` (after `_resolve_audio_url` returns):
   - The PodcastIndex platform resolvers (Spotify / Apple / Deezer / RSS) already return `feed_id` in the resolution metadata. Most also expose `feed_url` via the PodcastIndex API response. Audit `podcast_platform_resolvers.py` to confirm `feed_url` and `episode_guid` are surfaced through `PodcastResolutionOutcome.metadata`. If not, plumb them through.
   - When both are available, call `fetch_rss_transcript(feed_url=..., episode_guid=...)` BEFORE enqueuing to Deepgram.
   - On transcript hit: upload to `TRANSCRIPT_BUCKET` as `{job_id}.txt` (convert SRT/VTT to plain text by stripping timestamps), set `job.set_transcription_location()` + `job.set_transcription_metadata({"provider": "podcasting_2.0", "transcript_format": "srt|vtt|txt", "source_detail": "rss_podcast_transcript_tag", "language": ...})`, mark completed, publish `episode_completion_status(status=success)` with `minutes_used=1` (no audio-minute consumption).
   - On transcript miss / fetch error: fall through to the current Deepgram enqueue path (do NOT fail the job — silent fallback).

2. **Logging** — add a structured log at decision time:
   - `transcription.completed_inline` with `transcript_source="podcasting_2.0"` on the short-circuit path
   - `transcription.transcript_short_circuit_skipped` (DEBUG) with the reason (`no_feed_url`, `no_guid`, `tag_absent`, `fetch_failed`, `payload_empty`) when falling back

3. **Format conversion** — `fetch_rss_transcript()` returns the transcript bytes + content-type. We need a small parser that:
   - Accepts `text/plain` / `text/srt` / `application/x-subrip` / `text/vtt` / `application/json+subtitle` (cf. Podcasting 2.0 spec)
   - Strips timestamps and cue numbers, returns plain UTF-8 text
   - Reuse the existing `_parse_caption_payload()` from `tiktok_ingestion_worker.py` if its logic is reusable; otherwise extract a shared helper into `utils/rss_transcript.py`.

4. **Metadata propagation** — the orchestrator and downstream artifacts pipeline read `transcription_metadata.provider` to pick the right minutes-used / costs accounting. `provider="podcasting_2.0"` should yield `minutes_used=1` (constant, transcript not metered) and `duration_seconds=0` to bypass audio-minute quotas.

## Out of scope

- Adding `<podcast:transcript>` support to RSS feeds we host ourselves — this task is about CONSUMING the tag, not producing it.
- Streaming transcript-aligned playback (V2+ feature, requires keeping SRT/VTT timestamps).
- Backfilling already-processed episodes — only NEW ingestions benefit from the change.

## E2E impact

The existing podcast happy-path E2E test (`tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex`) uses an Apple Podcasts URL whose feed may or may not have `<podcast:transcript>`. Two outcomes:
- Feed has the tag: test reaches `completed` faster (no Deepgram call). Assert `transcription_metadata.provider == "podcasting_2.0"`.
- Feed has no tag: test still reaches `completed` via Deepgram fallback. Assert `transcription_metadata.provider == "deepgram"`.

Pick a test fixture that empirically has the tag to validate the short-circuit path; add a separate test (or fixture variation) that exercises the fallback.

## Constraints

- Do NOT change the PodcastIndex API integration or credentials
- Do NOT change Deepgram integration
- Backward-compat: messages already in `podcastindex-resolution-queue` continue to work (the new short-circuit is an additive code path)

## References

- `media_summarizer/workers/podcastindex_resolution_worker.py` (target of change)
- `media_summarizer/utils/rss_transcript.py::fetch_rss_transcript` (helper, currently unused)
- `media_summarizer/workers/podcast_platform_resolvers.py` (audit for `feed_url` + `episode_guid` plumbing)
- `docs/INGESTION_WORKERS_PROVIDERS.md` § Podcast (will need an update — see task-179)
- Podcasting 2.0 spec: https://podcastindex.org/namespace/1.0#transcript
- Test fixture: `tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `podcastindex_resolution_worker.process_message` calls `fetch_rss_transcript(feed_url, episode_guid)` BEFORE enqueuing to Deepgram when both fields are available
- [ ] #2 On transcript hit (non-empty payload), the worker uploads the parsed plain-text transcript to `TRANSCRIPT_BUCKET`, marks the job completed, and publishes the success event with `provider="podcasting_2.0"`. Deepgram is not invoked.
- [ ] #3 On transcript miss / fetch error / empty payload, the worker silently falls back to the current Deepgram pull enqueue path (no job failure, no user-visible error)
- [ ] #4 `feed_url` and `episode_guid` are surfaced through `PodcastResolutionOutcome.metadata` for every supported platform (Spotify, Apple, Deezer, RSS) — audit + plumbing as needed
- [ ] #5 Format parser handles SRT, VTT, and plain text payloads; output is stripped of timestamps/cue numbers and stored as UTF-8 plain text
- [ ] #6 Lambda image rebuilt + `media-summarizer-worker-podcastindex_resolution` redeployed
- [ ] #7 E2E test: assert `transcription_metadata.provider == "podcasting_2.0"` on a fixture URL whose feed empirically carries the tag; a separate fixture (or modified flow) confirms the Deepgram fallback still works
- [ ] #8 Empirical confirmation (CloudWatch logs) of at least one short-circuit firing in dev within 24h of deployment, OR a manually-submitted fixture URL proving it
<!-- AC:END -->
