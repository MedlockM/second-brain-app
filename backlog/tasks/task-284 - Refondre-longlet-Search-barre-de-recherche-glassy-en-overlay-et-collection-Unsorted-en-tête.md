---
id: task-284
title: >-
  Refondre l'onglet Search : barre de recherche glassy en overlay et collection
  Unsorted en tête
status: Done
assignee: []
created_date: '2026-08-18 03:18'
updated_date: '2026-08-18 03:41'
labels:
  - mobile
  - ui
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

L'écran concerné est `mobile/app/(tabs)/search.tsx`. Trois changements visuels demandés par l'owner, aucun travail backend.

## 1. Supprimer le gros titre "Search"

Le `<Text style={styles.title}>Search</Text>` en haut du header disparaît, ainsi que le style devenu mort. L'onglet reste identifié par son entrée de tab bar.

## 2. Barre de recherche en overlay, effet glassy

Référence visuelle : l'explorateur de fichiers iOS (screenshot owner `382646E5-4EBC-4134-B75F-744B6DE20ADA.png`) — une pilule translucide très arrondie, flottant au-dessus du contenu, laissant transparaître ce qui défile dessous avec un flou.

- La barre est **positionnée en absolu** au-dessus de la zone de contenu, plus dans le flux : la grille de collections et la liste de résultats défilent **sous** elle.
- Le flou vient de `expo-blur` (`BlurView`), **qui n'est pas encore une dépendance du projet** : l'ajouter avec `npx expo install expo-blur` depuis `mobile/` pour obtenir la version alignée sur le SDK Expo 55. Sur Android le flou natif est inégal — prévoir le repli documenté (teinte semi-opaque) plutôt qu'un rendu cassé.
- Le contenu doit garder un padding haut suffisant pour qu'au repos (scroll en haut) rien d'utile ne soit masqué par la barre.
- Le placeholder reste exactement `Search your library...` et l'input garde son `testID="search-input"` : `mobile/.maestro/06_search.yaml` s'appuie sur les deux.

## 3. Collection "Unsorted" au-dessus de la section Collections

Les médias enregistrés sans choix de collection sont **déjà** rangés côté backend dans le dossier par défaut (`folder_service` assigne le dossier `is_default` quand `folder_id` est `None`). Il n'y a donc rien à créer ni à migrer : ce dossier existe, il est simplement invisible dans l'onglet Search.

`buildCollectionTree` (`mobile/src/lib/collectionTree.ts`) exclut volontairement le dossier par défaut de `roots` et le retourne à part dans `defaultCollection` ; `search.tsx` ne consomme aujourd'hui que `roots`. Le pattern d'épinglage existe déjà dans `mobile/app/media/collections/index.tsx:113-116` — le reprendre plutôt que d'en inventer un second.

Libellé retenu par l'owner : **"Unsorted"** (l'UI mobile est en anglais ; le nom backend reste `Uncategorized`, seul l'affichage change). Aligner aussi `mobile/app/media/collections/index.tsx`, qui affiche encore "Uncategorized", pour ne pas donner deux noms au même dossier.

Un point de régression à traiter : aujourd'hui, quand l'utilisateur n'a créé aucune collection, `CollectionsState` rend l'empty state "No collections yet". Avec une tuile Unsorted, cet empty state ne doit plus masquer les médias non triés.

## Notes à l'owner

