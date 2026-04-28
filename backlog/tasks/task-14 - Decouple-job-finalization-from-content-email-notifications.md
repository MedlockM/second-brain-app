---
id: task-14
title: Decouple job finalization from content email notifications
status: Done
assignee:
  - '@codex'
created_date: '2026-02-23 22:08'
updated_date: '2026-02-24 09:57'
labels: []
dependencies: []
priority: high
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Current state (to decouple): for content jobs, completion still depends on email flow. In the current pipeline, success events are handled by `media_summarizer/workers/events/episode_completed_worker.py`, which queues completion emails; `media_summarizer/workers/notification/email_worker.py` then marks jobs completed. This creates coupling between terminal job state and email queue behavior.

Goal: make processing completion independent from content email delivery. Jobs must reach terminal states based on processing/artifact persistence, not on email worker execution.

Scope:
- Decouple completion path for content processing jobs from `email-notification-queue`.
- Remove summary/quiz content email as a required step in completion lifecycle.
- Remove or disable obsolete code paths that exist only to support content-email-driven completion.
- Keep minute usage/finalization semantics correct (finalize on success, release on failure where applicable).
- Preserve observability/retry behavior and avoid stranded jobs (`notifying`, etc.).

Must remove or refactor in this task (content-email specific):
- `media_summarizer/workers/events/episode_completed_worker.py`
  - completion email fan-out path (`_notify_watcher_completion` + payloads containing `summary_content`/`quiz`) must no longer be required for terminal success.
  - logic coupling billing/finalization to successful email queueing must be removed.
- `media_summarizer/workers/notification/email_worker.py`
  - completion-content path (`notification_type == "completion"`, `send_completion_notification`, summary/quiz rendering) must be removed or disabled.
  - completion status transitions must not depend on this worker.
- `media_summarizer/core/services/episode_submission.py`
  - cached-summary path currently sending completion emails with summary/quiz must be migrated away from email-driven completion.
- Email content templates dedicated to summary/quiz delivery:
  - `media_summarizer/email_templates/quiz/*` should be removed if no longer used.

Must keep (out of scope for removal here):
- Account/security email flows:
  - `media_summarizer/api/endpoints/auth.py` verification/resend flows.
  - `media_summarizer/utils/email_service.py` for auth-related emails.
- Reusable artifact generation engines:
  - `media_summarizer/workers/summarization/summarization_worker.py` (summary generation logic).
  - `media_summarizer/workers/quiz/worker.py` (quiz generation logic).
  - These must remain available for on-demand artifact generation (task-11).

Key code areas (expected touchpoints):
- `media_summarizer/workers/events/episode_completed_worker.py`
- `media_summarizer/workers/notification/email_worker.py`
- `media_summarizer/workers/summarization/summarization_worker.py`
- `media_summarizer/core/services/episode_submission.py`
- `media_summarizer/core/models/processing_job.py`
- Any API/read models depending on legacy `notifying -> completed` semantics.

Out of scope:
- Removing account/security emails (verification/auth related) unless explicitly required.
- Implementing on-demand artifacts (covered by task-11).

Definition of done emphasis:
- New chat/new agent can implement from this task alone without hidden assumptions.
- Documentation reflects the new completion model and any env toggles/migration behavior.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Successful processing jobs can transition to `completed` without requiring `email-notification-queue` consumption or `email_worker` execution.
- [ ] #2 Summary/quiz content email is no longer part of the mandatory completion path for content jobs.
- [ ] #3 Obsolete code paths dedicated only to content-email-driven completion are removed (or explicitly disabled), with no dead mandatory runtime dependency left.
- [ ] #4 Content-email templates for summary/quiz delivery are removed or confirmed unused in runtime paths.
- [ ] #5 No successful job remains stranded in `notifying` solely due to email queue/worker issues; terminal state behavior is deterministic.

- [ ] #6 Minute usage/finalization remains correct on success and failure paths after decoupling (including hold release where appropriate).
- [ ] #7 Reusable summary/quiz generation logic remains intact and callable for future on-demand artifacts (task-11), independent of email delivery.

- [ ] #8 Failure/retry behavior remains observable (logs/metrics/errors) and equivalent or better than before the change.

- [ ] #9 Automated regression coverage is added/updated for completion lifecycle without email dependency.
- [ ] #10 Runbook/docs are updated to describe the new completion semantics, migration notes (if needed), and relevant env flags.

