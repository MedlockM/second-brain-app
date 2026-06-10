---
id: task-187
title: Refactor mobile share intent to use expo-share-intent v6 official API
status: Done
assignee: []
created_date: '2026-06-10 21:51'
labels:
  - mobile
  - release
  - phase-5
  - tech-debt
  - blocker-share
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Description

Pendant les smoke tests Phase 5 (task-160 / task-181), un partage Instagram → app a échoué avec « Unmatched Route Page could not be found ». Cause racine : `expo-share-intent@6.x` (installé) envoie l'URL au format `media-summarizer://dataUrl=<extensionKey>?nonce=<uuid>#weburl` — il faut **lire les données réelles dans App Groups** via `ExpoShareIntentModule.getShareIntent(url)`. Mais le projet a une **implémentation custom maison** (`mobile/src/hooks/useShareIntent.ts` + `mobile/src/contexts/ShareIntentContext.tsx`, ~822 LoC) qui parse l'URL naïvement avec `Linking.parse` et tombe à l'eau sur ce format → expo-router voit un pathname `/dataUrl=...` invalide → écran Unmatched Route.

Diagnostic complet dans la session du 2026-06-10 (URL exacte capturée dans les logs Metro).

## Scope

Remplacer l'implémentation custom par l'API officielle de `expo-share-intent@^6.1` :

1. **Ajouter `ShareIntentProvider` du package** au root layout (`mobile/app/_layout.tsx`) en plus du `ShareIntentProvider` custom actuel — ou remplacer.
2. **Refondre `mobile/src/contexts/ShareIntentContext.tsx`** pour consommer `useShareIntentContext` (du package) au lieu de poller `Linking` à la main. Le hook officiel retourne un objet `{ webUrl, text, files, type, meta }` déjà résolu depuis App Groups.
3. **Refondre `mobile/src/hooks/useShareIntent.ts`** pour soit le supprimer (le Provider du package fait le boulot), soit le réduire à un thin wrapper.
4. **Préserver le contrat public `useShareIntake()`** consommé par `mobile/app/share-confirmation.tsx` (interface `ShareIntakeState` avec `status`, `url`, `rawText`, `contentType`, `audioFile`, etc.). On peut garder ce nom et adapter l'implémentation à l'intérieur.
5. **Conserver les 2 routes** `/share-confirm` (URL flow simple via params) et `/share-confirmation` (full flow via context).
6. **Préserver les flows non-Instagram** : Android intent filters (`text/plain`, `audio/*`), WhatsApp text/audio, share extension iOS pour les types `web url` / `text` / `file`.

## Tests manuels (owner-only)

Sur dev build iOS sideloadé :
1. Partager un **Reel Instagram** → écran share-confirmation avec l'URL Instagram extraite.
2. Partager une page **Safari** (article web) → écran share-confirmation.
3. Partager un **message WhatsApp** texte → écran share-confirmation, contentType=text.
4. Partager un **vocal WhatsApp** (audio) → écran share-confirmation, contentType=audio.
5. Aucune régression sur les imports d'app non-share (deep link `media-summarizer://` direct).

## Références

- Docs officielles : https://github.com/achorein/expo-share-intent#usage
- Code package : `mobile/node_modules/expo-share-intent/build/useShareIntent.js`, `ShareIntentProvider.js`, `utils.js`
- Format URL bloquant : `media-summarizer://dataUrl=<key>?nonce=<uuid>#weburl` (capturé dans les logs Metro 2026-06-10 ~23:44)
- Code custom à remplacer : `mobile/src/hooks/useShareIntent.ts` (240 LoC), `mobile/src/contexts/ShareIntentContext.tsx` (582 LoC)
- Consumers à preserver : `mobile/app/share-confirm.tsx`, `mobile/app/share-confirmation.tsx`, `mobile/src/components/ShareIntentHandler.tsx`

## Dette identifiée pendant le diagnostic

- Le custom `useShareIntent` n'a JAMAIS appelé l'API officielle du package depuis l'install initial — c'était un placeholder qui marchait par hasard sur les flows Android et WhatsApp parce qu'eux passent par `Linking` standard. Instagram + expo-share-intent v6 utilisent App Groups iOS sans toucher Linking → c'est ce qui a fait apparaître le bug.
- Le package `expo-share-intent` est dans `mobile/package.json` depuis longtemps mais ses APIs ne sont pas consommées : c'est de la dette technique pure.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 mobile/src/contexts/ShareIntentContext.tsx consomme useShareIntentContext du package expo-share-intent (plus de polling Linking custom)
- [ ] #2 mobile/src/hooks/useShareIntent.ts est supprimé OU réduit à un wrapper trivial
- [ ] #3 mobile/app/_layout.tsx wrappe l'arbre avec le ShareIntentProvider du package
- [ ] #4 Le contrat public useShareIntake() / ShareIntakeState reste compatible (consumers share-confirm.tsx + share-confirmation.tsx inchangés ou minimalement adaptés)
- [ ] #5 Partager un reel Instagram depuis l'app Instagram aboutit sur l'écran share-confirmation avec webUrl renseignée (plus de Unmatched Route)
- [ ] #6 Partager un lien Safari, un texte WhatsApp et un audio WhatsApp continuent de fonctionner sans régression
- [ ] #7 npm run typecheck passe sans erreur
- [ ] #8 Aucun console.log de debug ne reste après la session
<!-- AC:END -->
