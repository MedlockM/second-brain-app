---
id: task-4
title: Brainstorm fuzzy matching for podcast title search (PodcastIndexOrg)
status: Done
assignee:
  - codex
created_date: '2026-01-06 19:45'
updated_date: '2026-01-24 12:02'
labels: []
dependencies: []
priority: low
ordinal: 3000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Explore the best way to implement fuzzy matching for podcast title search in the dashboard using the existing search system. Review PodcastIndexOrg docs, and decide whether fuzzy matching should trigger on Enter or on-type (live results).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Review PodcastIndexOrg documentation for fuzzy search capabilities or relevant parameters.
- [x] #2 Assess how to integrate fuzzy matching into current search flow without breaking existing behavior.
- [x] #3 Recommend trigger strategy: on Enter vs on-type (with latency/UX considerations).
- [x] #4 Call out any API limits, performance concerns, or caching needs.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Plan d’implémentation
1) Lire la doc PodcastIndex.org (lien fourni) et relever les endpoints/paramètres de recherche pertinents (fuzzy/approx, fulltext, clean, limit, etc.) + contraintes (rate limits, auth).
2) Auditer le flux de recherche existant dans le code (UI + service API) : où la requête est construite, comment le déclenchement Enter/click est géré, et pourquoi la recherche est stricte.
3) Choisir l’intégration la plus simple côté API (paramètre officiel si disponible). Si pas de support fuzzy serveur, définir une stratégie de fallback (client-side fuzzy scoring) limitée à l’action Enter/click.
4) Implémenter la recherche fuzzy au déclenchement Enter/click (au minimum), en préservant le comportement existant ailleurs; ajouter debounce/anti‑spam uniquement si recherche on-type est conservée/ajoutée.
5) Ajouter notes sur limites/perf/caching possibles (ex: memoisation par requête, TTL court) et mettre à jour les AC atteints.
6) Vérifier le comportement end‑to‑end (tests rapides ou vérif manuelle) et documenter les décisions dans la task.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Doc PodcastIndex: /search/byterm = recherche la plus courante (title/author/owner, index de mots-clés nettoyés) ; /search/bytitle = recherche très explicite du titre pour résultats stricts. Le spec liste un paramètre `similar` sur ces endpoints → candidat pour activer le fuzzy côté API.
Intégration: garder `search_podcasts` strict par défaut pour les flows internes (playlist/tosum), activer `similar=true` sur l’endpoint UI /podcasts/search pour garantir le fuzzy sur Enter/click.
Trigger: UI actuelle = on-submit (Enter/bouton). Si on-type un jour → ajouter debounce + limiter.
Perf/limites: rate limit local déjà à 60/min sur l’endpoint; pas d’appel supplémentaire avec fuzzy. Si on-type → caching simple par requête/TTL pour réduire la charge.

Note: un vrai fuzzy matching (accents, préfixes, typos, stemming) nécessite un index contrôlé (ingestion + moteur de recherche type OpenSearch/Meili/Typesense + normalisation/edge‑ngrams/re‑ranking). Avec PodcastIndex seul, on reste limité à `similar` et aux capacités serveur.
Mise en place d’un index local impliquerait ingestion périodique (feeds) et gestion du rate limiting PodcastIndex lors des syncs; c’est plus complexe mais reste envisageable si on accepte l’infra et la maintenance.
<!-- SECTION:NOTES:END -->
