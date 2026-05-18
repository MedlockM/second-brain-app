---
id: task-94
title: Implement mobile media detail screen with artifact actions
status: Done
assignee: []
created_date: '2026-05-18 20:27'
labels:
  - feature
  - mobile
dependencies:
  - task-37
  - task-38
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the media detail screen showing transcript content and artifact action buttons (summary, flashcards, notes). Include collapsed/expanded states for artifacts, per-artifact progress visibility, and generation triggers.

**Design reference:**
- `mobile-design-mockups/media_detail_ai_artifacts_dropdown/` (collapsed state)
- `mobile-design-mockups/media_detail_ai_artifacts_expanded/` (expanded state)
**Design system:** `mobile-design-mockups/my_design_system/DESIGN.md`

Réutilisation obligatoire:
- `front/src/types/media.ts`: modèles media detail, transcript, artifact status
- `front/src/services/summariesService.ts`: pattern list/detail côté client API → `GET /api/media/{id}`, `GET /api/artifacts/{media_id}`
- `front/src/lib/httpError.ts` + `front/src/lib/getFriendlyErrorMessage.ts`: erreurs

Contraintes: implémenter nativement, actions non-bloquantes avec progress par artefact.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Écran media detail affiche le transcript et les métadonnées du média
- [ ] #2 Actions artefacts (summary, flashcards, notes) avec états collapsed/expanded
- [ ] #3 Progress visible par artefact pendant la génération
- [ ] #4 Actions non-bloquantes (l'user peut naviguer pendant la génération)
- [ ] #5 Layout conforme aux mockups media_detail_ai_artifacts_dropdown et expanded
<!-- AC:END -->
