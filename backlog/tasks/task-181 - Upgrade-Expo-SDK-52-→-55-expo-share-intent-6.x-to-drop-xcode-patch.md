---
id: task-181
title: Upgrade Expo SDK 52 → 55 + expo-share-intent 6.x to drop xcode patch
status: Done
assignee: []
created_date: '2026-06-10 14:04'
updated_date: '2026-06-10 14:46'
labels:
  - mobile
  - release
  - phase-5
  - tooling
  - blocker-160
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Description

Pendant l'exécution manuelle de task-160 (`expo prebuild`), le plugin `expo-share-intent@~3.2.0` plante avec :

```
TypeError: Cannot read properties of null (reading 'path')
    at correctForPath (.../node_modules/xcode/lib/pbxProject.js:1682:38)
    at correctForResourcesPath
    at pbxProject.addResourceFile
    at .../expo-share-intent/plugin/build/ios/withIosShareExtensionXcodeTarget.js:41
```

**Cause racine** : la lib `xcode@3.0.1` (transitive, `apache/cordova-node-xcode`) a un bug dans `correctForPath`. Le repo upstream est en quasi-mode maintenance — pas de 3.0.2 prévue.

## Décision

Plutôt que d'ajouter `patch-package` + un patch xcode (route officielle pour `expo-share-intent` 3.x/4.x/5.x), on saute directement à **Expo SDK 55 + `expo-share-intent@^6.1`** où le plugin a été refactor (PR #203, v6.0.0) pour ne plus appeler la fonction cassée. Le patch n'est plus requis du tout — `mobile/patches/` et `patch-package` n'ont jamais besoin d'être ajoutés.

Source recherche : voir conversation task-160 (rapport task-research, 2026-06-10).

## Scope

1. **Bump Expo SDK** : `expo` 52 → 55, suivre le canal officiel `npx expo install expo@^55` puis `npx expo install --fix` pour aligner toutes les deps Expo (`expo-router`, `expo-secure-store`, `expo-apple-authentication`, `expo-linking`, `expo-web-browser`, `expo-share-intent`, etc.).
2. **Bump react-native** à la version recommandée par Expo SDK 55 (probablement 0.81.x). Suivre le upgrade helper Expo : https://docs.expo.dev/workflow/upgrading-expo-sdk-walkthrough/
3. **Bump `expo-share-intent`** à `^6.1` (≥ 6.1.1 pour avoir le drop complet du patch — cf. recherche).
4. **Valider deps tierces** : `react-native-purchases` (RevenueCat), `react-native-google-signin`, `expo-apple-authentication`, share extension iOS (plugin custom `withShareExtension.js` à re-vérifier). Mettre à jour si nécessaire.
5. **Re-test critiques** :
   - `npx expo prebuild --clean` doit passer sans erreur ni patch.
   - Auth Google + Apple (mobile + serveur).
   - Share extension iOS : recevoir un lien WhatsApp / un texte / un fichier audio, redirection vers l'inbox.
   - Ingestion media (TikTok / Instagram / WhatsApp / RSS).
   - RevenueCat (sandbox iOS + Google Play).
   - Deep links / scheme `media-summarizer`.
6. **Mettre à jour le pré-flight check** `scripts/mobile_release_check.sh` ligne `Expo SDK is on expected major version (52)` → 55.

## Contexte risque

À 5 jours du launch (Phase 5). Saut de 3 SDK majeurs = risque de régressions sur les flows critiques V1. Owner a explicitement validé l'option « upgrade maintenant » plutôt que patch-package + dette.

## Blocage downstream

Cette tâche **bloque task-160** (prebuild manuel). Une fois cette tâche Done, task-160 peut être ré-exécutée et `expo prebuild --clean` doit passer sans patch.

## References

- Rapport recherche `task-research` 2026-06-10 (voir conversation task-160)
- Issue référence du plugin : https://github.com/achorein/expo-share-intent/issues/13
- PR du fix v6.0.0 : https://github.com/achorein/expo-share-intent/pull/203
- Expo upgrade walkthrough : https://docs.expo.dev/workflow/upgrading-expo-sdk-walkthrough/
- task-160 (downstream blocker)
- task-180 (placeholder icons — orthogonal, ne bloque pas)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 expo dans mobile/package.json est >= 55.0.0 et toutes les deps expo-* sont alignées via npx expo install --fix
- [x] #2 react-native est sur la version recommandée par Expo SDK 55 (cf. expo upgrade helper)
- [x] #3 expo-share-intent est >= 6.1.0
- [x] #4 Aucun mobile/patches/ ni script postinstall ni dépendance patch-package dans mobile/package.json
- [x] #5 npx expo prebuild --clean termine sans erreur (ni TypeError correctForPath, ni warning bloquant)
- [ ] #6 Tests manuels OK : auth Google + Apple, share extension iOS (texte + audio + URL), ingestion media (TikTok / Instagram / WhatsApp / RSS), RevenueCat sandbox, deep links scheme media-summarizer
- [x] #7 scripts/mobile_release_check.sh est mis à jour pour valider Expo SDK 55
- [x] #8 bash scripts/mobile_release_check.sh passe sans FAIL
<!-- AC:END -->
