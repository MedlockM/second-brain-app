#!/usr/bin/env bash
# Point d'entrée du triage quotidien des feedbacks beta TestFlight.
# Toute la logique — collecte, dédup, regroupement sémantique, délégation à
# task-mobile, rédaction et délivrance du rapport — est portée par
# .claude/agents/feedback-triage.md. Ce script ne fait que les gardes et le lancement.
#
# Usage:
#   ./scripts/testflight_triage.sh [OPTIONS]
#
# Options:
#   --since-hours N   Fenêtre de collecte en heures (défaut: 168). Ne borne que le
#                     coût API : la dédup est ancrée sur les ids, pas sur le temps.
#   --dry-run         Collecte, regroupe et rapporte, mais ne prépare aucun code.
#   --no-deliver      Écrit le rapport sur disque sans le pousser à la session Pro.
#
# Prérequis:
#   - claude-bedrock sur le PATH (le travail lourd ne consomme pas le quota Pro)
#   - une clé App Store Connect résolvable (cf. mobile/MOBILE_CI_CD.md)
#   - worktree.baseRef = "head" dans .claude/settings.json
#   - une session Pro nommée « TestFlight Feedback » vivante, pour la délivrance
#
# Différence assumée avec scripts/dispatch_backlog.sh : **aucune garde sur l'arbre
# sale.** Le dispatcher exige un arbre propre parce qu'il merge ; ce run ne commite
# pas, ne pousse pas, ne merge pas et ne touche pas au checkout principal. Or il se
# déclenche à 9h00, potentiellement au milieu du travail de l'owner, qui commite
# directement sur `main`. Refuser de tourner sur un arbre sale transformerait un run
# inoffensif en échec quotidien.

set -euo pipefail

# Claude Code tue sinon les agents d'arrière-plan au bout de 10 minutes en mode
# print. Un correctif mobile préparé par task-mobile dépasse régulièrement.
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0

SINCE_HOURS=168
MODE="execute"
DELIVER=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --since-hours)
      SINCE_HOURS="$2"
      shift 2
      ;;
    --dry-run)
      MODE="dry-run"
      shift
      ;;
    --no-deliver)
      DELIVER=false
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--since-hours N] [--dry-run] [--no-deliver]" >&2
      exit 1
      ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

if ! command -v claude-bedrock >/dev/null 2>&1; then
  echo "Error: claude-bedrock is not available on PATH." >&2
  echo "Un service systemd hérite d'un PATH minimal — vérifier Environment=PATH dans l'unité." >&2
  exit 1
fi

# `claude-bedrock` n'est qu'un wrapper qui fait `exec claude`, et sur cette machine
# ~/.local/bin/claude est un lien vers ~/snap/code/<révision>/.local/share/claude/
# — l'installation a tourné dans le bac à sable du snap VS Code, où $HOME est
# remappé. snapd ne conserve que deux révisions : deux rafraîchissements de VS Code
# et la cible disparaît. Le wrapper passerait quand même `command -v`, et le timer
# échouerait chaque matin sur un `exec` introuvable. On nomme la cause ici plutôt
# que de la laisser deviner depuis un journal.
CLAUDE_BIN="$(command -v claude || true)"
if [ -z "${CLAUDE_BIN}" ] || [ ! -x "$(readlink -f "${CLAUDE_BIN}")" ]; then
  echo "Error: le binaire claude est introuvable ou son lien est cassé." >&2
  echo "  lien   : ${CLAUDE_BIN:-<absent du PATH>}" >&2
  echo "  cible  : $(readlink -f "${CLAUDE_BIN}" 2>/dev/null || echo '<non résolue>')" >&2
  echo "Cause probable : une révision du snap VS Code élaguée sous ~/snap/code/." >&2
  echo "Réinstaller Claude Code hors du bac à sable du snap rétablit le lien durablement." >&2
  exit 1
fi

# Le serveur MCP asc-testflight est en portée utilisateur, donc `claude` tente de
# le démarrer via npx quelle que soit la session. Ce run n'en a pas besoin (il
# passe par testflight_feedback.py), mais un npx introuvable coûte 30 s de timeout
# au démarrage. Avertissement seulement : le triage fonctionne sans.
if ! command -v npx >/dev/null 2>&1; then
  echo "  Attention : npx introuvable — le serveur MCP asc-testflight ne démarrera pas."
  echo "  Sans conséquence sur ce run, mais 30 s de timeout au lancement."
  echo ""
fi

# Échec rapide sur les credentials : zéro appel API, et cela évite de dépenser un
# run d'agent complet pour découvrir qu'un .p8 a bougé.
if ! python3 scripts/testflight_feedback.py --check-credentials; then
  echo "Error: credentials App Store Connect inutilisables — triage interrompu." >&2
  exit 1
fi

# Les worktrees de task-mobile partent du HEAD local grâce à worktree.baseRef.
# Sans ce réglage ils se basent sur origin/<default>, une réf de suivi que
# l'autofetch ramène en arrière : le correctif serait écrit sur du code périmé.
if [ "$(git config --file .claude/settings.json --get worktree.baseRef 2>/dev/null || true)" != "head" ]; then
  if ! command -v jq >/dev/null 2>&1 \
     || [ "$(jq -r '.worktree.baseRef // empty' .claude/settings.json 2>/dev/null)" != "head" ]; then
    echo "Error: .claude/settings.json doit contenir worktree.baseRef = \"head\"." >&2
    echo "Sans ce réglage, les agents partent de origin/<default> (code périmé)." >&2
    exit 1
  fi
fi

mkdir -p .testflight-feedback

# `Persistent=true` rattrape un créneau manqué au réveil de la machine, ce qui peut
# tomber pendant un run lancé à la main. Deux triages concurrents dédupliqueraient
# l'un contre l'autre sur un état à moitié écrit et pourraient proposer deux
# branches pour un même feedback. Sauter est le comportement correct, pas une
# erreur : le prochain créneau reprendra ce qui reste, puisque les branches et le
# registre portent la mémoire.
exec 9>.testflight-feedback/triage.lock
if ! flock -n 9; then
  echo "Un triage est déjà en cours (.testflight-feedback/triage.lock) — run sauté."
  exit 0
fi

BASE_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

echo "=== TestFlight Feedback Triage ==="
echo "  Branche: ${BASE_BRANCH} ($(git rev-parse --short HEAD))"
echo "  Fenêtre: ${SINCE_HOURS} h"
echo "  Mode: ${MODE}"
echo "  Délivrance: $([ "${DELIVER}" = true ] && echo 'session Pro « TestFlight Feedback »' || echo 'disque seulement')"
echo ""

PROMPT="Traite les feedbacks beta TestFlight en attente.
Fenêtre de collecte : ${SINCE_HOURS} heures (--since-hours ${SINCE_HOURS}).
Branche de base : ${BASE_BRANCH}.
Mode : ${MODE}."

if [ "${MODE}" = "dry-run" ]; then
  PROMPT="${PROMPT}
MODE DRY-RUN : exécute les phases 0 à 4 — collecte, dédup, regroupement, classement des sorties — puis rédige le rapport en décrivant ce que tu ferais. Ne spawn AUCUN agent task-mobile et ne crée aucune branche."
fi

if [ "${DELIVER}" = false ]; then
  PROMPT="${PROMPT}
NE DÉLIVRE PAS le rapport : écris-le sur disque et arrête-toi là. N'appelle ni ListAgents ni SendMessage. L'absence de délivrance est ici voulue, donc ce n'est pas un échec — termine avec succès."
fi

claude-bedrock --agent feedback-triage \
  --dangerously-skip-permissions \
  -p "${PROMPT}"
