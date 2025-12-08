#!/bin/bash
# Setup script for Spotify Sync EventBridge + Lambda on LocalStack
# This simulates the production setup using LocalStack services

set -e

echo "🚀 Setting up Spotify Sync Scheduler on LocalStack..."

# Configuration
AWS_REGION=${AWS_REGION:-us-east-1}
AWS_ENDPOINT_URL=${AWS_ENDPOINT_URL:-http://localhost:4566}
SPOTIFY_SYNC_SCHEDULE=${SPOTIFY_SYNC_SCHEDULE:-"rate(1 day)"}  # Default: daily

# Queue URL
QUEUE_URL=$(AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_REGION=$AWS_REGION \
  aws --endpoint-url=$AWS_ENDPOINT_URL sqs get-queue-url \
  --queue-name spotify-sync-queue --query 'QueueUrl' --output text)

echo "✅ Queue URL: $QUEUE_URL"

# Create EventBridge rule
echo "📅 Creating EventBridge rule with schedule: $SPOTIFY_SYNC_SCHEDULE"
AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_REGION=$AWS_REGION \
  aws --endpoint-url=$AWS_ENDPOINT_URL events put-rule \
  --name SpotifyDailySync \
  --schedule-expression "$SPOTIFY_SYNC_SCHEDULE" \
  --state ENABLED \
  --description "Daily Spotify playlist sync trigger"

# Note: In LocalStack, we'll use a simpler approach with cron
# For production AWS, you would:
# 1. Create Lambda functions for dispatcher and worker
# 2. Set EventBridge to trigger dispatcher Lambda
# 3. Set SQS as event source for worker Lambda

echo "✅ EventBridge rule created"
echo ""
echo "📝 Next steps:"
echo "  1. For production: Deploy Lambda functions and configure event source mappings"
echo "  2. For local dev: Use scripts/trigger_spotify_sync.sh to manually trigger"
echo ""
echo "Environment variables:"
echo "  SPOTIFY_SYNC_SCHEDULE=$SPOTIFY_SYNC_SCHEDULE"
echo "  SPOTIFY_SYNC_QUEUE_URL=$QUEUE_URL"
