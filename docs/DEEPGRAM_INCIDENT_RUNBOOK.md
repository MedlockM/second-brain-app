# Deepgram Incident Runbook

## Scope
This runbook covers production incidents for the active transcription path using Deepgram.

## Signals To Watch
- `deepgram-transcription-queue` backlog growth (visible messages, oldest message age)
- `deepgram-transcription-dlq` message count > 0
- Worker errors with `worker=deepgram_transcription`
- Deepgram API HTTP spikes (`401/403`, `429`, `5xx`)

## Common Failure Modes

### 1) Authentication error (`401` / `403`)
Symptoms:
- Immediate transcription failures
- Error reason contains `deepgram_non_retryable`

Actions:
1. Verify `DEEPGRAM_API_KEY` secret value in deployment environment.
2. Check secret injection in ECS/Lambda/task definition.
3. Rotate key if compromised/expired and redeploy workers.

### 2) Rate limit (`429`)
Symptoms:
- Retry bursts, growing queue lag
- Repeated transient Deepgram errors

Actions:
1. Confirm request rate and concurrency for deepgram workers.
2. Reduce worker parallelism or scaling aggressiveness.
3. Keep retries bounded; monitor DLQ for spillover.

### 3) Upstream instability (`5xx` / timeouts)
Symptoms:
- Elevated retries and final failures
- Queue delay increasing

Actions:
1. Confirm Deepgram status page / provider incident.
2. Increase visibility timeout if jobs are timing out before completion.
3. Temporarily lower launch concurrency to avoid retry storms.
4. Reprocess DLQ messages after upstream recovery.

## DLQ Recovery
1. Inspect sample DLQ messages for root cause categories.
2. Fix configuration or external dependency.
3. Replay only validated messages from `deepgram-transcription-dlq` to `deepgram-transcription-queue`.
4. Confirm success events are emitted and watcher jobs finalize correctly.

## Validation Checklist
- New jobs move from `downloading` -> `transcribing` -> terminal status.
- Success path writes transcript to S3 and publishes `episode_completion_status=success`.
- Failure path publishes `episode_completion_status=failure` (non-retryable or final retry exhaustion).
- `transcription-queue` is not used in the V1 pipeline (Deepgram is the only active transcription provider).
