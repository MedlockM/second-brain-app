---
id: task-123
title: Align summarization worker with new artifact_id contract from task-122 — discovered during Phase 4
status: To Do
assignee: []
created_date: '2026-06-09 00:50'
labels:
  - bug
  - backend
dependencies: []
priority: high
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

Discovered during Phase 4 re-test on AWS dev (V1 launch plan §4) **after task-122 was merged**. task-122 successfully refactored `notes`, `flashcards`, and `quiz` workers to use the new `artifact_id` contract and added the `media_artifacts` DynamoDB table. **But it left the `summarization` worker on the legacy `job_id`-based contract**, which now diverges from the API.

## Symptom

After task-122, end-to-end test of all 4 artifact types on a freshly ingested article:

- ✅ `notes` reaches `ready` with `s3_key` set
- ✅ `flashcards` reaches `ready` with `s3_key` set
- ✅ `quiz` reaches `ready` with `s3_key` set
- ❌ `summary` stays in `queued` forever

CloudWatch `/aws/lambda/media-summarizer-worker-summarization` logs show:

```
Missing required fields in message: {
  'artifact_id': 'art_a37af51444424ac9b4cccbf6884c3dea',
  'media_item_id': 'a4b2b856-d5a5-4d4d-be55-e7222849536e',
  'artifact_type': 'summary',
  'parameters': {},
  'transcript_s3_key': 'a4b2b856-d5a5-4d4d-be55-e7222849536e.txt',
  'transcript_bucket': 'media-summarizer-transcripts-125313707865-dev',
  'generation_fingerprint': '...',
  'generator_version': 'summary:gpt-5.4-nano-2026-03-17:prompt-v1',
  ...
}
```

The API now sends a clean `artifact_id`-based message (post task-122) with `parameters`, `generation_fingerprint`, `generator_version`, etc. — **no `job_id`**. But `summarization_worker.py:238-244` still demands `job_id`:

```python
job_id = message_body.get("job_id")
transcript_s3_key = message_body.get("transcript_s3_key")
...
if not all([job_id, transcript_s3_key]):
    raise ValueError("Missing required fields in summarization message")
```

## Root cause

task-122 refactored the API to send a unified `artifact_id`-based contract for all artifact types and updated `notes`, `flashcards`, `quiz` workers (the latter newly added). It missed updating `summarization_worker.py`, which is still organized around `job_id`:

- Line 238: reads `job_id` (no longer present)
- Line 256: `logger.info(f"Starting summarization for job {job_id}")`
- Line 261: `database_async.get_processing_job_by_id(job_id)` — looks up the **processing_jobs** table
- Line 264: `job.mark_summarizing()` then `update_processing_job(job)` — mutates **processing_jobs** to track status
- Line 297-298: `summary_s3_key = f"{job_id}.json"` — uses job_id as S3 filename
- Line 304: uploads to `SUMMARY_BUCKET` keyed by `job_id`
- Line 308: `job.set_summary_location(summary_s3_key)` — persists S3 key on the **ProcessingJob** model
- Line 309: `job.set_processing_duration("summarization", ...)` — same
- Line 322-324: `finalize_usage(job_id, minutes_used)` — minute pool charge keyed by job_id
- Line 328-...: publishes `episode_completed` event keyed by `episode_guid` and `job_id`

The whole worker assumes a 1:1 mapping `job_id → summary`, where the summary is a property of the ProcessingJob, not its own artifact entity.

`notes`, `flashcards`, and `quiz` workers (post task-122) instead use `artifact_id` and persist to the new `media_artifacts` table via `mark_artifact_generating` / `update_artifact_with_s3_key` / `fail_artifact_generation`. They don't touch `processing_jobs`.

## Two possible fix shapes

### Option A — Migrate `summarization` worker fully to `artifact_id` contract

Rewrite `process_summarization_message` to:

