---
id: task-373
title: >-
  Renommer « Collection » en « Dossier » dans toute l'application et aligner le
  code mobile sur le vocabulaire `folder` du backend
status: Done
assignee: []
created_date: '2026-09-07 13:40'
updated_date: '2026-09-07 16:16'
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
- `unit_conversion.collection_sources_per_minute` dans `pricing_config_service.py`, lu par `quota_enforcer.minutes_for_collection_sources`, servi par `api/endpoints/pricing.py`, consommé par `mobile/src/services/pricingService.ts` et `lib/planCopy.ts`. ~~Cette clé est **stockée dans la table `pricing_config`** : `_merge_defaults` ne supprime rien, une clé retirée des défauts survit en base indéfiniment. Le renommage en code doit donc s'accompagner de la réécriture de l'item sur `-dev`, sinon la nouvelle clé lit le défaut et l'ancienne traîne pour toujours.~~

  > **Correction post-implémentation (2026-09-07) — l'affirmation barrée ci-dessus est fausse.** `unit_conversion` n'est **pas** stocké dans `pricing_config` : la table `pricing_config-dev` ne contient que deux items, `revenue_model` et `infra_cost_baseline`. `_load_from_db` ne sème les défauts que si la table est **vide** — elle ne l'est pas — donc `unit_conversion` n'a jamais été écrit et est servi entièrement depuis `DEFAULT_PRICING_CONFIG` via `_merge_defaults`. Il n'y avait donc aucune clé `collection_sources_per_minute` périmée à supprimer, et écrire l'item aurait figé `unit_conversion` en base définitivement. C'est la raison pour laquelle l'AC #6 reste non cochée : sa prémisse ne correspond pas à l'état réel de l'environnement. Ne pas rejouer ce raisonnement dans une future tâche touchant au pricing.

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
- [x] #1 `grep -ri collection mobile/src mobile/app --include="*.ts" --include="*.tsx"` ne renvoie plus aucune ligne : ni identifiant, ni clé i18n, ni valeur traduite, ni commentaire, ni `testID`.
- [x] #2 Plus aucun fichier ni répertoire dont le nom contient « collection » sous `mobile/` (hors `node_modules`) : les six fichiers et le répertoire `app/media/collections/` listés dans la description portent leur nom en `folder`/`Folder`, et `mobile/app/_layout.tsx` déclare les routes `media/folder`, `media/folders/index` et `media/folders/[id]`.
- [x] #3 Chacun des 11 catalogues de `mobile/src/i18n/` emploie le terme de sa langue pour « dossier » d'après le tableau de la description — `fr.ts` dit « dossier », `en.ts` « folder » — et aucun ne conserve un dérivé de « collection ».
- [x] #4 `mobile/src/services/organizationService.ts` n'interpose plus de traduction de vocabulaire : `toCollection()` n'existe plus, le type exposé est `Folder`, et les champs de `/api/folders` sont repris sous leur nom d'API (`parent_folder_id`, `is_default`, `default_folder_id`, `deleted_folders`).
- [x] #5 Les deux valeurs de contrat disent `folder` des deux côtés : `kind` vaut `media | folder` dans `api/endpoints/engagements.py` comme dans `EngagementKind`, et la clé de conversion s'appelle `folder_sources_per_minute` dans `pricing_config_service.py`, `quota_enforcer.py`, `api/endpoints/pricing.py` et `mobile/src/services/pricingService.ts`.
- [ ] #6 La table `pricing_config` de `-dev` porte `unit_conversion.folder_sources_per_minute` à la valeur 5 et ne porte plus `collection_sources_per_minute` ; la sortie de l'appel AWS CLI qui le vérifie est recopiée dans les notes d'implémentation.
- [x] #7 Les deux détails d'erreur anglais du backend disent « Folder not found » : `core/services/engagement_service.py` et `api/endpoints/artifacts.py`.
- [x] #8 `npm run lint` et `npm run typecheck` sortent 0 depuis `mobile/`, et `ruff check` comme `mypy` sont propres sur `media_summarizer/`.
- [x] #9 Les docs ne décrivent plus un dossier comme une collection : la parenthèse « a folder is what the UI calls a collection » a disparu de `docs/CANONICAL_MEDIA_API_CONTRACT.md`, et `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md`, `docs/V1_LAUNCH_PLAN.md` ainsi que la copie produit de `docs/store-listing/app-store-connect.md` emploient « folder ».
- [x] #10 Les emplois qui ne désignent pas un dossier sont inchangés par rapport à `main` : `docs/compliance/`, `docs/store-listing/QA-CHECKLIST.md`, `tests/e2e/test_phase4_other_sources.py`, `scripts/testflight_feedback.py` et `docs/testflight-feedback-log.md`.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Fichiers renommés (`git mv`, l'historique suit)

