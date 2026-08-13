---
id: task-264
title: Add file import and camera capture as mobile ingestion entry points
status: To Do
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
- [ ] #1 Depuis l'inbox, un geste « ajouter » ouvre un choix entre « Importer un fichier » et « Prendre une photo » ; les deux branches sont câblées jusqu'à un appel réseau réel — aucun TODO, aucun écran mort
- [ ] #2 Le picker de fichier n'expose que les extensions acceptées par le backend (documents/images de `DocumentFormat.supported_extensions()` et audio de `_AUDIO_EXTENSIONS`), et route chaque fichier vers le chemin correspondant à son extension
- [ ] #3 Un fichier hors liste ou dépassant `MAX_UPLOAD_SIZE_BYTES` est refusé côté app, avec un message nommant la raison, sans appel réseau
- [ ] #4 La capture photo enchaîne directement sur l'écran de confirmation, sans étape de re-sélection ; un refus de permission caméra affiche un message et laisse l'app utilisable
- [ ] #5 `mobile/app.config.ts` déclare la permission caméra sur les deux plateformes (`NSCameraUsageDescription` côté iOS, permission `CAMERA` côté Android) avec un texte d'usage en anglais, et la config résolue par `npx expo config` les contient
- [ ] #6 L'écran de confirmation unifié sert les deux nouveaux types de contenu (`ShareContentType` étendu) avec la même sélection collection/tags ; aucun second écran de sélection n'est dupliqué
- [ ] #7 Le chemin backend retenu accepte `folder_id` et `tag_ids`, valide que le dossier et les tags appartiennent à l'appelant, applique `MAX_TAGS_PER_MEDIA`, et les transmet à `save_media_for_user` ; aucun chemin d'upload atteignable depuis l'app ne reste sans rangement
- [ ] #8 Un refus de quota (en-tête `X-Quota-Error-Code`) sur ces deux gestes reçoit le même traitement que les sources existantes, CTA paywall incluse
- [ ] #9 `ruff check` et `mypy` passent sur le backend ; `npx tsc --noEmit` et l'ESLint du repo passent sur `mobile/` sans nouvelle erreur ni nouveau warning
- [ ] #10 `docs/CANONICAL_MEDIA_API_CONTRACT.md` décrit les champs ajoutés au chemin d'upload retenu
- [ ] #11 Aucune dépendance npm n'est ajoutée : la caméra passe par `expo-image-picker`, déjà installé. Si l'implémenteur en juge une nécessaire, la justification est écrite dans les Implementation Notes et signalée comme imposant un nouveau build natif
<!-- AC:END -->
