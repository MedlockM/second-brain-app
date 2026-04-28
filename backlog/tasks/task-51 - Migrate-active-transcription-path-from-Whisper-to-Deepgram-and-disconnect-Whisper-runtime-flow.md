---
id: task-51
title: >-
  Migrate active transcription path from Whisper to Deepgram and disconnect
  Whisper runtime flow
status: Done
assignee: []
created_date: '2026-03-01 21:05'
updated_date: '2026-03-03 20:59'
labels:
  - backend
  - workers
  - infra
  - transcription
  - deepgram
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement Deepgram as the active transcription worker path, reroute download queue output to Deepgram queue, keep Whisper worker code available for future fallback, and disable Whisper from active workflow/scaling. Update infra (queues/scaling/monitoring), API transcript source contract, env/config, and relevant docs/runbooks.
<!-- SECTION:DESCRIPTION:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented active transcription migration to Deepgram with new worker `media_summarizer/workers/transcription/deepgram_worker.py` (sync API mode, retryable/non-retryable error split, S3 transcript upload, completion/failure events).

Rerouted runtime flow in `workers/download_worker.py` from `transcription-queue` to `DEEPGRAM_TRANSCRIPTION_QUEUE` (`deepgram-transcription-queue`).

Added Deepgram env/config wiring in `.env.example`, `docker-compose.dev.yml`, and `core/config.py`.

Infra updates applied for queue/scaling/monitoring: localstack init + localstack terraform queue resources, scaling controller queue mapping, scaling terraform deepgram queue/task/secret/alarm wiring, deploy script Deepgram secret requirement, scaling docs/tests alignment.

Whisper worker code and transcription queue remain present for future fallback; active scaling no longer targets the Whisper transcription queue.

API/contract docs updated to expose transcript source `deepgram` for audio (`api/endpoints/media.py`, `api/models/media_contracts.py`, `docs/CANONICAL_MEDIA_API_CONTRACT.md`, front shared type).

Added ops runbook `docs/DEEPGRAM_INCIDENT_RUNBOOK.md` for auth/rate-limit/timeout/DLQ incidents.

Validation performed: AST parse OK on modified Python files; targeted grep confirms active queue/source reroute. Terraform fmt/check not run because terraform binary is unavailable in this environment.

Post-implementation adjustment: Deepgram worker now uses direct `audio_url` payload (`{"url": "..."}`) to Deepgram `/v1/listen`, and nominal routing bypasses `audio-download-queue` end-to-end. Download worker remains in repository for fallback-only future use and is no longer part of active scaling/queue flow.

Verification hardening pass completed: fixed `/api/v1/podcasts/submit` legacy behavior so RSS/feed URLs are routed to `PODCASTINDEX_RESOLUTION_QUEUE` (enclosure resolution first) while direct audio URLs are routed to `DEEPGRAM_TRANSCRIPTION_QUEUE`. Added missing Deepgram runtime placeholders in `.env.prod` and corrected `.env.dev` Deepgram key assignment syntax (`DEEPGRAM_API_KEY=...`).

Follow-up fixes applied from verification report: (1) `infrastructure/terraform/scaling.tf` now provisions queue name `podcastindex-resolution-queue` (via existing `rss_resolution` resource), includes it in queue alarms and outputs; (2) `infrastructure/localstack/init-aws.sh` now creates `podcastindex-resolution-queue` + DLQ and optional redrive policy; (3) `infrastructure/terraform/monitoring.tf` queue backlog widget now targets actual queue names (`podcastindex-resolution-queue`, `deepgram-transcription-queue`, `summarization-queue`) and failure/log widgets were aligned to active workers. Additionally tightened `/api/v1/podcasts/submit`: Deepgram direct path is now only for URLs that look like audio files; all other URLs route to `PODCASTINDEX_RESOLUTION_QUEUE`.

Additional safety guard: `deepgram_worker.call_deepgram_api` now rejects `audio_url` values that look like feed URLs (`*.rss`, `*.xml`) before calling Deepgram, preventing accidental RSS URL submission to the Deepgram API.
<!-- SECTION:NOTES:END -->
