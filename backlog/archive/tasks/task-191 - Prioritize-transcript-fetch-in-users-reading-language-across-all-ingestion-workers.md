---
id: task-191
title: >-
  Prioritize transcript fetch in user's reading language across all ingestion
  workers
status: To Do
assignee: []
created_date: '2026-06-11 10:01'
labels:
  - feature
  - ingestion
dependencies:
  - task-190
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Modifier les workers d'ingestion pour qu'ils tentent d'abord de récupérer un transcript déjà disponible dans la langue de lecture de l'user (cf. task-190) avant de tomber sur le transcript par défaut puis sur la transcription Deepgram.

Workers concernés (chaque worker doit gérer la priorisation par langue dans son fallback chain) :
- **YouTube** (`media_summarizer/workers/youtube_ingestion_worker.py`) — yt-dlp expose déjà `subtitleslangs: ["all"]`. Il faut filtrer/prioriser sur la langue user puis fallback sur la langue native de la vidéo, puis Apify, puis Deepgram (cf. task-177).
- **TikTok** (`media_summarizer/workers/tiktok_ingestion_worker.py`) — pareil sur les sous-titres natifs et automatiques.
- **Instagram** (`media_summarizer/infrastructure/resolvers/instagram_apify_resolver.py`) — généralement pas de transcript multilingue, mais documenter le comportement.
- **Podcasting 2.0** (`media_summarizer/workers/podcastindex_resolution_worker.py`) — Podcasting 2.0 supporte plusieurs `<podcast:transcript>` dont chaque tag peut avoir un attribut `language`. Récupérer celui matchant la langue user en priorité.
- **Document parsing** (LlamaParse + Unstructured) — généralement pas concerné, le doc est dans la langue qu'il est. Documenter qu'aucun changement n'est nécessaire ici.

Comportement attendu :
1. Worker reçoit la `reading_language` de l'user via le job context.
2. Worker tente de récupérer un transcript déjà dans cette langue.
3. Si trouvé : retour immédiat avec `language = user_reading_language`, `language_match = true`.
4. Si non trouvé : fallback sur la chaîne existante (transcript natif → Apify → Deepgram), retour avec `language = <langue_récupérée>`, `language_match = false`.
5. Le flag `language_match = false` déclenchera ensuite la traduction LLM dans task-192 avant que les artefacts (summary, flashcards, quiz) soient générés.

Cette tâche ne s'occupe PAS de la traduction elle-même — uniquement de la priorisation à la récupération. La traduction fallback est implémentée dans task-192.

Mettre à jour `docs/INGESTION_WORKERS_PROVIDERS.md` (cf. task-179) pour refléter la nouvelle priorisation par langue dans la fallback chain de chaque worker.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 YouTube worker tente d'abord la langue user, puis fallback sur l'existant
- [ ] #2 TikTok worker tente d'abord la langue user, puis fallback sur l'existant
- [ ] #3 Podcasting 2.0 worker sélectionne le `<podcast:transcript>` dans la langue user si disponible
- [ ] #4 Instagram worker : comportement documenté (probablement no-op)
- [ ] #5 Output transcript inclut un flag `language_match` (bool) consommé par task-192
- [ ] #6 Tests unitaires couvrant les cas : langue user trouvée / langue user absente / aucun transcript natif
- [ ] #7 `docs/INGESTION_WORKERS_PROVIDERS.md` mis à jour avec la nouvelle priorisation par langue
<!-- AC:END -->
