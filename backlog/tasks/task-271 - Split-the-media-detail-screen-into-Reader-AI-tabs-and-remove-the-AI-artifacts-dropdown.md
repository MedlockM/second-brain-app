---
id: task-271
title: >-
  Split the media detail screen into Reader / AI tabs and remove the AI
  artifacts dropdown
status: Done
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
- [x] #1 Un composant d'onglets réutilisable existe dans `mobile/src/components/`, paramétré par une liste d'onglets, sans dépendance à l'écran média, et expose un rôle d'accessibilité `tab` avec l'état sélectionné annoncé
- [x] #2 La tuile d'artefact est extraite de `mobile/app/media/[id].tsx` vers un composant de `mobile/src/components/`, avec tous ses états (queued, generating, ready + View, failed + Retry, generate, processing), et `[id].tsx` l'importe au lieu d'en garder une copie locale
- [x] #3 `mobile/app/media/[id].tsx` rend deux onglets intra-écran « Reader » et « AI » sous l'en-tête et le hero, avec « Reader » sélectionné par défaut
- [x] #4 L'onglet « Reader » rend le contenu du transcript et tous ses états (traitement, traduction en cours, traduction échouée, indisponible, erreur avec bouton de reprise) ; l'onglet « AI » rend les 5 tuiles d'artefacts et la navigation vers `/artifacts/[artifactId]`
- [x] #5 La mécanique de dépliage est supprimée : plus aucune occurrence de `artifactsExpanded`, `toggleArtifactsExpanded`, du toggle à chevrons ni du libellé « AI Artifacts » dans `mobile/app/media/[id].tsx`, et aucun code de repli conservé
- [x] #6 Le polling de statut des artefacts et le retry sur 409 pendant une traduction en vol sont préservés, et une génération lancée reste suivie même lorsque l'onglet AI n'est pas l'onglet actif
- [x] #7 Aucune valeur de couleur, d'espacement ou de typographie en dur n'est introduite : les nouveaux composants et les sections déplacées lisent `mobile/src/constants/theme.ts`
- [x] #8 `npx tsc --noEmit` et l'ESLint du repo passent sur `mobile/` sans nouvelle erreur ni nouveau warning, et les règles react-hooks restent au niveau où task-227 les a laissées
- [x] #9 Les Implementation Notes listent les libellés visibles et `testID` supprimés ou déplacés, avec pour chacun le flow de `mobile/.maestro/*.yaml` et la ligne qu'il casse ; aucun fichier `.maestro` n'est modifié
- [x] #10 Aucune dépendance npm n'est ajoutée sans justification écrite dans les Implementation Notes, avec mention explicite si elle impose un nouveau build natif
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### What was implemented

`mobile/app/media/[id].tsx` went from 1891 to 1226 lines. Header and hero are unchanged and still sit at the top; under them the screen now renders a two-tab control, and the artifacts dropdown is gone.

Four new files, three of them shared:

