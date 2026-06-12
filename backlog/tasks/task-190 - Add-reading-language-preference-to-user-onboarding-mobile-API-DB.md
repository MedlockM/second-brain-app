---
id: task-190
title: Add reading-language preference to user onboarding (mobile + API + DB)
status: To Do
assignee: []
created_date: '2026-06-11 10:00'
labels:
  - feature
  - mobile
  - api
dependencies:
  - task-189
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Demander à l'user sa langue de lecture préférée pendant l'onboarding mobile et la persister côté backend, pour que le pipeline d'ingestion puisse ensuite l'utiliser pour prioriser les transcripts dans cette langue (cf. task-191) et déclencher la traduction LLM en fallback (cf. task-192).

Périmètre :
1. **Mobile** — ajouter un écran d'onboarding (ou étape post-register) qui demande la langue de lecture. Pré-sélectionner la langue système du device par défaut. Liste de langues alignée avec celles validées V1 dans le benchmark task-189.
2. **Settings** — exposer le réglage dans l'écran Settings pour que l'user puisse le changer ultérieurement (avec préview de l'impact : "le contenu existant ne sera pas re-traduit").
3. **API** — endpoint `PATCH /api/users/me` (ou équivalent existant) pour persister `reading_language` (ISO 639-1, ex: `fr`, `en`).
4. **DB** — migration ajoutant la colonne `reading_language` à la table users, NOT NULL avec default sur la langue système ou `en` selon décision.
5. **Lecture de la préférence** — exposer la valeur via le contexte mobile (`AuthContext` ou nouveau `UserPreferencesContext`) et via la session côté API pour que les workers d'ingestion puissent la lire.

Cette tâche ne touche PAS au pipeline d'ingestion ni à la traduction — elle pose juste les fondations data + UX. Les tâches task-191 (priorisation transcript) et task-192 (traduction fallback) consomment cette préférence.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Écran d'onboarding mobile demandant la langue de lecture avec pré-sélection de la langue système
- [ ] #2 Réglage modifiable depuis l'écran Settings avec disclaimer sur le contenu existant non re-traduit
- [ ] #3 Endpoint API persistant `reading_language` (ISO 639-1) sur le user
- [ ] #4 Migration DB ajoutant la colonne `reading_language` avec default sensé
- [ ] #5 Préférence accessible côté mobile via contexte et côté API via session/user lookup pour les workers d'ingestion
- [ ] #6 Liste de langues V1 alignée avec la décision owner du benchmark task-189
- [ ] #7 Tests : onboarding flow, update via settings, persistance API
<!-- AC:END -->
