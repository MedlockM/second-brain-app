---
id: task-170
title: >-
  Add Maestro 07_paywall.yaml to verify paywall opens and displays 3 RevenueCat
  tiers
status: To Do
assignee: []
created_date: '2026-06-10 05:59'
labels:
  - phase-5
  - mobile
  - release
  - tooling
  - e2e
dependencies:
  - task-161
  - task-162
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
- [ ] #1 mobile/.maestro/07_paywall.yaml existe et passe en local
- [ ] #2 Vérifie l'ouverture du paywall sans crash
- [ ] #3 Vérifie l'affichage des 3 tiers RevenueCat (labels)
- [ ] #4 Aucun tap sur les CTA d'achat (sandbox IAP réservé à Phase 6)
- [ ] #5 Vérifie que la fermeture du paywall ramène sur l'écran précédent sans crash
<!-- AC:END -->
