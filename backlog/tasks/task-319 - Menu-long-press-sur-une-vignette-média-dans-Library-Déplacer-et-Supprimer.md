---
id: task-319
title: 'Menu long-press sur une vignette média dans Library : Déplacer et Supprimer'
status: Done
assignee: []
created_date: '2026-08-24 16:09'
updated_date: '2026-08-25 12:58'
labels:
  - mobile
  - ui
  - library
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Dans l'onglet **Library**, un média ne peut aujourd'hui être ni déplacé ni supprimé depuis la liste : la seule façon de changer sa collection est d'ouvrir le détail (`mobile/app/media/[id].tsx:394`, qui pousse `/media/collection?...`), et il n'existe **aucune** UI de suppression d'un média — `MediaService` (`mobile/src/services/mediaService.ts`) n'expose même pas d'appel `DELETE`, alors que le backend l'implémente depuis longtemps.

Les deux surfaces concernées affichent la même notion de vignette média mais deux composants différents :

1. **« All media »** — `LibraryState` dans `mobile/app/(tabs)/search.tsx` (~ligne 556), `FlatList` `testID="library-media-list"`, qui rend `MediaListCard` (`mobile/src/components/MediaListCard.tsx`).
2. **L'intérieur d'une collection** — `mobile/app/media/collections/[id].tsx` (~ligne 241), dont les lignes média sont rendues par le composant local `SourceRow` (~ligne 502), volontairement plus compact que `MediaListCard`.

Côté backend, tout est déjà en place et déployé :

- **Déplacer** : `PATCH /api/media/:id` avec `{ folder_id }`, déjà encapsulé par `OrganizationService.setMediaCollection()`. L'écran sélecteur de collection existe aussi (`mobile/app/media/collection.tsx`) : il accepte les params `mediaItemId` / `currentCollectionId`, sait créer une collection à la volée, et appelle lui-même `setMediaCollection` dans son `handleSave`. Le passer par `folder_id: null` correspond à « Unsorted ».
- **Supprimer** : `DELETE /api/media/:media_item_id` (`media_summarizer/api/endpoints/media.py:1661`). Suppression logique immédiate sur toutes les surfaces de lecture puis purge définitive après la fenêtre de grâce (`media_deletion_service`, `docs/DATA_RETENTION.md`). L'endpoint est **idempotent** : re-supprimer renvoie 200 avec le `purge_at` d'origine, jamais 404.

## Objectif

Rendre la gestion d'un média accessible depuis sa vignette dans Library : un **appui long** sur la vignette — qu'elle soit dans « All media » ou dans une collection — ouvre un modal proposant **Déplacer** et **Supprimer**, et les deux actions sont fonctionnelles de bout en bout (déplacement effectif vers la collection choisie, y compris une collection créée dans la foulée ; suppression effective du média).

## Périmètre

