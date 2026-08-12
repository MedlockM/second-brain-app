---
id: task-250
title: >-
  Benchmark how to make the audio-minutes quota count real minutes
  (resolve-before-accept vs reconcile-after)
status: To Do
assignee: []
created_date: '2026-08-12 18:31'
labels:
  - benchmark
  - billing
  - backend
  - quota
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte — le bug, mesuré dans le code le 2026-08-12

La limite « minutes d'audio par mois » **ne limite pas les minutes d'audio : elle compte les imports audio.**

Chemin exact, pour un partage d'URL (le seul chemin d'entrée de contenu dans l'app mobile, via le share intent) :

1. `media_summarizer/api/endpoints/media.py:597` appelle `check_submission_allowed(..., duration_seconds=0)`, avec le commentaire assumé `# duration unknown at URL ingestion time`. À ce stade l'URL n'est pas résolue, le média pas téléchargé.
2. `quota_enforcer.py:268` en déduit `minutes_needed = max(1, ceil(0/60)) if 0 > 0 else 1` → **1**. Le contrôle porte donc sur 1 minute quelle que soit la durée réelle.
3. `media.py:641` appelle `record_submission(duration_seconds=0)` → `quota_enforcer.py:400` débite `audio_minutes = 1`.
4. Après transcription, `workers/transcription/deepgram_worker.py:686-695` recalcule `minutes_used` depuis la vraie durée et l'émet dans l'événement SQS `episode_completion_status`. **Aucun consommateur ne lit ce champ** : `increment_monthly_usage` n'a qu'un seul appelant, `record_submission`, au moment de la soumission. `workers/events/media_completed_worker.py` ignore `minutes_used`.

**Conséquence chiffrée** : un utilisateur dont le cap est de 300 minutes peut faire transcrire 300 podcasts d'une heure, soit ~18 000 minutes réellement facturées par Deepgram pour 300 minutes débitées — un facteur 60. Le coût réel est supporté par le projet.

Effet de bord côté produit : les « minutes restantes » affichées par la carte task-245 dans l'onglet Account sont en réalité un compteur d'imports. Le chiffre montré à l'utilisateur n'a pas le sens que son libellé annonce.

Deux chemins échappent au bug, à confirmer pendant le benchmark : l'upload direct de fichier audio (`media.py:765`, la durée est connue localement) et le garde-fou `audio_too_long` par import.

## Objet du benchmark

Comparer la faisabilité réelle des deux corrections. **Aucune implémentation dans cette tâche.**

### Option A — résoudre la durée avant d'accepter le partage

C'est l'option que l'owner considère comme optimale sur le principe : le quota est alors exact, et le refus arrive avant tout coût. Le doute de l'owner, à instruire précisément : **on partage depuis beaucoup d'applications différentes**, donc obtenir la durée avant d'accepter n'est peut-être pas simple.

À établir, plateforme par plateforme (`SourcePlatform` dans `core/media_ingestion/domain.py` : spotify, apple_podcasts, deezer, rss, youtube, instagram, tiktok, x, whatsapp, web, direct_url, unknown) :

