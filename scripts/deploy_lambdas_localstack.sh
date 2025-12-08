#!/bin/bash
# Script to build and deploy Lambda functions to LocalStack
# Uses zip packages (not container images) for LocalStack Community compatibility
#
# Architecture:
# EventBridge (rate: 1 minute) -> Dispatcher Lambda -> SQS -> Worker Lambda -> Processing

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
LOCALSTACK_ENDPOINT="${AWS_ENDPOINT_URL:-http://localhost:4566}"
LAMBDA_ZIP_DIR="$PROJECT_ROOT/infrastructure/terraform/localstack"
LAMBDA_ZIP="$LAMBDA_ZIP_DIR/spotify_sync_lambda.zip"

export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_REGION="${AWS_REGION:-us-east-1}"

echo -e "${GREEN}🚀 Deploying Lambda functions to LocalStack${NC}"
echo ""

# Step 1: Build Lambda zip package using Docker
echo -e "${YELLOW}📦 Step 1: Building Lambda zip package...${NC}"

mkdir -p "$LAMBDA_ZIP_DIR"

# Build the zip package using Docker with Python 3.11
docker run --rm \
    -v "$PROJECT_ROOT:/app" \
    -w /app \
    python:3.11-slim \
    bash -c '
        set -e

        # Create build directory
        BUILD_DIR=/tmp/lambda_build
        mkdir -p $BUILD_DIR

        # Copy application code
        cp -r /app/media_summarizer $BUILD_DIR/

        # Install dependencies
        pip install --quiet --target $BUILD_DIR \
            aioboto3>=12.0.0 \
            aiohttp>=3.9.0 \
            boto3>=1.34.0 \
            httpx>=0.25.0 \
            pydantic>=2.5.0 \
            pydantic-settings>=2.1.0 \
            python-dotenv>=1.0.0 \
            tenacity>=8.2.0

        # Clean up unnecessary files
        cd $BUILD_DIR
        find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find . -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
        find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
        find . -type f -name "*.pyc" -delete 2>/dev/null || true
        rm -rf tests/ docs/ 2>/dev/null || true

        # Create zip
        apt-get update -qq && apt-get install -qq -y zip > /dev/null 2>&1
        zip -q -r /app/infrastructure/terraform/localstack/spotify_sync_lambda.zip .

        echo "Package built successfully"
    '

ZIP_SIZE=$(du -h "$LAMBDA_ZIP" | cut -f1)
echo -e "${GREEN}✅ Lambda package built: $LAMBDA_ZIP ($ZIP_SIZE)${NC}"
echo ""

# Step 2: Wait for LocalStack to be ready
echo -e "${YELLOW}⏳ Step 2: Waiting for LocalStack to be ready...${NC}"
MAX_RETRIES=30
RETRY_COUNT=0

while ! curl -s "${LOCALSTACK_ENDPOINT}/_localstack/health" | grep -q '"lambda": "running"'; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo -e "${RED}❌ LocalStack Lambda service not ready after ${MAX_RETRIES} retries${NC}"
        exit 1
    fi
    echo "  Waiting for LocalStack Lambda service... (${RETRY_COUNT}/${MAX_RETRIES})"
    sleep 2
done

echo -e "${GREEN}✅ LocalStack is ready${NC}"
echo ""

# Step 3: Create IAM role for Lambda (if not exists)
echo -e "${YELLOW}🔐 Step 3: Creating IAM role for Lambda...${NC}"

aws --endpoint-url="$LOCALSTACK_ENDPOINT" iam create-role \
    --role-name lambda-execution-role \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }' 2>/dev/null || echo "  IAM role already exists"

LAMBDA_ROLE_ARN="arn:aws:iam::000000000000:role/lambda-execution-role"
echo -e "${GREEN}✅ IAM role ready: ${LAMBDA_ROLE_ARN}${NC}"
echo ""

# Step 4: Deploy Spotify Sync Dispatcher Lambda
echo -e "${YELLOW}🔧 Step 4: Deploying spotify-sync-dispatcher Lambda...${NC}"

# Delete existing function if exists (to ensure clean state)
aws --endpoint-url="$LOCALSTACK_ENDPOINT" lambda delete-function \
    --function-name spotify-sync-dispatcher 2>/dev/null || true

# Determine the LocalStack endpoint for Lambda containers
# On Linux, host.docker.internal doesn't work, so we use the docker bridge IP
LAMBDA_ENDPOINT_URL="http://172.17.0.1:4566"

# Create function
aws --endpoint-url="$LOCALSTACK_ENDPOINT" lambda create-function \
    --function-name spotify-sync-dispatcher \
    --runtime python3.11 \
    --handler media_summarizer.workers.spotify_sync.dispatcher.lambda_handler \
    --role "$LAMBDA_ROLE_ARN" \
    --zip-file "fileb://$LAMBDA_ZIP" \
    --timeout 60 \
    --memory-size 256 \
    --environment "Variables={
        AWS_ENDPOINT_URL=$LAMBDA_ENDPOINT_URL,
        AWS_REGION=us-east-1,
        USERS_TABLE=users,
        SPOTIFY_FOLLOWS_TABLE=spotify_playlist_follows,
        SPOTIFY_SYNC_QUEUE_URL=http://sqs.us-east-1.localhost.localstack.cloud:4566/000000000000/spotify-sync-queue
    }" \
    > /dev/null

echo -e "${GREEN}✅ spotify-sync-dispatcher deployed${NC}"
echo ""

# Step 5: Deploy Spotify Sync Worker Lambda
echo -e "${YELLOW}🔧 Step 5: Deploying spotify-sync-worker Lambda...${NC}"

