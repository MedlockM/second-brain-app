---
id: task-175
title: Refactor JobStatus vocabulary (generic per-source stages) and drop progress percentage for V1
status: To Do
assignee: []
created_date: '2026-06-10 15:00'
labels:
  - tech-debt
  - backend
  - api
dependencies: []
priority: medium
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

The `JobStatus` enum in `media_summarizer/core/models/processing_job.py` was defined when the only ingestion source was a podcast: `PENDING → RSS_RESOLVING → DOWNLOADING → TRANSCRIBING → SUMMARIZING → COMPLETED`. As V1 added other sources (article, document, X, TikTok, Instagram, YouTube), the workers reused the same status names with mismatched semantics:

| Worker | Reality | Status reported today |
|---|---|---|
| `article_extraction_worker` | fetch HTML + parse trafilatura | jumps to `TRANSCRIBING` (no transcription happens) |
| `document_parsing/worker` | LlamaParse / Unstructured (PDF parse) | jumps to `TRANSCRIBING` |
| `x_ingestion_worker` | API X v2 (fetch JSON) | jumps to `TRANSCRIBING` |
| `tiktok_ingestion_worker` | yt-dlp + Apify (metadata + transcript, no file download) | reports `DOWNLOADING` |
| `instagram_ingestion_worker` | Apify scraper (no file download) | reports `DOWNLOADING` |
| `deepgram_worker` | actual audio transcription | `TRANSCRIBING` |
| `podcastindex_resolution_worker` | RSS resolution | `RSS_RESOLVING` (correct) |

Two problems:

1. **Misleading vocabulary**: `DOWNLOADING` and `TRANSCRIBING` describe podcast-specific operations that don't match what TikTok/Instagram/article/document/X workers actually do. Surfaces during debug — task-167 was hampered by reading "downloading 25%" and assuming a file download was happening when only metadata extraction was running.
2. **Inconsistent stages per source**: each worker visits a different subset of stages. The barre de progression (0/10/25/50/80/100) jumps non-uniformly: an article job's progress goes 0 → 50 → 80 → 100, a podcast job 0 → 10 → 25 → 50 → 80 → 100. We don't expose progress in the V1 UI, so the percentages have no consumer today.

## Decision (owner, 2026-06-10)

- **Refactor the vocabulary** to a generic, per-source-applicable set of stages.
- **Drop the percentage entirely** — V1 has no progress bar, the percentage field is dead weight.

## Target stages

Generic enum applicable to every V1 source:

```
PENDING → EXTRACTING → TRANSCRIBING → SUMMARIZING → COMPLETED
                                    ↘ FAILED / CANCELLED
```

Each source visits **only the stages applicable to it**, no fake transitions:

| Source | Path |
|---|---|
| Article (HTML) | `PENDING → EXTRACTING → SUMMARIZING → COMPLETED` |
| Document (PDF) | `PENDING → EXTRACTING → SUMMARIZING → COMPLETED` |
| X (text tweet) | `PENDING → EXTRACTING → SUMMARIZING → COMPLETED` |
| YouTube (with native captions) | `PENDING → EXTRACTING → SUMMARIZING → COMPLETED` |
| TikTok (yt-dlp / Apify, native transcript) | `PENDING → EXTRACTING → SUMMARIZING → COMPLETED` |
| Instagram (Apify native caption) | `PENDING → EXTRACTING → SUMMARIZING → COMPLETED` |
| Instagram (Apify → Deepgram fallback) | `PENDING → EXTRACTING → TRANSCRIBING → SUMMARIZING → COMPLETED` |
| Audio upload (mp3 direct) | `PENDING → TRANSCRIBING → SUMMARIZING → COMPLETED` |
| Podcast (PodcastIndex → audio URL → Deepgram) | `PENDING → EXTRACTING → TRANSCRIBING → SUMMARIZING → COMPLETED` |

Semantic rules:
- **EXTRACTING** = "obtain text or media from the source" (fetch HTML, parse PDF, scrape Apify, run yt-dlp, resolve RSS to audio URL, fetch X JSON, etc.). Replaces today's misuse of `DOWNLOADING` and the misuse of `TRANSCRIBING` for non-transcription steps.
- **TRANSCRIBING** = "actual audio→text transcription via Deepgram". Only present for sources that genuinely need it.
- **SUMMARIZING** = unchanged.
- `RSS_RESOLVING` and `DOWNLOADING` are **removed** from the enum.

## Implementation

### Code changes

1. **`media_summarizer/core/models/processing_job.py`**
   - Update `JobStatus` enum: drop `RSS_RESOLVING` and `DOWNLOADING`, add `EXTRACTING`. Keep `PENDING`, `TRANSCRIBING`, `SUMMARIZING`, `COMPLETED`, `FAILED`, `CANCELLED`.
   - Delete `mark_started` and `mark_downloading`. Add `mark_extracting`. Keep `mark_transcribing`, `mark_summarizing`, `mark_completed`, `mark_failed`, `mark_cancelled`.
   - **Delete `get_progress_percentage`** entirely.
   - Update `is_processing` to reference the new stages: `[EXTRACTING, TRANSCRIBING, SUMMARIZING]`.

