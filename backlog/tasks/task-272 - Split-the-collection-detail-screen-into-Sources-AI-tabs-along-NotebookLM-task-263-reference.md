---
id: task-272
title: >-
  Split the collection detail screen into Sources / AI tabs along NotebookLM
  (task-263 reference)
status: To Do
assignee: []
created_date: '2026-08-17 19:43'
updated_date: '2026-08-17 20:03'
labels:
  - mobile
  - ui
  - design
dependencies:
  - task-270
  - task-271
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Objectif

Décision de l'owner (2026-08-17) : l'écran de détail d'une collection reprend l'organisation d'un notebook NotebookLM — une **liste simple de sources** dans un onglet, et la **génération d'artefacts IA sur toute la collection** dans un second onglet.

Références visuelles déposées par l'owner dans `mobile-design-mockups/notebooklm-reference/` :

- `collection-sources-tab.png` — onglet « Sources » : liste dépouillée, une ligne par source, **icône + titre tronqué sur une ligne**, aucune métadonnée secondaire, un titre de section « Sources » au-dessus, un bouton d'ajout flottant en bas.
- `collection-studio-tab.png` — onglet « Studio » : titre de section « Générer », puis une pile de grandes pastilles pleine largeur, une par type d'artefact, chacune avec son icône à gauche et son libellé.
- `collection-ai-generated-list.png` — **le bas du même onglet** : sous les pastilles de génération, la liste des artefacts déjà produits. Chaque ligne = icône du type + titre + une ligne secondaire « N sources • Il y a X j ». C'est un historique, pas un état courant.