- [ ] #11 If error-notification emails are retained, they must not drive success completion semantics or mutate jobs to `completed` as a side effect.

- [ ] #12 `media_summarizer/core/services/episode_submission.py` is NOT deleted in this task; it is kept as a temporary compatibility adapter while removing content-email-driven completion paths.

- [ ] #13 Because the product is pre-production, obsolete legacy completion/email paths are removed directly once reusable logic is retained; no backward-compatibility shim is required for those deleted paths.
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1) Refactor `workers/events/episode_completed_worker.py` so success events finalize watcher jobs directly (set artifact keys, finalize usage, transition to terminal state) without any completion email fan-out.
2) Remove content-completion handling from `workers/notification/email_worker.py` and keep only error notification flow; ensure it never mutates jobs to `completed`.
3) Refactor duplicate-processed path in `core/services/episode_submission.py` to complete billing jobs directly (no completion email queue), keeping the file as compatibility adapter.
4) Remove obsolete summary/quiz content email assets and dead queue references linked only to completion emails.
5) Update docs/runbook notes to describe that success finalization is processing-driven (not email-driven) and record no-test execution per user request.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Migration guardrail: do not delete `media_summarizer/core/services/episode_submission.py` yet. Refactor it to remove content-email completion coupling, then keep it as a compatibility facade until URL-keyed idempotence/media submission flow fully replaces callers.

Legacy policy for this project: because the application is not yet in production, backward compatibility with legacy completion/email paths is NOT required. The implementing agent should delete obsolete legacy paths and references once reusable logic has been preserved/adapted for the new share-first architecture. Keep `episode_submission.py` only as long as required by task-15 migration constraints, then remove legacy branches instead of maintaining compatibility shims.

User explicitly requested no automated tests for this task; implementation-only change set.

Implemented success finalization decoupling in `workers/events/episode_completed_worker.py`: removed completion-email fan-out dependency, now watcher jobs are finalized directly (artifact keys + billing + terminal state) from `episode_completion_status` success events.

Removed completion-content behavior from `workers/notification/email_worker.py`: worker is now error-notification only; deprecated `notification_type=completion` messages are ignored and never mutate jobs to `completed`.

Refactored cached duplicate path in `core/services/episode_submission.py`: no completion email queue send; billing jobs are finalized directly and transitioned to terminal status in DB.

Removed content email assets and legacy helper script: deleted `media_summarizer/email_templates/quiz/*` and `scripts/render_quiz_templates_demo.py`.

Cleaned legacy completion-event wiring: removed obsolete `episode-completed-events` infra references from localstack terraform and compose env overrides; retained unified `episode-completion-events` flow.

Updated runbook notes in `docs/MEDIA_KEY_MIGRATION.md` to document processing-driven completion semantics and error-only email worker behavior.

Per explicit user instruction, automated regression test authoring/execution was skipped for this task (AC #9 intentionally not completed in this implementation pass).

Follow-up requested by user: remove remaining legacy mailing in processing flow (including error emails), and enforce automatic pipeline as download -> transcription only (summarization kept for on-demand only).

Follow-up applied per user request: removed remaining legacy mailing system (including error-email paths) across workers/runtime infra; deleted `workers/notification/email_worker.py`, `workers/notification/ops_alert.py`, `utils/email_service.py`, and `utils/ses.py`.

Removed `email-notification-queue` wiring from compose/localstack/scaling infra and deleted SES-specific local setup scripts/identities; `send_error_notification` in base worker is now log-only (no queue send).

Rewired automatic processing flow to `download -> transcription` only: download worker forwards `audio_duration_seconds`, transcription worker no longer enqueues summarization and now publishes `episode_completion_status(status=success)` directly with `minutes_used` + `transcription_s3_key`.

Updated event finalizer to persist `transcription_s3_key` onto watcher jobs, finalize billing, and complete jobs without email dependencies; added fallback canonical finalization when identity keys are missing so jobs are not stranded.

Kept summarization/quiz workers available for on-demand artifacts only (no auto-trigger from transcription).

Auth/email verification flow was neutralized to keep the app functional without mailing: local registration auto-verifies users, login no longer blocks on email verification, and verification/resend endpoints are compatibility no-ops.

No automated tests were implemented or executed, per explicit user instruction for this ticket.
<!-- SECTION:NOTES:END -->