- La durée est-elle obtenable **avant** acceptation, et à quel coût ? Distinguer les cas : métadonnée gratuite dans le flux RSS, appel API tiers facturé (Apify, PodcastIndex), `HEAD` HTTP + parsing de conteneur, ou strictement impossible sans télécharger.
- Quelle latence ajoutée sur le partage ? Le share intent est un contexte où l'utilisateur attend ; chiffrer, ne pas estimer à vue.
- Que fait-on quand la résolution échoue ou dépasse un budget de temps ? Refuser un partage légitime est une régression produit ; accepter en aveugle ramène au bug actuel.
- Combien de plateformes resteraient sans durée fiable — et faut-il alors un mode dégradé pour celles-là (ce qui rendrait l'option A partielle, donc combinable avec B).

### Option B — réconcilier après transcription

Débiter le delta quand la durée réelle est connue. La plomberie est en partie déjà là : `minutes_used` circule dans l'événement SQS et n'attend qu'un consommateur.

À établir :

- Où brancher la réconciliation (consommateur `media_completed_worker`, ou autre) et l'effort réel, l'événement portant déjà le champ.
- Idempotence : les événements SQS peuvent être redélivrés ; un double débit est un faux positif de quota pour l'utilisateur.
- Que faire d'un dépassement constaté après coup — le média est transcrit et le coût engagé. Laisser le solde négatif, écrêter à zéro, bloquer l'import suivant ? Conséquence produit à énoncer.
- Le trou résiduel : rien n'empêche un utilisateur à 1 minute restante de lancer un podcast de 3 h. L'option B corrige la comptabilité, pas la prévention.
- Cohérence avec les chemins qui connaissent déjà la durée (upload direct), pour ne pas débiter deux fois.

### Attendu de la recommandation

Un choix argumenté, qui peut être une combinaison (A là où la durée est gratuite et fiable, B en filet partout ailleurs). La recommandation doit dire explicitement, pour chaque plateforme, quel mécanisme s'applique — et ne pas masquer les plateformes où aucune des deux options ne donne un quota exact.

Chiffrer l'exposition financière actuelle avant/après est attendu : c'est ce qui justifie l'effort retenu.

## Références

- `media_summarizer/core/services/quota_enforcer.py` (`check_submission_allowed` §3 caps mensuels, `record_submission`)
- `media_summarizer/api/endpoints/media.py:597` et `:641` (partage d'URL), `:765` (upload direct, durée connue)
- `media_summarizer/api/endpoints/podcasts.py:274` (même `duration_seconds=0`)
- `media_summarizer/workers/transcription/deepgram_worker.py:686-695` (`minutes_used` réel, émis et jamais consommé)
- `media_summarizer/core/media_ingestion/adapters/orchestrators.py:272` (chemin Apify, `minutes_used` calculé puis émis)
- `media_summarizer/utils/quota_usage_db.py` (`increment_monthly_usage`)
- task-110 (enforcement backend), task-244 (traitement des refus côté mobile), task-245 (carte d'affichage qui expose le compteur trompeur)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 docs/research/task-250-audio-minutes-quota-accuracy/README.md exists with owner_decision: pending in its front-matter
- [x] #2 The README quantifies the current exposure: for each audio platform, minutes really consumed versus minutes debited, with the factor and an estimated monthly euro cost
- [x] #3 Option A is assessed per SourcePlatform value (spotify, apple_podcasts, deezer, rss, youtube, instagram, tiktok, x, whatsapp, web, direct_url, unknown): whether duration is obtainable before acceptance, by which mechanism, at what third-party cost and what added share latency
- [x] #4 The platforms where no pre-acceptance duration is reliably obtainable are named explicitly, with what the fallback would be for them
- [x] #5 Option B is assessed with its SQS redelivery idempotency problem and an explicit answer on what happens to an overrun detected after the fact (negative balance, clamped to zero, or next import blocked)
- [x] #6 The recommendation states, per platform, which mechanism applies, and may combine A and B rather than picking one
- [x] #7 No implementation: no change to quota_enforcer.py, the endpoints or the workers in this task
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
**Mode: initial** (no `docs/research/task-250-*` directory existed, no prior `README.owner-rejected-*.md`, no `complement-request-*.md`). Research only — no source file was modified, satisfying AC #7.

Deliverable: `docs/research/task-250-audio-minutes-quota-accuracy/README.md` (`owner_decision: pending`, 431 lines).

**Recommendation, awaiting owner validation**: neither Option A nor Option B as stated, but a three-layer hybrid — Layer 0 fix `classify_media_type` and the two independent platform detections plus the three missing enforcement points; Layer 1 gate on the real duration inside the existing resolution workers *before* the Deepgram enqueue (Option A's mechanisms, moved off the request path, 0 ms added share latency); Layer 2 settle from Deepgram's `metadata.duration` under a conditional DynamoDB write (Option B, hardened). Per-platform mechanism table in the `Recommendation` section covers all twelve `SourcePlatform` values.

Findings beyond the task description, all read from the code:
- `spotify`, `apple_podcasts`, `deezer` and `direct_url` are classified `article`, so they debit **zero** audio minutes while still reaching Deepgram; the `text_only` tier gate never fires for them either.
- `POST /media/upload-audio` and `POST /media/ingest-shared-content` have **no quota enforcement at all** (the task assumed the direct-upload path escaped the bug); `rss_feed_poll_worker` is a third unmetered Deepgram producer.
- `duration_seconds = 0` also disables `audio_too_long` / `max_audio_per_import_minutes` and the cost hard-block, not just the monthly cap.
- The `minutes_used` field the task proposes reconciling on is a producer hint defaulting to 1, and it is emitted **twice** per job to the same queue — a naive consumer double-debits every job before any SQS redelivery.

Quantified exposure (AC #2): up to **EUR 224.40/month of Deepgram per `mix` subscriber** (net revenue EUR 3.542) via URL shares alone, plus two endpoints with no ceiling; **EUR 132.00/month on a EUR 2.125 Reader plan** that is sold as excluding audio; expected overspend ~EUR 92/month at 100 subscribers under stated assumptions. After the recommended fix: 360 min/month, EUR 1.58.

New mechanism identified and measured (AC #3/#4): an **HTTP Range container probe** (one 64 KB ranged GET, occasionally a second 4 KB one) yields an exact duration for any MP3 enclosure, free, with **+0.01 % / +0.01 % / -0.02 %** error measured on three real podcast feeds across three CDNs. This closes the reliability gap on `apple_podcasts` and `rss`, where `trackTimeMillis` / `itunes:duration` are missing precisely on the newest episodes (measured: 3 of the newest 5 on lexfridman.com).

Overrun policy answered explicitly (AC #5): store the true over-cap value, clamp only for display (`entitlements.py:118` already does `max(0, cap - used)`, so no mobile change), never negative, never refund, next import refused naturally.

Side finding for a possible separate task: `providers.transcription.cost_per_minute_eur = 0.003` understates the Deepgram Nova-3 PAYG rate (USD 0.0048/min) by 47 %, which makes `audio_heavy` loss-making at full usage even with a perfectly exact quota.

Task left in `To Do` with `owner_decision: pending`; the owner's `Decision` field is what `task-251` must follow.
<!-- SECTION:NOTES:END -->
