---
id: task-148
title: Fix PodcastIndex resolver — still rejects Apple Podcasts URL with invalid_platform_url after task-138
status: Done
assignee: []
created_date: '2026-06-09 21:30'
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

Discovered while re-running E2E tests after task-138 was merged. task-138 was supposed to make the `/api/v1/podcasts/submit` endpoint **classify the URL host** before enqueueing (Apple Podcasts → `apple_podcasts`, Spotify → `spotify`, etc.). The endpoint code now does this (verified: `_classify_podcast_source_platform` at `media_summarizer/api/endpoints/podcasts.py:57`). **But the PodcastIndex resolver worker still rejects the URL with `invalid_platform_url`** — same error as before task-138.

So the fix on the producer side is in place, but the consumer side either ignores the new `source_platform` field or fails for a different reason (URL format, missing identifier, etc.).

## Symptom

`pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex` times out at `rss_resolving` (progress 10%).

CloudWatch `/aws/lambda/media-summarizer-worker-podcastindex_resolution`:

```
RuntimeError: Podcast URL could not be resolved. code=invalid_platform_url
  at podcastindex_resolution_worker.py:113 → _resolve_audio_url(body)
  at process_message:157
```

Stack trace shows `_resolve_audio_url(body)` raises this — exact same error message structure as before task-138.

## Root cause hypotheses (need investigation)

Three plausible causes; the agent picking up this task should grep the code to confirm:

1. **Consumer ignores `source_platform`**: the worker reads `body["normalized_url"]` but does NOT use `body["source_platform"]` (which task-138 added). The downstream classifier (`PodcastResolverErrorCode.INVALID_PLATFORM_URL` thrown in `core/media_ingestion/adapters/resolvers.py:91`) reclassifies via URL parsing alone and falls back to `unsupported` for some reason.
2. **Consumer expects different field name**: task-138 may have set `source_platform: "apple_podcasts"` but the consumer reads `body["platform"]` or expects an enum value like `"APPLE_PODCASTS"` (uppercase).
3. **Apple URL normalization actually fails**: even with the right `source_platform`, the URL `https://podcasts.apple.com/us/podcast/the-daily/id1200361736` may not match the `_APPLE_SHOW_ID_PATTERN` regex (line ~338 of `podcast_resolver_foundation.py`). Test the normalizer directly:
   ```python
   from media_summarizer.core.media_ingestion.adapters.podcast_resolver_foundation import normalize_podcast_source_url, SourcePlatform
   normalize_podcast_source_url(
     normalized_url="https://podcasts.apple.com/us/podcast/the-daily/id1200361736",
     source_platform=SourcePlatform.APPLE_PODCASTS
   )
   ```
   If this raises ValueError, it's the URL format. If it returns a descriptor, it's an issue further upstream.

## Reproduction

```bash
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex -v
```

Stays at `rss_resolving` 10%. Worker logs show `code=invalid_platform_url`.

## Investigation step (do FIRST)

```bash
# 1. Check what source_platform the producer emits
grep -nA3 "_classify_podcast_source_platform" media_summarizer/api/endpoints/podcasts.py | head -30

# 2. Check what the consumer reads
grep -nA10 "_resolve_audio_url\|source_platform" media_summarizer/workers/podcastindex_resolution_worker.py | head -40

# 3. Check the URL normalizer's regex for Apple
grep -nA10 "_APPLE_SHOW_ID_PATTERN\|_normalize_apple" media_summarizer/core/media_ingestion/adapters/podcast_resolver_foundation.py | head -30

# 4. Test the normalizer in isolation (running locally with .venv activated):
#    Use the owner-provided episode-level fixture — show_id=369369012,
#    episode_id=1000771893347 — so the test exercises the canonical path.
.venv/bin/python -c "
from media_summarizer.core.media_ingestion.adapters.podcast_resolver_foundation import normalize_podcast_source_url
from media_summarizer.core.media_ingestion.domain import SourcePlatform
print(normalize_podcast_source_url(
    normalized_url='https://podcasts.apple.com/fr/podcast/p%C3%A9pite-ils-ont-le-bracelet-ils-mangent-tout-az-d%C3%A9teste/id369369012?i=1000771893347',
    source_platform=SourcePlatform.APPLE_PODCASTS,
))
"
```

The output of step 4 will pinpoint the bug.

## Fix

Once root cause is identified, apply the targeted fix. Likely one of:
- Pass `source_platform` from message body into the resolver call (if consumer ignores it today)
- Align field names between producer and consumer
- Fix the Apple regex if the URL pattern has changed

## Out of scope

- Adding more platform support (Stitcher, Pocket Casts, etc.)
- Refactoring the resolver registry beyond fixing this bug
- Direct RSS feed URL support (the Daily test fixture would also work via RSS — separate concern)

## References

- task-138 (introduced URL classification on producer side; consumer side still broken)
- `media_summarizer/api/endpoints/podcasts.py:57, 268` (producer classification)
- `media_summarizer/workers/podcastindex_resolution_worker.py:113, 157` (consumer that rejects)
- `media_summarizer/core/media_ingestion/adapters/resolvers.py:91` (where INVALID_PLATFORM_URL is raised)
- `media_summarizer/core/media_ingestion/adapters/podcast_resolver_foundation.py:338` (Apple normalizer)
- CloudWatch `/aws/lambda/media-summarizer-worker-podcastindex_resolution` 2026-06-09 ~21:17 UTC
- `tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Investigation steps run; root cause documented in this task notes (which of the 3 hypotheses, with evidence)
- [ ] #2 Targeted fix applied (no over-engineering — only what addresses the root cause)
- [ ] #3 Lambda image rebuilt + `media-summarizer-worker-podcastindex_resolution` redeployed
- [ ] #4 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_podcast_via_podcastindex` passes (job reaches `completed`)
- [ ] #5 No regression on the 11 already-passing tests, especially `test_podcast_via_direct_audio_url` which uses the Deepgram path that the PodcastIndex resolver also routes to
<!-- AC:END -->