1. Read `artifact_id`, `transcript_s3_key`, `transcript_bucket`, `parameters`, etc. (same shape as `notes` worker).
2. Call `mark_artifact_generating(artifact_id)` instead of `job.mark_summarizing()`.
3. Upload to `SUMMARY_BUCKET` keyed by `artifact_id` (or a structured path including `media_item_id`), not `job_id`.
4. Call `update_artifact_with_s3_key(artifact_id, s3_key)` instead of `job.set_summary_location(...)`.
5. Decide what to do with `processing_jobs` mutations and minute pool finalization:
    - Keep them but look up `media_item_id → processing_job` indirectly (via the artifact's `media_item_id` field), OR
    - Move minute pool finalization out of summarization to a different lifecycle hook (e.g. into `media_completed_events` worker), OR
    - Keep summarization-driven processing job mutations and add `media_item_id` lookup at the top of the worker.

This is the **clean** fix and aligns summary with the rest of the artifact pipeline. Match what task-122 did for the other 3 workers.

Required changes:

- Worker rewrite (~50 LOC, mostly removing job-centric logic)
- Verify `Summary` is no longer stored as a property of `ProcessingJob` (or kept for backwards compat but ignored on read)
- Update mobile API consumers if they previously read summary from `ProcessingJob.summary_location` field

### Option B — API maintains backwards-compat by sending `job_id` for `summary` artifacts

Cheap and ugly: API endpoint `POST /api/media/{id}/artifacts` could special-case `artifact_type=summary` and additionally include `job_id=media_item_id` in the SQS message. Worker continues unchanged. **Not recommended** — it freezes the existing inconsistency and makes future maintenance painful. Mention only as a last resort if Option A turns out to be > 1 day of work.

## Recommendation

**Option A** is the right fix. It is consistent with task-122's vision and avoids creating a permanent special case for `summary`. Estimated effort: 2-4h including testing.

## Why does the summary worker do all this and others don't?

It's tech debt, not by design. The summarization worker is a relic from when the app had **only one artifact** (the summary). Notes, flashcards, and quiz arrived later with a cleaner pattern.

### History

The original `JobStatus` enum (`media_summarizer/core/models/processing_job.py:12-...`) is still:

```
PENDING → RSS_RESOLVING → DOWNLOADING → TRANSCRIBING → SUMMARIZING → NOTIFYING → COMPLETED
```

There's a `mark_summarizing()` method but **no** `mark_taking_notes()` / `mark_generating_flashcards()` / `mark_generating_quiz()`. The summary was the **last business step** before `COMPLETED` in the original podcast flow, so the worker took on:

- Updating the job status (`mark_summarizing`)
- Storing the result on the job itself (`set_summary_location`)
- Finalizing minute pool consumption (`finalize_usage`) — this was the natural moment to know how many audio minutes had been processed
- Publishing the `episode_completed` event so watchers (users following the podcast) get notified

When the V1 design switched to **on-demand artifacts**, the `processing_jobs` row reaches `COMPLETED` as soon as the **transcript** is ready, before any artifact. Artifacts are then triggered manually after the job completes. The new workers (notes/flashcards/quiz, post task-122) correctly:

- Don't touch `processing_jobs` (the job is already done by the time they run)
- Use the `media_artifacts` table via `mark_artifact_generating` / `update_artifact_with_s3_key` / `fail_artifact_generation`
- Don't finalize minute pool or publish events (that's not their concern)

The summary worker was never migrated — task-121 only removed the legacy `email` requirement, and task-122 missed it entirely. So `summary` still does work that should now belong elsewhere.

### Owner-recommended disposition for each side responsibility

This is the owner's recommended direction; agents implementing task-123 should validate it before committing.

| Current responsibility | Recommendation | Rationale |
|---|---|---|
| `job.mark_summarizing()` (line 263) | **Remove** | With on-demand design, the job is already `COMPLETED`. Having a `SUMMARIZING` status no longer reflects pipeline reality. Audit `JobStatus.SUMMARIZING` and `JobStatus.NOTIFYING` enum values for removal in a follow-up cleanup task once nothing else references them. |
| `job.set_summary_location(s3_key)` (line 308) | **Remove** | The S3 key now lives on `media_artifacts.s3_key`. Mobile / API consumers should read from `GET /api/media/{id}/artifacts`, not from `processing_jobs.summary_location`. **First verify** that `media_completed_worker.py:91` (other consumer of `set_summary_location`) is still alive — if it's also legacy, the method itself can disappear. |
| `job.set_processing_duration("summarization", duration)` (line 309) | **Move to `media_artifacts.generation_duration_ms`** (or remove) | This is observability metadata, not business data. It should hang off the artifact row, not the job. Cheap option: just log it via `log_event` and don't persist — the cloudwatch metric is enough. |
| `finalize_usage(job_id, minutes_used)` (line 322-324) | **Move to `deepgram_transcription_worker` (or `media_completed_events_worker`)** — important | Critical correctness bug: minute pool consumption must be finalized **when transcription completes**, not when an on-demand summary is generated. Otherwise: (a) if the user never requests a summary, billing never happens; (b) if the user re-generates the summary 5 times (idempotent re-trigger), the user is charged 5×. Bind it to the lifecycle event of the transcript reaching S3. |
| `sqs.send_message(EPISODE_COMPLETED_EVENTS_QUEUE, ...)` (line 328-...) | **Move to `deepgram_transcription_worker` or `media_completed_events_worker`** — important | Same reasoning: an "episode completed" event is about the **media item** being ready (transcript available), not about a summary being generated. Watchers (users following the podcast) want to be notified when there's new content to consume, regardless of whether anyone has clicked "summarize" yet. |

