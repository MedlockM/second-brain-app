#!/usr/bin/env bash
# Dispatch backlog tasks to parallel Claude Code agents via agent-teams.
# Seul point d'entrée du dispatch : la sélection, le worktree par agent, le merge
# séquentiel et la mise à jour du backlog sont portés par .claude/agents/backlog-dispatcher.md.
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
#   - claude-bedrock available on PATH and configured with Bedrock API credentials
#   - No uncommitted changes to tracked files on current branch
#   - No untracked files under backlog/tasks (worktrees cannot see them)
#   - Other untracked files only emit a warning because they can block merges
#   - Agent definitions in .claude/agents/

set -euo pipefail

# Claude Code otherwise terminates background agents after 10 minutes in print
# mode. Dispatcher tasks routinely take longer, so wait for them indefinitely.
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0

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

UNTRACKED_BACKLOG_TASKS="$(git ls-files --others --exclude-standard -- backlog/tasks)"
if [ -n "${UNTRACKED_BACKLOG_TASKS}" ]; then
  echo "Error: untracked backlog task files detected." >&2
  echo "Commit or remove them before dispatching; agent worktrees cannot see them:" >&2
  printf '%s\n' "${UNTRACKED_BACKLOG_TASKS}" >&2
  exit 1
fi

if ! git diff --quiet HEAD 2>/dev/null; then
  echo "Error: uncommitted changes detected. Commit or stash before dispatching." >&2
  exit 1
fi

# Les autres fichiers non suivis restent dans le checkout principal, invisibles
# aux agents et susceptibles de bloquer un merge. Avertissement seulement :
# l'owner garde parfois des brouillons locaux légitimes non commitables.
UNTRACKED_COUNT="$(git ls-files --others --exclude-standard | wc -l)"
if [ "${UNTRACKED_COUNT}" -gt 0 ]; then
  echo "  Attention : ${UNTRACKED_COUNT} fichier(s) non suivi(s) — invisibles aux agents."
  echo "  Ils peuvent bloquer un merge en Phase 4. Détail : git ls-files --others --exclude-standard"
  echo ""
fi

if ! command -v claude-bedrock >/dev/null 2>&1; then
  echo "Error: claude-bedrock is not available on PATH." >&2
  exit 1
fi

BASE_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

