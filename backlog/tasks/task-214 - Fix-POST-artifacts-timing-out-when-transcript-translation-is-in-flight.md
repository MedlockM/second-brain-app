---
id: task-214
title: Fix POST /artifacts timing out when transcript translation is in-flight
status: Done
assignee: []
created_date: '2026-06-16 15:07'
labels:
  - bug
  - api
  - translation
  - artifacts
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Reproduit le 2026-06-16 sur l'app Expo (dev) avec le media item `29edcb43-b018-4673-9df0-b716cd56a144` (article web ingéré depuis `theneuralmaze.substack.com`).

Sequence observée :
1. `POST /api/media/ingest-url` → article extracted → status `completed`.
2. `GET /raw-content` détecte `en` ≠ `fr`, réserve une traduction et **enqueue le worker `transcript_translation`** (réponse `raw_content.translation_enqueued`).
3. Worker SQS démarre la traduction (gpt-5-nano sur ~25k tokens, durée mesurée 141 s).
4. ~25 s plus tard, le user clique "Generate Learning notes" → mobile envoie `POST /api/media/{id}/artifacts` (`artifact_type=notes`).
5. La Lambda API timeout à 30 s (`Status: timeout` dans le rapport CloudWatch, RequestId `e3dc68fe-033e-4a18-908a-d6b7c49c1c13`), API Gateway renvoie `503`.
6. Le worker termine sa traduction ~110 s plus tard (`worker.translation_completed`, `duration_ms: 141102`).

Côté mobile l'erreur remonte comme `SyntaxError: JSON Parse error: Unexpected end of input` (connexion coupée) puis l'UI affiche "Failed".

## Cause racine

`media_summarizer/api/endpoints/artifacts.py::create_artifact` appelle `request_artifact_generation` qui appelle `_resolve_effective_transcript` (`media_summarizer/core/services/artifact_service.py:404`) → `ensure_translated_transcript` (`media_summarizer/core/services/transcript_translation.py:347`).

`ensure_translated_transcript` :
- ne consulte **pas** le lock DynamoDB `translation_idempotence` (le mécanisme `queued` / `in_progress` que `raw_content_service.get_raw_content` utilise pourtant — cf. l'event `raw_content.translation_in_flight` dans nos logs).
- vérifie uniquement `s3.object_exists(translated_key)`. Si l'objet n'est pas encore présent, elle relance une traduction **synchrone** dans la Lambda API (timeout 30 s).

Conséquence : tout `POST /artifacts` qui arrive pendant qu'un worker `transcript_translation` est en cours pour le même `(transcript_s3_key, target_language)` déclenche un appel OpenAI synchrone redondant qui dépasse le timeout API.

## Acceptance criteria

- [ ] `_resolve_effective_transcript` (ou `ensure_translated_transcript`, à arbitrer côté implémentation) consulte le lock DynamoDB `translation_idempotence` via `get_translation_lock(fingerprint)` avant de tenter une traduction synchrone.
- [ ] Si la traduction est `queued` ou `in_progress`, l'API renvoie `409 CONFLICT` avec un payload exploitable par le mobile (status + indication "translation pending"), au lieu de relancer une traduction.
- [ ] Si la traduction est `done` mais que `s3.object_exists` revient `false` (incohérence rare), garder le fallback actuel (re-traduction synchrone) pour ne pas bloquer l'utilisateur.
- [ ] Le mobile (`mobile/app/media/[id].tsx::handleGenerate`) gère le 409 sans afficher "Failed" : passer l'artefact en état `queued` et démarrer le polling déjà existant (cohérent avec le polling raw-content qui réussit après ~140 s sur le même flux).
- [ ] Tests unitaires couvrant les trois branches (lock `done` + objet présent → reuse, lock `in_progress` → 409, pas de lock → traduction synchrone comme aujourd'hui).
- [ ] Test d'intégration / repro manuel : ingest article EN, déclencher Generate notes pendant la traduction, vérifier que l'UI passe en `queued` et résout en `ready` sans 503.
<!-- SECTION:DESCRIPTION:END -->
