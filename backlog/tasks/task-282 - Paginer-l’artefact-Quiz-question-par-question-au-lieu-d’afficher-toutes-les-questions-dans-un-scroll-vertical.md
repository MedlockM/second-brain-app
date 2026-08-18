---
id: task-282
title: >-
  Paginer l’artefact Quiz question par question au lieu d’afficher toutes les
  questions dans un scroll vertical
status: Done
assignee:
  - '@Codex'
created_date: '2026-08-18 00:17'
updated_date: '2026-08-18 01:44'
labels:
  - mobile
  - ui
  - design
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Objectif

Améliorer l’interface mobile de l’artefact **Quiz** : aujourd’hui, toutes les questions sont rendues à la suite dans le même `ScrollView`, ce qui oblige l’utilisateur à faire défiler verticalement l’écran pour trouver et répondre aux questions suivantes.

La cible est une expérience **une question à la fois**, avec une progression explicite et une action pour passer à la suite, dans l’esprit de la capture fournie par l’owner :

- fichier source fourni : `539538D8-4FCB-4BDB-AF24-9FD378C948E6.png` (actuellement dans `~/Téléchargements/`) ;
- compteur « Question N / total » ;
- barre de progression proportionnelle ;
- une seule carte de question visible ;
- feedback immédiat après la réponse : choix erroné, bonne réponse et explication ;
- bouton explicite « Continue » pour afficher la question suivante.

Cette tâche est une déclinaison ciblée du rapprochement avec NotebookLM piloté par **task-263**, mais elle est dispatchable indépendamment : la référence visuelle et le comportement attendu sont suffisamment précis et il n’y a aucun choix technologique ou architectural ouvert.

## État actuel vérifié le 2026-08-18

Dans `mobile/app/artifacts/[artifactId].tsx` :

- l’écran de détail entier est un `ScrollView` ;
- `QuizBody` parcourt toutes les questions avec `questions.map(...)` ;
- chaque `QuizQuestionCard` porte son propre état `picked` et révèle immédiatement la bonne réponse et l’explication ;
- toutes les cartes restent donc empilées verticalement ;
- le contrat mobile contient déjà les données nécessaires : `question`, `options`, `correct_answer`, `explanation`.

Aucun changement backend ni changement du contrat `/api/artifacts/{artifact_id}/content` n’est nécessaire.

## Cible fonctionnelle

1. `QuizBody` pilote l’index de la question courante et ne rend qu’une seule question à la fois.
2. Le haut de la zone Quiz affiche la position courante et une barre de progression accessible.
3. Le choix d’une réponse conserve le comportement actuel : une seule réponse est possible, les choix sont ensuite verrouillés, la bonne réponse est indiquée même lorsque l’utilisateur s’est trompé, et l’explication apparaît.
4. Une action « Continue » n’est disponible qu’après avoir répondu. Elle remplace la question courante par la suivante et repositionne le contenu au début de la nouvelle question.
5. Sur la dernière question, l’action ne doit pas prétendre qu’une question suivante existe : utiliser un libellé terminal explicite (par exemple « Done ») qui laisse le feedback de la dernière question consultable et permet ensuite de quitter avec la navigation d’en-tête existante.
6. Le scroll vertical reste autorisé **à l’intérieur du contenu de la question courante** lorsque la question, ses options ou son explication dépassent la hauteur d’un petit écran. En revanche, aucune question suivante ne doit être atteignable par scroll : seule l’action de progression change de question.
7. Conserver l’en-tête, le hero de l’artefact, la navigation retour, les états loading/error/not-ready et le rendu des quatre autres types d’artefacts.

## Ce qui est repris — et ce qui ne l’est pas

À reprendre de la capture : la hiérarchie « progression → question → réponses → explication → action suivante » et le traitement visuel distinct d’une mauvaise réponse et de la bonne réponse.

À ne pas reprendre :

- la palette sombre de l’application de référence : utiliser exclusivement les tokens de `mobile/src/constants/theme.ts` ;
- le chrome propre à l’application source (« Study material », icônes système, menu) ;
- le badge de difficulté « MEDIUM », absent du contrat Quiz actuel ;
- toute nouvelle donnée, logique de score persisté ou modification backend.

## Vérification locale et périmètre

Aucun test automatisé n’est demandé. Vérifier localement TypeScript et ESLint selon les commandes déjà utilisées dans `mobile/`. Aucun flow Maestro actuel ne parcourt les questions d’un Quiz ; ne pas ajouter ni modifier de flow dans cette tâche, mais consigner dans les Implementation Notes les nouveaux libellés visibles, rôles d’accessibilité et éventuels `testID` pour la réactivation pilotée par task-254/task-172.

