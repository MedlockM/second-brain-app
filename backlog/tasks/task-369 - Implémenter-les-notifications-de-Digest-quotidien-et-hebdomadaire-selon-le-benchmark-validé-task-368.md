---
id: task-369
title: >-
  Implémenter les notifications de Digest quotidien et hebdomadaire selon le
  benchmark validé (task-368)
status: To Do
assignee: []
created_date: '2026-09-06 16:13'
labels:
  - mobile
  - backend
  - feature
dependencies:
  - task-367
  - task-368
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce qu'il faut lire d'abord

`docs/research/task-368-push-delivery/README.md` : **la décision de l'owner y est notée sous Owner Validation, et c'est elle qui fait foi**. Le chemin de livraison — Expo Push Service, AWS SNS ou APNs/FCM en direct — s'y trouve tranché, avec la forme du consommateur et les credentials.

Ne pas rejouer la comparaison ici, ne pas préférer une autre option à celle qui est validée. Si le README ne désigne aucune option, la tâche s'arrête et le dit : elle ne tranche pas à la place de l'owner. Si la décision renvoie à un fichier de complément du même dossier, le suivre.

## Le comportement attendu

Décisions owner du 2026-09-06 :

- **Daily** : une notification chaque jour à **18h30 heure locale de l'utilisateur**, portant sur les 24 heures glissantes qui précèdent.
- **Weekly** : une notification chaque **lundi à 9h30 heure locale**, portant sur la semaine écoulée, lundi à dimanche révolus.
- **Aucune notification quand la période est vide.** Rien d'enregistré, rien d'envoyé — pas de message « rien aujourd'hui ».
- **Aucune notification quand le fuseau est inconnu**, plutôt qu'un repli sur UTC qui sonnerait à une heure arbitraire. Le fuseau vient de task-367.
- La notification ouvre le Digest correspondant.

## L'existant sur lequel s'appuyer

- `media_summarizer/workers/digest/scheduler.py` **produit déjà** un message de notification sur une file SQS, mais **pour le weekly seulement** : le producteur daily est à écrire. Le nom de file est optionnel et non défini, et Terraform ne crée la file dans aucun environnement.
- **Aucune règle de planification ne vise ce worker** : les seules règles cron du dépôt visent `lambda_api`, `backup_library` et `media_lifecycle`.
- Le déclenchement à l'heure locale impose un balayage **toutes les 15 minutes** — et non toutes les 30, à cause des fuseaux à +5:45 et +12:45 — pour notifier ceux dont l'heure locale vient de franchir l'échéance. Le README de task-368 peut désigner un mécanisme moins coûteux : il prime.
- **L'opt-out existe déjà** : `UserDigestSettings` porte `digest_enabled`, `daily_digest_enabled` et `weekly_digest_enabled` (`core/models/digest.py`). Les réutiliser, ne pas créer un second jeu de réglages.
- Côté app, `expo-notifications` n'est pas installé : permission, enregistrement du token et gestion de l'ouverture sont à ajouter.

## Garde-fous

- **Une seule notification par période et par utilisateur.** Un balayage toutes les 15 minutes ne doit pas produire quatre envois par heure : l'envoi est marqué et l'idempotence est vérifiable.
- **Ne jamais écrire l'identité d'un testeur ni un token dans les logs.** Les tokens de push suivent la politique de `docs/DATA_RETENTION.md` et sont supprimés avec le compte — `core/services/account_deletion_service.py` doit les emporter.
- Le refus de la permission système est un état normal : l'app reste pleinement utilisable, sans relance insistante.

## Cadrage AGENTS.md, « Nothing is deployed yet »

Pas de double chemin d'envoi, pas de mode dégradé conservé, pas de file « au cas où ». Le chemin retenu par le README est le seul implémenté.

## Notes pour l'owner (pas des ACs)

- **Ceci n'est pas une OTA.** `expo-notifications` est une dépendance native : le fingerprint bouge et la livraison exige un **build EAS sur les deux plateformes**. Palier gratuit : 15 builds iOS par mois.
- La réception réelle sur un téléphone ne peut pas être un critère d'acceptation : elle demande un build et un déploiement, tous deux postérieurs à l'agent. C'est ta vérification.
- Les credentials à téléverser sont énumérés dans le README de task-368.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le chemin de livraison implémenté est celui désigné sous Owner Validation dans docs/research/task-368-push-delivery/README.md, et les notes d'implémentation citent l'option retenue telle qu'elle y est nommée
- [ ] #2 workers/digest/scheduler.py produit un message de notification pour le daily comme il le fait déjà pour le weekly
- [ ] #3 Une planification invoque le worker toutes les 15 minutes, ou selon le mécanisme désigné par le README, et terraform validate passe
- [ ] #4 La file de notification est créée par Terraform dans chaque environnement et la variable correspondante est renseignée, terraform validate passe
- [ ] #5 Un consommateur lit la file et remet la notification au fournisseur retenu, le chemin de code étant complet et câblé de bout en bout
- [ ] #6 Le daily part à 18h30 et le weekly le lundi à 9h30, heure locale de l'utilisateur issue du fuseau stocké par task-367, vérifiable en simulant plusieurs fuseaux contre les enregistrements DynamoDB -dev
- [ ] #7 Aucune notification n'est produite pour une période sans média, ni pour un compte dont le fuseau est inconnu, ni pour un compte dont digest_enabled, daily_digest_enabled ou weekly_digest_enabled le désactive
- [ ] #8 Une seule notification est émise par période et par utilisateur malgré le balayage répété : l'envoi est marqué et un second passage dans la même période ne réémet rien, vérifiable sur -dev
- [ ] #9 L'application demande la permission de notification, enregistre son token et ouvre le Digest correspondant à l'ouverture d'une notification, un refus de permission laissant l'app pleinement utilisable
- [ ] #10 Aucun token ni aucune donnée identifiante n'apparaît dans les logs, et la suppression de compte de account_deletion_service.py emporte les tokens de l'utilisateur
- [ ] #11 ruff et mypy passent sur media_summarizer/, npx tsc --noEmit et ESLint passent sur les fichiers mobile modifiés
<!-- AC:END -->
