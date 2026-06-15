---
id: task-203
title: >-
  Aligner la traduction de transcript async sur le pattern d'état/idempotence
  des artefacts pour supprimer le prewarm bloquant et la tempête de
  re-traductions (suite task-200)
status: Done
assignee: []
created_date: '2026-06-15 13:31'
labels:
  - feature
  - ingestion
  - mobile
dependencies:
  - task-200
  - task-192
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Deux bugs liés, observés en prod (dev) le 2026-06-15 sur un job YouTube (`5597e972`) et confirmés sur d'autres médias (Instagram `abddadd9`).

### Bug 1 — Prewarm synchrone bloquant (régression task-200)

task-192 a introduit `prewarm_translated_transcript()`, appelé **de façon bloquante** (`await`) dans chaque worker d'ingestion juste avant `job.mark_completed()`, plafonné à `PREWARM_TRANSLATION_TIMEOUT_SECONDS = 45s`. Or une traduction GPT-5-nano d'un transcript moyen/long prend 60-90s → le prewarm **timeout systématiquement** sur les transcripts un peu longs.

Conséquences mesurées :
- Le worker d'ingestion reste bloqué ~45s pour rien avant de compléter le job (job YouTube observé : 59s au total, dont 45s purement gaspillés sur le prewarm en timeout).
- Comme le timeout annule la coroutine, **rien n'est écrit en cache S3** → les 45s sont 100% perdus.

task-200 a rendu la traduction **entièrement asynchrone** (worker SQS dédié `transcript_translation_worker` + `/raw-content` qui enqueue à la demande + polling mobile). Le prewarm synchrone de task-192 aurait dû être retiré à ce moment-là, mais il subsiste dans **tous** les workers : `youtube_ingestion_worker`, `tiktok_ingestion_worker`, `deepgram_worker`, `article_extraction_worker`, `x_ingestion_worker`, `podcastindex_resolution_worker`, `document_parsing/worker`, et `media_ingestion/adapters/orchestrators.py` (instagram). D'où l'observation « sur d'autres médias aussi ».

### Bug 2 — Tempête de re-traductions (thundering herd)

Comme le prewarm ne remplit jamais le cache, quand le mobile poll `/raw-content`, chaque poll tombe sur un cache-miss et **réenqueue un nouveau job de traduction**. L'idempotence actuelle ne repose que sur `s3.object_exists(translated_key)`, qui ne distingue que « déjà terminé » vs « pas terminé » — elle n'a **aucune notion d'« en cours »**. Résultat mesuré : **le même transcript a été traduit 7+ fois en boucle** (job `5597e972`, 12:58:08 → 12:59:01), chaque traduction facturée à OpenAI. Bug amplifié par la durée variable des traductions : plus c'est long, plus il y a de polls qui réenqueuent pendant le trou.

## Insight clé : la solution existe déjà dans le repo

La **génération d'artefacts** (`artifact_service.py`, `request_artifact_generation`) ne souffre d'aucun de ces deux problèmes, alors que sa durée de génération est tout aussi variable (un quiz sur 3h de transcript vs un summary_short sur un tweet). Pourquoi ? Parce qu'elle ne raisonne pas en durée mais en **état persisté + réservation atomique** :

1. Un record de statut explicite : `MediaArtifactRecord.status ∈ {QUEUED, GENERATING, READY, FAILED}` — l'état « en cours » existe.
2. Une réservation atomique conditionnelle (`reserve_request_pointer`, `reserve_generation`, écritures DynamoDB `ConditionExpression`) : le premier appel gagne et enqueue ; tous les suivants lisent l'état existant et **ne réenqueuent jamais**.
3. La reprise sur échec passe par DLQ → statut `FAILED` (`fail_artifact_generation`), qui réautorise proprement un nouveau déclenchement.

La traduction async doit être **alignée sur ce même pattern**, déjà éprouvé en prod. Aucun timeout/TTL deviné n'est nécessaire — l'état reflète la réalité, indépendamment de la durée.

## Objectif

