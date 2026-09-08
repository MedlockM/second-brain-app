---
id: task-378
title: >-
  Démarrer le traitement du média dès la sélection de l’app dans le partage
  système
status: To Do
assignee: []
created_date: '2026-09-07 21:47'
updated_date: '2026-09-07 21:50'
labels:
  - mobile
  - ux
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Aujourd’hui, lorsqu’un utilisateur partage un média depuis une application tierce vers notre app, le traitement attend son appui sur « Enregistrer » dans le modal de sauvegarde. Le parcours actuel confirme ce déclenchement dans mobile/app/share-confirmation.tsx.

Faire démarrer le traitement dès que l’utilisateur choisit notre app dans la feuille de partage système : dès réception du contenu exploitable et validation de la session, sans attendre une interaction dans le modal. Objectif : utiliser le temps passé dans le modal pour avancer le traitement et réduire l’attente avant disponibilité du média.

Périmètre : partage entrant depuis une app tierce sur iOS et Android, pour les types de contenu déjà pris en charge. Conserver la possibilité de choisir le dossier pendant que le traitement avance. Le bouton « Enregistrer » confirme la conservation du média et finalise les choix du modal sans relancer l’ingestion. Le parcours d’ajout manuel depuis notre app n’est pas visé par cette demande.

Décision produit : si l’utilisateur clique sur la croix au lieu de cliquer sur « Enregistrer », supprimer le média créé par ce partage, que son traitement soit encore en cours ou déjà terminé. Il ne doit plus apparaître dans la bibliothèque ni dans la recherche. Gérer également une fermeture pendant la soumission initiale, avant réception de l’identifiant du média : une réponse tardive ou la fin du traitement ne doit pas laisser ni faire réapparaître le média annulé. La suppression cible uniquement la sauvegarde de ce partage, sans supprimer les autres sauvegardes du même contenu. Réutiliser la sémantique de suppression canonique existante. La fin du traitement ne vaut pas confirmation d’enregistrement et ne doit pas fermer automatiquement le modal avant le choix de l’utilisateur. Rendre visible un échec de suppression et permettre de réessayer, sans présenter l’annulation comme réussie.

Préserver les contrôles de session, de validité du contenu et de consommation existants. Réutiliser les contrats canoniques existants ; aucune décision de fournisseur ni benchmark nécessaire.

Validation manuelle par le propriétaire après intégration et disponibilité d’un build : partager depuis une app tierce, rester dans le modal sans appuyer sur « Enregistrer » et constater que le traitement a commencé, sur iOS et Android. Vérifier ensuite la suppression via la croix pendant le traitement et après sa fin, ainsi que la conservation via « Enregistrer ». Cette vérification ne constitue pas une condition de clôture dans le worktree.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Le parcours de partage externe iOS et Android déclenche automatiquement l’ingestion dès réception d’un contenu exploitable et validation de la session, sans dépendre du bouton « Enregistrer ».
- [x] #2 Ce déclenchement couvre les types de contenu déjà acceptés depuis les apps tierces, y compris le démarrage du transfert nécessaire pour les fichiers.
- [x] #3 Le modal permet de choisir le dossier pendant le traitement et applique ce choix au même média ; « Enregistrer » confirme sa conservation sans créer une seconde sauvegarde ni relancer le traitement.
- [x] #4 La gestion du partage protège une même réception contre les soumissions multiples liées au cycle de vie de l’écran ou au retour d’authentification, tout en permettant un nouveau partage volontaire.
- [x] #5 Les états de démarrage, de progression et d’échec sont représentés dans le parcours ; la fin du traitement ne ferme pas automatiquement le modal avant le choix de l’utilisateur.
- [x] #6 Les contrôles existants de session, de contenu et de consommation restent câblés avant la soumission ; un partage en attente d’authentification reprend automatiquement après connexion.

- [x] #7 La croix supprime la sauvegarde créée par ce partage, en cours de traitement comme déjà traitée, selon la suppression canonique existante ; elle disparaît de la bibliothèque et de la recherche sans affecter les autres sauvegardes du même contenu.
- [x] #8 Le parcours d’annulation prend en charge une fermeture avant réception de l’identifiant du média ; une réponse tardive ou la fin du traitement ne conserve ni ne fait réapparaître la sauvegarde annulée.
- [x] #9 Un échec de suppression est signalé avec une possibilité de réessayer ; l’interface ne présente pas l’annulation comme réussie tant que la suppression a échoué.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### What changed

