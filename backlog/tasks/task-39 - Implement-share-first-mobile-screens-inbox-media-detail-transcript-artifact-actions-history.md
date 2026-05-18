---
id: task-39
title: >-
  Implement share-first mobile screens (inbox, media detail, transcript,
  artifact actions, history)
status: To Do
assignee: []
created_date: '2026-02-24 11:04'
updated_date: '2026-05-18 15:32'
labels: []
dependencies:
  - task-37
  - task-38
  - task-10
  - task-11
  - task-12
  - task-22
  - task-33
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement the core share-first mobile screens that allow users to track ingestion/transcription and trigger artifact actions from media detail views.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Inbox, media detail, transcript, artifact action, and history screens are implemented.
- [ ] #2 Screens support loading, error, retry, and terminal states consistently.
- [ ] #3 Artifact actions are clear and non-blocking with per-artifact progress visibility.
- [ ] #4 Screen flows are usable on both small and standard mobile viewport sizes.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Réutilisation existante (obligatoire):
- `front/src/types/media.ts`: base de tous les modèles d’écran (inbox, détail média, transcript, actions artefacts, historique).
- `front/src/components/JobsInProgress.tsx`: réutiliser le modèle d’états (`pending/downloading/transcribing/...`), polling et mécanismes retry/refresh.
- `front/src/lib/httpError.ts` + `front/src/lib/getFriendlyErrorMessage.ts`: standardiser affichage des erreurs et recovery UX.
- `front/src/services/episodesService.ts` / `front/src/services/summariesService.ts`: réutiliser le pattern list/detail côté client API, en remplaçant les endpoints legacy par `/api/media/*` et `/api/artifacts/*`.
- `front/src/contexts/MinutesContext.tsx`: réutiliser le pattern de rafraîchissement périodique pour états synchronisés.
Contraintes: ne pas porter les composants web existants tels quels; réimplémenter les vues en natif.

**Design reference:** Use mockups in `mobile-design-mockups/` as visual spec for each screen:
- `inbox_daily_digest_button_ux/` — inbox with digest button
- `media_detail_ai_artifacts_dropdown/` — media detail with artifact actions (collapsed)
- `media_detail_ai_artifacts_expanded/` — media detail with artifact actions (expanded)
- `search_harmonized_v2/` — search screen
- `gestion_des_tags_no_keyboard_space/` — tag management
- `s_lection_de_collection/` — collection selection
- `daily_digest_your_day_in_review/` — daily digest screen
- `weekly_digest_harmonized_v2/` — weekly digest screen
Design system: `my_design_system/DESIGN.md`. All mockups are HTML/Tailwind prototypes; implement natively.
<!-- SECTION:NOTES:END -->
