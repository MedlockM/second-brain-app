---
id: task-308
title: Stop purging a shared cover object when other saves still reference it
status: To Do
assignee: []
created_date: '2026-08-20 19:38'
labels:
  - backend
  - ingestion
  - cleanup
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

`mirror_job` (`media_summarizer/core/services/durable_media_service.py:422`) fans `thumbnail_url` out to **every** `user_media` row sharing the job's `media_key`, across all owners — the loop at the end of the function deliberately updates rows whose `record.user_id != job.user_id` (only `last_job_id` is withheld). So when a cover has been re-hosted, the resulting `s3://` locator is a value several rows point at, exactly like the transcript.

`purge_media_item` (`media_summarizer/workers/cleanup/media_lifecycle.py:163`) does not treat it that way. It already guards the transcript and the job objects behind the `references` list computed just above, but deletes the cover unconditionally, on the strength of a comment whose premise is false:

```
# A re-hosted cover belongs to this one save, so it goes unconditionally --
# unlike the transcript, which other saves of the same content still read.
```

A re-hosted cover does not belong to one save. As soon as two rows share a `media_key`, the first one to purge deletes the S3 object the others still render from, and they are left with a locator pointing at nothing.

This is a data-model defect, not a scale problem: the cross-owner fan-out is in the code today, and the same failure occurs with a single owner saving the same content twice.

## Scope

Bring the cover under the same reference guard the transcript already uses, and fix the comment so it states the actual invariant.

The invariant to hold: an S3 cover object is deleted only when no other `user_media` row still points at it. The rows returned by `list_by_media_key(..., include_deleted=True)` are the rows still present in the table; soft-deleted ones purge later on their own TTL, and whichever purges last is the one that removes the object — so gating on the existing non-empty `references` check does not leak the object.

Note that a cover locator is not always shared: `parse_cover_locator` returning nothing (a hotlinked URL) still has nothing to delete, and that branch stays as-is (task-304).

## Owner note (not an acceptance criterion)

The behaviour is only observable after the cleanup worker image is redeployed on push to `main`. Worth confirming afterwards by saving the same reel twice on dev, soft-deleting one save, letting the TTL cascade run, and checking the surviving row's thumbnail still resolves.

## References

- Fan-out: `media_summarizer/core/services/durable_media_service.py` (`mirror_job`, `mirror_attributes`).
- Purge: `media_summarizer/workers/cleanup/media_lifecycle.py` (`purge_media_item`).
- Cover deletion primitive: `media_summarizer/core/services/cover_capture.py` (`delete_cover`, `parse_cover_locator`).
- Cover storage contract: task-304.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 purge_media_item deletes a re-hosted cover object only when no other user_media row still references it, using the same reference set that already guards the transcript and job objects
- [ ] #2 A cover whose stored value is a hotlinked URL still takes the no-op path and reports no deletion, unchanged from task-304
- [ ] #3 The comment above the cover-deletion branch states the real invariant (the locator is shared across every save of the same media_key) instead of claiming the cover belongs to a single save
- [ ] #4 The counts dictionary returned by purge_media_item distinguishes the skipped-because-shared case from the deleted case, so the cleanup batch summary does not report a deletion that did not happen
- [ ] #5 ruff and mypy are clean on media_summarizer/workers/cleanup/media_lifecycle.py
<!-- AC:END -->
