---
id: task-188
title: >-
  Fix expo-share-intent v6 cold-start race + remove duplicate share-extension
  plugin config
status: Done
assignee: []
created_date: '2026-06-11 07:58'
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

Suite à task-187 (refonte du share-intent vers l'API officielle), le partage Instagram → app **ne fonctionne toujours pas** : Expo Router affiche "Unmatched Route" et le hook `useShareIntentContext` reste `hasShareIntent: false`.

Diagnostic capturé en mode `debug: true` du Provider package :
```
useShareIntent[mount] media-summarizer
useShareIntent[refresh] null               ← url retournée par useLinkingURL est null
useShareIntent[refresh] not a valid refresh url
```

Donc `useLinkingURL()` (interne au package) retourne `null` au mount, malgré l'arrivée bien réelle de l'URL `media-summarizer://dataUrl=<key>?nonce=<uuid>#weburl` (vue dans les logs Metro avant task-187).

## Cause racine (recherche en ligne 2026-06-11)

**Combinaison de 2 bugs connus :**

1. **Cold-start race sur `useLinkingURL`** — bug Expo non-fixé en SDK 55 (cf. issues `expo/expo#23333` et `expo/expo#37401`). Symptômes identiques rapportés sur `expo-share-intent#208` (closed stale).

2. **Conflit potentiel** entre le plugin officiel `expo-share-intent` et notre plugin custom `mobile/plugins/withShareExtension.js` qui duplique :
   - L'App Groups entitlement (`com.apple.security.application-groups: ["group.com.secondbrainlabs.core"]`)
   - L'URL scheme `media-summarizer` dans `CFBundleURLTypes`
   
   Le plugin officiel v6 fait déjà ces 2 modifications. Le custom étant listé APRÈS dans `plugins:[]` peut introduire une duplication ou override partiel.

## Fix (4 étapes)

### Étape 1 — Nettoyer `mobile/plugins/withShareExtension.js`

Vérifier ce que fait actuellement le plugin custom et déterminer si chaque modification est encore nécessaire vu que le plugin officiel `expo-share-intent` v6 gère déjà :
- App Groups entitlement
- URL scheme `CFBundleURLTypes`
- App Groups dans Info.plist du share extension

**Option A** : supprimer entièrement `mobile/plugins/withShareExtension.js` et la référence dans `app.config.ts:68`.

**Option B** : garder uniquement les modifications NON gérées par le plugin officiel (s'il y en a — à auditer ligne par ligne).

### Étape 2 — Passer `scheme` explicitement au Provider

Dans `mobile/app/_layout.tsx`, préciser le scheme pour neutraliser toute ambiguïté de résolution :

```tsx
<ExpoShareIntentProvider options={{ debug: false, resetOnBackground: true, scheme: "media-summarizer" }}>
```

Le `debug: true` actuellement actif doit redevenir `debug: false` une fois la task done.

### Étape 3 — Ajouter `app/+native-intent.tsx`

Pattern Expo Router officiel pour intercepter les deep links AVANT que le router essaie de matcher un pathname. Doc : https://docs.expo.dev/router/advanced/native-intent/

Le fichier doit exporter une fonction `redirectSystemPath({ path, initial })` qui :
- Détecte le pattern `dataUrl=<extensionKey>` (l'extensionKey est `media-summarizerShareKey`)
- Retourne `/share-confirmation` (la route modale finale) au lieu de laisser le router parser `/dataUrl=...` → Unmatched Route

Référence d'implémentation : https://github.com/achorein/expo-share-intent/issues/189

### Étape 4 — Prebuild + EAS rebuild + smoke tests

```bash
cd mobile && npx expo prebuild --clean
eas build --platform ios --profile development
```

Puis ré-install sur device + tester :
1. Reel Instagram → écran share-confirmation avec webUrl
2. Lien Safari → idem
3. Texte WhatsApp → contentType=text
4. Audio WhatsApp → contentType=audio

## Cleanup

Avant de fermer la task, retirer les 3 `console.log("[ShareIntent.Context] ...")` ajoutés dans `mobile/src/contexts/ShareIntentContext.tsx` au commit (en cours) — ils étaient là uniquement pour cette investigation. Repasser `debug: false` dans le Provider du package.

## References

- Diagnostic complet dans la session 2026-06-10/11 (logs Metro capturés en mode debug)
- Rapport `task-research` complet : voir conversation task-187
- task-187 (parent — refonte share-intent vers API officielle, half-fix)
- Issues GitHub :
  - `achorein/expo-share-intent#189` (linking + native-intent pattern)
  - `achorein/expo-share-intent#208` (symptômes identiques, closed stale)
  - `achorein/expo-share-intent#200` + `#205` (plugin duplication bugs)
  - `expo/expo#37401` (useLinkingURL cold-start race)

## Pourquoi non-dispatchable ?

L'étape 4 (eas build + tests sur device physique) ne peut pas être faite par un agent en worktree. Mais les étapes 1-3 sont automatisables. Marquer `dispatchable: true` permet à un agent de faire les modifs code, l'owner ferait juste le rebuild + smoke tests à la fin.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 mobile/plugins/withShareExtension.js est nettoyé (toutes les modifications déjà gérées par le plugin officiel sont retirées) ou supprimé entièrement
- [ ] #2 Le Provider ExpoShareIntentProvider reçoit l'option scheme: 'media-summarizer' explicitement
- [ ] #3 Le fichier mobile/app/+native-intent.tsx existe et redirige les pattern dataUrl=*ShareKey vers /share-confirmation
- [ ] #4 expo prebuild --clean termine sans warning de duplicate plugin/entitlement
- [ ] #5 Après rebuild EAS + ru00e9-install, partager un reel Instagram aboutit sur l'écran share-confirmation avec webUrl renseignée (logs Metro montrent 'useShareIntent[refresh] media-summarizer://dataUrl=...' au lieu de 'null')
- [ ] #6 Aucune régression sur Safari, WhatsApp text, WhatsApp audio shares
- [ ] #7 Les 3 console.log de debug dans ShareIntentContext.tsx sont retirés
- [ ] #8 L'option debug: true du Provider est repassée à false (ou retirée)
<!-- AC:END -->
