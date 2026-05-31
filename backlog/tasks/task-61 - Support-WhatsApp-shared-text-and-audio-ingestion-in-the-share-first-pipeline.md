---
id: task-61
title: Support WhatsApp shared text and audio ingestion in the share-first pipeline
status: To Do
assignee:
  - '@codex'
created_date: '2026-03-20 21:50'
updated_date: '2026-05-31 21:31'
labels:
  - mobile
  - backend
  - ingestion
  - whatsapp
dependencies:
  - task-37
  - task-38
  - task-93
  - task-41
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Support end-to-end ingestion of content shared from WhatsApp so a user can forward either a text message or an audio message from WhatsApp into Media Summarizer and obtain a trackable media item in the share-first flow. The feature must cover the real payload shapes delivered by mobile share surfaces instead of assuming a URL-only entrypoint.

## ⚠ Backend slice already done — DO NOT redo

Audit code 2026-05-31 confirme que la **slice backend** est intégralement implémentée et figée. **Ne pas y toucher** sauf adaptation marginale dictée par un payload réel observé sur device :

- Endpoint `POST /api/media/ingest-shared-content` (multipart text/audio) : opérationnel dans `media_summarizer/api/endpoints/media.py` + use-case `build_default_ingest_shared_content_use_case` câblé dans `media_summarizer/core/media_ingestion/wiring.py:86`.
- Domaine étendu : `SourcePlatform.WHATSAPP` (`domain.py:40` + `media_contracts.py:40`), `MediaType.SHARED_TEXT` (`domain.py:27`), `staged_audio_s3_key` / `audio_s3_key` / `raw_text` sur `ResolvedMedia` (`domain.py:96-131`).
- Orchestrator (`adapters/orchestrators.py:212, 238-316`) gère :
  - path `raw_text` → upload transcript S3 + mark `completed` immédiat + publish `episode_completion_status` (cohérent avec les autres connecteurs).
  - path `audio_s3_key` → enqueue Deepgram avec la clé S3 staged (worker Deepgram accepte déjà cette branche depuis longtemps).
- Le path `audio_url` distant existant n'est pas modifié.

## Scope restant

1. **Mobile Android share entrypoint** : capturer un text-share et un audio-file-share venant de WhatsApp, faire le multipart `POST /api/media/ingest-shared-content` avec les bons champs (`source_platform=whatsapp`, fichier audio en multipart-file ou texte brut).
2. **Mobile iOS share extension** (`mobile/ios-share-extension/ShareViewController.swift`) : étendre pour gérer les types `kUTTypePlainText` / `public.audio` / `public.mpeg-4-audio` / fichier audio générique en plus de l'URL existante.
3. **Hook `useShareIntent.ts`** (`mobile/src/hooks/useShareIntent.ts`) : aujourd'hui il extrait une URL via `extractUrlFromText` et n'a pas de fallback si pas d'URL ni de path pour fichier audio. Ajouter le branchement vers le nouvel endpoint shared-content.
4. **Device validation** : capturer les payloads réels observés sur Android et iOS lors d'un partage WhatsApp (texte simple, texte avec URL, message vocal `.opus` ou autre, message audio fichier joint), documenter MIME types, filename, et différences entre les 2 OS. Ces données doivent guider la logique de dispatch côté hook.
5. **Erreurs et idempotence côté mobile** : payload trop gros, MIME non supporté, double-share rapide → user-facing errors stables, pas de doublons de jobs.
6. **Tests E2E sur device réel** : envoyer un message texte WhatsApp et un message audio WhatsApp depuis l'app WhatsApp vers Media Summarizer, vérifier que le job complet `pending → completed` aboutit et que le contenu est exploitable côté search/artifacts.

## Hors-scope

- **Modifier le contrat backend `POST /api/media/ingest-shared-content`** : il est figé. Si une adaptation est strictement nécessaire à cause d'un payload mobile observé, isoler le diff backend et le justifier explicitement dans les Implementation Notes.
- Étendre le support shared-content à d'autres apps (Telegram, Signal, etc.) : ce ticket cible uniquement WhatsApp.
- Refactor de la share extension iOS au-delà de l'ajout des types nécessaires.

## Validation

- Sur un device Android : forward d'un message texte WhatsApp → media item créé avec `source_platform=whatsapp` et le texte exploitable.
- Sur un device Android : forward d'un message vocal WhatsApp → media item créé, transcription Deepgram via `audio_s3_key` → `completed`.
- Sur un device iOS : idem (texte + audio).
- Document `docs/SHARED_CONTENT_INGESTION_PROPOSAL.md` (ou équivalent) mis à jour avec les payload shapes réels capturés sur device.

## Contexte fichiers utiles

