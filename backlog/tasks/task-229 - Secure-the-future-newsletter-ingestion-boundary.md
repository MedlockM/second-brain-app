---
id: task-229
title: Secure the future newsletter-ingestion boundary
status: To Do
assignee:
  - Codex
created_date: '2026-08-05 18:45'
updated_date: '2026-08-06 01:28'
labels:
  - security
  - api
  - newsletter
dependencies:
  - task-62
priority: high
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Security requirement paired with `task-62`. When newsletter ingestion is eventually implemented, its inbound email/provider boundary must reject untrusted events before reading external storage, following confirmation URLs, or enqueueing work. The implementation must define and verify the trusted provider signature, constrain the expected source/topic, and only read from configured ingestion storage. This task does not reactivate the removed V1 SES/SNS prototype.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Unsigned or invalid inbound newsletter events are rejected before any side effect.
- [ ] #2 Validly signed events from an unexpected source or topic are rejected.
- [ ] #3 Any provider confirmation callback is either removed or restricted to verified, allowlisted HTTPS hosts.
- [ ] #4 The ingestion worker only reads from explicitly configured ingestion storage, never a location supplied by an untrusted event.
- [ ] #5 After task-62 is implemented, a legitimate provider-originated newsletter ingests end to end with these controls enabled.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-06 : conservée comme exigence de sécurité de la future ingestion de newsletters. Elle dépend de `task-62` et reste hors exécution automatique via `dispatchable: false`. Le prototype SES/SNS V1 auquel la tâche faisait initialement référence a été supprimé dans `task-236`.
<!-- SECTION:NOTES:END -->
