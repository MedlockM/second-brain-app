---
id: task-389
title: >-
  Réduire le modal d'enregistrement d'un média à « en cours d'enregistrement —
  le ranger dans un dossier ? Oui / Non »
status: Done
assignee: []
created_date: '2026-09-09 20:03'
updated_date: '2026-09-10 08:37'
labels:
  - mobile
  - ui
  - cleanup
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce qu'on veut

Le modal qui s'ouvre à chaque entrée d'un média se réduit à **une phrase et une question** :

> Votre média est en cours d'enregistrement dans votre second cerveau.
>
> Souhaitez-vous également le ranger dans un dossier ?
>
> `[ Non ]`   `[ Oui ]`

- **Oui** ouvre le sélecteur de dossier existant (`router.push("/media/folder?mode=share")`). Un tap sur une destination range le média, et tout se ferme.
- **Non** ferme le modal. Le média reste dans l'inbox, sans dossier.

Plus de bouton « Enregistrer » dans la barre haute, plus de carte d'aperçu du contenu, plus de titre par type de contenu, plus de ligne « Ranger dans un dossier ». `mobile/app/share-confirmation.tsx` fait 1153 lignes : il ne doit rester que ce modal, l'attente de validation, et sa branche d'échec (ci-dessous).

## Deux décisions déjà tranchées par l'owner

**1. Les trois origines démarrent l'ingestion à l'arrivée.** Aujourd'hui `ShareIntakeOrigin` vaut `share`, `url-entry` ou `local`, et `ingestsOnArrival()` (`ShareIntentContext.tsx:87`) répond faux pour `local` : un fichier choisi ou une photo prise dans l'app n'est envoyé que par « Enregistrer ». Sur ce chemin, « votre média est en cours d'enregistrement » serait un mensonge. **L'import local part donc dès que le fichier est choisi / la photo prise**, comme le partage système et l'URL tapée depuis task-378 et task-379. L'effet d'auto-soumission (`ShareIntentContext.tsx:1141-1150`) ne teste plus l'origine, et `ingestsOnArrival` disparaît. Le champ `origin` **reste** : `sourceAppFor(intake.origin)` s'en sert pour dire d'où vient le média.

**2. La branche d'échec est conservée telle quelle.** Ce modal est le seul endroit où un refus de quota s'affiche avec son CTA « Voir les plans », où un téléversement raté montre son diagnostic technique (task-371), et où un contenu invalide (`share.invalid`) se dit. Le modal porte donc deux visages selon `intake.status` : la question quand tout va bien (`submitting`, `success`), l'état d'échec existant quand `error` ou `invalid`. Rien de la remontée d'erreur n'est perdu ni déplacé.

## Ce que « Non » ne fait pas

Aujourd'hui le bouton de fermeture **supprime** le média que le démarrage à l'arrivée a créé : c'est tout l'appareil `cancelIntake` / `ShareCancellation` / `CancellationState` / `share.cancel.*` posé par task-378. Ce n'est plus ce qu'on demande à l'utilisateur : la question porte sur le rangement, et ni « Oui » ni « Non » ne veut dire « jette-le ». **« Non » ferme, point.** Toute cette machinerie part, y compris le drapeau `cancelRequested` du `trackingRef` qui ne garde plus rien. Un média partagé par erreur se supprime depuis l'inbox, comme n'importe quel autre.

## Comment le dossier s'applique

Rien à inventer : `selectFolder` (`ShareIntentContext.tsx:926-935`) appelle déjà `syncFolder()` immédiatement, « pour que le choix arrive même si l'utilisateur quitte le modal », et `registerSave` fait pareil quand la soumission répond. Le tap sur une destination dans le sélecteur **est** donc déjà l'application. Il ne reste au modal qu'à se fermer au retour. `confirmIntake` / `ShareConfirmResult`, qui n'existaient que pour le bouton Enregistrer, partent avec lui ; `share.folderFailed` reste, un rangement peut toujours échouer.

## Inventaire des suppressions dans `share-confirmation.tsx`

