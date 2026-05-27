# Media-Key Per-User Submission Guard Contract

## Purpose

Define how per-user duplicate submission protection works with canonical
URL-based `media_key`.

This contract supports canonical ingestion/runtime endpoints (`task-10`,
`task-22`, `task-23`).

## Runtime Components

- Helper: `media_summarizer/utils/user_media_submissions.py`
- Table: `user_media_submissions` (PK `user_id`, SK `media_key`)

## Decision Semantics (Parity)

`has_user_already_submitted_media(...)` blocks or allows resubmission using
the same decision rules as historical GUID logic:

- Block when previous job completed successfully.
- Block when previous job failed permanently (`retry_count >= max_retries`).
- Allow retry when failed but retry budget remains.
- Block in-progress duplicates.
- Allow retry when the referenced job no longer exists.
- Block conservatively when status cannot be verified.

## Storage Strategy

1. Read from canonical media table only:
   - Query by `(user_id, media_key)`.
2. Write to canonical media table only:
   - Persist `(user_id, media_key, job_id, source)` at accepted submission.

## Integration Contract for Universal URL Ingestion

For canonical ingestion (`task-10`/`task-23`), callers should:

1. Canonicalize incoming URL.
2. Generate deterministic `media_key`.
3. Before creating pipeline work, call:
   - `has_user_already_submitted_media(user_id, media_key)`
4. On accepted submission, record:
   - `mark_user_media_submission(user_id, media_key, job_id, source)`

Expected behavior:

- Duplicate already-completed media is blocked at per-user level.
- Transiently failed prior jobs can be retried.
- In-progress duplicates are blocked.
- Behavior is independent from podcast GUID semantics.