- VÉRIF VISUELLE — le rendu glassy ne se contrôle ni en lint ni en typecheck. À regarder sur simulateur iOS (flou réel, contraste du placeholder sur contenu clair et sombre) et sur Android (repli).
- Si le flou Android déçoit, dire si vous préférez une barre opaque sur cette plateforme.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Le titre "Search" n'apparaît plus dans mobile/app/(tabs)/search.tsx et le style associé devenu inutilisé est supprimé, pas laissé mort
- [x] #2 La barre de recherche est rendue en superposition (position absolue) au-dessus de la zone de contenu, et la grille de collections comme la liste de résultats défilent sous elle
- [x] #3 La barre utilise BlurView d'expo-blur pour l'effet glassy, avec un repli explicite sur Android, et expo-blur figure dans mobile/package.json à une version installée via expo install (SDK 55)
- [x] #4 Au repos, le premier élément du contenu n'est pas masqué par la barre : le décalage haut est appliqué au contenu, pas obtenu en réduisant la barre
- [x] #5 L'input conserve testID="search-input" et le placeholder "Search your library...", tous deux référencés par mobile/.maestro/06_search.yaml
- [x] #6 La grille Collections de l'onglet Search affiche en première position une tuile alimentée par defaultCollection de buildCollectionTree, libellée "Unsorted"
- [x] #7 Le tap sur la tuile Unsorted ouvre /media/collections/[id] avec l'id du dossier par défaut, comme n'importe quelle autre collection
- [x] #8 Le compteur de la tuile Unsorted est calculé par la même mécanique directCountById que les autres tuiles
- [x] #9 La tuile Unsorted reste affichée quand l'utilisateur n'a créé aucune autre collection : l'empty state "No collections yet" ne s'affiche plus à sa place
- [x] #10 mobile/app/media/collections/index.tsx affiche "Unsorted" et non plus "Uncategorized" pour ce même dossier
- [x] #11 npm run lint et npm run typecheck sont clean dans mobile/
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Ce qui a été fait

**1. Titre supprimé** — `<Text style={styles.title}>Search</Text>` et le style `title` retirés de `mobile/app/(tabs)/search.tsx`. Le wrapper `styles.header` (dont l'unique raison d'être était de contenir titre + barre dans le flux) disparaît aussi : la barre est maintenant un overlay, plus un enfant du flux.

**2. Barre en overlay glassy**
- `expo-blur@~55.0.17` installé via `npx expo install expo-blur` depuis `mobile/` (version résolue par le solveur SDK 55) → présent dans `mobile/package.json` et `package-lock.json`.
- La barre est rendue **après** la zone de contenu dans le JSX, dans un wrapper `styles.searchBarOverlay` en `position: "absolute"` (`top`/`left`/`right`, `zIndex: 10`, `pointerEvents="box-none"`). La grille de collections et la FlatList de résultats sont dans un `View flex: 1` qui occupe toute la hauteur : elles défilent donc sous la pilule.
- Composant `GlassSurface` : `BlurView` (`intensity={60}`, `tint="light"`) sur iOS ; sur Android, repli explicite sur un `View` teinté `rgba(252, 249, 246, 0.92)` (`styles.searchBarAndroidFallback`) — le flou natif Android est inégal selon le constructeur et se dégrade silencieusement quand le système désactive les animations.
- Forme : `BorderRadius.full`, hauteur `TouchTarget.minimum` (48), `overflow: "hidden"` pour que le flou soit clippé par le rayon. L'ombre `Shadows.soft` est portée par le wrapper, pas par la pilule (un `overflow: hidden` annulerait l'ombre).

**3. Décalage du contenu** — constantes en tête de fichier : `SEARCH_BAR_HEIGHT` (48) + `SEARCH_BAR_TOP` (8) + `Spacing.md` = `CONTENT_TOP_INSET` (72). Appliqué en `paddingTop` sur `resultsList`, `collectionsGridContent` et `emptyContainer`. La barre garde sa taille de cible tactile pleine.

**4. Contrat Maestro préservé** — `testID="search-input"` et le placeholder `Search your library...` sont inchangés, seul leur parent a bougé. `mobile/.maestro/06_search.yaml` n'a pas eu besoin d'être touché.

