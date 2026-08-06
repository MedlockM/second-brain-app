---
id: task-235
title: Disable the legacy newsletter ingestion webhook in the V1 runtime
status: Done
assignee:
  - Codex
created_date: '2026-08-06 01:16'
updated_date: '2026-08-06 01:19'
labels:
  - cleanup
  - newsletter
  - v1
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Remove the legacy newsletter ingestion router from the V1 application runtime while retaining newsletter ingestion as a deferred future capability tracked in Backlog.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The V1 FastAPI application no longer imports or registers the legacy newsletter ingestion router.
- [x] #2 The canonical V1 media and artifact routes remain unchanged.
- [x] #3 The deferred newsletter implementation and its webhook-authentication requirement remain tracked but non-dispatchable.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Identify all runtime registrations of the newsletter ingestion endpoint.
2. Remove the legacy router from the V1 FastAPI application without altering canonical media/artifact routes.
3. Validate route registration and update the deferred newsletter backlog metadata.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Removed the legacy newsletter webhook import and router registration from `media_summarizer/api/main.py`; canonical media and artifact routers were left intact. Reopened task-62 as the deferred newsletter capability, removed its `post-v1` label, and set `dispatchable: false`. Made task-229 depend on task-62 and set it non-dispatchable as well. Verified the FastAPI route table no longer contains `/api/media/newsletter/ingest` while canonical media/artifact routes remain present.
<!-- SECTION:NOTES:END -->
