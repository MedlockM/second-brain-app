---
id: task-79
title: Add prepare-only verification mode for Claude multi-agent backlog launcher
status: Done
assignee: []
created_date: '2026-03-31 18:30'
updated_date: '2026-03-31 18:32'
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
Add a non-executing preparation mode to the backlog-driven Claude multi-agent launcher so it can generate and store the full orchestration artifacts without launching Claude Code. The goal is to let the user review the selected tasks, custom agent definitions, and orchestration prompt before any real multi-agent run.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The script provides a mode that writes complete orchestration artifacts without launching Claude Code.
- [x] #2 Prepare-only output includes the selected task list, custom agent definitions, and orchestration prompt.
- [x] #3 The prepare-only mode is documented as the approval checkpoint before any real multi-agent launch.
- [x] #4 The mode is verified locally and produces reviewable artifacts for the current backlog state.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added a real `prepare-only` mode to `scripts/backlog_agent_orchestrator.py`. In this mode the script does not call the `claude` CLI at all: it selects dispatchable tasks, builds static review prompts, writes the prompt files, writes `claude-agents.json`, writes `orchestration-prompt.md`, and writes a synthetic `orchestrator-result.json` indicating that no Claude orchestration session was launched. Updated `docs/BACKLOG_SUBAGENT_ORCHESTRATION.md` to document prepare-only as the approval checkpoint before any real verify/execute run. Verified locally with `python3 scripts/backlog_agent_orchestrator.py --max-dispatch 2 --launch-claude-orchestrator .claude/dispatch-runs --claude-launch-mode prepare-only`, which produced `.claude/dispatch-runs/claude-dispatch-20260331-203205/` containing `README.md`, `dispatch-plan.json`, `claude-agents.json`, `orchestration-prompt.md`, `orchestrator-result.json`, and one prompt file per selected task.
<!-- SECTION:NOTES:END -->
