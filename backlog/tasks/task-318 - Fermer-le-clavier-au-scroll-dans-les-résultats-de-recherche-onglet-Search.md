---
id: task-318
title: Fermer le clavier au scroll dans les résultats de recherche (onglet Search)
status: Done
assignee: []
created_date: '2026-08-23 19:27'
updated_date: '2026-08-24 12:00'
labels:
  - mobile
  - ui
  - search
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Sur l'onglet Search (`mobile/app/(tabs)/search.tsx`), une fois une requête tapée et le clavier affiché, faire défiler la liste de résultats ne ferme pas le clavier aujourd'hui. Le `FlatList` `testID="search-results-list"` de `SearchResultsState` (autour de la ligne 724) définit `keyboardShouldPersistTaps="handled"` mais pas `keyboardDismissMode` : React Native retombe donc sur le défaut `"none"`, et le clavier reste ouvert pendant le scroll. L'utilisateur doit taper sur la touche recherche (loupe bleue) du clavier pour le fermer avant de pouvoir balayer confortablement toute la liste de résultats.

Le même défaut existe sur le `FlatList` `testID="library-media-list"` de `LibraryState` (état "All media" affiché quand aucune requête n'est encore tapée, autour de la ligne 540) : le clavier peut déjà être ouvert à ce moment-là (barre de recherche tapée mais rien saisi), et le même geste de scroll ne le ferme pas non plus.

## Objectif

Faire en sorte qu'un scroll démarré sur l'une ou l'autre de ces deux listes ferme automatiquement le clavier (par exemple via la prop `keyboardDismissMode` de `FlatList`), pour que l'utilisateur puisse consulter les résultats par simple balayage, sans étape manuelle de fermeture du clavier au préalable.

## Contraintes

- `keyboardShouldPersistTaps="handled"` doit rester en l'état sur les deux listes : les taps sur une carte doivent continuer de fonctionner directement, sans qu'un premier tap serve uniquement à fermer le clavier.
- Ne pas casser le geste de pull-to-refresh existant sur `library-media-list` (`RefreshControl`).
- Choisir le mode de fermeture (`"on-drag"` vs `"interactive"`, éventuellement différencié iOS/Android) et documenter le choix et le pourquoi dans les Implementation Notes.
- `cd mobile && npm run lint && npm run typecheck` doivent rester clean.

## Notes à l'owner

- VÉRIF VISUELLE — le ressenti du geste de fermeture (immédiat vs suivant le doigt) ne se juge pas en lint/typecheck. À tester sur simulateur iOS et Android, clavier ouvert, sur les deux états (liste "All media" et liste de résultats après frappe).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Le FlatList search-results-list (SearchResultsState) ferme le clavier dès que l'utilisateur commence à faire glisser la liste, sans nécessiter un appui sur la touche recherche du clavier
- [x] #2 Le FlatList library-media-list (LibraryState) a le même comportement de fermeture du clavier au scroll, pour rester cohérent entre les deux états de l'onglet Search
- [x] #3 keyboardShouldPersistTaps="handled" reste inchangé sur les deux listes et les taps sur une carte de résultat/média continuent de fonctionner sans tap préalable pour fermer le clavier
- [x] #4 Le pull-to-refresh de library-media-list reste fonctionnel
- [x] #5 Les testID search-results-list et library-media-list restent inchangés
- [x] #6 Les Implementation Notes documentent le mode de fermeture retenu (on-drag, interactive, ou différencié par plateforme) et pourquoi
- [x] #7 cd mobile && npm run lint && npm run typecheck sont clean
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Le mode retenu : `on-drag`, identique sur les deux plateformes (AC #6)

`keyboardDismissMode="on-drag"`, posé sur les deux `FlatList` via une constante partagée `KEYBOARD_DISMISS_MODE` — les deux listes sont les deux moitiés du même onglet, et le geste doit y être le même.

**Pourquoi pas `interactive`** (le clavier qui suit le doigt, geste iOS natif) : React Native ne l'implémente que sur iOS. Sur Android il se comporte exactement comme `none`, c'est-à-dire comme le défaut que cette tâche corrige. Le choisir aurait donc laissé Android avec le bug d'origine, sur le geste qui *est* l'usage principal de cet écran. Un `Platform.OS === "ios" ? "interactive" : "on-drag"` aurait couvert les deux, mais au prix d'un ressenti différent d'une plateforme à l'autre sur le geste central de l'écran — un coût non justifié ici.

**Deuxième raison, propre à `library-media-list`** : cette liste porte un `RefreshControl`. Avec `on-drag`, le clavier part au premier mouvement et le geste appartient ensuite entièrement au pull-to-refresh. `interactive` aurait passé un glissement vers le bas à *remonter* le clavier — précisément le geste du pull-to-refresh, donc deux interprétations concurrentes du même mouvement.

**Ce que la fermeture ne coûte pas** : la barre de recherche est une pilule flottante en overlay, qui reste visible pendant tout le scroll. Un tap la ramène avec son clavier ; rien n'est perdu à la fermer.

## Ce qui n'a pas bougé

- `keyboardShouldPersistTaps="handled"` est inchangé sur les deux listes (AC #3). C'est la prop qui décide du sort d'un *tap*, `keyboardDismissMode` celui d'un *drag* : elles ne se recouvrent pas, et un tap sur une carte continue d'ouvrir l'élément directement, sans premier tap consommé par la fermeture du clavier.
- Le `RefreshControl` de `library-media-list` (AC #4) et les deux `testID` (AC #5) sont intacts.

## Vérifications

- `npm run typecheck` clean ; `npm run lint` 0 erreur, 2 warnings préexistants sans rapport (`digest.tsx` `CARD_WIDTH` inutilisé, `purchaseService.ts` `any`) — AC #7.
- `grep` : `keyboardDismissMode` présent sur les deux listes, `keyboardShouldPersistTaps="handled"` toujours sur les deux, les deux `testID` inchangés.

## Non vérifiable depuis le worktree

Le ressenti du geste, qui est la note owner de la description : à tester sur simulateur iOS et émulateur Android, clavier ouvert, sur les deux états de l'onglet (liste « All media » sans requête, puis liste de résultats après frappe).
<!-- SECTION:NOTES:END -->
