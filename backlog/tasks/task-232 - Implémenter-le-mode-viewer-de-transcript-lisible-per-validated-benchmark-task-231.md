---
id: task-232
title: >-
  Implémenter le mode viewer de transcript lisible per validated benchmark
  (task-231)
status: To Do
assignee: []
created_date: '2026-08-06 00:39'
labels:
  - mobile
  - ingestion
dependencies:
  - task-231
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implémenter l'amélioration du rendu du transcript dans le viewer de détail média mobile, selon l'architecture validée par le benchmark task-231.

Lire impérativement `docs/research/task-231-.../README.md` pour connaître la décision finale de l'owner (format de stockage retenu, présence ou non de paragraphes/speakers/timestamps, stratégie de migration des transcripts existants) avant de commencer l'implémentation. Ne pas se baser sur une recommandation initiale qui pourrait avoir été amendée par l'owner — seule la section "Decision" du README fait foi.

Périmètre attendu (à affiner selon la décision du README) :
- Adapter le pipeline d'extraction/stockage du transcript si le README l'exige (media_summarizer/workers/transcription/deepgram_worker.py, media_summarizer/core/services/raw_content_service.py).
- Adapter l'affichage dans mobile/app/media/[id].tsx (TranscriptContent) pour restituer une lecture structurée (paragraphes, espacement, éventuellement speakers/timestamps selon la décision).
- Vérifier la compatibilité avec le pipeline de traduction existant (RawContentResponse.translation).
- Vérifier que les transcripts déjà ingérés restent lisibles (stratégie de migration ou fallback si le README en définit une).
<!-- SECTION:DESCRIPTION:END -->