- `media_summarizer/api/endpoints/media.py` — endpoint shared-content (lecture seule).
- `media_summarizer/core/media_ingestion/use_cases.py` + `wiring.py` — use-case figé.
- `media_summarizer/core/media_ingestion/domain.py` — enums étendues figées.
- `media_summarizer/core/media_ingestion/adapters/orchestrators.py:212-316` — paths `raw_text` et `audio_s3_key` figés.
- `mobile/src/hooks/useShareIntent.ts` — hook à étendre pour fallback non-URL.
- `mobile/ios-share-extension/ShareViewController.swift` — share extension iOS à étendre.
- `mobile/app/share-confirmation.tsx` — écran de confirmation share, à brancher sur le nouveau path.
- `mobile/src/services/shareIntentService.ts` — service unifié à étendre.
- `mobile/src/types/media.ts` — `whatsapp` déjà dans l'enum côté types mobile.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Android and iOS share entrypoints can receive WhatsApp text shares and WhatsApp audio-file shares and preserve enough source metadata for downstream handling.
- [x] #2 A shared WhatsApp text message can create a media item without requiring a URL and makes the source text available to the transcript-first product flow.
- [x] #3 A shared WhatsApp audio message can create a media item from a local shared file payload and route it through the shared transcription pipeline without assuming a remote audio URL.
- [ ] #4 Unsupported, oversized, or malformed shared payloads fail safely with stable user-facing errors and without creating duplicate processing records.
- [ ] #5 Device validation documents the actual payload shapes observed from real WhatsApp text and audio shares on Android and iOS, including share type, MIME/content type, and filename or original name when available.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Extend canonical media contracts with shared-content request/enum additions while keeping the URL-ingestion response shape unchanged.
2. Add a backend endpoint `POST /api/media/ingest-shared-content` that accepts multipart text/audio payloads, stages audio uploads to S3, and builds a shared-content command.
3. Add shared-content domain/use-case wiring and minimal enum/model changes (`whatsapp`, `text`, `shared_text`, `audio_s3_key`) without disturbing URL router behavior.
4. Extend the transitional orchestrator to handle `raw_text` immediate transcript completion and `audio_s3_key` queueing alongside the existing `audio_url` path.
5. Extend the Deepgram worker so it can transcribe either a remote `audio_url` or a staged S3 audio object, then run targeted compile/smoke validation without adding new tests.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Research snapshot captured on 2026-03-20:
- Current runtime is URL-first (`POST /api/media/ingest-url`) with resolver routing based on canonical URL classification.
- There is no current canonical product endpoint for shared raw text or uploaded audio files.
- Current Deepgram worker uses remote URL transcription; WhatsApp audio support will likely require either a file-upload transcription mode or an internal upload/store step before transcription.
- Existing mobile roadmap tasks (`task-37`, `task-38`, `task-39`) cover generic share-first inbox flow and are prerequisites for end-user delivery.
- Real WhatsApp payload shape must be verified on devices and treated as runtime input, not hardcoded from assumptions about file extension.

Added design artifact `docs/SHARED_CONTENT_INGESTION_PROPOSAL.md` capturing the proposed canonical endpoint `POST /api/media/ingest-shared-content`, the minimal domain diff (`SourcePlatform.WHATSAPP`, `MediaFamily.TEXT`, `MediaType.SHARED_TEXT`, `ResolvedMedia.audio_s3_key`), and the recommended Deepgram file-backed path for WhatsApp audio. The proposal intentionally keeps the frozen URL-ingestion baseline untouched and scopes task-61 to a parallel shared-content flow.

Backend shared-content slice implemented on 2026-03-24. Added canonical `POST /api/media/ingest-shared-content` endpoint for multipart text/audio payloads, shared-content domain/use-case/wiring, enum expansions (`whatsapp`, `text`, `shared_text`), staged-audio S3 path, and Deepgram byte-upload transcription fallback via `audio_s3_key` in addition to existing remote `audio_url`.

Shared text path now stores the transcript immediately, marks the job completed locally, and publishes the standard `episode_completion_status` success event so watcher/minute/idempotence finalization stays aligned with other native ingestion paths.

Validation completed with targeted backend smoke checks only: `PYTHONPYCACHEPREFIX=/tmp/pycache .venv/bin/python -m py_compile media_summarizer/api/endpoints/media.py media_summarizer/core/media_ingestion/adapters/orchestrators.py media_summarizer/workers/transcription/deepgram_worker.py media_summarizer/core/media_ingestion/use_cases.py media_summarizer/core/media_ingestion/domain.py media_summarizer/api/models/media_contracts.py` and `.venv/bin/ruff check ... --select F401,I` both passed.

Remaining scope for full task closure: mobile Android/iOS share entrypoints (`task-37`, `task-38`, `task-39`) and device validation capturing real WhatsApp text/audio payload shapes, MIME types, filenames, and platform differences.
<!-- SECTION:NOTES:END -->
