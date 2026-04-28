---
id: task-55
title: Prioriser les transcripts RSS Podcasting 2.0 avant la transcription audio
status: Done
assignee: []
created_date: '2026-03-16 21:23'
updated_date: '2026-04-28 12:00'
labels:
  - podcast
  - rss
  - transcript
  - deepgram
dependencies:
  - task-24
  - task-25
  - task-26
  - task-27
  - task-28
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Pour chaque épisode de podcast traité, le système doit d'abord tenter de récupérer un transcript directement depuis le flux RSS en s'appuyant sur le standard Podcasting 2.0, afin d'éviter une transcription audio inutile quand un transcript structuré est déjà disponible. Si aucun transcript exploitable n'est trouvé par cette voie, le comportement actuel doit rester disponible en repli en récupérant l'URL du fichier audio puis en l'envoyant à Deepgram pour transcription. La solution doit garantir ce comportement quel que soit la plateforme d'origine du podcast, notamment pour des épisodes distribués via Spotify, Apple Podcasts ou Deezer. La mise en oeuvre devra être précédée d'une recherche internet sur le standard Podcasting 2.0 et sur les points de compatibilité nécessaires pour l'intégrer proprement.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Pour tout épisode traité, le système tente d'abord de récupérer un transcript depuis le flux RSS avant toute récupération du fichier audio ou envoi à Deepgram.
- [ ] #2 Si aucun transcript exploitable n'est disponible via le flux RSS, le système retombe sur la méthode déjà en place basée sur la récupération du fichier audio puis sa transcription.
- [ ] #3 Le comportement est assuré quel que soit la plateforme d'origine du podcast, y compris pour des podcasts diffusés via Spotify, Apple Podcasts et Deezer.
- [ ] #4 L'implémentation repose sur une vérification préalable du standard Podcasting 2.0 et des contraintes de compatibilité nécessaires pour une intégration correcte.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Dispatch 2026-04-28: Implémentation complétée par agent-task-55. Créé media_summarizer/utils/rss_transcript.py (fetch/parse podcast:transcript tag, support text/SRT/VTT/JSON, normalisation). Modifié download_worker.py pour tenter RSS transcript avant audio. Propagation feed_url dans tout le pipeline (media_submission, podcast_search, podcasts, media endpoints). Merged dans second-brain-project.
<!-- SECTION:NOTES:END -->
