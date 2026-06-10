---
id: task-177
title: Align YouTube ingestion fallback chain with TikTok pattern (yt-dlp → Apify → Deepgram)
status: To Do
assignee: []
created_date: '2026-06-10 16:05'
labels:
  - backend
  - ingestion
  - youtube
dependencies: []
priority: medium
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Today the YouTube ingestion worker (`media_summarizer/workers/youtube_ingestion_worker.py`) has a **single provider, no fallback**: it calls the Apify YouTube Transcript actor (`scrape-creators/best-youtube-transcripts-scraper`) directly. If the actor returns no transcript, the job fails terminally with `youtube_unavailable`.

This is fragile compared to the TikTok pipeline (`tiktok_ingestion_worker.py`), which uses a layered fallback:
1. **yt-dlp** native subtitles (free, fast, works when YouTube allows IP)
2. **Apify** transcript actor (when yt-dlp is IP-blocked)
3. **Deepgram on direct media URL** (when neither captions source has a transcript)

The owner wants the YouTube worker to follow the same pattern — extended with one extra fallback (Apify → Deepgram on the actor's resolved video URL when the actor itself returns no transcript).

## Target architecture

```
youtube URL
  → yt-dlp extract_info (skip_download=True, writesubtitles=True, subtitleslangs=["all"])
     ├─ IP block ("Sign in to confirm you're not a bot" / login wall)  → go to Apify path
     ├─ yt-dlp succeeded WITH native subtitles            → upload transcript, complete
     ├─ yt-dlp succeeded WITHOUT subtitles                → resolve direct media URL from yt-dlp info
     │                                                       → enqueue Deepgram (mode=push)
     └─ other yt-dlp error                                  → fail terminally

  Apify path (ip-blocked branch):
    → call Apify YouTube Transcript actor (existing _fetch_apify_transcript)
       ├─ actor returns transcript                         → upload, complete
       ├─ actor returns NO transcript                      → fail terminally (see "Apify limitation" below)
       └─ actor failed terminally (auth, geo, deleted)     → fail with the original error code
```

### Apify limitation: no Deepgram-on-Apify-URL fallback in V1 (verified 2026-06-10)

Actor `scrape-creators~best-youtube-transcripts-scraper` (the one we use today, configured in `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID`) **does NOT expose any media-stream URL**. Verified by reading the actor's published README via `GET https://api.apify.com/v2/acts/scrape-creators~best-youtube-transcripts-scraper/builds/default`. Output schema is exactly:

| Field | Description |
|---|---|
| `id` | Video ID |
| `url` | Input URL (the YouTube watch URL the user submitted, NOT a stream URL) |
| `transcript_only_text` | Full transcript text (if available) |
| `transcript` | Array of timestamped segments |

There is no `videoUrl`, no `streamUrl`, no `audioUrl`, no `mediaUrl` field. So a 4th-level fallback "Apify ran, returned no transcript → Deepgram on the actor's resolved URL" is **not realisable with this actor**.

**V1 decision (owner, 2026-06-10): we skip this fallback for now.** When both yt-dlp is IP-blocked AND the Apify actor has no transcript, the worker fails terminally with `youtube_unavailable`. Empirically this should be rare — if a video has no captions on YouTube AND yt-dlp can't reach it from Lambda, both transcript-extraction paths have already failed. The user can retry on a different video.

If post-V1 telemetry shows this terminal failure firing too often, a separate task can benchmark alternative YouTube actors that expose stream URLs (`apidojo/youtube-scraper`, `bernardo/youtube-scraper`, etc.) and switch the actor.

## Implementation notes

### 1. yt-dlp primary path

Reuse the TikTok worker's pattern almost verbatim:

```python
ydl_opts = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "writesubtitles": True,
    "writeautomaticsub": True,        # YouTube auto-generated captions are useful
    "subtitleslangs": ["all"],
    "socket_timeout": YTDLP_TIMEOUT_SECONDS,
}
info = await asyncio.to_thread(_run_ytdl, url, ydl_opts)
```

Subtitle collection: prefer **manual** captions over auto-generated. YouTube exposes both via `info["subtitles"]` (manual) and `info["automatic_captions"]` (auto). Manual = higher quality. Reuse `_collect_subtitle_candidates` + `_parse_caption_payload` from `tiktok_ingestion_worker.py` (extract them into a shared helper module — see "Shared helper" below).

### 2. IP-block detection for YouTube

YouTube's IP-block error message differs from TikTok. Empirically, yt-dlp surfaces:
- `"Sign in to confirm you're not a bot"` (login-wall on Lambda IPs since 2024)
- `"This video is unavailable from your location"` (geo)
- `"Video unavailable"` (generic)
- `"Failed to extract any player response"` (sometimes a side-effect of IP block)

Add `_is_ip_blocked_youtube_error(exc)`:
```python
def _is_ip_blocked_youtube_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(token in msg for token in (
        "sign in to confirm you're not a bot",
        "confirm you're not a bot",
        "failed to extract any player response",
        # Add tokens empirically as we observe them in CloudWatch
    ))
```

Geo-restriction (`"video is unavailable from your location"`, `"not available in your country"`) is **NOT** an IP block — it's a non-retryable terminal failure (the user picked a video that's region-locked away from us; Apify would also fail). Keep the existing `youtube_geo_restricted` code path for those.

### 3. Apify fallback (existing path, no new branch — see "Apify limitation" above)

The current `_fetch_apify_transcript` function stays as-is. The 4th-level Deepgram-on-Apify-URL fallback originally requested for this task is dropped because the configured actor (`scrape-creators~best-youtube-transcripts-scraper`) does not expose any media-stream URL in its output (only `id`, `url`, `transcript_only_text`, `transcript`).