Aucun de ces symboles n'a de consommateur hors de ce fichier (vérifié) : `IntakeChoice`, `OrganizationControls`, `IntakePreview`, `UrlPreviewCard`, `TextPreviewCard`, `AudioPreviewCard`, `FilePreviewCard`, `PreviewStatus`, `previewStatus`, `submissionLabel`, `getSuccessMessage`, `CancellationState`, `TOP_BAR_TITLE_KEYS`, plus les styles qui deviennent orphelins.

## Les 27 clés i18n à supprimer

Dans les **11 catalogues** de `mobile/src/i18n/` : les 5 `share.title.*`, `share.saved`, `share.saving`, `share.uploadingAudio`, `share.uploadingFile`, les 3 `share.autoStart.*`, les 5 `share.cancel.*`, les 7 `share.success.*`, `share.noteText`, `share.chooseFolder`, `share.folderPlaceholder`. Il doit rester exactement 11 clés `share.*` : `processing`, `invalid`, `saveFailed`, `folderFailed`, les 3 `reject.*`, les 3 `signIn*`, `unsupportedFile`.

**`share.folderPlaceholder` est la clé que task-374 vient de livrer** (« Ranger dans un dossier »). Elle n'a plus de ligne où s'afficher : elle part, dans les 11 catalogues. C'est attendu, ce n'est pas une régression à éviter.

## Les 5 nouvelles clés

Noms proposés, à ajuster si besoin : `share.inProgress.body`, `share.inProgress.duplicate`, `share.inProgress.question`, `common.yes`, `common.no`.

Copie française, **verbatim de l'owner**, les cinq :
- `share.inProgress.body` → « Votre média est en cours d'enregistrement dans votre second cerveau. »
- `share.inProgress.question` → « Souhaitez-vous également le ranger dans un dossier ? »
- `common.yes` → « Oui » ; `common.no` → « Non »

`share.inProgress.duplicate` remplace `share.success.duplicate` pour le cas où le backend reconnaît un contenu déjà ingéré (`intake.deduplicated`) : la phrase nominale y serait fausse, le média n'est pas en cours d'enregistrement, il est déjà là. Sa valeur française est « Ce média est déjà dans votre second cerveau. », validée par l'owner le 2026-09-09. La question de rangement, elle, reste posée dans les deux cas.

## Mécanique i18n

`TranslationKey = keyof typeof en` (`mobile/src/i18n/runtime.ts`) : une clé se déclare d'abord dans `en.ts`, puis `Catalog = Record<TranslationKey, string>` impose de la définir dans les 11 catalogues (`en, fr, es, de, it, pt, nl, ja, zh, ar, hi`) — un catalogue oublié casse `npm run typecheck`, et c'est ce qui prouve la complétude. `pseudo.ts` ne contient aucun littéral. Les dix langues non françaises reprennent le mot « dossier » de leur langue d'après le tableau de task-373 et le registre déjà employé par le catalogue concerné.

## Ce qui n'est pas touché

- La route reste `share-confirmation`, `presentation: "modal"` dans `app/_layout.tsx:183-190`.
- Le sélecteur de dossier (`app/media/folder.tsx`, `FolderPickerView`) et son `mode=share` : inchangés, `handleSelect` continue de poser `setSelectedFolder` puis `router.back()`.
- Le garde de session (`guardSession`, `parkCurrentIntakeForAuth`, la revalidation sur `AppState`) de task-278 et task-295 : inchangé.
- `retry()` : la branche d'échec garde son bouton Réessayer.

## Notes à l'owner (pas des AC)

