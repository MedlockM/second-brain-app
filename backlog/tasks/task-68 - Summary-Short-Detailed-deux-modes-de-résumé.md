---
id: task-68
title: Summary Short + Detailed (deux modes de résumé)
status: Done
assignee: []
created_date: '2026-03-29 21:01'
updated_date: '2026-04-23 08:58'
labels:
  - feature
  - artifact
  - v1
dependencies:
  - task-11
  - task-33
  - task-34
  - task-72
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Le résumé doit exister en deux modes distincts : **Short** (adapté au format digest/newsletter in-app) et **Detailed** (adapté à l'apprentissage, exhaustif). Ce sont deux artefacts distincts générés indépendamment.

## Spécification V1

### Summary Short
- Format concis adapté à la consultation rapide dans le digest
- Utilisé par défaut dans le daily/weekly digest
- Bullet points ou paragraphe court

### Summary Detailed
- Format exhaustif adapté à l'apprentissage
- Structuré en sections (contexte, points clés, citations, conclusion)
- Plus long et approfondi

### Comportement
- Les deux sont des artifact_type distincts : `summary_short` et `summary_detailed`
- Générés on-demand (sauf Summary Short qui peut être pré-généré pour le digest)
- Le LLM utilisé est configurable (à déterminer par benchmark)
- Même pattern de déduplication (generation_fingerprint) que les autres artefacts

## Aspects techniques
- Deux prompts LLM distincts
- Deux artifact_type dans le modèle MediaArtifact
- Endpoints via les endpoints canoniques existants
- Le summarization_worker actuel doit supporter les deux modes (paramètre dans le message SQS)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Summary Short générable (format concis, adapté digest)
- [ ] #2 Summary Detailed générable (format exhaustif, adapté apprentissage)
- [ ] #3 Deux artifact_type distincts : summary_short et summary_detailed
- [ ] #4 Prompts LLM dédiés pour chaque mode
- [ ] #5 Modèle LLM configurable (pas hardcodé)
- [ ] #6 Déduplication via generation_fingerprint
- [ ] #7 Récupérables via les endpoints canoniques existants
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Dispatch 2026-04-23: Implémentation complétée par agent-task-68. Ajout de summary_short et summary_detailed comme artifact types distincts avec prompts dédiés, modèle LLM configurable, et worker unifié. Merged dans second-brain-project.
<!-- SECTION:NOTES:END -->
