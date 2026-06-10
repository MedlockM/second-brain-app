---
id: task-167
title: Update fallback chain E2E tests (test_fallback_chains.py) after task-158 deepgram_mode refactor
status: To Do
assignee: []
created_date: '2026-06-10 06:00'
labels:
  - testing
  - tech-debt
dependencies: []
priority: medium
dispatchable: true
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
## Context

`tests/e2e/test_fallback_chains.py` was authored by tasks 149/150/151/152 against the **previous** Deepgram architecture (automatic pull→push fallback on every CDN 403). task-158 replaced that architecture with **explicit `deepgram_mode` declared by the producer worker**. The 4 fallback E2E tests no longer exercise the path they claim to test, and all 4 currently fail.

Run from 2026-06-10 05:37 UTC, full E2E suite:

- ✅ 14 happy path tests PASS
- ❌ 4 fallback chain tests FAIL

This task realigns the 4 fallback tests with the new architecture so they actually validate the fallback behavior and stop polluting the suite output.

## Failures observed

### 1. `test_tiktok_apify_fallback` — TimeoutError, status `downloading` 25%

```
TimeoutError: poll_until timed out after 60s on /api/media/<id>;
last body: {'status': 'downloading', 'source_platform': 'tiktok', 'progress': 25, ...}
```

Note on naming: the TikTok worker calls `job.mark_downloading()` at line 1093 right at entry — `downloading` here is a **phase label** that covers the entire "extract transcript" step (both yt-dlp and the Apify fallback), not a file download. The status stays sticky until the worker transitions to `transcribing` (50 %).

The worker (post-task-144) tries yt-dlp first; on Lambda IP block it falls back to Apify. The test stays at 25 % for the full 60 s window — meaning neither yt-dlp nor the Apify fallback finished in time. Plausible causes:

- **yt-dlp slow to fail**: on some TikTok URLs, yt-dlp can take 30+ s to diagnose an IP block (HTTP timeouts, internal retries) before surfacing the error
- **Apify cold-start + run latency**: Apify run-sync can take 20–30 s when the actor is cold; TikTok-specific anti-bot challenges can push it further
- **Cumulative**: yt-dlp slow-fail (30 s) + Apify (30 s) easily exceeds 60 s — Apify alone is rarely > 15 s, but the combination can blow the timeout
- **SQS retry loop**: a retryable error from yt-dlp or Apify pushes the message back to the queue (visibility timeout ~720 s in the worker config); from the test's perspective the status looks stuck

Investigation: pick a URL that empirically triggers the yt-dlp IP block today, inspect CloudWatch to see whether yt-dlp fails fast and Apify takes over, then bump the test timeout to whatever the worst-case happy chain takes (likely 90–120 s).

### 2. `test_instagram_deepgram_fallback` — AssertionError, status `failed`

```
'failure_details': 'apify_non_retryable:Unable to resolve transcribable media from this Instagram URL.'
'source_url': 'https://www.instagram.com/reel/CwHSCpMoe7Z/'
```

The fixture Reel URL is unresolvable by Apify (probably deleted, geo-restricted, or the actor's input field name issue from task-156 surfacing again). Pick a different stable fixture URL.

### 3. `test_document_unstructured_fallback` — AssertionError, wrong provider

```
Expected fallback provider 'unstructured', got: 'llamaparse'.
Ensure FORCE_LLAMAPARSE_FAILURE=1 is set on the document-parsing worker.
```

The test relies on a **runtime feature flag** `FORCE_LLAMAPARSE_FAILURE=1` to force LlamaParse to fail, triggering the Unstructured fallback. The flag isn't set on the deployed Lambda. Two options:

- **A. Set the flag on the document-parsing worker via Lambda env var** for the duration of E2E runs (fragile — leaks into production paths if forgotten).
- **B. Pick a real-world PDF that LlamaParse genuinely rejects** (option 1 of task-151's original spec) — more robust, no flag needed.

Recommend B: it's the more E2E-pure approach.

### 4. `test_deepgram_pushmode_fallback` — DELETED 2026-06-10

The test is gone (commit alongside this task's creation). Rationale: after task-158, the `pull_with_push_fallback` branch is reserved for user-pasted `.mp3` URLs, an unstable code path no fixture can reliably exercise. The TikTok/Instagram path that previously triggered the fallback now routes directly to `push` mode.

No replacement test — the branch is a defensive fallback for unknown sources, not a code path used by any V1 producer.

## Approach

For each test, pick the right fix:

| Test | Approach |
|---|---|
| `test_tiktok_apify_fallback` | Find/lock a TikTok URL that empirically triggers Lambda IP block today; bump timeout if needed |
| `test_instagram_deepgram_fallback` | Find/lock a stable Reel URL; rerun Apify Instagram resolver to confirm it returns `videoUrl` without native transcript |
| `test_document_unstructured_fallback` | Find a PDF LlamaParse genuinely rejects (option 1 in task-151) OR set the FORCE_LLAMAPARSE_FAILURE flag deliberately for this test only |
| `test_deepgram_pushmode_fallback` | DELETED 2026-06-10 — branch no longer exercised by any V1 producer post task-158 |

After fixes, the test file should pass without flags or environment-specific setup.

## Out of scope

- Refactoring the broader fallback architecture (task-158 already done)
- Adding new fallback tests for X video, audio upload, etc. (separate concern)
- Documenting the fallback semantics in `tests/e2e/README.md` (could be a follow-up)

## References

- task-149 (TikTok→Apify E2E test, originally written)
- task-150 (Instagram→Deepgram E2E test, originally written)
- task-151 (Document LlamaParse→Unstructured E2E test, originally written)
- task-152 (Deepgram pull→push E2E test, originally written, made obsolete by task-158)
- task-158 (Deepgram explicit mode routing — the architecture change that broke these tests)
- `tests/e2e/test_fallback_chains.py:63, 155, 245, 323` (failing assertions)
- E2E run log 2026-06-10 05:37 UTC (4 failed, 14 passed, 4 deselected)
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `test_tiktok_apify_fallback` passes (correct fixture URL + timeout)
- [ ] #2 `test_instagram_deepgram_fallback` passes (stable Reel URL; verified locally before commit)
- [ ] #3 `test_document_unstructured_fallback` passes either via a real-world failing PDF fixture OR a documented flag-based approach with the flag set in test setup (not on the deployed Lambda)
- [x] #4 `test_deepgram_pushmode_fallback` deleted 2026-06-10 (branch no longer exercised by any V1 producer post task-158)
- [ ] #5 Full `pytest -m e2e` runs clean — all 14 happy path tests pass AND all `test_fallback_chains.py` tests pass (or are explicitly deleted)
- [ ] #6 No `FORCE_*` flags set on production Lambda env vars (test-only flags must be ephemeral)
<!-- AC:END -->
