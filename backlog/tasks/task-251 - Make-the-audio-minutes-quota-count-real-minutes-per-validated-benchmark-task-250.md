---
id: task-251
title: >-
  Make the audio-minutes quota count real minutes, per validated benchmark
  (task-250)
status: Done
assignee: []
created_date: '2026-08-12 18:32'
updated_date: '2026-08-13 08:45'
labels:
  - billing
  - backend
  - quota
dependencies:
  - task-250
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Objet

Corriger la comptabilité des minutes d'audio, de sorte que la limite mensuelle porte sur les minutes réellement transcrites et non sur le nombre d'imports.

**Lire d'abord `docs/research/task-250-audio-minutes-quota-accuracy/README.md`**, section `Owner Validation`, champ `Decision` : c'est elle qui dit quel mécanisme retenir, plateforme par plateforme. La décision de l'owner peut différer de la recommandation initiale du benchmark, et peut combiner les deux options (résolution avant acceptation là où la durée est fiable et gratuite, réconciliation après coup en filet ailleurs). Suivre aussi les fichiers `complement-response-*.md` si le champ `Decision` y renvoie.

Ne pas rouvrir le choix d'architecture ici : il est tranché dans le README.

## Portée

Ce que la décision de l'owner impliquera, à adapter à ce qu'elle dit :

1. Rendre le débit conforme à la durée réelle sur les chemins désignés par la décision.
2. Traiter le sort d'un dépassement constaté après coup selon ce que la décision arrête (solde négatif, écrêtage à zéro, blocage de l'import suivant).
3. Garantir l'idempotence si la décision retient une réconciliation sur événement : les messages SQS peuvent être redélivrés, et un double débit se traduit par un refus injustifié pour un utilisateur qui paie.
4. Ne pas doubler le débit sur les chemins qui connaissent déjà la durée à la soumission (upload direct de fichier audio, `media.py:765`).

## Points de vigilance

- **Le libellé côté mobile doit rester vrai.** La carte « YOUR PLAN » de task-245 affiche `minutes_remaining` calculé par `entitlements.py:118` à partir de `audio_minutes_used`. Si la sémantique du compteur change, vérifier que le chiffre affiché garde le sens que son libellé annonce.
- **Un entitlement inconnu doit rester permissif.** Une erreur de lecture du quota ne doit pas verrouiller un utilisateur abonné.
- L'enforcement reste côté backend : aucune règle de quota ne doit être déplacée côté client.

## Hors portée

- Le grisage préventif d'actions côté mobile (écarté par l'owner le 2026-08-12 sur task-245 : l'app n'a pas de bouton d'import, le contenu entre par le share intent du système).
- La tarification et le dimensionnement des caps par tier.

## Références