- Un composant modal partagé par les deux surfaces (le pattern maison est `mobile/src/components/AddSourceSheet.tsx` : `Modal` RN natif, insets, overlay tapable pour fermer — le reprendre plutôt qu'introduire une librairie de bottom sheet).
- Le modal identifie le média sur lequel l'appui long a eu lieu (titre visible dans l'en-tête, pour lever toute ambiguïté sur la cible d'une suppression).
- **Déplacer** réutilise le sélecteur de collection existant `/media/collection` plutôt que de réimplémenter un arbre de collections. Au retour, la liste appelante doit refléter le nouvel état (dans « All media » le média reste présent, dans une collection il disparaît s'il en est sorti).
- **Supprimer** : confirmation destructive obligatoire avant l'appel (le pattern maison est `Alert.alert` avec un bouton `style: "destructive"`, cf. `mobile/app/(tabs)/account.tsx:121`), puis appel `DELETE`, puis disparition du média de la liste. Pas d'undo : la fenêtre de grâce backend n'est pas exposée à l'UI dans cette tâche.
- Ajout de la méthode de suppression manquante sur `MediaService`.
- Toutes les nouvelles chaînes passent par `t()` et sont ajoutées aux **11 catalogues** de `mobile/src/i18n/` (`tsc` échoue sur une clé manquante, cf. le type `Catalog` dans `runtime.ts`).

## Hors périmètre

- Les vignettes de **résultats de recherche** (`SearchResultsState` dans `search.tsx`) et les tuiles de **Home** : `MediaListCard` est partagé avec les résultats de recherche depuis task-317, donc le handler d'appui long doit être une **prop optionnelle** que seules les surfaces Library fournissent — pas un comportement câblé en dur dans le composant.
- La sélection multiple / le mode batch.
- Le renommage, le retag, ou toute autre action que Déplacer et Supprimer.
- Toute évolution backend : les deux endpoints existent et suffisent.

## Contraintes

- L'appui simple doit continuer d'ouvrir le détail du média, sur les deux surfaces. L'appui long ne doit pas déclencher la navigation, et ne doit pas entrer en conflit avec le scroll ni avec le pull-to-refresh de `library-media-list`.
- `keyboardShouldPersistTaps="handled"` et `keyboardDismissMode` restent inchangés sur `library-media-list` (task-318), et les `testID` existants (`library-media-list`, `library-media-card`) ne changent pas.
- Un échec réseau sur l'une des deux actions doit laisser la liste dans un état cohérent et le dire à l'utilisateur ; il ne doit jamais faire disparaître un média qui existe toujours.
- `cd mobile && npm run lint && npm run typecheck` doivent rester clean.
- Pas de tests automatisés sauf demande explicite (règle projet) ; la validation qui compte est le run manuel de l'owner.

## Notes à l'owner

- **VÉRIF VISUELLE / E2E** — à faire sur simulateur iOS et émulateur Android, non vérifiable depuis le worktree : durée et ressenti de l'appui long, apparition du modal, absence de navigation parasite vers le détail, et le cycle complet « appui long → Déplacer → choisir/créer une collection → retour » puis « appui long → Supprimer → confirmer → le média a disparu de Library et de la collection ».
- La suppression est **irréversible passé la fenêtre de grâce** décrite dans `docs/DATA_RETENTION.md` : tester sur `-dev` avec un média jetable, pas sur l'article persistant « Commonplace book » dont dépendent d'autres flows.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Un appui long sur une vignette média de la liste "All media" (LibraryState dans mobile/app/(tabs)/search.tsx) ouvre un modal d'actions identifiant le média visé (son titre y est visible)
- [ ] #2 Un appui long sur une ligne média à l'intérieur d'une collection (SourceRow dans mobile/app/media/collections/[id].tsx) ouvre le même modal d'actions
- [ ] #3 Le modal propose exactement deux actions, Déplacer et Supprimer, plus un moyen de fermer sans rien faire (bouton d'annulation et/ou tap sur l'overlay)
- [ ] #4 Le handler d'appui long est une prop optionnelle de MediaListCard : les vignettes de résultats de recherche (SearchResultsState), qui partagent ce composant, n'ouvrent pas le modal
- [ ] #5 L'appui simple continue d'ouvrir le détail du média sur les deux surfaces, et l'appui long n'y navigue pas
- [ ] #6 Déplacer ouvre le sélecteur de collection existant /media/collection avec le mediaItemId et la collection courante du média, sans réimplémenter d'arbre de collections
- [ ] #7 Choisir une collection existante, choisir "Unsorted", ou créer une collection à la volée dans ce sélecteur déplace effectivement le média (PATCH /api/media/:id avec folder_id)
- [ ] #8 Au retour du déplacement, la liste appelante reflète le nouvel état : le média disparaît de l'écran de collection s'il en a été sorti, et reste présent dans "All media"
- [ ] #9 Supprimer demande une confirmation destructive explicite avant tout appel réseau, et l'annuler ne supprime rien
- [ ] #10 La confirmation acceptée déclenche DELETE /api/media/:media_item_id via une méthode de suppression ajoutée à MediaService, et le média disparaît de la liste sans rechargement manuel de l'écran
- [ ] #11 Un échec réseau sur le déplacement ou la suppression affiche un message à l'utilisateur et ne retire pas le média de la liste
- [ ] #12 Toutes les nouvelles chaînes passent par t() et sont présentes dans les 11 catalogues de mobile/src/i18n/ (typecheck clean sur le type Catalog)
- [ ] #13 Les testID library-media-list et library-media-card, ainsi que keyboardShouldPersistTaps / keyboardDismissMode de library-media-list, sont inchangés
- [ ] #14 Le pull-to-refresh de library-media-list et le scroll des deux listes restent fonctionnels, sans conflit avec le geste d'appui long
- [ ] #15 cd mobile && npm run lint && npm run typecheck sont clean
<!-- AC:END -->
