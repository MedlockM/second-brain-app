---
id: task-216
title: >-
  Drive YouTube Apify transcript language from user's reading_language
  preference
status: Done
assignee: []
created_date: '2026-06-17 13:31'
updated_date: '2026-08-05 18:40'
labels:
  - feature
  - ingestion
  - youtube
  - apify
  - i18n
dependencies:
  - task-190
  - task-202
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Aujourd'hui, la langue dans laquelle on tente de récupérer un transcript YouTube via l'actor Apify **n'est pas pilotée par la préférence de lecture de l'user** (`User.reading_language`, ajoutée par task-190 et utilisée par les workers d'artefacts via task-192). Elle est :

- soit fournie ad-hoc par le client mobile dans le champ `transcript_language` de `POST /api/media/ingest-url` (`media_summarizer/api/endpoints/media.py` → `IngestUrlRequest.transcript_language`),
- soit absente, auquel cas le worker tombe sur le default `DEFAULT_YOUTUBE_TRANSCRIPT_LANGUAGE` (cf. `_requested_transcript_language` dans `media_summarizer/workers/youtube_ingestion_worker.py`, fallback codé en dur sur `fr`).

Pire : depuis la correction de régression `task-202`, le payload envoyé à l'actor Apify configuré (`scrape-creators~best-youtube-transcripts-scraper`) ne contient plus que `{"videoUrls": [url]}` — la `language` est ignorée côté Apify (cet actor n'expose pas ce paramètre dans son input schema). On a donc une variable `transcript_language` qui est passée au worker mais qui n'a aucun effet sur le path Apify ; seule la sélection des sous-titres natifs yt-dlp s'en sert (`_language_preference_key` / `preferred_language=transcript_language`).

## Objectif

Variabiliser la langue cible utilisée pour récupérer le transcript YouTube (yt-dlp ET Apify) en la liant à la préférence de lecture de l'user, définie pendant l'onboarding ou modifiée plus tard dans Settings (cf. task-190). Concrètement :

1. **Source de vérité = `User.reading_language`**. Quand un user soumet une URL YouTube, l'API doit, en l'absence de `transcript_language` explicite dans le payload, utiliser `current_user.reading_language` comme valeur par défaut. La `transcript_language` du payload reste un override possible mais n'est plus la valeur principale.

2. **Pipeline de bout en bout** : la `reading_language` doit voyager API → orchestrateur → message SQS → worker YouTube. Aujourd'hui :
   - `media_summarizer/api/endpoints/media.py` (`IngestUrlRequest`) propage `transcript_language` ; il faut soit le défaulter à `current_user.reading_language`, soit ajouter un champ dédié dans `DomainIngestUrlRequest`.
   - `media_summarizer/core/media_ingestion/adapters/orchestrators.py` (branche `MediaFamily.YOUTUBE`) sérialise `transcript_language` dans `message_body` ; même branche pour la propagation.
   - `media_summarizer/workers/youtube_ingestion_worker.py` (`_requested_transcript_language`, `_fetch_apify_transcript`) lit la valeur côté worker.

3. **Côté actor Apify** : pour que la langue soit *réellement* prise en compte par Apify (et pas juste utilisée pour le tri yt-dlp natif), il faut **soit** :
   - **(a)** Changer l'actor pour un qui accepte un paramètre de langue dans son input schema (par ex. `easyapi/youtube-transcript-scraper` qui accepte `youtube_url` + `language` + `include_transcript_text` selon les notes de task-202). Mettre à jour `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID` dans le secret runtime + adapter le payload + adapter le parsing de la réponse (`transcript_text` vs `transcript_only_text`). **C'est l'option recommandée** car elle permet de réellement piloter la langue côté Apify, ce qui est le but explicite de cette tâche.
   - **(b)** Conserver l'actor actuel (`scrape-creators~best-youtube-transcripts-scraper`) et accepter qu'on ne pilote *pas* la langue Apify ; on garde la `reading_language` uniquement pour le tri des sous-titres natifs yt-dlp et on laisse le pipeline downstream task-192 (détection de langue + traduction GPT-5-nano) ramener au `reading_language` cible si nécessaire. Plus simple mais ne répond pas à la demande "variabiliser la langue dans le payload de l'actor Apify".

   L'implémenteur doit choisir explicitement entre (a) et (b) et documenter la décision. Si (a), prévoir un test coût/qualité minimal avant rollout (1 URL EN, 1 URL FR, 1 URL ES) pour confirmer que le nouvel actor renvoie un transcript dans la langue demandée quand elle existe et fallback propre sinon.

4. **Override par contenu** : si l'user soumet explicitement `transcript_language` dans la requête (ex. il regarde une vidéo en EN alors que sa `reading_language` est FR et veut le transcript EN d'origine pour l'avoir non traduit avant que task-192 ne le retraduise), ce paramètre doit primer sur la `reading_language` du profil. Le default = profil, l'override = payload request.

5. **Compatibilité avec task-192** : la `reading_language` reste la cible *finale* pour le user. Si Apify renvoie un transcript dans une langue ≠ `reading_language` (ex. la vidéo n'a pas de transcript dans la langue demandée et Apify retourne la langue source), task-192 prendra le relais et fera la traduction LLM. Cette tâche n'invalide donc pas task-192 — elle améliore juste le "best effort" amont en demandant à Apify la bonne langue dès le départ pour économiser un appel LLM de traduction quand c'est possible.

## Hors-scope

- Pas de changement côté autres sources (TikTok, Instagram, Deepgram audio/podcast) — leur traitement de langue reste régi par task-192.
- Pas de changement du modèle de données `User.reading_language` — il existe déjà.
- Pas de changement UX mobile — le réglage existe déjà dans Settings (task-190).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 L'API `POST /api/media/ingest-url` utilise `current_user.reading_language` comme default pour `transcript_language` quand le client ne le fournit pas explicitement
- [ ] #2 La `transcript_language` voyage API → orchestrator → message SQS → worker YouTube et n'est plus écrasée par un default codé en dur côté worker quand la valeur arrive bien depuis l'API
- [ ] #3 Décision documentée (a) ou (b) sur l'actor Apify : si (a), `APIFY_YOUTUBE_TRANSCRIPT_ACTOR_ID` mis à jour, payload et parsing adaptés, mini-test 3 URLs (EN/FR/ES) probant ; si (b), justification écrite dans la PR pourquoi on garde l'actor actuel
- [ ] #4 Le payload HTTP envoyé à Apify embarque effectivement la langue cible (cas (a)) OU il est documenté que la langue n'est utilisée que côté yt-dlp et task-192 prend le relais (cas (b))
- [ ] #5 Override : si `transcript_language` est fourni explicitement dans la requête, il prime sur `current_user.reading_language`
- [ ] #6 Tests unitaires : (1) requête sans `transcript_language` + user.reading_language=fr → message SQS porte transcript_language=fr ; (2) requête avec transcript_language=en + user.reading_language=fr → message porte en ; (3) si actor change (cas a), test du payload outgoing vers Apify et du parsing de la réponse
- [ ] #7 E2E `tests/e2e/test_phase4_other_sources.py::test_youtube_ingestion` continue de passer ; pas de régression sur path natif yt-dlp ni sur path Deepgram fallback
- [ ] #8 Pas de régression task-192 : la détection+traduction reste fonctionnelle si Apify renvoie une langue ≠ reading_language
<!-- AC:END -->
