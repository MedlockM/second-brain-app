---
id: task-33
title: Implement artifact read endpoints (list and detail)
status: Done
assignee:
  - '@codex'
created_date: '2026-02-24 11:03'
updated_date: '2026-03-15 21:47'
labels: []
dependencies:
  - task-11
  - task-12
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Expose canonical artifact read endpoints so clients can list artifacts for a media item and retrieve artifact details reliably.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 GET /api/media/{media_item_id}/artifacts returns all artifacts with status metadata.
- [x] #2 GET /api/artifacts/{artifact_id} returns artifact content and metadata consistently.
- [x] #3 Read endpoints return stable not-found and unauthorized errors.
- [x] #4 Endpoint responses align with frozen API/domain contract.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Add canonical authenticated list endpoint `GET /api/media/{media_item_id}/artifacts` that validates parent media ownership through the existing media/job read path and returns `ArtifactListResponse` from canonical `media_artifacts` storage.
2. Add canonical authenticated detail endpoint `GET /api/artifacts/{artifact_id}` on a dedicated router, resolve the parent media item from the artifact record, enforce ownership via the parent media/job, and load JSON content from S3 only for ready artifacts with storage metadata.
3. Reuse/factor shared helpers for artifact contract mapping, canonical error responses, and S3 artifact content loading so list/detail responses stay aligned with the frozen contract and existing media status endpoint.
4. Update runtime documentation/OpenAPI artifacts as needed, regenerate `openapi.json`, run structural validation checks, and record implementation notes plus acceptance criteria/results back into Backlog.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented canonical artifact read endpoints on the existing authenticated API surface. `GET /api/media/{media_item_id}/artifacts` now validates parent media ownership via `ProcessingJob` and returns `ArtifactListResponse` from canonical `media_artifacts` storage. `GET /api/artifacts/{artifact_id}` is exposed on a dedicated `/api/artifacts` router, resolves the parent media item from the artifact record, enforces ownership through the parent `ProcessingJob`, returns `ARTIFACT_NOT_FOUND` when the artifact or its parent media record is absent, and loads JSON content from S3 only for ready artifacts.

Reused the existing artifact contract mapper from `media.py` so list/detail/status responses stay aligned with the frozen contract. Updated the runtime contract note in `docs/CANONICAL_MEDIA_API_CONTRACT.md` and regenerated `openapi.json`; verification confirmed `/api/media/{media_item_id}/artifacts` exposes `get`+`post` and `/api/artifacts/{artifact_id}` exposes `get`.

Validation run in this session: Python AST parse OK for `api/endpoints/artifacts.py`, `api/endpoints/media.py`, and `api/main.py`. OpenAPI generation/import required an in-memory stub for `media_summarizer.utils.ses` because the current workspace state still references that removed module from `media_summarizer/utils/__init__.py`; this issue pre-existed the task-33 implementation and was not modified here. No automated endpoint tests were added or run for this task, per project delivery rules unless explicitly requested.
<!-- SECTION:NOTES:END -->
