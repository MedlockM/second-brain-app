---
id: task-92
title: >-
  Remplacer Typesense Cloud par Algolia (plan Build free) pour la recherche
  full-text
status: Done
assignee: []
created_date: '2026-05-12 22:13'
labels:
  - feature
  - search
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Le benchmark task-53.1 (REDO 2ᵉ passe, 2026-05-12) a révélé que Typesense Cloud coûte **43 €/mois** @100u heavy-podcast (cluster 2 GB, ratio RAM 2,1×), soit 75 % de l'infra fixe. En comparaison, **Algolia plan Build est gratuit** et supporte 100u × 200 docs (80k records, ~720 MB < cap 1 GB) avec typo tolerance best-in-class et zéro ops.

L'owner a décidé de remplacer Typesense Cloud par Algolia Build (free) pour la phase V1 launch.

## Architecture actuelle (à remplacer)

3 fichiers constituent l'intégration Typesense :
1. `media_summarizer/utils/typesense_client.py` — client singleton, schema collection
2. `media_summarizer/core/services/search_indexing.py` — `index_transcript()`, `delete_document()`, `search_transcripts()`
3. `media_summarizer/api/endpoints/search.py` — transforme la réponse Typesense en réponse API

Le worker (`workers/search_indexing_worker.py`) et les triggers (transcription workers) appellent `search_indexing.index_transcript()` et n'ont **pas besoin de modification**.

## Travail à réaliser

1. **Créer `media_summarizer/utils/algolia_client.py`** : init du client Algolia (SDK `algoliasearch-python`), configuration via env vars (`ALGOLIA_APP_ID`, `ALGOLIA_API_KEY`, `ALGOLIA_INDEX_NAME`).

2. **Réécrire `media_summarizer/core/services/search_indexing.py`** avec le SDK Algolia :
   - `index_transcript()` : **chunker le transcript** en morceaux de <10 KB (limit plan Build). Chaque chunk = 1 record Algolia avec `objectID = "{media_item_id}_chunk_{i}"`, + attributs `user_id`, `media_item_id`, `title`, `source_platform`, `created_at`, `chunk_index`.
   - `delete_document()` : supprimer tous les chunks d'un media_item_id (utiliser `deleteBy` avec filtre `media_item_id`).
   - `search_transcripts()` : recherche avec filtre `user_id:"{user_id}"`, puis **dédupliquer les hits** par `media_item_id` (plusieurs chunks du même doc peuvent matcher). Retourner le meilleur snippet par document.

3. **Adapter `media_summarizer/api/endpoints/search.py`** : le format de réponse Algolia diffère (highlights dans `_highlightResult`, score dans `_rankingInfo`). Adapter le mapping vers `SearchResponse`.

4. **Supprimer `media_summarizer/utils/typesense_client.py`** et la dépendance `typesense` du `requirements.txt` / `pyproject.toml`.

5. **Mettre à jour la config** (`core/config.py`) : remplacer les vars Typesense par Algolia.

6. **Mettre à jour les tests** existants pour search_indexing si présents.

## Contraintes techniques

- **Limite record Build : 10 KB** (JSON sérialisé, espaces supprimés). Le chunk doit inclure les attributs metadata (~200 bytes) + le texte. Donc chunk texte max ≈ 9,5 KB.
- **Limite index Build : 1 GB total**. À 100u × 200 docs × 4 chunks × 9 KB ≈ 720 MB. OK mais serré.
- **Limite requests Build : 10K/mois**. Avec debounce 300ms côté client, ~4K requests/mois @100u. OK.
- **Multi-tenancy** : Algolia supporte le filtrage via `filters: "user_id:xxx"` dans les search params. Pas de scoped API keys comme Typesense — le filtrage se fait côté serveur (pas de query direct frontend → Algolia pour l'instant).

## Instructions pour l'agent

**IMPORTANT** : Avant d'implémenter, l'agent DOIT consulter la documentation officielle Algolia à jour pour :
- Le SDK Python (`algoliasearch` v4+) : API d'indexation, recherche, deleteBy
- Les limites exactes du plan Build (record size, index size, requests/mois)
- Le format de réponse search (structure `_highlightResult`, `_rankingInfo`)
- Les bonnes pratiques de chunking de documents longs (Algolia recommande `distinct` + `attributeForDistinct` pour la déduplication)

Documentation de référence :
- https://www.algolia.com/doc/api-client/getting-started/install/python/
- https://www.algolia.com/doc/guides/sending-and-managing-data/prepare-your-data/how-to/reducing-object-size/
- https://www.algolia.com/doc/api-reference/api-methods/search/
- https://support.algolia.com/hc/en-us/articles/4406981897617 (record size limits)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le service search_indexing.py indexe les transcripts dans Algolia avec chunking <10KB par record
- [ ] #2 La recherche retourne des résultats dédupliqués par media_item_id (un seul hit par document même si plusieurs chunks matchent)
- [ ] #3 Le filtrage par user_id est appliqué à chaque requête (tenant isolation)
- [ ] #4 Le worker search_indexing_worker.py fonctionne sans modification (il appelle toujours search_indexing.index_transcript())
- [ ] #5 L'endpoint GET /api/search/transcripts retourne le même format de réponse (SearchResponse) qu'avant
- [ ] #6 La dépendance typesense est supprimée, remplacée par algoliasearch
- [ ] #7 Les tests passent avec la nouvelle implémentation
<!-- AC:END -->
