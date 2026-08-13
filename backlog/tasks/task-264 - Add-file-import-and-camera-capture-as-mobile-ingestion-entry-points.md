---
id: task-264
title: Add file import and camera capture as mobile ingestion entry points
status: Done
assignee: []
created_date: '2026-08-13 19:46'
labels:
  - mobile
  - feature
  - ingestion
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Ce qu'on veut

Deux points d'entrée d'ingestion manquent dans l'app : **importer un fichier** depuis le téléphone, et **prendre une photo** qui part à l'ingestion dans la continuité directe de la capture. Aujourd'hui la seule façon de faire entrer un fichier est le share sheet du système.

## Existant, vérifié le 2026-08-13

**Backend — les endpoints d'upload existent et fonctionnent, mais aucun n'est appelé par le mobile :**

- `POST /api/media/upload` (`media_summarizer/api/endpoints/media.py:857`) : multipart `file`, extensions validées par `DocumentFormat.supported_extensions()` (`media_summarizer/core/ports/document_parser.py`) = pdf, docx, pptx, xlsx, jpg, jpeg, png, tiff, tif, bmp, heif, heic. Fait déjà : contrôle de quota, ligne durable `user_media` via `save_media_for_user`, upload S3 `DOCUMENT_BUCKET`, enqueue `DOCUMENT_PARSING_QUEUE`, parsing LlamaParse avec fallback Unstructured — **l'OCR des images est donc déjà couvert** (task-90/91). **N'accepte ni `folder_id` ni `tag_ids`.**
- `POST /api/media/upload-audio` (ligne 1024) : extensions `_AUDIO_EXTENSIONS` (media.py:122) = mp3, m4a, aac, ogg, wav, flac, opus. Accepte `tag_ids` (tableau JSON en champ Form) mais **pas `folder_id`**.
- `POST /api/media/ingest-shared-content` (ligne 1253) accepte, lui, `folder_id` **et** `tag_ids` **et** un `audio_file` multipart, mais son `share_type` est restreint à `text|audio`.
- Plafond commun : `MAX_UPLOAD_SIZE_BYTES`, 50 Mo par défaut (media.py:104), lu depuis l'environnement.
- `save_media_for_user` (`media_summarizer/core/services/durable_media_service.py:107`) accepte déjà `folder_id` et `tag_ids` : le rangement n'est pas à inventer, seulement à transporter.

**Mobile :**

