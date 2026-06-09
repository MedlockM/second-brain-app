---
id: task-133
title: Fix 4 source bugs blocking Phase 4 completion (TikTok mark_extracting, document circular import, podcast fixture, Instagram empty transcript)
status: To Do
assignee: []
created_date: '2026-06-09 14:00'
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

Discovered while flipping the remaining `tests/e2e/test_phase4_other_sources.py` skeletons from `skip` to active E2E. Article + 4 artifacts + YouTube + X are all green. The four other declared V1 sources each fail for a different distinct reason.

Test run summary on 2026-06-09 (E2E suite, AWS dev):

```
✅ test_health_endpoint_returns_200
✅ test_ingest_article_url_returns_202
✅ test_article_reaches_completed
✅ test_artifact_summary_e2e
✅ test_artifact_notes_e2e
✅ test_artifact_flashcards_e2e
✅ test_artifact_quiz_e2e
✅ test_youtube_ingestion
✅ test_x_ingestion              (Jack's first tweet, text-only via X API)
❌ test_tiktok_ingestion         (Bug 1)
❌ test_instagram_ingestion      (Bug 4)
❌ test_document_upload          (Bug 3)
❌ test_podcast_via_direct_audio_url   (Bug 2)
⏭ test_podcast_via_podcastindex (skip, helper not adapted yet)
```

## Bug 1 — TikTok worker calls `ProcessingJob.mark_extracting()` (does not exist)

`media_summarizer/workers/tiktok_ingestion_worker.py:757` calls `job.mark_extracting()`. The Pydantic model `ProcessingJob` has no such method. Stack trace:

```
AttributeError: 'ProcessingJob' object has no attribute 'mark_extracting'
  at tiktok_ingestion_worker.py:757
```

Probable origin: this is a sibling pattern to `mark_summarizing()` audited and removed in task-125. The TikTok worker still references the old lifecycle method even though it's not in the model. Need to either:
- Add `mark_extracting()` to `ProcessingJob` (with a corresponding `JobStatus.EXTRACTING` if appropriate), OR
- Replace the call with `update_status(JobStatus.<existing-state>)` that maps to the desired phase, OR
- Remove the call entirely if the lifecycle update isn't needed for V1 (artifacts are on-demand, the job-level status is mostly cosmetic now).

