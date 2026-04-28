---
id: task-88
title: Apply LLM provider/model configuration per validated benchmark (task-72)
status: To Do
assignee: []
created_date: '2026-04-28 16:05'
labels:
  - llm
  - artifacts
  - v1
  - implementation
dependencies:
  - task-72
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Apply the LLM provider/model decisions validated in task-72 across the artifact generation workers (summary_short, summary_detailed, flashcards, notes). Read the owner's Decision from `docs/research/task-72-llm-artifact-benchmark/README.md` (Owner Validation section) before planning the implementation.

Scope covers: provider/model selection per artifact type, prompt updates if required, environment variables and client configuration, and removal of obsolete provider/model references.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each artifact worker uses the provider/model validated in docs/research/task-72-llm-artifact-benchmark/README.md
- [ ] #2 Environment variables and client configuration reflect the chosen providers/models and are documented
- [ ] #3 Prompts and worker plumbing are updated for reliable JSON output where applicable (flashcards)
<!-- AC:END -->
