---
id: task-277
title: >-
  Unify Apify access behind one adapter across the three ingestion workers and
  switch it to run webhooks
status: Done
assignee:
  - Codex
created_date: '2026-08-17 21:48'
updated_date: '2026-08-18 00:53'
labels:
  - ingestion
  - backend
dependencies:
  - task-274
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Problem

Three ingestion workers call Apify, and no two of them do it the same way:

| Worker | Apify call | Wait |
|---|---|---|
| TikTok (`tiktok_ingestion_worker.py:656`) | `run-sync-get-dataset-items` | one HTTP request, client timeout 120 s, Lambda timeout 120 s |
| YouTube (`youtube_ingestion_worker.py:567`) | `run-sync-get-dataset-items` | one HTTP request, client timeout 60 s, Lambda timeout 120 s |
| Instagram (`instagram_apify_resolver.py`) | start-run + hand-written polling | `APIFY_MAX_POLLS` 40 x `APIFY_POLL_INTERVAL_SECONDS` 3 s = 120 s, Lambda timeout 120 s |

All three block a Lambda for the whole duration of a provider run, and all three have a nominal budget equal to their own Lambda ceiling, i.e. no margin.

## Why `run-sync` is the wrong shape to converge on

`run-sync-get-dataset-items` starts the actor and returns the dataset in a single response, so **the caller never holds a run ID**. Three consequences:

- When the client gives up, the run keeps going on Apify, succeeds, is billed, and its result is unreachable — the exact waste measured on Instagram on 2026-08-17 (six paid runs, zero saved media), but irrecoverable by construction. With SQS `maxReceiveCount: 3`, one slow item can bill three full runs.
- The client timeout is not the bound it looks like: `httpx.AsyncClient(timeout=N)` applies N per phase, and the read timeout is the maximum gap *between packets*, not the total elapsed time. A steadily-but-slowly responding actor can exceed it.
- There is nothing to correlate a callback with, so `run-sync` cannot be webhooked at all.

The Instagram shape (start-run, keep the run ID) is the right one. Its defect is the fixed poll count, not the shape.

## Scope

**One Apify adapter** shared by the three workers: start the run, persist the run ID on the processing job, register a webhook for the run's terminal states, and return without waiting. No polling loop and no blocking call remains on the Apify path.

**Resume on callback.** A public endpoint receives the Apify webhook, matches it against the run ID persisted on the job, and continues the pipeline exactly where each worker does today (Deepgram hand-off for Instagram/TikTok audio, transcript path for YouTube). It must authenticate the caller and tolerate duplicate deliveries — Apify can deliver a webhook more than once, and a second delivery must not enqueue a second Deepgram job.

**A terminal deadline, not a heartbeat.** A callback is not guaranteed: a delivery can be lost, the endpoint can be unavailable during a deploy. Without a backstop, such a job stays in `extracting` forever — no failure event, no DLQ, nothing in the Inbox but an item that never completes. This project has already been burned by exactly that class of silent failure (task-242, an archiver invoked 144 times that never wrote an object). The backstop here is deliberately minimal: when the run is started, post a delayed message on the same queue with `DelaySeconds`; when it fires, it is a no-op if the job already completed, and marks the job failed otherwise. No heartbeat, no visibility extension, no scheduled sweeper.

**Worker ceilings come down.** Once no worker waits on Apify, the 120 s timeouts and their visibility timeouts are oversized and should be brought back to what the remaining work actually needs.

## Risk to hold in mind

TikTok and YouTube are not broken today — this task changes two working paths. The failure mode to guard against is a run started whose ID is lost before it is persisted: the run ID must be written to the job **before** the worker returns, so that an orphaned run is always recoverable rather than merely improbable.

## Relationship to the other tasks

- Depends on **task-274**, which rebinds Instagram to its queue-first worker and is the fix for the user-visible `Save failed`. task-274's bounded-polling criterion stays valid: it is the interim correctness of a path that ships before this one.
- Supersedes **task-275** and **task-276**: there is no longer a technology choice to benchmark, only a shape to generalise.

## Notes to the owner

