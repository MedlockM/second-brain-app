---
id: task-251
title: >-
  Make the audio-minutes quota count real minutes, per validated benchmark
  (task-250)
status: To Do
assignee: []
created_date: '2026-08-12 18:32'
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
- [ ] #1 The implementation follows the mechanism recorded in the Decision field of docs/research/task-250-audio-minutes-quota-accuracy/README.md, per platform
- [ ] #2 A transcribed audio debits the user's monthly counter by its real duration in minutes, verified end to end on AWS dev with a media whose real duration exceeds one minute
- [ ] #3 A user whose remaining balance is smaller than the real duration of the submission is handled per the owner's decision, and the behaviour is stated in the implementation notes
- [ ] #4 If the retained mechanism reconciles on an event, a redelivered message does not debit twice, proven by replaying the same event
- [ ] #5 The paths that already know the duration at submission time (direct audio upload) are not debited twice
- [ ] #6 minutes_remaining returned by /api/v1/entitlements/status still matches what the Account tab claims it means
- [ ] #7 A failure to read or write the quota counters leaves an already-subscribed user able to submit, and the failure is logged
<!-- AC:END -->
