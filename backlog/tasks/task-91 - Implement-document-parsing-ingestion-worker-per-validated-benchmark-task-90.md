---
id: task-91
title: Implement document parsing ingestion worker per validated benchmark (task-90)
status: To Do
assignee: []
created_date: '2026-04-29 17:14'
labels:
  - feature
  - ingestion
dependencies:
  - task-90
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implémenter le worker d'ingestion de fichiers uploadés par l'user en suivant la solution retenue par l'owner dans `docs/research/task-90-document-parser-benchmark/README.md` (section Owner Validation → Decision).

L'implémenteur doit :
1. Lire la décision finale de l'owner dans le README du benchmark
2. Intégrer le parser choisi dans le pipeline d'ingestion existant
3. Supporter tous les formats validés dans la décision
4. Respecter l'architecture hexagonale en place (resolver pattern dans `media_summarizer/infrastructure/resolvers/`)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Worker d'ingestion fonctionnel pour les formats validés par l'owner
- [ ] #2 Intégration dans le pipeline existant (endpoint /api/media)
- [ ] #3 Gestion d'erreur pour les formats non supportés
- [ ] #4 Extraction de texte structuré exploitable par le pipeline LLM en aval
<!-- AC:END -->
