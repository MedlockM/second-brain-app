---
id: task-49
title: Rename episode-centric identifiers to media-agnostic naming across codebase
status: Done
assignee: []
created_date: '2026-02-24 20:39'
updated_date: '2026-04-21 21:15'
labels: []
dependencies:
  - task-23
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
The product scope is now generic media ingestion and processing, but many runtime identifiers, file names, models, payload keys, and UI references still use podcast/episode-centric terminology. Consolidate naming so active code paths reflect a media-agnostic domain language.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Active runtime code paths use media-agnostic naming for core domain concepts, replacing episode/podcast-specific names where they no longer represent the product scope.
- [x] #2 File and module names in active media ingestion/processing flows are aligned with media-agnostic terminology.
- [x] #3 Public API contracts and payload fields for generic media flows expose media-agnostic naming; any temporarily retained legacy aliases are explicitly documented as deprecated.
- [x] #4 Operational/configuration names used by active generic media flows are aligned with media-agnostic terminology or explicitly documented as legacy-only.
- [x] #5 UI/product copy in active user flows refers to generic media concepts rather than podcast-only concepts, except where a source-specific context is intentional.
- [x] #6 Project documentation and runbooks describe the canonical media-agnostic naming model and list any remaining intentional exceptions.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-04-21 : Renamed 6 core modules from episode-centric to media-agnostic naming: episodes.py→media_items.py, episode_submission.py→media_submission.py, episode_idempotence.py→media_idempotence.py, episode_watchers.py→media_watchers.py, user_episode_submissions.py→user_media_submissions.py, episode_completed_worker.py→media_completed_worker.py. Updated internal identifiers within each module. Commit f9680df on branch worktree-agent-a722c1d5.
<!-- SECTION:NOTES:END -->
