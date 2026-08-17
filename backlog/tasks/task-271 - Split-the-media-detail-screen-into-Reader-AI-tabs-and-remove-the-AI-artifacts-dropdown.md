---
id: task-271
title: >-
  Split the media detail screen into Reader / AI tabs and remove the AI
  artifacts dropdown
status: To Do
assignee: []
created_date: '2026-08-17 19:42'
labels:
  - mobile
  - ui
  - design
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Objectif

Décision de l'owner (2026-08-17), dans le cadre du rapprochement avec Google NotebookLM (task-263) : la liste des artefacts IA **pollue l'écran d'un média**. Elle passe dans un onglet dédié, à côté d'un onglet qui porte le contenu lisible.

Cible : `mobile/app/media/[id].tsx` expose deux onglets intra-écran :

- **« Reader »** — le contenu textuel du média (aujourd'hui la section « Transcript »).
- **« AI »** — les tuiles de génération d'artefacts (aujourd'hui la section dépliante « AI Artifacts »).

Les onglets sont **internes à l'écran**, sous l'en-tête, pas dans la barre d'onglets basse d'`expo-router` (`app/(tabs)/_layout.tsx`), qui reste inchangée.

## État actuel (vérifié le 2026-08-17)

Dans `mobile/app/media/[id].tsx` (≈1890 lignes, tous les sous-composants sont locaux au fichier) :

- `ARTIFACT_TYPES` (≈L51-69) : les 5 tuiles `summary_short` « Summary », `summary_detailed` « Detailed summary », `notes` « Learning notes », `flashcards` « Flashcards », `quiz` « Quiz ».
- `CompletedDetailView` (≈L365) : `artifactsExpanded` (≈L467, **ouvert par défaut**), `artifactStates`, `toggleArtifactsExpanded` (≈L662, `LayoutAnimation`), polling `startArtifactPolling` (≈L525), `handleGenerate` (≈L578, avec retry sur 409 « translation in flight »).
- Rendu (≈L871-952) : `heroSection` (titre, `SourceChip`, date, durée) → `artifactsSection` (≈L902-943 : `Pressable` de toggle avec `chevron-up`/`chevron-down` et le texte visible **« AI Artifacts »**, puis `artifactsList` mappant `ARTIFACT_TYPES` sur `ArtifactRow`) → `contentSection` (≈L945 → `TranscriptSection`).
- `ArtifactRow` (≈L1114-1155) porte tous les états : « Queued » / « Generating… » / « Ready » + « View » / « Failed » + « Retry » / « Generate » / « Processing… », et navigue vers `/artifacts/${artifactId}`.
- `TranscriptSection` (≈L1160-1277) porte le titre visible **« Transcript »**, les métadonnées (langue, durée, nombre de paragraphes) et tous les états de traitement/traduction, via `TranscriptBody` / `TranscriptContent`.
- **Aucun composant d'onglets réutilisable n'existe** : `mobile/src/components/` ne contient que `AddSourceSheet.tsx`, `MediaListCard.tsx`, `SocialAuthButtons.tsx`, `SubscriptionStatusCard.tsx`.

## Ce que la tâche doit produire

1. **Un composant d'onglets partagé** dans `mobile/src/components/` (le nom est au choix de l'implémenteur, p. ex. `ScreenTabs`), piloté par une liste d'onglets `{ key, label, icon? }`, accessible (rôle `tab`, état sélectionné annoncé), et **conçu pour être réutilisé tel quel par task-272** sur l'écran collection. Pas de composant d'onglets local à un écran : task-272 doit pouvoir l'importer sans le réécrire.
2. **Un composant de tuile d'artefact partagé**, extrait de l'`ArtifactRow` actuel de `[id].tsx`, avec ses états. Même raison : l'onglet IA d'une collection (task-272) affiche les mêmes tuiles.
3. **Le découpage de `[id].tsx`** : en-tête et hero au-dessus des onglets ; l'onglet **Reader** rend le transcript et tous ses états ; l'onglet **AI** rend les tuiles et le polling de génération. Le fichier fait bientôt 1900 lignes : extraire les sous-composants réutilisés est attendu, pas optionnel.
4. **La suppression de la mécanique de dépliage** : `artifactsExpanded`, `toggleArtifactsExpanded`, le `Pressable` de toggle, les chevrons et le libellé « AI Artifacts » disparaissent. Rien n'est conservé en fallback — aucune donnée en production, aucun utilisateur installé.
5. **La préservation du comportement fonctionnel** : polling de statut, retry sur 409 pendant une traduction en vol, navigation vers `/artifacts/[artifactId]`, états de transcript (traitement, traduction en cours, traduction échouée, indisponible, erreur + « Retry ») restent tous atteignables depuis l'onglet correspondant.

## Décisions déjà tranchées (ne pas les rouvrir)

