---
id: task-63
title: Spaced Repetition FSRS sur Flashcards
status: Done
assignee: []
created_date: '2026-03-25 16:08'
updated_date: '2026-04-28 12:00'
labels:
  - feature
  - differentiation
  - flashcards
  - spaced-repetition
  - v1
dependencies:
  - task-64
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Système de spaced repetition basé sur l'algorithme FSRS (Free Spaced Repetition Scheduler) pour les flashcards générées automatiquement. **Quiz exclu de la V1** — seules les flashcards sont concernées.

## Décisions produit (validées 2026-03-29)

- **Algorithme** : FSRS (pas SM-2). Librairies : `fsrs` (Python backend), `ts-fsrs` (TypeScript mobile)
- **Opt-in par média** : au moment du share, l'utilisateur peut activer/désactiver le spaced repetition pour ce média spécifiquement
- **Flashcards auto-générées** : les flashcards sont générées automatiquement après le transcript (pas on-demand) afin d'être disponibles immédiatement pour le scheduling FSRS
- **Sessions de review** : uniquement in-app, pas d'email
- **Notifications push** : "Programme de répétition : testez vos connaissances sur [titre média]"
- **Daily review batché** : 1 seule notification/jour regroupant les flashcards mûres

## Modèle de données

- Par carte : `stability`, `difficulty`, `elapsed_days`, `scheduled_days`, `reps`, `lapses`, `state`, `last_review`
- Table DynamoDB : `review_schedule` (PK: user_id, SK: card_id)
- Settings utilisateur : fréquence, heure, max items/session, opt-out global

## Endpoints API

- GET /api/review/due — flashcards mûres du jour pour l'utilisateur
- POST /api/review/{card_id}/result — résultat (Again/Hard/Good/Easy)
- PATCH /api/user/settings — toggle spaced rep on/off, fréquence, heure

## Pas en V1
- Quiz dans le spaced rep (quiz exclu de V1)
- Cross-content thématique (nécessiterait un knowledge graph)
- Option D du design original (agrégation par thème)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Algorithme FSRS implémenté via librairie fsrs (Python)
- [ ] #2 L'utilisateur peut activer/désactiver le spaced repetition par média au moment du share
- [ ] #3 Les flashcards mûres sont regroupées en une seule notification push quotidienne
- [ ] #4 Endpoint GET /api/review/due retourne les flashcards à réviser
- [ ] #5 Endpoint POST /api/review/{card_id}/result met à jour le scheduling FSRS
- [ ] #6 Settings utilisateur : fréquence, heure, max items/session, opt-out global
- [ ] #7 Modèle DynamoDB review_schedule avec les champs FSRS (stability, difficulty, reps, lapses, state, last_review)
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Dispatch 2026-04-28: Implémentation complétée par agent-task-63. Créé core/models/review_schedule.py (ReviewScheduleRecord, CardState, UserReviewSettings), core/services/fsrs_service.py (intégration librairie fsrs), utils/review_db.py (DynamoDB CRUD), api/endpoints/review.py (GET /api/review/due, POST /api/review/{card_id}/result, PATCH /api/user/settings, POST /api/review/media/{id}/toggle). Modifié flashcards/worker.py pour initialisation automatique des cards FSRS. DynamoDB tables review_schedule et user_review_settings. Ajouté fsrs>=1.0.0 à pyproject.toml. Merged dans second-brain-project.
<!-- SECTION:NOTES:END -->
