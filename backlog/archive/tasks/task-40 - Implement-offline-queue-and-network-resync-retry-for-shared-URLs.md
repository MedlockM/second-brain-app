---
id: task-40
title: Implement offline queue and network resync/retry for shared URLs
status: To Do
assignee: []
created_date: '2026-02-24 11:04'
updated_date: '2026-05-18 20:27'
labels: []
dependencies:
  - task-93
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement offline-first URL queueing with reliable sync and retry behavior for unstable network conditions.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Shared URLs are queued locally when network is unavailable or degraded.
- [ ] #2 Queued URLs are synchronized automatically when connectivity returns.
- [ ] #3 Retry behavior is bounded and avoids duplicate submissions.
- [ ] #4 Users can distinguish queued, syncing, success, and failed queue states.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Réutilisation existante (obligatoire):
- `front/src/types/media.ts`: définir les états de queue/sync/retry en cohérence avec les statuts canoniques media/job/artifact.
- `front/src/components/JobsInProgress.tsx`: réutiliser la logique de transitions d’état, polling et retry borné.
- `front/src/services/authService.ts`: réutiliser la logique de refresh token pour sécuriser les resync/retries en arrière-plan.
- `front/src/lib/httpError.ts` + `front/src/lib/getFriendlyErrorMessage.ts`: normaliser la catégorisation des erreurs réseau/session.
Contraintes: implémentation offline native requise (persist locale RN), pas de dépendance aux APIs browser.
<!-- SECTION:NOTES:END -->