- `media_summarizer/core/services/quota_enforcer.py` (`check_submission_allowed`, `record_submission`)
- `media_summarizer/api/endpoints/media.py:597`, `:641`, `:765` — `media_summarizer/api/endpoints/podcasts.py:274`
- `media_summarizer/workers/transcription/deepgram_worker.py:686-695` (`minutes_used` déjà émis dans l'événement SQS)
- `media_summarizer/workers/events/media_completed_worker.py` (consommateur candidat)
- `media_summarizer/utils/quota_usage_db.py` (`increment_monthly_usage`)
- `media_summarizer/api/endpoints/entitlements.py:118` (calcul de `minutes_remaining` exposé au mobile)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The implementation follows the mechanism recorded in the Decision field of docs/research/task-250-audio-minutes-quota-accuracy/README.md, per platform
- [x] #2 A transcribed audio debits the user's monthly counter by its real duration in minutes, verified end to end on AWS dev with a media whose real duration exceeds one minute
- [x] #3 A user whose remaining balance is smaller than the real duration of the submission is handled per the owner's decision, and the behaviour is stated in the implementation notes
- [x] #4 If the retained mechanism reconciles on an event, a redelivered message does not debit twice, proven by replaying the same event
- [x] #5 The paths that already know the duration at submission time (direct audio upload) are not debited twice
- [x] #6 minutes_remaining returned by /api/v1/entitlements/status still matches what the Account tab claims it means
- [x] #7 A failure to read or write the quota counters leaves an already-subscribed user able to submit, and the failure is logged
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Three-layer hybrid, implemented in the order 0 -> 1 -> 2 required by the owner's `Decision`.

**Layer 0 — classification and enforcement holes.** `quota_enforcer.classify_media_type` now maps `spotify`, `apple_podcasts`, `deezer`, `direct_url` and `manual` to the `audio` category (they used to fall through to `article`, so the `text_only` tier gate never fired on a shared podcast link). Platform detection in `media.py` is unified on the single `RuleBasedUrlClassifier` — the duplicate `_detect_platform` helper is deleted. Three unmetered entry points are now gated: `POST /api/media/upload-audio`, `POST /api/media/ingest-shared-content` and `rss_feed_poll_worker`.

**Layer 1 — one debit at submission, with a real duration when it is free.** New `core/services/audio_duration_probe.py` reads container metadata without ffmpeg: ID3v2 tag length + first MPEG frame header + `Xing`/`Info`/`VBRI` frame count (CBR bitrate fallback), MP4 `moov`/`mvhd` box walk, Ogg granule position, WAV, FLAC. Remotely it costs at most three short HTTP Range requests under a 5 s budget; when the ID3v2 tag is larger than the head window (embedded cover art of several hundred kB is routine on podcast CDNs) the tag header gives the exact offset of the first audio frame and one extra Range request lands on it. If the server ignores Range, the probe returns `None` rather than parsing bytes from the wrong offset. New `core/services/audio_quota_gate.py` wraps "resolve the cheapest duration available -> check -> debit -> mark the job failed on refusal" and is called once per path, immediately before the Deepgram enqueue. A metadata failure never refuses a legitimate submission: the gate debits a provisional 1 minute and Layer 2 settles.

**Layer 2 — settlement from Deepgram's billed duration.** `deepgram_worker` reads `metadata.duration` out of the API response right after `extract_transcript` and applies the delta versus what the producer already debited (carried in the SQS body as `quota_debited_minutes`). Settlement lives in the transcription worker, not in `media_completed_worker`, and no longer trusts the old `minutes_used` producer hint. A non-audio quota category (social video) short-circuits the settlement so a reel never consumes audio minutes.

**Idempotency.** Every counter write carries a token (`{job_id}:gate` or `{job_id}:settle`) and DynamoDB applies the `ADD` under `attribute_not_exists(settled_jobs) OR NOT contains(settled_jobs, :token)`. A redelivered SQS message therefore fails the condition and is skipped, logged as `quota.monthly_increment_skipped_duplicate`.

**AC #3 — overrun behaviour (per the owner's decision).** The true value is stored, display is clamped, nothing is ever refunded and the balance never goes negative. Concretely: a submission is refused up front when the *known* duration does not fit (`tier_quota_exceeded`, or `audio_too_long` when a single import exceeds the per-import cap) and nothing is debited; but when the real duration is only discovered at settlement time, the counter is topped up to the true value even if that pushes usage past the cap, and the *next* import is refused naturally. `entitlements.py` already clamps with `max(0, cap - used)`, so `minutes_remaining` never displays a negative number.

**AC #5 — no double debit.** Exactly one debit per job, at the producer gate. Producers forward `quota_debited_minutes`; an absent field means 0, so an un-gated path is charged the full real duration at settlement instead of nothing. `media_submission.py` had a latent double-debit window (`record_submission` after `send_message`) — the debit now happens before the enqueue, with the gate token.

**AC #6 — mobile label.** No mobile change was needed and none was made. The "AUDIO MIN LEFT" figure only becomes truthful with this task: before it decremented once per import regardless of length.

**AC #7 — fail open.** `check_submission_allowed` is now a permissive wrapper around `_evaluate_submission_allowed`: any exception is logged as `quota.check_failed_open` with a stack trace and the submission is allowed. Settlement write failures are likewise swallowed and logged.

**Known residual, deliberately untouched.** `POST /api/v1/podcasts/submit` still calls `record_submission(duration_seconds=0)` without a token and does not forward `quota_debited_minutes`, so it over-charges by exactly one provisional minute (the settlement then adds the remaining delta). `AGENTS.md` forbids touching `/api/v1/` endpoints, so this is left as is.

No automated tests were added (repository rule). Verification was done on AWS dev (eu-west-3) against the real DynamoDB / S3 / SQS / Deepgram resources with a real podcast enclosure: probe 145 s, Deepgram billed 145.00569 s, counter settled to 3 = ceil(145/60); replaying the same message body two more times left the counter unchanged; a tier-M user at 299/300 was refused without any debit; pointing the usage table at a non-existent name still allowed the submission and logged `quota.check_failed_open`.
<!-- SECTION:NOTES:END -->
