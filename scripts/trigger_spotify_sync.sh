#!/bin/bash
# Manual trigger script for Spotify Sync (simulates EventBridge trigger)

set -e

echo "🎯 Triggering Spotify Sync manually..."

# Set environment
export AWS_REGION=${AWS_REGION:-us-east-1}
export AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID:-test}
export AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY:-test}
export AWS_ENDPOINT_URL=${AWS_ENDPOINT_URL:-http://localhost:4566}
export PYTHONPATH=${PYTHONPATH:-.}

# Step 1: Run dispatcher
echo "📤 Step 1: Running dispatcher..."
.venv/bin/python -m media_summarizer.workers.spotify_sync.dispatcher

# Step 2: Check queue
QUEUE_URL=$(aws --endpoint-url=$AWS_ENDPOINT_URL sqs get-queue-url \
  --queue-name spotify-sync-queue --query 'QueueUrl' --output text)

MSG_COUNT=$(aws --endpoint-url=$AWS_ENDPOINT_URL sqs get-queue-attributes \
  --queue-url "$QUEUE_URL" \
  --attribute-names ApproximateNumberOfMessages \
  --query 'Attributes.ApproximateNumberOfMessages' --output text)

echo "📊 Messages in queue: $MSG_COUNT"

if [ "$MSG_COUNT" -eq "0" ]; then
  echo "ℹ️  No messages to process (no enabled playlists or all skipped)"
  exit 0
fi

# Step 3: Process messages with worker
echo "⚙️  Step 2: Processing messages with worker..."
echo "📝 Note: Worker will process all messages then exit"

# Process each message
while [ "$MSG_COUNT" -gt "0" ]; do
  # Receive one message
  MESSAGE=$(aws --endpoint-url=$AWS_ENDPOINT_URL sqs receive-message \
    --queue-url "$QUEUE_URL" \
    --max-number-of-messages 1 \
    --wait-time-seconds 5 \
    --query 'Messages[0]' --output json)
  
  if [ "$MESSAGE" == "null" ] || [ -z "$MESSAGE" ]; then
    break
  fi
  
  # Extract body and receipt handle
  BODY=$(echo "$MESSAGE" | jq -r '.Body')
  RECEIPT=$(echo "$MESSAGE" | jq -r '.ReceiptHandle')
  
  echo "Processing message: $BODY"
  
  # Process with worker
  .venv/bin/python -m media_summarizer.workers.spotify_sync.worker "$BODY"
  
  # Delete message
  aws --endpoint-url=$AWS_ENDPOINT_URL sqs delete-message \
    --queue-url "$QUEUE_URL" \
    --receipt-handle "$RECEIPT"
  
  # Update count
  MSG_COUNT=$(aws --endpoint-url=$AWS_ENDPOINT_URL sqs get-queue-attributes \
    --queue-url "$QUEUE_URL" \
    --attribute-names ApproximateNumberOfMessages \
    --query 'Attributes.ApproximateNumberOfMessages' --output text)
done

echo "✅ Spotify Sync completed!"
