---
id: task-201
title: >-
  Brancher la barre de recherche mobile sur l'endpoint Algolia
  /api/search/transcripts (corrige task-95)
status: Done
assignee: []
created_date: '2026-06-15 12:31'
labels:
  - feature
  - mobile
  - search
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
La barre de recherche de l'onglet Search du mobile est non fonctionnelle. `SearchService.searchMedia` (mobile/src/services/searchService.ts) appelle `GET /api/media/search`, un endpoint qui n'existe pas : le routeur media (préfixe `/api/media`) n'expose que `GET /api/media` (recherche substring sur le titre) et `GET /api/media/{media_item_id}`. L'appel est donc capté par la route paramétrée avec `media_item_id="search"` et renvoie 404, affiché en ErrorState côté écran.

La vraie recherche full-text Algolia (titre + transcripts, typo-tolérance, highlights, isolation par utilisateur) est exposée par le backend sous `GET /api/search/transcripts` (livré par task-85, voir media_summarizer/api/endpoints/search.py). task-95 a implémenté l'écran en supposant à tort que `/api/media/search` était l'endpoint Algolia ; cette tâche corrige ce branchement.

Périmètre : uniquement la barre de recherche texte libre, qui doit interroger Algolia via `/api/search/transcripts`. Cela implique d'adapter le service mobile et l'écran au contrat de réponse de cet endpoint (`{query, found, page, per_page, hits[]}`, chaque hit exposant `media_item_id`, `title`, `source_platform`, `created_at`, `text_match_score`, `highlights[]`), différent du contrat `MediaSearchItem` actuellement attendu par l'écran.

Hors périmètre (à traiter séparément) : les chips de filtres metadata (type, source, dossier, tags). L'endpoint Algolia n'expose aujourd'hui que le filtre `source_platform` ; le comportement des chips pendant une recherche full-text doit être clarifié mais ne fait pas partie de cette tâche. Si nécessaire, désactiver/masquer les filtres non supportés plutôt que d'envoyer des paramètres ignorés silencieusement.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Une recherche texte depuis la barre de l'onglet Search renvoie des résultats provenant d'Algolia (match sur titre ET contenu de transcript), avec debounce, sans erreur 404
- [ ] #2 Le service mobile et l'écran consomment le contrat de réponse de GET /api/search/transcripts (champs query/found/page/per_page/hits) sans dépendre de champs absents de ce contrat (ex: original_url, status)
- [ ] #3 Chaque résultat affiche au minimum un titre exploitable et permet d'ouvrir le media correspondant via media_item_id
- [ ] #4 Une requête sans résultat affiche l'état 'aucun résultat' et une erreur backend (ex: 503 service non configuré) affiche un état d'erreur lisible, sans crash
- [ ] #5 Les filtres metadata non supportés par l'endpoint Algolia ne sont pas envoyés silencieusement comme paramètres ignorés (désactivés/masqués ou explicitement documentés comme hors recherche full-text)
<!-- AC:END -->
