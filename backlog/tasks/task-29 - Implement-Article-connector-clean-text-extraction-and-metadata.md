---
id: task-29
title: Implement Article connector (clean text extraction and metadata)
status: Done
assignee: []
created_date: '2026-02-24 11:03'
updated_date: '2026-03-03 22:00'
labels: []
dependencies:
  - task-20
  - task-21
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement article ingestion connector that extracts clean source text and extraction metadata for transcript-first processing.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Article URLs produce clean extracted text suitable for artifact generation.
- [ ] #2 Extraction metadata is persisted for traceability and diagnostics.
- [ ] #3 Connector handles common extraction failures with stable errors.
- [ ] #4 Connector output is normalized to shared ingestion contract fields.
<!-- AC:END -->
