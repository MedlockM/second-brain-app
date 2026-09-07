---
id: task-368
title: >-
  Benchmark des chemins de livraison de notifications push mobiles pour le
  Digest
status: Done
assignee: []
created_date: '2026-09-06 16:12'
updated_date: '2026-09-07 14:44'
labels:
  - benchmark
  - mobile
  - backend
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## La question à trancher

Le Digest doit notifier l'utilisateur **chaque jour à 18h30 locale** (daily) et **chaque lundi à 9h30 locale** (weekly), en notification système classique iOS et Android.

Trois chemins de livraison produisent **exactement la même notification** à l'écran — l'utilisateur ne peut pas les distinguer. Ils diffèrent sur ce qui est invisible : credentials, coût, ops, et forme du consommateur. C'est ce choix, et lui seul, que ce benchmark doit trancher :

1. **Expo Push Service** — un token unique pour les deux plateformes, relais tiers, gratuit.
2. **AWS SNS mobile push** — cohérent avec le backend existant, endpoints par appareil à gérer.
3. **APNs et FCM en direct** — aucun intermédiaire, deux intégrations à maintenir.

## L'existant à prendre en compte

Le producteur est **déjà écrit** : `media_summarizer/workers/digest/scheduler.py` publie un message de notification sur une file SQS pour le weekly. Son commentaire dit pourquoi rien n'arrive :

> « Real push notifications are post-V1, so Terraform does not create the queue in any environment and the variable is unset everywhere. »

Manquent donc : la file en Terraform, un consommateur, le producteur daily (seul le weekly existe), la planification du worker (aucune règle cron ne le vise aujourd'hui), et la réception côté app — `expo-notifications` n'est pas installé.

La recommandation doit **partir de ce producteur SQS existant** et dire ce qu'il devient dans chaque option, plutôt que de proposer une architecture qui l'ignore.

## Critères de comparaison attendus

- Credentials nécessaires de bout en bout et leur place dans EAS : clé APNs, compte de service FCM v1, ce qui doit être téléversé et où.
- Coût réel aux volumes de ce projet, et à un ordre de grandeur au-dessus.
- Charge d'exploitation : cycle de vie des tokens (enregistrement, rotation, invalidation d'un appareil désinstallé), accusés de réception, observabilité des échecs.
- Intégration avec la file SQS déjà produite, et forme du consommateur (Lambda, worker existant).
- Dépendance à un tiers : ce qu'on perd si le relais tombe, et la réversibilité.
- Traitement des tokens au regard de la politique de rétention du dépôt (`docs/DATA_RETENTION.md`).
- Effort d'implémentation, et impact sur le fingerprint mobile.

## Question secondaire, à traiter dans le même document

Le déclenchement à l'heure locale suppose de balayer les fuseaux : le scheduler doit tourner **toutes les 15 minutes** — et non toutes les 30, à cause des fuseaux à +5:45 (Népal) et +12:45 (Chatham) — pour notifier ceux dont l'heure locale vient de franchir 18h30. Le benchmark doit chiffrer ce que coûte ce balayage dans chaque option et dire s'il existe un mécanisme plus économe (regroupement par fuseau, planification différée côté fournisseur).

Le fuseau lui-même est déjà traité par **task-367** et n'est pas dans ce périmètre.

## Ce que cette tâche ne fait pas

Aucune implémentation, aucune dépendance ajoutée, aucun Terraform écrit. Recherche, comparaison, recommandation.

## Notes pour l'owner (pas des ACs)

