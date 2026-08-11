---
id: task-244
title: >-
  Add UI entry points to the paywall (Account upgrade CTA + quota-refusal
  trigger)
status: To Do
assignee: []
created_date: '2026-08-11 16:24'
labels:
  - mobile
  - billing
  - feature
  - phase-6
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

`mobile/app/paywall.tsx` existe et fonctionne depuis task-99 (3 tiers RevenueCat : Reader 3 €, Mix 5 €, Audio-Heavy 9 €, Subscribe par tier, Restore purchases, Close). **Mais aucun écran de l'app n'y navigue.**

Audit du code (2026-08-11) :
- `grep -rni "paywall" mobile/app/ mobile/src/` ne retourne, hors `paywall.tsx` lui-même, qu'un **commentaire** dans `PurchasesContext.tsx`.
- Aucun `router.push("/paywall")`, aucun `<Link href>`, aucun bouton « Upgrade » nulle part.
- La route n'est pas déclarée dans `app/_layout.tsx` (elle n'existe que par le routage implicite de fichiers d'expo-router).
- Le seul accès actuel est le deep link `media-summarizer://paywall`, utilisé par `mobile/.maestro/07_paywall.yaml` faute d'alternative. task-170 avait laissé le choix ouvert (« soit via Settings → Upgrade, soit via un trigger explicite — vérifier le path d'entrée actuel ») : la vérification donne qu'il n'y en a aucun.

Conséquence : le paywall est inatteignable pour un utilisateur réel, donc **aucun abonnement ne peut être souscrit dans l'app**. Deux bugs y sont d'ailleurs restés invisibles jusqu'à ce que le flow E2E les révèle (commits f7ab842 et c006f46 : `router.back()` no-op quand la pile est vide, bouton Close sous la Dynamic Island).

## Scope

1. **CTA permanent** dans l'onglet Account (`mobile/app/(tabs)/account.tsx`) : « Upgrade » / « Manage subscription » selon `isSubscribed` de `usePurchases()`, qui pousse `/paywall`.
2. **Déclenchement contextuel au refus de quota.** Le backend renvoie déjà un contrat exploitable — `media_summarizer/api/endpoints/media.py:601-605` répond avec `quota_result.http_status` (403 `tier_quota_exceeded`, 413 `audio_too_long`, …) et l'en-tête `X-Quota-Error-Code`. Côté mobile **rien n'intercepte ces réponses** aujourd'hui. Sur `tier_quota_exceeded`, afficher un message expliquant la limite atteinte avec une action qui ouvre le paywall. Ne pas ouvrir le paywall sur `audio_too_long` : c'est une limite par import, pas un manque d'abonnement.
3. **Déclarer la route** dans `app/_layout.tsx` avec les autres `Stack.Screen`, en modal si cohérent avec les écrans existants.

## Hors scope

- Le gating des fonctionnalités par tier (tâche séparée).
- Le provisioning Google Play (task-238).

## Références

- `mobile/app/paywall.tsx`, `mobile/app/(tabs)/account.tsx`, `mobile/app/_layout.tsx`
- `mobile/src/contexts/PurchasesContext.tsx` (expose déjà `isSubscribed`, `entitlementStatus`)
- `media_summarizer/core/services/quota_enforcer.py` (codes d'erreur), `media_summarizer/api/endpoints/media.py:594-605`
- task-99 (intégration RevenueCat), task-170 (flow E2E paywall), task-110 (moteur de quotas, Done)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The Account tab shows an Upgrade action that opens the paywall, and shows a subscription-management state instead when isSubscribed is true
- [ ] #2 A submission refused by the backend with X-Quota-Error-Code: tier_quota_exceeded surfaces a message naming the limit reached plus an action that opens the paywall
- [ ] #3 A submission refused with audio_too_long surfaces the per-import limit and does NOT open the paywall
- [ ] #4 The paywall route is declared in app/_layout.tsx alongside the other Stack.Screen entries
- [ ] #5 07_paywall.yaml reaches the paywall through the Account CTA instead of the media-summarizer://paywall deep link, and still passes on iOS and Android
- [ ] #6 Closing the paywall returns to the screen that opened it
<!-- AC:END -->
