---
id: task-37
title: Implement Android Share Intent to app inbox flow
status: To Do
assignee: []
created_date: '2026-02-24 11:04'
updated_date: '2026-05-18 15:32'
labels: []
dependencies:
  - task-36
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement native Android share-intent entry so links shared from external apps are received and stored in the app inbox flow.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The app appears as a share target on Android for supported URL sharing.
- [ ] #2 Incoming shared URLs are received and persisted in the app inbox flow.
- [ ] #3 User feedback is immediate and clear after sharing into the app.
- [ ] #4 Share intake handles invalid payloads safely and predictably.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Réutilisation existante (obligatoire):
- `front/src/types/media.ts`: utiliser `IngestUrlRequest`, `IngestUrlResponse`, `MediaStatusResponse`, statuts `ProcessingJobLifecycleStatus`/`ArtifactStatus` pour structurer l’inbox Android.
- `front/src/lib/httpError.ts` et `front/src/lib/getFriendlyErrorMessage.ts`: harmoniser les erreurs de share intake (payload invalide, non supporté, session expirée).
- `front/src/services/podcastService.ts`: réutiliser le pattern technique du client API (fetch typé + `parseErrorResponse`), mais ne pas réutiliser les endpoints podcast legacy.
- `front/src/components/JobsInProgress.tsx`: reprendre la logique de feedback immédiat + retry/refresh (pas le JSX web).
Contraintes: réécrire l’UI en React Native; ne réutiliser que logique/contrats.

**Design reference:** Use `mobile-design-mockups/confirmation_de_partage_version_finale/` for the share confirmation screen (layout, feedback UX, animations). Implement natively.
<!-- SECTION:NOTES:END -->
