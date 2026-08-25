---
id: task-324
title: >-
  Remplacer la carte Daily Digest du Home par un modal de triage « Unsorted
  review » : carrousel swipable, Discard / Deepen / Save
status: To Do
assignee: []
created_date: '2026-08-25 12:24'
labels:
  - mobile
  - ui
  - i18n
dependencies:
  - task-323
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Le Home (`mobile/app/(tabs)/inbox.tsx`) porte une carte « Daily Digest » qui ne fait que pousser vers l'onglet Digest — un raccourci vers un écran déjà atteignable d'un tap dans la tab bar. Pendant ce temps le dossier par défaut (`is_default`, affiché « Unsorted ») se remplit à chaque ingestion sans que rien ne pousse à le vider : tout média partagé sans collection y atterrit et y reste.

Cette tâche remplace ce raccourci par l'entrée d'une **file de triage** : un modal plein écran qui présente chaque média non trié, du plus ancien au plus récent, avec de quoi décider en quelques secondes, et trois issues — jeter, approfondir, ranger.

**L'onglet Digest et tout son backend restent en place.** Seule la carte du Home disparaît : `app/(tabs)/digest.tsx`, `digestService.ts`, `types/digest.ts`, l'entrée `tabs.digest` et toutes les clés `digest.*` restent vivants et référencés.

## L'écran à construire

Un modal plein écran (`presentation: "fullScreenModal"`), enregistré comme les autres écrans dans `mobile/app/_layout.tsx`. Deux écarts assumés à la convention du fichier, à commenter dans le code : le mode plein écran plutôt que le `modal` iOS, dont la carte encastrée casse un pager horizontal pleine largeur ; et le geste de dismiss désactivé, parce qu'un dismiss vertical sur un écran dont le métier est le swipe produit des sorties accidentelles — le bouton de fermeture est la sortie.

**La carte**, dans cet ordre : la vignette du média en petit en haut à gauche, le titre à côté d'elle, le nom de l'auteur sous le titre. Puis, sous ce bloc, le résumé court en prose fourni par task-323 sur l'item de bibliothèque. Le résumé va dans un `ScrollView` vertical imbriqué, pour qu'un texte long ne pousse jamais la barre d'action hors de l'écran.

**Les trois actions**, en bas :

- **Discard**, en bas à gauche : une croix avec le texte « Discard » dessous. Suppression **immédiate**, sans dialogue de confirmation (décision de l'owner : un tri se fait au rythme d'un tap), puis passage à la carte suivante.
- **Deepen**, à droite de Discard, **centré par rapport à la largeur de l'écran** : ouvre la page du média. Le média reste dans la file — Deepen est « je regarde », pas une décision. L'écran de détail se pousse par-dessus le modal et le retour retrouve la même carte, index et liste intacts.
- **Save**, à droite de Deepen : un gros icône de collection. **Son UI doit faire comprendre que c'est le bouton important de cet écran** : si l'utilisateur ne save pas et swipe, le média reste dans les Unsorted. Concrètement, c'est le seul contrôle rempli de l'écran, et le plus grand.

Pour centrer Deepen quelles que soient les largeurs de Discard et Save, encadre-le de deux gouttières `flex: 1` — un `space-between` ne centrerait pas.

**Le swipe** : gauche pour le précédent, droite pour le suivant, sur le principe d'un carrousel d'images Instagram — c'est-à-dire la pagination horizontale native. `mobile/app/(tabs)/digest.tsx` en est le seul exemple dans l'app et le patron à copier : `ScrollView horizontal pagingEnabled`, index dérivé de `Math.round(offsetX / SCREEN_WIDTH)`, chaque page en `width: SCREEN_WIDTH`.

**Les points de pagination**, au-dessus du bouton Deepen : une succession de petits points représentant les médias non triés dans l'ordre, celui du média courant changeant de couleur. **Sept points visibles au maximum à tout instant, avec un decrescendo de taille** comme sous le carrousel Instagram. Fais-en un composant réutilisable dans `mobile/src/components/`, en core React Native, couleurs alignées sur celles de `digest.tsx`.

