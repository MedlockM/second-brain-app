---
id: task-372
title: >-
  Supprimer entièrement la fonctionnalité de tags : bouton du modal de partage,
  écran de gestion, API et table DynamoDB
status: To Do
assignee: []
created_date: '2026-09-07 13:36'
labels:
  - mobile
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Décision

Les tags disparaissent du produit. Le point de départ est le modal de confirmation de partage (`mobile/app/share-confirmation.tsx`), où une ligne « Tags » avec l'icône `pricetag-outline` ouvre un écran de sélection. **Les collections/dossiers restent** : seuls les tags partent.

## Pourquoi la suppression va jusqu'au bout de la chaîne

Ce modal est le **seul** point d'entrée des tags dans tout le produit :

- `router.push("/media/tags?mode=share")` à `mobile/app/share-confirmation.tsx:187` est le seul appel vers l'écran de tags dans tout `mobile/`.
- `mobile/app/media/tags.tsx` est le seul consommateur de `getUserTags`, `createTag` et `updateMediaTags`. Son second mode (`mediaItemId` + `currentTags`, ligne 55-63) est **déjà mort** : plus rien ne pousse cet écran sans `mode=share`.
- Aucun écran mobile n'affiche ni ne filtre par tag. Le paramètre `tags` de la recherche média et `SearchFilters.tags` (`media_search_service.py:55,197-199`) ne sont appelés par personne.

Retirer le bouton laisserait donc une verticale entière de code mort : 4 routes `/api/tags`, un `PATCH /api/media/{id}/tags`, un service, un modèle, cinq fonctions DynamoDB et une table. Conformément à `AGENTS.md` « Nothing is deployed yet », **tout part dans la même passe** — pas de couche de compatibilité, pas de conservation « au cas où ».

## Inventaire du périmètre

### `mobile/`
- **Supprimer** `app/media/tags.tsx` (543 lignes) et sa déclaration `<Stack.Screen name="media/tags">` dans `app/_layout.tsx:193`.
- `app/share-confirmation.tsx` : `handleOpenTags` (l.186), la ligne « Tags » et son `tagsLabel` (~l.739-803), et les props `selectedTags`/`onOpenTags` propagées dans les **huit** variantes de source (l.246-415).
- `src/contexts/ShareIntentContext.tsx` : `ShareSelectedTag`, `selectedTags`, `setSelectedTags`, leur reset, et `tag_ids`/`tagIds` dans les **quatre** payloads de soumission (l.595, 650, 698, 797).
- `src/services/organizationService.ts` : `TagListResponse`, `toTag`, `getUserTags`, `createTag`, `updateMediaTags`. Les méthodes collections restent.
- `src/types/organization.ts` : l'interface `Tag` (`Collection` reste). `src/types/media.ts:232,295` : `tag_ids`.
- i18n (11 catalogues) : les 9 clés `tags.*`, plus `share.tags` et `share.chooseTags`.