- `expo-document-picker` et `expo-image-picker` sont **déjà** dans `mobile/package.json`, utilisés uniquement par `mobile/app/bug-report.tsx` (pièce jointe d'un rapport de bug, `getDocumentAsync` + `launchImageLibraryAsync`). La caméra est donc accessible via `ImagePicker.launchCameraAsync` sans nouvelle dépendance.
- Aucun service ne poste vers `/upload` ni `/upload-audio` : `mobile/src/services/mediaService.ts` ne connaît que `/api/media/ingest-url`, `sharedContentService.ts` ne connaît que `/api/media/ingest-shared-content`.
- `mobile/app.config.ts` déclare `NSPhotoLibraryUsageDescription` mais **aucune permission caméra** : ni `NSCameraUsageDescription` (iOS), ni permission `CAMERA` côté Android. Sans elles, l'ouverture de la caméra échoue sur un build natif.
- L'écran de confirmation unifié posé par task-206 existe : `mobile/app/share-confirmation.tsx` + `mobile/src/contexts/ShareIntentContext.tsx`, dont `ShareContentType` vaut aujourd'hui `"url" | "text" | "audio"`.
- Aucun geste « ajouter » dans l'app : `mobile/app/(tabs)/inbox.tsx` ne porte qu'un bouton vers le digest.

Pas de tâche benchmark : le pipeline de parsing/OCR est déjà choisi et validé (task-90 → task-91), les pickers sont déjà installés, il n'y a aucun choix technologique ouvert.

## Décisions de l'owner (2026-08-13)

1. **Périmètre des formats : documents + images + audio.** Les deux endpoints d'upload sont branchés dans la même passe — le câblage est le même et `/upload-audio` (task-142) cesse d'être du code jamais appelé.
2. **Rangement : les deux gestes passent par l'écran de confirmation collection/tags** avant l'envoi. « La photo s'importe dès qu'elle est prise » se lit donc : la capture **enchaîne directement** sur la confirmation, sans retour à la galerie ni deuxième sélection de fichier ; le Save déclenche l'envoi. Pas de mode d'envoi silencieux. L'owner a tranché en connaissance de l'écart avec la formulation initiale, au bénéfice de l'uniformité avec toutes les autres sources d'ingestion.

Conséquence directe : `folder_id` (et `tag_ids` pour `/upload`) doivent traverser jusqu'à la ligne `user_media`.

## Scope

1. **Point d'entrée** : un geste « ajouter » accessible depuis l'inbox, ouvrant le choix entre « Importer un fichier » et « Prendre une photo ».
2. **Import de fichier** : picker filtré sur les extensions réellement acceptées par le backend (les trois listes ci-dessus), avec routage vers le bon chemin selon l'extension. Refus explicite et message clair pour tout le reste, y compris le dépassement du plafond, détecté avant l'envoi.
3. **Prise de photo** : capture puis enchaînement direct sur la confirmation. Permissions caméra déclarées dans `app.config.ts` sur les deux plateformes, avec un texte d'usage **en anglais** cohérent avec le reste de l'app (task-2), et refus de permission traité sans crash.
4. **Confirmation** : étendre `share-confirmation.tsx` / `ShareIntentContext` aux nouveaux types de contenu plutôt que de dupliquer un second écran de sélection collection/tags.
5. **Backend** : porter `folder_id`/`tag_ids` sur le chemin d'upload retenu jusqu'à `save_media_for_user`, avec la même validation d'appartenance que `/ingest-url` et `/ingest-shared-content` (dossier appartenant à l'appelant, tags appartenant à l'appelant, plafond `MAX_TAGS_PER_MEDIA`). **Le choix entre étendre `/upload` + `/upload-audio` ou faire passer ces gestes par `ingest-shared-content` appartient à l'implémenteur** — la seule contrainte est de ne pas créer un troisième dialecte de rangement.
6. **États visibles** : envoi en cours, succès, échec avec retry, et refus de quota traité comme les autres sources (`mobile/src/lib/quotaError.ts`, CTA paywall posée par task-244).
7. Une entrée importée apparaît dans la médiathèque et suit la progression comme n'importe quelle autre source.

Lien avec task-263 (refonte UI NotebookLM) : cette tâche ajoute un geste dans l'inbox et étend l'écran de confirmation, qui sont deux surfaces que task-263 refondra. Aucune dépendance déclarée dans les deux sens pour ne pas se bloquer mutuellement (task-263 est verrouillée en attente des screenshots de l'owner) — celle qui passe en second absorbe la surface de la première.

## Note à l'owner — hors AC

- **Un nouveau build natif sera nécessaire.** Ajouter les permissions caméra modifie les projets natifs iOS et Android : les dev builds actuels (task-161 iOS, task-163 Android) ne les portent pas, donc la caméra ne s'ouvrira pas avant un `expo prebuild` suivi d'un nouveau `eas build`. À prévoir avant la validation.
- **Validation E2E après merge et push sur `main`** (le backend ne se déploie qu'à ce moment) : importer un pdf, une image, un mp3, prendre une photo ; vérifier l'apparition dans la médiathèque, le rattachement à la collection choisie et aux tags, et le rendu du texte extrait / OCR dans l'onglet Brut (task-69).
- **Le plafond de 50 Mo est une variable d'environnement** (`MAX_UPLOAD_SIZE_BYTES`). Si les photos HEIC de l'iPhone ou des pdf scannés le dépassent, c'est un réglage à revoir, pas un défaut de la tâche.
- **HEIC** : accepté par le backend (mappé sur `IMAGE_HEIF`), mais `expo-image-picker` peut renvoyer un jpeg converti selon les options retenues. Sans impact fonctionnel — juste à savoir si le format affiché n'est pas celui attendu.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Depuis l'inbox, un geste « ajouter » ouvre un choix entre « Importer un fichier » et « Prendre une photo » ; les deux branches sont câblées jusqu'à un appel réseau réel — aucun TODO, aucun écran mort
- [x] #2 Le picker de fichier n'expose que les extensions acceptées par le backend (documents/images de `DocumentFormat.supported_extensions()` et audio de `_AUDIO_EXTENSIONS`), et route chaque fichier vers le chemin correspondant à son extension
- [x] #3 Un fichier hors liste ou dépassant `MAX_UPLOAD_SIZE_BYTES` est refusé côté app, avec un message nommant la raison, sans appel réseau
- [x] #4 La capture photo enchaîne directement sur l'écran de confirmation, sans étape de re-sélection ; un refus de permission caméra affiche un message et laisse l'app utilisable
- [x] #5 `mobile/app.config.ts` déclare la permission caméra sur les deux plateformes (`NSCameraUsageDescription` côté iOS, permission `CAMERA` côté Android) avec un texte d'usage en anglais, et la config résolue par `npx expo config` les contient
- [x] #6 L'écran de confirmation unifié sert les deux nouveaux types de contenu (`ShareContentType` étendu) avec la même sélection collection/tags ; aucun second écran de sélection n'est dupliqué
- [x] #7 Le chemin backend retenu accepte `folder_id` et `tag_ids`, valide que le dossier et les tags appartiennent à l'appelant, applique `MAX_TAGS_PER_MEDIA`, et les transmet à `save_media_for_user` ; aucun chemin d'upload atteignable depuis l'app ne reste sans rangement
- [x] #8 Un refus de quota (en-tête `X-Quota-Error-Code`) sur ces deux gestes reçoit le même traitement que les sources existantes, CTA paywall incluse
- [x] #9 `ruff check` et `mypy` passent sur le backend ; `npx tsc --noEmit` et l'ESLint du repo passent sur `mobile/` sans nouvelle erreur ni nouveau warning
- [x] #10 `docs/CANONICAL_MEDIA_API_CONTRACT.md` décrit les champs ajoutés au chemin d'upload retenu
- [x] #11 Aucune dépendance npm n'est ajoutée : la caméra passe par `expo-image-picker`, déjà installé. Si l'implémenteur en juge une nécessaire, la justification est écrite dans les Implementation Notes et signalée comme imposant un nouveau build natif
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
### Backend path chosen: extend `/upload` + `/upload-audio`

Routing the two gestures through `ingest-shared-content` was rejected: its domain use case only
knows `SharedContentType.TEXT | AUDIO`, so a pdf or a photo would have meant a new share type
travelling through the whole hexagon (domain command, resolver, orchestrator) for content the
document pipeline already handles end to end. The two upload endpoints already do the real work
(quota, durable row, S3, queue, LlamaParse/OCR, Deepgram) — they were only missing the organization
fields.

To honour "do not create a third organization dialect", the folder/tag validation that was inlined in
`ingest_url` and `ingest-shared-content` was factored into one helper, now the only implementation in
the codebase:

- `_parse_form_tag_ids` — decodes the multipart `tag_ids` field (a JSON array; multipart has no array
  type), 400 on anything that is not a JSON array.
- `_resolve_media_organization` — folder exists and belongs to the caller, tags exist and belong to
  the caller, at most `MAX_TAGS_PER_MEDIA` distinct tags; returns `(folder_id, tag_ids)` for
  `save_media_for_user`.

All four ingestion entrypoints (`ingest-url`, `ingest-shared-content`, `/upload`, `/upload-audio`)
now call it, and the three previous inline blocks were deleted. `/upload` gained `folder_id` and
`tag_ids` form fields, `/upload-audio` gained `folder_id` (it already had `tag_ids`, which now goes
through the shared validation instead of its own). In both endpoints the resolver runs **before** the
quota check, so an unusable folder or tag costs nothing to the user's allowance.

### Mobile

- `mobile/src/types/upload.ts` — mirrors the two backend extension lists and
  `MAX_UPLOAD_SIZE_BYTES`; `prepareLocalUploadFile` returns either a `LocalUploadFile` (with the
  `kind` that decides the endpoint) or a rejection naming the reason
  (`unsupported_extension | too_large | empty`). Nothing here touches the network, which is what
  makes AC #3 hold: a refusal costs no upload.
- `mobile/src/services/uploadService.ts` — multipart `fetch` (not `apiRequest`: the boundary must be
  set by the runtime, so Content-Type cannot be provided by us), reusing `parseErrorResponse` /
  `createHttpError` so `X-Quota-Error-Code` survives to the UI.
- `mobile/src/lib/localImport.ts` — the two gestures. The document picker is filtered on
  `UPLOAD_PICKER_MIME_TYPES`, but that filter is advisory on some Android providers, so the picked
  result is re-validated: `prepareLocalUploadFile` is the authoritative gate, not the picker.
  `capturePhotoToImport` requests the camera permission and turns a denial into a normal `error`
  result (different wording depending on `canAskAgain`), so the app stays usable.
- `ShareIntentContext` — `ShareContentType` extended to `"url" | "text" | "audio" | "file" | "photo"`,
  plus `uploadFile` on the intake state and two actions: `startLocalUpload` (opens the confirmation
  screen on the picked file) and `submitUpload` (sends on Save). `uploadFile` is optional on purpose:
  the ~10 existing share-intent state literals stay untouched, and omitting it clears a previous
  import.
- `share-confirmation.tsx` — one screen for the five content types. Added a `FilePreviewCard` and the
  `file` / `photo` branches of `ready` / `submitting` / `success`; the `OrganizationControls` and the
  quota error card with the paywall CTA are the exact same components as for a shared link, so AC #6
  and AC #8 hold without a second selection screen. `media/collection.tsx` and `media/tags.tsx`
  needed no change: in `mode=share` they already read `useShareIntake()`.
- `AddSourceSheet.tsx` — plain RN `Modal` bottom sheet rather than a router screen: it is a two-line
  choice, and the gesture it triggers presents its own full-screen surface right after. The sheet is
  dismissed **before** the picker opens, so on iOS the camera view controller never lands on top of a
  modal that is still up.
- `inbox.tsx` — amber floating add button, the sheet, and the refusal path (`Alert.alert`, the
  precedent set by `bug-report.tsx`). List bottom padding raised so the button never covers the last
  card.

### Display fix that came with the feature

The two upload endpoints store `media_type` `document` / `audio` on the library row, and the list
endpoint returns that value as-is (the URL paths store canonical values, so this only affects
uploads). Without a case for them, an imported pdf rendered as "LINK" with a link icon. Added
`document` / `audio` to the mobile `MediaType` union and the label/icon cases in `inbox.tsx` and
`MediaListCard.tsx` ("DOC" / "AUDIO"). The canonical enum was deliberately left alone: adding a
`document` member would be a contract change well outside this task, and the detail endpoint already
normalizes both values.

### Verified in this run

- `python -m ruff check media_summarizer` → All checks passed.
- `python -m mypy media_summarizer/api/endpoints/media.py` → Success, no issues.
- `mobile: tsc --noEmit` → clean.
- `mobile: eslint . --ext .ts,.tsx` → 0 errors, 10 warnings, all pre-existing and in files this task
  did not touch (same baseline as before the change).
- `mobile: expo config --type public` → `ios.infoPlist.NSCameraUsageDescription` and
  `android.permissions: ["android.permission.CAMERA"]` both present in the resolved config (AC #5).
- No npm dependency added: `mobile/package.json` is untouched (AC #11).

### Out of reach from this worktree

- End-to-end validation (import a pdf / image / mp3, take a photo, check the collection, the tags and
  the extracted text) needs the backend deployed, which happens on push to `main`, and a **new native
  build**: the camera permission changes both native projects, so the current dev builds cannot open
  the camera. Both were already owner notes on this task.
- Whether a given Android file provider actually honours the MIME filter is device-dependent; the
  re-validation on the picked result is what makes the refusal deterministic.
- No automated tests were written: this project forbids them unless explicitly requested, and no AC
  asked for any.

### Left alone on purpose

The share-sheet branch for a non-audio file still answers "This file type is not supported yet."
Widening the iOS share extension and the Android intent filters to documents is a different entry
point from the one this task adds, and rebuilding the extension is out of its scope.
<!-- SECTION:NOTES:END -->
