#!/usr/bin/env bash
# Dispatch backlog tasks to parallel Claude Code agents via agent-teams.
# Replaces the 1070-line backlog_dispatch.py with native agent-teams orchestration.
#
# Usage:
#   ./scripts/dispatch_backlog.sh [OPTIONS]
#
# Options:
#   --max-dispatch N   Max tasks to dispatch (default: 5)
#   --dry-run          Show dispatch plan without launching agents
#   --plan-only        Agents plan but don't implement
#   --test             Create and dispatch two dummy tasks that conflict on the same file
#
# Prerequisites:
#   - CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 (set in ~/.claude/settings.json)
#   - No uncommitted changes on current branch
#   - Agent definitions in .claude/agents/

set -euo pipefail

MAX_DISPATCH=5
MODE="execute"
TEST_MODE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-dispatch)
      MAX_DISPATCH="$2"
      shift 2
      ;;
    --dry-run)
      MODE="dry-run"
      shift
      ;;
    --plan-only)
      MODE="plan-only"
      shift
      ;;
    --test)
      TEST_MODE=true
      MAX_DISPATCH=2
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--max-dispatch N] [--dry-run] [--plan-only] [--test]" >&2
      exit 1
      ;;
  esac
done

if ! git diff --quiet HEAD 2>/dev/null; then
  echo "Error: uncommitted changes detected. Commit or stash before dispatching." >&2
  exit 1
fi

BASE_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

if [ "$TEST_MODE" = true ]; then
  echo "=== Backlog Dispatch — TEST MODE ==="
  echo "  Branch: ${BASE_BRANCH}"
  echo "  Mode: ${MODE}"
  echo ""
  echo "  Dispatching ONLY task-82 (TEST-A) and task-83 (TEST-B)."
  echo "  Both modify media_summarizer/core/constants.py → conflict guaranteed."
  echo ""

  claude --agent backlog-dispatcher \
    --dangerously-skip-permissions \
    -p "MODE TEST : dispatche UNIQUEMENT les tâches task-82 et task-83 (labels test-dispatch).
Ignore toutes les autres tâches du backlog.
Branche de base : ${BASE_BRANCH}.
Mode : ${MODE}.
Ces deux tâches modifient le même fichier (media_summarizer/core/constants.py) — un conflit est attendu. Résous-le lors du merge séquentiel."
else
  echo "=== Backlog Dispatch ==="
  echo "  Branch: ${BASE_BRANCH}"
  echo "  Max tasks: ${MAX_DISPATCH}"
  echo "  Mode: ${MODE}"
  echo ""

  claude --agent backlog-dispatcher \
    --dangerously-skip-permissions \
    -p "Dispatche jusqu'à ${MAX_DISPATCH} tâches du backlog en parallèle.
Branche de base : ${BASE_BRANCH}.
Mode : ${MODE}."
fi
