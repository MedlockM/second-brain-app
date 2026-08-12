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
- [ ] #1 docs/research/task-250-audio-minutes-quota-accuracy/README.md exists with owner_decision: pending in its front-matter
- [ ] #2 The README quantifies the current exposure: for each audio platform, minutes really consumed versus minutes debited, with the factor and an estimated monthly euro cost
- [ ] #3 Option A is assessed per SourcePlatform value (spotify, apple_podcasts, deezer, rss, youtube, instagram, tiktok, x, whatsapp, web, direct_url, unknown): whether duration is obtainable before acceptance, by which mechanism, at what third-party cost and what added share latency
- [ ] #4 The platforms where no pre-acceptance duration is reliably obtainable are named explicitly, with what the fallback would be for them
- [ ] #5 Option B is assessed with its SQS redelivery idempotency problem and an explicit answer on what happens to an overrun detected after the fact (negative balance, clamped to zero, or next import blocked)
- [ ] #6 The recommendation states, per platform, which mechanism applies, and may combine A and B rather than picking one
- [ ] #7 No implementation: no change to quota_enforcer.py, the endpoints or the workers in this task
<!-- AC:END -->
