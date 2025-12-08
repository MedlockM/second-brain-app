# Lambda Zip Builder Dockerfile
# This container builds an optimized Lambda deployment package (zip) with all dependencies
# Key optimization: Prunes unused botocore service models to reduce size from ~21MB to ~8MB
#
# The zip file is output to /output/spotify_sync_lambda.zip

FROM python:3.11-slim

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    zip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Script to build the Lambda zip
COPY <<'EOF' /build-lambda.sh
#!/bin/bash
set -e

echo "📦 Building optimized Lambda zip package..."
echo ""

BUILD_DIR=/tmp/lambda_build
mkdir -p $BUILD_DIR

# Step 1: Copy application code
echo "📁 Step 1: Copying application code..."
cp -r /app/media_summarizer $BUILD_DIR/

# Step 2: Install all dependencies
echo "📥 Step 2: Installing dependencies..."
pip install --quiet --target $BUILD_DIR \
    aioboto3>=12.0.0 \
    boto3>=1.34.0 \
    httpx>=0.25.0 \
    pydantic>=2.5.0 \
    pydantic-settings>=2.1.0 \
    python-dotenv>=1.0.0 \
    tenacity>=8.2.0

# Step 3: Clean up unnecessary files
echo "🧹 Step 3: Cleaning up unnecessary files..."
cd $BUILD_DIR

# Remove Python cache and metadata
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Remove test directories and examples (but NOT docs - botocore.docs is required at runtime)
find . -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "test" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "examples" -exec rm -rf {} + 2>/dev/null || true
# Note: Do NOT delete "docs" directories - botocore/docs is required by boto3

# Remove pydantic v1 compatibility layer (not needed, saves ~500KB)
rm -rf pydantic/v1 2>/dev/null || true

# Step 4: Prune unused botocore service models (THE BIG OPTIMIZATION)
# This reduces botocore from ~17MB to ~3MB
echo "✂️  Step 4: Pruning unused botocore service models..."
echo "   (Keeping only: dynamodb, sqs, sts, iam, lambda, events, logs)"

if [ -d "$BUILD_DIR/botocore/data" ]; then
    cd $BUILD_DIR/botocore/data

    # Count before
    BEFORE_COUNT=$(ls -d */ 2>/dev/null | wc -l)

    # Keep only essential services for this Lambda
    # - dynamodb: For reading/writing to DynamoDB tables
    # - sqs: For sending messages to queues
    # - sts: For STS AssumeRole (required by boto3)
    # - iam: For IAM operations (required by Lambda)
    # - lambda: For Lambda invocations if needed
    # - events: For EventBridge
    # - logs: For CloudWatch Logs
    for dir in */; do
        service="${dir%/}"
        case "$service" in
            dynamodb|sqs|sts|iam|lambda|events|logs|endpoints|partitions|_retry|sdk-default-configuration)
                # Keep these essential services
                ;;
            *)
                rm -rf "$service" 2>/dev/null || true
                ;;
        esac
    done

    # Count after
    AFTER_COUNT=$(ls -d */ 2>/dev/null | wc -l)
    echo "   Removed $((BEFORE_COUNT - AFTER_COUNT)) unused service models (kept $AFTER_COUNT)"
fi

# Step 5: Create the zip
echo "📦 Step 5: Creating zip archive..."
cd $BUILD_DIR
zip -q -r /output/spotify_sync_lambda.zip .

# Step 6: Show results
ZIP_SIZE=$(du -h /output/spotify_sync_lambda.zip | cut -f1)
echo ""
echo "✅ Lambda package built successfully!"
echo ""
echo "📊 Package size: $ZIP_SIZE"
echo "   (Optimized from ~21MB by pruning unused botocore models)"
echo ""
echo "📍 Output: /output/spotify_sync_lambda.zip"
EOF

RUN chmod +x /build-lambda.sh

ENTRYPOINT ["/build-lambda.sh"]
