---
id: task-41
title: Run manual mobile E2E validation matrix for share-first flows
status: To Do
assignee: []
created_date: '2026-02-24 11:04'
updated_date: '2026-05-18 20:27'
labels: []
dependencies:
  - task-93
  - task-94
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Validate share-first mobile behavior end-to-end across a manual test matrix of source apps, devices, and network conditions.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A manual E2E matrix covers Android and iOS with representative source apps.
- [ ] #2 Matrix includes normal, degraded network, and offline-to-online scenarios.
- [ ] #3 Results clearly identify pass/fail outcomes and blocking issues.
- [ ] #4 Validation evidence is documented for release readiness gates.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Références existantes à utiliser pour la matrice de validation:
- `front/src/types/media.ts`: vérifier explicitement chaque statut canonique attendu (ingestion, transcript, artefacts, erreurs).
- `front/src/components/JobsInProgress.tsx`: dériver les cas de test sur progression, retry, terminal states.
- `front/src/lib/getFriendlyErrorMessage.ts`: vérifier cohérence des messages d’erreur affichés en mobile.
Objectif: la validation E2E doit couvrir les comportements déjà standardisés dans ces modules partagés, pas réinventer une grille différente.
<!-- SECTION:NOTES:END -->
