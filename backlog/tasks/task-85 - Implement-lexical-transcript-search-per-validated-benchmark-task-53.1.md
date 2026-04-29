---
id: task-85
title: Implement lexical transcript search per validated benchmark (task-53.1)
status: Done
assignee: []
created_date: '2026-04-28 16:05'
labels:
  - search
  - v1
  - implementation
dependencies:
  - task-53.1
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement per-user lexical search over media transcripts using the engine and architecture validated in task-53.1. Read the owner's Decision from `docs/research/task-53.1-lexical-search/README.md` (Owner Validation section) before planning the implementation.

Scope covers: provisioning/configuring the chosen search engine, indexing pipeline from transcripts in S3, per-user tenant isolation, and a search API integrated with the canonical surface.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Search engine and integration pattern follow the recommendation validated in docs/research/task-53.1-lexical-search/README.md
- [ ] #2 Transcripts are indexed asynchronously after transcription completes, with per-user tenant isolation
- [ ] #3 Search API exposed under the canonical surface and returns ranked results with acceptable latency
<!-- AC:END -->
