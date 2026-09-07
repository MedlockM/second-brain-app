---
id: task-374
title: >-
  Afficher « Ranger dans un dossier » au lieu de « Non trié » sur le bouton de
  dossier du modal de partage
status: To Do
assignee: []
created_date: '2026-09-07 13:42'
labels:
  - mobile
  - ui
dependencies:
  - task-373
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Le constat

Quand un média arrive depuis une app tierce, le modal de confirmation (`mobile/app/share-confirmation.tsx`, composant `OrganizationControls`) affiche une ligne « dossier » avec l'icône `folder-open-outline` et un chevron. Tant que rien n'est choisi, cette ligne affiche **« Non trié »** :

```tsx
{selectedFolder?.path ?? t("collectionPicker.unsorted")}   // aujourd'hui ~l.775
```

« Non trié » est un **état**, pas une invitation : sur un bouton, il ne dit pas qu'on peut appuyer dessus pour ranger le média. Le libellé attendu est **« Ranger dans un dossier »**.

## Ce qu'on veut

Une **nouvelle clé i18n dédiée** dans la famille `share.*` (p. ex. `share.folderPlaceholder`), utilisée uniquement comme repli de cette ligne quand `selectedFolder` est `null`. Valeur française **exactement** « Ranger dans un dossier ».

**Pourquoi une nouvelle clé et pas une nouvelle valeur sur l'ancienne.** `collectionPicker.unsorted` (renommée par task-373) est partagée avec la carte sélectionnable en tête du sélecteur (`CollectionPickerView`, `showUnsorted`), où « Non trié » est le **nom du dossier par défaut** — task-373 acte explicitement que ce libellé-là ne bouge pas. Écraser la valeur renommerait le dossier par défaut partout ; il faut donc séparer les deux emplois.

## Périmètre exact

- Une seule ligne de rendu change, dans `OrganizationControls`. Ce composant est monté par les **huit** variantes de source du modal : l'édition unique couvre tous les partages, quelle que soit l'app d'origine.
- L'état « un dossier est choisi » ne change pas : la ligne continue d'afficher `selectedFolder.path`.
- L'icône, le chevron et l'`accessibilityLabel` de l'action (`share.chooseCollection`, renommée `share.chooseFolder` par task-373) restent tels quels : ce label annonce l'action, pas l'état.
- Le sélecteur (`app/media/collection.tsx` + `CollectionPickerView`, tous deux renommés en `folder`/`Folder` par task-373) n'est pas touché : sa carte « Non trié » reste une destination choisissable.

## Le cas « Non trié » choisi explicitement

Dans le sélecteur, choisir « Non trié » appelle `setSelectedFolder(null)` (`app/media/collection.tsx`, `handleSelect`) : le contexte de partage ne distingue pas « rien choisi » de « rangé nulle part volontairement ». Le bouton affichera donc « Ranger dans un dossier » dans les deux cas, et c'est le comportement retenu. **Ne pas ajouter d'état intermédiaire** dans `ShareIntentContext` pour mémoriser un « Non trié » explicite : personne ne l'a demandé, et le média part de toute façon sans dossier.

## Mécanique i18n

`TranslationKey = keyof typeof en` (`mobile/src/i18n/runtime.ts`) : la clé se déclare d'abord dans `en.ts`, puis `Catalog = Record<TranslationKey, string>` impose de la définir dans les **11 catalogues** (`en, fr, es, de, it, pt, nl, ja, zh, ar, hi`) — un catalogue oublié casse `npm run typecheck`. `pseudo.ts` ne contient aucun littéral, rien à y ajouter.

Le français est la copie de l'owner, verbatim. Les dix autres langues reprennent le mot « dossier » de leur langue d'après le tableau de task-373 (`folder`, `carpeta`, `Ordner`, `cartella`, `pasta`, `map`, `フォルダ`, `文件夹`, `مجلد`, `फ़ोल्डर`) et le registre déjà employé par le catalogue concerné, sans réinventer le verbe utilisé ailleurs dans le même fichier.

## Ordonnancement

- **Dépend de task-373** (renommage « Collection » → « Dossier » et alignement du code sur `folder`). Faire l'inverse ferait naître une clé au vocabulaire périmé que task-373 devrait renommer aussitôt, et son AC#1 — `grep -ri collection` muet sous `mobile/` — retomberait dessus.
- task-372 (suppression des tags) touche le **même composant** `OrganizationControls`, mais sa ligne « Tags », pas celle du dossier. Si elle est passée avant, il ne reste que la ligne dossier dans le composant ; le changement est le même.

## Note à l'owner (pas un AC)

Vérification visuelle à faire après merge, sur un build : partager une URL depuis Safari/Chrome et regarder le modal avant toute sélection. « Ranger dans un dossier » est nettement plus long que « Non trié » — la ligne est en `numberOfLines={1}`, donc l'allemand et le portugais sont les candidats à la troncature.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Dans `mobile/app/share-confirmation.tsx`, la ligne dossier de `OrganizationControls` n'utilise plus la clé du dossier par défaut du sélecteur (`folderPicker.unsorted` après task-373) comme repli : elle affiche une nouvelle clé dédiée de la famille `share.*` quand `selectedFolder` est `null`
- [ ] #2 La nouvelle clé vaut exactement « Ranger dans un dossier » dans `mobile/src/i18n/fr.ts`
- [ ] #3 La nouvelle clé est définie dans les 11 catalogues de `mobile/src/i18n/` — `en.ts` compris, puisque `TranslationKey = keyof typeof en` — et chaque valeur emploie le mot « dossier » de sa langue d'après le tableau de task-373, sans dérivé de « collection »
- [ ] #4 Un `grep -rn` de la nouvelle clé sous `mobile/src` et `mobile/app` (hors `src/i18n/`) ne renvoie qu'une seule occurrence, celle de `share-confirmation.tsx`
- [ ] #5 La carte « Non trié » du sélecteur (`CollectionPickerView`, renommée par task-373, garde `showUnsorted`) est intacte : cette tâche ne touche ni le nom de sa clé, ni sa valeur dans aucun des 11 catalogues, ni son `accessibilityLabel`
- [ ] #6 La ligne dossier affiche toujours `selectedFolder.path` quand un dossier est choisi, et son icône, son chevron et son `accessibilityLabel` d'action (`share.chooseFolder` après task-373) sont inchangés
- [ ] #7 Aucun état « Non trié choisi explicitement » n'est ajouté à `ShareIntentContext` : le `handleSelect(null)` de l'écran sélecteur (`app/media/collection.tsx`, renommé par task-373) continue d'appeler `setSelectedFolder(null)`
- [ ] #8 `npm run lint` et `npm run typecheck` sortent 0 depuis `mobile/`
<!-- AC:END -->
