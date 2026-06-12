---
id: task-198
title: >-
  Implement POST /api/media/ingest-shared-content endpoint to unblock WhatsApp
  text/audio share ingestion
status: Done
assignee: []
created_date: '2026-06-12 16:06'
labels:
  - backend
  - api
  - ingestion
  - whatsapp
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Le flow de partage WhatsApp (texte et audio) vers Media Summarizer est entièrement câblé côté mobile (`ShareIntentContext`, `SharedContentService`, écran `share-confirmation.tsx`) et côté domaine/orchestration backend (`IngestSharedContentUseCase`, branches `raw_text` et `audio_s3_key` de `ProcessingJobSubmissionOrchestrator`, `build_default_ingest_shared_content_use_case`), mais **la route HTTP `POST /api/media/ingest-shared-content` que le mobile appelle n'existe pas** dans `media_summarizer/api/endpoints/media.py`.

Conséquence actuelle : tout partage WhatsApp (texte ou note vocale) vers l'app reçoit un 404 et l'écran de confirmation affiche un état d'erreur. C'est le seul blocage restant sur le flow décrit dans task-61 (Done) — dont les notes d'implémentation affirment à tort que cet endpoint a déjà été ajouté et audité opérationnel (vérifié par grep complet + `git log -S` sur tout l'historique : la string n'a jamais existé dans `endpoints/media.py`).

## Référence de design

Le contrat complet (champs multipart, validation, mapping vers le domaine) est déjà spécifié dans `docs/SHARED_CONTENT_INGESTION_PROPOSAL.md`. Le use-case cible existe déjà et est figé : `build_default_ingest_shared_content_use_case()` (`media_summarizer/core/media_ingestion/wiring.py:92-98`) → `IngestSharedContentUseCase` (`media_summarizer/core/media_ingestion/use_cases.py:93-189`).

## Point d'attention : contrat de réponse

Le proposal doc suggère de renvoyer la forme `IngestUrlResponse` (avec `media_item` + `processing_job` imbriqués). Mais le mobile (déjà figé, ne pas modifier) attend la forme plus simple `IngestSharedContentResponse` définie dans `mobile/src/types/sharedContent.ts:83-89` : `{ media_item_id, status, source_platform, deduplicated?, duplicate_of_media_item_id? }`. L'endpoint doit suivre le contrat attendu par le mobile, pas celui du proposal doc.

## Référence pour le staging audio S3

L'endpoint `/api/media/upload-audio` (`media_summarizer/api/endpoints/media.py:810-982`) montre le pattern attendu : lecture du fichier, validation taille/format, upload vers `AUDIO_BUCKET` via `s3.upload_file_object`, puis enqueue. Le path `share_type=audio` doit produire le `staged_audio_s3_key` (+ `content_hash`) attendus par `IngestSharedContentCommand`.

## Fichiers clés
- `media_summarizer/api/endpoints/media.py` — ajouter la route
- `media_summarizer/api/models/media_contracts.py` — `IngestSharedContentRequest` déjà défini (ligne 213-222) ; vérifier si un nouveau response model est nécessaire
- `media_summarizer/core/media_ingestion/use_cases.py` — `IngestSharedContentUseCase` (figé, ne pas modifier sauf adaptation marginale justifiée et documentée)
- `media_summarizer/core/media_ingestion/adapters/orchestrators.py:293-373` — branches `raw_text` / `audio_s3_key` (figées)
- `mobile/src/services/sharedContentService.ts` — client déjà figé, source de vérité du contrat HTTP réellement attendu (champs FormData envoyés, shape de réponse lue)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 POST /api/media/ingest-shared-content (authentifié) accepte multipart/form-data avec share_type=text, crée un media item via IngestSharedContentUseCase et répond dans la forme IngestSharedContentResponse attendue par le mobile
- [ ] #2 POST /api/media/ingest-shared-content accepte multipart/form-data avec share_type=audio + audio_file, valide MIME/taille, stage le fichier en S3 (content_hash + staged_audio_s3_key) et route vers le path audio_s3_key existant de l'orchestrateur
- [ ] #3 Les payloads invalides (MIME non supporté, fichier vide ou trop gros, champs requis manquants, idempotency_key dupliqué) retournent des erreurs stables exploitables par le mobile sans créer de jobs dupliqués
- [ ] #4 Un partage réel WhatsApp (message texte et note vocale .m4a) depuis un device aboutit à un media item visible dans l'inbox qui atteint completed / ready_for_artifacts
<!-- AC:END -->
