---
id: task-138
title: Fix /api/v1/podcasts/submit — endpoint hardcodes source_platform=rss instead of classifying Apple/Spotify URLs
status: Done
assignee: []
created_date: '2026-06-09 16:50'
updated_date: '2026-06-09'
labels:
  - bug
  - backend
  - ingestion
dependencies: []
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Discovered during E2E re-run on the Podcast pipeline test (`test_podcast_via_podcastindex`). The endpoint that's supposed to support Apple Podcasts / Spotify / Deezer URLs as input (per the V1 launch plan §0) silently treats every non-audio URL as a generic RSS feed, breaking platform-specific resolution.

## Symptom

`pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex` times out (or the job lands in `failed`).

CloudWatch `/aws/lambda/media-summarizer-worker-podcastindex_resolution`:

```
"message": "RSS URL has no explicit feed hint, trying direct feed resolution: https://podcasts.apple.com/us/podcast/the-daily/id1200361736"
"message": "Worker handler failed for message ...: Podcast URL could not be resolved. code=invalid_platform_url"
```

The Apple Podcasts URL is fetched as if it were an RSS feed (it returns HTML, not XML), feed parsing fails, and the resolver gives up with `invalid_platform_url`.

## Root cause

`media_summarizer/api/endpoints/podcasts.py:241-254`:

```python
else:
    # Non-audio URL path: resolve enclosure URL first, then route to Deepgram.
    # Pass feed_url so the resolution worker can provide it for RSS transcript lookup.
    await sqs.send_message(
        queue_name=PODCASTINDEX_RESOLUTION_QUEUE,
        message_body={
            "job_id": job.id,
            "user_email": user.email,
            "user_id": user.id,
            "normalized_url": submitted_url,
            "feed_url": submitted_url,
            "source_platform": "rss",  # <-- HARDCODED, ignores actual platform
        },
    )
```

The endpoint hardcodes `source_platform: "rss"` regardless of the URL host. The downstream PodcastIndex resolver uses `source_platform` to pick the platform-specific normalizer (`_normalize_apple`, `_normalize_spotify`, `_normalize_deezer`, or generic RSS). With "rss" it skips the Apple normalizer entirely and tries to fetch the Apple HTML page as XML.

The infrastructure is in place to support Apple/Spotify/Deezer (cf. `media_summarizer/core/media_ingestion/adapters/podcast_resolver_foundation.py:201-245`) — the endpoint just doesn't classify the URL before enqueueing.

## Fix

1. In `podcasts.py:241-254`, classify the URL host **before** building the SQS message:
   - `podcasts.apple.com` → `source_platform = "apple_podcasts"`
   - `open.spotify.com` → `source_platform = "spotify"`
   - `deezer.com` → `source_platform = "deezer"`
   - else → `source_platform = "rss"` (current default for raw RSS feed URLs)
2. There may already be a helper for this — search for `SourcePlatform.APPLE_PODCASTS` usage and any URL→platform mapper.
3. Optionally: also consider routing direct audio (`.mp3`/`.m4a`/etc.) URLs through the audio path automatically inside `/podcasts/submit` if `_looks_like_audio_url` doesn't already cover everything. (Not in scope unless the fix above creates a regression.)
4. Test against fixture URLs from each platform:
   - `https://podcasts.apple.com/us/podcast/the-daily/id1200361736`
   - `https://open.spotify.com/show/3IM0lmZxpFAY7CwMuv9H4g`
   - A direct RSS feed URL (e.g. `https://feeds.simplecast.com/54nAGcIl`)

## Reproduction

```bash
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex -v
```

## Out of scope

- Other source-specific bugs (TikTok episode_url, Instagram queue, document Algolia key, podcast Decimal) — separate tasks 134, 135, 136, 137
- Adding new platform support (Pocket Casts, Overcast, etc.) — V1 only declares Apple/Spotify

## References

- `media_summarizer/api/endpoints/podcasts.py:241-254` (offending hardcoded value)
- `media_summarizer/core/media_ingestion/adapters/podcast_resolver_foundation.py` (platform normalizers)
- V1 launch plan §0 (Podcasts via PodcastIndex resolver)
- `tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex`
- CloudWatch `/aws/lambda/media-summarizer-worker-podcastindex_resolution` 2026-06-09 ~16:50 UTC
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `/api/v1/podcasts/submit` classifies URL host before enqueue (Apple/Spotify/Deezer/RSS)
- [ ] #2 Apple Podcasts URL submission reaches the PodcastIndex Apple resolver branch (not the generic RSS path)
- [ ] #3 Lambda image rebuilt + `media-summarizer-api` redeployed
- [ ] #4 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex` passes (job reaches `completed`, transcript on S3)
- [ ] #5 No regression on the 9 already-passing tests, including any other test that hits `/api/v1/podcasts/submit`
<!-- AC:END -->
