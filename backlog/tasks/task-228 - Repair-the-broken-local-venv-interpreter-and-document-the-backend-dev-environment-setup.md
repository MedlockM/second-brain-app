---
id: task-228
title: >-
  Repair the broken local venv interpreter and document the backend dev
  environment setup
status: Done
assignee:
  - Codex
created_date: '2026-08-05 18:17'
updated_date: '2026-08-06 01:03'
labels:
  - tooling
  - dx
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Découvert pendant le dispatch de task-223. Deux symptômes cumulés :

1. `ruff` et `mypy` ne sont pas sur le PATH. Il faut les invoquer via `.venv/bin/ruff` et `.venv/bin/mypy`. Aucune documentation ne le mentionne, ce qui fait perdre du temps à chaque agent et à chaque nouveau contributeur.
2. L'interpréteur du venv était signalé cassé depuis le 2026-07-31 (noté dans la description de task-223). L'agent task-223 a contourné le problème en construisant un venv parallèle `.venv-task223/` de 348 Mo **à la racine du repo principal**, non gitignoré. Je l'ai supprimé, mais la cause reste.

Risque associé : un venv non gitignoré à la racine casse le garde-fou de `scripts/dispatch_backlog.sh` sur les fichiers non commités et peut se retrouver accidentellement ajouté à un commit.

## Objectif

Rendre l'environnement de dev backend reproductible et documenté.

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 #1 #1 L'état du venv .venv est diagnostiqué et réparé, ou une procédure de recréation propre est documentée
- [x] #2 #2 #2 ruff et mypy sont invocables de façon documentée et reproductible
- [x] #3 #3 #3 .gitignore couvre les variantes de venv par un motif générique (par ex. .venv*) pour éviter qu'un venv ad-hoc devienne untracked à la racine
- [x] #4 #4 #4 AGENTS.md ou un doc de setup indique la commande exacte pour lancer ruff, mypy et pytest
- [x] #5 #5 #5 Les fichiers backlog/tasks non commités (task-221, 222, 223) sont commités ou le garde-fou du dispatcher est étendu aux fichiers untracked du backlog
<!-- SECTION:DESCRIPTION:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Documenter le diagnostic local : le venv est actuellement exécutable (Python 3.10.19, ruff et mypy présents), mais son pyvenv.cfg conserve un ancien chemin VS Code/uv disparu ; fournir une recréation uv propre qui ne dépend pas d’un chemin Snap versionné.
2. Généraliser .gitignore à toutes les variantes racine .venv* afin qu’un environnement ad hoc ne devienne jamais un fichier non suivi.
3. Renforcer scripts/dispatch_backlog.sh : refuser explicitement tout fichier non suivi sous backlog/tasks, tout en conservant un avertissement pour les autres fichiers non suivis.
4. Documenter les commandes exactes ruff, mypy et pytest via les binaires du venv, puis valider syntaxe du script, motifs gitignore et disponibilité des outils.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implémentation terminée :
- Diagnostic local : .venv exécute Python 3.10.19 et contient ruff 0.12.7, mypy 1.17.1 et pytest 9.0.3. pyvenv.cfg conservait toutefois un ancien chemin Snap VS Code disparu, alors que le symlink Python actif cible le runtime uv courant.
- README.md documente une recréation indépendante du PATH avec uv venv --clear --python 3.10 .venv puis uv pip install --python .venv/bin/python -e ".[dev]", ainsi que les commandes exactes ruff/mypy/pytest.
- .gitignore utilise désormais .venv*/ et couvre les variantes ad hoc.
- dispatch_backlog.sh échoue avant dispatch lorsqu’un fichier non suivi existe sous backlog/tasks ; les autres fichiers non suivis restent un avertissement.

Validation :
- bash -n scripts/dispatch_backlog.sh : succès.
- git check-ignore confirme .venv-task223, .venv-foo et .venv311.
- Les quatre outils du venv répondent avec leurs versions.
- ./scripts/dispatch_backlog.sh --dry-run : exit 1 attendu et liste les tâches backlog non suivies, dont task-221/222/223.
- git diff --check : succès.
<!-- SECTION:NOTES:END -->

<!-- AC:END -->

<!-- AC:END -->
