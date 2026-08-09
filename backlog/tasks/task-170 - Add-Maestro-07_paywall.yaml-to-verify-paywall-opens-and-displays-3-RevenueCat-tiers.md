---
id: task-170
title: >-
  Add Maestro 07_paywall.yaml to verify paywall opens and displays 3 RevenueCat
  tiers
status: In Progress
assignee:
  - Codex
created_date: '2026-06-10 05:59'
updated_date: '2026-08-09 21:24'
labels:
  - phase-5
  - mobile
  - release
  - tooling
  - e2e
dependencies:
  - task-161
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Phase 5 TDD coverage. Le paywall est le déclencheur de l'IAP en Phase 6. En Phase 5 on ne teste **pas** l'achat (sandbox tester + StoreKit configuration arrivent en Phase 6), mais on doit garantir que :

1. Le paywall **s'ouvre sans crash** depuis son entrypoint
2. Les **3 offerings RevenueCat** (text_only_monthly, mix_monthly, audio_heavy_monthly) sont affichés
3. Pas d'erreur de fetch RevenueCat (le call à `Purchases.getOfferings()` aboutit)

Toute régression côté `mobile/app/paywall.tsx` ou côté init RevenueCat (`mobile/src/services/RevenueCatService.ts` ou équivalent) doit être attrapée par ce flow.

## Scope

Crée `mobile/.maestro/07_paywall.yaml` qui :

1. Lance l'app, authentifie via login email (factorisé)
2. Navigue vers le paywall — soit via Settings → "Upgrade", soit via un trigger explicite (vérifier le path d'entrée actuel dans `mobile/app/paywall.tsx`)
3. Attend l'apparition des labels des 3 tiers (texte connu : ex `Text Only`, `Mix`, `Audio Heavy` — vérifier les labels exacts dans le code)
4. Vérifie qu'aucun message d'erreur RevenueCat n'apparaît
5. Tap "Close" / "X" / back → retour à l'écran précédent sans crash

## Important

- **NE PAS tester l'achat lui-même** — pas de tap sur les CTA "Subscribe"/"Continue" qui déclencheraient un sandbox flow IAP. Le pop-up Apple/Google d'achat ne fonctionne qu'avec sandbox testers actifs (Phase 6).
- Si le paywall affiche le `<PaywallProvider>` de `react-native-purchases-ui`, certaines parties peuvent être en webview hors process — utiliser des selectors texte tolérants.

## Convention

- `appId: com.secondbrainlabs.core`, tags `critical, paywall`
- Pas d'env var sensible nécessaire ; `EXPO_PUBLIC_REVENUCAT_APPLE_KEY` (resp. `_GOOGLE_KEY`) doit être renseigné côté `mobile/.env` (déjà fait au 2026-06-08 pour iOS)
- Timeout généreux pour la première récupération des offerings (jusqu'à 10s).

## References

- `mobile/app/paywall.tsx`
- `docs/V1_LAUNCH_PLAN.md` Phase 6 (IAP sandbox, hors scope ici)
- task-99 (intégration RevenueCat)
- task-86 (V1 pricing config — 3 tiers)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 mobile/.maestro/07_paywall.yaml existe et s'exécute sur les jobs iOS et Android CI
- [x] #2 Le flow vérifie l'ouverture du paywall sans crash
- [ ] #3 Le flow vérifie Reader, Mix et Audio-Heavy ainsi que la disponibilité des trois packages RevenueCat
- [x] #4 Le flow ne déclenche aucun achat sandbox
- [x] #5 Le flow ferme le paywall et vérifie le retour à l'écran précédent
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Ouvrir le paywall par deep link après authentification. 2. Vérifier Reader, Mix et Audio-Heavy et refuser les packages indisponibles. 3. Fermer le paywall sans déclencher d’achat. 4. Utiliser la clé RevenueCat Test Store dans les builds E2E iOS/Android et un SDK React Native compatible. 5. Compiler les binaires autonomes en CI et valider le flow ciblé puis la suite complète sur Android et iOS.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Ajout de `mobile/.maestro/07_paywall.yaml` et de testID stables. Le flow ouvre `media-summarizer://paywall`, vérifie Reader/Mix/Audio-Heavy, échoue si un package est indisponible, ne touche aucun CTA d’achat, puis ferme le paywall.

2026-08-09 — Configuration Test Store finalisée : `text_only_monthly_test` (3 USD), `mix_monthly_test` (5 USD) et `audio_heavy_monthly_test` (9 USD), tous mensuels et sans free trial Store, sont associés respectivement aux packages `text_only`, `mix`, `audio_heavy` de l’offering courant `default`, ainsi qu’à l’entitlement actif `pro`. Vérification API réussie.

2026-08-09 — `react-native-purchases` fixé à 9.5.4. Le workflow CI utilise désormais l’unique secret `E2E_REVENUECAT_TEST_KEY` sur iOS et Android; le placeholder Android a été retiré. TypeScript, ESLint et `npm ci` passent. Les prebuilds Android/iOS réussissent; la compilation Android locale ne peut pas aller plus loin sans Android SDK et sera validée en CI avec la compilation iOS. Les AC #1 et #3 attendent les runs CI.
<!-- SECTION:NOTES:END -->