- DEPLOY PREREQUISITE — the callback cannot be exercised from a worktree. After merge and deploy, save one reel per platform (Instagram, TikTok, YouTube) and confirm each job carries a persisted Apify run ID, receives its callback, and reaches a transcript.
- The webhook secret must be created in Secrets Manager and registered on the Apify side; it is owner-side setup, not repository content.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A single Apify adapter module is the only place in media_summarizer/ that builds an Apify API URL or holds an Apify token, poll interval or timeout constant; the Instagram, TikTok and YouTube workers reach Apify only through it
- [x] #2 No call site uses run-sync-get-dataset-items any more: every actor run is started through the start-run endpoint
- [x] #3 The run ID is persisted on the processing job before the worker returns, so a run started by a worker that then dies is still identifiable from DynamoDB
- [x] #4 No polling loop, sleep or blocking wait on an Apify run remains in any of the three workers or in the resolver; the worker returns without knowing the run's outcome
- [x] #5 A webhook is registered per run covering the succeeded state and the terminal failure states (failed, aborted, timed-out), so a run that never succeeds still resolves its job instead of leaving it pending
- [x] #6 The callback endpoint rejects a request that does not carry the expected shared secret, and resumes a job only when the payload's run ID matches the run ID persisted on that job
- [x] #7 A duplicate delivery of an already-processed callback is a no-op: it does not enqueue a second Deepgram job and does not overwrite a completed job's state
- [x] #8 Starting a run also posts a delayed backstop message with DelaySeconds; when it fires it is a no-op if the job already completed, and marks the job failed with an explicit reason otherwise
- [x] #9 APIFY_MAX_POLLS and APIFY_POLL_INTERVAL_SECONDS are deleted rather than defaulted or disabled, and no environment variable or flag can restore the inline waiting path
- [x] #10 The three ingestion workers' Lambda timeouts and their queues' visibility timeouts are reduced to fit the work that remains once no Apify wait happens inside them
- [x] #11 ruff and mypy are clean, and terraform validate plus terraform plan exit 0 for the dev env
- [x] #12 No Apify token and no webhook secret is written into any tracked file, task notes and Terraform included
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Centraliser dans media_summarizer/infrastructure/apify_adapter.py les URL, jetons, actor IDs, timeouts, création des runs asynchrones avec webhook ad hoc sur les quatre états terminaux, authentification du callback et lecture des datasets.
2. Étendre ProcessingJob et database_async avec l’état opérationnel Apify, la persistance immédiate du run, une acquisition conditionnelle avec lease pour les callbacks et une expiration conditionnelle pour le backstop.
3. Faire router les messages initiaux, apify_callback et apify_backstop dans les trois workers ; conserver yt-dlp comme primaire, reprendre le traitement existant depuis le dataset au callback, gérer le second run YouTube sans langue et garantir les no-op sur doublons/runs périmés.
4. Ajouter POST /api/webhooks/apify : secret Bearer en comparaison constante, validation job/platform/run/dataset, puis réinjection durable sur la file du worker ; déclarer APIFY_WEBHOOK_URL via Terraform sans valeur secrète.
5. Supprimer run-sync, polling et anciennes constantes/configurations, ramener les trois Lambdas à 60 s et leurs visibilités à 360 s, actualiser la documentation opérateur.
6. Vérifier les 12 critères par recherches ciblées, ruff, mypy, terraform fmt/validate/plan dev et audit du diff/secrets ; consigner, passer Done et committer si tout est prouvé.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implémentation terminée le 2026-08-18.

- Ajout de `media_summarizer/infrastructure/apify_adapter.py`, unique propriétaire des URL, credentials et timeouts Apify. Les runs utilisent l’endpoint asynchrone, un webhook ad hoc couvrant SUCCEEDED, FAILED, ABORTED et TIMED_OUT, puis la lecture du dataset terminal.
- Ajout de la corrélation opérationnelle Apify sur `ProcessingJob` et de transitions DynamoDB conditionnelles : persistance immédiate du run, claim avec lease, finalisation atomique et expiration. Une course callback/backstop ne peut pas réécrire le gagnant ; les doublons et runs périmés deviennent des no-op.
- Ajout de `POST /api/webhooks/apify` avec authentification Bearer en comparaison constante, validation job/platform/run/dataset et réinjection sur la file du worker concerné.
- Instagram, TikTok et YouTube démarrent désormais le run puis rendent la main. Le callback reprend le parseur existant ; YouTube conserve son second run sans langue quand la piste demandée est absente.
- Chaque démarrage programme sur la même file un backstop SQS à 900 secondes. Les trois Lambdas passent à 60 secondes et leurs files à 360 secondes de visibilité. Terraform injecte seulement l’URL publique aux trois workers ; la valeur du secret reste exclusivement dans Secrets Manager.
- Suppression des endpoints run-sync, boucles/options de polling, de la configuration Apify du Settings général et de l’ancien `invocation_budget`, devenu sans lecteur.
- Documentation opérateur mise à jour.

Vérifications : `ruff check media_summarizer` OK ; `mypy media_summarizer` OK (169 fichiers) ; `terraform validate` dev OK ; `terraform plan` dev OK (exit 0, 0 destruction). `git diff --check` OK et audit du diff sans email, credential, jeton, secret ou identifiant de support ajouté. Aucun test automatisé ajouté ou exécuté, conformément à la règle du dépôt.
<!-- SECTION:NOTES:END -->
