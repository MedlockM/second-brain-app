---
id: task-273
title: Show the timestamped artifact history in the media AI tab (append-only model)
status: Done
assignee: []
created_date: '2026-08-17 20:13'
updated_date: '2026-08-18 00:13'
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
- [x] #1 L'onglet « AI » de `mobile/app/media/[id].tsx` affiche sous les tuiles de génération la liste des artefacts déjà produits pour ce média, triés du plus récent au plus ancien, chacun avec l'icône de son type, son titre et sa date de génération en temps relatif ; un tap ouvre l'artefact
- [x] #2 Plusieurs artefacts du même type coexistent dans la liste sans être dédupliqués, masqués ni marqués comme périmés
- [x] #3 L'état vide (aucun artefact généré) et l'état d'une génération en vol sont tous deux rendus explicitement
- [x] #4 La ligne d'historique est un composant partagé de `mobile/src/components/`, avec la métadonnée « N sources » optionnelle, utilisable tel quel par l'onglet AI d'une collection (task-272)
- [x] #5 Le listing passe par `mobile/src/services/artifactService.ts` étendu (pas de nouveau client HTTP) sur les routes livrées par task-270, avec des types déclarés dans `mobile/src/types/`
- [x] #6 Plus aucun code mobile ne suppose un artefact unique par type et par média : l'état dérivé de `artifact_statuses` et le polling de `mobile/app/media/[id].tsx` sont alignés sur ce qu'expose task-270, sans code de repli conservé
- [x] #7 `mobile/app/artifacts/[artifactId].tsx` reste correct lorsque deux artefacts du même type existent pour un même média ; les endroits qui supposaient l'unicité sont corrigés ou listés dans les Implementation Notes s'ils sortent du périmètre
- [x] #8 Aucune valeur de couleur, d'espacement ou de typographie en dur n'est introduite : les nouveaux composants lisent `mobile/src/constants/theme.ts`
- [x] #9 `npx tsc --noEmit` et l'ESLint du repo passent sur `mobile/` sans nouvelle erreur ni nouveau warning
- [x] #10 Les Implementation Notes consignent les libellés visibles et `testID` ajoutés ou modifiés, avec les flows de `mobile/.maestro/*.yaml` que cela casse, sans modifier ces flows
- [x] #11 Aucune dépendance npm n'est ajoutée sans justification écrite dans les Implementation Notes, avec mention explicite si elle impose un nouveau build natif
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Ce qui a été fait

L'onglet **AI** de `mobile/app/media/[id].tsx` liste sous les tuiles les artefacts déjà produits pour ce média, du plus récent au plus ancien, via le composant partagé `ArtifactHistoryRow` (livré par task-272, réutilisé tel quel) avec `showSourceCount={false}` — un média est une source unique, il n'y a pas de « N sources » à dire. Un tap ouvre `/artifacts/{id}`.

**Le sens de la dépendance est inversé, et c'est le cœur du changement.** L'écran ne tient plus « un état par type » d'où l'on déduirait une liste : il tient **l'historique**, et les tuiles en sont un `useMemo` (l'entrée la plus récente de chaque type, la liste revenant déjà triée). Il n'y a donc qu'une source de vérité derrière les tuiles et la liste, et plus aucun chemin qui suppose l'unicité par type :

- `setArtifactStates` n'existe plus ; `artifactStates` est dérivé.
- Le polling démarre et s'arrête d'après `hasArtifactInFlight`, calculé sur la liste, au lieu d'un drapeau tenu à la main.
- Une génération se contente de rafraîchir : la réponse du `POST` contient déjà l'entrée en `queued`, donc aucun état optimiste à réconcilier et l'entrée s'affiche avec son vrai id.

## Décisions d'implémentation à connaître

- **La boucle de retry silencieuse sur 409 est supprimée** (`ARTIFACT_TRANSLATION_RETRY_MAX_ATTEMPTS = 100`, les deux `useRef` de retry et `handleGenerateRef`). Elle rejouait le `POST` toutes les 3 s jusqu'à 100 fois en laissant la tuile sur « Queued » : l'utilisateur voyait un spinner de cinq minutes sans savoir pourquoi. Depuis task-270 le refus est typé et porte sa raison (`sources_not_ready` avec le nombre de sources en attente), donc il est affiché. Le remède reste un retap, qui est exactement ce que le README de task-269 décrit comme « réessayable tel quel ».
- **`describeArtifactRefusal` est extrait dans `src/lib/artifactRefusal.ts`** et partagé avec l'onglet AI de collection : les deux onglets reçoivent les mêmes refus, ils doivent les dire de la même façon. Le paramètre `scope` ne change que la formulation (« this collection » vs « this item »).
- **Les types de l'API artefacts passent dans `src/types/artifacts.ts`** (AC #5), le service les réexporte pour ne casser aucun import existant.
- **`bucketArtifactType` est supprimé** : il repliait le type legacy `summary` sur `summary_short` pour reconstruire une projection par type. L'historique porte le vrai type de chaque entrée, il n'y a plus rien à replier.

## Trois erreurs React Compiler apparues, et pourquoi

