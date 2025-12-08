# AWS Production Deployment Guide - Spotify Sync with Lambda

## Architecture Overview

**Production (AWS)**:
```
EventBridge (Cron) → Lambda (Dispatcher) → SQS → Lambda (Worker via Event Source Mapping)
```

**Local (LocalStack)**:
```
Scheduler Service → Dispatcher Script → SQS → Worker Script (triggered by script)
```

## Environment Variables

### Sync Schedule Configuration
- `SPOTIFY_SYNC_INTERVAL_HOURS` (default: `24`) - Hours between syncs (local dev only)
- `SPOTIFY_SYNC_INTERVAL_MINUTES` (default: `0`) - Additional minutes (local dev only)
- `SPOTIFY_SYNC_SCHEDULE` (default: `"rate(1 day)"`) - EventBridge schedule expression (production)

Examples:
- Daily: `SPOTIFY_SYNC_INTERVAL_HOURS=24`
- Every 12 hours: `SPOTIFY_SYNC_INTERVAL_HOURS=12`
- Every 6 hours: `SPOTIFY_SYNC_INTERVAL_HOURS=6`
- Every hour: `SPOTIFY_SYNC_INTERVAL_HOURS=1`
- Every 30 minutes: `SPOTIFY_SYNC_INTERVAL_HOURS=0 SPOTIFY_SYNC_INTERVAL_MINUTES=30`

## Local Development Setup

### Option 1: Automated Scheduler (Recommended)
Add to `docker-compose.dev.yml`:
```yaml
spotify-sync-scheduler:
  profiles: ["workers", "full"]
  build:
    context: .
    dockerfile: infrastructure/docker/worker.Dockerfile
  volumes:
    - .:/app
  env_file:
    - .env.dev
  environment:
    - AWS_ENDPOINT_URL=http://localstack:4566
    - AWS_ACCESS_KEY_ID=test
    - AWS_SECRET_ACCESS_KEY=test
    - AWS_DEFAULT_REGION=us-east-1
    - SPOTIFY_SYNC_INTERVAL_HOURS=24  # Adjust as needed
    - SPOTIFY_SYNC_INTERVAL_MINUTES=0
  depends_on:
    localstack:
      condition: service_healthy
    terraform:
      condition: service_completed_successfully
  command: python -m media_summarizer.workers.spotify_sync.scheduler
```

### Option 2: Manual Trigger
```bash
./scripts/trigger_spotify_sync.sh
```

## AWS Production Setup

### 1. Create Lambda Functions

#### Dispatcher Lambda
```bash
# Package the code
cd media_summarizer/workers/spotify_sync
zip -r dispatcher.zip dispatcher.py ../../utils/ ../../core/

# Create Lambda function
aws lambda create-function \
  --function-name SpotifySyncDispatcher \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/SpotifySyncRole \
  --handler dispatcher.lambda_handler \
  --zip-file fileb://dispatcher.zip \
  --timeout 60 \
  --memory-size 256 \
  --environment Variables="{
    SPOTIFY_SYNC_QUEUE_URL=https://sqs.REGION.amazonaws.com/ACCOUNT_ID/spotify-sync-queue
  }"
```

#### Worker Lambda
```bash
# Package the code
zip -r worker.zip worker.py ../../utils/ ../../core/

# Create Lambda function
aws lambda create-function \
  --function-name SpotifySyncWorker \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT_ID:role/SpotifySyncRole \
  --handler worker.lambda_handler \
  --zip-file fileb://worker.zip \
  --timeout 300 \
  --memory-size 512
```

### 2. Configure EventBridge

```bash
# Create rule
aws events put-rule \
  --name SpotifyDailySync \
  --schedule-expression "rate(1 day)" \
  --state ENABLED \
  --description "Daily Spotify playlist sync"

# Add Lambda target
aws events put-targets \
  --rule SpotifyDailySync \
  --targets "Id"="1","Arn"="arn:aws:lambda:REGION:ACCOUNT_ID:function:SpotifySyncDispatcher"

# Grant EventBridge permission to invoke Lambda
aws lambda add-permission \
  --function-name SpotifySyncDispatcher \
  --statement-id AllowEventBridgeInvoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:REGION:ACCOUNT_ID:rule/SpotifyDailySync
```

### 3. Configure SQS Event Source Mapping

```bash
# Create event source mapping for worker
aws lambda create-event-source-mapping \
  --function-name SpotifySyncWorker \
  --event-source-arn arn:aws:sqs:REGION:ACCOUNT_ID:spotify-sync-queue \
  --batch-size 1 \
  --enabled
```

### 4. IAM Role Permissions

The Lambda execution role needs:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ],
      "Resource": "arn:aws:sqs:REGION:ACCOUNT_ID:spotify-sync-queue"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": [
        "arn:aws:dynamodb:REGION:ACCOUNT_ID:table/spotify_playlist_follows",
        "arn:aws:dynamodb:REGION:ACCOUNT_ID:table/users",
        "arn:aws:dynamodb:REGION:ACCOUNT_ID:table/minute_buckets",
        "arn:aws:dynamodb:REGION:ACCOUNT_ID:table/processing_jobs"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

## Monitoring

### CloudWatch Alarms
```bash
# Alarm on DLQ messages
aws cloudwatch put-metric-alarm \
  --alarm-name SpotifySyncDLQAlarm \
  --alarm-description "Alert when messages in Spotify Sync DLQ" \
  --metric-name ApproximateNumberOfMessagesVisible \
  --namespace AWS/SQS \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --dimensions Name=QueueName,Value=spotify-sync-dlq
```

### Lambda Insights
Enable Lambda Insights for both functions to monitor:
- Execution duration
- Memory usage
- Cold starts
- Errors and throttles

## Cost Optimization

### Lambda Pricing (example for 1000 users, daily sync)
- **Dispatcher**: 1 invocation/day × 2s × 256MB = ~$0.000001/day
- **Worker**: 1000 invocations/day × 10s × 512MB = ~$0.02/day
- **Total**: ~$0.60/month

### Alternative: Fargate Spot
For larger scales, consider ECS Fargate Spot:
- Dispatcher: Fargate Task (0.25 vCPU, 0.5 GB) = ~$0.01/day
- Worker: Fargate Task with auto-scaling = ~$0.50/day
- **Total**: ~$15/month (but handles 10,000+ users)

## Troubleshooting

### Check Dispatcher Logs
```bash
aws logs tail /aws/lambda/SpotifySyncDispatcher --follow
```

### Check Worker Logs
```bash
aws logs tail /aws/lambda/SpotifySyncWorker --follow
```

### Check Queue Depth
```bash
aws sqs get-queue-attributes \
  --queue-url https://sqs.REGION.amazonaws.com/ACCOUNT_ID/spotify-sync-queue \
  --attribute-names ApproximateNumberOfMessages
```

### Manual Trigger (Testing)
```bash
# Trigger dispatcher manually
aws lambda invoke \
  --function-name SpotifySyncDispatcher \
  --payload '{}' \
  response.json

cat response.json
```
