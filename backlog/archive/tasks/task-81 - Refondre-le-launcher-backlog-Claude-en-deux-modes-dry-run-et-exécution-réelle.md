---
id: task-81
title: Refondre le launcher backlog Claude en deux modes dry-run et exécution réelle
status: In Progress
assignee:
  - Codex
created_date: '2026-03-31 19:13'
updated_date: '2026-04-01 07:54'
labels:
  - tooling
  - claude-code
  - orchestration
dependencies:
  - task-78
priority: medium
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Remplacer le pipeline plan/prepare/verify/execute par un contrat plus simple: un unique lancement qui calcule les tâches parallélisables, prépare les artefacts, puis soit simule les appels LLM en dry-run, soit lance réellement Claude Code sans --dry-run. Les artefacts de sortie doivent rester relisibles et cohérents entre dry-run et exécution réelle.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le script n'expose plus les stages plan/prepare/verify/execute.
- [ ] #2 Le script supporte un mode --dry-run qui simule les appels LLM tout en générant les artefacts attendus.
- [ ] #3 Le mode par défaut exécute le vrai lancement Claude à partir des tâches parallélisables calculées localement.
- [ ] #4 La documentation est alignée sur le nouveau contrat CLI.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Le script backlog_agent_orchestrator.py utilise désormais une phase de décision LLM read-only avant la génération des prompts. Si une tâche est classée `agent_team`, le prompt du top-level subagent lui ordonne de planifier, puis de créer et piloter une agent team interne avec plan approval pour les teammates. L'environnement `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` est injecté sur les appels Claude pertinents lorsque ce mode peut être requis.

Refonte avancée du launcher effectuée: chaque tâche de dispatch_now reçoit maintenant une décision LLM explicite `simple_subagent | agent_team` avant la génération des prompts. Le dry-run génère `execution-mode-result.json`, `prompt-generation-result.json`, `claude-agents.json` et les prompts par tâche avec le mode injecté. Le mode réel n'a pas encore été lancé après cette modification.

Ajout d'un mode `--plan-only-real` : la chaîne Claude est réelle (décision `simple_subagent | agent_team`, génération de prompts, orchestration), mais les top-level subagents et éventuels teammates sont explicitement forcés à s'arrêter au planning. L'orchestration passe en `permission_mode=plan` dans ce mode.

Refonte supplémentaire demandée: séparer la responsabilité LLM en 4 appels séquentiels distincts: (1) décision `simple_subagent | agent_team`, (2) distillation de contexte par tâche, (3) génération de sous-prompt par tâche, (4) génération du prompt d'orchestration global. Objectif: réduire la charge d'un appel unique et améliorer robustesse/qualité.

2026-04-01: ajout d'une écriture incrémentale du bundle de run (`dispatch-plan`, résultats/RAW par phase, prompts, orchestration), persistance de `run-failure.json` et des sorties Claude brutes même en cas d'échec, et durcissement du contrat JSON de l'orchestrateur (selected_task_count, execution_mode, status, validations supplémentaires). Vérifications locales OK: py_compile, ruff, dry-run max-dispatch=2.
<!-- SECTION:NOTES:END -->
