---
id: task-125
title: Audit JobStatus.SUMMARIZING and JobStatus.NOTIFYING for dead code removal
status: To Do
priority: low
labels: [tech-debt, backend]
created: 2026-06-09
---

# Audit JobStatus.SUMMARIZING and JobStatus.NOTIFYING for dead code removal

## Context

After task-122 and task-123, the summarization worker no longer sets `JobStatus.SUMMARIZING` on the `ProcessingJob`. The only remaining caller of `mark_summarizing()` outside of the model itself is the newsletter worker (`newsletter/worker.py`).

`JobStatus.NOTIFYING` was used when the old email notification step ran after summarization. Since task-102 removed the email notification worker, `mark_notifying()` may have no callers.

These statuses are still referenced in:
- `ProcessingJob.is_processing()` (includes SUMMARIZING and NOTIFYING)
- `ProcessingJob.get_progress_percentage()` (maps both to progress %)
- The `JobStatus` enum itself

## Acceptance Criteria

1. Confirm whether `JobStatus.SUMMARIZING` is still used by any active code path (check newsletter worker usage).
2. Confirm whether `JobStatus.NOTIFYING` has any active callers.
3. If both are dead, remove them from the enum, the model methods, and any frontend/mobile references.
4. If SUMMARIZING is still needed for the newsletter worker, document why and leave it.
5. Update any progress percentage logic if statuses are removed.

## Key Files

- `media_summarizer/core/models/processing_job.py`
- `media_summarizer/workers/newsletter/worker.py` (may still use `mark_summarizing`)
- Mobile app status display code (if any maps these status strings)