# Delete existing function if exists
aws --endpoint-url="$LOCALSTACK_ENDPOINT" lambda delete-function \
    --function-name spotify-sync-worker 2>/dev/null || true

# Create function
aws --endpoint-url="$LOCALSTACK_ENDPOINT" lambda create-function \
    --function-name spotify-sync-worker \
    --runtime python3.11 \
    --handler media_summarizer.workers.spotify_sync.worker.lambda_handler \
    --role "$LAMBDA_ROLE_ARN" \
    --zip-file "fileb://$LAMBDA_ZIP" \
    --timeout 300 \
    --memory-size 512 \
    --environment "Variables={
        AWS_ENDPOINT_URL=$LAMBDA_ENDPOINT_URL,
        AWS_REGION=us-east-1,
        USERS_TABLE=users,
        SPOTIFY_FOLLOWS_TABLE=spotify_playlist_follows,
        SPOTIFY_PLAYLIST_FOLLOWS_TABLE=spotify_playlist_follows,
        PROCESSING_JOBS_TABLE=processing_jobs,
        AUDIO_DOWNLOAD_QUEUE=audio-download-queue
    }" \
    > /dev/null

echo -e "${GREEN}✅ spotify-sync-worker deployed${NC}"
echo ""

# Step 6: Wait for functions to be active
echo -e "${YELLOW}⏳ Step 6: Waiting for Lambda functions to be active...${NC}"
sleep 3

# Step 7: Create SQS -> Lambda event source mapping for worker
echo -e "${YELLOW}🔗 Step 7: Creating SQS event source mapping...${NC}"

SPOTIFY_SYNC_QUEUE_ARN="arn:aws:sqs:us-east-1:000000000000:spotify-sync-queue"

# Check if mapping exists and delete it
EXISTING_MAPPINGS=$(aws --endpoint-url="$LOCALSTACK_ENDPOINT" lambda list-event-source-mappings \
    --function-name spotify-sync-worker \
    --event-source-arn "$SPOTIFY_SYNC_QUEUE_ARN" \
    --query 'EventSourceMappings[*].UUID' \
    --output text 2>/dev/null || echo "")

for uuid in $EXISTING_MAPPINGS; do
    if [ -n "$uuid" ] && [ "$uuid" != "None" ]; then
        aws --endpoint-url="$LOCALSTACK_ENDPOINT" lambda delete-event-source-mapping \
            --uuid "$uuid" 2>/dev/null || true
    fi
done

# Create new mapping
aws --endpoint-url="$LOCALSTACK_ENDPOINT" lambda create-event-source-mapping \
    --function-name spotify-sync-worker \
    --event-source-arn "$SPOTIFY_SYNC_QUEUE_ARN" \
    --batch-size 1 \
    --enabled \
    > /dev/null

echo -e "${GREEN}✅ SQS event source mapping ready${NC}"
echo ""

# Step 8: Create EventBridge rule and target for dispatcher
echo -e "${YELLOW}⏰ Step 8: Setting up EventBridge schedule...${NC}"

# Create the rule
aws --endpoint-url="$LOCALSTACK_ENDPOINT" events put-rule \
    --name spotify-sync-schedule \
    --schedule-expression "rate(1 minute)" \
    --state ENABLED \
    > /dev/null 2>&1 || echo "  Rule already exists"

# Add the target
aws --endpoint-url="$LOCALSTACK_ENDPOINT" events put-targets \
    --rule spotify-sync-schedule \
    --targets "Id=SpotifySyncDispatcherLambda,Arn=arn:aws:lambda:us-east-1:000000000000:function:spotify-sync-dispatcher" \
    > /dev/null 2>&1

# Add permission for EventBridge to invoke Lambda
aws --endpoint-url="$LOCALSTACK_ENDPOINT" lambda add-permission \
    --function-name spotify-sync-dispatcher \
    --statement-id AllowEventBridgeInvoke \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn "arn:aws:events:us-east-1:000000000000:rule/spotify-sync-schedule" \
    > /dev/null 2>&1 || true

echo -e "${GREEN}✅ EventBridge schedule configured (rate: 1 minute)${NC}"
echo ""

# Step 9: Verify deployment
echo -e "${YELLOW}🔍 Step 9: Verifying deployment...${NC}"
echo ""

echo "Lambda Functions:"
aws --endpoint-url="$LOCALSTACK_ENDPOINT" lambda list-functions \
    --query 'Functions[*].[FunctionName, Runtime, Timeout, MemorySize]' \
    --output table

echo ""
echo "EventBridge Rules:"
aws --endpoint-url="$LOCALSTACK_ENDPOINT" events list-rules \
    --query 'Rules[*].[Name, State, ScheduleExpression]' \
    --output table

echo ""
echo "Event Source Mappings:"
aws --endpoint-url="$LOCALSTACK_ENDPOINT" lambda list-event-source-mappings \
    --query 'EventSourceMappings[*].[FunctionArn, EventSourceArn, State]' \
    --output table

echo ""
echo -e "${GREEN}🎉 Lambda deployment complete!${NC}"
echo ""
echo "Architecture:"
echo "  EventBridge (1 min) -> spotify-sync-dispatcher -> SQS -> spotify-sync-worker"
echo ""
echo "To test the dispatcher manually:"
echo "  aws --endpoint-url=$LOCALSTACK_ENDPOINT lambda invoke --function-name spotify-sync-dispatcher /tmp/response.json && cat /tmp/response.json"
echo ""
echo "To view LocalStack logs:"
echo "  docker logs media-summarizer-project-localstack-1 2>&1 | grep -i lambda"