Deux détails séparent « ça ressemble » de « c'est ça ». La fenêtre se calcule en clampant `activeIndex - 3` entre 0 et `count - 7` : ce clamp *est* le comportement Instagram. Et le decrescendo s'indexe sur la **troncature**, pas sur la position dans la fenêtre : on ne rétrécit un bord que s'il existe des médias au-delà, si bien qu'un point rétréci signifie exactement « il y en a d'autres de ce côté ».

**Fin de file** : un état de complétion remplace le pager, avec une action explicite de fermeture. Pas d'auto-dismiss : arracher l'écran au moment où la dernière carte est traitée vole la confirmation.

**Résumé absent** (génération en cours, échouée, ou média ingéré avant task-323) : un texte de repli discret et traduit, les trois actions restant actives. Pas de spinner, pas de polling.

## Le piège à ne pas manquer

Après un Discard ou un Save, l'item quitte la liste, la largeur de contenu du `ScrollView` perd une page, et React Native **conserve l'ancien `contentOffset`** : le pager se retrouve visuellement entre deux pages. **Chaque mutation de la liste doit donc se terminer par un ré-ancrage explicite** — un `scrollTo` non animé sur l'index suivant, dans un `requestAnimationFrame` après le `setState`. Retirer la carte courante fait glisser la suivante à sa place, il n'y a donc pas d'animation à jouer. À commenter : sans explication, ça se relit comme un bug.

Autre point : **la file est figée à l'ouverture**, chargée une fois au montage, sans `useFocusEffect`. Revenir de Deepen ne doit pas rebattre les index sous le doigt. Écart assumé à la convention de l'app, à commenter aussi.

## Le bouton du Home

Il remplace la carte Digest à la même place et **réutilise tout son bloc de styles**, renommé : même silhouette, même carte, même badge, même chevron. Ne redessine pas, renomme. Trois changements : l'icône, le libellé, la destination.

Le compteur est le `media_count` du dossier par défaut, déjà disponible via `buildCollectionTree` (`mobile/src/lib/collectionTree.ts`) sur les collections que `useHomeSections` charge déjà — zéro requête supplémentaire. Cible `is_default`, **jamais le libellé** (règle de task-297). À zéro, le bouton ne s'affiche pas du tout.

À supprimer dans le même mouvement : le composant de la carte digest, son handler, toute la plomberie `digestCount` — dont la branche `getDailyDigest()` du `Promise.allSettled` de `useHomeSections`, une requête réseau en moins à chaque chargement du Home — et les trois clés `home.digest*` des 11 catalogues.

## La sheet de sauvegarde

Décision de l'owner : Save ouvre un **bottom sheet intégré au modal**, pas un push vers l'écran sélecteur existant. Le patron est `mobile/src/components/AddSourceSheet.tsx` — un `<Modal transparent animationType="slide">` React Native, rendu par-dessus le modal de route sans imbrication de navigateur, ce qui est précisément ce qui rend ce choix possible. Reprends-en le scrim, les insets, et la ruse de déféremment sur `onDismiss` qui enchaîne « créer puis sélectionner » sur iOS.

Contenu : la liste **plate** des collections non-défaut en chemins fil d'Ariane — reprends la construction de chemins de `mobile/app/media/collection.tsx`. À plat parce que l'utilisateur répond « laquelle ? » en deux secondes, il ne navigue pas, et le chemin lève l'ambiguïté des noms de feuille dupliqués. Inclut la création en ligne puis sélection immédiate, sinon un utilisateur sans collection adaptée est bloqué. L'assignation passe par `OrganizationService.setMediaCollection` ; en succès le média quitte la file, en échec la sheet reste ouverte avec un message lisible.

## Chevauchement avec task-319, à ne pas « harmoniser »

task-319 ajoute un menu long-press Déplacer/Supprimer dans Library. Deux points de contact, sans dépendance dans un sens ni dans l'autre. **La méthode de suppression sur `MediaService`** n'existe pas encore et les deux tâches en ont besoin : si 319 est passée avant, réutilise-la telle quelle ; sinon ajoute-la ; jamais deux. Et **les deux surfaces divergent volontairement** — 319 réutilise l'écran `/media/collection` et exige une confirmation destructive, ici c'est une sheet et pas de confirmation. Deux décisions de l'owner pour deux contextes : ne les aligne pas.

