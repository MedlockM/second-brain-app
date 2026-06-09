---
id: task-137
title: Fix Deepgram worker — Float types not supported. Use Decimal types instead. (DynamoDB write after transcription)
status: To Do
assignee: []
created_date: '2026-06-09 16:50'
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

Discovered during E2E re-run after task-133 was merged. The `test_podcast_via_direct_audio_url` test now reaches Deepgram successfully (LibriVox MP3 fixture URL is accepted, Deepgram returns a transcript), but the worker crashes immediately after when persisting state to DynamoDB.

## Symptom

`pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_podcast_via_direct_audio_url` times out (job never reaches `completed`).

CloudWatch `/aws/lambda/media-summarizer-worker-deepgram_transcription`:

```
"event": "external_call.succeeded"
"message": "Deepgram request succeeded"

# Then immediately after:
"message": "Worker handler failed for message ...: Float types are not supported. Use Decimal types instead."
```

## Root cause

DynamoDB's Python SDK (boto3 / aioboto3) refuses to write Python `float` values — they must be converted to `decimal.Decimal` first. Some field written by the worker after Deepgram succeeds (probably `audio_duration_seconds` or `confidence` or `processing_duration` from the Deepgram response) is a Python `float`, not `Decimal`.

Likely culprits in the post-Deepgram code path:
- The Deepgram response includes a `confidence` float per word and a `duration` float for the whole audio
- `audio_duration_seconds` written to `processing_jobs` for the minute pool finalization
- Any field added since the migration that didn't go through the Decimal-conversion helper

The pattern across the codebase is to convert via `decimal.Decimal(str(float_value))` or use a generic helper (`media_summarizer/utils/dynamodb_decimal.py` — verify exists).

## Fix

1. Locate the exact write that triggers the error. The stack trace in CloudWatch (full one, not just the message) will point to the line.
2. Wrap the offending value(s) with `Decimal(str(...))` or route through the existing helper.
3. Audit other workers (X, TikTok, summarization, etc.) for the same pattern — any place that takes a Deepgram numeric field and writes to DynamoDB without Decimal conversion is a latent bug.
4. Rebuild + redeploy `media-summarizer-worker-deepgram_transcription` Lambda.

## Reproduction

```bash
.venv/bin/pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_podcast_via_direct_audio_url -v
```

## Out of scope

- Other source-specific bugs (TikTok episode_url, Instagram queue, document Algolia key, podcast PodcastIndex routing) — separate tasks 134, 135, 136, 138

## References

- `media_summarizer/workers/transcription/deepgram_worker.py` (likely location of the offending write)
- `media_summarizer/utils/dynamodb_decimal.py` (if it exists; helper for Decimal conversion)
- `tests/e2e/test_phase4_other_sources.py::test_podcast_via_direct_audio_url`
- CloudWatch `/aws/lambda/media-summarizer-worker-deepgram_transcription` 2026-06-09 ~14:50 UTC
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Exact line of the offending DynamoDB write identified and documented in this task
- [ ] #2 Fix applied: float values converted to Decimal before persistence
- [ ] #3 Audit performed on other workers writing Deepgram/numeric fields to DynamoDB; follow-up task created for any other latent occurrences
- [ ] #4 Lambda image rebuilt + `media-summarizer-worker-deepgram_transcription` redeployed
- [ ] #5 `pytest -m e2e tests/e2e/test_phase4_other_sources.py::test_podcast_via_direct_audio_url` passes (job reaches `completed`, transcript on S3)
- [ ] #6 No regression on the 9 already-passing tests
<!-- AC:END -->
