---
id: task-75
title: Add minimal Backlog-driven subagent orchestrator for ready-task dispatch
status: Done
assignee: []
created_date: '2026-03-31 17:40'
updated_date: '2026-03-31 17:44'
labels:
  - tooling
  - backlog
  - agents
  - orchestration
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Provide a lightweight local orchestrator that reads a task graph snapshot, identifies dispatchable ready tasks, applies repo-specific guardrails, and outputs a deterministic dispatch plan suitable for Codex/Claude subagent workflows. The first version should stay intentionally minimal: no direct agent spawning or automated backlog mutation, just planning-quality selection with clear reasons for dispatch/skip decisions.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A local script can read a backlog task snapshot from JSON and compute tasks that are ready to run based on status and dependencies.
- [x] #2 The orchestrator applies repo-specific dispatch guardrails and classifies tasks as dispatchable or skipped with explicit reasons.
- [x] #3 The script emits a deterministic, human-reviewable dispatch plan that includes task id, title, lane, write scope, and rationale.
- [x] #4 Usage is documented with the expected input shape and example command lines.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added `scripts/backlog_agent_orchestrator.py` as a minimal deterministic planner that reads a JSON snapshot, computes `ready` tasks from statuses/dependencies, applies repo-specific dispatch guardrails, and selects non-overlapping tasks for immediate dispatch. Added `docs/BACKLOG_SUBAGENT_ORCHESTRATION.md` for usage and `docs/examples/backlog_dispatch_snapshot.example.json` as a concrete snapshot based on the current backlog shape. Verification passed with `python3 scripts/backlog_agent_orchestrator.py --snapshot docs/examples/backlog_dispatch_snapshot.example.json`, `python3 -m py_compile scripts/backlog_agent_orchestrator.py`, and `.venv/bin/ruff check scripts/backlog_agent_orchestrator.py`.
<!-- SECTION:NOTES:END -->
