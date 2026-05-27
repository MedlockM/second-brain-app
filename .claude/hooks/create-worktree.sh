#!/bin/bash
# WorktreeCreate hook: creates worktrees from the current branch (HEAD)
# instead of the default origin/HEAD (main).
#
# Receives JSON on stdin with fields: base_directory, worktree_name, cwd
# Must print the worktree path to stdout.
#
# If the expected fields are missing, exits 0 silently to let Claude Code
# fall back to its default worktree creation behavior.

set -euo pipefail

LOG="/tmp/worktree-hook-debug.log"
INPUT=$(cat)
echo "$(date): INPUT=$INPUT" >> "$LOG"

# The WorktreeCreate payload provides: session_id, transcript_path, cwd, agent_type, hook_event_name, name
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null) || true
NAME=$(echo "$INPUT" | jq -r '.name // empty' 2>/dev/null) || true

echo "$(date): CWD=$CWD NAME=$NAME" >> "$LOG"

if [ -z "$CWD" ] || [ -z "$NAME" ]; then
  echo "$(date): Missing cwd or name, exiting silently" >> "$LOG"
  exit 0
fi

WT_PATH="${CWD}/.claude/worktrees/${NAME}"
BRANCH="worktree-${NAME}"
CURRENT_BRANCH=$(cd "$CWD" && git rev-parse --abbrev-ref HEAD)

echo "$(date): Creating worktree at $WT_PATH from $CURRENT_BRANCH" >> "$LOG"

cd "$CWD"
git worktree remove --force "$WT_PATH" 2>/dev/null || true
git branch -D "$BRANCH" 2>/dev/null || true

mkdir -p "$(dirname "$WT_PATH")"
git worktree add -b "$BRANCH" "$WT_PATH" "$CURRENT_BRANCH" 2>>"$LOG"

echo "$(date): Success, path=$WT_PATH" >> "$LOG"
echo "$WT_PATH"
