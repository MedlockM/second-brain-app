---
id: task-16
title: >-
  Extract and generalize podcast episode matching utilities from Spotify sync
  services
status: Done
assignee:
  - '@codex'
created_date: '2026-02-23 22:46'
updated_date: '2026-02-23 23:05'
labels: []
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Extract the reusable podcast-title matching logic currently duplicated inside Spotify-specific services into a provider-agnostic shared module, so Spotify code can be removed without losing matching capability needed by new podcast URL ingestion flows.

Context:
- `_normalize` and `_best_match_episode` are implemented in both `media_summarizer/core/services/playlist_sync.py` and `media_summarizer/core/services/tosum_sync.py`.
- These heuristics are useful beyond Spotify (future Apple/Deezer/etc. resolver path to PodcastIndex episodes).

Scope:
- Create a shared module (e.g. `media_summarizer/core/services/podcast_matching.py`) with:
  - text normalization utility
  - episode candidate matching utility with deterministic scoring
- Refactor existing Spotify services to call the shared module (temporary until Spotify removal) to prove compatibility.
- Add unit tests with representative cases (accents, punctuation, substring, token overlap, threshold edge cases).
- Document API/usage so future podcast resolvers reuse this module.

Out of scope:
- Full Spotify feature removal.
- Implementing new media ingestion endpoints.

Key files:
- `media_summarizer/core/services/playlist_sync.py`
- `media_summarizer/core/services/tosum_sync.py`
- new shared module under `media_summarizer/core/services/`

Acceptance Criteria:
- Matching utilities exist in one provider-agnostic module and are imported by callers instead of duplicated inline implementations.
- Behavioral parity is verified with tests (existing and new edge-case fixtures).
- Public callable interface is documented for reuse by future non-Spotify podcast resolvers.
- No Spotify-specific naming leaks into the new module.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Matching utilities exist in one provider-agnostic module and are imported by callers instead of duplicated inline implementations.
- [ ] #2 Behavioral parity is verified with tests (existing and new edge-case fixtures).
- [ ] #3 Public callable interface is documented for reuse by future non-Spotify podcast resolvers.
- [ ] #4 No Spotify-specific naming leaks into the new module.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Plan validé avec l’utilisateur (sans suppression ni refactor des services Spotify existants):
1) Créer un module partagé provider-agnostic bien nommé sous `media_summarizer/core/services/` pour préserver la logique réutilisable de normalisation et de matching d’épisodes.
2) Exposer une API claire et documentée via docstrings/type hints (normalisation, scoring, sélection du meilleur candidat) en conservant le comportement actuel (égalité normalisée -> substring -> overlap Jaccard, seuil 0.60 par défaut).
3) Ajouter des tests unitaires dédiés couvrant accents, ponctuation, substring, overlap de tokens, seuil limite (>= / <), et déterminisme en cas d’égalité de score.
4) Ne pas modifier `playlist_sync.py` ni `tosum_sync.py` dans cette itération; l’objectif est la sauvegarde intelligente du réutilisable pour les prochains resolvers.
5) Exécuter les tests ciblés avec `pytest -c pytest.nocov.ini` et documenter le résultat dans les notes de tâche.

Mise à jour validée avec l’utilisateur: aucun test à ajouter dans cette itération; livraison focalisée uniquement sur l’extraction/sauvegarde du module réutilisable.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Décision utilisateur: ne pas ajouter de tests pour cette itération.

Extraction réalisée dans un module dédié provider-agnostic: `media_summarizer/core/services/podcast_matching.py`.

`playlist_sync.py` et `tosum_sync.py` laissés inchangés conformément à la consigne (pas de suppression, pas de refactor).

Validation technique sans tests: parsing syntaxique du module OK via `ast.parse` (pas de génération bytecode à cause de permissions `__pycache__`).
<!-- SECTION:NOTES:END -->