### Copy produit devenue fausse
Trois clés promettent les tags et doivent être reformulées dans les 11 langues, pas seulement supprimées : `plan.highlight.organise` (« Organisez en collections **et en tags** »), `plan.includes.organise.file` (« Classez n'importe quoi en collections **et en tags** ») et `deleteAccount.erased.library` (« Votre bibliothèque, vos dossiers **et vos tags** »). Les fiches store (`docs/store-listing/`) ne mentionnent pas les tags : rien à faire côté consoles.

### `media_summarizer/`
- **Supprimer** `api/endpoints/tags.py`, `core/services/tag_service.py`, `core/models/tag.py`.
- `api/main.py` : import l.33 et `include_router(tags.router, prefix="/api/tags", ...)` l.152.
- `api/endpoints/media.py` : la route `PATCH /{media_id}/tags` (l.2199), la branche de validation des tags dans `_resolve_organization` (~l.398-442), l'import `MAX_TAGS_PER_MEDIA`, le paramètre `tags` de la recherche et son parsing `tag_list` (~l.1086-1092).
- `core/constants.py:25,28` : `MAX_TAGS_PER_MEDIA`, `DEFAULT_TAG_COLOR`.
- `utils/database_async.py` : `USER_TAGS_TABLE` (l.47) et les cinq fonctions `create_tag`, `get_tag_by_id`, `get_tags_by_user_id`, `update_tag`, `delete_tag` (l.1132-1250).
- `tag_ids` sur toute la chaîne d'ingestion : `api/models/media_contracts.py`, `core/media_ingestion/domain.py:78,105`, `adapters/orchestrators.py:322,367`, `core/services/durable_media_service.py:119,164`, `core/models/user_media.py:133,191,247-248`.
- `core/services/media_search_service.py` : `SearchFilters.tags`, le filtre l.197-199, et `"tag_ids"` l.353 dans le payload de liste. **Attention** : ce dict est validé contre le modèle de réponse de l'endpoint — retirer la clé impose de retirer le champ du modèle en même temps.
- `core/services/account_deletion_service.py:97` : l'entrée `("USER_TAGS_TABLE", "id")` de la liste de purge.

### `infrastructure/terraform/`
- `modules/platform/dynamodb_core_tables.tf:387-425` : `aws_dynamodb_table.user_tags_v1` et l'output `user_tags_table_name` (que personne ne consomme).
- `modules/platform/runtime_env.tf:24` : `USER_TAGS_TABLE`.
- `modules/platform/backup_library.tf:74-76` : l'entrée `"user-tags"` du plan de sauvegarde.

### Docs
- `docs/CANONICAL_MEDIA_API_CONTRACT.md` : `tag_ids` dans les payloads d'ingestion (l.99, 103-105, 674, 694) et la règle de validation l.707-710.
- `docs/DATA_RETENTION.md:16,92` : `user_tags` dans les stores couverts.
- **Ne pas toucher** aux READMEs de `docs/research/` : ce sont des archives datées, pas de la documentation vivante.

## Piège de grep

`tags=[...]` est un kwargs FastAPI présent sur **tous** les `include_router` de `api/main.py` (l.142-160) et n'a rien à voir avec les tags produit. Idem pour `highlightPreTag`/`highlightPostTag` (Algolia), le corpus « tagged [S1] » des générateurs d'artefacts, et les nombreux `stage`/`staged` du pipeline. Ne rien supprimer sur un grep nu de « tag ».

Bonne nouvelle côté recherche : `tag_ids` n'est **pas** indexé dans Algolia (`search_indexing.py` ne le liste ni dans `attributesToRetrieve` ni dans une facette), donc aucun réglage d'index à modifier.

## Note pour l'owner (pas un AC)

La table `user_tags-dev` ne disparaît qu'au `terraform apply` qui suivra le merge — la suppression du bloc Terraform ne détruit rien par elle-même. Le README de recherche de task-221 relevait 1 item dans `user_tags` sur dev, sans PITR : rien à sauvegarder avant destruction.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 mobile/app/media/tags.tsx n'existe plus et la déclaration <Stack.Screen name="media/tags"> a disparu de mobile/app/_layout.tsx
- [x] #2 mobile/app/share-confirmation.tsx n'affiche plus de ligne « Tags » : ni bouton, ni icône pricetag-outline, ni props selectedTags/onOpenTags dans aucune des huit variantes de source
- [x] #3 ShareIntentContext n'expose plus ShareSelectedTag, selectedTags ni setSelectedTags, et aucun des quatre payloads de soumission ne porte tag_ids ou tagIds
- [x] #4 OrganizationService ne conserve que ses méthodes collections : getUserTags, createTag, updateMediaTags, TagListResponse, toTag et le type Tag sont supprimés
- [x] #5 Aucune clé tags.*, share.tags ni share.chooseTags ne subsiste dans les 11 catalogues i18n
- [x] #6 plan.highlight.organise, plan.includes.organise.file et deleteAccount.erased.library sont reformulées dans les 11 langues et ne promettent plus les tags
- [x] #7 Les routes /api/tags (POST/GET/PUT/DELETE) et PATCH /api/media/{id}/tags n'existent plus ; endpoints/tags.py, core/services/tag_service.py et core/models/tag.py sont supprimés et le routeur n'est plus monté dans api/main.py
- [x] #8 tag_ids a disparu de media_contracts.py, domain.py, orchestrators.py, durable_media_service.py et models/user_media.py, ainsi que du payload de liste et du modèle de réponse qui le déclare
- [x] #9 Le paramètre de requête tags de la recherche média, son parsing tag_list et SearchFilters.tags sont supprimés
- [x] #10 USER_TAGS_TABLE, les cinq fonctions tag de utils/database_async.py et l'entrée de purge de account_deletion_service.py sont supprimés ; MAX_TAGS_PER_MEDIA et DEFAULT_TAG_COLOR ne sont plus dans core/constants.py
- [x] #11 aws_dynamodb_table.user_tags_v1, l'output user_tags_table_name, la variable USER_TAGS_TABLE de runtime_env.tf et l'entrée user-tags de backup_library.tf sont supprimés
- [x] #12 docs/CANONICAL_MEDIA_API_CONTRACT.md et docs/DATA_RETENTION.md ne décrivent plus les tags ; aucun fichier de docs/research/ n'est modifié
- [x] #13 grep -rn "tag_ids\|USER_TAGS_TABLE\|MAX_TAGS_PER_MEDIA\|DEFAULT_TAG_COLOR" sur media_summarizer/ infrastructure/terraform/ mobile/src mobile/app ne renvoie aucun résultat
- [x] #14 Les kwargs FastAPI tags=[...] des include_router de api/main.py sont intacts, à l'exception de la ligne du routeur tags supprimée
- [x] #15 ruff check, mypy et terraform validate passent ; le typecheck et le lint de mobile/ passent
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Deleted files
- `mobile/app/media/tags.tsx` (543 lines, the tag picker screen).
- `media_summarizer/api/endpoints/tags.py` (the 4 `/api/tags` routes).
- `media_summarizer/core/services/tag_service.py`.
- `media_summarizer/core/models/tag.py`.

## Mobile
- `app/_layout.tsx`: the `<Stack.Screen name="media/tags">` modal declaration is gone.
- `app/share-confirmation.tsx`: `handleOpenTags`, the "Tags" row with its `pricetag-outline` icon and `tagsLabel`, the `ShareContent` `selectedTags`/`onOpenTags` props and the 16 prop lines that threaded them through the eight source variants. `OrganizationControls` now renders the folder row only, and `organizationSection` lost its dead `gap`.
- `src/contexts/ShareIntentContext.tsx`: `ShareSelectedTag`, `selectedTags`, `setSelectedTags`, the four resets, the four `useCallback` dependency entries and the `tag_ids`/`tagIds` fields of the four submission payloads.
- `src/services/organizationService.ts`: `TagListResponse`, `toTag`, `getUserTags`, `createTag`, `updateMediaTags`. Collections methods untouched.
- `src/types/organization.ts`: the `Tag` interface. `src/types/media.ts`: both `tag_ids` fields.
- `src/services/uploadService.ts` and `src/services/sharedContentService.ts`: the `tagIds` options and the `tag_ids` payload entries.
- i18n, all 11 catalogues: the 9 `tags.*` keys plus `share.tags` and `share.chooseTags` removed in lockstep (`TranslationKey` is `keyof typeof en`, so a partial removal breaks `tsc`). `ar.ts` also lost its 4 extra Arabic plural variants of those keys.
- Copy that promised tags is reworded, not deleted, in all 11 languages: `plan.highlight.organise`, `plan.includes.organise.file`, `deleteAccount.erased.library`.

## Backend
- `api/main.py`: the `tags` import and its `include_router` line. Every other `tags=[...]` FastAPI kwarg is untouched (AC #14).
- `api/endpoints/media.py`: `PATCH /{media_id}/tags` with its request/response models, the tag branch of `_resolve_media_organization` (now returns a single `Optional[str]`), the `MAX_TAGS_PER_MEDIA` import, the `tag_ids` fields of the four ingestion request models, `MediaSearchItem.tag_ids`, and the search `tags` query param with its `tag_list` parsing.
- `core/constants.py`: `MAX_TAGS_PER_MEDIA`, `DEFAULT_TAG_COLOR`.
- `utils/database_async.py`: `USER_TAGS_TABLE` and the five tag functions (`create_tag`, `get_tag_by_id`, `get_tags_by_user_id`, `update_tag`, `delete_tag`).
- `core/services/account_deletion_service.py`: the `("USER_TAGS_TABLE", "id")` purge entry.
- `tag_ids` removed along the whole ingestion chain: `api/models/media_contracts.py`, `core/media_ingestion/domain.py`, `adapters/orchestrators.py`, `core/services/durable_media_service.py`, `core/models/user_media.py` (field, `to_dynamodb_item`, `from_dynamodb_item`), `utils/user_media.py` (`update_organization`).
- `core/services/media_search_service.py`: `SearchFilters.tags`, the tag filter block and the `"tag_ids"` key of the list payload — removed together with the response-model field that validated it.
- `scripts/purge_e2e_accounts.py` and `tests/e2e/conftest.py`: the `user_tags` child table and its env default.
- `USER_MEDIA_SCHEMA_VERSION` is unchanged: Pydantic v2 defaults to `extra='ignore'`, so dev rows that still carry `tag_ids` read back fine and the attribute simply stops being written.

## Terraform
- `dynamodb_core_tables.tf`: `aws_dynamodb_table.user_tags_v1` and the `user_tags_table_name` output (41 lines).
- `runtime_env.tf`: the `USER_TAGS_TABLE` entry. `backup_library.tf`: the `"user-tags"` entry of `local.library_backup_tables`.

## Docs
- `docs/CANONICAL_MEDIA_API_CONTRACT.md`: `tag_ids` out of the ingest example, the optional-fields paragraph, both contract table rows, and the shared-semantics bullets (now `folder_id` / `400 Folder not found` only).
- `docs/DATA_RETENTION.md`: `user_tags` out of the covered stores and of the deletion sentence.
- `README.md`, `tests/e2e/README.md`: wording. `.env.example`: `USER_TAGS_TABLE=user_tags-dev` removed.
- No file under `docs/research/` was modified; `docs/dispatch-runs/` was left alone too (dated archives).

## Checks
- `ruff check media_summarizer/ scripts/ tests/`: all checks passed.
- `mypy media_summarizer/`: no issues in 176 source files.
- `terraform validate` on `infrastructure/terraform/envs/dev`: configuration is valid.
- `cd mobile && npm run typecheck`: clean. `npm run lint`: 0 errors, only the pre-existing `purchaseService.ts:98` `no-explicit-any` warning in a file this task does not touch.
- AC #13 grep gate returns nothing on `media_summarizer/ infrastructure/terraform/ mobile/src mobile/app`.
- No automated tests were added, per the repository rule.
- Scope note: no `Collection` renaming was attempted — task-373 owns that on the same files.
<!-- SECTION:NOTES:END -->