- Un fait à garder en tête en lisant la recommandation : `expo-notifications` est une dépendance native. Quelle que soit l'option retenue, la livraison passera par un **build EAS sur les deux plateformes, pas par une OTA** — et le palier gratuit plafonne à 15 builds iOS par mois.
- La décision finale t'appartient : le README sortira en `owner_decision: pending` et attend ton arbitrage.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Un document docs/research/task-368-push-delivery/README.md existe, avec une front-matter portant owner_decision: pending et les champs Decision et Validated at vides sous Owner Validation
- [x] #2 Le document compare Expo Push Service, AWS SNS mobile push et APNs/FCM en direct sur chacun des critères listés dans la description, sous forme de tableau lisible
- [x] #3 Le document dit, pour chaque option, ce que devient le producteur SQS déjà écrit dans workers/digest/scheduler.py et quelle forme prend le consommateur
- [x] #4 Le document énumère les credentials à obtenir et l'endroit exact où les déposer dans EAS et dans la console du fournisseur, en nommant les intitulés de l'interface actuelle
- [x] #5 Le document chiffre le coût du balayage toutes les 15 minutes imposé par le déclenchement à l'heure locale, et indique s'il existe un mécanisme moins coûteux
- [x] #6 Le document énonce une recommandation unique et argumentée, distincte de la section Owner Validation
- [x] #7 Aucun code applicatif, aucune dépendance et aucun fichier Terraform ne sont modifiés par cette tâche
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
**Mode: initial.** No `docs/research/task-368-*/` directory existed before this run, so this is a from-scratch benchmark — no `README.owner-rejected-*.md` to reconcile, no open `complement-request-*.md` to answer.

**Deliverable**: `docs/research/task-368-push-delivery/README.md` (685 lines), front-matter `owner_decision: pending`, `Decision` and `Validated at` left empty under `Owner Validation`.

**Recommendation awaiting owner validation**: option 1, Expo Push Service, with a single SQS consumer in the existing worker image and the push-receipt check re-enqueued onto the same queue with `delay_seconds=900`. The owner decides; the implementation task must read the `Decision` field, not this recommendation.

What the document establishes, and why the comparison is narrow:

- **The three options share almost their whole cost.** `expo-notifications`, the EAS build on both platforms, the Firebase project, `google-services.json`, the APNs `.p8`, the SQS queue, the token table, the scheduled sweep Lambda and the existing producer are identical in all three. §2 isolates that common trunk so no option is charged for something all three carry. The choice reduces to four questions: where the credentials live, how many state objects per device, how invalidation comes back, and who sits on the path.
- **The existing SQS producer survives untouched in all three options** (§8.1): its message names no token, no `EndpointArn`, no platform, no provider. Only the consumer differs — which is also what keeps the decision reversible on the backend side.
- **Cost cannot decide** (§11): all three are free at 20, 1 000 and 10 000 accounts; SNS is the only one that bills the message, and its delta is about 4.2 $/month at 100 000 accounts. Prices come from the AWS Price List Query API for eu-west-3, read 2026-09-07.
- **The secondary question is answered with a measurement, not an estimate** (§10). Across 498 IANA zones probed on two dates, a local 18:30 (and Monday 09:30) maps to UTC minute marks {:00, :30, :45} only — never :15 — so `cron(0,30,45 * * * ? *)` is provably exhaustive at 72 fires/day instead of 96. The trigger itself is free in all three options (no billed usage type for a scheduled CloudWatch Events rule; Lambda inside the free tier). The real cost is the per-fire DynamoDB reads: about 0.18 $/1.81 $/18.07 $ per month at 1k/10k/100k accounts with the current full `Scan`, and at 100k a naive fire no longer finishes inside the 900 s Lambda ceiling. A GSI keyed on the stored IANA zone name cuts that by ~62x and removes the time wall. Per-timezone `aws_scheduler_schedule` and provider-side deferred scheduling are both evaluated and rejected, with reasons (§10.4) — no send API among APNs, FCM v1, Expo or SNS offers a send-later field.
- **Console paths are given with the verbatim labels of the current UI** (§9), per the repo rule: Apple Developer, Firebase Console, Google Cloud Console, EAS CLI and dashboard, and the Amazon SNS console including the delivery-status and event-notification paths.
- **A fourth option is documented and rejected rather than ignored** (§7): local scheduled `expo-notifications` triggers, which cost zero and follow the device timezone natively, but cannot know whether the period is empty.
- **Honest gaps are listed in §16**, notably the unverified SNS `Publish` TPS quota and the fact that nothing was sent end-to-end.

**No application code, no dependency and no Terraform file was modified** (AC#7). The only files written are the research document and this task file. Task status stays `To Do`; Phase 0 of the dispatcher will move it once the owner sets `owner_decision`.
<!-- SECTION:NOTES:END -->