Reference: this is the 4th bug of the same class (caller assumes a method exists that doesn't): cf. task-120 `extraction_metadata`, task-122 `artifact_id` contract, task-123 `mark_summarizing` migration.

## Bug 2 — Podcast direct-audio-URL test: Deepgram empty transcript

The test uses `https://www.learningcontainer.com/wp-content/uploads/2020/02/Kalimba.mp3` (a 5s instrumental music clip). Deepgram returns successfully but the transcript is empty (no spoken words):

```
"event": "transcription.failed"
"error_code": "deepgram_non_retryable"
"detail": "Deepgram transcript is empty"
```

The fixture is wrong, not the code. Replace with a public 5-10s **spoken-word** MP3. Suggestions:
- A short spoken-word audio from archive.org (search for `mediatype:audio AND language:eng AND year:2020s` with `<10s` runtime).
- A custom-generated TTS clip uploaded to S3 dev bucket.
- A 5-10s extract from a Creative Commons podcast trailer.

Decide on a strategy that's stable (no link rot risk for ≥1 year). Update the test URL and re-run.

## Bug 3 — Document worker: circular import `InstagramApifyResolver` ↔ `llamaparse_resolver`

```
ImportError: cannot import name 'InstagramApifyResolver' from partially initialized module
'media_summarizer.infrastructure.resolvers.instagram_apify_resolver'
(most likely due to a circular import)

  document_parsing/worker.py:32 imports llamaparse_resolver
    -> infrastructure/resolvers/__init__.py:3 imports instagram_apify_resolver
      -> instagram_apify_resolver.py:45 imports core.media_ingestion.domain
        -> core/media_ingestion/__init__.py:37 imports .wiring
          -> wiring.py:18 imports infrastructure/resolvers/instagram_apify_resolver
            -> back at start, partially initialized
```

Looks like task-127 (Apify per-account split) added the Instagram resolver to `__init__.py`'s eager exports, creating a cycle through `core.media_ingestion.wiring`.

Fix candidates:
- Remove the eager re-export from `infrastructure/resolvers/__init__.py` and require callers to do explicit `from media_summarizer.infrastructure.resolvers.instagram_apify_resolver import InstagramApifyResolver`.
- Move the cycle-causing import inside a function body or behind a `TYPE_CHECKING` guard.
- Restructure `core.media_ingestion.wiring` to not pull in concrete resolvers at module load.

The first option is the cheapest and matches the practice already used elsewhere (most files import resolvers by full path, not via the package).

## Bug 4 — Instagram: Apify transcript empty → Deepgram empty too

The Reel `https://www.instagram.com/reel/CtMSAg9JqWZ/` was processed:
- Apify resolver succeeded (no error)
- The native transcript field was either absent or empty
- Worker fell back to Deepgram on the downloadedVideo URL
- Deepgram returned an empty transcript ("Deepgram transcription failed with non-retryable error")

Two distinct possible causes:
1. The Reel has no spoken audio (instrumental music) — same root cause as Bug 2. Need a Reel fixture with English speech.
2. The downloadedVideo URL Apify returned has expired (Apify CDN URLs are short-lived; if the test is dispatched 5 minutes after Apify generated the URL, Deepgram may get a 403/404 on download).

Pick a different Reel (must have spoken English content). If the second cause is real, the worker should re-fetch from Apify in case of expired URL — separate concern.

## Reproduction

```bash
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_tiktok_ingestion -v
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_podcast_via_direct_audio_url -v
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_document_upload -v
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_instagram_ingestion -v
```

Each fails for a different reason described above. CloudWatch logs are in `/aws/lambda/media-summarizer-worker-{tiktok_ingestion,document_parsing,deepgram_transcription}` for the period 2026-06-09 13:40-14:00 UTC.

## Out of scope

- Auditing all callers of removed `JobStatus.*` methods more broadly (separate cleanup task)
- Refactoring the resolver wiring system (separate architecture task)
- Adding a re-fetch on expired Apify URLs (separate resilience task)

## References

- task-120, task-122, task-123, task-125 (sibling bugs of the same class)
- task-127 (Apify per-account split, likely introduced the circular import)
- task-129 (YouTube migration, established the Apify-based pattern)
- `tests/e2e/test_phase4_other_sources.py` (the failing tests)
- `media_summarizer/workers/tiktok_ingestion_worker.py:757`
- `media_summarizer/workers/document_parsing/worker.py:32`
- `media_summarizer/infrastructure/resolvers/__init__.py:3`
- CloudWatch logs `/aws/lambda/media-summarizer-worker-{tiktok_ingestion,document_parsing,deepgram_transcription}` 2026-06-09 13:40-14:00 UTC
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Bug 1 (TikTok `mark_extracting`) fixed — decision recorded (add method / replace call / remove call)
- [ ] #2 Bug 2 (podcast empty transcript) fixed by replacing the fixture URL with a stable short spoken-word MP3 (≤ 10s)
- [ ] #3 Bug 3 (document circular import) fixed in `infrastructure/resolvers/__init__.py` (or wherever the cycle originates)
- [ ] #4 Bug 4 (Instagram empty transcript) fixed — either a Reel with spoken English content is picked, or the worker is hardened against expired Apify URLs (decision recorded)
- [ ] #5 Lambda image rebuilt + redeployed for affected workers
- [ ] #6 `pytest -m e2e` shows all 13 declared tests passing (only `test_podcast_via_podcastindex` may stay skipped pending helper adaptation)
- [ ] #7 No regression on the 9 already-passing tests
<!-- AC:END -->
