---
id: task-64
title: 'Artefact Flashcards (Q/R simple, auto-généré post-transcript)'
status: Done
assignee: []
created_date: '2026-03-25 16:12'
updated_date: '2026-04-22 14:07'
labels:
  - feature
  - flashcards
  - artifact
  - v1
dependencies:
  - task-33
  - task-34
  - task-72
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Ajouter les Flashcards comme type d'artefact. **Format V1 : Question/Réponse simple uniquement.** Les flashcards sont **read-only** (non éditables par l'utilisateur) et **générées automatiquement après le transcript** (pas on-demand) pour être disponibles immédiatement dans le spaced repetition program.

## Spécification V1

### Format
- Question / Réponse simple (pas de cloze deletion, pas de terme/définition, pas de cards réversibles en V1)
- 5-15 flashcards par média selon la longueur du contenu
- Read-only : l'utilisateur ne peut pas créer/éditer/supprimer de flashcards

### Génération
- **Automatique post-transcript** : dès qu'un transcript est prêt, le worker flashcards est déclenché automatiquement
- Le LLM utilisé est configurable (pas verrouillé sur GPT-4 — à déterminer par benchmark)
- Même pattern de déduplication (generation_fingerprint) que les autres artefacts
- Le système d'idempotence des artefacts s'applique : toute feature (on-demand, spaced rep, digest) cherche d'abord dans l'historique avant de demander une génération

### Règles de qualité (prompt LLM)
- Principe de minimum information (1 concept par card)
- Pas de cards triviales
- Pas de cards ambiguës (réponse unique et vérifiable)

## Aspects techniques

- Nouveau worker : `media_summarizer/workers/flashcards/worker.py`
- Nouveau type d'artefact : `artifact_type = "flashcards"`
- Nouvelle queue SQS : `FLASHCARDS_QUEUE`
- Stockage S3 aligné sur les autres artefacts
- Trigger automatique depuis le pipeline de complétion (pas on-demand)
- Endpoints API via les endpoints canoniques existants (GET /api/media/{id}/artifacts, GET /api/artifacts/{id})

## Hors scope V1
- Édition/création manuelle de flashcards
- Cards réversibles
- Niveaux de difficulté
- Tags sur les flashcards
- Frontend (construit séparément dans Stitch)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Worker flashcards fonctionnel avec prompt LLM dédié (modèle configurable)
- [ ] #2 Format Q/R simple : 5-15 flashcards par média
- [ ] #3 Génération automatique déclenchée après la complétion du transcript
- [ ] #4 Flashcards read-only (pas d'édition utilisateur)
- [ ] #5 Stockage S3 + modèle DynamoDB aligné sur les artefacts existants (generation_fingerprint)
- [ ] #6 Queue SQS FLASHCARDS_QUEUE configurée
- [ ] #7 Artefacts récupérables via les endpoints canoniques existants (/api/media/{id}/artifacts, /api/artifacts/{id})
<!-- AC:END -->