| avant | après |
| --- | --- |
| `mobile/src/components/CollectionPickerView.tsx` | `FolderPickerView.tsx` |
| `mobile/src/components/CollectionSaveSheet.tsx` | `FolderSaveSheet.tsx` |
| `mobile/src/hooks/useCollectionActions.ts` | `useFolderActions.ts` |
| `mobile/src/lib/collectionSearch.ts` | `folderSearch.ts` |
| `mobile/src/lib/collectionTree.ts` | `folderTree.ts` |
| `mobile/app/media/collection.tsx` | `mobile/app/media/folder.tsx` |
| `mobile/app/media/collections/{index,[id]}.tsx` | `mobile/app/media/folders/{index,[id]}.tsx` |

`mobile/app/_layout.tsx` déclare désormais `media/folder`, `media/folders/index`,
`media/folders/[id]`.

### La couche de traduction a disparu, pas seulement son nom

`toCollection()` n'existait pas pour renommer trois champs : il produisait un type
*différent* de la réponse d'API (`parent_id`, `path`, `children`, `is_default`
optionnel). Le type `Folder` de `types/organization.ts` est maintenant la forme du
fil telle quelle, avec `media_count` / `created_at` / `updated_at` / `is_default`
requis — ce que `FolderResponse` côté backend émet toujours. `FolderResponse`,
`FolderDeleteResponse` et le mapper sont supprimés de `organizationService.ts` ;
les quatre méthodes renvoient directement la forme du fil. `folderTree.ts` lit
`node.parent_folder_id` et rien d'autre (le `?? node.parent_id` de repli n'a plus
d'objet).

### Ce qu'un renommage aveugle avait rendu tautologique, réécrit à la main

Sept endroits disaient « la collection, c'est-à-dire le dossier » et devenaient
absurdes une fois les deux mots confondus :

- `mobile/app/artifacts/[artifactId].tsx` — le ternaire `scope === "folder" ? "folder" : "media"` devient `reportEngagement(response.scope, …)` : `ArtifactScope` et `EngagementKind` sont désormais les deux mêmes mots.
- `media_summarizer/api/endpoints/artifacts.py` — même chose côté backend : `kind=scope.value` remplace le ternaire sur `KIND_MEDIA` / `KIND_FOLDER`.
- `core/models/media_artifact.py` — le docstring d'`ArtifactScope` (« `FOLDER` is what the UI calls a collection ») se réduit à ce que le type dit.
- `core/services/audio_quota_gate.py` (×2) et `core/services/durable_media_service.py` — « any folder, any collection » énumérait deux fois la même chose ; devient « in any folder at all ».
- `core/services/artifact_service.py` — « a media item is a collection of one source » employait « collection » au sens générique anglais ; devient « has exactly one source ».
- `api/endpoints/engagements.py` et `api/endpoints/artifacts.py` — les descriptions de champ « Media item id, or collection (folder) id » perdent leur parenthèse.
- `docs/CANONICAL_MEDIA_API_CONTRACT.md` — « a collection covers the folder and all its descendants » devient « a folder-scoped artifact covers … ».

### i18n : trois passes, pas un `sed`

Un `sed` global aurait produit « Aucune folder ». Donc : (1) renommage des seules
clés sur les 11 catalogues (55 clés, 62 en `ar.ts` qui porte les catégories de
pluriel supplémentaires) ; (2) passe complète clés + valeurs sur `en.ts`, source
des clés via `TranslationKey = keyof typeof en` ; (3) traduction des valeurs
langue par langue.

Le genre change dans deux langues et impose des accords, pas un échange de mot :
**fr** collection (f) → dossier (m) — « cette collection sera supprimée » → « ce
dossier sera supprimé », « Sa sous-collection … qu'elle contient » → « Son
sous-dossier … qu'il contient » ; **de** Sammlung (f) → Ordner (m) — « diese
Sammlung » → « diesen Ordner », « Name der Sammlung » → « Name des Ordners »,
« Ihre Untersammlung » → « Sein Unterordner » ; **ar** مجموعة (f) → مجلد (m) —
« هذه المجموعة » → « هذا المجلد », « ستُحذف » → « سيُحذف », duel
« مجموعتان فرعيتان » → « مجلدان فرعيان ». Les autres gardent le genre (es/it/pt
féminin, nl commun, ja/zh/hi sans accord) et se contentent de l'échange.

Collision tranchée : `collections.empty` et `collections.emptyFolder` deviennent
`folders.empty` (« No folders yet ») et `folders.emptySubtitle` (« Empty »).
`folderPicker.unsorted` garde son libellé « Unsorted » / « Non trié » — c'est le
nom du dossier par défaut, pas un synonyme.

