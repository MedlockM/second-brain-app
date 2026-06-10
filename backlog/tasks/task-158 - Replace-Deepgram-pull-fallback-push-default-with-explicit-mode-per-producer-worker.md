---
id: task-158
title: Replace Deepgram pull→push automatic fallback with explicit mode declared by producer workers
status: To Do
assignee: []
created_date: '2026-06-10 01:00'
labels:
  - backend
  - performance
  - ingestion
dependencies: []
priority: medium
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

task-139 introduced an automatic Deepgram fallback: when pull-mode (we send a URL, Deepgram fetches it) hits a 403 from the source CDN, the worker downloads the audio in Lambda and pushes the binary to Deepgram in push-mode.

**Problem**: this automatic fallback adds latency for sources where pull-mode is **known to fail systematically** (TikTok CDN, Instagram CDN, X video CDN). Today every Instagram or TikTok ingestion pays a ~5-10s pull-attempt timeout before falling back to push. The retry is wasted — we already know it won't work.

**Owner decision 2026-06-10**: replace the automatic fallback with **explicit `deepgram_mode` declared by the producer worker**, with one targeted exception (see below).

## Architecture change

### Before (today)

```python
# Any worker enqueues to Deepgram queue:
sqs.send_message(queue=DEEPGRAM_QUEUE, body={
    "audio_url": cdn_url,
    ...
})

# Deepgram worker:
try:
    transcribe_url(audio_url)  # try pull
except DeepgramRemoteContentError403:
    download_audio(audio_url)
    transcribe_file(binary)  # fallback push
```

### After (this task)

```python
# Worker declares the mode based on the source:
sqs.send_message(queue=DEEPGRAM_QUEUE, body={
    "audio_url": cdn_url,
    "deepgram_mode": "push",  # or "pull" or "pull_with_push_fallback"
    ...
})

# Deepgram worker:
mode = body.get("deepgram_mode", "pull")
if mode == "push":
    download_audio(audio_url); transcribe_file(binary)
elif mode == "pull":
    transcribe_url(audio_url)  # if 403, fail loudly — producer guessed wrong
elif mode == "pull_with_push_fallback":
    try: transcribe_url(audio_url)
    except DeepgramRemoteContentError403:
        download_audio(audio_url); transcribe_file(binary)
```

## Per-producer routing

| Producer worker / endpoint | `deepgram_mode` | Rationale |
|---|---|---|
| `tiktok_ingestion_worker` | `"push"` | TikTok CDN blocks Deepgram (validated empirically task-139) |
| `instagram_ingestion_worker` (Apify→Deepgram fallback path) | `"push"` | Instagram CDN blocks Deepgram (validated empirically — `deepgram_pending_cdn_fallback` log marker fires every time today) |
| `x_ingestion_worker` (video tweet path, when wired) | `"push"` | X video CDN expected to block (same anti-bot family). Set `"push"` to match the behavior of the other social-network sources; reconsider if empirical evidence shows X allows Deepgram. |
| `podcastindex_resolution_worker` (after resolving the audio URL) | `"pull"` | Podcast hosts (libsyn, simplecast, megaphone, anchor.fm, etc.) historically have open CDNs. If a specific host blocks Deepgram in the future, surface as `failed` job and create a follow-up task — don't silently retry. |
| `POST /api/media/upload-audio` (per task-142) | `"pull"` | We hand Deepgram an S3 pre-signed URL. S3 doesn't block Deepgram. |
| `POST /api/media/ingest-url` with `.mp3` URL (user-pasted) | `"pull_with_push_fallback"` | Source unknown — could be a friendly host (archive.org) or a hostile CDN. The fallback is justified here because we can't predict. |
| `POST /api/v1/podcasts/submit` with direct `.mp3` URL | same as above (`pull_with_push_fallback`) | Same reason: unknown source. |

## Out of scope

- Streaming Deepgram (websocket) — V1 uses batch
- Audio format conversion before push-mode (Deepgram supports common formats natively)
- Refactoring the broader transcription pipeline beyond the mode-routing change

## Implementation notes

