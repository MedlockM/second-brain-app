---
id: task-378
title: >-
  Démarrer le traitement du média dès la sélection de l’app dans le partage
  système
status: To Do
assignee: []
created_date: '2026-09-07 21:47'
updated_date: '2026-09-07 21:50'
labels:
  - mobile
  - ux
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aujourd’hui, lorsqu’un utilisateur partage un média depuis une application tierce vers notre app, le traitement attend son appui sur « Enregistrer » dans le modal de sauvegarde. Le parcours actuel confirme ce déclenchement dans mobile/app/share-confirmation.tsx.

Faire démarrer le traitement dès que l’utilisateur choisit notre app dans la feuille de partage système : dès réception du contenu exploitable et validation de la session, sans attendre une interaction dans le modal. Objectif : utiliser le temps passé dans le modal pour avancer le traitement et réduire l’attente avant disponibilité du média.

Périmètre : partage entrant depuis une app tierce sur iOS et Android, pour les types de contenu déjà pris en charge. Conserver la possibilité de choisir le dossier pendant que le traitement avance. Le bouton « Enregistrer » confirme la conservation du média et finalise les choix du modal sans relancer l’ingestion. Le parcours d’ajout manuel depuis notre app n’est pas visé par cette demande.

Décision produit : si l’utilisateur clique sur la croix au lieu de cliquer sur « Enregistrer », supprimer le média créé par ce partage, que son traitement soit encore en cours ou déjà terminé. Il ne doit plus apparaître dans la bibliothèque ni dans la recherche. Gérer également une fermeture pendant la soumission initiale, avant réception de l’identifiant du média : une réponse tardive ou la fin du traitement ne doit pas laisser ni faire réapparaître le média annulé. La suppression cible uniquement la sauvegarde de ce partage, sans supprimer les autres sauvegardes du même contenu. Réutiliser la sémantique de suppression canonique existante. La fin du traitement ne vaut pas confirmation d’enregistrement et ne doit pas fermer automatiquement le modal avant le choix de l’utilisateur. Rendre visible un échec de suppression et permettre de réessayer, sans présenter l’annulation comme réussie.

Préserver les contrôles de session, de validité du contenu et de consommation existants. Réutiliser les contrats canoniques existants ; aucune décision de fournisseur ni benchmark nécessaire.

Validation manuelle par le propriétaire après intégration et disponibilité d’un build : partager depuis une app tierce, rester dans le modal sans appuyer sur « Enregistrer » et constater que le traitement a commencé, sur iOS et Android. Vérifier ensuite la suppression via la croix pendant le traitement et après sa fin, ainsi que la conservation via « Enregistrer ». Cette vérification ne constitue pas une condition de clôture dans le worktree.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Le parcours de partage externe iOS et Android déclenche automatiquement l’ingestion dès réception d’un contenu exploitable et validation de la session, sans dépendre du bouton « Enregistrer ».
- [ ] #2 Ce déclenchement couvre les types de contenu déjà acceptés depuis les apps tierces, y compris le démarrage du transfert nécessaire pour les fichiers.
- [ ] #3 Le modal permet de choisir le dossier pendant le traitement et applique ce choix au même média ; « Enregistrer » confirme sa conservation sans créer une seconde sauvegarde ni relancer le traitement.
- [ ] #4 La gestion du partage protège une même réception contre les soumissions multiples liées au cycle de vie de l’écran ou au retour d’authentification, tout en permettant un nouveau partage volontaire.
- [ ] #5 Les états de démarrage, de progression et d’échec sont représentés dans le parcours ; la fin du traitement ne ferme pas automatiquement le modal avant le choix de l’utilisateur.
- [ ] #6 Les contrôles existants de session, de contenu et de consommation restent câblés avant la soumission ; un partage en attente d’authentification reprend automatiquement après connexion.

- [ ] #7 La croix supprime la sauvegarde créée par ce partage, en cours de traitement comme déjà traitée, selon la suppression canonique existante ; elle disparaît de la bibliothèque et de la recherche sans affecter les autres sauvegardes du même contenu.
- [ ] #8 Le parcours d’annulation prend en charge une fermeture avant réception de l’identifiant du média ; une réponse tardive ou la fin du traitement ne conserve ni ne fait réapparaître la sauvegarde annulée.
- [ ] #9 Un échec de suppression est signalé avec une possibilité de réessayer ; l’interface ne présente pas l’annulation comme réussie tant que la suppression a échoué.
<!-- AC:END -->
