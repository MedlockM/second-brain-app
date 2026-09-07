---
id: task-373
title: >-
  Renommer « Collection » en « Dossier » dans toute l'application et aligner le
  code mobile sur le vocabulaire `folder` du backend
status: To Do
assignee: []
created_date: '2026-09-07 13:40'
labels:
  - mobile
  - backend
  - ui
  - tech-debt
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Le constat

Une même chose porte trois noms selon l'endroit où on la regarde :

- **l'écran dit « Collection »** — 55 clés dans `mobile/src/i18n/en.ts` (la source des clés, `TranslationKey = keyof typeof en`) et leurs valeurs traduites dans les 11 catalogues ;
- **le code mobile dit `Collection`** — 41 fichiers de `mobile/src` et `mobile/app` : le type `Collection` (`types/organization.ts`), `CollectionPickerView.tsx`, `CollectionSaveSheet.tsx`, `useCollectionActions.ts`, `lib/collectionTree.ts`, `lib/collectionSearch.ts`, et les routes `/media/collection` et `/media/collections/[id]` ;
- **le backend dit `folder`** depuis toujours — `/api/folders`, `folder_id`, `scope="folder"`, `core/services/folder_service.py`, `core/models/folder.py`, `stamp_folder_engagement`.

Le raccord entre les deux vocabulaires est une fonction de traduction, `toCollection()` dans `mobile/src/services/organizationService.ts`, qui renomme champ par champ ce que l'API renvoie (`parent_folder_id` → `parent_id`, `default_folder_id` → `default_collection_id`, `deleted_folders` → `deleted_collections`). `docs/CANONICAL_MEDIA_API_CONTRACT.md` finit même par expliciter l'écart en toutes lettres : « a folder is what the UI calls a collection ».

## Ce qu'on veut

Un seul mot. **« Dossier » à l'écran** et son équivalent dans chacune des 11 langues ; **`folder` dans le code** — le mobile s'aligne sur le backend, pas l'inverse, parce que le backend porte déjà ce nom jusque dans DynamoDB. La couche de traduction disparaît avec l'écart qu'elle comblait.

Ce n'est pas une transition : rien n'est déployé, il n'y a pas de base installée. Pas d'alias de route, pas de clé i18n conservée en doublon, pas de champ accepté sous ses deux noms.

## Les deux valeurs de contrat qui traversent le réseau

Le backend n'est pas totalement propre non plus. Deux valeurs sortent encore le mot « collection » côté API et se renomment **des deux côtés dans le même passage**, sinon le mobile ne parle plus au backend :

- `kind: Literal["media", "collection"]` dans `api/endpoints/engagements.py` (constante `KIND_COLLECTION`), reflété par `EngagementKind` dans `mobile/src/types/engagements.ts` et par les gardes `item.kind === "collection"` de `HomeTile.tsx`. La couche DynamoDB dit déjà `stamp_folder_engagement` et l'engagement est écrit comme un attribut sur l'enregistrement du dossier — confirmer que la valeur `kind` n'est pas persistée avant de la renommer.
- `unit_conversion.collection_sources_per_minute` dans `pricing_config_service.py`, lu par `quota_enforcer.minutes_for_collection_sources`, servi par `api/endpoints/pricing.py`, consommé par `mobile/src/services/pricingService.ts` et `lib/planCopy.ts`. Cette clé est **stockée dans la table `pricing_config`** : `_merge_defaults` ne supprime rien, une clé retirée des défauts survit en base indéfiniment. Le renommage en code doit donc s'accompagner de la réécriture de l'item sur `-dev`, sinon la nouvelle clé lit le défaut et l'ancienne traîne pour toujours.

## Ce qu'un `sed` global casserait

Cinq emplois de « collection » ne désignent pas un dossier et ne bougent pas :

- **« data collection »** dans `docs/compliance/` (apple-app-privacy, google-play-data-safety, privacy-policy) et `docs/store-listing/QA-CHECKLIST.md` — c'est le vocabulaire RGPD / App Privacy ;
- la fixture LibriVox **« Short Nonfiction Collection »** de `tests/e2e/test_phase4_other_sources.py` — un titre d'œuvre ;
- la variable locale `collection` de `scripts/testflight_feedback.py` — une collection App Store Connect ;
- `docs/testflight-feedback-log.md` — journal historique daté de retours et de décisions, on ne réécrit pas le passé ;
- « Non trié » / « Unsorted » (`collectionPicker.unsorted`) est le **nom du dossier par défaut**, pas un synonyme de collection : la clé se renomme, le libellé non.

## Le mot par langue

