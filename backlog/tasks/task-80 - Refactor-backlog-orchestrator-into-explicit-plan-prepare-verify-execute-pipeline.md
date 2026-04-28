---
id: task-80
title: >-
  Refactor backlog orchestrator into explicit plan/prepare/verify/execute
  pipeline
status: Done
assignee: []
created_date: '2026-03-31 18:46'
updated_date: '2026-03-31 18:50'
labels:
  - tooling
  - backlog
  - agents
  - orchestration
  - claude-code
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Restructure the backlog-driven Claude orchestration script so it exposes four explicit stages: `plan`, `prepare`, `verify`, and `execute`. Each stage must have a clear responsibility and reuse artifacts from the previous stage instead of regenerating ambiguous state. The goal is to make review and approval flow explicit before any real multi-agent execution.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The script exposes explicit `plan`, `prepare`, `verify`, and `execute` stages with documented semantics.
- [x] #2 `prepare` consumes the planning result and writes reusable launch artifacts without calling Claude Code.
- [x] #3 `verify` and `execute` consume prepared artifacts instead of recomputing ambiguous orchestration state.
- [x] #4 The refactor is verified locally with at least one successful `plan` run and one successful `prepare` run producing reviewable artifacts.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Refactored `scripts/backlog_agent_orchestrator.py` into an explicit four-stage pipeline driven by `--stage plan|prepare|verify|execute`. `plan` now computes dispatchability and can write a reusable plan bundle (`dispatch-plan.json`, `dispatch-plan.txt`). `prepare` now consumes a previously generated `dispatch-plan.json` and writes a reusable prepared bundle (`README.md`, `dispatch-plan.json`, `prepared-launch.json`, `claude-agents.json`, `orchestration-prompt.md`, `orchestrator-result.json`, and one prompt file per selected task) without calling Claude Code. `verify` and `execute` now require `--prepared-dir` and consume only the prepared artifacts instead of recomputing task selection or prompt state. Updated `docs/BACKLOG_SUBAGENT_ORCHESTRATION.md` to document the explicit stage semantics and approval workflow. Verified locally with `python3 scripts/backlog_agent_orchestrator.py --stage plan --max-dispatch 2 --output-dir .claude/pipeline` producing `.claude/pipeline/dispatch-plan-20260331-205031/`, and `python3 scripts/backlog_agent_orchestrator.py --stage prepare --plan-file .claude/pipeline/dispatch-plan-20260331-205031/dispatch-plan.json --output-dir .claude/pipeline` producing `.claude/pipeline/claude-prepare-20260331-205037/`.
<!-- SECTION:NOTES:END -->
