---
id: task-280
title: >-
  Allow the same media to be saved several times by the same user while keeping
  transcription globally deduplicated
status: To Do
assignee: []
created_date: '2026-08-17 22:20'
labels:
  - ingestion
  - backend
dependencies:
  - task-279
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem

A user cannot save the same media twice — for instance to file it in two different collections. The library row id is derived from the content and the user:

```
build_media_item_id(user_id, media_key) = "mi_" + sha256(f"{user_id}|{media_key}")[:32]
```

(`core/models/user_media.py:73`), and the row is written with `create_if_absent` (`durable_media_service.py:175`). A second save of the same URL therefore converges on the **same single row** — and because the write is conditional, the folder and tags requested on that second save are silently dropped. The user sees a save that reports success and changes nothing.

This is a deliberate property of the current model ("idempotent by construction... re-saving the same content converges on the same single row instead of creating a duplicate"), and it is the property that has to change.

## What must not change

Deduplication of the **pipeline** stays: the same media must never be transcribed, nor paid for, twice. Idempotence is global across users, keyed by `media_key`, and that stays as it is.

The rule is therefore a separation of two things the current model conflates: *what was processed* (one entity per `media_key`, global) and *what a user saved* (one row per save, with its own folder and tags).

## Scope

A save creates its own library row. `media_item_id` becomes the id of a save, not a function of `(user_id, media_key)`; several rows for one user may share a `media_key`. Folder and tags belong to the row, so two saves of the same URL land in two collections independently, and deleting one does not touch the other.

The reads must follow: a row addresses its content by `media_key` rather than through a job that only the first save owns. That is what makes the deduplicated save — including one deduplicated against **another user's** job — able to show its transcript, which task-279 explicitly left open.

Generated artifacts follow the content, not the row: a second save of an already-processed media must not regenerate or re-bill any artifact, and both rows must surface the same ones.

## Legacy to delete, not to support

Some rows predate the derived id: the task-241 backfill kept the legacy **job id** as `media_item_id`, which is why `resolve_job_for_record` carries a branch for ids that do not start with `mi_` (`durable_media_service.py:260`). On dev this produces exactly the confusing state observed on 2026-08-17 — two rows for the same `media_key`, one legacy and ready, one derived and empty.

Nothing is deployed and there is no installed base: these rows and that branch are deleted in this task, not migrated or supported alongside the new shape.

## Notes to the owner

- DEPLOY CHECK — after merge, save the same YouTube video twice into two different collections and confirm two entries appear, each in its own collection, both showing the same transcript, and that only the first one triggered a provider run.
- Quota is deliberately out of scope here: not debiting a user twice for content they already hold is the follow-up task.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A library row id is no longer a function of (user_id, media_key): two saves of the same URL by the same user produce two distinct rows
- [ ] #2 build_media_item_id and the create_if_absent convergence behaviour are deleted rather than kept behind a flag or a fallback
- [ ] #3 Folder and tags requested on a save are always applied to that save's own row, including when the same media is already in the user's library under another folder
- [ ] #4 Deleting one of several rows sharing a media_key leaves the others readable and does not purge the shared content
- [ ] #5 A row resolves its transcript through its media_key rather than through a job it does not own, so a save deduplicated against another user's job displays the same content
- [ ] #6 A save deduplicated against existing content creates no new processing job and triggers no provider call
- [ ] #7 Generated artifacts are resolved by content, so a second save of an already-processed media regenerates nothing and both rows surface the same artifacts
- [ ] #8 The task-241 legacy rows whose media_item_id is not prefixed mi_ are deleted from user_media-dev, and the resolve_job_for_record branch that exists to support them is removed
- [ ] #9 The two YouTube rows sharing media_key mkey_v1_9f75a099… in user_media-dev are reduced to a single coherent state, verified by querying the table with the AWS CLI
- [ ] #10 ruff and mypy are clean, and terraform validate plus terraform plan exit 0 for the dev env if any infrastructure is touched
<!-- AC:END -->
