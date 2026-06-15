---
id: task-206
title: >-
  Unify share confirmation modal: same collection/tags UI for all ingestion
  sources
status: Done
assignee: []
created_date: '2026-06-15 15:17'
updated_date: '2026-06-15 18:06'
labels:
  - mobile
  - backend
  - refactor
  - ingestion
  - share-intent
dependencies:
  - task-208
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Contexte

Le modal de confirmation de partage (`mobile/app/share-confirmation.tsx`) doit afficher le même bloc d'organisation (Collection + Tags) **quelle que soit la source d'ingestion** : URL, texte WhatsApp, vocal WhatsApp, et toute future source. Aujourd'hui, ce bloc n'est rendu que pour le cas `url` ; les flux `text` et `audio` (partage WhatsApp) montrent uniquement la carte de prévisualisation, sans possibilité de ranger le media dans une collection ou de lui attacher des tags.

## Problème observé

Quand l'utilisateur partage un vocal WhatsApp vers l'app, le modal de share s'ouvre correctement mais le bloc Collection/Tags est absent. Le media est créé "Non trié" et sans tags, et l'utilisateur doit ouvrir l'item après ingestion pour l'organiser manuellement — ce qui casse la promesse UX d'un seul modal unifié à la capture.

## Cause racine (3 couches)

1. **UI** — `share-confirmation.tsx` ne rend `OrganizationControls` que dans la branche `url` du `switch` sur `intake.contentType`. Les branches `audio` et `text` retournent tôt avec uniquement la `*PreviewCard`.
2. **Service mobile** — `ShareIntentContext.submitSharedContent` n'inclut pas `selectedFolder`/`selectedTags` dans ses dépendances ni dans son payload. `SharedContentService.ingestSharedText` / `ingestSharedAudio` n'ont aucun paramètre folder/tags.
3. **Backend** — `POST /api/media/ingest-shared-content` (dans `media_summarizer/api/endpoints/media.py`) n'expose pas de champs `Form` `folder_id`/`tag_ids`. Le domaine `IngestSharedContentRequest` ne les transporte pas, et le `ProcessingJob` créé par le use-case est toujours en folder par défaut, sans tags.

À comparer avec `POST /api/media/ingest-url` qui résout le folder, valide les tags utilisateur et les pose sur le `ProcessingJob` (`media.py` ~ lignes 530-597).

## Objectif

Unifier le flux derrière un modèle unique : peu importe la source (URL, texte, audio, futurs formats), le modal de share affiche les mêmes contrôles d'organisation, le user peut choisir collection + tags avant de soumettre, et ces choix sont persistés sur le media créé.

Le design est déjà clair (on duplique ce qui existe pour `ingest-url`), donc pas de benchmark requis.

## Hors-scope

- Création de nouveaux types de partage (rester sur les 3 existants : url / text / audio).
- Modification du flux d'upload audio in-app (`/upload-audio`) — il accepte déjà `tag_ids` ; vérifier la cohérence mais ne pas refactorer.
- Reorganization post-ingestion (déjà couverte par le détail media).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 UI : le bloc OrganizationControls (Collection + Tags) s'affiche dans le modal share-confirmation pour les 3 contentType (url, text, audio) dans les états ready et submitting
- [ ] #2 UI : la sélection de collection et de tags via les écrans `media/collection?mode=share` et `media/tags?mode=share` fonctionne identiquement pour les 3 contentType
- [ ] #3 Mobile service : SharedContentService.ingestSharedText et ingestSharedAudio acceptent et transmettent folder_id (string|null) et tag_ids (string[]) dans le multipart form-data
- [ ] #4 Mobile service : ShareIntentContext.submitSharedContent passe selectedFolder?.id et selectedTags.map(t=>t.id) au service, et inclut ces deux valeurs dans les dépendances du useCallback
- [ ] #5 Backend : POST /api/media/ingest-shared-content accepte les champs Form folder_id (Optional[str]) et tag_ids (Optional[str] JSON-encoded array, comme /upload-audio) avec la même validation que /ingest-url (folder existe, tags appartiennent à l'utilisateur, MAX_TAGS_PER_MEDIA respecté)
- [ ] #6 Backend : le folder_id et tag_ids résolus sont posés sur le ProcessingJob créé par le use-case ingest_shared_content, dans la même fenêtre de transaction que la création du job
- [ ] #7 Backend : si folder_id est absent, le default folder de l'utilisateur est utilisé (cohérence avec /ingest-url)
- [ ] #8 Tests : un test d'intégration backend vérifie qu'un POST /ingest-shared-content avec folder_id + tag_ids crée un ProcessingJob avec ces valeurs (un cas pour text, un cas pour audio)
- [ ] #9 Tests : les erreurs de validation (folder inexistant, tag non possédé, > MAX_TAGS_PER_MEDIA) renvoient HTTP 400 avec un message clair, comme /ingest-url
- [ ] #10 Pas de régression : un partage URL continue de fonctionner exactement comme avant (folder + tags pris en compte)
- [ ] #11 Pas de régression : un partage text/audio sans folder ni tags continue de fonctionner (default folder, pas de tags)
<!-- AC:END -->
