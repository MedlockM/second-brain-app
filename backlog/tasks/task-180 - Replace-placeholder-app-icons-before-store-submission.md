---
id: task-180
title: Replace placeholder app icons before store submission
status: To Do
assignee: []
created_date: '2026-06-10 13:48'
labels:
  - mobile
  - release
  - phase-5
  - blocker-store-submission
dependencies: []
priority: high
dispatchable: false
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
> ⚠️ **MANUAL — OWNER ONLY. NEVER DISPATCH TO A SUBAGENT.**
> Cette tâche relève de la création de visuels (design + outils graphiques propriétaires) et ne peut pas être exécutée par un agent. Toute tentative de dispatch doit être ignorée.

## Description

Pendant la task-160 (`expo prebuild` manuel), `mobile/assets/icon.png`, `mobile/assets/splash.png` et `mobile/assets/adaptive-icon.png` étaient absents alors que `mobile/app.config.ts` (lignes 9, 13, 34) les référence. Pour débloquer le prebuild, des **placeholders** ont été générés et commités : 3 PNG 1024×1024 warm-white (#fcf9f6) avec un cercle « SB » centré.

Ces placeholders permettent à `prebuild` et `eas build` de fonctionner mais **ne doivent pas atteindre une soumission store**. Apple risque de rejeter (« icon doesn't represent the app ») et Google laissera passer mais c'est moche.

## Scope

Produire les vrais visuels conformes à la spec décidée dans `docs/store-listing/icon-and-graphics.md` (Direction A ou B selon préférence owner) et remplacer les 3 PNG dans `mobile/assets/`.

## Contraintes techniques

- `mobile/assets/icon.png` : **RGB sans alpha**, 1024×1024 (App Store rejette l'alpha).
- `mobile/assets/adaptive-icon.png` : RGBA 1024×1024, foreground centré dans la safe zone (66×66 dp / 264×264 px center). Le background `#fcf9f6` est appliqué par Android via `app.config.ts:35`.
- `mobile/assets/splash.png` : 1024×1024, fond `#fcf9f6` (cohérent avec `app.config.ts:15`).
- Après remplacement : relancer `cd mobile && npx expo prebuild --clean` pour régénérer le natif avec les bonnes images.

## Blocage release

Cette tâche **bloque toute soumission App Store / Play Store**. Tant que les placeholders sont en place, ne pas exécuter de submit production.

## À livrer dans le même push que task-186

Les 3 PNG de `mobile/assets/` sont des **sources de l'empreinte `runtimeVersion`** (raison `expoConfigExternalFile`). Les remplacer déplace l'empreinte des **deux** plateformes, donc déclenche un build natif iOS *et* un build natif Android : `@expo/fingerprint` hashe le config Expo résolu comme un seul bloc, il n'existe pas de hash par plateforme.

task-186 (rebrand) touche exactement le même genre de sources — `appName`, `iosShareExtensionName`, les 11 `mobile/locales/*.json`. Livrées séparément, les deux tâches coûtent **quatre** builds natifs ; dans le même push, **deux**. Sur le palier gratuit à 15 builds/mois, le regroupement est la seule parade.

Mesuré le 2026-09-08 : une seule ligne ajoutée à `androidIntentFilters` (task-380, `4543f75`) a déplacé les deux empreintes — Android `87b855f2` → `96e3267b`, iOS `784f7b9c` → `421e4b93` — et consommé un build iOS pour un changement qu'iOS ne voit pas. Pour attribuer un déplacement d'empreinte : `eas fingerprint:compare --build-id A --build-id B`, depuis `mobile/`. Détails dans `mobile/MOBILE_CI_CD.md`, section « An Android-only config change moves the iOS fingerprint too ».

## References

- `docs/store-listing/icon-and-graphics.md` (spec design)
- `mobile/app.config.ts:9,13,34` (chemins consommés)
- task-160 (contexte du blocker initial)
- task-44 (Done — couvre les screenshots/copy store, pas les icons)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 mobile/assets/icon.png est un PNG RGB 1024×1024 sans alpha conforme à docs/store-listing/icon-and-graphics.md
- [ ] #2 mobile/assets/adaptive-icon.png est un PNG RGBA 1024×1024 dont le foreground respecte la safe zone Android
- [ ] #3 mobile/assets/splash.png est un PNG 1024×1024 cohérent avec backgroundColor #fcf9f6
- [ ] #4 expo prebuild --clean termine sans erreur après remplacement des assets
- [ ] #5 Aucune mention « SB » placeholder ne subsiste dans les visuels finaux
<!-- AC:END -->
