---
id: task-121
title: Fix summarization worker still requires deprecated email field — discovered during Phase 4
status: Done
assignee: []
created_date: '2026-06-08 22:00'
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

Discovered during Phase 4 re-test on AWS dev (V1 launch plan §4) **after task-120 was merged**. Article ingestion now reaches `completed` (transcript uploaded to S3 ✅), but **on-demand artifact generation fails** for every artifact type.

## Symptom

`POST /api/media/{id}/artifacts` with `{"artifact_type":"summary"}` returns `202 queued`, but the summarization worker Lambda then crashes with:

```
ValueError: Missing required fields in summarization message
```

at `media_summarizer/workers/summarization/summarization_worker.py:246`.

### Reproduction

```bash
API=https://jji077bi8e.execute-api.eu-west-3.amazonaws.com
TOKEN=<...>  # from POST /api/v1/auth/login

# Ingest article — works, reaches completed
RESP=$(curl -X POST "${API}/api/media/ingest-url" \
  -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
  -d '{"url":"https://en.wikipedia.org/wiki/Personal_knowledge_management"}')
MEDIA_ID=$(echo "$RESP" | jq -r .media_item_id)

# Wait until status=completed (transcript on S3)

# Trigger summary artifact — fails downstream
curl -X POST "${API}/api/media/${MEDIA_ID}/artifacts" \
  -H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json" \
  -d '{"artifact_type":"summary"}'
```

CloudWatch logs `/aws/lambda/media-summarizer-worker-summarization` show:

```
Missing required fields in message: {
  'job_id': '917cb2b4-...',
  'media_item_id': '917cb2b4-...',
  'artifact_type': 'summary',
  'user_id': '029dab96-...',
  'transcript_s3_key': '917cb2b4-....txt'
}
```

## Root cause

`summarization_worker.py:237-246`:

```python
job_id = message_body.get("job_id")
transcript_s3_key = message_body.get("transcript_s3_key")
transcript_bucket = message_body.get("transcript_bucket", "media-summarizer-transcripts")  # also stale default
email = message_body.get("email")

if not all([job_id, transcript_s3_key, email]):
    raise ValueError("Missing required fields in summarization message")
```

The worker still requires `email` — a legacy field from the SMTP-based notification flow that was **removed in task-102** ("Remove email notification worker, replaced by mobile polling"). The cleanup missed this consumer. The API enqueueing the message no longer provides `email` (correct), but the worker hasn't been updated to stop demanding it.

Bonus stale value: `transcript_bucket` default is `"media-summarizer-transcripts"` (no env suffix) — same legacy naming bug fixed by task-120 in the worker output path. Stale here in the input path. The worker should **read `TRANSCRIPT_BUCKET` from env** (Terraform-injected via task-120) instead of hardcoding a default.

## Probable other consumers with the same issue

The `email` field requirement is suspicious enough that other artifact workers (notes, flashcards, quiz) may have the same pattern. Need to grep them all:

```bash
grep -rn "email.*required\|Missing required fields\|message_body.get(\"email\")" \
  media_summarizer/workers/ --include="*.py"
```

## Fix

1. Remove `email` from the required-fields check in `summarization_worker.py:244`.
2. Remove the unused `email` variable assignment line 242 (or keep with a comment if used elsewhere downstream — verify).
3. Replace hardcoded `"media-summarizer-transcripts"` default with `os.getenv("TRANSCRIPT_BUCKET")` (Terraform now injects it via task-120). If the env var is missing, fail loudly rather than fall back to a non-existent bucket.
4. Apply same fixes to other artifact workers if they require `email` (notes_worker, flashcards_worker, quiz_worker).
5. Re-build + push Lambda image (`docker buildx build --platform linux/arm64 --provenance=false --sbom=false ... --push`), update affected Lambdas.

## Re-test acceptance

After fix:
- `POST /api/media/{id}/artifacts` with each of `summary`, `notes`, `flashcards`, `quiz` types
- Each returns `202 queued`
- Worker Lambda processes the message, generates artifact, uploads to corresponding S3 bucket
- `GET /api/media/{id}/artifacts` lists each artifact with `status=completed` and `s3_key` set

## Out of scope

- Refactoring artifact generation flow architecture
- Adding new artifact types
- Cascading auto-generation (V1 spec is on-demand only)

## References

- task-102 (email notification removal — incomplete cleanup)
- task-120 (S3 bucket name alignment — fixed output, missed input default)
- V1 launch plan §Phase 4
- `media_summarizer/workers/summarization/summarization_worker.py:237-246`
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 `email` removed from required-fields check in `summarization_worker.py`
- [ ] #2 Other artifact workers (notes, flashcards, quiz) audited for the same `email` requirement; fixed if present
- [ ] #3 Hardcoded `"media-summarizer-transcripts"` default replaced with `os.getenv("TRANSCRIPT_BUCKET")` in summarization_worker (and any other worker with the same hardcoded default — grep for it)
- [ ] #4 Lambda image rebuilt + redeployed via `docker buildx build --platform linux/arm64 --provenance=false --sbom=false ...` and `aws lambda update-function-code` for all affected functions
- [ ] #5 E2E re-test: ingest article → reaches `completed` → trigger each artifact type (summary, notes, flashcards, quiz) → each reaches `completed` with S3 key populated
- [ ] #6 At least 1 non-article source tested E2E (YouTube or podcast) to validate generality of fix
<!-- AC:END -->
