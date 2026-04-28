---
id: task-87
title: Implement OCR ingestion worker per validated benchmark (task-70)
status: To Do
assignee: []
created_date: '2026-04-28 16:05'
labels:
  - ingestion
  - ocr
  - v1
  - implementation
dependencies:
  - task-70
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the OCR ingestion worker using the service and architecture validated in task-70. Read the owner's Decision from `docs/research/task-70-ocr-benchmark/README.md` (Owner Validation section) before planning the implementation.

Scope covers: URL classifier for images and PDFs, OCR worker calling the chosen service, extracted text stored as transcript in S3, integration with the canonical ingestion pipeline via a resolver/adapter, and support for multi-page PDFs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 OCR service and worker architecture follow the recommendation validated in docs/research/task-70-ocr-benchmark/README.md
- [ ] #2 Images (jpg, png) and multi-page PDFs are ingested through the canonical flow and produce a transcript artifact
- [ ] #3 Worker errors are mapped to stable user-safe error codes consistent with the rest of the ingestion pipeline
<!-- AC:END -->