- Libellés d'onglets **« Reader »** et **« AI »**, en anglais comme le reste de l'UI. « Reader » est imposé par l'owner.
- **Reader est l'onglet sélectionné par défaut** à l'ouverture d'un média.
- Le polling des artefacts ne doit pas s'arrêter quand l'onglet AI n'est pas visible si une génération est en vol : l'utilisateur doit retrouver le bon statut en y revenant.
- Aucune valeur de couleur, d'espacement ou de typographie en dur : tout vient de `mobile/src/constants/theme.ts` (« Amber Clarity »), y compris pour le nouveau composant d'onglets.

## Casses Maestro à consigner

Les flows suivants assertent la structure qui disparaît, et **ne doivent pas être réécrits ici** (la suite est en sommeil depuis le 2026-08-13, task-254 ; la réactivation est pilotée par task-263 / task-172) — ils doivent être **listés** dans les Implementation Notes avec le libellé cassé :

- `mobile/.maestro/04_media_detail_progression.yaml` : `text: "AI Artifacts"` (≈L67) et le tap dessus (≈L72), puis les tuiles « Summary » / « Detailed summary » / « Learning notes » / « Flashcards » / « Quiz », et `text: "Transcript"` (≈L94).
- `mobile/.maestro/05_artifact_trigger_action.yaml` : `"AI Artifacts"` (≈L68, L72, L130), `"Summary"`, `"Generate"`, la regex `"Queued|Generating|Ready"`, `"View"`.

## Note à l'owner — hors AC

- La validation visuelle sur dev build iOS et Android vous revient : un agent en worktree ne lance pas l'app.
- Cette tâche déplace le libellé « Transcript » sous un onglet « Reader ». Si vous voulez aussi renommer le titre de section à l'intérieur de l'onglet, dites-le : par défaut l'onglet s'appelle « Reader » et la section intérieure garde son titre et ses métadonnées.
- task-272 (onglets Sources/IA de la collection) importe les deux composants partagés créés ici. Ordonner celle-ci avant.
- **Périmètre volontairement limité au déplacement.** L'owner a décidé le 2026-08-17 que les artefacts deviennent un historique horodaté (plusieurs entrées par type, avec leur date), y compris côté média. Cet affichage n'est **pas** dans cette tâche : il a besoin du backend de task-270 et il est traité par **task-273**. Ici, le comportement fonctionnel actuel — un artefact par type, tuile qui passe à « Ready » — est préservé tel quel, on ne fait que le déplacer dans un onglet. Ne pas anticiper l'historique ; en revanche, ne pas verrouiller la tuile partagée de façon à interdire l'ajout ultérieur d'une ligne secondaire (date, nombre de sources).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Un composant d'onglets réutilisable existe dans `mobile/src/components/`, paramétré par une liste d'onglets, sans dépendance à l'écran média, et expose un rôle d'accessibilité `tab` avec l'état sélectionné annoncé
- [ ] #2 La tuile d'artefact est extraite de `mobile/app/media/[id].tsx` vers un composant de `mobile/src/components/`, avec tous ses états (queued, generating, ready + View, failed + Retry, generate, processing), et `[id].tsx` l'importe au lieu d'en garder une copie locale
- [ ] #3 `mobile/app/media/[id].tsx` rend deux onglets intra-écran « Reader » et « AI » sous l'en-tête et le hero, avec « Reader » sélectionné par défaut
- [ ] #4 L'onglet « Reader » rend le contenu du transcript et tous ses états (traitement, traduction en cours, traduction échouée, indisponible, erreur avec bouton de reprise) ; l'onglet « AI » rend les 5 tuiles d'artefacts et la navigation vers `/artifacts/[artifactId]`
- [ ] #5 La mécanique de dépliage est supprimée : plus aucune occurrence de `artifactsExpanded`, `toggleArtifactsExpanded`, du toggle à chevrons ni du libellé « AI Artifacts » dans `mobile/app/media/[id].tsx`, et aucun code de repli conservé
- [ ] #6 Le polling de statut des artefacts et le retry sur 409 pendant une traduction en vol sont préservés, et une génération lancée reste suivie même lorsque l'onglet AI n'est pas l'onglet actif
- [ ] #7 Aucune valeur de couleur, d'espacement ou de typographie en dur n'est introduite : les nouveaux composants et les sections déplacées lisent `mobile/src/constants/theme.ts`
- [ ] #8 `npx tsc --noEmit` et l'ESLint du repo passent sur `mobile/` sans nouvelle erreur ni nouveau warning, et les règles react-hooks restent au niveau où task-227 les a laissées
- [ ] #9 Les Implementation Notes listent les libellés visibles et `testID` supprimés ou déplacés, avec pour chacun le flow de `mobile/.maestro/*.yaml` et la ligne qu'il casse ; aucun fichier `.maestro` n'est modifié
- [ ] #10 Aucune dépendance npm n'est ajoutée sans justification écrite dans les Implementation Notes, avec mention explicite si elle impose un nouveau build natif
<!-- AC:END -->
