---
id: task-270
title: >-
  Implement collection-scoped AI artifact generation per validated benchmark
  (task-269)
status: Done
assignee: []
created_date: '2026-08-17 19:41'
updated_date: '2026-08-17 23:24'
labels:
  - backend
  - ai
  - feature
dependencies:
  - task-269
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Objectif

Rendre possible la génération d'artefacts IA au niveau d'une **collection** — sur l'ensemble des médias qu'elle contient — et non plus seulement sur un média isolé. C'est le backend qui manque à l'onglet « IA » de l'écran collection (task-272).

**Lire d'abord `docs/research/task-269-collection-artifact-aggregation/README.md`**, section `Owner Validation`, champ `Decision`. C'est cette décision qui fixe la stratégie d'agrégation, le modèle de stockage, la forme des routes, le contenu du snapshot, la déduplication et les plafonds. Si le `Decision` renvoie à un fichier `complement-response-*.md` du même dossier, le suivre aussi. Ne pas rejouer le benchmark et ne pas substituer une autre architecture : en cas de contradiction entre cette description et le README, **le README gagne**.

## Contraintes indépendantes de la décision

- Périmètre de types tranché par l'owner : les **5 types existants** (`summary_short`, `summary_detailed`, `notes`, `flashcards`, `quiz`). Aucun nouveau type d'artefact, aucune nouvelle modalité.
- **Historique append-only, aucune invalidation** (décision de l'owner du 2026-08-17, référence `mobile-design-mockups/notebooklm-reference/collection-ai-generated-list.png`). Chaque génération crée une entrée immuable qui porte un snapshot de ce sur quoi elle a porté — au minimum la liste des `media_item_id` retenus, leur nombre et l'horodatage. Plusieurs artefacts du même type coexistent pour une même collection. Une modification de la composition de la collection **ne périme, ne régénère et ne supprime rien**. Ne pas implémenter de péremption, de statut « obsolète », ni de régénération automatique.
- **Le scope média passe au même modèle** (décision de l'owner du 2026-08-17). Aujourd'hui un média n'a qu'un artefact par type, écrasé à la régénération : cela devient un historique horodaté lui aussi. Une seule mécanique append-only sert les deux scopes — pas deux modèles concurrents. Concrètement, la projection `artifact_statuses` de `GET /api/media/{id}`, sur laquelle le mobile poll aujourd'hui, doit être remplacée par ce que le README prescrit ; l'affichage mobile correspondant est traité par task-273.
- La déduplication reste nécessaire mais **à courte portée uniquement** : un double tap et une relivraison SQS (*at-least-once*) ne doivent pas produire deux artefacts. C'est la seule chose que les locks d'idempotence couvrent ici.
- Rappel « rien n'est déployé » : pas de double écriture, pas de champ conservé « au cas où », pas de fenêtre de dépréciation. Si le README impose de restructurer la table `media_artifacts` ou la forme des messages SQS, la restructuration est faite franchement et les chemins devenus morts sont supprimés dans le même run.
- « Collection » côté UI = `folder` côté backend. Ne pas introduire un troisième vocabulaire : rester sur `folder` dans le code Python et l'infra, et ne parler de « collection » que dans les libellés exposés.
- L'API doit rester utilisable par un mobile qui poll : l'avancement d'une génération en vol et l'historique des artefacts produits doivent être lisibles sans multiplier les appels, dans la forme décidée par le README.
- Les erreurs métier doivent être des refus explicites et typés (dans l'esprit des `ArtifactGenerationDisabledError` / `ArtifactTypeNotEnabledError` / `ArtifactTranscriptNotReadyError` existantes), pas des 500 : dépassement de plafond, collection vide, transcripts non prêts.

## Surface concernée (point de départ, à confronter au README)

- `media_summarizer/core/models/media_artifact.py`, `core/models/folder.py`
- `media_summarizer/core/services/artifact_service.py` (fingerprints, locks, résolution du transcript effectif, enqueue), `core/services/folder_service.py`
- `media_summarizer/api/endpoints/artifacts.py`, `api/endpoints/folders.py`, `api/models/media_contracts.py`
- `media_summarizer/workers/artifact_generator/worker.py` et ses `generators/*.py` (prompts et schémas de sortie)
- `media_summarizer/utils/{media_artifacts.py,artifact_idempotence.py,user_media.py}`
- `infrastructure/terraform/modules/platform/{dynamodb_core_tables.tf,s3.tf,sqs.tf,lambda_workers.tf}`

## Note à l'owner — hors AC

- Le déploiement (image Lambda + `terraform apply` sur `-dev`) se fait au push sur `main`, après le passage de l'agent. La vérification E2E « je génère un résumé sur une collection de 5 médias depuis le mobile, puis je retrouve l'artefact daté dans la liste » est manuelle et vous revient.
- Si le README retient une stratégie multi-appels LLM, surveiller le coût sur `-dev` après les premiers essais avant d'ouvrir l'onglet côté mobile. Le modèle append-only n'oppose aucune limite technique aux régénérations répétées.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Les Implementation Notes citent explicitement la décision lue dans `docs/research/task-269-collection-artifact-aggregation/README.md` (stratégie d'agrégation, modèle de stockage, forme des routes, contenu du snapshot, plafonds) et signalent tout point où l'implémentation a dû interpréter le README
- [x] #2 Le chemin complet existe et est câblé de bout en bout pour les 5 types (`summary_short`, `summary_detailed`, `notes`, `flashcards`, `quiz`) : route API → service → lock d'idempotence → enqueue SQS → worker `artifact_generator` → écriture S3 + DynamoDB → lecture du contenu, avec le scope collection dans la forme décidée par le README
- [x] #3 Les routes de génération, de listing et de récupération du contenu d'un artefact de collection sont montées dans l'app FastAPI et déclarées dans le schéma OpenAPI, avec les modèles de requête/réponse typés
- [x] #4 Chaque artefact de collection persiste un snapshot immuable de sa génération — au minimum la liste des `media_item_id` retenus, leur nombre et l'horodatage — et le listing rend **tous** les artefacts d'une collection triés par date de génération décroissante, plusieurs entrées du même type incluses
- [x] #5 Aucun mécanisme d'invalidation n'est implémenté : ajouter ou retirer un média d'une collection ne modifie, ne marque et ne supprime aucun artefact existant, et aucun statut de péremption n'est introduit
- [x] #6 La déduplication couvre le double tap et la relivraison SQS — deux demandes concomitantes pour le même type sur la même collection produisent une seule génération — sans empêcher une régénération ultérieure demandée par l'utilisateur, qui crée bien une nouvelle entrée
- [x] #7 L'avancement d'une génération en vol est lisible par le mobile dans la forme décidée par le README, sans requête par type d'artefact
- [x] #8 Le plafond retenu par le README est appliqué et le dépassement, la collection vide, et les transcripts non prêts renvoient chacun un refus explicite typé avec un code HTTP distinct de 500
- [ ] #9 Les ressources d'infrastructure requises par le README (attributs et index DynamoDB, buckets S3, queue SQS, event source de la Lambda) sont déclarées dans `infrastructure/terraform/modules/platform/` et `terraform validate` passe
- [x] #10 Aucune couche de compatibilité n'est introduite : pas de double écriture, pas de champ ou de route conservé sans lecteur ; tout chemin rendu mort par la restructuration est supprimé dans le même run et listé dans les Implementation Notes

- [x] #11 `ruff` et `mypy` passent sur `media_summarizer/` sans nouvelle erreur
- [x] #12 Une vérification directe contre le `-dev` est consignée dans les Implementation Notes (lecture AWS CLI des tables/buckets/queue ciblés, ou requête sur les médias d'un `folder_id` réel) montrant que les identifiants de ressources utilisés par le code correspondent à ceux qui existent

- [x] #13 Le scope média utilise la même mécanique append-only que le scope collection : une régénération sur un média crée une nouvelle entrée horodatée au lieu d'écraser la précédente, le listing par média rend l'historique trié par date décroissante, et ce qui remplaçait la projection `artifact_statuses` de `GET /api/media/{id}` est implémenté conformément au README
- [x] #14 Aucun code ne suppose plus « un seul artefact par type et par média » : les chemins qui faisaient cette hypothèse (écriture, lecture, contrats API) sont listés dans les Implementation Notes avec ce qui les remplace
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Décision lue dans le README (AC #1)

`docs/research/task-269-collection-artifact-aggregation/README.md`, `owner_decision: ok`, `Decision: statégie s1`. Implémenté tel quel :

- **Agrégation** : S1, passe unique sur le corpus concaténé. Un appel LLM par type, aucun étage de condensation, aucun store intermédiaire, aucun verrou de coordination.
- **Stockage** : une seule table `media_artifacts`, `scope` + `scope_id`, **un** GSI `scope-index` (hash `scope_key = user_id#scope#scope_id`, range `created_at`, projection `INCLUDE`). Les trois GSI existants sont supprimés.
- **Routes** : `POST /api/artifacts`, `GET /api/artifacts?scope=&scope_id=`, `GET /api/artifacts/{id}`, `GET /api/artifacts/{id}/content`. Les deux routes par média disparaissent, sans alias.
- **Snapshot** : `sources` (liste ordonnée `media_item_id`, `title`, `transcript_s3_key`, `language`, `excluded`), `source_count`, `created_at`, `generator_version`.
- **Plafonds** : `MAX_COLLECTION_SOURCES = 25`, `MAX_COLLECTION_CORPUS_TOKENS = 120_000`, constantes de code (pas dans `pricing_config`), refus explicite sans troncature.
- **Dédup** : `artifact_id` déterministe + `ConditionExpression`, fenêtre de 120 s, fenêtre précédente contrôlée aussi.
- **Titre** : émis par le LLM, recopié sur l'enregistrement. `headline` de `summary_short` renommé `title`.
- **Sous-collections** : incluses via `_get_descendant_ids`, sources dédupliquées à plat.
- **Quota** : `ai_generations_per_day` (deux scopes) + `collection_source_units` (collection seule), plus l'alimentation de `cost_eur_estimated` par le coût mesuré.
- **FSRS** : `scope`/`scope_id` à la place de `media_item_id`.

### Points où le README a dû être interprété

1. **`GET /api/media/{id}` renvoyait aussi un tableau `artifacts`.** Le README ne cite explicitement que `artifact_statuses`, mais ce tableau porte la même hypothèse « un artefact courant par type » **et** il était alimenté par le GSI `media-item-index` que le README fait supprimer : le garder était impossible. Supprimé, avec les contrats d'artefact de `api/models/media_contracts.py` devenus sans lecteur.
2. **Ordre des vérifications de §10.3.** Dédup et écriture vivaient dans une seule fonction, ce qui rendait impossible de placer le quota entre les deux sans une lecture DynamoDB de plus. Scindé en `plan_artifact_generation` (résout l'id, rend le verdict de dédup) et `commit_artifact_generation` (écriture conditionnelle + SQS). L'endpoint exprime alors littéralement l'ordre du README : propriété → sources → plafonds → dédup → quota → écriture + compteurs + envoi.
3. **Le curseur de pagination** n'est pas spécifié : c'est le `created_at` de la dernière entrée rendue, soit la range key du GSI.
4. **`pricing_config` n'était semé que si la table est vide.** Ajouter les deux clés aux défauts ne suffisait donc pas : `pricing_config-dev` est peuplée depuis le 2026-06-08 et son `rate_limits` n'a pas `ai_generations_per_day`, donc la limite aurait lu 0 et le garde-fou aurait été inerte, silencieusement. `_load_from_db` superpose désormais les valeurs stockées sur les défauts, feuille par feuille (une valeur stockée gagne toujours, 0 explicite inclus). C'est ce qui rend §11.4 réellement effectif, pour cette clé et pour toute clé ajoutée plus tard.
5. **Le worker revérifie le plafond** après téléchargement (§3.2) avec un `ValueError` `corpus_too_large` plutôt qu'un type dédié : il n'a pas d'autre appelant que lui-même.

## Ce qui a été supprimé, pas conservé (AC #10, AC #14)

Chemins qui supposaient « un seul artefact par type et par média », et leur remplacement :

| Supprimé | Remplacé par |
|---|---|
| `ArtifactStatusSnapshot`, `build_status_snapshots`, champ `artifact_statuses` (backend, contrat, types mobile) | `GET /api/artifacts?scope=&scope_id=` : historique **et** entrées en vol en une réponse |
| tableau `artifacts` de `GET /api/media/{id}` | idem |
| `POST`/`GET /api/media/{media_item_id}/artifacts` | les mêmes routes `/api/artifacts` avec `scope="media"` |
| table `artifact_idempotence` + `ArtifactGenerationLock` + `utils/artifact_idempotence.py` | `artifact_id` déterministe + écriture conditionnelle |
| pointeurs `request#` (`REQUEST_POINTER_PREFIX`, `reserve_request_pointer`, `save_request_pointer`, `get_request_pointer`, `delete_request_pointer`) | plus rien : ils polluaient 55 % de la table et étaient filtrés en Python à chaque liste |
| `build_request_fingerprint`, `build_generation_fingerprint`, `reused_from_artifact_id`, `transcript_s3_key`/`transcript_sha256` singuliers | `artifact_id` + `sources` |
| GSI `media-item-index`, `request-fingerprint-index`, `generation-fingerprint-index` | `scope-index` |
| `list_media_artifacts_by_media_item`, `safe_list_…`, `list_…_by_generation_fingerprint`, `get_latest_…_by_request_fingerprint` | `list_artifacts_by_scope` |
| drapeau `reused` | `deduplicated`, dont le sens est « même tap » |
| règle du frère survivant de `media_purge_service` | chaque entrée possède son objet S3 (clé dérivée de son `artifact_id`, qui contient `user_id`) |
| `get_cards_by_media_item`, `toggle_spaced_rep_for_media`, `POST /api/review/media/{id}/toggle` | `get_cards_by_scope`, `toggle_spaced_rep_for_scope`, `POST /api/review/scopes/{scope}/{scope_id}/toggle` |

Trois chemins connexes ont dû suivre, sinon ils lisaient un index disparu :
- `purge_e2e_accounts.py` interrogeait `media-item-index` par id de job → balaie `scope-index` sur les scopes `media` **et** `folder` de l'utilisateur.
- la jauge d'orphelins de `media_lifecycle.py` filtrait les lignes `request#` et lisait `media_item_id` → lit `scope`/`scope_id`, ne compte que le scope `media`. `scope` étant un mot réservé DynamoDB, la projection passe par un placeholder de nom.
- `account_deletion_service` purge désormais explicitement les dossiers : un effacement qui ne parcourait que les médias laissait **tous** les artefacts de collection derrière lui.

## Vérifications (AC #11, #12)

- `ruff` et `mypy` clean (167 fichiers) ; mobile : `npx tsc --noEmit` exit 0, `eslint` sans erreur (9 warnings préexistants, autres fichiers).
- `terraform validate` Success ; `plan` exit 0, `Plan: 1 to add, 17 to change, 1 to destroy`, diff montrant exactement les trois attributs/GSI d'empreinte retirés, `scope_key` + `created_at` + `scope-index` ajoutés, `artifact_idempotence_v1` détruit. Le `1 to add` est un metric filter RevenueCat de dérive préexistante ; les Lambdas « updated in-place » ne sont que la disparition de `ARTIFACT_IDEMPOTENCE_TABLE` de leur environnement.
- **AC #12, lecture directe du `-dev`** : tous les identifiants nommés par le code existent — `media_artifacts-dev`, `user_folders-dev`, `user_media-dev`, `user_usage_{daily,monthly}-dev`, `review_schedule-dev`, `pricing_config-dev`, les 5 buckets d'artefacts, la queue `artifact-generator-queue-dev`. Et la requête que la résolution de scope émet réellement a été rejouée telle quelle : `query` sur `user_media-dev` / index `folder-index`, `user_id = <owner> AND begins_with(folder_sort_key, "c4ef2e55-…#")` renvoie **11** items — exactement la plus grosse collection mesurée par le README. `describe-table` montre encore les trois anciens GSI et `artifact_idempotence-dev` existe toujours : attendu, les `apply` sont des gestes owner (§12.1).
- **AC #9 non cochée** : les ressources sont déclarées et `validate`/`plan` passent, mais la mise en place réelle demande la séquence d'`apply` ci-dessous, que seul l'owner peut exécuter.

## Notes à l'owner — hors AC

- **Un `apply` direct échouera ; la séquence de §12.1 est obligatoire.** `artifact_idempotence_v1` porte `deletion_protection_enabled = true` sur la table réelle : `plan` accepte la destruction (le bloc, donc son `prevent_destroy`, a disparu de la configuration) mais AWS refusera le `DeleteTable`. Et le passage de trois GSI à un seul est planifié « in-place » alors que DynamoDB n'autorise qu'une opération d'index par `UpdateTable`. Marche à suivre : (1) `apply` avec `deletion_protection_enabled = false` et sans `prevent_destroy` sur les deux tables ; (2) `apply -replace='module.platform.aws_dynamodb_table.media_artifacts_v1'` — les 168 lignes du `-dev` sont jetables ; (3) rétablir les deux protections. Je n'ai pas désactivé la protection de suppression sur l'infra vivante : c'est un garde-fou que vous avez posé.
- **Les 168 lignes actuelles de `media_artifacts-dev` deviennent invisibles sans purge** : pas de `scope_key`, donc le GSI sparse les ignore.
- **Le blocage de coût va enfin pouvoir se déclencher.** `cost_eur_estimated` n'avait aucun écrivain côté artefacts ; le worker y écrit le coût mesuré (`core/services/llm_pricing.py`, prix catalogue OpenAI, `USD_EUR = 0.86` comme task-65). Les seuils `hard_block_eur` (3,5 / 6 / 10 €) ont été dimensionnés sans cette contribution : à surveiller au premier mois réel.
- **L'écran mobile de détail média est adapté au minimum, pas refondu.** Il lit l'historique du scope et garde l'entrée la plus récente par type pour ses tuiles existantes. Le rendu de l'historique horodaté est task-273, l'onglet IA de collection task-272.
- **Vérification E2E après déploiement, qui vous revient** : sur la collection de 11 médias du `-dev`, générer les cinq types, vérifier cinq entrées horodatées, relancer un type et vérifier qu'une **sixième** entrée apparaît au-dessus sans écraser la précédente, puis qu'un double tap rapide n'en crée qu'une (`200` au lieu de `202`).
- **Trois documents restent inchangés volontairement** — `STITCH_MOBILE_PROMPT_PACK.md`, `STITCH_MOBILE_MEGA_PROMPT.md`, `MOBILE_APP_IMPLEMENTATION_PLAN.md` citent les anciennes routes : historique de conception, pas contrats vivants. `docs/CANONICAL_MEDIA_API_CONTRACT.md`, qui fait foi, est à jour.
- **Un `409 sources_not_ready` est attendu sur une collection fraîche** dont des sources ne sont pas traduites. Le corps porte `pending_count` et `pending_titles`, et l'appel a déjà enclenché les traductions : réessayer tel quel est le remède.
<!-- SECTION:NOTES:END -->
