---
id: task-244
title: >-
  Add UI entry points to the paywall (Account upgrade CTA + quota-refusal
  trigger)
status: In Progress
assignee: []
created_date: '2026-08-11 16:24'
updated_date: '2026-08-11 16:51'
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
- [x] #1 The Account tab shows an Upgrade action that opens the paywall, and shows a subscription-management state instead when isSubscribed is true
- [x] #2 A submission refused by the backend with X-Quota-Error-Code: tier_quota_exceeded surfaces a message naming the limit reached plus an action that opens the paywall
- [x] #3 A submission refused with audio_too_long surfaces the per-import limit and does NOT open the paywall
- [x] #4 The paywall route is declared in app/_layout.tsx alongside the other Stack.Screen entries
- [ ] #5 07_paywall.yaml reaches the paywall through the Account CTA instead of the media-summarizer://paywall deep link, and still passes on iOS and Android
- [x] #6 Closing the paywall returns to the screen that opened it

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

## Ce qui a été implémenté (2026-08-11)

### Entrée permanente — onglet Account

`mobile/app/(tabs)/account.tsx` : carte dédiée au-dessus de la carte de menu, `testID="account-upgrade-button"`, qui pousse `/paywall`. Le libellé et l'icône suivent `usePurchases()` : « Upgrade » / `sparkles` quand `isSubscribed` est faux, « Manage subscription » / `shield-checkmark` sinon, avec en sous-titre le palier actif (`Reader` / `Mix` / `Audio-Heavy` d'après `entitlementStatus.subscription_tier`, mappé sur les `display_name` de l'endpoint entitlements). Le corps de l'écran passe dans un `ScrollView` (`testID="account-screen"` sur le `SafeAreaView`) : c'est ce qui empêche l'item supplémentaire de rendre `account-sign-out-button` intappable sur petit écran.

### Interception du refus de quota

- `mobile/src/lib/httpError.ts` : `parseErrorResponse` lit `X-Quota-Error-Code` **avant** le corps (un payload illisible ne doit pas coûter le code), et `createHttpError` le porte sur l'erreur (`quotaErrorCode`). Les deux points de levée (`apiClient.ts` pour `ingest-url`, `sharedContentService.ts` pour le multipart texte/audio) le propagent.
- `mobile/src/lib/quotaError.ts` (nouveau) : type `QuotaErrorCode` (`tier_quota_exceeded`, `audio_too_long`, `daily_rate_limit`, `cost_hard_block`), extraction depuis l'erreur, titre par code, et `quotaErrorOffersUpgrade()` qui ne renvoie vrai que pour `tier_quota_exceeded`. Le message affiché est le `detail` du backend **verbatim** : c'est le seul texte qui nomme la limite atteinte, et `getFriendlyErrorMessage` l'aurait écrasé par « You need more minutes or credits to continue. » via sa règle `/quota/`.
- `mobile/src/contexts/ShareIntentContext.tsx` : `quotaErrorCode` ajouté à `ShareIntakeState`, alimenté par `toSubmissionError()` dans les deux chemins de soumission, remis à `null` par `retry()`.
- `mobile/app/share-confirmation.tsx` : état d'erreur conscient du quota — icône `lock-closed` ambre au lieu de `alert-circle` rouge, titre par code (« Plan limit reached », « Audio too long », « Daily limit reached », « Imports paused »), et bouton `share-quota-upgrade-button` (« See plans » → `/paywall`) **uniquement** sur `tier_quota_exceeded`. « Try again » reste présent : après un achat, il permet de renvoyer la même soumission.

Le contrat backend n'a pas été touché : `media_summarizer/api/error_handling.py:30` réémet déjà `exc.headers`, donc l'en-tête arrive bien au client, et le corps `{"detail": …}` est déjà mappé sur `message` par `parseErrorResponse`.

### Route et flows

- `mobile/app/_layout.tsx` : `<Stack.Screen name="paywall">` déclarée en `presentation: "modal"` + `slide_from_bottom`, comme `bug-report` et `share-confirmation`. L'écran appelant reste monté, donc `dismiss()` (`router.back()` derrière `canGoBack()`) revient bien dessus ; le repli `router.replace("/(tabs)")` reste utile pour l'entrée par deep link.
- `mobile/.maestro/07_paywall.yaml` : entre par l'onglet Account (`account-tab-button` → `account-upgrade-button`) au lieu de `media-summarizer://paywall` ; tout le contournement du dialogue iOS « Open in … » (tap positionnel à 67%,56% + `launchApp stopApp:false`) disparaît. Le `scrollUntilVisible` vers `paywall-close-button` est remplacé par un `assertVisible` : le bouton est dans l'en-tête fixe, et un swipe vers le bas dans une sheet iOS serait interprété comme un dismiss. La fin du flow assère la disparition du paywall puis `account-screen` (retour à l'appelant, plus l'inbox).
- `mobile/.maestro/utils/sign_out.yaml` : attend `account-screen` puis `scrollUntilVisible` sur `account-sign-out-button` avant de taper (no-op quand la ligne est déjà à l'écran). Corrige d'un coup les trois flows qui passent par `ensure_logged_out.yaml` (01_login, 06_search, 07_paywall).

### Vérifications exécutées

- `cd mobile && npm run typecheck` : OK.
- `npx eslint` sur les 9 fichiers touchés : 0 erreur, 4 warnings **préexistants** (`any` dans les `catch` de `paywall.tsx`, imports de types inutilisés dans `sharedContentService.ts`).
- Les deux YAML Maestro modifiés parsent (2 documents, 22 et 7 steps).
- Aucun test automatisé ajouté (règle projet pour cet agent).

### Reste à faire — critères #5, #7, #8

Non cochés : ils exigent un run vert, impossible depuis le sandbox de l'agent (pas d'émulateur Android, pas de simulateur iOS, `maestro`/`adb` absents). Le code et les flows sont prêts ; il manque l'exécution CI :

- Android tourne automatiquement sur la PR (`mobile-e2e-maestro.yml`, déclencheur `pull_request` sur `mobile/**`).
- iOS est `workflow_dispatch` uniquement : lancer « Mobile E2E Tests (Maestro) » avec `platform: both` (ou `ios`) sur la branche. Le diff touche `mobile/` hors `.maestro`, donc l'empreinte de build change et les trois flows sont rejoués sans reprise de cache.
- Points de vigilance au premier run : la sheet modale iOS du paywall (géométrie du bouton Close, `notVisible: paywall-screen` après fermeture) et le `scrollUntilVisible` de `sign_out.yaml` sur l'écran Account devenu scrollable.
<!-- SECTION:NOTES:END -->