| locale | singulier | pluriel | sous-dossier |
| --- | --- | --- | --- |
| en | folder | folders | subfolder |
| fr | dossier | dossiers | sous-dossier |
| es | carpeta | carpetas | subcarpeta |
| de | Ordner | Ordner | Unterordner |
| it | cartella | cartelle | sottocartella |
| pt | pasta | pastas | subpasta |
| nl | map | mappen | submap |
| ja | フォルダ | フォルダ | サブフォルダ |
| zh | 文件夹 | 文件夹 | 子文件夹 |
| ar | مجلد | مجلدات | مجلد فرعي |
| hi | फ़ोल्डर | फ़ोल्डर | सबफ़ोल्डर |

`pseudo.ts` n'a aucune clé littérale (c'est une transformation appliquée par-dessus un catalogue réel) : rien à y toucher.

Deux clés entrent en collision au renommage — `collections.empty` (« Aucune collection ») et `collections.emptyFolder` (« Vide », le libellé d'un dossier vide dans l'arbre) deviendraient toutes deux des variantes de `folders.empty`. Trancher le nommage sur place, la seule contrainte est que les deux libellés restent distincts.

## Notes à l'owner

- **Passe visuelle après merge** : le mot change de longueur dans plusieurs langues (« Ordner » plus court que « Collection », « مجلدات » en RTL). Lancer l'app en mode pseudo-locale une fois pour repérer les libellés tronqués du sélecteur de dossier et de l'en-tête de la page dossier.
- **Fiche store** : le fichier `docs/store-listing/app-store-connect.md` est la copie versionnée ; le champ description sur App Store Connect lui-même reste à mettre à jour à la main, la tâche ne peut pas le faire.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `grep -ri collection mobile/src mobile/app --include="*.ts" --include="*.tsx"` ne renvoie plus aucune ligne : ni identifiant, ni clé i18n, ni valeur traduite, ni commentaire, ni `testID`.
- [ ] #2 Plus aucun fichier ni répertoire dont le nom contient « collection » sous `mobile/` (hors `node_modules`) : les six fichiers et le répertoire `app/media/collections/` listés dans la description portent leur nom en `folder`/`Folder`, et `mobile/app/_layout.tsx` déclare les routes `media/folder`, `media/folders/index` et `media/folders/[id]`.
- [ ] #3 Chacun des 11 catalogues de `mobile/src/i18n/` emploie le terme de sa langue pour « dossier » d'après le tableau de la description — `fr.ts` dit « dossier », `en.ts` « folder » — et aucun ne conserve un dérivé de « collection ».
- [ ] #4 `mobile/src/services/organizationService.ts` n'interpose plus de traduction de vocabulaire : `toCollection()` n'existe plus, le type exposé est `Folder`, et les champs de `/api/folders` sont repris sous leur nom d'API (`parent_folder_id`, `is_default`, `default_folder_id`, `deleted_folders`).
- [ ] #5 Les deux valeurs de contrat disent `folder` des deux côtés : `kind` vaut `media | folder` dans `api/endpoints/engagements.py` comme dans `EngagementKind`, et la clé de conversion s'appelle `folder_sources_per_minute` dans `pricing_config_service.py`, `quota_enforcer.py`, `api/endpoints/pricing.py` et `mobile/src/services/pricingService.ts`.
- [ ] #6 La table `pricing_config` de `-dev` porte `unit_conversion.folder_sources_per_minute` à la valeur 5 et ne porte plus `collection_sources_per_minute` ; la sortie de l'appel AWS CLI qui le vérifie est recopiée dans les notes d'implémentation.
- [ ] #7 Les deux détails d'erreur anglais du backend disent « Folder not found » : `core/services/engagement_service.py` et `api/endpoints/artifacts.py`.
- [ ] #8 `npm run lint` et `npm run typecheck` sortent 0 depuis `mobile/`, et `ruff check` comme `mypy` sont propres sur `media_summarizer/`.
- [ ] #9 Les docs ne décrivent plus un dossier comme une collection : la parenthèse « a folder is what the UI calls a collection » a disparu de `docs/CANONICAL_MEDIA_API_CONTRACT.md`, et `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md`, `docs/V1_LAUNCH_PLAN.md` ainsi que la copie produit de `docs/store-listing/app-store-connect.md` emploient « folder ».
- [ ] #10 Les emplois qui ne désignent pas un dossier sont inchangés par rapport à `main` : `docs/compliance/`, `docs/store-listing/QA-CHECKLIST.md`, `tests/e2e/test_phase4_other_sources.py`, `scripts/testflight_feedback.py` et `docs/testflight-feedback-log.md`.
<!-- AC:END -->
