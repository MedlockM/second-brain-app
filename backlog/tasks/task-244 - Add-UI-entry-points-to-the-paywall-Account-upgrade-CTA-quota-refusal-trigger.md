---
id: task-244
title: >-
  Add UI entry points to the paywall (Account upgrade CTA + quota-refusal
  trigger)
status: To Do
assignee: []
created_date: '2026-08-11 16:24'
updated_date: '2026-08-11 16:32'
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

- [ ] #7 utils/sign_out.yaml still reaches account-sign-out-button with the new Upgrade menu item present — if the item pushes it out of view, the flow scrolls to it or the Account screen becomes scrollable
- [ ] #8 01_login, 06_search and 07_paywall all pass on iOS and Android in the same run as the UI change, not in a follow-up
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Impact E2E à traiter dans cette même tâche

Ajouter un item au menu Account n'affecte pas seulement le flow paywall :

- `utils/sign_out.yaml` tape `account-sign-out-button`, et il est appelé par `utils/ensure_logged_out.yaml`, lui-même utilisé par **01_login, 06_search et 07_paywall**. Un item de plus dans le menu impacte donc les trois flows.
- `mobile/app/(tabs)/account.tsx` **n'est pas scrollable** (`SafeAreaView` + carte de menu à hauteur fixe, aucun `ScrollView`). Un item supplémentaire peut pousser le bouton de déconnexion hors de la zone visible : le tap échoue alors sans message explicite, exactement le mode d'échec débusqué en août 2026 sur la suite iOS (bouton Close du paywall sous la Dynamic Island).

Les flows doivent donc être ajustés **dans la même PR** que le changement d'UI, pas dans une tâche de suivi : sinon `main` reste rouge dans l'intervalle. Le mécanisme de cache de `.github/scripts/run-ios-maestro.sh` rejouera automatiquement les trois flows, puisque toute modification du binaire invalide l'empreinte de build.
<!-- SECTION:NOTES:END -->
