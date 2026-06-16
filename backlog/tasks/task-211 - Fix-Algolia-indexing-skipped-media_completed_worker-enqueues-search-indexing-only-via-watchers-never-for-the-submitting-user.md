---
id: task-211
title: >-
  Fix Algolia indexing skipped: media_completed_worker enqueues search-indexing
  only via watchers, never for the submitting user
status: Done
assignee: []
created_date: '2026-06-15 16:56'
labels:
  - backend
  - bug
  - search
  - critical
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Symptom

Owner saved a YouTube video, transcript is generated and visible in the media detail screen. Searching a word from the transcript returns "No results found".

## Root cause

Verified via CloudWatch logs `/aws/lambda/media-summarizer-worker-media_completed_events`:

```
"No watchers for media key mkey_v1_8ebd115dd1ef95a105e6db6e36908e616f376a25e4735d84e365b5ffdfaa7c59"
```

`/aws/lambda/media-summarizer-worker-search_indexing` has **zero invocations** for the last 2h. The Algolia indexing message is never enqueued.

In `media_summarizer/workers/events/media_completed_worker.py`:

- Line 134-137: `watchers = await media_watchers.list_watchers(media_key)`. If empty, the handler returns early without indexing.
- Line 202-210: `_enqueue_search_indexing(...)` is called **inside** the `for w in watchers:` loop (line 154).

The `media_watchers` table only receives entries from `media_summarizer/core/services/media_submission.py:189`, and that call site is in the cross-user dedup branch (when `reserve_or_skip` returns False because another user already submitted the same `media_key`). The **submitting user (the owner of the new job) is never registered as a watcher** — they are tracked implicitly through `processing_jobs.user_id`. So for any first-time submission, `list_watchers` returns `[]` and the worker exits before reaching the Algolia enqueue.

This worked before task-205 centralized the enqueue: the previous indexing call sites in `deepgram_worker` and `document_parsing/worker` enqueued directly off the job's `user_id` from the processing event, regardless of watchers. Task-205 moved the enqueue into the watcher fan-out loop, which silently broke the primary-user path.

This is independent of task-208 (the URL ingestion migration) and task-210 (DynamoDB rename) — both of which are now correctly deployed. The bug is purely in the completion worker's control flow.

## Scope

Decouple Algolia indexing from the watcher loop. Indexing must happen for the submitting user (read from `processing_jobs.user_id` of the job that produced the event) **always**, plus once per watcher (current behavior, for cross-user dedup).

### File: `media_summarizer/workers/events/media_completed_worker.py`

1. **Move `_enqueue_search_indexing` out of the watcher loop and add a primary-user enqueue.** After computing `media_key`, fetch the canonical job that produced this completion event (the producer must include `media_item_id` / `job_id` in the event body — verify by reading the publishers; they all already attach a `job_id` or equivalent). Load it via `database_async.get_processing_job_by_id(...)`. If the job exists and has a `user_id`, call `_enqueue_search_indexing` once for that user, regardless of whether watchers exist.

2. **Keep the per-watcher enqueue** so cross-user dedup (when the same media_key is reused for another user) also indexes into that other user's index.

3. **Skip the early return when there are no watchers**, but only after the primary-user enqueue has had a chance to run. Effectively: do not let the `if not watchers: return` short-circuit the indexing.

4. **Deduplicate enqueues**: if the primary user is also in the watchers list (rare; would mean a user re-submitted their own media), the message should be sent once. Track enqueued user_ids in a `set`.

### Verification

After deploy:

1. Save a fresh YouTube video from the mobile app.
2. Tail `/aws/lambda/media-summarizer-worker-media_completed_events`: confirm a `search_indexing.enqueue` message (or success log) is emitted with `user_id` set, even when "No watchers" is logged.
3. Tail `/aws/lambda/media-summarizer-worker-search_indexing`: confirm an invocation occurs and Algolia indexing succeeds.
4. In the mobile app, search a word from the transcript: results should appear.

## What NOT to do

- Do **not** start adding the submitting user as a watcher — `media_watchers` is for cross-user fan-out; conflating roles will create dedup/billing bugs (each watcher has its own `job_id` and minute hold).
- Do **not** index from the producer workers (deepgram, document_parsing, youtube, …) — task-205's centralization is the right design; the bug is just that the join point picked the wrong loop.
- Do **not** require `transcription_s3_key` to be present to enqueue summaries-only items: keep the existing `_enqueue_search_indexing` skip behavior (it logs `search_indexing.skipped` with the missing field — that's correct).

## Notes for the implementer

- Producers that publish `episode_completion_status`: deepgram, document_parsing, youtube_ingestion (native + apify), tiktok, instagram, x, article_extraction, podcastindex_resolution. Confirm each one already includes the `job_id` (or `media_item_id`) in the event body — this is what the worker uses to look up the primary user.
- Existing tests for this worker live in `tests/workers/test_media_completed_worker.py` (or similar). Update / add a test that asserts `_enqueue_search_indexing` is called when `watchers == []` but the event references a valid job.
- Once fixed, also reflect this in the architectural intent in the docstring at the top of `media_completed_worker.py` so the next refactor doesn't regress the same way.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 media_completed_worker enqueues search-indexing for the submitting user (resolved from the event's job_id / media_item_id) regardless of whether the watchers list is empty
- [ ] #2 Per-watcher enqueue is preserved for cross-user dedup; same user_id is never enqueued twice for one event (dedup via a set of enqueued user_ids)
- [ ] #3 The early return on empty watchers no longer prevents the primary-user indexing enqueue
- [ ] #4 After deploy: saving a fresh YouTube video produces a successful invocation of media-summarizer-worker-search_indexing in CloudWatch (verified end-to-end)
- [ ] #5 After deploy: searching a word from the transcript in the mobile app returns the saved item (Algolia per-user index populated)
- [ ] #6 Unit test added: media_completed_worker calls _enqueue_search_indexing once when watchers is [] and the event references a job with a user_id
- [ ] #7 Unit test added: when watchers contains the submitting user, the user is indexed only once (not twice)
- [ ] #8 No producer-side enqueue logic re-introduced in deepgram/document_parsing/youtube/tiktok/instagram/x/article/podcastindex workers
<!-- AC:END -->
