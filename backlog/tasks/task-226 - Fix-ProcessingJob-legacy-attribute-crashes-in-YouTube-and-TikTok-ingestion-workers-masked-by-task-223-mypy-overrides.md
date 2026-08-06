---
id: task-226
title: >-
  Fix ProcessingJob legacy attribute crashes in YouTube and TikTok ingestion
  workers (masked by task-223 mypy overrides)
status: Done
assignee:
  - Codex
created_date: '2026-08-05 18:16'
updated_date: '2026-08-06 00:57'
labels:
  - bug
  - ingestion
  - type-safety
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Découvert pendant la vérification de task-223. Pour rendre le gate mypy vert, task-223 a ajouté un override per-module désactivant `attr-defined` sur les workers d'ingestion. Cet override masque des bugs de crash runtime réels, et non de simples plaintes de typage.

Vérifié par exécution directe (`ProcessingJob` est un modèle Pydantic sans `extra="allow"`) :

```
j.episode_url = '...'  -> ValueError: "ProcessingJob" object has no field "episode_url"
j.episode_title        -> AttributeError: 'ProcessingJob' object has no attribute 'episode_title'
```

Sites concernés signalés par mypy avant suppression :
- `media_summarizer/workers/youtube_ingestion_worker.py:835` (`job.episode_url =`), `:847` (`job.episode_title`), `:848` (`job.podcast_title`)
- `media_summarizer/workers/tiktok_ingestion_worker.py:1032` (`job.episode_url =`), `:1045` (`job.episode_title`), `:1046` (`job.podcast_title`)
- `media_summarizer/workers/base_worker.py:105` — `"type[ProcessingJob]" has no attribute "get"`
- `media_summarizer/workers/newsletter/worker.py:96` — `Module has no attribute "get_user_by_ingest_address"`

C'est exactement la classe de défaut corrigée par task-134 (TikTok `episode_url`) et que task-141 devait balayer sur tous les workers. L'audit de task-141 a manifestement manqué ces occurrences YouTube et TikTok.

Ces lignes sont sur les chemins de fallback Apify -> Deepgram, donc pas exercées par le happy path : elles ne crashent que lorsque le fallback se déclenche.

## Objectif

Corriger les accès d'attributs pour utiliser les champs réels de `ProcessingJob` (cf. `media_summarizer/core/models/processing_job.py` : `media_url`, `title`, etc. — vérifier le mapping correct pour chaque usage), puis **retirer `attr-defined` de la liste `disable_error_code`** de l'override workers dans `pyproject.toml` afin que mypy protège à nouveau contre cette régression.

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 #1 #1 Chaque accès à un attribut inexistant de ProcessingJob dans les workers YouTube et TikTok est corrigé vers le champ réel du modèle
- [x] #2 #2 #2 base_worker.py:105 et newsletter/worker.py:96 sont corrigés ou justifiés
- [x] #3 #3 #3 attr-defined est retiré du disable_error_code de l'override workers dans pyproject.toml et mypy media_summarizer exite toujours 0
- [x] #4 #4 #4 Un test couvre le chemin de fallback qui assignait episode_url, prouvant l'absence de ValueError Pydantic
- [x] #5 #5 #5 Audit des autres workers pour la meme classe de defaut, complétant ce que task-141 a manqué
<!-- SECTION:DESCRIPTION:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Corriger les mappings legacy des fallbacks YouTube/TikTok vers les champs réels de ProcessingJob (media_url, title, source_platform).
2. Remplacer les deux appels inexistants dans base_worker et newsletter/worker par les accès database_async réellement supportés, sans masquer les erreurs de typage.
3. Ajouter une régression ciblée sur le fallback sans sous-titres afin de prouver que la mutation Pydantic ne lève plus ValueError, puis auditer les workers pour les autres attributs ProcessingJob invalides.
4. Retirer attr-defined de l’override mypy des workers et valider les tests ciblés ainsi que mypy media_summarizer.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implémentation terminée :
- Les fallbacks sans sous-titres YouTube/TikTok utilisent désormais ProcessingJob.media_url, title et source_platform.
- base_worker recharge et persiste les jobs via database_async ; correction associée du mark_failed synchrone qui était awaité.
- Le lookup newsletter appelle l’API database_async existante get_user_by_id selon la convention actuelle de l’adresse d’ingestion.
- L’override mypy workers ne masque plus attr-defined ; l’audit complet couvre les 159 modules backend.
- Régression ajoutée sur le fallback TikTok vers Deepgram, vérifiant la persistance de media_url et l’absence de ValueError Pydantic.

Validation :
- .venv/bin/mypy media_summarizer : succès, 159 fichiers.
- .venv/bin/python -m pytest tests/unit/workers/test_tiktok_ingestion_worker.py : 5 tests passés.
- ruff ciblé et git diff --check : succès.
<!-- SECTION:NOTES:END -->

<!-- AC:END -->

<!-- AC:END -->