### Scope discipline

Task-123 should **only** do the migration of summarization itself. The minute pool relocation and the event publication relocation can be split into a follow-up task if they make task-123 too big — but mention the **decision** in this task explicitly so they don't get forgotten. If they're left in `summarization_worker` for now, document the resulting bugs (delayed/missing/duplicate minute charges, delayed/missing watcher notifications) clearly in code comments and as a known issue in the V1 launch plan, with a follow-up task created.

## Reproduction

```bash
API=https://jji077bi8e.execute-api.eu-west-3.amazonaws.com
TOKEN=<...>
MEDIA_ID=<an article media that reached completed>

curl -X POST "${API}/api/media/${MEDIA_ID}/artifacts" \
  -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
  -d '{"artifact_type":"summary"}'
# → 202 queued

# Poll: artifact stays at status=queued forever
# CloudWatch logs: "Missing required fields in summarization message"
```

## Out of scope

- Refactoring the artifact pipeline beyond aligning summarization
- Adding summary auto-generation cascading
- Migrating ProcessingJob model away from holding artifact references (separate cleanup)

## References

- task-122 (introduced new artifact_id contract for notes, flashcards, quiz; missed summary)
- task-121 (removed deprecated email field from summary worker — last touch on this worker)
- V1 launch plan §Phase 4
- `media_summarizer/api/endpoints/artifacts.py` (new contract producer)
- `media_summarizer/workers/summarization/summarization_worker.py:230-340` (worker on legacy contract)
- `media_summarizer/workers/notes/worker.py` (post task-122 reference for what summary should look like)
- `media_summarizer/utils/media_artifacts.py` (artifact persistence helpers)
- `media_summarizer/core/services/artifact_service.py` (mark/fail/update helpers)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Decision recorded in this task: Option A (full migration) confirmed by owner
- [ ] #2 `summarization_worker.py` reads `artifact_id` from the message instead of `job_id`
- [ ] #3 Worker uses `mark_artifact_generating` / `update_artifact_with_s3_key` / `fail_artifact_generation` (consistent with notes/flashcards/quiz workers)
- [ ] #4 S3 key in `SUMMARY_BUCKET` uses a stable scheme (e.g. `{artifact_id}.json` or `{media_item_id}/{artifact_id}.json`); document choice in this task
- [ ] #5 `ProcessingJob.summary_location` mutations removed from `summarization_worker.py`. Consumers of `processing_jobs.summary_location` (incl. `media_completed_worker.py:91`) audited and migrated to read from `media_artifacts` instead, OR left in place if still needed (with rationale). Owner recommendation: **remove**.
- [ ] #6 `processing_duration["summarization"]` mutation either removed or replaced with a `media_artifacts.generation_duration_ms` column. Owner recommendation: **drop persistence; rely on CloudWatch metric only**.
- [ ] #7 `finalize_usage(job_id, minutes_used)` moved out of `summarization_worker.py`. Owner recommendation: **move to `deepgram_transcription_worker` (or `media_completed_events_worker`)** so minute pool consumption is bound to transcription lifecycle, not to summary generation. If left in summarization for scope reasons, document the known bug (no charge if user skips summary; multiple charges if user re-triggers) and create a follow-up task.
- [ ] #8 `episode_completed` event publication moved out of `summarization_worker.py`. Owner recommendation: **move to `deepgram_transcription_worker` (or `media_completed_events_worker`)** so watchers are notified when content is ready, not when a summary is generated. Same rule as #7: if deferred, document and create follow-up task.
- [ ] #9 `JobStatus.SUMMARIZING` and `JobStatus.NOTIFYING` enum values audited for unused references; if dead, follow-up cleanup task created (do NOT remove inside task-123 to keep scope tight).
- [ ] #10 Lambda image rebuilt + redeployed via `docker buildx build --platform linux/arm64 --provenance=false --sbom=false ...` and `aws lambda update-function-code`
- [ ] #11 E2E re-test on AWS dev: ingest article → reaches `completed` → trigger all 4 artifact types → all 4 reach `ready` with `s3_key` set
- [ ] #12 At least 1 non-article source tested E2E (YouTube or podcast) — confirms minute pool finalization (whether moved or left in place) works on audio sources too
<!-- AC:END -->