La capture devra être déposée sous un nom durable dans `mobile-design-mockups/notebooklm-reference/` et son mapping vers l’écran `mobile/app/artifacts/[artifactId].tsx` consigné dans le README de référence de task-263, afin que la spécification visuelle ne dépende pas du dossier Téléchargements de l’owner.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 La capture `539538D8-4FCB-4BDB-AF24-9FD378C948E6.png` est déposée sous un nom durable dans `mobile-design-mockups/notebooklm-reference/`, et le README de ce dossier la mappe vers l’artefact Quiz en précisant les éléments repris et exclus
- [x] #2 `QuizBody` ne rend qu’une seule question à la fois ; aucune question suivante n’est présente dans le flux vertical ou atteignable par scroll
- [x] #3 La position `Question N / total` et une barre de progression proportionnelle sont visibles pour chaque question et exposent une information d’accessibilité compréhensible
- [x] #4 Avant réponse, toutes les options de la question courante sont sélectionnables et l’action de progression n’est pas disponible ; après un premier choix, les options sont verrouillées
- [x] #5 Après réponse, la bonne option est toujours identifiable, l’option choisie incorrecte est distinguée le cas échéant, et l’explication de la question courante est affichée
- [x] #6 Après réponse, l’action « Continue » affiche la question suivante et repositionne son contenu au début ; la dernière question utilise une action terminale explicite qui ne suggère pas qu’une question supplémentaire existe
- [x] #7 Sur un petit écran, le contenu trop long de la seule question courante reste consultable verticalement sans rendre une autre question par scroll
- [x] #8 L’en-tête, le hero, la navigation retour, les états loading/error/not-ready et les rendus summary_short, summary_detailed, notes et flashcards de `mobile/app/artifacts/[artifactId].tsx` restent inchangés fonctionnellement
- [x] #9 Toutes les nouvelles couleurs, espacements, typographies, rayons et tailles de cible tactile utilisent `mobile/src/constants/theme.ts` ; aucune valeur visuelle en dur ni dépendance npm n’est ajoutée
- [x] #10 `npx tsc --noEmit` et l’ESLint du repo passent sur `mobile/` sans nouvelle erreur ni nouveau warning ; aucun test automatisé ni fichier `mobile/.maestro/*.yaml` n’est ajouté ou modifié
- [x] #11 Les Implementation Notes consignent les libellés visibles, rôles d’accessibilité et éventuels `testID` introduits pour le parcours Quiz, comme matière pour la réactivation Maestro de task-254/task-172
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Inspecter la capture owner et l'écran Quiz actuel, puis copier la référence sous un nom durable dans `mobile-design-mockups/notebooklm-reference/` et documenter précisément son mapping/repris/exclus dans le README.
2. Refactorer uniquement `QuizBody`/`QuizQuestionCard` pour piloter une question courante, une réponse verrouillée et un état terminal, sans modifier les contrats ni les quatre autres rendus d'artefacts.
3. Ajouter avec les seuls tokens du thème le compteur, la barre de progression accessible, les états visuels correct/incorrect/explication et l'action `Continue`/terminale ; remonter le scroll au début à chaque changement de question.
4. Auditer les libellés, rôles d'accessibilité et `testID`, puis exécuter TypeScript et l'ESLint mobile sans tests ni modification Maestro.
5. Vérifier le diff et les secrets, documenter/cocher les critères, passer la tâche Done et commiter uniquement task-282 en conservant hors commit les changements concurrents task-283.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Dispatch automatique autorisé par le `/goal` actif après remise à zéro du contexte. Les tâches antérieures de priorité haute sont owner-only, bloquées par des prérequis externes ou explicitement `dispatchable: false`; task-282 est indépendante et dispatchable. Les modifications non commités de task-283 dans `media_artifact.py`, `artifact_service.py` et son fichier Backlog seront préservées hors de ce commit.

## Implémentation

- Le Quiz ne monte plus qu'une seule question. `QuizBody` possède l'index courant, la réponse sélectionnée et l'état terminal ; changer de question remplace la carte et remonte le `ScrollView` au début du corps d'artefact.
- La progression visible `Question N / total` est accompagnée d'une barre proportionnelle avec rôle `progressbar` et valeur accessible.
- Avant réponse, chaque option est un bouton sélectionnable. Après le premier choix, toutes les options sont désactivées ; la bonne réponse reçoit le traitement primaire et un check, tandis qu'un choix erroné reçoit le traitement d'erreur et une croix. L'explication reste visible.
- `Continue` n'apparaît qu'après une réponse. Sur la dernière question, l'action devient `Done`; son activation garde le feedback affiché et montre `Quiz complete`, la navigation retour d'en-tête restant disponible.
- Le `ScrollView` extérieur est conservé, donc une question ou explication longue reste consultable sur petit écran sans rendre la question suivante.
- La capture owner a été copiée bit-à-bit vers `mobile-design-mockups/notebooklm-reference/quiz-question-by-question.png` et son mapping, ses reprises et ses exclusions sont documentés dans le README de référence.

## Surface d'automatisation et accessibilité

- Libellés visibles : `Question N / total`, `EXPLANATION`, `Continue`, `Done`, `Quiz complete`.
- Rôles : `progressbar` pour la progression ; `button` pour chaque option et l'action `Continue`/`Done` ; `text` avec live region polie pour la confirmation terminale.
- Test IDs : `quiz-progress`, `quiz-option-<label>`, `quiz-continue-button`, `quiz-complete`.
- Les options exposent aussi leurs états accessibles `selected` et `disabled`, ainsi que le résultat correct/incorrect dans leur libellé après réponse.

## Vérifications

- `npx tsc --noEmit` dans `mobile/` : succès.
- `npx eslint 'app/artifacts/[artifactId].tsx' --max-warnings=0` : succès, aucun avertissement sur le fichier modifié.
- `npm run lint` dans `mobile/` : succès, 0 erreur ; les 8 avertissements affichés sont tous préexistants dans d'autres fichiers.
- `git diff --check` ciblé : succès.
- Aucun fichier Maestro, manifeste de dépendances, contrat ou backend n'est modifié par task-282. Aucun test automatisé n'a été ajouté ou exécuté, conformément au périmètre.
- Contrôle du diff anti-secrets : aucune donnée d'authentification ou identité de compte ajoutée.
<!-- SECTION:NOTES:END -->
