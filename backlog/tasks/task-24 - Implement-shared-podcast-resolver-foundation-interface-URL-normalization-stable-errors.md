---
id: task-24
title: >-
  Implement shared podcast resolver foundation (interface, URL normalization,
  stable errors)
status: Done
assignee:
  - '@codex'
created_date: '2026-02-24 11:03'
updated_date: '2026-03-03 20:54'
labels: []
dependencies:
  - task-20
  - task-9
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Create the shared podcast resolver foundation used by all podcast platforms so platform-specific resolvers follow one interface and one error contract.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 All podcast platform resolvers implement a single shared interface.
- [x] #2 Podcast URL normalization rules are centralized and reusable.
- [x] #3 Error outcomes are standardized across resolvers with stable client-safe semantics.
- [x] #4 Foundation usage guidelines are documented for future resolver additions.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1) Introduire un socle partagé des resolvers podcast dans le core ingestion: interface unique `PodcastPlatformResolver`, registre de plateformes, type de résultat standardisé (success/pending/error) avec codes d’erreur stables et messages client-safe.
2) Centraliser la normalisation URL podcast dans ce socle (Spotify/Apple/Deezer/RSS) via une API réutilisable par tous les resolvers plateforme.
3) Adapter `PodcastResolver` pour déléguer à ce socle partagé (normalization + dispatch plateforme) sans changer le flux d’orchestration hexagonal existant.
4) Garder le comportement runtime compatible: si `audio_url` absent, continuer le chemin queue-first PodcastIndex; enrichir `metadata` avec les champs standardisés du résultat resolver.
5) Documenter les guidelines d’usage/extension (ajout d’un resolver plateforme) dans la documentation d’architecture ingestion.
6) Validation technique ciblée: vérification syntaxe/compilation des modules modifiés et revue rapide des imports/exports.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented shared podcast resolver foundation in `media_summarizer/core/media_ingestion/adapters/podcast_resolver_foundation.py` with a single interface (`PodcastPlatformResolver`), centralized URL normalization (`normalize_podcast_source_url`), deterministic platform registry, and stable resolution outcome/error taxonomy (`PodcastResolutionOutcome`, `PodcastResolutionStatus`, `PodcastResolverErrorCode`).

Integrated the foundation into ingestion API resolver path by refactoring `PodcastResolver` in `media_summarizer/core/media_ingestion/adapters/resolvers.py` to always normalize podcast URLs, route through deferred platform registry, and emit standardized metadata envelope (`podcast_resolution_*`, `podcast_source_url`, `podcast_url_identifiers`) while keeping canonical HTTP error contract unchanged.

Finalized worker integration by introducing platform resolvers module `media_summarizer/workers/podcast_platform_resolvers.py` and wiring `media_summarizer/workers/podcastindex_resolution_worker.py` to resolve via shared platform interface: RSS resolver implemented with PodcastIndex lookup + retries; Spotify/Apple/Deezer return stable `platform_not_implemented` outcome codes.

Exported foundation symbols via `media_summarizer/core/media_ingestion/adapters/__init__.py` to keep resolver foundation reusable for upcoming tasks 25/26/27/28 without touching ingestion use-case.

Documented task-24 usage and extension guidelines in `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` with explicit interface/outcome semantics and add-a-platform-resolver procedure.

Validation performed with AST parsing on all touched Python files (`AST_OK`). Runtime smoke import remains limited in this environment because `pydantic` dependency is unavailable.
<!-- SECTION:NOTES:END -->
