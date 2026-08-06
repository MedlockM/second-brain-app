---
id: task-234
title: 'Treat dispatchable:false as a hard gate in every backlog dispatcher'
status: Done
assignee:
  - Codex
created_date: '2026-08-06 01:16'
updated_date: '2026-08-06 01:19'
labels:
  - tooling
  - backlog
  - dispatcher
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Ensure every active backlog dispatch path excludes tasks whose front matter sets dispatchable: false. Preserve this gate independently of labels, priority, status, and dependency readiness.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The deterministic Python orchestrator parses dispatchable from local task front matter and JSON snapshots.
- [x] #2 Tasks with dispatchable: false are never emitted in the dispatch-now lane even when otherwise ready.
- [x] #3 The existing Claude dispatcher contract and the deterministic orchestrator consistently document and enforce the same hard gate.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Inspect every active dispatch path and its task parser.
2. Add dispatchable parsing and enforce a hard exclusion in the deterministic orchestrator.
3. Align the dispatcher documentation/contract and validate both task-62 and task-229 are excluded.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented a first-class `dispatchable` boolean in `scripts/backlog_agent_orchestrator.py` for both local front matter and JSON snapshots. Classification now records an explicit skip reason and cannot place disabled tasks in `dispatch_now`. `scripts/dispatch_backlog.sh` derives a denylist from tracked task front matter and injects it into the Claude dispatcher prompt because Backlog MCP views omit custom fields. Updated the dispatcher contract and orchestration documentation. Validated Python compilation, Ruff, Bash syntax, local backlog classification, JSON snapshot classification, and the shell denylist. Existing unrelated Mypy errors remain in the orchestrator.
<!-- SECTION:NOTES:END -->
