---
id: task-200
title: >-
  Rendre la traduction de transcript /raw-content asynchrone via un worker SQS
  dédié (suite task-192)
status: To Do
assignee: []
created_date: '2026-06-15 11:12'
updated_date: '2026-06-15 11:12'
labels:
  - feature
  - ingestion
  - mobile
dependencies:
  - task-192
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

task-192 a mis en place la détection+traduction (GPT-5-nano) des transcripts vers la `reading_language` de l'user, avec un "prewarm" best-effort (45s max) déclenché à la complétion du job d'ingestion. Quand ce prewarm n'a pas le temps de finir (traduction GPT-5-nano occasionnellement >45s), `/raw-content` retombe sur une traduction synchrone à la demande.

Le problème : `/raw-content` est exposé via API Gateway, qui a un **plafond dur et non négociable de 30s** sur le temps d'intégration Lambda (contrairement aux 15 workers d'ingestion existants, déclenchés par SQS, sans cette contrainte). Une traduction synchrone qui dépasse ce délai fait échouer toute la requête avec un 503, remonté côté mobile comme "Unable to load the transcript right now".

Un correctif d'urgence vient d'être posé : `get_raw_content` borne désormais l'appel de traduction à `RAW_CONTENT_TRANSLATION_TIMEOUT_SECONDS` (20s) et retombe sur le transcript original (`translation_failed=true`) en cas de dépassement. C'est un filet de sécurité, pas la bonne architecture.

## Objectif

Sortir complètement la traduction à la demande du chemin synchrone de `/raw-content`, en suivant le pattern déjà éprouvé des 15 workers d'ingestion (Lambda déclenchée par SQS, sans contrainte API Gateway) :

- `/raw-content` ne doit plus jamais déclencher d'appel LLM de traduction de manière synchrone.
- Si la traduction est déjà en cache S3 (cas normal grâce au prewarm task-192) → retournée immédiatement, comme aujourd'hui.
- Si elle ne l'est pas (cache miss) → `/raw-content` retourne immédiatement le transcript original avec un flag indiquant que la traduction est en cours, et déclenche un job de traduction asynchrone (SQS → nouveau worker dédié, sans contrainte de timeout).
- Le worker dédié traduit et persiste le résultat en S3 (réutilise `ensure_translated_transcript`), de façon idempotente.
- L'app mobile, en présence du flag "traduction en cours", relance `/raw-content` après un court délai jusqu'à obtenir la version traduite.

Le prewarm task-192 reste le chemin principal (cache chaud dans la grande majorité des cas) ; ce nouveau worker async devient le filet de sécurité pour les cache miss, et remplace le `RAW_CONTENT_TRANSLATION_TIMEOUT_SECONDS` actuel.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 /raw-content ne fait plus aucun appel LLM de traduction synchrone : si la traduction cible existe déjà en cache S3, elle est retournée immédiatement (comportement actuel inchangé)
- [ ] #2 Si la traduction n'est pas en cache, /raw-content retourne immédiatement le transcript original accompagné d'un flag explicite (ex: translation_pending=true) et déclenche un job de traduction asynchrone
- [ ] #3 Nouveau worker Lambda dédié, déclenché par SQS (suivant le pattern des workers d'ingestion existants, sans contrainte de timeout API Gateway), qui consomme ces jobs et appelle ensure_translated_transcript pour produire et persister la traduction en S3
- [ ] #4 Idempotence : des jobs de traduction dupliqués pour le même couple (transcript_s3_key, target_language) ne déclenchent pas de traductions redondantes (réutilise la logique d'idempotence existante)
- [ ] #5 L'app mobile gère le flag translation_pending en relançant /raw-content après un court délai jusqu'à obtenir la version traduite, sans afficher d'erreur
- [ ] #6 Le fallback synchrone borné (RAW_CONTENT_TRANSLATION_TIMEOUT_SECONDS) introduit en filet de sécurité est retiré, remplacé par ce mécanisme asynchrone
- [ ] #7 Logs structurés du nouveau worker suivant les conventions existantes (source, detected_language, target_language, méthode de détection, modèle, tokens, durée, coût estimé)
- [ ] #8 docs/INGESTION_WORKERS_PROVIDERS.md mis à jour pour documenter le nouveau worker et le contrat /raw-content (translation_pending)
<!-- AC:END -->
