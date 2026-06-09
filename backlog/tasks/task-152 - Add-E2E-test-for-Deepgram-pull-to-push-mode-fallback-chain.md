---
id: task-152
title: Add E2E test for Deepgram pull-mode → push-mode fallback chain
status: To Do
assignee: []
created_date: '2026-06-09 22:30'
labels:
  - testing
  - tech-debt
  - deepgram
dependencies:
  - task-139
priority: medium
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

**task-139** introduced a Deepgram fallback: when Deepgram's pull-mode (we send a URL, Deepgram fetches it) hits a 403 from the source CDN, the worker downloads the audio in Lambda and pushes the binary to Deepgram instead.

The current happy-path tests use audio URLs from S3 / archive.org which Deepgram fetches without issue — pull-mode succeeds, push-mode never fires. A regression on push-mode would only surface when a real user submits content from a CDN-blocked source (TikTok CDN, some podcast hosts).

This task adds an E2E test that **deliberately picks a CDN-blocked URL** to force the push-mode path.

## What to add

A new test in `tests/e2e/test_fallback_chains.py`:

```python
@pytest.mark.e2e
async def test_deepgram_pushmode_fallback(
    http_client: httpx.AsyncClient,
    auth_headers: Dict[str, str],
) -> None:
    """Deepgram pull-mode 403 → push-mode binary upload succeeds.

    Triggered by a TikTok URL whose CDN refuses Deepgram's IPs.
    The TikTok worker hands Deepgram a CDN URL; pull-mode fails;
    Lambda downloads the audio and re-submits via push-mode.
    """
    media_item_id = await _ingest_and_wait(
        http_client, auth_headers,
        "<TBD: TikTok URL with no native captions, CDN-blocked for Deepgram>",
        timeout_s=60,
    )
    detail = await _get_media_item(http_client, auth_headers, media_item_id)
    assert detail.get("transcription_metadata", {}).get("deepgram_mode") == "push", \
           f"expected push-mode marker, got: {detail}"
```

## Picking the fixture

The trigger is double:
1. The TikTok video has NO native auto-captions (forces Deepgram fallback)
2. The TikTok CDN URL handed to Deepgram returns 403 to Deepgram's IPs (forces push-mode)

Both conditions are non-trivial:
- Condition #1: pick a music-only TikTok or one in a language Deepgram can't handle (rare). Or override Deepgram options to not parse a captions field.
- Condition #2: most TikTok CDN URLs reject Deepgram per task-139's empirical observation. So if condition #1 holds, condition #2 should automatically hold.

Investigation step before writing the test:
1. Find a TikTok URL with spoken English audio but no auto-captions
2. Submit through the worker; observe in CloudWatch which Deepgram mode fires
3. Lock that URL as the fixture

If no stable URL is found, mock the Deepgram pull-mode response with a 403 in the worker for this specific test (less E2E-pure but reliable).

## Cost

- yt-dlp from Lambda: free
- Lambda audio download: free
- Deepgram push-mode: ~$0.005 (TikTok ≤ 3 min)
- Total ~$0.01 per run

## Out of scope

- Other source fallback chains (separate tasks 149, 150, 151)
- New Deepgram modes (streaming WebSocket etc.)
- Audio format conversion before push-mode

## References

- task-139 (push-mode fallback implementation)
- task-140 / task-144 (TikTok IP-block context — both yt-dlp AND Deepgram path are CDN-affected)
- `media_summarizer/workers/transcription/deepgram_worker.py`
- `tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion` (happy path baseline)
- `tests/e2e/test_phase4_other_sources.py::test_podcast_via_direct_audio_url` (URL-mode happy path with archive.org)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 New test `test_deepgram_pushmode_fallback` added in `tests/e2e/test_fallback_chains.py`
- [ ] #2 Fixture URL chosen and documented (rationale for why pull-mode fails, push-mode succeeds)
- [ ] #3 Test asserts BOTH `status == "completed"` AND a metadata marker proving push-mode (not pull-mode) was used
- [ ] #4 If the metadata field doesn't exist, `GET /api/media/{id}` (or its `transcription_metadata` block) is extended to expose `deepgram_mode`
- [ ] #5 Wall-clock < 60s
- [ ] #6 No regression on existing audio happy-path tests (article, podcast direct, TikTok happy)
<!-- AC:END -->
