---
id: task-379
title: Ajouter un média par saisie de son URL depuis le menu « + » de l'Accueil
status: Done
assignee: []
created_date: '2026-09-08 09:58'
updated_date: '2026-09-08 10:48'
labels:
  - mobile
  - ux
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

L'Accueil (`mobile/app/(tabs)/inbox.tsx`, bouton `inbox-add-button`) ouvre `AddSourceSheet` (`mobile/src/components/AddSourceSheet.tsx`), qui ne propose aujourd'hui que deux entrées : importer un fichier et importer une photo. Un troisième bouton, hors du menu, prend une photo. Autrement dit : depuis l'app elle-même, on ne peut ajouter que du local. Ajouter un média par son URL n'est possible que par le partage système depuis une app tierce.

## Demande

Ajouter dans ce menu « + » une entrée qui permet à l'utilisateur de saisir ou coller l'URL du média qu'il veut ajouter. Dès que l'URL est ajoutée, le traitement du média qui se trouve à cette URL démarre — sans attendre une confirmation supplémentaire, exactement comme le partage système depuis task-378.

## Périmètre

- **Entrée dans le menu** : une ligne de plus dans `AddSourceSheet`, alignée sur les deux existantes (icône, libellé, description, chevron), avec sa copie dans les 11 catalogues i18n de `mobile/src/i18n/` (en, fr, es, de, it, pt, nl, ja, zh, ar, hi).
- **Surface de saisie** : une surface produit de l'app, pas un dialogue système — `Alert.prompt` est iOS-only et n'existe pas sur Android. Champ mono-ligne, clavier de type URL, sans autocapitalisation ni autocorrection, collage par le clavier système. Pas de nouveau module natif : un bouton « Coller » explicite demanderait `expo-clipboard` et donc un nouveau build natif, ce qui est hors périmètre.
- **Validation** : réutiliser `mobile/src/lib/urlValidation.ts` — schémas http/https, hôte avec point, extraction d'une URL entourée de texte, domaine nu complété en `https://`. Une saisie sans URL exploitable est refusée sur place, avec un message, et ne crée aucune sauvegarde.
- **Ingestion** : réutiliser le chemin URL existant (`ShareIntentContext` → `MediaService.ingestUrl` → `POST /api/media/ingest-url`). Aucun nouvel endpoint, aucun contrat backend touché, aucune nouvelle plateforme à reconnaître. Le `source_app` envoyé doit distinguer cette entrée du partage système (`ios-share-extension` / `android-share-intent`), pour que l'origine reste lisible côté données.
- **Déclenchement et confirmation** : le traitement part dès que l'URL est validée. L'écran de confirmation existant (`mobile/app/share-confirmation.tsx`) reste la surface où l'utilisateur choisit le dossier pendant que le traitement avance. Reprendre la sémantique déjà tranchée par task-378 pour un média dont le traitement est lancé avant confirmation : « Enregistrer » confirme la conservation sans relancer l'ingestion ni créer une seconde sauvegarde ; la croix supprime la sauvegarde créée par cette saisie, que le traitement soit en cours ou terminé, via la suppression canonique, et un échec de suppression est visible et réessayable plutôt que présenté comme une annulation réussie.
- **Gardes conservées** : session et authentification (une saisie en attente de connexion reprend après), quota et minutes, déduplication (une URL déjà ingérée revient en succès avec la formulation « déjà dans votre boîte »), erreurs réseau et rate limit.

## Hors périmètre

Le partage système entrant, les imports fichier/photo/caméra, tout changement backend, l'ajout de plateformes sources.

## Note au propriétaire (pas une condition de clôture)

À valider sur un build après intégration : depuis l'Accueil, coller une URL d'article puis une URL YouTube, sur iOS et Android ; constater que le traitement a démarré avant tout appui sur « Enregistrer », puis vérifier la croix pendant le traitement et après sa fin, et la conservation par « Enregistrer ».
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Le menu « + » de l'Accueil propose une entrée de saisie d'URL, alignée sur les deux entrées d'import existantes ; sa copie existe dans les 11 catalogues i18n de mobile/src/i18n/.
- [x] #2 La saisie se fait sur une surface de l'app, sans dialogue système iOS-only, avec un champ à clavier URL, sans autocapitalisation ni autocorrection, et collage par le clavier ; aucun nouveau module natif n'est ajouté à mobile/package.json.
- [x] #3 La validation passe par mobile/src/lib/urlValidation.ts ; une saisie sans URL exploitable est refusée sur place avec un message et ne crée aucune sauvegarde ni n'ouvre l'écran de confirmation.
- [x] #4 Une URL validée déclenche l'ingestion par le chemin existant (MediaService.ingestUrl) sans attendre « Enregistrer », et ouvre l'écran de confirmation où le dossier reste choisissable pendant que le traitement avance.
- [x] #5 Le source_app envoyé par cette entrée est distinct de celui du partage système ; aucun endpoint, contrat backend ou modèle de requête n'est modifié.
- [x] #6 « Enregistrer » confirme la conservation sans seconde sauvegarde ni relance du traitement ; la croix supprime la sauvegarde créée par cette saisie, en cours de traitement comme terminée, selon la suppression canonique existante, et un échec de suppression est affiché avec une possibilité de réessayer.
- [x] #7 Les gardes existantes restent câblées en amont de la soumission : authentification avec reprise après connexion, quota et minutes, déduplication annoncée comme succès, erreurs réseau et rate limit.
- [x] #8 Une même saisie ne peut pas être soumise deux fois (cycle de vie de l'écran, retour d'authentification), tandis qu'une nouvelle saisie volontaire repart.
- [x] #9 npm run lint et npm run typecheck passent dans mobile/.
- [x] #10 mobile/MANUAL_TEST_CHECKLIST.md et docs/testing/manual-e2e-validation-matrix.md couvrent le nouveau parcours : nouveaux cas SI-xx décrits, total de la catégorie Share Intake et grand total du Results Summary mis à jour en conséquence.
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### What changed