### AC #6 non atteint : il n'y a pas d'item `unit_conversion` sur `-dev`

La description partait du principe que la clé est stockée en base. Elle ne l'est
pas. La table `pricing_config-dev` contient exactement deux items :

```
$ aws dynamodb get-item --region eu-west-3 --table-name pricing_config-dev \
    --key '{"config_key":{"S":"unit_conversion"}}' --output json
(aucune sortie : pas d'item)

$ aws dynamodb scan --region eu-west-3 --table-name pricing_config-dev \
    --projection-expression "config_key" --output json
{
    "Items": [
        { "config_key": { "S": "revenue_model" } },
        { "config_key": { "S": "infra_cost_baseline" } }
    ],
    "Count": 2,
    "ScannedCount": 2,
    "ConsumedCapacity": null
}
```

`_load_from_db` ne sème les défauts que si la table est **vide** : elle ne l'est
pas, donc `unit_conversion` n'a jamais été écrit et est servi entièrement depuis
`DEFAULT_PRICING_CONFIG` via `_merge_defaults`. Conséquences :

1. Il n'y a **aucun** `collection_sources_per_minute` périmé à supprimer — la
   moitié « ne porte plus » de l'AC est déjà vraie, sans écriture.
2. La moitié « porte `folder_sources_per_minute` = 5 » est satisfaite par le
   défaut renommé, et **écrire** l'item serait nuisible : cela figerait
   `unit_conversion` en base pour toujours, exactement le verrou contre lequel le
   docstring de `_merge_defaults` prévient (« a top-level key removed from the
   defaults stays in the table until it is deleted there »). Aucune autre section
   de `DEFAULT_PRICING_CONFIG` n'est stockée sur `-dev`, la fixer seule créerait
   l'asymétrie.

L'AC reste donc décoché : sa prémisse est fausse, et le faire passer à la lettre
dégraderait l'environnement. Rien à faire côté owner.

### Hors périmètre des AC, fait quand même

- `sub-folder` → `subfolder` dans les commentaires et messages de log du backend (`folder_service.py`, `media_search_service.py`, `user_media.py`, `api/endpoints/folders.py`, `api/endpoints/media.py`) : le refus utilisateur d'`artifact_service.py` dit désormais « smaller subfolder instead », la même graphie que le tableau de la description.
- `MAX_COLLECTION_SOURCES` / `MAX_COLLECTION_CORPUS_TOKENS` → `MAX_FOLDER_*`, y compris la référence dans `infrastructure/observability/runbooks/pipeline-alerts.md`.
- `stamps_purged_collections` et la clé de métrique `engagement_stamps_purged_collections` de `workers/cleanup/media_lifecycle.py` → `…_folders`. Vérifié : aucun metric filter ni alarme Terraform ne lit cette clé, c'est un champ de log event.
- Commentaires de `infrastructure/terraform/modules/platform/dynamodb_core_tables.tf` (aucune ressource touchée).

### Volontairement laissés en l'état

Au-delà de la liste de l'AC #10 : `docs/research/**` et `backlog/tasks/**`
(artefacts datés, on ne réécrit pas le passé), `mobile-design-mockups/**` (les
noms de fichiers PNG de référence NotebookLM en font partie),
`mobile/MOBILE_CI_CD.md` (collecte d'UDID, permission ASC `GET_COLLECTION`),
`docs/store-listing/app-store-connect.md:379` (« App Privacy (Data Collection) »,
titre de section d'Apple), `docs/store-listing/RELEASE-HANDOFF.md` et
`google-play-store.md` (data collection), `.claude/agents/feedback-triage.md`
(exemple de slug dans une configuration d'agent). Le code des tags est renommé
comme le reste mais rien n'en est supprimé — task-372 en a la charge.

### Vérifications

- `cd mobile && npm run lint` → exit 0 (1 warning préexistant, `purchaseService.ts:98`, fichier non touché).
- `cd mobile && npm run typecheck` → exit 0.
- `ruff check media_summarizer/ scripts/purge_e2e_accounts.py` → All checks passed.
- `mypy media_summarizer/` → Success, 179 fichiers.
- `grep -ri collection mobile/src mobile/app --include="*.ts" --include="*.tsx"` → aucune ligne ; `find mobile -iname "*collection*"` (hors `node_modules`) → aucun résultat.
- `grep -rn -i collection media_summarizer/ --include="*.py"` → aucune ligne.
- `git status --porcelain` sur les fichiers de l'AC #10 → vide.
<!-- SECTION:NOTES:END -->
