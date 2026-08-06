---
id: task-231
title: Benchmark des approches de mise en forme du transcript pour le viewer media
status: To Do
assignee: []
created_date: '2026-08-06 00:39'
labels:
  - benchmark
  - mobile
  - ingestion
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Le viewer de détail média (mobile/app/media/[id].tsx, section TranscriptContent) affiche actuellement le transcript comme un unique bloc de texte brut, sans paragraphes, sans espacement structurant, sans repères visuels (speakers, timestamps). Cela dégrade fortement la lisibilité sur les transcripts longs.

Constat technique actuel :
- Backend : Deepgram est déjà appelé avec `paragraphs=true` et `utterances=true` (media_summarizer/workers/transcription/deepgram_worker.py), mais seule la chaîne plate `alt.transcript` est extraite et stockée en S3 (extract_transcript) — la structure de paragraphes/utterances/speakers renvoyée par l'API est jetée avant persistance. Le modèle ProcessingJob (media_summarizer/core/models/processing_job.py) ne conserve qu'une référence S3 + des métadonnées génériques (pas de structure de segments).
- Frontend : mediaService.getRawContent() récupère ce texte plat via GET /api/media/:id/raw-content, et TranscriptContent (mobile/app/media/[id].tsx) l'affiche tel quel dans un `<Text>` unique, sans aucun post-traitement.
- Note : task-69 (Done) avait un critère d'acceptation "transcripts Deepgram formatés en texte lisible (paragraphes, speaker labels si disponibles)" qui n'a en réalité jamais été implémenté malgré la clôture de la tâche — le code actuel le confirme.

Cette tâche de recherche doit produire une recommandation sur la meilleure architecture pour restituer un transcript agréable à lire, en explorant notamment :
- Reconstruction des paragraphes/utterances/speakers côté backend à partir de la réponse structurée Deepgram (results.paragraphs / results.utterances), et impact sur le format de stockage S3 (texte plat vs JSON structuré) et sur la migration des transcripts déjà existants.
- Alternative : post-traitement côté client (découpage heuristique en paragraphes à partir de la ponctuation/longueur) si la donnée structurée n'est pas disponible ou pas rentable à backporter.
- Faisabilité et coût d'affichage des speaker labels et/ou timestamps dans l'UI mobile (React Native), et ergonomie de lecture attendue (mode "lecture" vs mode "brut" actuel).
- Impact sur les autres sources d'ingestion (YouTube, RSS/podcast, TikTok...) qui n'utilisent pas forcément Deepgram ou n'ont pas la même richesse de structure.
- Impact sur la traduction du transcript (RawContentResponse.translation) : la structuration doit rester compatible avec le pipeline de traduction existant.

Livrable attendu : docs/research/task-XX-.../README.md avec front-matter owner_decision: pending, comparant les options et recommandant une architecture cible (format de stockage, effort de migration, plan d'implémentation UI).
<!-- SECTION:DESCRIPTION:END -->
