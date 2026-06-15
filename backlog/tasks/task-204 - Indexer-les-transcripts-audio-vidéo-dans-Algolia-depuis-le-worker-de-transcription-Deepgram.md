---
id: task-204
title: >-
  Indexer les transcripts audio/vidéo dans Algolia depuis le worker de
  transcription Deepgram
status: To Do
assignee: []
created_date: '2026-06-15 13:53'
labels:
  - feature
  - search
  - ingestion
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Les transcripts produits par la transcription Deepgram (podcasts, YouTube, audio) ne sont jamais indexés dans Algolia, donc invisibles à la recherche full-text. Conséquence : la barre de recherche renvoie systématiquement zéro résultat pour ces medias, même quand les mots recherchés sont présents dans le transcript.

Cause : un seul producteur pousse aujourd'hui vers SEARCH_INDEXING_QUEUE (la queue consommée par le worker d'indexation Algolia, media_summarizer/workers/search_indexing_worker.py) : c'est media_summarizer/workers/document_parsing/worker.py (chemin upload de documents, livré/corrigé par task-136). Le worker de transcription media_summarizer/workers/transcription/deepgram_worker.py sauvegarde bien le transcript dans S3 ({job_id}.txt) et publie l'événement de complétion, mais n'enqueue jamais de message d'indexation. Le chemin audio/vidéo n'a donc jamais été câblé à la recherche.

Périmètre : à la fin d'une transcription Deepgram réussie, enqueuer un message vers SEARCH_INDEXING_QUEUE à parité avec le chemin document (voir document_parsing/worker.py autour de la ligne 299), avec les mêmes champs attendus par le worker d'indexation : media_item_id, user_id, transcription_s3_key, title, source_platform, created_at. Le source_platform doit refléter la vraie plateforme du media (youtube, spotify, audio, etc.) et non une valeur figée.

Hors périmètre : aucun backfill de l'existant (décision owner). Seuls les medias transcrits après la mise en production de ce fix seront cherchables. Le branchement de la barre de recherche mobile fait l'objet de task-201.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 À la fin d'une transcription Deepgram réussie, un message d'indexation est enqueué vers SEARCH_INDEXING_QUEUE avec les champs media_item_id, user_id, transcription_s3_key, title, source_platform et created_at attendus par le worker d'indexation
- [ ] #2 Le source_platform du message reflète la plateforme réelle du media transcrit (ex: youtube, spotify, audio) et non une valeur codée en dur
- [ ] #3 Après transcription d'un podcast/vidéo, une recherche sur un terme présent dans son transcript le retourne via l'endpoint Algolia
- [ ] #4 L'échec d'enqueue de l'indexation est journalisé sans faire échouer la transcription ni la complétion du media (best-effort, à parité avec le chemin document)
- [ ] #5 Aucun backfill des medias déjà transcrits n'est effectué
<!-- AC:END -->