**5. Tuile Unsorted** — `search.tsx` stocke désormais `tree.defaultCollection` en plus de `tree.roots`, et `sortedCollections` épingle en tête `{ ...defaultCollection, name: DEFAULT_COLLECTION_LABEL }` — même pattern que `mobile/app/media/collections/index.tsx`. Le tap passe par le `handleOpenCollection` existant, donc `/media/collections/[id]` avec l'id réel du dossier par défaut. Comme la liste rendue contient toujours au moins cette tuile, l'empty state « No collections yet » ne peut plus masquer les médias non triés (il ne subsiste que pour le cas où le backend ne renvoie aucun dossier du tout).

**6. Libellé unifié** — constante `DEFAULT_COLLECTION_LABEL = "Unsorted"` exportée par `mobile/src/lib/collectionTree.ts`, consommée par les deux écrans. `mobile/app/media/collections/index.tsx` n'affiche plus « Uncategorized ». Le nom backend reste `Uncategorized` : aucune écriture, seul l'affichage change. Plus aucune occurrence de « Uncategorized » dans le code hors commentaires explicatifs.

## AC#8 — précision

Aucune tuile de la grille Search n'affiche de compteur visible (ni avant, ni après). L'AC est satisfaite au sens du chemin de données : `directCountById` est construit à partir de `media.folder_id` puis passé à `buildCollectionTree`, qui renseigne `directMediaCount` sur **tous** les nœuds, `defaultCollection` compris. Aucun compteur spécifique n'a été inventé pour Unsorted, ce qui aurait justement rompu l'homogénéité avec les autres tuiles.

## Vérifications

- `npm run lint` : 0 erreur. 8 warnings, tous préexistants et dans d'autres fichiers (`_layout.tsx`, `digest.tsx`, `paywall.tsx`, `purchaseService.ts`, `sharedContentService.ts`) — aucun dans les fichiers touchés.
- `npm run typecheck` : clean.

## Notes à l'owner

- **VÉRIF VISUELLE requise** — le rendu glassy ne se contrôle ni en lint ni en typecheck. À regarder sur simulateur iOS (flou réel, contraste du placeholder sur contenu clair et sombre) et sur Android (repli teinté). `intensity={60}` et l'opacité `0.92` du repli Android sont des points de départ à ajuster à l'œil.
- **Si le flou Android déçoit**, dire si vous préférez une barre franchement opaque sur cette plateforme : le repli est isolé dans `styles.searchBarAndroidFallback`, un seul token de couleur à changer.
- **`mobile/ios/` et `mobile/android/` sont gitignorés** : `expo-blur` est un module natif, il ne sera lié qu'au prochain `expo prebuild` local ou build EAS. Un rechargement JS seul sur un dev client existant ne suffira pas.

## Correctif post-vérif visuelle owner (screenshot 2026-08-18)

Deux constats sur le premier rendu device :

**1. Bug de positionnement corrigé.** La pilule s'affichait collée en haut de l'écran, par-dessus l'heure et les indicateurs réseau. Cause : le wrapper absolu était enfant du `SafeAreaView`, et Yoga ne décale pas un enfant `position: "absolute"` du padding de son parent — le `paddingTop` d'inset était donc ignoré pour l'overlay (mais bien appliqué au contenu, d'où le décalage correct de la grille). Correctif : la racine est un `View` neutre, le `SafeAreaView edges={["top"]}` n'enveloppe plus que la zone de contenu, et l'overlay est un frère positionné par `top: insets.top + SEARCH_BAR_TOP` via `useSafeAreaInsets()`. Plus de dépendance à la sémantique Yoga du padding sur les absolus.

**2. `Unimplemented component: <ViewManagerAdapter_ExpoBlur_ExpoBlurView>` — pas un bug de code.** C'est le message RN quand la vue native d'un module n'est pas dans le binaire. Le dev client sur lequel le screenshot a été pris a été construit avant l'ajout de `expo-blur`. Aucun rechargement JS ne le corrigera : il faut un nouveau build du dev client (`eas build --profile development --platform ios`). Le JS est correct, seul le binaire est en retard.
<!-- SECTION:NOTES:END -->
