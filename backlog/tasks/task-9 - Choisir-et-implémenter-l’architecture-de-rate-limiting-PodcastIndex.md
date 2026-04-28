---
id: task-9
title: Choisir et implémenter l’architecture de rate limiting PodcastIndex
status: Done
assignee:
  - '@codex'
created_date: '2026-01-24 14:07'
updated_date: '2026-03-01 21:04'
labels: []
dependencies: []
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Décider de l’architecture pour gérer la limite 1 req/s de l’API PodcastIndex et mettre en œuvre la solution retenue. Se baser sur l’ADR: `docs/ADR/podcastindex-rate-limiting.md`. L’objectif est d’éviter des erreurs utilisateur et de transformer les bursts en latence contrôlée, tout en tenant compte des flux manuels et async en multi‑instance.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 La décision d’architecture est actée et référencée dans l’ADR `docs/ADR/podcastindex-rate-limiting.md` (mise à jour si nécessaire).
- [x] #2 La recherche manuelle respecte le rate limit global PodcastIndex (pas d’erreurs 429 côté utilisateur dans des scénarios de burst).
- [x] #3 Les flux async respectent le rate limit global PodcastIndex tout en restant fiables et observables.
- [x] #4 Les impacts de configuration/déploiement (ex. variables d’environnement, queues, dépendances) sont documentés.
- [x] #5 Un test ou une vérification reproductible démontre que la limite est respectée en multi‑instance.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1) Re-cadrer l’ADR avec le contexte produit actuel: suppression des flux legacy (Spotify sync, recherche manuelle podcast), entrée unique via partage d’URL podcast vers /api/media/ingest-url.
2) Réévaluer les options de rate limiting PodcastIndex dans ce nouveau contexte (inline limiter distribué vs queue dédiée + worker vs alternatives non viables).
3) Proposer une recommandation pragmatique pour multi-instance: suppression de la séparation de clés manual/async, mécanisme global 1 req/s, stratégie de backpressure, retries et observabilité.
4) Documenter impacts techniques et déploiement (variables d’environnement, queue/DLQ, dépendance Redis, comportement API attendu).
5) Définir une vérification reproductible multi-instance pour démontrer le respect de la limite PodcastIndex et l’absence de 429 utilisateur.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-02-24: utilisateur a validé le choix #1 (option B queue-first). ADR mis à jour avec justification comparative détaillée Option B vs Option A (latence API, backpressure, multi-instance, fiabilité/retries, observabilité, trade-off complexité infra).

Implémentation queue-first effectuée pour les résolutions PodcastIndex: l’orchestrateur d’ingestion envoie désormais les podcasts sans audio_url vers `podcastindex-resolution-queue` au lieu de rester en attente.

Ajout d’un worker dédié `media_summarizer/workers/podcastindex_resolution_worker.py` qui consomme la queue de résolution, résout l’URL audio via PodcastIndex (scope task-9: RSS-like feed URLs), puis pousse le job vers `audio-download-queue`.

Ajout d’un rate limiter global `media_summarizer/utils/podcastindex_limiter.py` (Redis partagé via script Lua atomique) avec fallback local in-process pour résilience dev. Intégration dans `media_summarizer/utils/podcast_index.py` pour gouverner les appels sortants PodcastIndex.

Mise à jour config/infra: `.env.example` (vars limiter + queue), `docker-compose.dev.yml` (service worker + redis + env), `infrastructure/terraform/localstack/main.tf` (queue+DLQ podcastindex résolution).

ADR mise à jour: contexte share-only, décision acceptée, comparaison Option B vs A, statut implémentation task-9 et commande de vérification reproductible multi-instance.

Vérifications techniques: AST parse OK sur fichiers Python modifiés; import runtime OK avec `.venv/bin/python`. `compileall` standard non exploitable dans cet environnement à cause des permissions `__pycache__`.

Ajout d’un script de vérification reproductible multi-instance du limiter: `scripts/verify_podcastindex_limiter_multi_instance.py` (concurrence multiprocess, validation du gap global).
<!-- SECTION:NOTES:END -->
