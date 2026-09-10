---
id: task-397
title: Auditer et corriger tous les messages d'erreur destinés aux utilisateurs
status: To Do
assignee: []
created_date: '2026-09-10 12:42'
labels:
  - mobile
  - backend
  - ux
  - i18n
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce qui est demandé

Passer **toute la codebase** en revue à la recherche des messages d'erreur destinés à l'utilisateur, et corriger tous ceux qui ne satisfont pas les deux règles ci-dessous. Ce n'est pas un correctif ponctuel : c'est un balayage exhaustif suivi des corrections.

Le public de l'application est composé de consommateurs non techniques. Un message d'erreur n'est pas un canal de diagnostic.

### Règle 1 — aucun détail technique dans un message utilisateur

Ni nom d'exception, ni code HTTP, ni trace, ni nom de fonction, de fichier, de module, de bucket ou de table, ni identifiant interne, ni message brut remonté d'une bibliothèque ou du système d'exploitation. Si l'information sert au diagnostic, elle va dans les logs, pas à l'écran.

Cas connu à traiter, à l'origine de cette tâche : le bloc `upload.diagnostics.title` / `upload.diagnostics.hint` (« Détails techniques », affiché dans `mobile/app/share-confirmation.tsx`) demande à l'utilisateur de recopier une ligne d'étape technique s'il signale le problème. Un beta testeur l'a signalé comme « beaucoup trop technique pour un user ». Il n'y a pas de raison de le conserver sous une autre forme : le rapport de bug embarque déjà le contexte nécessaire.

### Règle 2 — une erreur causée par l'utilisateur doit lui dire comment la corriger

Quand la cause est une action de l'utilisateur — identifiants incorrects, champ mal rempli, fichier d'un type non pris en charge, fichier trop volumineux, quota atteint — le message doit être assez explicite pour qu'il sache **quoi faire ensuite**, sans être technique pour autant. `error.invalidCredentials` (« E-mail ou mot de passe incorrect. Veuillez réessayer. ») et `upload.reject.tooLarge`, qui nomme la taille et la limite, sont les formes de référence à généraliser.

Inversement, une erreur qui ne vient pas de l'utilisateur ne doit pas lui suggérer une action qui ne changera rien. Le cas rencontré en beta est instructif : un fichier local illisible affichait « Vérifiez votre connexion », alors qu'aucun réseau n'était en jeu.

## La convention est déjà tranchée — l'appliquer, pas la redéfinir

**task-359 (Done)** a posé la forme et l'a justifiée par RFC 9457 et Google AIP-193 : le serveur émet un **code stable**, jamais une phrase ; `mobile/src/lib/getFriendlyErrorMessage.ts` mappe ce code vers une clé de catalogue, résolue à l'appel et non à l'import ; les 11 catalogues `mobile/src/i18n/*.ts` portent les textes. Toute correction passe par ce chemin. Un message écrit en dur dans un composant est en soi un défaut, même s'il est bien tourné.

Repères de volumétrie relevés à l'écriture, à confirmer par l'implémenteur et non à prendre pour un périmètre : 64 appels à `getFriendlyErrorMessage`, 22 `Alert.alert`, 3 endroits affichant directement un `.message` d'erreur. Le balayage couvre aussi les messages `user_message` côté `media_summarizer/` et les `detail` d'exceptions HTTP de l'API qui remontent jusqu'à l'écran.

## Confidentialité

Un message affiché devient une capture d'écran dans App Store Connect. Il ne doit donc jamais porter le nom d'un fichier de l'utilisateur — donc le titre d'une note —, une adresse e-mail, ni un identifiant de compte. La redaction des messages natifs a déjà été durcie dans `mobile/src/services/localFileTransfer.ts` ; vérifier qu'aucun autre chemin ne contourne ce durcissement.

## Cadrage

`AGENTS.md`, « Nothing is deployed yet » : un message fautif se remplace, il ne se double pas d'une variante conservée « au cas où ». Aucun repli sur l'ancienne formulation, aucune fenêtre de dépréciation.

## Notes au propriétaire (hors critères d'acceptation)

La vérification visuelle des écrans corrigés demande un build ou une OTA et t'appartient. Les textes des catalogues étant des chaînes JS, ils partent en OTA sans consommer de build TestFlight. L'inventaire produit par l'implémenteur te permettra de relire les reformulations sans ouvrir chaque écran.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Un inventaire exhaustif des messages d'erreur susceptibles d'être affichés à un utilisateur est produit dans un fichier du dépôt : emplacement, texte actuel, verdict au regard des deux règles, et correction appliquée le cas échéant.
- [ ] #2 Aucun message affiché à l'utilisateur ne comporte de détail technique : nom d'exception, code HTTP, trace, nom de fichier de code, de module ou de ressource d'infrastructure, identifiant interne, ou texte brut remonté d'une bibliothèque ou du système.
- [ ] #3 Le bloc « Détails techniques » de l'écran de confirmation de partage est supprimé, ses clés retirées des 11 catalogues i18n, et aucun équivalent ne subsiste ailleurs.
- [ ] #4 Tout message correspondant à une erreur causée par une action de l'utilisateur indique ce qu'il doit faire pour la corriger ; aucun message ne suggère une action sans effet sur la cause réelle.
- [ ] #5 Tout message corrigé passe par le chemin établi par task-359 — code stable, résolution par getFriendlyErrorMessage, texte en catalogue i18n — et aucun texte affiché n'est écrit en dur dans un composant.
- [ ] #6 Les 11 catalogues i18n restent complets et cohérents entre eux : aucune clé présente dans l'un et absente d'un autre.
- [ ] #7 Aucun message affiché ne peut porter le nom d'un fichier de l'utilisateur, une adresse e-mail ou un identifiant de compte.
- [ ] #8 ruff et mypy passent sans erreur sur les modules backend touchés, et le lint et le typage du projet mobile passent sans erreur.
<!-- AC:END -->