Après le refactor, ESLint a signalé **3 erreurs** sur ce fichier alors que `HEAD` en avait 0 (vérifié en stashant le diff et en relançant `eslint app/media/[id].tsx` : sortie vide, exit 0). Elles ne sont pas nouvelles dans le code — elles étaient **masquées** : l'ancienne ligne `handleGenerateRef.current = handleGenerate;` écrivait dans une ref pendant le rendu, ce qui faisait renoncer l'analyse sur le reste du composant. En la supprimant, le compilateur a pu voir la suite. Les trois sont corrigées plutôt que contournées :

1. `const toastOpacity = useRef(new Animated.Value(0)).current` → `useMemo(() => new Animated.Value(0), [])`. Une `Animated.Value` créée une fois et lue au rendu, c'est la définition de `useMemo`, pas d'une ref.
2. `pollForTranslation` se replanifiait en se référençant elle-même dans son propre `useCallback` (« Cannot access variable before it is declared ») → passage par `pollForTranslationRef`, tenue à jour dans un effet. La dépendance devenue inutile a été retirée de `fetchRawContent`.
3. L'effet du transcript appelait `setState` de façon synchrone **et** déclenchait `fetchRawContent()` depuis l'intérieur d'un updater — un effet de bord dans une fonction qui doit être pure, que React peut appeler deux fois en StrictMode, donc deux requêtes. Réécrit en corps async avec un `rawFetchStartedRef` : le fetch part une fois par état du média, se réarme quand le média repasse en traitement, et le bouton « Retry » de `TranscriptReader` appelle toujours `fetchRawContent` directement.

Résultat : `npx eslint app src --ext .ts,.tsx` → **0 erreur, 9 warnings**, la ligne de base exacte d'avant la tâche. `npx tsc --noEmit` exit 0.

## AC #7 — `app/artifacts/[artifactId].tsx`

L'écran résout par `artifact_id`, donc deux artefacts du même type ne se marchent pas dessus. Deux endroits supposaient en revanche l'ancien schéma de contenu et ont été corrigés dans le commit de task-272, dont c'était la conséquence directe : `summary_short.headline` → `title`, et `notable_quotes` passé de `string[]` à `[{text, source_ref}]` (sinon les deux sections se rendaient vides, `pickStringArray` jetant les objets). Le `source_ref` est affiché sous la citation.

## Libellés et testID (AC #10)

Ajoutés dans l'onglet AI du média : titre de section **« Generated »** ; état vide « Nothing generated yet. Pick a format above to create one. » ; `testID` `media-ai-history-empty` et `media-ai-refusal`. Les lignes d'historique portent `artifact-history-row-<artifactId>` (composant partagé). Les tuiles portent `artifact-tile-generate-<label>` / `artifact-tile-view-<label>`.

Modifiés : le badge **« Ready »** de la tuile a disparu (task-272), remplacé par le seul bouton « View » ; le bouton de génération s'appelle **« Regenerate »** quand une entrée existe déjà.

**Flows Maestro cassés — non modifiés, conformément à l'AC :**

| Flow | Ce qui casse | Cause |
|---|---|---|
| `05_artifact_trigger_action.yaml` l.100 | `extendedWaitUntil visible text: "Ready"` | le badge « Ready » n'existe plus ; l'ancre de remplacement est le bouton « View », ou `artifact-tile-view-Summary` |
| `05_artifact_trigger_action.yaml` l.68, 72, 130 | `tapOn text: "AI Artifacts"` | le dépliant a été retiré par **task-271**, pas par cette tâche ; l'ancre est maintenant l'onglet « AI » |
| `04_media_detail_progression.yaml` l.67, 72 | idem `"AI Artifacts"` | idem task-271 |
| `06_search.yaml` l.47 | `text: "AI Artifacts.*"` | idem task-271 |

Reste valide dans `05` : `text: "Queued|Generating|Ready"` (Queued et Generating sont toujours rendus par la tuile), `"Generate"`, `"View"`, et l'assertion `"SUMMARY"` de l'écran artefact. La réactivation de ces flows relève de task-254.

## AC #11 — dépendances

Aucune dépendance npm ajoutée. Le temps relatif passe par `src/lib/relativeTime.ts` (extrait par task-272 des copies privées de `MediaListCard` et de l'inbox) : six branches sur une différence de millisecondes, aucune librairie de dates, donc aucun build natif.

## Notes à l'owner — hors AC

- La validation visuelle iOS/Android vous revient. Le point à regarder : la liste sous les tuiles s'allonge à chaque régénération — c'est le comportement voulu, et c'est le changement le plus visible pour vous.
- **L'onglet AI dépend du déploiement de task-270.** Avant le push et les `apply` DynamoDB, la liste affichera son erreur de chargement : attendu, pas une régression de cet écran.
- Supprimer une entrée de l'historique à la main n'est pas prévu — rien dans la référence NotebookLM ne l'indique, et le README de task-269 le place explicitement hors périmètre. Si l'historique devient long à l'usage, c'est une tâche produit à ouvrir.
<!-- SECTION:NOTES:END -->