- **`mobile/src/components/ScreenTabs.tsx`** — the reusable intra-screen tab control (AC#1). Generic over the key type (`ScreenTabs<"reader" | "ai">`), driven by `tabs: readonly ScreenTab<K>[]` where `ScreenTab = { key, label, icon? }`, plus `activeKey` / `onChange` / `accessibilityLabel`. It knows nothing about media, artifacts or the router — task-272 imports it as-is for `Sources` / `AI`. Accessibility: the container is `accessibilityRole="tablist"`, each `Pressable` is `accessibilityRole="tab"` with `accessibilityState={{ selected }}` and its label. Visually it is the Amber Clarity segmented control, same tokens as the existing digest control (pill of `surfaceContainerLow`, active pill `Colors.primary` with `onPrimary` text), with `minHeight: TouchTarget.minimum` per tab.
- **`mobile/src/components/ArtifactTile.tsx`** — the old local `ArtifactRow` extracted (AC#2), with every state preserved verbatim: `Queued`, `Generating...`, `Ready` + `View`, `Failed` + `Retry`, `Generate`, `Processing...`. It also exports `ArtifactTileState` (the former local `ArtifactLocalState`) and `ARTIFACT_TILES` (the former local `ARTIFACT_TYPES`: the same 5 types, same labels, same glyphs, same order), because task-272 needs the identical catalogue. Two deliberate changes: the `mediaReady` prop is renamed `sourceReady` so a collection can drive it, and the dead `type` prop is dropped (it was the source of the only pre-existing lint warning in this file). The label sits in its own column (`labelColumn`) so the timestamped-history line of task-273 (`N sources • 11d ago`) drops in without reshaping the tile — no history behaviour is anticipated here, one artifact per type as before.
- **`mobile/src/components/TranscriptReader.tsx`** — the Reader tab's content: the former `TranscriptSection` / `TranscriptBody` / `TranscriptContent`, `splitTranscriptParagraphs` and the exported `TranscriptContentState` (former `RawContentState`). Rendering only; the fetch, the translation poll and the retry stay in the screen that owns the state.
- **`mobile/src/lib/formatDuration.ts`** — the duration formatter, now shared by the hero chip row and the reader's metadata line instead of being duplicated across two files.

In the screen itself: `activeTab` is `useState<MediaDetailTabKey>("reader")` (AC#3), the tab bar is the sticky child of the `ScrollView` (`stickyHeaderIndices={[1]}`, hero is child 0, content is child 2) so switching to AI never requires scrolling back up through a long transcript, and the AI tab opens with a `Generate` section title above the tile stack — the section title the NotebookLM reference establishes, matching the `Transcript` title the Reader tab keeps (owner's default per the task description).

The tile stack is now five self-contained cards on `Colors.surface` separated by a `Spacing.sm` gap, replacing the single bordered container with hairline row separators. That is the "No-Line rule" of the design system, and it is what makes the future secondary metadata line legible. `Shadows.soft` is no longer used on this screen: it was carried by the amber toggle bar and the artifacts container, both of which are gone.

### AC#6 — why polling survives the tab switch

`artifactStates`, `startArtifactPolling`, `handleGenerate` (with its 409 "translation in flight" retry chain, `ARTIFACT_TRANSLATION_RETRY_MAX_ATTEMPTS`, `artifactRetryTimeoutsRef`) and the whole transcript fetch/translation-poll machinery all stayed in `CompletedDetailView`, which is mounted for both tabs. Only the *rendering* moved into the tab branches. So a generation started in the AI tab keeps polling while the user reads in the Reader tab, and the tile shows the current status when they come back; symmetrically, a translation poll started in the Reader tab keeps running while the AI tab is displayed. The `setInterval` is still cleared when no artifact is `queued`/`generating` and on unmount — the tab switch is not an unmount.

### AC#9 — Maestro breakages (no `.maestro` file was touched)

The suite has been dormant since 2026-08-13 (task-254) and its reactivation is driven by task-263 / task-172, so the flows below are **listed, not rewritten**. No element in this screen ever carried a `testID`: every assertion below matches visible text or an accessibility label, so the inventory is a text inventory.

| Flow | Line | Selector | Why it breaks |
|---|---|---|---|
| `04_media_detail_progression.yaml` | 66-68 | `assertVisible: text: "AI Artifacts"` | The label and its container are deleted. Replacement: the tab labels `Reader` / `AI`. |
| `04_media_detail_progression.yaml` | 71-72 | `tapOn: text: "AI Artifacts"` | The expand toggle no longer exists. Replacement: `tapOn: text: "AI"` to select the tab. |
| `04_media_detail_progression.yaml` | 75-85 | `"Summary"`, `"Detailed summary"`, `"Learning notes"`, `"Flashcards"`, `"Quiz"` | Same labels, same order, but now only rendered when the AI tab is selected — they are invisible on the default Reader tab. |
| `04_media_detail_progression.yaml` | 93-95 | `assertVisible: text: "Transcript"` (optional) | Still rendered, but as the Reader tab's section title. It is now visible *by default* instead of after a scroll past the artifacts block; the `scroll` step at 89-91 may scroll past it. Marked `optional: true`, so it does not hard-fail. |
| `04_media_detail_progression.yaml` | 4-10 | header comment describing an "expandable AI Artifacts section" | Documentation of a structure that no longer exists. |
| `05_artifact_trigger_action.yaml` | 67-69 | `assertVisible: text: "AI Artifacts"` | Deleted label. |
| `05_artifact_trigger_action.yaml` | 71-72 | `tapOn: text: "AI Artifacts"` | Deleted toggle; must become `tapOn: text: "AI"`. |
| `05_artifact_trigger_action.yaml` | 74-76 | `assertVisible: text: "Summary"` | Only visible once the AI tab is selected. |
| `05_artifact_trigger_action.yaml` | 82-89 | `"Generate"` (wait + tap, `index: 0`) | Label unchanged, still `index: 0` for the Summary tile, but only reachable from the AI tab. |
| `05_artifact_trigger_action.yaml` | 92-96 | regex `"Queued\|Generating\|Ready"` | Labels unchanged (`Queued`, `Generating...`, `Ready`) — reachable only from the AI tab. |
| `05_artifact_trigger_action.yaml` | 100-110 | `"Ready"`, `assertVisible`/`tapOn` `"View"` | Unchanged labels, reachable only from the AI tab. The router pushes `/artifacts/[id]` on top, so the media screen stays mounted and comes back with the AI tab still selected — no re-tap needed after the back navigation. |
| `05_artifact_trigger_action.yaml` | 128-131 | `assertVisible: text: "AI Artifacts"` (back-navigation check) | Deleted label. Replacement: assert the hero title or `tapOn: text: "AI"` then a tile. |
| `05_artifact_trigger_action.yaml` | 2-10 | header comment ("Expand \"AI Artifacts\"…") | Documents the removed dropdown. |
| `06_search.yaml` | 41-48 | `extendedWaitUntil: text: "AI Artifacts.*"` | **Not listed in the task description** but broken by the same deletion: the flow waited on the toggle's accessibility label (`"AI Artifacts, collapse"` on iOS) as the signal that detail polling reached a terminal state. Replacement signal: the `Reader`/`AI` tab bar, or the hero title. |

Labels that did **not** change and stay assertable once the AI tab is selected: `Summary`, `Detailed summary`, `Learning notes`, `Flashcards`, `Quiz`, `Generate`, `Queued`, `Generating...`, `Ready`, `View`, `Failed`, `Retry`, `Processing...`, `Transcript`, `Loading transcript…`, `Translating transcript...`, `Translation failed. Showing original transcript.`, `Transcript content is not available for this item.`, `No transcript available yet.`, `Transcript will appear once processing completes.`. New labels available as anchors: `Reader`, `AI`, `Generate` (section title).

### AC#10 — dependencies

No npm dependency added, so no new native build is required for this change. The tab control is plain `View`/`Pressable`/`Text` and the sticky header is the RN `ScrollView` prop — no `react-native-tab-view`, no `react-native-pager-view`, no reanimated.

### Checks

- `npx tsc --noEmit` in `mobile/`: clean.
- `npx eslint . --ext .ts,.tsx` in `mobile/`: **0 errors, 9 warnings**, against a pre-change baseline of 0 errors / 10 warnings on the same tree. The warning that disappeared is `app/media/[id].tsx:1065 'type' is defined but never used` (the dead `ArtifactRow` prop). No warning was added, and `.eslintrc.js` is untouched — the five `react-hooks/*` rules stay at the `error` level task-227 set.
- The visual pass on iOS and Android dev builds is the owner's (an agent in a worktree does not run the app), as stated in the task. Worth checking first: the sticky tab bar while scrolling a long transcript, and the tile stack now that the container frame is gone.
<!-- SECTION:NOTES:END -->
