---
id: task-315
title: 'Renommer les onglets mobile : Inbox -> Home, Library -> Search'
status: Done
assignee: []
created_date: '2026-08-23 00:30'
updated_date: '2026-08-23 19:30'
labels:
  - mobile
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Le tab navigator principal de l'app mobile (`mobile/app/(tabs)/_layout.tsx`) affiche actuellement le premier onglet sous le label "Inbox" et le troisième sous "Library". Ces labels doivent devenir respectivement "Home" et "Search".

Le fichier `search.tsx` porte déjà volontairement ce nom de fichier/testID depuis task-306 (ne pas le renommer à nouveau, seul le label affiché change ici). Vérifier si un renommage de fichier équivalent est nécessaire pour l'onglet "Inbox" -> "Home", ou si seul le label change.

Vérifier aussi les éventuelles chaînes de traduction/i18n (mobile/src/i18n/, en cours d'ajout dans task-313) qui référencent ces labels, ainsi que tout testID ou texte de test Maestro qui s'appuierait sur "Inbox" ou "Library" comme libellé affiché (rappel : Maestro est legacy, ne pas se laisser contraindre par ces flows, juste vérifier qu'ils ne cassent pas silencieusement autre chose).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Le premier onglet du tab navigator affiche le label "Home" au lieu de "Inbox"
- [x] #2 L'onglet précédemment labellisé "Library" affiche le label "Search"
- [x] #3 Les autres labels d'onglets (Digest, Account) restent inchangés
- [x] #4 Le testID du screen search.tsx n'est pas renommé (reste conforme à task-306)
- [x] #5 Aucune référence résiduelle au libellé affiché "Inbox" ou "Library" ne subsiste dans le code des onglets ou les chaînes i18n associées
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Ce qui a changé

Les libellés d'onglets ne sont plus des littéraux depuis task-313 : ils vivent dans les onze catalogues. Le renommage porte donc sur les catalogues, pas sur l'écran.

- **`tabs.home`** : la valeur passe de « Inbox » à « Home » dans les onze langues.
- **`tabs.library` est renommée `tabs.search`**, valeur « Search ». La clé est renommée en même temps que la valeur : la garder aurait laissé le nom de la clé comme dernière trace du libellé remplacé, ce que l'AC #5 vise explicitement (« aucune référence résiduelle […] dans les chaînes i18n associées »).

Traductions retenues : Accueil/Recherche (fr), Inicio/Buscar (es), Start/Suche (de), Home/Cerca (it), Início/Pesquisa (pt), Start/Zoeken (nl), ホーム/検索 (ja), 主页/搜索 (zh), الرئيسية/بحث (ar), होम/खोज (hi).

## Aucun fichier renommé

La description demandait de vérifier si l'onglet « Inbox » → « Home » appelait un renommage de fichier. Non, pour la même raison que `search.tsx` n'en avait pas eu à task-306 : le nom de fichier est une route Expo Router, et la changer casserait chaque `router.push("/(tabs)/inbox")` du code pour un gain nul. `inbox.tsx` reste `inbox.tsx`, `search.tsx` reste `search.tsx`, et `search-tab-button` reste son testID (AC #4).

## Deux commentaires corrigés

Le docstring du layout annonçait « (Inbox, Library, Digest, Account) », et un commentaire de bloc justifiait le libellé « Library » choisi par task-306 (« labelled for the content and not for one of the two ways to reach it »). Les deux contredisaient le code après ce changement. Ils disent maintenant que les deux libellés nomment l'action — aller à l'accueil, chercher — plutôt que le contenu de l'écran.

## Hors périmètre, à connaître

D'autres chaînes i18n contiennent encore les mots « inbox » et « library » dans leur **corps** : `home.loading` (« Loading your inbox… »), `home.loadFailed`, `search.emptyLibrary` (« Your library is empty »), `addSource.title` (« Add to your inbox »), `search.placeholder` (« Search your library… »). Ce sont des phrases sur la boîte de réception et sur la bibliothèque en tant que contenus, pas des libellés d'onglets : l'AC #5 vise « le code des onglets ou les chaînes i18n associées », et elles n'en font pas partie. Elles restent cohérentes en l'état — mais si l'intention est de renommer aussi les *concepts* et non seulement les onglets, c'est une tâche distincte, et elle toucherait les onze catalogues.

## Maestro

Cinq flows (`02_share_intake`, `03_inbox_visibility`, `04_media_detail_progression` ×2, `05_artifact_trigger_action`) tapent sur `text: "Inbox"` pour revenir à l'accueil. Ils ne trouveront plus ce libellé. Conformément à la description — et au statut legacy de Maestro — ils n'ont pas été modifiés et n'ont pas contraint ce changement ; c'est signalé ici pour que la rupture ne surprenne pas au prochain run déclenché par l'owner.

## Vérifications

- `grep -rn "tabs.library" app/ src/` : zéro occurrence.
- Les libellés Digest et Account (`tabs.digest`, `account.title`) sont inchangés (AC #3).
- `npm run typecheck` clean ; `npm run lint` 0 erreur, 2 warnings préexistants sans rapport.
<!-- SECTION:NOTES:END -->
