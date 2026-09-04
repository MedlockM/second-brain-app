---
id: task-355
title: >-
  Rattraper une erreur JS de démarrage au lieu de laisser le process mourir, y
  compris sur un lancement sans UI
status: Done
assignee: []
created_date: '2026-09-04 15:20'
updated_date: '2026-09-04 15:57'
labels:
  - mobile
  - bug
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## D'où ça vient

Le rapport de crash joint à un feedback beta du 2026-09-04 (build `1.0.0 (6)`) documente un défaut distinct de celui que le feedback décrivait. Le feedback portait sur l'écran de chargement bloqué après un partage — corrigé par ailleurs, et sans rapport avec ce qui suit.

Ce que le rapport établit, en prose plutôt qu'en extraits (le log brut porte des chemins de conteneur et des identifiants d'incident, il reste hors du dépôt) :

- le process n'avait **aucun rôle d'interface** et était parenté par le lanceur du système : iOS avait préchauffé l'app en arrière-plan, sans que personne ne la lance ;
- il a vécu un peu plus d'une minute, puis s'est terminé par un abandon (`SIGABRT`) déclenché par le pont d'exceptions de React Native — la signature d'une **erreur JavaScript fatale**, pas d'un crash natif ;
- le démarrage de React Native est **inconditionnel** : il a lieu même quand le système n'a donné aucun rôle d'interface au process.

## Pourquoi c'est un défaut à soi seul

Il n'existe aujourd'hui **aucun garde-fou** : `grep -rn "ErrorBoundary|componentDidCatch|getDerivedStateFromError|ErrorUtils" mobile/app mobile/src` ne renvoie rien. Toute erreur JS pendant le bootstrap termine donc en abandon du process, au lieu d'un écran d'erreur.

Deux conséquences, l'une visible et l'autre non :

- sur un lancement normal, l'utilisateur voit l'app se fermer d'un coup, sans rien comprendre ;
- sur un lancement d'arrière-plan comme celui observé, il ne voit rien — mais le système enregistre le crash, et un historique de crashes en arrière-plan le conduit à préchauffer l'app moins souvent, ce qui dégrade la latence d'ouverture de la feuille de partage.

L'occurrence observée était de la seconde sorte, donc sans plainte utilisateur associée. C'est ce qui explique la priorité, pas l'absence de gravité : le même chemin est ouvert sur un lancement visible.

## Contrainte à connaître avant de commencer

**`mobile/ios` est gitignoré** — le projet est en génération native continue, le dossier natif est reconstruit à chaque prebuild. Une modification du démarrage natif éditée directement dans `mobile/ios` serait effacée au prochain build. Si le comportement natif doit changer, cela passe par un **config plugin**.

Le garde-fou côté JavaScript, lui, n'a pas cette contrainte. Deux niveaux à couvrir, car ils n'attrapent pas les mêmes erreurs : le rendu React (une frontière d'erreur ne voit que ce qui casse pendant un rendu) et **hors rendu** (une promesse rejetée ou un `throw` dans un effet asynchrone pendant le bootstrap passe à côté d'une frontière d'erreur).

Attention au point d'entrée : `mobile/app/+native-intent.tsx` réécrit les partages vers l'inbox, donc l'arbre est monté par plusieurs chemins. Le garde-fou doit couvrir tous les points d'entrée, pas la seule route `/` — c'est exactement le piège qui avait produit le bug de splash.

Cadrage (`AGENTS.md`, « Nothing is deployed yet ») : aucun repli de compatibilité à conserver.

## Note pour l'owner (pas un AC)

La validation réelle vous revient, après merge et push : laisser le téléphone préchauffer l'app (attendre, écran verrouillé), puis partager un média, et vérifier dans les diagnostics qu'aucun nouveau rapport de crash n'apparaît pour un lancement sans interface.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Une frontière d'erreur racine existe et **est montée** au point d'entrée unique de l'arbre (`mobile/app/_layout.tsx`), de sorte que tous les chemins d'entrée en héritent, y compris une ouverture par partage passant par `+native-intent` : `grep -rn 'ErrorBoundary' mobile/app mobile/src` montre le composant et son montage, pas seulement sa définition
- [ ] #2 Une erreur survenant **hors du cycle de rendu** pendant le bootstrap (promesse rejetée, effet asynchrone) est également rattrapée par un gestionnaire global installé au démarrage ; le chemin de code existe et est câblé
- [ ] #3 Le rattrapage affiche un état de repli lisible au lieu de laisser le process se terminer, et l'erreur reste consultable pour le diagnostic (pas d'échec silencieux)
- [ ] #4 Aucun fichier sous `mobile/ios` n'est modifié : si le démarrage natif doit changer, cela passe par un config plugin déclaré dans `app.config.ts`
- [ ] #5 `npm run typecheck` et `npm run lint` sont propres dans `mobile/`
<!-- AC:END -->
