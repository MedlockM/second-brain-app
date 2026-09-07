---
id: task-368
title: >-
  Benchmark des chemins de livraison de notifications push mobiles pour le
  Digest
status: To Do
assignee: []
created_date: '2026-09-06 16:12'
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
- [ ] #1 Un document docs/research/task-368-push-delivery/README.md existe, avec une front-matter portant owner_decision: pending et les champs Decision et Validated at vides sous Owner Validation
- [ ] #2 Le document compare Expo Push Service, AWS SNS mobile push et APNs/FCM en direct sur chacun des critères listés dans la description, sous forme de tableau lisible
- [ ] #3 Le document dit, pour chaque option, ce que devient le producteur SQS déjà écrit dans workers/digest/scheduler.py et quelle forme prend le consommateur
- [ ] #4 Le document énumère les credentials à obtenir et l'endroit exact où les déposer dans EAS et dans la console du fournisseur, en nommant les intitulés de l'interface actuelle
- [ ] #5 Le document chiffre le coût du balayage toutes les 15 minutes imposé par le déclenchement à l'heure locale, et indique s'il existe un mécanisme moins coûteux
- [ ] #6 Le document énonce une recommandation unique et argumentée, distincte de la section Owner Validation
- [ ] #7 Aucun code applicatif, aucune dépendance et aucun fichier Terraform ne sont modifiés par cette tâche
<!-- AC:END -->
