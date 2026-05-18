---
id: task-97
title: Implement mobile daily and weekly digest screens
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
Implement the daily digest ("Your Day in Review") and weekly digest screens showing summarized activity and key insights from processed media.

**Design reference:**
- `mobile-design-mockups/daily_digest_your_day_in_review/` (daily digest)
- `mobile-design-mockups/weekly_digest_harmonized_v2/` (weekly digest)
**Design system:** `mobile-design-mockups/my_design_system/DESIGN.md`

Réutilisation obligatoire:
- Endpoints canoniques: `GET /api/digest/daily`, `GET /api/digest/weekly`

Contraintes: implémenter nativement, contenu scrollable, navigation vers les médias sources.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Écran daily digest affiche le résumé quotidien avec les médias traités
- [ ] #2 Écran weekly digest affiche la synthèse hebdomadaire
- [ ] #3 Navigation vers les médias sources depuis les digests
- [ ] #4 Layout conforme aux mockups daily_digest et weekly_digest_harmonized_v2
- [ ] #5 Contenu scrollable et adapté à tous les viewports
<!-- AC:END -->