**`mobile/src/components/UrlEntryDialog.tsx`** (new) is the entry surface: a centred
RN `Modal` card, modelled on `RenameDialog` because it is the same thing — one field
reached from a menu, over the screen it was opened from. `Alert.prompt` was never an
option (iOS-only). The field is `keyboardType="url"`, `autoCapitalize="none"`,
`autoCorrect={false}`, `spellCheck={false}`, single-line, `returnKeyType="go"`;
pasting is the keyboard's own long-press paste. There is deliberately **no** "Paste"
button: reading the clipboard needs `expo-clipboard`, which is a native module and
therefore a new build — `mobile/package.json` is untouched (AC#2). Validation and
submission belong to the caller, so a refusal leaves the typed text in place. The
input is pinned `textAlign: "left"` / `writingDirection: "ltr"` so an Arabic UI does
not reorder the address.

**`mobile/src/components/AddSourceSheet.tsx`** gained `onEnterUrl` and a first row
(`link-outline`, `add-source-url`), above the file and photo rows — the link is what
the product is about, and it was the one intake with no way in from the app itself.
It goes through the existing `runAfterClose` deferral like the two pickers: an RN
`Modal` is presented on the very controller the sheet is leaving, so raising one over
a dismissing one is the same iOS conflict as a system picker.

**`mobile/app/(tabs)/inbox.tsx`** hosts the dialog rather than a new router screen.
A dedicated `app/add-url.tsx` route was considered and rejected: the provider owns
navigation (`navigateToConfirmation` pushes), so a route would stack two modals — the
way back from `/share-confirmation` would land on a filled-in add-url screen — and an
expired session would `router.replace("/(auth)/login")` from a modal route. Hosted by
the inbox, the redirect and the push both happen from the inbox route, exactly as they
already do for a picked file. `handleSubmitUrl` runs `validateShareIntentPayload` and,
on failure, sets `addUrl.error.invalid` and returns: no save, no navigation (AC#3). A
`urlHandedOver` ref swallows a second tap on Add landing in the same frame as the
first, and is reset on every opening, so a new deliberate entry starts over (AC#8).

**`mobile/src/contexts/ShareIntentContext.tsx`** takes the URL through the exact path
task-378 built, rather than a variant of it:

- `ShareIntakeOrigin` gained `"url-entry"`, and the binary `origin === "share"` test
  is replaced by an exported `ingestsOnArrival(origin)` predicate. That test conflated
  two different questions — *who sent this* and *is it already processing* — and a
  typed URL answers them differently. Every task-378 behaviour (auto-start effect,
  Save-confirms, X-deletes, retry, the folder row staying live) now keys off the
  predicate and is inherited untouched (AC#6, AC#7).
- `shareSourceApp()` became `sourceAppFor(origin)`, returning `app-url-entry` for a
  typed URL and the two unchanged platform values for a share (AC#5). `source_app` is
  `Optional[str]` server-side, so this is a new *value*, not a contract change — no
  endpoint, request model or platform list was touched.
- `startUrlEntry(url)` parks the URL in `pendingIntakeRef` and calls
  `resumePendingIntake`, the same way `startLocalUpload` parks a file, so the auth
  guard is shared: an expired session signs the user in and the URL is applied on the
  way back. The submission is fired by the existing effect, not from `startUrlEntry`,
  which is what keeps the return from the login screen from adding a second save.
- `applyUrlEntry` sets the intake to `ready` with `contentType: "url"`, so the effect
  submits on the first frame and the confirmation screen opens over a run already
  under way (AC#4).

**`mobile/app/share-confirmation.tsx`** has no `isShare` left: `startedOnArrival =
ingestsOnArrival(intake.origin)`, and the auto-dismiss, `canSave`, the close button's
label, the success branch and the folder row's `disabled` all read that instead.

### Nuances worth knowing

- **Deduplication wording.** `IngestUrlResponse` carries no `deduplicated` flag —
  `POST /api/media/ingest-url` folds a duplicate server-side and answers 200 with the
  existing `media_item_id`. So a re-typed URL is announced as a plain success, which
  is the pre-existing behaviour of every URL share; the "already in your inbox"
  wording only ever came from the shared-content endpoints, which do return the flag.
  Surfacing it for URLs would need a backend response field, and the task excludes
  backend changes.
- **One error string, not four.** `validateShareIntentPayload` can only return
  `empty_payload` on a blank field, which the disabled Add button already prevents, so
  a single `addUrl.error.invalid` covers every reachable refusal.
- **No automated tests were written**, per the project rule. The 7 new SI cases in
  `docs/testing/manual-e2e-validation-matrix.md` (SI-16…SI-22, Share Intake 15 → 22,
  TOTAL 100 → 107, SI-16 added to the critical path) and the new subsection in
  `mobile/MANUAL_TEST_CHECKLIST.md` are what covers the journey (AC#10).
- **The owner note is out of reach from the worktree**: validating on a build (article
  URL then YouTube URL, iOS and Android, processing started before Save, X during and
  after processing) needs a device and a deployed backend. It is a note, not an AC.

### Verification

`cd mobile && npm run typecheck` — clean. `cd mobile && npm run lint` — 0 errors, 1
warning, pre-existing in `src/services/purchaseService.ts`, untouched here.
<!-- SECTION:NOTES:END -->