# Backlog.md accepts custom front-matter fields, but its MCP task views do not
# expose them. Build the hard denylist from the task files and inject it into
# the dispatcher prompt so `dispatchable: false` cannot be mistaken for a
# merely documentary flag.
#
# On énumère les fichiers présents sur le disque, pas l'index git : un fichier
# renommé sans commit reste listé par `git ls-files` sous son ancien nom, si bien
# que le verrou s'évaporait au lieu de s'appliquer (constaté sur task-229). Les
# guards ci-dessus garantissent déjà que disque et index concordent.
#
# Toute anomalie de lecture est fatale : un `dispatchable: false` qui échoue
# silencieusement laisserait la tâche partir en dispatch, soit exactement
# l'inverse du verrou demandé. On échoue donc côté fermé.
NON_DISPATCHABLE_IDS=""
shopt -s nullglob
TASK_FILES=(backlog/tasks/*.md)
shopt -u nullglob
if [ "${#TASK_FILES[@]}" -eq 0 ]; then
  echo "Error: aucun fichier de tâche trouvé dans backlog/tasks/." >&2
  echo "Lance ce script depuis la racine du dépôt." >&2
  exit 1
fi
for TASK_FILE in "${TASK_FILES[@]}"; do
  # 0 = verrouillée, 1 = dispatchable, autre = fichier illisible ou awk en échec.
  AWK_STATUS=0
  awk '
    NR == 1 && $0 == "---" { in_front_matter = 1; next }
    in_front_matter && $0 == "---" { exit(found ? 0 : 1) }
    in_front_matter && $0 ~ /^dispatchable:[[:space:]]*false[[:space:]]*$/ { found = 1 }
    END { if (in_front_matter) exit(found ? 0 : 1); exit 1 }
  ' "${TASK_FILE}" || AWK_STATUS=$?
  if [ "${AWK_STATUS}" -gt 1 ]; then
    echo "Error: impossible de lire le front-matter de ${TASK_FILE} (awk: ${AWK_STATUS})." >&2
    echo "Le verrou dispatchable:false ne peut pas être garanti — dispatch interrompu." >&2
    exit 1
  fi
  if [ "${AWK_STATUS}" -eq 0 ]; then
    TASK_ID="$(sed -n 's/^id:[[:space:]]*//p' "${TASK_FILE}" | head -n 1)"
    if [ -z "${TASK_ID}" ]; then
      echo "Error: ${TASK_FILE} porte dispatchable:false sans champ id exploitable." >&2
      echo "Impossible de l'inscrire dans la denylist — dispatch interrompu." >&2
      exit 1
    fi
    NON_DISPATCHABLE_IDS="${NON_DISPATCHABLE_IDS}${NON_DISPATCHABLE_IDS:+, }${TASK_ID}"
  fi
done
NON_DISPATCHABLE_IDS="${NON_DISPATCHABLE_IDS:-aucune}"

# Les worktrees d'agents (isolation: worktree) partent du HEAD local grâce à
# `worktree.baseRef: "head"` dans .claude/settings.json — ils voient donc les
# commits non poussés (cf. régression task-143 écrasée par un refacto parti d'une
# base de 2 semaines). Sans ce réglage, Claude Code les base sur origin/<default>,
# une réf de suivi que l'autofetch de l'IDE ramène en arrière en pleine session.
# Ce guard échoue vite si le réglage disparaît, plutôt que de laisser des agents
# travailler silencieusement sur du code périmé.
if [ "$(git config --file .claude/settings.json --get worktree.baseRef 2>/dev/null || true)" != "head" ]; then
  if ! command -v jq >/dev/null 2>&1 \
     || [ "$(jq -r '.worktree.baseRef // empty' .claude/settings.json 2>/dev/null)" != "head" ]; then
    echo "Error: .claude/settings.json doit contenir worktree.baseRef = \"head\"." >&2
    echo "Sans ce réglage, les agents partent de origin/<default> (code périmé)." >&2
    exit 1
  fi
fi
echo "  Worktrees basés sur HEAD ($(git rev-parse --short HEAD)) via worktree.baseRef"
echo ""

if [ "$TEST_MODE" = true ]; then
  echo "=== Backlog Dispatch — TEST MODE ==="
  echo "  Branch: ${BASE_BRANCH}"
  echo "  Mode: ${MODE}"
  echo ""
  echo "  Dispatching ONLY task-82 (TEST-A) and task-83 (TEST-B)."
  echo "  Both modify media_summarizer/core/constants.py → conflict guaranteed."
  echo ""

  claude-bedrock --agent backlog-dispatcher \
    --dangerously-skip-permissions \
    -p "MODE TEST : dispatche UNIQUEMENT les tâches task-82 et task-83 (labels test-dispatch).
Ignore toutes les autres tâches du backlog.
Tâches verrouillées par dispatchable:false — ne jamais les sélectionner : ${NON_DISPATCHABLE_IDS}.
Branche de base : ${BASE_BRANCH}.
Mode : ${MODE}.
Ces deux tâches modifient le même fichier (media_summarizer/core/constants.py) — un conflit est attendu. Résous-le lors du merge séquentiel."
else
  echo "=== Backlog Dispatch ==="
  echo "  Branch: ${BASE_BRANCH}"
  echo "  Max tasks: ${MAX_DISPATCH}"
  echo "  Mode: ${MODE}"
  echo ""

  claude-bedrock --agent backlog-dispatcher \
    --dangerously-skip-permissions \
    -p "Dispatche jusqu'à ${MAX_DISPATCH} tâches du backlog en parallèle.
Tâches verrouillées par dispatchable:false — ne jamais les sélectionner : ${NON_DISPATCHABLE_IDS}.
Branche de base : ${BASE_BRANCH}.
Mode : ${MODE}."
fi
