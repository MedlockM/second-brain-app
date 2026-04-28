---
id: task-38
title: Implement iOS Share Extension to app inbox flow
status: To Do
assignee: []
created_date: '2026-02-24 11:04'
updated_date: '2026-02-24 20:55'
labels: []
dependencies:
  - task-36
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement native iOS share extension entry so links shared from external apps are received and stored in the app inbox flow.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The app share extension is available from iOS share sheet for supported URL sharing.
- [ ] #2 Incoming shared URLs are received and persisted in the app inbox flow.
- [ ] #3 User feedback is immediate and clear after sharing into the app.
- [ ] #4 Share intake handles invalid payloads safely and predictably.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Réutilisation existante (obligatoire):
- `front/src/types/media.ts`: utiliser `IngestUrlRequest`, `IngestUrlResponse`, `MediaStatusResponse`, statuts canoniques pour l’inbox iOS.
- `front/src/lib/httpError.ts` et `front/src/lib/getFriendlyErrorMessage.ts`: conserver le mapping d’erreurs utilisateur pour l’extension iOS/app cible.
- `front/src/services/podcastService.ts`: reprendre le pattern de client HTTP (gestion erreurs/réponses), sans réutiliser les routes podcast legacy.
- `front/src/components/JobsInProgress.tsx`: réutiliser la logique de progression/retry pour le feedback post-partage.
Contraintes: portage logique seulement, pas de composants DOM/Tailwind ni dépendances browser.
<!-- SECTION:NOTES:END -->
