---
id: task-93
title: Implement mobile inbox screen with processing states and polling
status: To Do
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
Implement the inbox screen showing shared media items with their processing states (pending, downloading, transcribing, completed, failed). Include polling for live status updates and retry/refresh mechanisms.

**Design reference:** `mobile-design-mockups/inbox_daily_digest_button_ux/` (layout, digest button UX)
**Design system:** `mobile-design-mockups/my_design_system/DESIGN.md`

Réutilisation obligatoire:
- `front/src/types/media.ts`: modèles d'écran inbox, statuts `ProcessingJobLifecycleStatus`
- `front/src/components/JobsInProgress.tsx`: modèle d'états, polling, retry/refresh
- `front/src/lib/httpError.ts` + `front/src/lib/getFriendlyErrorMessage.ts`: erreurs et recovery UX
- Endpoints canoniques: `GET /api/media` (liste), polling sur statuts

Contraintes: implémenter nativement en React Native/Expo, pas de portage DOM/Tailwind.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Inbox affiche la liste des médias partagés avec leur statut de traitement
- [ ] #2 Polling live pour mise à jour des statuts (pending → transcribing → completed)
- [ ] #3 États loading, error, retry et terminal gérés de manière cohérente
- [ ] #4 Layout conforme au mockup inbox_daily_digest_button_ux
- [ ] #5 Fonctionne sur petits et grands viewports mobile
<!-- AC:END -->
