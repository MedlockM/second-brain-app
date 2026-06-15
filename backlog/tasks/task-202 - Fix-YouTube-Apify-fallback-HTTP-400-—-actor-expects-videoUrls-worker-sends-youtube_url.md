---
id: task-202
title: >-
  Fix YouTube Apify fallback HTTP 400 — actor expects videoUrls, worker sends
  youtube_url
status: Done
assignee: []
created_date: '2026-06-15 12:42'
labels:
  - bug
  - ingestion
  - youtube
  - apify
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Le worker YouTube (`media_summarizer/workers/youtube_ingestion_worker.py`) échoue sur le path Apify avec `apify_client_error:400` lorsque yt-dlp est IP-blocked par YouTube (cas standard sur AWS Lambda). Constaté en prod le 2026-06-15 sur la vidéo `WNYqS2462k0` (job `43f90a29-0b1d-41c9-bd09-4d0caa758f46`), log CloudWatch :

```
ERROR: [youtube] WNYqS2462k0: Sign in to confirm you're not a bot...
{"event": "transcription.failed", "error_code": "youtube_apify_failed", "detail": "apify_client_error:400"}
```

## Cause racine

Le commit `4958083` (2026-06-12 — `feat(youtube): support preferred transcript language end-to-end`) a changé le payload envoyé à l'actor Apify de :

```json
{"videoUrls": ["<url>"]}
```

vers :

```json
{"include_transcript_text": true, "language": "fr", "youtube_url": "<url>"}
```

Or l'actor configuré dans le secret runtime (`APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID = scrape-creators~best-youtube-transcripts-scraper`) exige toujours `videoUrls` (vérifié via `GET /v2/acts/.../builds/default` : `inputSchema.required = ["videoUrls"]`). Reproduction directe :

```bash
curl -X POST "https://api.apify.com/v2/acts/scrape-creators~best-youtube-transcripts-scraper/run-sync-get-dataset-items?token=$T" \
  -d '{"include_transcript_text": true, "language": "fr", "youtube_url": "..."}'
# → HTTP 400  "Field input.videoUrls is required"
```

Cette régression réintroduit le bug que `task-132` avait corrigé (mais avec un autre actor en tête : le commit `4958083` semble avoir été écrit en supposant l'actor `easyapi/youtube-transcript-scraper` — qui prend bien `youtube_url` + `language` + `include_transcript_text`).

## Pourquoi le test e2e `test_youtube_ingestion` est passé

Le test e2e `tests/e2e/test_phase4_other_sources.py::test_youtube_ingestion` n'a pas été relancé depuis la régression : son dernier passage en prod date du 2026-06-12 16:00 (avant le commit de 18:09). Aucun test unitaire ne couvre le payload envoyé à Apify. Le test e2e suivant a été passé manuellement avant régression — donc invisible jusqu'à la prochaine ingestion réelle.

## Décision attendue

Deux options à trancher par l'owner :

1. **Aligner le worker sur l'actor configuré** (`scrape-creators~best-youtube-transcripts-scraper`) : revenir à `{"videoUrls": [url]}` et supprimer le passage de `language` (l'actor ne l'accepte pas — il renvoie quoi qu'il arrive la langue source). Lire `transcript_only_text` plutôt que `transcript_text` côté réponse. C'est le plus rapide et restaure le comportement antérieur à `4958083`. La préférence de langue côté natif (yt-dlp) reste fonctionnelle.
2. **Changer d'actor** vers un actor qui accepte `language` (ex. `easyapi/youtube-transcript-scraper`) en ajustant `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID` dans le secret runtime + valider input/output schema. Garde la fonctionnalité préférence de langue Apify, mais demande un mini-benchmark coût/qualité.

L'option 1 est sans doute préférable pour un fix immédiat (reverte un comportement par ailleurs validé). L'option 2 peut faire l'objet d'une tâche séparée si on veut vraiment piloter la langue côté Apify.

## Prévention de récurrence

- Ajouter un test unitaire `tests/unit/workers/test_youtube_ingestion_worker.py` (ou équivalent) qui mock `httpx.AsyncClient` et vérifie le payload exact (`videoUrls` keyed) envoyé à Apify, plus le parsing de `transcript_only_text` côté réponse.
- Optionnel : ajouter un sentinel `__e2e_force_ip_block__` côté YouTube (comme TikTok/Instagram dans `task-185`) pour exercer le path Apify dans le test e2e sans dépendre de l'IP-block réel — sinon le path Apify reste invisible quand yt-dlp réussit (rare en Lambda mais possible).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Une ingestion YouTube réelle (URL publique standard) déclenche le fallback Apify et complète le job sans 400 (job DB en `completed`, transcript en S3, événement `transcription.completed` émis)
- [ ] #2 Le payload HTTP envoyé à Apify est compatible avec l'actor configuré dans le secret runtime (`APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID`) — vérifié soit en alignant le code sur `videoUrls`, soit en changeant l'actor
- [ ] #3 Un test unitaire mocke l'appel HTTP à Apify et vérifie le payload outgoing + le parsing du payload réponse, de sorte qu'une régression similaire casse le test
- [ ] #4 Le test e2e `tests/e2e/test_phase4_other_sources.py::test_youtube_ingestion` est ré-exécuté et passe après le fix
- [ ] #5 Pas de régression sur le path natif (yt-dlp subtitles trouvés → upload direct) ni sur le path Deepgram (yt-dlp sans sous-titres → enqueue Deepgram)
<!-- AC:END -->
