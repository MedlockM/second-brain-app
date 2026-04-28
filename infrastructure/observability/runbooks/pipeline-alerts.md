# Pipeline Alerts Runbook

Operational runbook for the Media Summarizer share-first pipeline alerts.
Each section corresponds to a specific CloudWatch alarm defined in `infrastructure/terraform/pipeline_alerts.tf`.

---

## Table of Contents

- [Ingestion Failures](#ingestion-failures)
- [Resolver Failures](#resolver-failures)
- [Resolver Retries](#resolver-retries)
- [Transcription Failures](#transcription-failures)
- [Transcription Latency](#transcription-latency)
- [Artifact Generation Failures](#artifact-generation-failures)
- [Artifact Generation Latency](#artifact-generation-latency)
- [DLQ Messages](#dlq-messages)
- [Pipeline Stalled](#pipeline-stalled)

---

## Ingestion Failures

**Alarm:** `media-summarizer-ingestion-sustained-failures`
**Severity:** High
**Threshold:** >3 failures per 5-min period, sustained for 3 periods (15 min)

### Symptoms

- Users receive 500 errors when sharing URLs
- `media.ingest.failed` events in API logs

### Investigation Steps

1. **Check API health:**
   ```
   CloudWatch Insights query on /ecs/media-summarizer-api:
   fields @timestamp, error_type, error_code, source_platform
   | filter event = "media.ingest.failed"
   | sort @timestamp desc
   | limit 20
   ```

2. **Check DynamoDB availability:**
   - CloudWatch -> AWS/DynamoDB -> `processing_jobs` table -> ThrottledRequests, SystemErrors
   - If throttled: check provisioned capacity or on-demand scaling

3. **Check SQS send failures:**
   - Look for `external_call.failed` with `provider="sqs"` in API logs
   - Verify queue exists and IAM permissions are correct

4. **Check minute pool (quota):**
   - If errors mention "insufficient minutes", check the `user_minute_pools` table

### First Response

- If DynamoDB is throttled: scale capacity or switch to on-demand billing
- If SQS is unreachable: check VPC endpoints and security groups
- If auth-related: verify Cognito/JWT configuration is not expired

### Escalation

- If issue persists >30 min: page backend on-call
- If DynamoDB outage: check AWS Health Dashboard

---

## Resolver Failures

**Alarm:** `media-summarizer-{platform}-resolver-sustained-failures`
**Severity:** High
**Threshold:** >3 failures per 5-min period, sustained for 3 periods (15 min)
**Platforms:** youtube, tiktok, rss

### Symptoms

- Jobs stuck in PROCESSING state
- `worker.failed` events in resolver worker logs

### Investigation Steps

1. **Identify failing platform:**
   ```
   CloudWatch Insights on /ecs/media-summarizer-{platform}-worker:
   fields @timestamp, job_id, error_type, error_code
   | filter event = "worker.failed"
   | sort @timestamp desc
   | limit 20
   ```

2. **Platform-specific checks:**

   **YouTube:**
   - yt-dlp version may be outdated (YouTube frequently changes APIs)
   - Check if YouTube is blocking IP range (429 responses)
   - Verify `youtube-transcript-api` is returning transcripts

   **TikTok:**
   - yt-dlp version may need update for TikTok format changes
   - Check for geo-blocking or rate limiting

   **Podcast (RSS):**
   - PodcastIndex API may be down: check https://status.podcastindex.org
   - RSS feed may have changed format or be unreachable

3. **Check network connectivity:**
   - Verify Fargate tasks can reach external endpoints
   - Check NAT Gateway / VPC egress configuration

### First Response

- **YouTube/TikTok:** Update yt-dlp package: `pip install -U yt-dlp`
- **Podcast:** Test PodcastIndex API manually; check API key rotation
- **All:** If rate-limited, reduce concurrency via scaling controller config

### Escalation

- If upstream API is confirmed down: communicate to users via status page
- If yt-dlp update needed: deploy new worker image

---

## Resolver Retries

**Alarm:** `media-summarizer-{platform}-resolver-high-retry-rate`
**Severity:** Medium
**Threshold:** >10 retries per 5-min period, sustained for 2 periods

### Symptoms

- Increased latency for users (jobs taking longer)
- `worker.retry_scheduled` events spiking

### Investigation Steps

1. **Check error patterns:**
   ```
   CloudWatch Insights on /ecs/media-summarizer-{platform}-worker:
   fields @timestamp, job_id, error_type, attempt
   | filter event = "worker.retry_scheduled"
   | stats count(*) by error_type
   ```

2. **Determine if transient:**
   - If retries succeed on 2nd/3rd attempt: likely transient network issue
   - If retries always fail: will escalate to resolver failure alarm

### First Response

- Monitor for 15 minutes; retries are expected for transient errors
- If retries consistently hit max: investigate as resolver failure
- Check if external service has degraded performance (not full outage)

---

## Transcription Failures

**Alarm:** `media-summarizer-transcription-sustained-failures`, `media-summarizer-transcription-success-rate-breach`
**Severity:** Critical
**Threshold:** >2 failures per 5-min period for 3 periods, OR success rate < 98%

### Symptoms

- Jobs stuck after resolver completes
- `worker.transcription.failed` events in Deepgram worker logs
- DLQ accumulating messages

### Investigation Steps

1. **Check Deepgram status:**
   - https://status.deepgram.com
   - Check for API key quota exhaustion

2. **Examine failures:**
   ```
   CloudWatch Insights on /ecs/media-summarizer-deepgram-worker:
   fields @timestamp, job_id, error_type, error_code, duration_ms
   | filter event = "worker.transcription.failed"
   | sort @timestamp desc
   | limit 20
   ```

3. **Common error types:**
   - `DeepgramAPIError`: API returning errors (check status page, rate limits)
   - `TimeoutError`: Audio files too large or network issues
   - `AudioFormatError`: Unsupported audio format from resolver

4. **Check audio files:**
   - Verify files exist in S3 `media-summarizer-audio` bucket
   - Check file sizes (very large files may timeout)

### First Response

- If Deepgram outage: no immediate fix; monitor for recovery
- If rate limit: reduce concurrent Deepgram workers in scaling controller
- If audio format errors: check resolver output format
- If API key issue: rotate key in Secrets Manager

### Escalation

- Deepgram outage >1h: consider enabling Whisper fallback if available
- API key quota exhausted: contact Deepgram support

---

## Transcription Latency

**Alarm:** `media-summarizer-transcription-latency-p95-breach`
**Severity:** High
**Threshold:** p95 > 120s for 3 consecutive 5-min periods

### Symptoms

- Users waiting longer than usual for results
- p95 latency climbing on dashboard

### Investigation Steps

1. **Check latency distribution:**
   ```
   CloudWatch Insights on /ecs/media-summarizer-deepgram-worker:
   fields @timestamp, job_id, duration_ms
   | filter event = "worker.transcription.completed"
   | stats avg(duration_ms), pct(duration_ms, 50), pct(duration_ms, 95), pct(duration_ms, 99) by bin(5m)
   | sort bin desc
   ```

2. **Correlate with audio duration:**
   - Very long audio files (>60 min) naturally take longer
   - Check if a batch of long files is skewing p95

3. **Check Deepgram response times:**
   - May indicate Deepgram is under load
   - Check Deepgram status page for degraded performance

### First Response

- If caused by a few very large files: expected behavior, monitor
- If widespread latency increase: check Deepgram status
- Consider raising visibility timeout if transcription workers are timing out

### Escalation

- Sustained >1h: contact Deepgram if their service is degraded
- If caused by our infrastructure: check network, NAT Gateway throughput

---

## Artifact Generation Failures

**Alarm:** `media-summarizer-artifact-generation-sustained-failures`, `media-summarizer-artifact-generation-success-rate-breach`
**Severity:** High
**Threshold:** >3 failures per 5-min period for 3 periods, OR success rate < 95%

### Symptoms

- Transcriptions complete but summaries/notes are not generated
- `artifact.generation.failed` events in summarization worker logs

### Investigation Steps

1. **Check LLM API status:**
   - OpenAI: https://status.openai.com
   - Check API key validity and quota

2. **Examine failures:**
   ```
   CloudWatch Insights on /ecs/media-summarizer-summarization-worker:
   fields @timestamp, job_id, artifact_type, error_type, error_code
   | filter event = "artifact.generation.failed" OR event = "worker.failed"
   | sort @timestamp desc
   | limit 20
   ```

3. **Common error patterns:**
   - `LLMAPIError`: API returned error (rate limit, content policy, etc.)
   - `TimeoutError`: LLM took too long to respond
   - `JSONDecodeError`: LLM returned malformed JSON response
   - `ContentPolicyError`: Content flagged by LLM safety filters

4. **Check transcript availability:**
   - Verify transcript exists in S3 before artifact generation starts

### First Response

- If LLM API rate limit: reduce concurrency, implement exponential backoff
- If content policy: specific transcripts may be triggering filters (acceptable loss)
- If API key quota: rotate/upgrade key
- If timeout: increase `LLM_TIMEOUT_SECONDS` env var

### Escalation

- LLM provider outage >1h: consider switching to fallback model
- Persistent JSON parsing failures: may need prompt engineering fix

---

## Artifact Generation Latency

**Alarm:** `media-summarizer-artifact-generation-latency-p95-breach`
**Severity:** High
**Threshold:** p95 > 30s for 3 consecutive 5-min periods

### Symptoms

- Artifacts taking unusually long to generate
- Users see "generating" state for extended periods

### Investigation Steps

1. **Check latency by artifact type:**
   ```
   CloudWatch Insights on /ecs/media-summarizer-summarization-worker:
   fields @timestamp, job_id, artifact_type, duration_ms
   | filter event = "artifact.generation.completed"
   | stats avg(duration_ms), pct(duration_ms, 95) by artifact_type
   ```

2. **Check LLM API response times:**
   - summary_detailed naturally takes longer than summary_short
   - Check if specific model (gpt-4o-mini) is experiencing latency

3. **Check input transcript sizes:**
   - Very long transcripts produce more tokens, increasing latency

### First Response

- If LLM provider is slow: monitor, typically self-resolves
- If specific artifact type: may need model change or prompt optimization
- Consider switching to a faster model for non-critical artifacts

### Escalation

- Sustained >1h: consider model fallback (e.g., gpt-4o-mini to gpt-3.5-turbo)

---

## DLQ Messages

**Alarm:** `media-summarizer-{stage}-dlq-non-empty`
**Severity:** Medium
**Threshold:** Any message in DLQ (>0)

### Symptoms

- Messages that exhausted all retries
- Usually indicates a persistent bug or data issue

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
   - Check processing_jobs DynamoDB table for error details
   - Check worker logs for the specific job_id

3. **Determine root cause:**
   - Bad input data (malformed URL, unsupported format)
   - Transient failure that was not actually transient
   - Bug in worker code

### First Response

- Inspect first few messages to determine if systematic or isolated
- If isolated bad data: delete DLQ messages, mark jobs as failed
- If systematic: fix root cause, then replay messages

### Replay Procedure

```bash
# Move messages back to source queue for reprocessing
aws sqs start-message-move-task \
  --source-arn <DLQ_ARN> \
  --destination-arn <SOURCE_QUEUE_ARN>
```

### Escalation

- If DLQ grows continuously: likely a code bug; prioritize fix
- If >50 messages: create incident ticket

---

## Pipeline Stalled

**Alarm:** `media-summarizer-pipeline-stalled`
**Severity:** Critical
**Threshold:** Zero transcription completions for 30 minutes (6 x 5-min periods)

### Symptoms

- Complete pipeline halt
- Jobs ingested but never completing
- All queues may be growing

### Investigation Steps

1. **Check ECS task health:**
   ```bash
   aws ecs list-tasks --cluster media-summarizer-cluster --desired-status RUNNING
   aws ecs describe-tasks --cluster media-summarizer-cluster --tasks <TASK_ARNS>
   ```

2. **Check scaling controller:**
   - Lambda function may have failed
   - Check `/aws/lambda/media-summarizer-scaling-controller` logs

3. **Check queue visibility:**
   - Messages may be invisible (being processed) but workers are dead
   - Check `ApproximateNumberOfMessagesNotVisible` in SQS

4. **Check infrastructure:**
   - VPC/subnet connectivity
   - NAT Gateway status
   - ECR image pull failures

### First Response

1. Verify at least one worker task is running per queue type
2. If no tasks running: manually trigger scaling controller
3. If tasks running but not processing: check container logs for startup errors
4. Force visibility timeout reset if messages are stuck invisible:
   ```bash
   # Messages will become visible again after timeout expires naturally
   # Or reduce visibility timeout on the queue temporarily
   ```

### Escalation

- If infrastructure-level issue (VPC, NAT, ECS): page infrastructure on-call
- If complete outage >15 min: communicate to users

---

## General Diagnostic Queries

### End-to-End Job Trace

```
CloudWatch Insights (all log groups):
fields @timestamp, @logStream, event, message, duration_ms
| filter job_id = "<JOB_ID>"
| sort @timestamp asc
```

### Error Rate by Stage (last 1h)

```
CloudWatch Insights (all worker log groups):
fields event
| filter level = "ERROR"
| stats count(*) as errors by event
| sort errors desc
```

### SLO Budget Check (28-day window)

```
CloudWatch Insights on /ecs/media-summarizer-api:
filter event in ["media.ingest.started", "media.ingest.created"]
| stats count(*) as total, sum(event = "media.ingest.created") as successes by bin(1d)
| sort bin asc
```

---

## Contact and Escalation Path

| Level | Who | When |
|-------|-----|------|
| L1 | On-call engineer (SNS email) | All alerts |
| L2 | Backend team lead | Unresolved after 30 min |
| L3 | Infrastructure + vendor support | Platform/provider outage |
