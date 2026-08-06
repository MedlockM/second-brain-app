---
id: task-236
title: Remove the deferred legacy newsletter-ingestion implementation from V1
status: Done
assignee:
  - Codex
created_date: '2026-08-06 01:25'
updated_date: '2026-08-06 01:27'
labels:
  - cleanup
  - newsletter
  - v1
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up to completed task-235. Delete the inactive SES/SNS newsletter webhook, worker, MIME parser, and newsletter-specific error surface from the V1 codebase. Remove their configuration and typing remnants, and stop advertising inbound newsletters in V1 pricing copy while preserving the in-app digest/newsletter presentation language.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 No legacy newsletter webhook, worker, parser, or newsletter-specific error module remains in the V1 runtime source.
- [x] #2 Newsletter-ingestion queue configuration and newsletter-specific Mypy exceptions are removed.
- [x] #3 V1 entitlement and pricing descriptions no longer advertise inbound newsletter ingestion.
- [x] #4 Digest-oriented uses of newsletter wording remain intact.
- [x] #5 No live source or infrastructure reference can reactivate the legacy newsletter-ingestion pipeline.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Delete the unreachable newsletter webhook, worker package, parser, and error module.
2. Remove queue configuration, Mypy overrides, legacy quota/comment remnants, and misleading V1 pricing copy.
3. Search all live source and infrastructure references, preserving only in-app digest wording, then run static validation.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Deleted the inactive newsletter webhook, newsletter worker package, stdlib MIME parser, and newsletter-specific error module (926 source lines). Removed NEWSLETTER_INGESTION_QUEUE from Settings and .env.example, removed both newsletter Mypy override entries, removed the explicit newsletter quota alias, and made the legacy summarizing-status comment generic. Removed newsletter ingestion claims from the Reader entitlement/pricing descriptions and removed task-62 from the V1 mobile implementation plan. Preserved the two newsletter references in summary_short.py because they describe the in-app daily/weekly digest format. Validation: uv lock check, Python compilation, Ruff, targeted Mypy, FastAPI route inspection, legacy-reference search, and diff whitespace check all passed. No automated tests were run per repository instructions.
<!-- SECTION:NOTES:END -->
