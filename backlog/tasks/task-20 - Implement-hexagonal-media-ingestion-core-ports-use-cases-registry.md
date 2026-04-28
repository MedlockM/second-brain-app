---
id: task-20
title: 'Implement hexagonal media ingestion core (ports, use-cases, registry)'
status: Done
assignee:
  - '@codex'
created_date: '2026-02-24 11:03'
updated_date: '2026-02-24 20:25'
labels: []
dependencies:
  - task-19
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Build the core media-ingestion application layer with explicit ports and a resolver registry so media-specific providers can be added without changing core orchestration.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Core ingestion use-cases are isolated from provider-specific logic behind ports.
- [x] #2 A resolver registry routes providers through a single extension point.
- [x] #3 Adding a new resolver does not require changes in core orchestration code.
- [x] #4 Core architecture boundaries and extension rules are documented.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Créer la couche core media ingestion hexagonale
- Ajouter un package dédié `media_summarizer/core/media_ingestion/` avec frontières explicites (`ports`, `domain`, `use_cases`, `registry`, `errors`).
- Garder cette couche indépendante des détails FastAPI/endpoints.

2. Définir les ports (interfaces)
- `UrlClassifierPort`: classification déterministe d’URL vers une famille média.
- `ContentResolverPort`: résolution URL -> payload normalisé d’ingestion.
- `SubmissionOrchestratorPort`: orchestration de création de job/pipeline (adapter temporaire vers orchestration existante).
- Documenter les contrats d’entrée/sortie des ports avec types dataclass/pydantic légers.

3. Définir le domain model d’ingestion
- Introduire les types canoniques minimaux pour ingestion (request, classification, resolved media, ingestion result).
- Réutiliser les enums/states gelés de task-19 quand pertinent pour éviter divergence contractuelle.

4. Implémenter un registry de resolvers
- Ajouter un registry central permettant:
  - enregistrement des resolvers par famille média/platform
  - résolution du resolver actif via clé déterministe
  - extension sans modification du code d’orchestration
- Ajouter erreurs explicites quand aucun resolver n’est enregistré.

5. Implémenter le use-case d’ingestion
- Ajouter un use-case `ingest_url` qui orchestre:
  - canonicalisation/identity
  - classification via port
  - résolution via resolver du registry
  - soumission/orchestration via port
- Conserver ce use-case purement applicatif (pas de dépendance endpoint).

6. Ajouter adapters initiaux de base
- Fournir au moins un classifier rule-based et un resolver minimal branché sur les primitives existantes pour rendre la couche exécutable.
- Ajouter un adapter orchestrator qui délègue à l’orchestration existante (`episode_submission`) en mode transitoire.

7. Documenter les frontières et règles d’extension
- Rédiger une doc dédiée décrivant les boundary rules, comment ajouter un resolver, et quelles couches ne doivent pas se coupler entre elles.
- Lier la doc aux tâches suivantes (`task-10`, `task-21`, `task-24+`).

8. Validation et clôture task-20
- Vérifier la cohérence structurelle (imports, wiring, absence de couplage endpoint).
- Mettre à jour les notes Backlog et cocher les AC quand le noyau, le registry et les règles d’extension sont en place.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Created a dedicated hexagonal core package: `media_summarizer/core/media_ingestion/` with isolated modules (`domain.py`, `ports.py`, `registry.py`, `use_cases.py`, `errors.py`, `wiring.py`).

Implemented explicit ports: `UrlClassifierPort`, `ContentResolverPort`, and `SubmissionOrchestratorPort` to isolate use-case logic from provider and runtime specifics.

Implemented central resolver extension point `ResolverRegistry` with key-based registration and lookup errors, ensuring routing through a single registry path.

Implemented ingestion use-case `IngestUrlUseCase` orchestrating identity derivation -> classification -> registry resolver selection -> submission orchestration, with no FastAPI endpoint coupling.

Added default adapters: `RuleBasedUrlClassifier`, default resolvers (`podcast.default`, `article.default`, `youtube.default`, `social.default`, `audio.default`), and transitional submission adapter `ProcessingJobSubmissionOrchestrator` reusing existing DB/SQS/idempotence primitives behind the orchestrator port.

Added wiring helpers (`build_default_resolver_registry`, `build_default_ingest_url_use_case`) so future endpoint work can consume the core without extra orchestration code.

Documented architecture boundaries and extension rules in `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md`, including allowed dependencies, single extension point, resolver onboarding workflow, and links to next tasks.

Validation performed with AST parse across all new Python modules (`AST_OK`) and targeted structural checks on key classes/functions/doc sections.
<!-- SECTION:NOTES:END -->
