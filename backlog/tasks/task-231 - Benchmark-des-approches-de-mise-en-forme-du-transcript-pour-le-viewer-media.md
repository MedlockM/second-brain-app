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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
**Mode: initial** (no pre-existing `docs/research/task-231-*/` directory, therefore no `README.owner-rejected-*.md` to integrate and no open complement request).

Deliverable produced: `docs/research/task-231-transcript-formatting/README.md` (685 lines, front-matter `owner_decision: pending`).

Contents:
- 15 sections: evidence tables with file:line citations, the Deepgram response shape confirmed against the live API docs, a storage sizing model, the 8-producer cross-source impact map, a 7-option scoring matrix, an explicit rejection section, translation compatibility analysis, migration analysis, a target design, and a React Native UI plan.
- Every bullet of the task description is addressed explicitly: backend reconstruction from `results.paragraphs` / `results.utterances` and its S3 storage impact (section 3), the client-side heuristic alternative (sections 1.3 and 6.1), speaker labels and timestamps feasibility/cost in React Native (section 7), impact on non-Deepgram sources — YouTube, TikTok, RSS/podcast, X, articles (section 4), and translation-pipeline compatibility (section 8).
- Three quantitative measurements were run against the actual repo code (not estimates): the current `_format_plain_text` heuristic produces **1 paragraph of ~54 000 characters** on unpunctuated caption input (today's YouTube/TikTok shape); the full raw Deepgram payload would cost **x42.6** storage versus plain text; paragraph-delimited plain text costs **+0.3 %**.

**Recommendation (Option B)**: keep the canonical S3 object as plain UTF-8 text, stop discarding Deepgram's free `paragraphs.transcript` (already blank-line delimited), introduce one shared idempotent normalizer called both at write time by all 8 producers and at read time in `raw_content_service._format_content()` (idempotence is what removes any need for an S3 migration), and render one selectable `<Text>` per paragraph in `TranscriptContent`. Speaker-label rendering is implemented but diarization stays off by default (+$0.0020/min, +41.7 % on the Nova-3 promo rate — an owner pricing call). Timestamps are deliberately excluded from V1 since the app has no player.

**Explicitly rejected**: raw Deepgram JSON as the canonical object, compact JSON as the canonical object, a JSON sidecar in V1, client-only heuristic re-paragraphing, an LLM re-paragraphing pass, read-time-only normalization, an S3 backfill migration, sentence-level timings, diarization by default, and a reading/raw mode toggle.

Six open questions are listed for the owner in section 14 (diarization, timestamps, paragraph length, design mockup, dead-code cleanup scope, `segments_count` semantics).

No source code was modified — research only. **The recommendation awaits owner validation**: the task stays `To Do` and the README front-matter stays `owner_decision: pending` until the owner records a decision.
<!-- SECTION:NOTES:END -->
