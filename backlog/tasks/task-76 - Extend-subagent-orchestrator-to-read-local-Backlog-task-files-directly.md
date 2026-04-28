---
id: task-76
title: Extend subagent orchestrator to read local Backlog task files directly
status: Done
assignee: []
created_date: '2026-03-31 17:46'
updated_date: '2026-03-31 17:47'
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
Remove the need for manual snapshot extraction by teaching the local subagent orchestrator to read Backlog task markdown files from `backlog/tasks/`, parse task metadata, and build the same deterministic dispatch plan directly from the repository state. Keep the JSON snapshot mode as an optional input for testing and reproducible examples.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The orchestrator can load tasks directly from local Backlog task markdown files without requiring a pre-generated JSON snapshot.
- [x] #2 Front matter metadata needed for planning is parsed reliably for the current Backlog task file format.
- [x] #3 The existing JSON snapshot mode remains supported for reproducible examples and tests.
- [x] #4 Documentation and examples describe the zero-manual-extraction workflow and verified command lines.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Extended `scripts/backlog_agent_orchestrator.py` so `--snapshot` is now optional and the default mode reads `backlog/tasks/*.md` directly. Added a lightweight front matter parser for the current Backlog task file format, including folded multiline titles and list-valued metadata (`labels`, `dependencies`, `assignee`). Kept JSON snapshot mode unchanged for reproducible examples. Updated `docs/BACKLOG_SUBAGENT_ORCHESTRATION.md` to document the zero-manual-extraction workflow. Verification passed with `python3 scripts/backlog_agent_orchestrator.py`, `python3 scripts/backlog_agent_orchestrator.py --snapshot docs/examples/backlog_dispatch_snapshot.example.json`, `python3 -m py_compile scripts/backlog_agent_orchestrator.py`, and `.venv/bin/ruff check scripts/backlog_agent_orchestrator.py`.
<!-- SECTION:NOTES:END -->