**`mobile/src/contexts/ShareIntentContext.tsx`** carries the whole behaviour change.

- `ShareIntakeState` gained a required `origin: "share" | "local"`. Only `"share"`
  auto-submits and only `"share"` deletes on close; a local import (file picker,
  camera, manual paste) keeps its exact current behaviour, as the task excludes it.
- The old `response` field is replaced by `mediaItemId` + `deduplicated`, because the
  per-save `media_item_id` is what cancellation has to delete. `IngestUrlResponse` in
  `mobile/src/types/media.ts` was rewritten to the real flat wire shape it always had.
- Auto-start is an effect on `(origin === "share" && status === "ready")`, guarded by
  `autoSubmittedId === receptionId` so a remount, a foreground/background cycle or the
  return from the auth flow cannot submit twice (AC#4). `beginReception()` bumps
  `receptionId`, so a *new* deliberate share submits again.
- `submitIntake()` dispatches to the three existing endpoints (url / shared-content /
  upload), so every already-accepted type auto-starts, files included: the upload path
  begins its presigned staging on arrival (AC#2). The session, content-validity and
  consumption checks were left where they were, upstream of the submission (AC#6).
- Folder choice while processing (AC#3): `desiredFolderId` / `appliedFolderId` +
  a serialized `folderSync` promise. Picking a folder before the id is known records
  the intent; `registerSave()` flushes it once the id arrives. `PATCH /api/media/:id`
  is only called when the two differ.
- `confirmIntake()` (Save) awaits the in-flight submission, flushes the folder, then
  closes. It never re-submits, so there is no second save. Save on a failed submission
  still retries, via `isSubmittable(status) = ready || error`.
- `cancelIntake()` (X) sets `cancelRequested`, awaits `inFlight` to learn the id when
  the close lands mid-submission (AC#8), then calls the canonical
  `DELETE /api/media/:id` — no new deletion semantics, no status precondition. It
  returns `false` and surfaces `share.cancel.failed*` on failure, and the screen stays
  open with a retry (AC#9).

**`mobile/app/share-confirmation.tsx`**: `ready` and `submitting` collapse into one
choice view (preview + folder row + hint), the card footer shows a spinner then a
checkmark, and the 2 s auto-dismiss on success is now local-only so the end of
processing never closes the modal for a share (AC#5). A cancellation renders its own
pending / failed state in place of the content.

**`media_summarizer/workers/search_indexing_worker.py`**: the one path that could
resurrect a cancelled share. The message is written when transcription ends and read
minutes later; without a check it would re-create Algolia chunks for an item the user
already removed, and the search endpoint reads Algolia and cannot filter that out. The
worker now reads `get_user_media` first and skips when the row is absent (a
soft-deleted row reads as absent). No IAM or env change was needed: the shared worker
policy already grants `dynamodb:GetItem` on `local.table_arns` and `USER_MEDIA_TABLE`
is already injected into every worker Lambda.

AC#7's "sans affecter les autres sauvegardes du même contenu" holds by construction:
`save_media_for_user` mints a fresh `media_item_id` per submission, so deleting this
share's id cannot touch another save of the same URL.

### Out of reach from this worktree

- **Owner device validation** (share from a third-party app on iOS and Android, stay
  in the modal, observe processing has started; then X during and after processing,
  and Save) is not a closure condition per the description. Recorded in
  `docs/testing/manual-e2e-validation-matrix.md` §4.1 (SI-06..SI-15, total 95 → 100)
  and in `mobile/MANUAL_TEST_CHECKLIST.md`.
- **The search-indexing guard only takes effect once deployed.** The deploy happens on
  push to `main`, after this run. Until then, a share cancelled mid-transcription on
  dev can still reappear in Search.
- **No automated tests were added** (project rule). Verification is `npx tsc --noEmit`
  clean, `npm run lint` clean (only the pre-existing `purchaseService.ts:98`
  `no-explicit-any` warning), `ruff check media_summarizer/` and
  `mypy media_summarizer/` both clean.

### Pre-existing bug fixed in passing

`submitSharedContent` set the intake to `submitting` *before* the `isText || isAudio`
check and returned without resetting it, stranding the modal forever on an unsupported
shared type. The check now runs first — it matters more now that Save awaits the
in-flight submission.
<!-- SECTION:NOTES:END -->
