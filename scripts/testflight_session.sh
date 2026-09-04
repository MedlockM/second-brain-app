#!/usr/bin/env bash
# Gère la session Pro 24/7 qui reçoit les rapports de triage TestFlight, pousse la
# notification sur le téléphone de l'owner et exécute ses go/no-go.
# Sa procédure est dans .claude/agents/feedback-decisions.md.
#
# Usage:
#   ./scripts/testflight_session.sh start     # démarre si elle ne tourne pas déjà
#   ./scripts/testflight_session.sh status    # état, et l'URL Remote Control
#   ./scripts/testflight_session.sh restart   # après une mise à jour de Claude Code
#   ./scripts/testflight_session.sh stop
#   ./scripts/testflight_session.sh logs
#
# La commande brute est plus subtile qu'il n'y paraît : quatre éléments sont
# indispensables et chacun a été établi en le cassant d'abord.
#
# 1. `env -u CLAUDE_CODE_USE_BEDROCK -u AWS_BEARER_TOKEN_BEDROCK -u ANTHROPIC_MODEL`
#    Lancée depuis une session `claude-bedrock`, la commande hérite de ces trois
#    variables et la session « Pro » démarre en réalité sur Bedrock — ce qui vide de
#    son sens le partage du travail (le lourd sur Bedrock, le pilotage sur Pro).
#    Inoffensif depuis un terminal ordinaire, où elles ne sont pas définies.
#
# 2. `--model claude-opus-5`, l'identifiant complet et non l'alias `opus`.
#    `claude` et `claude-bedrock` partagent ~/.claude.json, dont un cache
#    (`clientDataCacheSlots`) mémorise le dernier modèle utilisé. En mode Bedrock il
#    y inscrit `us.anthropic.claude-opus-5`, que la session Pro reprend et que
#    l'API Claude.ai refuse — la session démarre, affiche « Claude Pro », puis chaque
#    tour meurt sur « issue with the selected model ». L'identifiant explicite
#    court-circuite le cache.
#
# 3. `--name` ET `--remote-control` séparément, avec le même libellé.
#    `--remote-control [nom]` ne nomme que la session côté téléphone. Le nom
#    d'adressage inter-sessions — celui que `ListAgents` affiche et que
#    `SendMessage` prend — vient de `--name`. Sans lui, il est auto-généré depuis le
#    contenu de la conversation (observé : « feedback triage review ») et change à
#    chaque relance : le triage de 9h00 ne retrouverait pas sa cible.
#
# 4. `--agent feedback-decisions`
#    Le contexte d'une session qui vit des jours finit compacté. La procédure de
#    go/no-go doit donc être une définition d'agent, relue à chaque tour, pas un
#    prompt de démarrage qui s'évapore.

set -euo pipefail

SESSION_NAME="TestFlight Feedback"
MODEL="claude-opus-5"
AGENT="feedback-decisions"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Le compte Pro, jamais Bedrock : cf. note 1 ci-dessus.
claude_pro() {
  env -u CLAUDE_CODE_USE_BEDROCK -u AWS_BEARER_TOKEN_BEDROCK -u ANTHROPIC_MODEL claude "$@"
}

session_field() {
  claude_pro agents --json 2>/dev/null \
    | SESSION_NAME="${SESSION_NAME}" FIELD="$1" python3 -c '
import json, os, sys
name, field = os.environ["SESSION_NAME"], os.environ["FIELD"]
try:
    rows = json.load(sys.stdin)
except (json.JSONDecodeError, ValueError):
    sys.exit(0)
for row in rows if isinstance(rows, list) else []:
    if row.get("name") == name:
        print(row.get(field, ""))
        break
'
}

start_session() {
  local existing
  existing="$(session_field sessionId)"
  if [ -n "${existing}" ]; then
    echo "Déjà en cours : « ${SESSION_NAME} » ($(session_field status))."
    echo "Pour la remplacer : $0 restart"
    return 0
  fi

  cd "${REPO_ROOT}"
  claude_pro --bg \
    --name "${SESSION_NAME}" \
    --remote-control "${SESSION_NAME}" \
    --agent "${AGENT}" \
    --model "${MODEL}" \
    "Tu es la session de pilotage des décisions sur les feedbacks beta TestFlight. Reste disponible et n'entreprends rien tant qu'un rapport n'arrive pas. Réponds en une ligne que tu es prête."
}

stop_session() {
  local sid
  sid="$(session_field sessionId)"
  if [ -z "${sid}" ]; then
    echo "Aucune session « ${SESSION_NAME} » en cours."
    return 0
  fi
  claude_pro stop "${sid}"
}

case "${1:-status}" in
  start)
    start_session
    ;;
  stop)
    stop_session
    ;;
  restart)
    stop_session
    sleep 2
    start_session
    ;;
  logs)
    sid="$(session_field sessionId)"
    if [ -z "${sid}" ]; then
      echo "Aucune session « ${SESSION_NAME} » en cours." >&2
      exit 1
    fi
    # Le rendu TUI est truffé de séquences ANSI ; on les retire pour rendre le
    # journal lisible dans un pipe.
    claude_pro logs "${sid}" 2>&1 | sed 's/\x1b\[[0-9;]*[a-zA-Z]//g'
    ;;
  status)
    sid="$(session_field sessionId)"
    if [ -z "${sid}" ]; then
      echo "« ${SESSION_NAME} » : arrêtée."
      echo "Le triage de 9h00 écrira son rapport sur disque et sortira non-zéro."
      echo "Démarrer : $0 start"
      exit 1
    fi
    echo "« ${SESSION_NAME} » : $(session_field status) (session ${sid}, pid $(session_field pid))"
    echo "URL Remote Control (téléphone) : voir la ligne « /remote-control is active » de $0 logs"
    ;;
  *)
    echo "Usage: $0 {start|stop|restart|status|logs}" >&2
    exit 1
    ;;
esac