- **Vérification visuelle après merge, sur un build**, les trois entrées : partager une URL depuis Safari/Chrome, taper une URL dans le menu « + », prendre une photo depuis l'app. Les deux boutons portent des libellés très courts (« Oui », « Non ») : c'est l'allemand et le néerlandais qui allongent le plus la phrase au-dessus.
- **Perte assumée** : il n'y a plus de moyen d'annuler un partage accidentel depuis le modal. La suppression se fait depuis l'inbox.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Dans `mobile/app/share-confirmation.tsx`, l'état nominal du modal (statuts `submitting` et `success`) rend exactement la phrase, la question et deux boutons « Non » et « Oui » : aucune carte d'aperçu du contenu, aucun titre par type de contenu dans la barre haute, aucune ligne « dossier », et aucun bouton « Enregistrer » dans le slot `trailing` du `ScreenHeader`
- [x] #2 « Oui » appelle `router.push("/media/folder?mode=share")`, et au retour du sélecteur avec un dossier choisi le modal se ferme de lui-même sans qu'une action supplémentaire de l'utilisateur soit requise ; l'application du dossier repose sur le `syncFolder()` déjà déclenché par `selectFolder` et `registerSave` dans `ShareIntentContext`
- [x] #3 « Non » quitte le modal sans supprimer quoi que ce soit : aucun chemin partant de ce bouton n'appelle `MediaService.deleteMedia`
- [x] #4 L'effet d'auto-soumission de `mobile/src/contexts/ShareIntentContext.tsx` ne teste plus l'origine de l'intake : un import local (`startLocalUpload`) est soumis dès sa réception, comme un partage système et une URL tapée
- [x] #5 `ingestsOnArrival` n'existe plus : `grep -rn "ingestsOnArrival" mobile/src mobile/app` ne renvoie rien. Le champ `origin` de `ShareIntakeState` et le type `ShareIntakeOrigin` sont conservés, et `sourceAppFor(intake.origin)` est inchangé
- [x] #6 La branche d'échec est intégralement conservée dans le modal : titre et message de refus de quota, CTA « Voir les plans » vers `/paywall?reason=out_of_minutes`, bloc de diagnostic de téléversement de task-371 (`intake.uploadDiagnostics`, `upload.diagnostics.*`), bouton Réessayer câblé sur `retry()`, et l'état `invalid` avec `share.invalid`
- [x] #7 Toute la machinerie d'annulation est supprimée : `grep -rn "cancelIntake\|ShareCancellation\|CancellationState\|cancelRequested\|share.cancel" mobile/src mobile/app` ne renvoie rien, catalogues i18n compris
- [x] #8 Les composants et helpers devenus sans emploi sont supprimés de `share-confirmation.tsx` : un `grep -rn` de `IntakeChoice`, `OrganizationControls`, `IntakePreview`, `UrlPreviewCard`, `TextPreviewCard`, `AudioPreviewCard`, `FilePreviewCard`, `previewStatus`, `submissionLabel`, `getSuccessMessage`, `TOP_BAR_TITLE_KEYS`, `confirmIntake` et `ShareConfirmResult` sous `mobile/src` et `mobile/app` ne renvoie rien
- [x] #9 Les 27 clés listées dans la description sont supprimées des 11 catalogues de `mobile/src/i18n/`, et il reste exactement 11 clés de la famille `share.*` : `processing`, `invalid`, `saveFailed`, `folderFailed`, les 3 `reject.*`, les 3 `signIn*`, `unsupportedFile`
- [x] #10 Les 5 nouvelles clés (la phrase, sa variante dédup, la question, « Oui », « Non ») sont définies dans les 11 catalogues, et `mobile/src/i18n/fr.ts` porte exactement « Votre média est en cours d'enregistrement dans votre second cerveau. », « Ce média est déjà dans votre second cerveau. », « Souhaitez-vous également le ranger dans un dossier ? », « Oui » et « Non »
- [x] #11 Le cas `intake.deduplicated` affiche la variante dédup à la place de la phrase nominale, et pose la même question de rangement
- [x] #12 Aucune clé `share.*` restante n'est orpheline : chacune des 11 clés conservées a au moins un consommateur sous `mobile/src` ou `mobile/app` hors de `mobile/src/i18n/`
- [x] #13 `npm run lint` et `npm run typecheck` sortent 0 depuis `mobile/`
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
## Delivered