## Contraintes

- **Aucune nouvelle dépendance.** L'app n'a ni `reanimated`, ni `gesture-handler`, ni `pager-view`, ni `FlashList`, ni lib de bottom sheet, et n'en aura pas ici.
- Design system `mobile/src/constants/theme.ts`, icônes Ionicons, pas de couleur en dur.
- La vignette réutilise les dimensions exportées par `MediaListCard` et sa politique de cache.
- Toutes les chaînes passent par `t()` et existent dans **les 11 catalogues** de `mobile/src/i18n/` : le type dérivé du catalogue anglais fait échouer `tsc` sur une clé manquante.
- `cd mobile && npm run lint && npm run typecheck` doivent rester propres.

## Hors périmètre

- Tout le backend : task-323 livre le type de résumé, sa génération et le tri croissant.
- L'onglet Digest, son service et ses écrans.
- Le mode multi-sélection, le renommage, le retag, la régénération du résumé.

## Notes à l'owner (non vérifiables par l'agent)

- **Les résumés n'apparaîtront qu'après le déploiement de task-323 et le passage de son backfill.** D'ici là l'écran est fonctionnel mais affiche partout le texte de repli — comportement attendu, pas un bug.
- **VÉRIFICATION VISUELLE / E2E**, sur simulateur iOS et émulateur Android : le ressenti du swipe et du snap, le decrescendo des points face aux captures de référence, le centrage de Deepen, la hiérarchie des trois boutons (Save doit sauter aux yeux), et le cycle « swipe, Save dans une collection créée à la volée, Discard, retour de Deepen » sans pager désaligné.
- La suppression est **irréversible passé la fenêtre de grâce** de `docs/DATA_RETENTION.md`, et aucun endpoint de restauration n'existe : l'UI ne promet aucun undo. Teste sur `-dev` avec des médias jetables, pas avec l'article persistant « Commonplace book » dont dépendent d'autres flows.
- `mobile/.maestro/03_inbox_visibility.yaml` assertera un libellé disparu. Les flows Maestro sont legacy et ne contraignent pas le code ; à mettre à jour ou pas, au choix.
- Ajout au cahier des charges initial, à valider ou retirer : un compteur « 3 / 12 » dans l'en-tête du modal. Les points plafonnant à sept ne peuvent pas dire la position réelle ; ce compteur porte l'information pour les lecteurs d'écran.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Un nouvel écran modal de triage existe sous `mobile/app/media/`, enregistré dans `mobile/app/_layout.tsx` en présentation plein écran, avec le geste de dismiss désactivé et une animation d'entrée par le bas
- [ ] #2 Le Home rend un bouton « Unsorted review » là où était la carte Daily Digest, qui pousse le nouvel écran, en réutilisant le bloc de styles de l'ancienne carte renommé plutôt qu'un nouveau design
- [ ] #3 Le compteur du bouton vient du `media_count` du dossier `is_default` obtenu via `buildCollectionTree` sur les collections déjà chargées par `useHomeSections`, sans requête supplémentaire, et le bouton ne s'affiche pas du tout quand ce compte est nul
- [ ] #4 Le composant de carte digest, son handler et toute la plomberie `digestCount` ont disparu d'`inbox.tsx` et d'`useHomeSections.ts`, branche `getDailyDigest()` comprise, et `grep -rn "digestCount" mobile/` ne renvoie rien
- [ ] #5 `app/(tabs)/digest.tsx`, `digestService.ts`, `types/digest.ts`, l'entrée `tabs.digest` et les clés `digest.*` sont toujours présents et référencés
- [ ] #6 Les trois clés `home.digest*` sont absentes des 11 catalogues i18n, et toutes les nouvelles clés sont présentes dans les 11
- [ ] #7 La file est chargée en une seule requête sur l'endpoint canonique des médias, filtrée sur le dossier par défaut et triée du plus ancien au plus récent via le paramètre de sens de tri livré par task-323, avec un re-filtrage client sur l'identifiant exact du dossier
- [ ] #8 La file est chargée une seule fois au montage : aucun rafraîchissement au retour de focus ne peut rebattre les index pendant que l'utilisateur trie
- [ ] #9 Chaque carte affiche, dans cet ordre, la vignette en petit en haut à gauche, le titre à côté d'elle, le nom de l'auteur sous le titre, puis le résumé en prose sous ce bloc dans un `ScrollView` vertical imbriqué
- [ ] #10 La vignette réutilise les dimensions exportées par `MediaListCard` avec sa politique de cache disque-mémoire, une clé de cache dérivée de l'identifiant et de la date de mise à jour, une clé de recyclage, et un repli glyphe sur erreur
- [ ] #11 Quand le résumé est absent, la carte affiche un texte de repli discret et traduit, et les trois actions restent actives
- [ ] #12 Le carrousel est un `ScrollView horizontal pagingEnabled` du core React Native, une page par média en largeur d'écran, index dérivé de l'offset de défilement
- [ ] #13 La barre d'action place Deepen au centre horizontal de l'écran grâce à deux gouttières `flex: 1`, Discard aligné à gauche dans la première et Save à droite dans la seconde
- [ ] #14 Discard est une croix avec le libellé « Discard » dessous, en bas à gauche ; Save porte un grand icône de collection et est le seul contrôle rempli de l'écran, avec la plus grande cible tactile des trois
- [ ] #15 Discard appelle immédiatement la suppression du média, sans dialogue de confirmation, puis retire la carte de la file
- [ ] #16 La méthode de suppression vit sur `MediaService` et émet `DELETE` sur l'endpoint média canonique : ajoutée ici si task-319 ne l'a pas déjà posée, réutilisée telle quelle sinon, jamais dupliquée
- [ ] #17 Deepen ouvre la page de détail du média et le retour retrouve la même carte avec la file et l'index intacts, le média restant dans la file
- [ ] #18 Save ouvre un bottom sheet rendu par-dessus le modal via un `Modal` transparent React Native, sur le patron d'`AddSourceSheet.tsx`, sans aucune librairie de bottom sheet ajoutée
- [ ] #19 Le sheet liste à plat les collections non-défaut sous forme de chemins fil d'Ariane, permet de créer une collection en ligne puis de la sélectionner immédiatement, et assigne via `OrganizationService.setMediaCollection`
- [ ] #20 Une assignation réussie ferme le sheet et retire le média de la file ; un échec laisse le sheet ouvert avec un message lisible et ne retire rien
- [ ] #21 Un composant de points de pagination réutilisable existe dans `mobile/src/components/`, n'utilise que des primitives du core React Native, et rend au plus sept points
- [ ] #22 La fenêtre de points est calculée en clampant `activeIndex - 3` entre 0 et `count - 7`, de sorte que le point actif reste centré au milieu de la liste et que la fenêtre s'épingle aux extrémités
- [ ] #23 Le decrescendo de taille est indexé sur la troncature et non sur la position dans la fenêtre : un point n'est rétréci que s'il existe des médias au-delà de ce côté, et le point actif garde toujours la taille de base
- [ ] #24 Les points rendent `null` pour une file vide, un seul point pour un unique média, et la hauteur du conteneur est fixe pour que la rangée ne tremble pas au changement de carte
- [ ] #25 Les points sont placés au-dessus du bouton Deepen et masqués de l'arbre d'accessibilité, l'information de position étant portée par un élément textuel de l'en-tête
- [ ] #26 Toute mutation de la file se termine par un ré-ancrage explicite du pager par `scrollTo` non animé sur l'index suivant, après la mise à jour d'état, avec un commentaire expliquant pourquoi
- [ ] #27 Quand la file est vide, un état de complétion remplace le carrousel et propose une action explicite de fermeture, sans fermeture automatique
- [ ] #28 Le type d'item de bibliothèque côté mobile porte le champ de résumé optionnel exposé par task-323, et l'énumération des types d'artefacts mobiles est inchangée
- [ ] #29 `grep -rn "reanimated\|gesture-handler\|pager-view\|FlashList\|bottom-sheet"` sur les fichiers ajoutés ou modifiés ne renvoie rien, et `mobile/package.json` n'a aucune dépendance ajoutée
- [ ] #30 `cd mobile && npm run lint && npm run typecheck` sont propres
<!-- AC:END -->
