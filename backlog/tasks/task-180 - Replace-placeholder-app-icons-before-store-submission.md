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
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
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