Ce qui est repris : la structure de navigation (onglets intra-écran), la densité de la liste de sources, la forme « pile de grandes pastilles » de l'onglet de génération, et la liste horodatée des artefacts produits en dessous. Ce qui **n'est pas** repris : la palette sombre de NotebookLM, ses icônes, son onglet « Chat » (pas de chat dans l'app), et ses types d'artefacts propres (résumé audio, présentation, infographie, rapports) — le périmètre est celui des 5 types existants.

## Écran concerné — ne pas se tromper de fichier

- **Cible : `mobile/app/media/collections/[id].tsx`** (≈395 lignes) — le détail d'une collection : sous-collections + médias, `getCollectionMedia`, filtre sur `folder_id`.
- **Hors périmètre : `mobile/app/media/collection.tsx`** — malgré son nom, c'est le **modal de sélection** de collection (« Non trié », « My collections », bouton « Save »), utilisé pour déplacer un média. Ne pas y toucher.
- `mobile/app/media/collections/index.tsx` (la racine de l'explorateur) n'est pas dans le périmètre au-delà de la propagation de tokens.

## Ce que la tâche doit produire

1. **Deux onglets intra-écran** sur `collections/[id].tsx` : **« Sources »** (par défaut) et **« AI »**. Réutiliser le composant d'onglets partagé créé par task-271 — ne pas en écrire un second.
2. **Onglet Sources** : liste simple, une ligne par élément, icône + titre sur une ligne. Les sous-collections restent listées, avant les médias. Cette liste remplace la présentation actuelle des médias de la collection ; le composant `MediaListCard` riche n'est pas utilisé ici (il reste en place pour l'inbox et la recherche). Conserver la navigation existante : tap sur un média → `media/[id]`, tap sur une sous-collection → sa page.
3. **Onglet AI, partie haute — générer** : les 5 types d'artefacts (`summary_short`, `summary_detailed`, `notes`, `flashcards`, `quiz`) proposés **au scope collection**, en réutilisant la tuile d'artefact partagée extraite par task-271, disposée comme la pile de pastilles du screenshot Studio.
4. **Onglet AI, partie basse — l'historique** : sous les pastilles, la liste des artefacts déjà générés pour cette collection, **triés du plus récent au plus ancien**, chacun avec l'icône de son type, son titre, le **nombre de sources** de son snapshot et sa **date de génération en temps relatif** (« Il y a 11 j »). Un tap ouvre l'artefact. Plusieurs entrées du même type peuvent coexister : c'est un historique append-only, décidé par l'owner — ne rien dédupliquer, ne rien marquer comme périmé, ne pas masquer les anciennes entrées quand la composition de la collection a changé. Prévoir l'état vide (aucun artefact généré) et le fait qu'une génération en vol apparaisse dans cette liste ou au-dessus, selon ce que renvoie task-270.
5. **Un service mobile pour ces routes** dans `mobile/src/services/` (étendre `artifactService.ts` plutôt que de dupliquer le client HTTP), typé dans `mobile/src/types/`.
6. **Le traitement honnête des refus** décidés par task-270 : collection vide, transcripts pas encore prêts, plafond de médias dépassé. Chacun doit produire un message lisible dans l'onglet AI, pas un échec silencieux ni un spinner infini.

La forme exacte des routes, du polling, du snapshot (nombre de sources, horodatage) et des refus est celle livrée par **task-270** : lire ses Implementation Notes et le champ `Decision` de `docs/research/task-269-collection-artifact-aggregation/README.md` avant de coder l'appel.

## Décisions déjà tranchées (ne pas les rouvrir)

- Libellés d'onglets **« Sources »** et **« AI »**, en anglais comme le reste de l'UI ; **Sources** sélectionné par défaut.
- L'onglet AI d'une collection propose **les mêmes 5 types** que l'onglet AI d'un média. Aucun nouveau type.
- **Pas d'invalidation** : la liste d'artefacts est un historique horodaté. Un artefact généré sur 4 sources reste affiché tel quel quand la collection en compte 7 — c'est précisément ce que le « N sources » sert à dire.
- Aucune valeur de couleur, d'espacement ou de typographie en dur : tout vient de `mobile/src/constants/theme.ts` (« Amber Clarity »). La palette de NotebookLM n'est pas reprise.
- Pas de bouton d'ajout de source flottant dans le cadre de cette tâche : le point d'entrée d'ingestion est traité par task-264 (`AddSourceSheet`). Si task-264 a déjà landé au moment du dispatch, réutiliser son composant plutôt qu'en créer un.

## Note à l'owner — hors AC

- La validation visuelle sur dev build iOS et Android vous revient, et elle est ici plus importante que d'habitude : c'est le premier écran de l'app avec des onglets internes.
- Aucun flow Maestro ne couvre aujourd'hui l'écran collection (vérifié le 2026-08-17 : zéro occurrence de « collection » dans `mobile/.maestro/`). Cette tâche ne casse donc rien côté E2E, mais elle crée une surface non couverte à intégrer au plan de réactivation de task-254.
- Le temps relatif (« Il y a 11 j ») suppose un formateur de dates. Vérifier s'il en existe déjà un dans `mobile/src/` avant d'en ajouter un, et surtout avant d'ajouter une dépendance npm pour ça.
- Le mapping screenshot → écran est consigné dans `mobile-design-mockups/notebooklm-reference/README.md`, qui reste le document de référence du chantier task-263.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `mobile/app/media/collections/[id].tsx` rend deux onglets intra-écran « Sources » et « AI », avec « Sources » sélectionné par défaut, en important le composant d'onglets partagé livré par task-271 sans en créer un second
- [ ] #2 L'onglet « Sources » affiche une ligne par élément réduite à une icône et un titre tronqué sur une seule ligne, sous-collections listées avant les médias, conformément à `mobile-design-mockups/notebooklm-reference/collection-sources-tab.png`, et n'utilise pas `MediaListCard`
- [ ] #3 La navigation existante est préservée : un tap sur un média ouvre `media/[id]`, un tap sur une sous-collection ouvre sa page, et aucune cible de navigation morte ne subsiste
- [ ] #4 L'onglet « AI » propose les 5 types (`summary_short`, `summary_detailed`, `notes`, `flashcards`, `quiz`) au scope collection, disposés en pile de pastilles pleine largeur à la manière de `collection-studio-tab.png`, en réutilisant la tuile d'artefact partagée extraite par task-271
- [ ] #5 Sous les pastilles de génération, l'onglet « AI » liste les artefacts déjà générés pour la collection, triés du plus récent au plus ancien, chacun avec l'icône de son type, son titre, son nombre de sources et sa date de génération en temps relatif, conformément à `collection-ai-generated-list.png` ; un tap ouvre l'artefact
- [ ] #6 Plusieurs artefacts du même type coexistent dans la liste sans être dédupliqués, masqués ni marqués comme périmés lorsque la composition de la collection a changé depuis leur génération
- [ ] #7 L'état vide de l'historique (aucun artefact généré) et l'état d'une génération en vol sont tous deux rendus explicitement
- [ ] #8 La génération, le polling de statut, le listing de l'historique et l'ouverture d'un artefact passent par les routes livrées par task-270, appelées depuis `mobile/src/services/artifactService.ts` étendu (pas de nouveau client HTTP) et typées dans `mobile/src/types/`
- [ ] #9 Les refus renvoyés par le backend (collection vide, transcripts non prêts, plafond de médias dépassé) produisent chacun un message lisible dans l'onglet AI ; aucun cas ne laisse un spinner permanent ni un échec silencieux
- [ ] #10 `mobile/app/media/collection.tsx` (le modal de sélection de collection) n'est pas modifié
- [ ] #11 Aucune valeur de couleur, d'espacement ou de typographie en dur n'est introduite : l'écran et ses nouveaux sous-composants lisent `mobile/src/constants/theme.ts`

- [ ] #12 `npx tsc --noEmit` et l'ESLint du repo passent sur `mobile/` sans nouvelle erreur ni nouveau warning, et les règles react-hooks restent au niveau où task-227 les a laissées
- [ ] #13 Les Implementation Notes consignent les libellés visibles et les `testID` introduits sur l'écran collection, comme matière pour la réactivation Maestro prévue par task-254
- [ ] #14 Aucune dépendance npm n'est ajoutée sans justification écrite dans les Implementation Notes, avec mention explicite si elle impose un nouveau build natif
<!-- AC:END -->
