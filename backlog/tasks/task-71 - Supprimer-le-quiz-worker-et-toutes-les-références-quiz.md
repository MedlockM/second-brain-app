---
id: task-71
title: Supprimer le quiz worker et toutes les références quiz
status: Done
assignee: []
created_date: '2026-03-29 21:01'
labels:
  - cleanup
  - v1
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Les quiz sont exclus de la V1. Le quiz worker existe encore dans la codebase et doit être supprimé, ainsi que toutes les références associées.

## Fichiers à supprimer/nettoyer

- `media_summarizer/workers/quiz/worker.py` — supprimer le worker
- `media_summarizer/workers/quiz/` — supprimer le dossier entier
- Références dans `docker-compose.dev.yml` (service quiz-worker si existant)
- Références dans les configs Terraform (queue quiz si existante)
- Références dans les modèles (artifact_type "quiz" dans les enums)
- Références dans les tests unitaires existants
- Variable d'environnement ENABLE_QUIZ_GENERATION / ENABLE_QUIZ_EMAIL
- Queue SQS quiz-queue dans les configs

## Contraintes
- Ne pas casser les autres workers ou le pipeline existant
- Les artefacts quiz déjà générés en base peuvent rester (pas de migration destructive)
- Le type "quiz" peut rester dans les enums pour backward-compatibility en lecture, mais ne doit plus être générable
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Quiz worker supprimé (dossier media_summarizer/workers/quiz/)
- [ ] #2 Références quiz dans docker-compose.dev.yml nettoyées
- [ ] #3 Références quiz dans Terraform nettoyées
- [ ] #4 Variables ENABLE_QUIZ_GENERATION et ENABLE_QUIZ_EMAIL supprimées
- [ ] #5 Le pipeline de génération d'artefacts ne peut plus déclencher de quiz
- [ ] #6 Les autres workers et le pipeline existant fonctionnent toujours
<!-- AC:END -->
