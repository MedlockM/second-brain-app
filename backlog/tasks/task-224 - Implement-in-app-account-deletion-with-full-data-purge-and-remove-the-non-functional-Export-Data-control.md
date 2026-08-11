---
id: task-224
title: >-
  Implement in-app account deletion with full data purge and remove the
  non-functional Export Data control
status: To Do
assignee: []
created_date: '2026-08-05 17:54'
updated_date: '2026-08-11 16:12'
labels:
  - feature
  - compliance
  - mobile
  - api
  - release
dependencies:
  - task-240
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Deux manques bloquent la soumission stores et la conformité :

1. **Aucune suppression de compte in-app.** L'App Store guideline **5.1.1(v)** impose que toute app permettant la création d'un compte permette sa suppression **depuis l'app**. C'est un motif de rejet automatique. C'est aussi le droit à l'effacement (RGPD art. 17).
2. **Un bouton `Export Data` inactif** dans `mobile/app/(tabs)/account.tsx:107`. Un contrôle mort est en soi un risque de review.

## Décision owner (2026-08-05) — périmètre RGPD volontairement minimal

L'owner arbitre de n'implémenter que le strict nécessaire. **Le bouton `Export Data` est supprimé**, pas implémenté.

Précision juridique retenue : les données de l'app **sont** des données personnelles au sens de l'art. 4(1) — email, mot de passe, bibliothèque de médias sauvegardés, tags, dossiers, `reading_language` sont rattachés à un compte identifiable, même quand le contenu source est public. Les droits d'accès (art. 15) et de portabilité (art. 20) s'appliquent donc.

Mais ces deux droits **n'ont aucune obligation d'être self-service in-app** : un traitement manuel sur demande via l'email de support satisfait le règlement, dans le délai d'un mois. La politique de confidentialité doit alors documenter cette voie de recours. La suppression, elle, doit être in-app pour la raison Apple ci-dessus.

## Attention : `DELETE /api/v1/users/{user_id}` n'est pas la base

L'endpoint actuel est non authentifié (cf. task-222) **et** ne purge pas les données liées. Ne pas le réutiliser tel quel.

La purge doit couvrir l'ensemble des données rattachées au compte, à recenser à l'implémentation — au minimum : `users`, `auth_tokens`, `processing_jobs`, `media_artifacts`, tags, dossiers, `user_media_submissions`, `subscriptions`, `revenucat_events`, `media_watchers`, l'index Algolia, et les objets S3 (audio, documents, archives, flashcards).

## Dépendance task-219

La persistance durable de la media library (task-219) introduit une nouvelle source de vérité pour les médias sauvegardés. La purge doit la couvrir. Coordonner l'ordre de réalisation : si task-219 n'est pas encore mergée, la purge doit être écrite de façon à ce que l'ajout du nouveau store soit une extension évidente, et une note de suivi explicite doit être laissée.

Côté RevenueCat : la suppression du compte applicatif n'annule pas un abonnement store actif. Le comportement attendu (et son message à l'utilisateur) doit être décidé et documenté.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An authenticated account-deletion endpoint exists that derives the target account from the session and cannot delete another user's account
- [ ] #2 The Account screen exposes a discoverable account-deletion action with an explicit irreversible-action confirmation, satisfying App Store guideline 5.1.1(v)
- [ ] #3 Deletion purges every store holding data attached to the account, and the implementation notes list the full inventory of stores covered
- [ ] #4 S3 objects and Algolia records belonging to the account are removed, not just the DynamoDB rows
- [ ] #5 Durable media-library records introduced by task-219 are covered by the purge, or an explicit follow-up is recorded if task-219 lands later
- [ ] #6 Deletion is idempotent and a partial failure leaves no state where the account is unusable but its data is still discoverable
- [ ] #7 The behaviour toward an active RevenueCat subscription is decided, implemented, and surfaced to the user before confirmation
- [ ] #8 The non-functional Export Data control is removed from the Account screen along with any dead handler code
- [ ] #9 The privacy policy documents the manual support-email procedure for access and portability requests and the one-month response window
- [ ] #10 Deletion is verified end to end against AWS dev: the account can no longer authenticate and its media, artifacts, folders, tags and search records are gone
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
2026-08-11 — task-219 a été découpée (task-239 → 240 → 241 → 220 → 242 → 243). La dépendance passe de task-219 (archivée) à **task-240**, qui crée la table durable `user_media` — c'est le minimum nécessaire pour que la purge de compte ait quelque chose à purger. Pas besoin d'attendre le backfill ni le basculement des lectures.

Coordination avec task-243 (cycle de vie rétention/suppression/backup) : task-243 a un critère dédié à garantir que `user_media` est inclus dans le périmètre de purge de la suppression de compte. Si cette tâche-ci part la première, elle doit inclure `user_media` dans la purge, et task-243 se contentera de le vérifier. Éviter de dupliquer la logique de suppression entre les deux.
<!-- SECTION:NOTES:END -->
