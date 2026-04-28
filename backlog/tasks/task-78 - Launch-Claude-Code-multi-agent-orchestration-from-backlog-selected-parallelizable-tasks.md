---
id: task-78
title: >-
  Launch Claude Code multi-agent orchestration from backlog-selected
  parallelizable tasks
status: In Progress
assignee: []
created_date: '2026-03-31 18:10'
labels:
  - tooling
  - backlog
  - agents
  - orchestration
  - claude-code
dependencies: []
priority: medium
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Extend the backlog-driven orchestrator so it can launch a single Claude Code orchestrator session that receives the currently selected parallelizable tasks, creates one custom subagent per task, and delegates those tasks in parallel. The implementation must also produce verification artifacts so the user can inspect the exact agents, orchestration prompt, and structured result returned by Claude Code.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The script can identify a set of parallelizable tasks and launch one Claude Code orchestrator session for them.
- [ ] #2 The launcher creates one custom Claude Code agent per selected task with task-specific prompt content.
- [ ] #3 The launcher stores verification artifacts including the custom agents definition, orchestration prompt, and Claude Code structured result.
- [ ] #4 The implementation is verified with a real Claude Code launch in a safe verification mode that confirms task-to-agent assignment behavior.
<!-- AC:END -->
