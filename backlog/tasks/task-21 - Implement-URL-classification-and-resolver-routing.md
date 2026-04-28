---
id: task-21
title: Implement URL classification and resolver routing
status: Done
assignee:
  - '@codex'
created_date: '2026-02-24 11:03'
updated_date: '2026-02-24 20:37'
labels: []
dependencies:
  - task-20
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement deterministic URL classification and routing so each incoming URL is sent to the correct media resolver path.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 URL classification is deterministic for supported media families.
- [x] #2 Unsupported URLs return stable, user-safe errors.
- [x] #3 Resolver routing is centralized and reusable by ingestion entrypoints.
- [x] #4 Routing behavior is documented with representative examples.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Baseline de la classification/routing existante
- Revoir l’implémentation actuelle (`RuleBasedUrlClassifier`, `ResolverRegistry`, `IngestUrlUseCase`) issue de task-20.
- Identifier les zones non conformes à task-21: URL non supportées non explicites, absence de taxonomie d’erreurs dédiées, règles de routing incomplètes.

2. Durcir la classification déterministe
- Implémenter des règles explicites et stables pour les familles supportées (podcast, article, youtube, social_video, audio) basées sur schéma/host/path.
- Ajouter validations strictes (URL vide/mal formée, schéma non supporté, host interdit/inexploitable) avec erreurs dédiées.

3. Rendre les erreurs non supportées stables et user-safe
- Introduire des erreurs métier spécifiques (`UnsupportedUrlError`, `InvalidUrlError`) dans le core ingestion.
- Normaliser les messages d’erreur pour qu’ils soient stables et exploitables par les clients.

4. Centraliser le routing resolver
- Ajouter un composant de routing central réutilisable qui encapsule classifier + resolver registry.
- Faire consommer ce router par le use-case pour garantir un unique point de décision.

5. Documenter le comportement de routing
- Ajouter une documentation dédiée des règles de classification/routing et des cas représentatifs (supportés et rejetés).
- Lier la doc aux tâches d’intégration endpoint (`task-10`) et resolvers (`task-24+`).

6. Validation et clôture task-21
- Vérifier structure/imports/parse sur les modules touchés.
- Mettre à jour les notes task-21 et cocher les AC si classification déterministe, erreurs stables, routing centralisé, documentation complète.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented centralized routing component `ResolverRouter` (`media_summarizer/core/media_ingestion/router.py`) with `ResolverRoute` so classification + resolver lookup now happens in one reusable decision point.

Updated `IngestUrlUseCase` to depend on `ResolverRouter` instead of directly coupling classifier and resolver registry; URL input validation now emits stable `InvalidUrlError` for empty/malformed inputs.

Extended ingestion error taxonomy with explicit stable user-safe errors: `InvalidUrlError` and `UnsupportedUrlError`, plus shared stable message constants in `errors.py`.

Hardened `RuleBasedUrlClassifier` with deterministic host/path/scheme rules per supported media family: podcast (Spotify/Apple/Deezer/RSS), youtube, social video (Instagram/TikTok), direct audio, and article fallback.

Unsupported URLs now return stable `UnsupportedUrlError` messages for unsupported schemes, forbidden hosts, and unsupported platform-specific URL formats (e.g., invalid YouTube/Spotify paths).

Added reusable wiring helper `build_default_resolver_router(...)`, updated `build_default_ingest_url_use_case(...)` composition, and exported new routing/errors symbols from package `__init__.py`.

Documented routing policy and representative supported/rejected URL examples in `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` (task-21 section).

Validation run: `python3 -m compileall media_summarizer/core/media_ingestion` passed. Runtime smoke import in this environment is limited by missing dependency `pydantic` (outside task-21 scope).
<!-- SECTION:NOTES:END -->
