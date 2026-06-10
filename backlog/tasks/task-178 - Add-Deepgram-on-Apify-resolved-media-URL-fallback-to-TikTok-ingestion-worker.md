---
id: task-178
title: Add Deepgram-on-Apify-resolved-media-URL fallback to TikTok ingestion worker
status: Done
assignee: []
created_date: '2026-06-10 16:10'
labels:
  - backend
  - ingestion
  - tiktok
dependencies: []
priority: medium
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

`media_summarizer/workers/tiktok_ingestion_worker.py` currently has two-and-a-half fallback layers:

1. **yt-dlp native subtitles** (primary)
2. **Apify TikTok Transcript actor** (when yt-dlp is IP-blocked, status 10204)
3. **Deepgram on yt-dlp's resolved media URL** (when yt-dlp succeeded but the video has no captions)

Missing: when yt-dlp is IP-blocked AND the Apify actor runs but returns NO usable transcript (the video has no spoken content for the actor to extract, or the actor's whisper layer fails silently), the worker fails terminally with `apify_actor_failed:no_transcript_in_actor_output`.

This task adds a 4th layer: when Apify returned an empty transcript, use the actor's response payload to resolve a direct media URL, then dispatch to Deepgram in push mode (same exit point as the yt-dlp-no-captions branch).

## Target architecture

```
TikTok URL
  → yt-dlp extract_info
     ├─ IP block (status 10204)                          → Apify path
     ├─ yt-dlp succeeded WITH captions                   → upload native transcript, complete
     └─ yt-dlp succeeded WITHOUT captions                → resolve yt-dlp media URL → Deepgram push

  Apify path (ip-blocked branch):
    → call _fetch_apify_tiktok_transcript
       ├─ actor returns transcript                        → upload, complete
       ├─ actor returns NO transcript                     → NEW: resolve media URL from Apify response
       │                                                       → enqueue Deepgram (mode=push)
       └─ actor failed terminally (auth, run failed)      → fail with the original error code
```

## Implementation notes

### 1. Apify TikTok actor response schema (verified 2026-06-10)

Actor: `clockworks~tiktok-scraper`. Schema verified by reading the actor's published README via `GET https://api.apify.com/v2/acts/clockworks~tiktok-scraper/builds/default`.

| Field | Availability | Notes |
|---|---|---|
| `musicMeta.playUrl` | Default (free) | CDN URL of the audio track (`mime_type=audio_mpeg`). **Primary choice** for this fallback. URL expires after a few hours but the worker enqueues to Deepgram immediately, so expiry is not an issue. |
| `mediaUrls[]` | Only if input flag `shouldDownloadVideos: true` (paid add-on, $0.001/video) | Apify-hosted permanent URLs to the downloaded MP4. More stable than CDN URLs but adds cost. |
| `videoMeta.subtitleLinks[].downloadLink` | Default | Native subtitle download URLs — already consumed by `_extract_apify_transcript_text` if present (not a media URL). |
| `webVideoUrl` | Default | Public TikTok page URL — **not** a media stream. |

**Recommended approach**: read `musicMeta.playUrl` from `items[0]`. Caveat: when `musicMeta.musicOriginal=false` (the user's post borrows a viral sound rather than recording original audio), `playUrl` may point to the original sound — which is *correct* for transcription if the post just plays the sound, but *wrong* if the user added voice on top. Empirically observe a few real runs to decide whether this matters in practice.

**Fallback if `playUrl` proves unreliable**: enable `shouldDownloadVideos: true` on the actor input ONLY for runs that reach this fallback layer (not on every Apify call), then read `mediaUrls[0]`. Adds $0.001/video.

### 2. Modify `_fetch_apify_tiktok_transcript`

Today the function raises `TikTokIngestionError("apify_actor_failed", details="no_transcript_in_actor_output")` when `_extract_apify_transcript_text(items)` returns an empty string. Instead:
- Try to extract a media URL from the same `items` payload (new helper `_resolve_apify_tiktok_media_url(items)`)
- If a URL is found: return a special marker dict (e.g. `{"text": None, "fallback_audio_url": url}`) instead of raising. The caller (`process_tiktok_message`) will see the marker and route to the Deepgram push path.
- If no URL is extractable either: raise as today (terminal failure).

Cleaner alternative: split `_fetch_apify_tiktok_transcript` into:
- `_fetch_apify_tiktok_dataset(items)` (raw fetch, returns the actor's items)
- `_extract_apify_transcript_text(items)` (existing)
- `_resolve_apify_tiktok_media_url(items)` (new)

Then in `process_tiktok_message`, after the IP-block branch:
```python
items = await _fetch_apify_tiktok_dataset(normalized_url)
transcript_text = _extract_apify_transcript_text(items)
if transcript_text:
    # Path: Apify transcript success (existing behavior)
    ...
else:
    audio_url = _resolve_apify_tiktok_media_url(items)
    if audio_url:
        # NEW path: Deepgram push on Apify-resolved media URL
        await sqs.send_message(
            queue_name=DEEPGRAM_TRANSCRIPTION_QUEUE,
            message_body={
                "job_id": job.id,
                "audio_url": audio_url,
                "deepgram_mode": "push",
                ...
            },
        )
        ... # mark transcribing, return mode="deepgram_via_apify_url"
    else:
        # Terminal failure as today
        raise TikTokIngestionError("apify_actor_failed", ...)
```

### 3. Metadata

Extend `_build_apify_extraction_metadata` (or add a sibling builder) with `strategy_used="deepgram_via_apify_tiktok_url"` for the new branch. Helps disambiguate from the existing `strategy_used="apify_tiktok_ip_block_fallback"` and `strategy_used="direct_media_url_fallback"`.

### 4. Logging

Add a log marker when the new branch fires:
```python
log_event(
    logger, logging.INFO,
    "transcription.enqueued",
    "TikTok queued Deepgram fallback after Apify returned empty transcript",
    job_id=..., transcript_source="deepgram",
    fallback_strategy="deepgram_via_apify_tiktok_url",
)
```

## Out of scope

- Adding new TikTok providers beyond yt-dlp / Apify
- Apify TikTok actor configuration changes (e.g. enabling `shouldDownloadVideos=True` to get a stable video URL — depends on what fields the actor exposes by default)
- TikTok proxy V2 (covered by task-145)

## E2E impact

The existing fallback chain test (`tests/e2e/test_fallback_chains.py::test_tiktok_apify_fallback`, currently failing per task-167) exercises the IP-block → Apify path. After this task, that test should still pass (Apify-with-transcript branch unchanged).

Add a new test: pick a TikTok video that's IP-blocked from Lambda AND has no spoken content (e.g. a music-only / silent meme reel). Assert:
- Job reaches `completed`
- `extraction_metadata.strategy_used == "deepgram_via_apify_tiktok_url"`
- `transcription_metadata.provider == "deepgram"`

This test fixture is hard to lock in deterministically (depends on TikTok IP-block state + a video Apify can extract a media URL for but no captions); document as a best-effort fixture. Mark `xfail(strict=False)` if the fixture proves unstable.

## References

- `media_summarizer/workers/tiktok_ingestion_worker.py` (target of change, lines 495–721 for the Apify branch)
- `media_summarizer/workers/tiktok_ingestion_worker.py::_resolve_direct_media_url` (audio-stream selection logic, reusable)
- `media_summarizer/workers/transcription/deepgram_worker.py` (push mode)
- Apify actor docs (verified 2026-06-10): `https://apify.com/clockworks/tiktok-scraper`, JSON output schema via `https://api.apify.com/v2/acts/clockworks~tiktok-scraper/builds/default`. Default-output media URLs: `musicMeta.playUrl` (CDN, free) + addon `mediaUrls[]` via `shouldDownloadVideos:true` ($0.001/video).
- task-149 (original TikTok Apify fallback E2E test)
- task-167 (fallback chain tests cleanup — overlaps with the new test added here)
- `docs/INGESTION_WORKERS_PROVIDERS.md` § TikTok (will need an update — see task-179)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 When the Apify TikTok actor runs successfully but returns no transcript, the worker resolves a direct media URL from the actor's response payload
- [ ] #2 When a media URL is found, the worker enqueues Deepgram with `deepgram_mode="push"` and routes through the existing TRANSCRIBING / completion-event flow
- [ ] #3 When the Apify response has no transcript AND no extractable media URL, the worker fails terminally with a clear error code distinguishing it from the previous `no_transcript_in_actor_output` case
- [ ] #4 `extraction_metadata.strategy_used` records the new strategy (`deepgram_via_apify_tiktok_url`) on the new branch
- [ ] #5 The existing `strategy_used="apify_tiktok_ip_block_fallback"` and `direct_media_url_fallback` paths remain unchanged and continue to pass their tests
- [ ] #6 Lambda image rebuilt + `media-summarizer-worker-tiktok_ingestion` redeployed
- [ ] #7 New E2E test (best-effort, can be `xfail(strict=False)` if fixture is unstable) confirms the new branch fires for a fixture that's IP-blocked AND has no captions
<!-- AC:END -->