1. **Supprimer le prewarm bloquant** de tous les workers d'ingestion. Le job doit se compléter immédiatement après l'upload du transcript (gain ~45s). La traduction est laissée au chemin async existant (`/raw-content` cache-miss → enqueue → polling mobile). Pas de second chemin d'enqueue à l'ingestion (éviter la duplication soulevée pendant l'analyse) : le déclenchement reste lazy via `/raw-content`.

2. **Reporter `persist_detected_language()`** (effet de bord actuel du prewarm) dans le worker async `transcript_translation_worker` / `ensure_translated_transcript`, pour ne pas perdre la persistance de la langue détectée sur le job.

3. **Introduire une machine à états de traduction** persistée (statut + réservation atomique conditionnelle), calquée sur le pattern artefacts, pour tuer la tempête de re-traductions :
   - statut `none → queued → in_progress → done | failed`
   - enqueue gardé par une réservation atomique (`ConditionExpression`) : seul le premier passe
   - `/raw-content` et le mobile **lisent** ce statut au lieu de tester `object_exists` → plus de re-déclenchement, quelle que soit la durée
   - reprise sur échec via DLQ → statut `failed`, qui réautorise un réenqueue propre

## Hors scope

- Optimisation du temps de traduction lui-même (chunking, modèle, parallélisation) — la durée variable est acceptée telle quelle, c'est l'état qui la gère.
- Prewarming proactif à l'ingestion : explicitement écarté pour ne pas dupliquer le chemin d'enqueue de `/raw-content`.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 L'appel bloquant prewarm_translated_transcript() est retiré de TOUS les workers d'ingestion (youtube, tiktok, deepgram, article_extraction, x, podcastindex_resolution, document_parsing, et orchestrators.py pour instagram) ; le job se complète immédiatement après l'upload du transcript sans attendre la traduction
- [ ] #2 persist_detected_language() est désormais appelé par le chemin async (transcript_translation_worker / ensure_translated_transcript) afin que la langue détectée reste persistée sur le job malgré le retrait du prewarm
- [ ] #3 Une machine à états de traduction est persistée avec les statuts none → queued → in_progress → done | failed, exposée de façon à ce que /raw-content et le mobile puissent la lire
- [ ] #4 Le déclenchement d'une traduction est gardé par une réservation atomique (ConditionExpression DynamoDB, sur le modèle de reserve_generation/reserve_request_pointer des artefacts) : pour un couple (transcript_s3_key, target_language) donné, seul le premier appel enqueue un job ; les appels concurrents/suivants lisent l'état existant sans réenqueuer
- [ ] #5 /raw-content ne réenqueue plus de job de traduction lorsqu'une traduction est déjà queued ou in_progress : il retourne le transcript original avec le statut courant (translation_pending reflétant queued/in_progress). Vérifié : un transcript long traduit une seule fois malgré N polls (reproduction du cas 5597e972 qui produisait 7+ traductions)
- [ ] #6 Le worker async met à jour le statut (queued → in_progress au début, → done en fin de succès) ; sur échec après épuisement des retries (DLQ), le statut passe à failed, ce qui réautorise un réenqueue propre lors d'un prochain accès
- [ ] #7 Aucun paramètre de durée/TTL deviné n'est introduit pour gérer le in-flight : la sûreté repose uniquement sur l'état persisté + la réservation atomique + le mécanisme natif SQS (visibility timeout / DLQ), à l'image des artefacts
- [ ] #8 Le mobile gère les statuts queued/in_progress (affiche le transcript original + indicateur de traduction en cours, poll jusqu'à done) et failed (badge d'échec, pas de boucle de polling infinie)
- [ ] #9 Logs structurés conservés sur le worker async (source, detected_language, target_language, méthode de détection, modèle, tokens, durée, coût estimé) et complétés par les transitions d'état (queued/in_progress/done/failed)
- [ ] #10 Tests : (a) retrait du prewarm n'altère pas la complétion du job ni la persistance de detected_language ; (b) N requêtes /raw-content concurrentes sur une traduction non encore en cache ne déclenchent qu'UN seul job (anti-thundering-herd) ; (c) un échec worker → DLQ → statut failed → réenqueue autorisé ensuite
- [ ] #11 docs mis à jour (docs/INGESTION_WORKERS_PROVIDERS.md et/ou la doc translation de task-200) pour décrire la machine à états de traduction et le nouveau contrat /raw-content (statuts au lieu d'un simple translation_pending booléen)
<!-- AC:END -->
