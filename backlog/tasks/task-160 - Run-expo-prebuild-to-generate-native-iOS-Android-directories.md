---
id: task-160
title: Run expo prebuild to generate native iOS/Android directories
status: To Do
assignee: []
created_date: '2026-06-10 05:36'
updated_date: '2026-06-10 14:04'
labels:
  - phase-5
  - mobile
  - release
dependencies:
  - task-159
  - task-181
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
> ⚠️ **MANUAL — OWNER ONLY. NEVER DISPATCH TO A SUBAGENT.**
> Cette tâche doit être exécutée à la main par l'owner. Même si à un moment elle est marquée `dispatchable: true` par erreur, **aucun agent ne doit la prendre**. Raison : la commande `expo prebuild` peut être interactive en cas de conflit (overwrite fichiers natifs), et le résultat (`mobile/ios/`, `mobile/android/`) est gitignored — un agent travaillant en worktree perdrait l'output au cleanup. Il n'y a rien à automatiser ici.

## Context

Phase 5 du V1_LAUNCH_PLAN, étape 1 : `cd mobile && npx expo prebuild` génère `mobile/ios/` et `mobile/android/` à partir de `app.config.ts`, `eas.json` et des plugins (`withShareExtension`, `expo-share-intent`, `expo-apple-authentication`). Sans ce prebuild, les `eas build` ultérieurs n'ont pas de natif sur lequel travailler.

## Convention CNG (Continuous Native Generation)

`mobile/ios/` et `mobile/android/` restent **gitignored** (cf. `mobile/.gitignore`). Le prebuild est relancé par EAS à chaque build cloud — pas besoin de commit le natif. Toute customisation native passe par un config plugin (cf. `mobile/plugins/withShareExtension.js`).

## Scope manuel

1. Lance d'abord `bash scripts/mobile_release_check.sh` (créé par task-159) pour valider la config en amont.
2. `cd mobile && npx expo prebuild --clean` — flag `--clean` pour repartir à zéro si une exécution antérieure existe.
3. Vérifie `git status` après prebuild : aucun fichier dans `mobile/ios/` ou `mobile/android/` ne doit apparaître (gitignore correct).
4. Note dans le ticket :
   - Warnings éventuels (plugins, peer deps)
   - Versions natives résolues (Xcode build version, Android SDK)
   - Le `bundleIdentifier` iOS et `package` Android effectivement écrits dans le natif

## References

- `docs/V1_LAUNCH_PLAN.md` Phase 5 §1
- `mobile/app.config.ts` (source de vérité bundle ID + plugins)
- `mobile/plugins/withShareExtension.js` (plugin custom App Groups + URL scheme)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 expo prebuild --clean termine sans erreur
- [ ] #2 git status reste propre après prebuild (mobile/ios/ et mobile/android/ gitignored)
- [ ] #3 mobile/ios/ et mobile/android/ existent et contiennent le natif généré
- [ ] #4 Bundle ID com.secondbrainlabs.core présent dans le natif iOS (project.pbxproj) et Android (AndroidManifest.xml ou build.gradle)
<!-- AC:END -->