- `mobile/app/share-confirmation.tsx` goes from 1153 to 572 lines. The nominal state is `FolderQuestion`: the sentence, the question, and `[ Non ] [ Oui ]`. The header carries a close button and nothing else — `ScreenHeader` is given only a `leading`, so both the per-content-type title and the Save slot are gone.
- All three origins now ingest on arrival. The auto-submission effect no longer reads `intake.origin`, `ingestsOnArrival` is deleted, and `ShareIntakeOrigin` / `origin` / `sourceAppFor(intake.origin)` are untouched — the value is a fact reported to the backend, not a branch.
- The cancellation apparatus is gone whole: `cancelIntake`, `ShareCancellation`, `ShareCancellationStatus`, `NO_CANCELLATION`, the `cancellation` state, the `cancelRequested` flag and its four guards, and the `MediaService.deleteMedia` call the close button used to make. `dismissIntake` replaces `dismiss`/`cancelIntake` and only lets go: it does not reset `trackingRef`, so a folder patch still in flight when the modal closes lands on the right save (only `beginReception` starts fresh tracking).
- `confirmIntake` and `ShareConfirmResult` left with the Save button. `share.folderFailed` kept its consumer: `reportFolderFailure` in the provider raises it as an `Alert` from the two `syncFolder()` call sites (`registerSave`, `selectFolder`), which is where it belongs now that the modal is normally gone by the time a folder PATCH fails. Its copy was rewritten in all 11 catalogues — the old wording named a Save button that no longer exists.
- 27 keys deleted from the 11 catalogues; the 11 pre-existing `share.*` keys named in AC#9 remain, plus the 3 new `share.inProgress.*`, giving 14 `share.*` per catalogue. `common.yes` / `common.no` sit next to `common.ok`. The 11 key sets are byte-identical across catalogues.

## Two decisions worth knowing

- **"Oui" is a one-way door.** The modal closes on *any* return from the picker, not only when a folder came back. The picker answers in three ways a folder id cannot carry: a folder lands in `selectedFolder`, "Unsorted" lands as `null` — indistinguishable from never having gone — and backing out means "no folder after all". Keying the close on `selectedFolder` alone would have stranded a user who tapped "Unsorted" on the same question. A `visitedPickerRef` set at push time is the signal instead. AC#2 is satisfied either way: a return with a chosen folder closes with no further action.
- **A quota refusal still has no in-modal way forward.** Retry stays gated on `quotaErrorCode === null` (branche d'échec conservée telle quelle, AC#6), and Save — which used to be the way back after subscribing — is gone. Someone who subscribes on the paywall has to send the content again from the app it came from. Worth a follow-up task if the owner would rather the Retry button appear once an entitlement changes.

## Also touched

Three doc comments that had gone stale on the deleted Save button: `applyUrlEntry` in the provider, the header block of `mobile/app/(tabs)/inbox.tsx` ("the three local imports still send on Save"), and the header of `mobile/src/lib/localImport.ts`.

## Verification

- `cd mobile && npm run typecheck`: passes. This is also the proof of i18n completeness — `Catalog = Record<TranslationKey, string>` makes a key missing from any of the 11 catalogues a `tsc` error.
- `cd mobile && npm run lint`: exit 0, 0 errors. The single warning is pre-existing in `src/services/purchaseService.ts:98`, untouched here.
- The AC greps (#5, #7, #8) return nothing over `mobile/src mobile/app`. `deleteMedia` survives only in `useMediaActions.ts` and `media/unsorted-review.tsx` — nothing reachable from the modal (#3).
- Each of the 14 remaining `share.*` keys has at least one consumer outside `mobile/src/i18n/` (#12).
- No automated tests were added, per repository delivery rules. Maestro flows were not treated as a constraint.

## Owner check after merge

The visual pass the description asks for is not reachable from a worktree: it needs a build on a device. The three entries to walk are share a URL from Safari/Chrome, type a URL in the "+" menu, and take a photo from the app — plus, on each, tapping "Oui" then "Unsorted" to see the modal close. German and Dutch are the languages that stretch the question the most.
<!-- SECTION:NOTES:END -->
