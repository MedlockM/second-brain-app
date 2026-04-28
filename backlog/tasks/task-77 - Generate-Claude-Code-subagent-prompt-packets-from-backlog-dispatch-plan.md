---
id: task-77
title: Generate Claude Code subagent prompt packets from backlog dispatch plan
status: Done
assignee: []
created_date: '2026-03-31 17:49'
updated_date: '2026-03-31 17:54'
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
Extend the local backlog-driven orchestrator so it can generate ready-to-use Claude Code prompt packets for each selected dispatchable task. The output should include a batch index plus one prompt file per selected task, grounded in the repository task metadata and repo-specific execution constraints.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The orchestrator can emit Claude Code prompt files for the tasks selected in `dispatch_now`.
- [x] #2 Each generated prompt includes the task objective, dependencies, acceptance criteria, repo-specific guardrails, and recommended write scope.
- [x] #3 A batch index file is generated so the user can see which prompts correspond to which tasks.
- [x] #4 Documentation covers the command line for generating Claude Code prompts from the local backlog without manual snapshot extraction.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Extended `scripts/backlog_agent_orchestrator.py` so it can generate real Claude Code prompt packets for the selected `dispatch_now` tasks via the local `claude` CLI in non-interactive `-p` mode with structured JSON output. Added richer task parsing from Backlog markdown files (description, acceptance criteria, implementation notes, source path), repo guardrails, recommended reading, timestamped batch output under a chosen directory, batch `README.md`, and `dispatch-plan.json`. Updated `docs/BACKLOG_SUBAGENT_ORCHESTRATION.md` with the zero-manual-extraction Claude generation workflow. Verification passed with `python3 -m py_compile scripts/backlog_agent_orchestrator.py`, `.venv/bin/ruff check scripts/backlog_agent_orchestrator.py`, and a real Claude-backed run: `python3 scripts/backlog_agent_orchestrator.py --generate-claude-prompts .claude/dispatch-prompts`, which generated `.claude/dispatch-prompts/claude-dispatch-20260331-195343/` including the prompt for `task-65`.
<!-- SECTION:NOTES:END -->
