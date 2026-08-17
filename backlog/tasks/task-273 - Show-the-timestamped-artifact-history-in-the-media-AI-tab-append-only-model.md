---
id: task-273
title: Show the timestamped artifact history in the media AI tab (append-only model)
status: To Do
assignee: []
created_date: '2026-08-17 20:13'
labels:
  - mobile
  - ui
  - ai
dependencies:
  - task-270
  - task-271
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Objectif

Décision de l'owner (2026-08-17) : l'historique horodaté des artefacts ne concerne pas que les collections — **un média a lui aussi la liste de ses artefacts passés**, avec leur date de génération, comme dans `mobile-design-mockups/notebooklm-reference/collection-ai-generated-list.png`. Le comportement actuel (« un artefact par type, écrasé à la régénération ») disparaît.

Cette tâche est la **contrepartie mobile** du passage du scope média à l'append-only livré par task-270. Elle est séparée de task-271 pour une raison d'ordonnancement : task-271 (le découpage en onglets Reader/AI) ne dépend d'aucun backend et peut être faite tout de suite, tandis que cet affichage a besoin des routes de task-270.

## Ce que la tâche doit produire

1. Dans l'onglet **« AI »** de `mobile/app/media/[id].tsx`, sous les tuiles de génération : la liste des artefacts déjà produits pour ce média, **triés du plus récent au plus ancien**, chacun avec l'icône de son type, son titre et sa date de génération en temps relatif. Contrairement à l'onglet AI d'une collection, il n'y a pas de « N sources » à afficher — un média est une source unique.
2. Plusieurs entrées du même type coexistent sans être dédupliquées, masquées ni marquées comme périmées.
3. L'état vide (aucun artefact généré) est rendu explicitement.
4. L'appel passe par `mobile/src/services/artifactService.ts` (étendu, pas dupliqué) sur les routes livrées par task-270, typé dans `mobile/src/types/`.
5. **Le retrait de l'ancienne hypothèse côté mobile** : la logique qui suppose un artefact unique par type — l'état dérivé de `artifact_statuses` dans `[id].tsx`, et tout ce qui en découle dans le polling — est remplacée par ce que task-270 expose. Rien n'est conservé en repli.
6. Cohérence avec l'onglet AI d'une collection (task-272) : la ligne d'historique doit être **le même composant**, avec la métadonnée « N sources » rendue optionnelle. Si task-272 a déjà landé, réutiliser son composant ; sinon, écrire celui-ci dans `mobile/src/components/` de façon à ce que task-272 puisse l'importer.

## À vérifier avant de coder

- Le champ `Decision` de `docs/research/task-269-collection-artifact-aggregation/README.md` et les Implementation Notes de task-270 : c'est là que se trouvent la forme des routes, le contenu du snapshot, et ce qui a remplacé la projection `artifact_statuses` de `GET /api/media/{id}`.
- L'écran `mobile/app/artifacts/[artifactId].tsx` : il affiche un artefact ouvert et suppose lui aussi l'unicité par type par endroits. Vérifier ce qui casse quand deux artefacts du même type existent.
- L'existence d'un formateur de temps relatif dans `mobile/src/` avant d'en ajouter un, et surtout avant d'ajouter une dépendance npm pour ça.

## Note à l'owner — hors AC

- La validation visuelle sur dev build iOS et Android vous revient.
- Conséquence assumée de l'append-only : régénérer un résumé sur un média n'écrase plus l'ancien, la liste s'allonge. Si vous voulez pouvoir supprimer une entrée à la main, c'est une tâche à part — rien dans le screenshot NotebookLM ne l'indique, donc ce n'est pas prévu ici.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 L'onglet « AI » de `mobile/app/media/[id].tsx` affiche sous les tuiles de génération la liste des artefacts déjà produits pour ce média, triés du plus récent au plus ancien, chacun avec l'icône de son type, son titre et sa date de génération en temps relatif ; un tap ouvre l'artefact
- [ ] #2 Plusieurs artefacts du même type coexistent dans la liste sans être dédupliqués, masqués ni marqués comme périmés
- [ ] #3 L'état vide (aucun artefact généré) et l'état d'une génération en vol sont tous deux rendus explicitement
- [ ] #4 La ligne d'historique est un composant partagé de `mobile/src/components/`, avec la métadonnée « N sources » optionnelle, utilisable tel quel par l'onglet AI d'une collection (task-272)
- [ ] #5 Le listing passe par `mobile/src/services/artifactService.ts` étendu (pas de nouveau client HTTP) sur les routes livrées par task-270, avec des types déclarés dans `mobile/src/types/`
- [ ] #6 Plus aucun code mobile ne suppose un artefact unique par type et par média : l'état dérivé de `artifact_statuses` et le polling de `mobile/app/media/[id].tsx` sont alignés sur ce qu'expose task-270, sans code de repli conservé
- [ ] #7 `mobile/app/artifacts/[artifactId].tsx` reste correct lorsque deux artefacts du même type existent pour un même média ; les endroits qui supposaient l'unicité sont corrigés ou listés dans les Implementation Notes s'ils sortent du périmètre
- [ ] #8 Aucune valeur de couleur, d'espacement ou de typographie en dur n'est introduite : les nouveaux composants lisent `mobile/src/constants/theme.ts`
- [ ] #9 `npx tsc --noEmit` et l'ESLint du repo passent sur `mobile/` sans nouvelle erreur ni nouveau warning
- [ ] #10 Les Implementation Notes consignent les libellés visibles et `testID` ajoutés ou modifiés, avec les flows de `mobile/.maestro/*.yaml` que cela casse, sans modifier ces flows
- [ ] #11 Aucune dépendance npm n'est ajoutée sans justification écrite dans les Implementation Notes, avec mention explicite si elle impose un nouveau build natif
<!-- AC:END -->
