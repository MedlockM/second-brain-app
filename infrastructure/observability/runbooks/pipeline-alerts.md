# Pipeline Alerts Runbook

Operational runbook for the Media Summarizer pipeline alerts (Lambda architecture).
Each section corresponds to a specific CloudWatch alarm defined in `infrastructure/terraform/pipeline_alerts.tf`.

---

## Table of Contents

- [API Latency](#api-latency)
- [API 5xx Rate](#api-5xx-rate)
- [DLQ Messages](#dlq-messages)
- [How to Recover a DLQ After a Fix](#how-to-recover-a-dlq-after-a-fix)
- [Lambda Errors](#lambda-errors)
- [Lambda Throttles](#lambda-throttles)
- [Deepgram Error Rate](#deepgram-error-rate)
- [LlamaParse Fallback](#llamaparse-fallback)
- [Archiver Failure](#archiver-failure)

---

## API Latency

**Alarm:** `media-summarizer-api-latency-p95-breach`
**Severity:** High
**Threshold:** API Gateway p95 latency > `API_SLOW_REQUEST_THRESHOLD_MS` (default 3000ms) for 5 minutes

### Symptoms

- Users experiencing slow responses
- Timeout errors on mobile clients
- p95 latency climbing on the dashboard

### Investigation Steps

1. **Check API Gateway metrics:**
   - CloudWatch -> API Gateway -> Latency by route
   - Identify which route(s) are contributing to the high p95

2. **Check Lambda API duration:**
   ```
   CloudWatch -> Lambda -> media-summarizer-api -> Duration p95
   ```
   - If Lambda Duration is high, the bottleneck is in the application code
   - If API Gateway latency is high but Lambda is normal, check cold starts

3. **Check downstream dependencies:**
   - DynamoDB read/write latency (check ThrottledRequests)
   - SQS SendMessage latency

4. **Check for cold starts:**
   - CloudWatch Insights on `/aws/lambda/media-summarizer-api`:
     ```
     filter @type = "REPORT"
     | fields @duration, @initDuration
     | filter @initDuration > 0
     | stats count(*), avg(@initDuration) by bin(5m)
     ```

### First Response

- If cold start related: increase provisioned concurrency
- If DynamoDB throttled: switch to on-demand billing or increase provisioned capacity
- If specific route: check for N+1 queries or missing pagination
- If widespread: check if Lambda memory is undersized (increase to 512MB+)

### Escalation

- If persists >30 min: page backend on-call
- If caused by AWS service degradation: check AWS Health Dashboard

---

## API 5xx Rate

**Alarm:** `media-summarizer-api-5xx-rate-breach`
**Severity:** Critical
**Threshold:** 5xx / total requests > 1% over 5 minutes

### Symptoms

- Users receiving server error responses
- Mobile clients showing generic error messages
- `api.request_error` events with status >= 500 in API logs

### Investigation Steps

1. **Identify error patterns:**
   ```
   CloudWatch Insights on /aws/lambda/media-summarizer-api:
   fields @timestamp, path, method, status, error_type, error_code
   | filter status >= 500
   | sort @timestamp desc
   | limit 20
   ```

2. **Check if deployment related:**
   - Was there a recent deployment? Check Lambda version aliases
   - If yes: consider rollback to previous version

3. **Check dependencies:**
   - DynamoDB: SystemErrors, ThrottledRequests
   - SQS: check if queues are accessible
   - Secrets Manager: check if secrets can be fetched

4. **Check Lambda errors:**
   - Unhandled exceptions, out-of-memory, timeout

### First Response

- If post-deployment: rollback Lambda to previous version
- If dependency outage: check AWS Health Dashboard
- If code bug: identify and hotfix
- If auth-related: check JWT secret rotation status

### Escalation

- If 5xx rate > 10%: immediate escalation to backend team
- If AWS service outage: communicate to users via status page

---

## DLQ Messages

**Alarm:** `media-summarizer-dlq-{dlq-name}-non-empty`
**Severity:** Medium
**Threshold:** Any message in DLQ (>0) for 5 minutes

### Affected DLQs

| DLQ Name | Source Queue | Worker |
|----------|-------------|--------|
| `podcastindex-resolution-dlq` | `podcastindex-resolution-queue` | Podcast resolution |
| `youtube-ingestion-dlq` | `youtube-ingestion-queue` | YouTube ingestion |
| `tiktok-ingestion-dlq` | `tiktok-ingestion-queue` | TikTok ingestion |
| `x-ingestion-dlq` | `x-ingestion-queue` | X (Twitter) ingestion |
| `audio-download-dlq` | `audio-download-queue` | Audio download |
| `deepgram-transcription-dlq` | `deepgram-transcription-queue` | Deepgram transcription |
| `article-extraction-dlq` | `article-extraction-queue` | Article extraction |
| `artifact-generator-dlq` | `artifact-generator-queue` | Artifact generation (flashcards, notes, quiz, summary_short, summary_detailed) |
| `episode-completed-dlq` | `episode-completed-events` | Episode completed fan-out |
| `push-notification-dlq` | `push-notification-queue` | Push notifications |
| `spotify-sync-dlq` | `spotify-sync-queue` | Spotify sync |

### Symptoms

- Messages that exhausted all retries (default: 3 attempts)
- Usually indicates a persistent bug or bad input data

### Investigation Steps

1. **Inspect DLQ messages:**
   ```bash
   aws sqs receive-message \
     --queue-url <DLQ_URL> \
     --max-number-of-messages 5 \
     --attribute-names All \
     --message-attribute-names All
   ```

2. **Correlate with job_id:**
   - Extract `job_id` from message body
   - Check `processing_jobs` DynamoDB table for error details
   - Check worker Lambda logs for the specific job_id

3. **Determine root cause:**
   - Bad input data (malformed URL, unsupported format)
   - Transient failure that persisted across all retries
   - Bug in worker code
   - External service consistently failing for specific inputs

### First Response

- Inspect first few messages to determine if systematic or isolated
- If isolated bad data: delete DLQ messages, mark jobs as failed
- If systematic: fix root cause, then replay messages

### Replay Procedure

Use the replay script (see [How to Recover a DLQ After a Fix](#how-to-recover-a-dlq-after-a-fix) for the full procedure):

```bash
./scripts/replay_dlq.sh <dlq-name>
```

### Escalation

- If DLQ grows continuously: likely a code bug; prioritize fix
- If >50 messages: create incident ticket

---

## How to Recover a DLQ After a Fix

This section describes the end-to-end procedure for replaying messages from a Dead Letter Queue after deploying a bugfix that resolves the root cause of the failures.

### Prerequisites

- The bugfix has been **deployed and verified** (e.g., the worker Lambda is updated and healthy).
- You have AWS CLI v2 (>= 2.12.0) installed with appropriate credentials.
- You have confirmed that the DLQ contains messages (check via `aws sqs get-queue-attributes` or the SQS console).

### Step-by-Step Procedure

1. **Confirm the fix is deployed:**
   Verify the relevant Lambda function is running the new code version:
   ```bash
   aws lambda get-function --function-name media-summarizer-<worker> \
     --query 'Configuration.LastModified'
   ```

2. **Inspect a sample of DLQ messages** (optional but recommended):
   ```bash
   aws sqs receive-message \
     --queue-url <DLQ_URL> \
     --max-number-of-messages 3 \
     --attribute-names All \
     --visibility-timeout 0
   ```
   Verify these messages match the class of failures you just fixed. If some messages are genuinely bad data (not recoverable), consider purging those individually before replaying.

3. **Run the replay script:**
   ```bash
   ./scripts/replay_dlq.sh <dlq-name>
   ```
   For example:
   ```bash
   ./scripts/replay_dlq.sh summarization-dlq
   ./scripts/replay_dlq.sh podcastindex-resolution-dlq
   ```
   The script will:
   - Refuse to run if the DLQ is empty
   - Start a message move task (SQS `StartMessageMoveTask` API)
   - Poll and report progress until all messages are moved back to the source queue

4. **Monitor reprocessing:**
   After replay, watch:
   - The source queue's `ApproximateNumberOfMessagesVisible` (should decrease as the worker processes)
   - The worker Lambda's error rate and invocation count in CloudWatch
   - The DLQ's message count (should stay at 0; if it grows again, the fix is incomplete)

5. **Verify success:**
   ```bash
   aws sqs get-queue-attributes \
     --queue-url <DLQ_URL> \
     --attribute-names ApproximateNumberOfMessages \
     --query 'Attributes.ApproximateNumberOfMessages'
   ```
   Should return `"0"`.

### Important Notes

- **DLQ retention is 14 days** (matching source queues). You have up to 14 days from when a message entered the DLQ to replay it.
- **Do not replay before fixing the root cause** — messages will fail again and re-enter the DLQ (after exhausting retries), burning through the receive count unnecessarily.
- **Partial replay is not supported** by the `StartMessageMoveTask` API — it moves all messages. If you only want to replay a subset, use `receive-message` + `send-message` + `delete-message` manually.
- **All queues now have a DLQ** with `maxReceiveCount = 3`. A message that fails 3 times will land in the corresponding DLQ.

### Script Reference

| Script | Location | Purpose |
|--------|----------|---------|
| `replay_dlq.sh` | `scripts/replay_dlq.sh` | Replay all messages from a named DLQ to its source queue |

Run `./scripts/replay_dlq.sh --help` for the full list of available DLQs.

---

## Lambda Errors

**Alarm:** `media-summarizer-{worker}-lambda-error-rate`
**Severity:** High
**Threshold:** Error rate > 5% over 10 minutes (2 consecutive 5-min periods)

### Symptoms

- Lambda function returning errors
- Jobs failing without completing
- Increased DLQ depth

### Investigation Steps

1. **Check error pattern:**
   ```
   CloudWatch Insights on /aws/lambda/media-summarizer-{worker}:
   fields @timestamp, event, error_type, error_code, job_id
   | filter level = "ERROR"
   | sort @timestamp desc
   | limit 20
   ```

2. **Check Lambda execution errors:**
   - Timeouts (check Duration vs configured timeout)
   - Out of memory (check Max Memory Used in REPORT lines)
   - Permission errors (check IAM role)

3. **Worker-specific checks:**

   **podcastindex-resolution:** PodcastIndex API down, API key expired
   **youtube-ingestion:** yt-dlp outdated, YouTube blocking
   **tiktok-ingestion:** Apify actor failing, rate limits
   **x-ingestion:** X API rate limits, bearer token expired
   **audio-download:** S3 permissions, source URL unreachable
   **deepgram-transcription:** Deepgram API down, quota exhausted
   **article-extraction:** Target site blocking, timeout
   **document-parsing:** LlamaParse + Unstructured both failing
   **summarization:** OpenAI API rate limit, content policy
   **flashcards:** OpenAI API errors
   **search-indexing:** Algolia API errors

### First Response

- If timeout: increase Lambda timeout or optimize code
- If memory: increase Lambda memory size
- If external API: check provider status page
- If permission: check IAM role policies

### Escalation

- If error rate > 20%: immediate page to backend on-call
- If caused by external provider outage: communicate ETA to users

---

## Lambda Throttles

**Alarm:** `media-summarizer-{worker}-lambda-throttled`
**Severity:** High
**Threshold:** Any throttle (>0) in 5 minutes

### Symptoms

- Lambda invocations being rejected
- SQS messages remaining visible (not being consumed)
- Increased queue depth without corresponding invocations

### Investigation Steps

1. **Check concurrency:**
   ```
   CloudWatch -> Lambda -> {function} -> ConcurrentExecutions
   ```
   - Compare with account-level concurrent execution limit (default: 1000)
   - Check if reserved concurrency is set too low

2. **Check account limits:**
   ```bash
   aws lambda get-account-settings
   ```

3. **Check if burst-related:**
   - Initial burst limit is 500-3000 depending on region
   - After burst, scaling rate is 500/minute

### First Response

- If reserved concurrency too low: increase it
- If account limit reached: request limit increase via AWS Support
- If burst-related: add SQS batching or increase batch window
- Consider: adjust SQS event source mapping `MaximumConcurrency`

### Escalation

- If persistent throttling: request AWS Lambda concurrency limit increase
- If multiple functions throttled: likely account-level limit hit

---

## Deepgram Error Rate

**Alarm:** `media-summarizer-deepgram-error-rate-breach`
**Severity:** High
**Threshold:** Deepgram error rate > 5% over 15 minutes

### Symptoms

- Transcription jobs failing
- `worker.transcription.failed` events with `transcript_source=deepgram`
- DLQ for `deepgram-transcription-dlq` accumulating

### Investigation Steps

1. **Check Deepgram status:** https://status.deepgram.com

2. **Examine error details:**
   ```
   CloudWatch Insights on /aws/lambda/media-summarizer-deepgram-transcription:
   fields @timestamp, job_id, error_type, error_code, duration_ms
   | filter event = "worker.transcription.failed" AND transcript_source = "deepgram"
   | sort @timestamp desc
   | limit 20
   ```

3. **Common error types:**
   - `DeepgramAPIError`: API returning errors (rate limits, auth)
   - `TimeoutError`: Audio files too large or network issues
   - `AudioFormatError`: Unsupported audio format

4. **Check quota:**
   - Verify Deepgram API key quota and usage
   - Check if concurrent request limit is reached

### First Response

- If Deepgram outage: wait for recovery, messages will retry
- If rate limit: reduce Lambda reserved concurrency for deepgram-transcription
- If audio format: check upstream resolver output
- If API key issue: rotate key in Secrets Manager

### Escalation

- Deepgram outage > 1h: contact Deepgram support
- API key quota exhausted: upgrade plan or contact support

---

## LlamaParse Fallback

**Alarm:** `media-summarizer-llamaparse-fallback-rate-breach`
**Severity:** Medium
**Threshold:** Unstructured fallback triggered > N times/hour (configurable, default 20)

### Symptoms

- `document_parsing.primary_failed` events increasing
- `document_parsing.fallback_success` events compensating
- Documents still being parsed but via the fallback path (Unstructured API)

### Investigation Steps

1. **Check LlamaParse quota:**
   - Free tier: 1000 pages/day
   - Check daily usage at https://cloud.llamaindex.ai

2. **Examine failure reasons:**
   ```
   CloudWatch Insights on /aws/lambda/media-summarizer-document-parsing:
   fields @timestamp, job_id, error_code, provider
   | filter event = "document_parsing.primary_failed"
   | stats count(*) by error_code
   ```

3. **Common causes:**
   - `RATE_LIMITED`: Daily quota exhausted
   - `TIMEOUT`: LlamaParse taking too long (large documents)
   - `AUTH_ERROR`: API key invalid or expired

### First Response

- If quota exhausted: the fallback (Unstructured) is handling it -- no immediate action needed, but monitor Unstructured costs
- If auth error: check/rotate LLAMAPARSE_API_KEY in Secrets Manager
- If timeout: consider splitting large documents before parsing

### Escalation

- If both LlamaParse AND Unstructured are failing: `document_parsing.all_failed` will fire Lambda error rate alarm
- If cost concern: evaluate upgrading LlamaParse plan vs relying on Unstructured

---

## Archiver Failure

**Alarms:** `media-summarizer-job-archiver-silent-failure` (composite), `media-summarizer-job-archiver-archive-gap`
**Severity:** Critical
**Threshold:** silent-failure = archiver Lambda invoked while zero objects archived in the same 5-minute period; archive-gap = `remove_records - archived > 0`

Both alarms answer the same question in two different ways, because the failure
they exist for (task-218 §1.5) was an archiver invoked 144 times that never wrote
an object while `processing_jobs` rows were expiring:

- `archive-gap` sees the handler run and drop deletions. Derived from the
  `job_archiver.batch_completed` JSON summary line emitted once per invocation.
- `silent-failure` is the composite of `job-archiver-invoked` (`AWS/Lambda`
  `Invocations`, emitted by the platform, not by the function) AND
  `job-archiver-nothing-archived` (`treat_missing_data = breaching`, so a handler
  that logs nothing at all still breaches). This is the one that survives a
  regression to a no-op deployment package.

### Symptoms

- The archives bucket stops growing while jobs keep disappearing from `processing_jobs`
- `job_archiver.batch_completed` shows `archived` below `remove_records`, or is absent entirely

### Investigation Steps

1. **Read the invocation summaries:**
   ```
   CloudWatch Insights on /aws/lambda/media-summarizer-job-archiver-<env>:
   fields @timestamp, remove_records, archived, failed
   | filter event = "job_archiver.batch_completed"
   | sort @timestamp desc
   ```
   No rows at all + non-zero `Invocations` = the deployed package is not the real
   archiver. Check `CodeSize` on the function against a local build of
   `media_summarizer/workers/cleanup/job_archiver.py`.

2. **Check what actually landed:**
   ```
   aws s3 ls s3://media-summarizer-archives-<account>-<env>/$(date -u +%Y/%m/%d)/
   ```

3. **Common causes:**
   - `ARCHIVE_BUCKET` unset on the function (the handler reports the whole batch as `failed`)
   - `s3:PutObject` denied on the archives bucket
   - Records without `OldImage` (stream view type changed away from `OLD_IMAGE`/`NEW_AND_OLD_IMAGES`)

### First Response

- The deletions already lost cannot be recovered from the stream (24h retention at best).
  If the TTL is the source of the deletions, consider raising
  `processing_jobs_ttl_days` while the archiver is broken to slow the bleeding.
- Fix the archiver, then confirm recovery: a successful invocation writes
  `archived >= 1`, which returns both alarms to OK.

### Escalation

- If rows are expiring unarchived for more than one TTL window, treat as data loss
  and reopen the task-218 durable-persistence thread.

---

## General Diagnostic Queries

### End-to-End Job Trace

```
CloudWatch Insights (all Lambda log groups):
fields @timestamp, @logStream, event, message, duration_ms
| filter job_id = "<JOB_ID>"
| sort @timestamp asc
```

### Error Rate by Worker (last 1h)

```
CloudWatch Insights (all worker Lambda log groups):
fields event
| filter level = "ERROR"
| stats count(*) as errors by event
| sort errors desc
```

### Lambda Cold Starts

```
CloudWatch Insights on /aws/lambda/media-summarizer-{function}:
filter @type = "REPORT"
| fields @duration, @initDuration, @maxMemoryUsed, @memorySize
| filter @initDuration > 0
| stats count(*) as cold_starts, avg(@initDuration) as avg_init_ms by bin(5m)
```

---

## Contact and Escalation Path

| Level | Who | When |
|-------|-----|------|
| L1 | On-call engineer (SNS email) | All alerts |
| L2 | Backend team lead | Unresolved after 30 min |
| L3 | Infrastructure + vendor support | Platform/provider outage |
