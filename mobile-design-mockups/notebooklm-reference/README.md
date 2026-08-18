# Référence NotebookLM

Screenshots de référence déposés par l'owner pour le chantier de refonte **task-263**. Ce fichier est le document que suivent les implémenteurs : pour chaque screenshot, l'écran visé, ce qui doit être repris, et ce qui ne doit surtout pas l'être.

Ce README est incomplet par construction : il ne couvre que les écrans pour lesquels l'owner a déposé une référence. Les autres écrans du périmètre de task-263 restent à documenter avant son déverrouillage.

## `collection-sources-tab.png` — onglet « Sources » d'un notebook

- **Écran visé** : `mobile/app/media/collections/[id].tsx` (détail d'une collection). **Pas** `mobile/app/media/collection.tsx`, qui est le modal de sélection de collection.
- **Écart avec l'écran actuel** : l'écran liste aujourd'hui les sous-collections et les médias avec une présentation riche (`MediaListCard` : vignette, métadonnées, statut). NotebookLM réduit chaque source à une **icône + un titre tronqué sur une ligne**, sans métadonnée secondaire, et place la liste sous un onglet.
- **À reprendre** : la structure en onglets intra-écran ; la densité et le dépouillement de la liste ; le titre de section au-dessus de la liste.
- **À ne pas reprendre** : la palette sombre, les icônes Google, le bouton d'ajout flottant (traité séparément par task-264), l'onglet « Chat » — l'app n'a pas de chat.
- **Tâche** : task-272.

## `collection-studio-tab.png` — onglet « Studio » d'un notebook

- **Écran visé** : le même écran, second onglet ; et par extension l'onglet « AI » de `mobile/app/media/[id].tsx` (task-271).
- **Écart avec l'écran actuel** : les artefacts IA sont aujourd'hui proposés uniquement au niveau d'**un** média, dans une section dépliante (« AI Artifacts ») qui charge l'écran de détail. Rien n'existe au niveau d'une collection, ni côté UI ni côté backend.
- **À reprendre** : le titre de section « Générer » ; la pile de grandes pastilles pleine largeur, une par type d'artefact, icône à gauche et libellé.
- **À ne pas reprendre** : la palette sombre et les couleurs par pastille de NotebookLM ; ses types d'artefacts propres (résumé audio, résumé vidéo, présentation, infographie, rapports). Le périmètre reste les **5 types existants** : `summary_short`, `summary_detailed`, `notes`, `flashcards`, `quiz`.
- **Tâches** : task-272 (collection), task-271 (média). Le backend d'agrégation manquant est traité par task-269 (benchmark) puis task-270 (implémentation).

## `collection-ai-generated-list.png` — bas de l'onglet « Studio »

- **Écran visé** : le même onglet, sous les pastilles de génération.
- **Ce que le screenshot établit** : les artefacts produits restent affichés, chacun avec l'icône de son type, son titre, le **nombre de sources** sur lequel il a été généré et sa **date de génération en temps relatif** (« 10 sources • Il y a 11 j »). Deux entrées peuvent coexister pour des types différents, et rien n'indique qu'une entrée soit périmée.
- **Décision de l'owner qui en découle (2026-08-17)** : **pas d'invalidation**. Un artefact est un résultat immuable et horodaté, pas une projection à maintenir. Ajouter ou retirer un média d'une collection ne périme rien et ne régénère rien ; l'utilisateur régénère s'il le veut, et l'ancien artefact reste dans la liste. Le « N sources » est ce qui rend l'entrée honnête quand la collection a bougé depuis.
- **À reprendre** : la ligne icône + titre + métadonnée secondaire « N sources • temps relatif », et le tri du plus récent au plus ancien.
- **À ne pas reprendre** : les types propres à NotebookLM visibles sur la capture (infographie, rapports, mindmap).
- **Tâches** : task-272 (affichage), task-269 puis task-270 (stockage append-only et snapshot).

## `quiz-question-by-question.png` — détail d'un artefact Quiz

- **Écran visé** : `mobile/app/artifacts/[artifactId].tsx`, uniquement lorsque l'artefact est un Quiz.
- **Écart avec l'écran actuel avant task-282** : toutes les questions étaient empilées dans le même flux vertical. La référence montre au contraire une seule question, sa progression, son feedback et une action explicite pour avancer.
- **À reprendre** : la hiérarchie « progression → question → réponses → explication → action suivante » ; le compteur de position et la barre proportionnelle ; la distinction visuelle entre la mauvaise réponse choisie et la bonne réponse ; le bouton « Continue » après réponse.
- **À ne pas reprendre** : la palette sombre, le chrome « Study material », les icônes et menus propres à NotebookLM, le badge de difficulté « MEDIUM », ainsi que toute logique de score ou donnée absente du contrat Quiz.
- **Tâche** : task-282.

## Décisions de nommage de l'owner (2026-08-17)

- L'onglet qui porte le transcript d'un média s'appelle **« Reader »**.
- L'onglet de génération s'appelle **« AI »** (et non « Studio »).
- L'onglet de liste d'une collection s'appelle **« Sources »**.

## Maquettes existantes périmées par cette refonte

Ne pas les supprimer : ce sont les documents de design de l'owner, leur sort lui revient.

- `mobile-design-mockups/media_detail_ai_artifacts_dropdown/` — la liste déroulante qu'elle décrit disparaît (task-271).
- `mobile-design-mockups/media_detail_ai_artifacts_expanded/` — même raison : l'état « déplié » n'existe plus, les artefacts vivent dans un onglet.