2. **API surface (`api/endpoints/jobs.py`, `api/endpoints/media.py`)**
   - Remove `progress_percentage: int` and `progress: int` fields from the response models. The frontend doesn't consume them in V1; if it does later, status is enough.
   - Remove `progress=job.get_progress_percentage()` and `progress_percentage=…` call sites.

3. **Workers — update each `mark_*` call**:
   - `tiktok_ingestion_worker.py:1093` `mark_downloading()` → `mark_extracting()`
   - `instagram_ingestion_worker.py:264` `mark_downloading()` → `mark_extracting()`
   - `article_extraction_worker.py:353` `mark_transcribing()` → `mark_extracting()` (and **add** the proper `mark_summarizing()` later if it's missing — audit needed)
   - `document_parsing/worker.py:205` `mark_transcribing()` → `mark_extracting()`
   - `x_ingestion_worker.py:431` `mark_transcribing()` → `mark_extracting()`
   - `core/media_ingestion/adapters/orchestrators.py:377, 534` `mark_downloading()` → `mark_extracting()`
   - `core/media_ingestion/adapters/orchestrators.py:417` `mark_transcribing()` → keep as `mark_transcribing()` only if Deepgram is actually invoked next, otherwise `mark_extracting()`
   - `transcription/deepgram_worker.py:537` `mark_transcribing()` → keep (legitimate transcription)
   - `podcastindex_resolution_worker` — replace `RSS_RESOLVING` usage with `EXTRACTING`
   - `instagram_ingestion_worker.py:309` `mark_transcribing()` — keep ONLY on the Deepgram-fallback branch (Apify failed, falling back to push-mode audio transcription); on the Apify-native-caption branch this should be `mark_extracting()` followed directly by `mark_summarizing()`.

4. **Tests** — grep for `RSS_RESOLVING`, `DOWNLOADING`, `progress_percentage`, `progress=`, `mark_downloading` in `tests/`. Update or delete assertions that reference removed states/fields.

### Audit grep before claiming done

```bash
grep -rnE "RSS_RESOLVING|DOWNLOADING|mark_downloading|mark_started|get_progress_percentage|progress_percentage|progress=" \
  media_summarizer/ tests/ \
  | grep -v "test_quota_enforcer.py" | grep -v "core/services/quota"
```

Should return zero hits in workers / models / api after refactor (some `progress` matches in unrelated quota code — eyeball them).

## E2E impact

Tests in `tests/e2e/` poll on `(completed, failed)` terminal states only — they don't assert on intermediate stages. No impact expected on the 14 happy-path tests post-task-167. Run the full E2E suite after the refactor to confirm.

## Out of scope

- Per-source vocabulary (`FETCHING_HTML`, `SCRAPING_APIFY`, etc.) — explicitly rejected as overkill for V1.
- Re-introducing a progress percentage with a new formula — no UI consumer today.
- Adding new stages (`QUEUED`, `PROVISIONING`, etc.) — keep the enum minimal.
- Frontend changes — the V1 UI doesn't render the status string user-facing; downstream PRs can adjust labels later.

## References

- `media_summarizer/core/models/processing_job.py:28` (JobStatus enum)
- `media_summarizer/core/models/processing_job.py:357` (`get_progress_percentage`, to be deleted)
- `media_summarizer/api/endpoints/jobs.py:25, 104, 176` (progress field exposure)
- `media_summarizer/api/endpoints/media.py:117, 176, 818` (progress field exposure)
- task-167 (debug confusion caused by `downloading` label on TikTok worker)
- task-158 (deepgram_mode refactor — already split source-specific behavior)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `JobStatus` enum reduced to `PENDING`, `EXTRACTING`, `TRANSCRIBING`, `SUMMARIZING`, `COMPLETED`, `FAILED`, `CANCELLED`. `RSS_RESOLVING` and `DOWNLOADING` removed.
- [ ] #2 `get_progress_percentage` removed from `ProcessingJob`. `progress` and `progress_percentage` fields removed from all API response models. Audit grep returns zero hits.
- [ ] #3 Each worker / orchestrator transitions through ONLY the stages applicable to its source per the table in the description (no fake `TRANSCRIBING` on article/X/document workers).
- [ ] #4 `mark_downloading` and `mark_started` deleted (no shim). Audit grep returns zero hits.
- [ ] #5 Lambda images rebuilt + redeployed for every affected worker.
- [ ] #6 Full `pytest -m e2e` clean: 14 happy paths still pass.
- [ ] #7 No frontend regression — V1 mobile app doesn't render `progress` field; verify via grep on `mobile/` that nothing reads it.
<!-- AC:END -->
