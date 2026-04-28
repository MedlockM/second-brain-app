---
id: task-7
title: >-
  Build mobile app UX for share-first flow (ingestion -> transcription ->
  artifacts)
status: To Do
assignee: []
created_date: '2026-01-24 13:06'
updated_date: '2026-02-24 20:55'
labels: []
dependencies:
  - task-39
  - task-40
priority: high
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Validate and finalize native mobile UX quality for the share-first flow: users share any URL into the app, see ingestion/transcription progress, and trigger on-demand artifacts (summary, quiz, notes). Focus on Android + iOS ergonomics, loading/error/offline states, and artifact actions.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Audit core native screens for 320–430px equivalence and modern phone sizes: inbox of shared links, media detail, transcript view, artifact actions, history.
- [ ] #2 No horizontal overflow; key screens are fully usable one-handed with thumb-friendly primary actions (>=44px touch targets).
- [ ] #3 Share entry flow works from external apps to app inbox with clear immediate feedback.
- [ ] #4 Transcription status and errors are explicit and recoverable (retry/cancel/refresh behaviors defined).
- [ ] #5 On-demand actions for summary/quiz/notes are clear, non-blocking, and show per-artifact progress and failure states.
- [ ] #6 Offline/poor network behavior is defined and implemented for shared-link queue and sync.

- [ ] #7 Validated on at least one small viewport and one standard viewport; manual test checklist documented.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Réutilisation existante (obligatoire) pour la passe UX finale:
- `front/src/lib/getFriendlyErrorMessage.ts`: conserver les messages et règles de fallback pour les états erreur critiques/non-critiques.
- `front/src/lib/httpError.ts`: conserver le format et la propagation des erreurs côté client.
- `front/src/components/JobsInProgress.tsx`: reprendre la logique d’états progressifs, feedback, retry et rafraîchissement.
- `front/src/types/media.ts`: vérifier que les écrans couvrent l’ensemble des statuts canoniques media/transcript/artifacts.
- `front/src/utils/validation.ts`: conserver la logique de validation de saisie côté auth/inputs.
Contraintes: l’UI visuelle web actuelle sert de référence fonctionnelle uniquement; implémentation native obligatoire.
<!-- SECTION:NOTES:END -->
