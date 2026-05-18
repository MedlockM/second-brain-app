---
id: task-36
title: 'Implement mobile foundation (app shell, navigation, auth/refresh session)'
status: Done
assignee: []
created_date: '2026-02-24 11:04'
updated_date: '2026-05-18 15:32'
labels: []
dependencies:
  - task-18
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Build the mobile application foundation required for share-first flows, including app shell, navigation, and authenticated session handling.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 App shell and navigation architecture are in place for the primary mobile flows.
- [ ] #2 Authentication and refresh-session behavior is integrated and stable.
- [ ] #3 Session failure/expiry states are handled with consistent UX behavior.
- [ ] #4 Foundation is ready for native share entrypoint integration.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Réutilisation existante (obligatoire):
- `front/src/services/authService.ts`: réutiliser la logique login/register/refresh/logout et la stratégie `getValidToken`; adapter le stockage token pour mobile (SecureStore/Keychain) et supprimer l’usage direct de `localStorage`/`sessionStorage`.
- `front/src/App.tsx`: réutiliser la logique d’amorçage de session au démarrage + refresh programmé avant expiration.
- `front/src/lib/httpError.ts` et `front/src/lib/getFriendlyErrorMessage.ts`: mutualiser la gestion d’erreurs API et les messages UX.
- `front/src/utils/validation.ts` et `front/src/types/auth.ts`: reprendre les validations/formats auth existants.
- `front/src/services/settingsService.ts` / `front/src/services/billingService.ts`: réutiliser le pattern de client API (headers auth, parsing d’erreurs) si nécessaire.
Contraintes: ne pas porter les primitives web telles quelles (`import.meta.env`, router web, DOM/Tailwind).

**Design reference:** Use mockups in `mobile-design-mockups/` as visual spec. Key files:
- `my_design_system/DESIGN.md` — design system (colors, typography, elevation, components)
- `account_harmonized_v2/` — account screen layout and navigation pattern
All mockups are HTML/Tailwind prototypes; implement natively in the chosen mobile framework.
<!-- SECTION:NOTES:END -->