If the actor returns no transcript, raise the existing `youtube_unavailable` / `apify_actor_failed` errors (terminal). A separate task should benchmark alternative YouTube actors that expose stream URLs if the empirical failure rate of this combined chain proves problematic.

### 4. yt-dlp succeeded but no captions → Deepgram on yt-dlp media URL

Reuse `_resolve_direct_media_url(info)` from `tiktok_ingestion_worker.py` (audio-track-preferred selection logic). Extract it to a shared module too.

Deepgram message body: `{"audio_url": media_url, "deepgram_mode": "push"}`.

### 5. Shared helper module

Create `media_summarizer/utils/ytdlp_helpers.py` (or fold into an existing `utils` module) and move:
- `_collect_subtitle_candidates(info)`
- `_fetch_subtitle_candidate(candidate, ...)`
- `_parse_caption_payload(payload, ext, content_type)`
- `_parse_timed_text_payload(payload)`
- `_parse_json_caption_payload(payload)`
- `_select_direct_media_stream(info)`
- `_resolve_direct_media_url(info)`

Update `tiktok_ingestion_worker.py` to import from the new module. Keep the TikTok-specific logic (rate limiter, IP-block detection regex, error messages) in the TikTok worker.

### 6. Metadata fields

Extend `extraction_metadata` with `strategy_used`:
- `"native_subtitles"` (yt-dlp succeeded with captions)
- `"apify_transcript"` (Apify fallback succeeded with transcript)
- `"deepgram_via_ytdlp_url"` (yt-dlp succeeded, no captions, Deepgram on yt-dlp resolved URL)

This enables observability ("how often is each strategy firing?") via CloudWatch metrics.

## Out of scope

- Streaming Deepgram (websocket) — V1 uses batch
- Adding new YouTube providers beyond yt-dlp / Apify / Deepgram
- Captions language selection (use `["all"]` and let the actor / yt-dlp pick — manual > auto > first available)

## E2E impact

The existing YouTube happy-path E2E test currently exercises only the Apify-only path. After this change, the test will likely exercise yt-dlp first (much faster) with Apify as a transparent fallback. Update the test to either:
- Pin a fixture that empirically goes through yt-dlp (most public videos)
- Add a separate xfail-ish test that exercises the Apify fallback (hard to trigger deterministically — IP block depends on Lambda IP rotation; document as best-effort)

For the new "Deepgram on yt-dlp URL" branch (no captions on the video), pick a fixture URL pointing to a YouTube video known to have NO captions (rare for major channels, but exists for small uploads). Add a happy-path assertion: `transcription_metadata.provider == "deepgram"` AND `extraction_metadata.strategy_used == "deepgram_via_ytdlp_url"`.

## References

- `media_summarizer/workers/youtube_ingestion_worker.py` (target of change)
- `media_summarizer/workers/tiktok_ingestion_worker.py` (reference implementation — esp. lines 400–490 for yt-dlp + 495–720 for Apify branch)
- `media_summarizer/workers/transcription/deepgram_worker.py` (push mode)
- Apify YouTube transcript actor docs (verified 2026-06-10): `https://apify.com/scrape-creators/best-youtube-transcripts-scraper` — output schema confirmed via `GET https://api.apify.com/v2/acts/scrape-creators~best-youtube-transcripts-scraper/builds/default`. Output fields: `id`, `url`, `transcript_only_text`, `transcript[]`. **No** `videoUrl` / `streamUrl` / `audioUrl` exposed.
- task-126 (original "YouTube IP block on Lambda" diagnosis)
- task-158 (Deepgram explicit mode routing — already declares `push` for social-video CDNs)
- `docs/INGESTION_WORKERS_PROVIDERS.md` § YouTube (will need an update — see task-179)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 yt-dlp is the primary path: `extract_info` runs first, native captions (manual preferred over auto-generated) are uploaded directly when available
- [ ] #2 IP-block detection: when yt-dlp surfaces a YouTube login-wall / "confirm you're not a bot" / equivalent, the worker falls back to the Apify actor (existing `_fetch_apify_transcript`)
- [ ] #3 yt-dlp succeeded but no subtitles available: the worker resolves a direct media URL from yt-dlp's `info` and enqueues Deepgram with `deepgram_mode="push"`
- [ ] #4 Apify fallback returned no transcript: fail terminally with a clear error code (the actor `scrape-creators~best-youtube-transcripts-scraper` does NOT expose any media URL — the Deepgram-on-Apify-URL branch is dropped from this task; a separate follow-up benchmark may evaluate alternative actors)
- [ ] #5 Geo-restricted / age-restricted / deleted videos surface as `youtube_geo_restricted` / `youtube_age_restricted` / `youtube_unavailable` — NOT routed to fallbacks
- [ ] #6 Shared helpers (`_collect_subtitle_candidates`, `_resolve_direct_media_url`, `_parse_caption_payload`, etc.) extracted from `tiktok_ingestion_worker.py` into a shared module reused by both workers
- [ ] #7 `extraction_metadata.strategy_used` records the actual strategy that produced the transcript (`native_subtitles` / `apify_transcript` / `deepgram_via_ytdlp_url`)
- [ ] #8 Lambda image rebuilt + `media-summarizer-worker-youtube_ingestion` redeployed
- [ ] #9 E2E test: existing happy path passes (likely via yt-dlp now, faster). Add a fixture for the no-captions branch asserting `strategy_used="deepgram_via_ytdlp_url"`.
<!-- AC:END -->