1. Add a new message body field `deepgram_mode` (string enum: `"pull" | "push" | "pull_with_push_fallback"`). Default is `"pull"` for backward compatibility — but every producer in the table above must set it explicitly.
2. Refactor `media_summarizer/workers/transcription/deepgram_worker.py` to dispatch on `deepgram_mode`. The current automatic try/except remains, but only fires when `mode == "pull_with_push_fallback"`.
3. Update each producer worker / endpoint listed above to set the field. Audit grep:
   ```bash
   grep -rnE "DEEPGRAM_TRANSCRIPTION_QUEUE|deepgram-transcription-queue" \
     media_summarizer/workers/ media_summarizer/api/endpoints/
   ```
4. For each call site, add `"deepgram_mode": "<value>"` to the message body per the table above.
5. Add a log warning if the worker receives a Deepgram message with no `deepgram_mode` field (helps catch missed call sites).
6. **Performance assertion**: after the change, an Instagram or TikTok ingestion should reach `completed` ~5-10s faster than today (no wasted pull attempt).

## E2E impact

After deployment, re-run the full E2E suite. The 13 currently-passing tests should still pass:

- TikTok happy path (uses native captions, no Deepgram path) → unchanged
- TikTok with no captions (when fixture exists, e.g. via task-149 fallback test) → faster, push-mode direct
- Instagram → faster (no wasted pull attempt)
- Podcast PodcastIndex → unchanged (still pull)
- Podcast direct audio URL → unchanged (still pull, archive.org friendly)
- All others → unchanged

The fallback E2E test added by task-152 (Deepgram pull→push) needs to be updated:
- It currently triggers the automatic fallback by submitting a TikTok URL.
- After this task, that path no longer exists for TikTok (it'd go directly to push).
- Adapt the test to either submit a `pull_with_push_fallback` message manually, OR document that the fallback is only exercised on user-pasted URLs and pick a fixture URL that triggers it.

## Constraints

- Do NOT change Deepgram credentials, region, or any AWS infra
- Do NOT change the SQS queue itself; this is a message-body schema addition
- Backward-compat: messages with no `deepgram_mode` field continue to work (default = `"pull"`); this lets the rollout be a single Lambda image redeploy without queue draining

## References

- task-139 (introduced the current automatic pull→push fallback)
- task-152 (E2E test for the current automatic fallback path; needs update after this task)
- task-142 (audio file upload endpoint — must set mode `pull`)
- V1 launch plan §0 (declares all V1 sources)
- `media_summarizer/workers/transcription/deepgram_worker.py`
- `media_summarizer/workers/tiktok_ingestion_worker.py`
- `media_summarizer/workers/instagram_ingestion_worker.py`
- `media_summarizer/workers/x_ingestion_worker.py`
- `media_summarizer/workers/podcastindex_resolution_worker.py`
- `media_summarizer/api/endpoints/media.py` (`POST /upload-audio`, `POST /ingest-url`)
- `media_summarizer/api/endpoints/podcasts.py` (`POST /podcasts/submit`)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Deepgram worker dispatches on `deepgram_mode` field with the 3 modes (`pull`, `push`, `pull_with_push_fallback`); default = `pull` for backward compat
- [ ] #2 TikTok / Instagram / X video producers set `deepgram_mode=push` in every message
- [ ] #3 PodcastIndex resolver + audio upload endpoint set `deepgram_mode=pull`
- [ ] #4 User-pasted `.mp3` URL paths (ingest-url + podcasts/submit) set `deepgram_mode=pull_with_push_fallback`
- [ ] #5 Audit grep confirms every Deepgram queue producer sets the mode explicitly
- [ ] #6 task-152's E2E test (Deepgram pull→push fallback) updated to match the new architecture
- [ ] #7 Lambda image rebuilt + redeployed; all 13 passing E2E tests still pass
- [ ] #8 Empirical confirmation (CloudWatch timing or test wall-clock) that Instagram / TikTok ingestion is ~5-10s faster than before the change
- [ ] #9 No silent failures — `pull` mode that hits 403 fails the job loudly (not a silent retry); error_message includes the producer that misrouted
<!-- AC:END -->
