---
id: task-220
title: >-
  Migrate media library, Search, and folder workflows to the durable media
  source of truth
status: To Do
assignee: []
created_date: '2026-08-02 22:38'
labels: []
dependencies:
  - task-218
  - task-219
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Move all user-facing library and organization behavior onto the durable media persistence established by task-219, following the owner-approved decision in docs/research/task-218-durable-media-library-persistence/README.md. Search results, collection counts, folder contents, media detail ownership, and organization mutations must remain correct even after the associated processing job expires.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Canonical media list and search responses are sourced from durable user-media records rather than from the presence of processing_jobs rows
- [ ] #2 Folder counts and folder-content views include durable media whose processing jobs have expired
- [ ] #3 Moving media between folders and assigning or removing tags updates the durable authoritative record
- [ ] #4 Deleting a folder applies the documented reassignment behavior to all affected durable media, including media with no remaining processing job
- [ ] #5 Media ownership checks and artifact navigation continue to enforce user isolation when processing-job data is absent
- [ ] #6 Processing state is represented as optional operational data and its absence does not remove the media from the library
- [ ] #7 The default Uncategorized behavior assigns newly saved media consistently, including saves without an explicit folder_id
- [ ] #8 All active backend code paths that treat processing_jobs as the user-library source of truth are removed or explicitly justified as operational-only
- [ ] #9 The existing canonical /api/media/* and /api/artifacts/* contracts remain coherent for mobile consumers without introducing /api/v1 media endpoints
- [ ] #10 AWS dev verification covers list, Search, folder count, folder open, folder move, tag filtering, media detail, and processing-job expiry scenarios
- [ ] #11 The known marc.medlock@live.fr scenario is documented as a regression case: folders remain populated after job TTL cleanup
<!-- AC:END -->
