---
id: task-52
title: >-
  Align remaining share-first ingestion scope on Deepgram and retire Whisper
  assumptions
status: Done
assignee:
  - '@codex'
created_date: '2026-03-15 20:37'
updated_date: '2026-03-17 15:41'
labels:
  - backend
  - docs
  - ingestion
  - transcription
  - deepgram
dependencies:
  - task-51
  - task-30
  - task-31
  - task-54
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Track and complete the remaining migration work so YouTube, Instagram, and TikTok ingestion paths consistently target Deepgram for audio transcription and no active share-first implementation scope depends on self-hosted Whisper assumptions. The active runtime migration was already completed in task-51; this follow-up task covers the residual alignment work across implementation guidance, connector expectations, and connector delivery for the remaining share-first platforms, including the distinct Instagram and TikTok connector tasks.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 No active share-first YouTube, Instagram, or TikTok ingestion path relies on self-hosted Whisper as the intended audio transcription target.
- [x] #2 Connector-level fallback behavior and transcript source metadata are aligned on Deepgram for audio transcription and remain consistent with the approved ADRs.
- [x] #3 Residual implementation guidance for share-first ingestion no longer describes Whisper as the target solution for YouTube or social-video audio fallback.
- [x] #4 The migration scope is bounded so it does not duplicate the already completed active runtime switch tracked in task-51.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Align public transcript-source contracts on Deepgram by removing `whisper` from canonical backend/frontend documentation and normalizing legacy runtime exposure in `GET /api/media/{media_item_id}`.
2. Update share-first architecture documentation to reflect the actual dedicated YouTube/Instagram/TikTok connector paths, including `tiktok.default` and Deepgram-only audio fallback behavior.
3. Update the mobile implementation plan sections that still describe pre-implementation connector state and outdated task status for `task-30`, `task-31`, and `task-54`.
4. Regenerate runtime `openapi.json` from the FastAPI app and run targeted validation (`rg`, Python compile/import smoke) to confirm no public share-first contract still exposes Whisper as the nominal audio target.
5. Record implementation notes and acceptance-criteria completion in Backlog, explicitly bounding scope to alignment work and not removal of the legacy Whisper fallback preserved by `task-51`.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Aligned public share-first transcript-source contracts on Deepgram by removing `whisper` from the canonical backend/frontend `TranscriptInfo.source` documentation and by normalizing legacy `whisper` metadata exposure in `GET /api/media/{media_item_id}` back to the existing Deepgram public default for non-article media.

Updated share-first implementation guidance to match the actual runtime: `docs/MEDIA_INGESTION_CORE_ARCHITECTURE.md` now lists `tiktok.default`, documents the dedicated TikTok queue-first worker path, and keeps `social.default` only as a generic non-active resolver for future/non-share-first use.

Updated `docs/MOBILE_APP_IMPLEMENTATION_PLAN.md` to reflect the current backend state (article/YouTube/Instagram/TikTok connectors already exist), replaced the outdated generic social-video adapter reference with dedicated Instagram/TikTok resolver references, and corrected roadmap status for completed connector tasks (`task-29`, `task-30`, `task-31`, `task-54`).

Regenerated runtime `openapi.json` from the FastAPI app and validated the final contract surface: no `whisper` string remains in the targeted public/canonical files; Python compile checks passed using a temporary `PYTHONPYCACHEPREFIX`; targeted grep confirmed YouTube/TikTok still emit `native_transcript` on native success and enqueue only fallback audio to `DEEPGRAM_TRANSCRIPTION_QUEUE`.

Scope remained explicitly bounded to alignment work for `task-52`; the legacy Whisper fallback artifacts preserved by `task-51` (worker code, docker service, infra fallback references) were intentionally left untouched.
<!-- SECTION:NOTES:END -->
