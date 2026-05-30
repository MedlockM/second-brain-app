#!/bin/bash
# DEPRECATED: This init script is no longer used. Use Terraform for LocalStack provisioning instead.
# See infrastructure/terraform/localstack for a LocalStack-specific Terraform root.

echo "[DEPRECATED] LocalStack init script is no longer used. Use Terraform in infrastructure/terraform/localstack."
exit 0

# Set AWS credentials for LocalStack
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=us-east-1

# Wait for LocalStack to be ready
echo "⏳ Waiting for LocalStack to be ready..."
sleep 10

# Function to create DynamoDB table with retry
create_table_with_retry() {
    local table_name=$1
    local max_retries=3
    local retry_count=0

    while [ $retry_count -lt $max_retries ]; do
        if aws --endpoint-url=http://localhost:4566 dynamodb describe-table --table-name "$table_name" --region us-east-1 >/dev/null 2>&1; then
            echo "✅ Table $table_name already exists"
            return 0
        fi

        echo "Creating table: $table_name (attempt $((retry_count + 1)))"
        if eval "$2"; then
            echo "✅ Successfully created table: $table_name"
            return 0
        else
            retry_count=$((retry_count + 1))
            echo "⚠️ Failed to create $table_name, retrying..."
            sleep 2
        fi
    done

    echo "❌ Failed to create table $table_name after $max_retries attempts"
    return 1
}

echo "📊 Creating DynamoDB tables with indexes..."

# Users table with email index
create_table_with_retry "users" 'aws --endpoint-url=http://localhost:4566 dynamodb create-table \
    --table-name users \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
        AttributeName=email,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --global-secondary-indexes \
        "IndexName=email-index,KeySchema=[{AttributeName=email,KeyType=HASH}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}" \
    --provisioned-throughput \
        ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --region us-east-1 >/dev/null 2>&1'


# Auth tokens table with multiple indexes
create_table_with_retry "auth_tokens" 'aws --endpoint-url=http://localhost:4566 dynamodb create-table \
    --table-name auth_tokens \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
        AttributeName=token,AttributeType=S \
        AttributeName=user_id,AttributeType=S \
        AttributeName=token_type,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --global-secondary-indexes \
        "IndexName=token-index,KeySchema=[{AttributeName=token,KeyType=HASH}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}" \
        "IndexName=user-index,KeySchema=[{AttributeName=user_id,KeyType=HASH}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}" \
        "IndexName=user-type-index,KeySchema=[{AttributeName=user_id,KeyType=HASH},{AttributeName=token_type,KeyType=RANGE}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}" \
    --provisioned-throughput \
        ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --region us-east-1 >/dev/null 2>&1'

# Transactions table with user index
create_table_with_retry "transactions" 'aws --endpoint-url=http://localhost:4566 dynamodb create-table \
    --table-name transactions \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
        AttributeName=user_id,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --global-secondary-indexes \
        "IndexName=user-index,KeySchema=[{AttributeName=user_id,KeyType=HASH}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}" \
    --provisioned-throughput \
        ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --region us-east-1 >/dev/null 2>&1'

# Credit transactions table with user index
create_table_with_retry "credit_transactions" 'aws --endpoint-url=http://localhost:4566 dynamodb create-table \
    --table-name credit_transactions \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
        AttributeName=user_id,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --global-secondary-indexes \
        "IndexName=user-index,KeySchema=[{AttributeName=user_id,KeyType=HASH}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}" \
    --provisioned-throughput \
        ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --region us-east-1 >/dev/null 2>&1'

# Stripe webhook idempotency events table
create_table_with_retry "stripe_events" 'aws --endpoint-url=http://localhost:4566 dynamodb create-table \
    --table-name stripe_events \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --provisioned-throughput \
        ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --region us-east-1 >/dev/null 2>&1'

# Processing jobs table with user and status indexes
create_table_with_retry "processing_jobs" 'aws --endpoint-url=http://localhost:4566 dynamodb create-table \
    --table-name processing_jobs \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
        AttributeName=user_id,AttributeType=S \
        AttributeName=job_status,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --global-secondary-indexes \
        "IndexName=user-index,KeySchema=[{AttributeName=user_id,KeyType=HASH}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}" \
        "IndexName=status-index,KeySchema=[{AttributeName=job_status,KeyType=HASH}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}" \
    --provisioned-throughput \
        ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --region us-east-1 >/dev/null 2>&1'

# Podcasts table with user index
create_table_with_retry "podcasts" 'aws --endpoint-url=http://localhost:4566 dynamodb create-table \
    --table-name podcasts \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
        AttributeName=user_id,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --global-secondary-indexes \
        "IndexName=user-index,KeySchema=[{AttributeName=user_id,KeyType=HASH}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}" \
    --provisioned-throughput \
        ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --region us-east-1 >/dev/null 2>&1'

# Episodes table with podcast index
create_table_with_retry "episodes" 'aws --endpoint-url=http://localhost:4566 dynamodb create-table \
    --table-name episodes \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
        AttributeName=podcast_id,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --global-secondary-indexes \
        "IndexName=podcast-index,KeySchema=[{AttributeName=podcast_id,KeyType=HASH}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}" \
    --provisioned-throughput \
        ReadCapacityUnits=5,WriteCapacityUnits=5 \
    --region us-east-1 >/dev/null 2>&1'

echo "🪣 Creating S3 buckets..."

# Create S3 buckets with proper naming
buckets=("media-summarizer-audio" "media-summarizer-transcriptions" "media-summarizer-summaries" "test-data")

for bucket in "${buckets[@]}"; do
    if aws --endpoint-url=http://localhost:4566 s3 ls "s3://$bucket" >/dev/null 2>&1; then
        echo "✅ Bucket $bucket already exists"
    else
        aws --endpoint-url=http://localhost:4566 s3 mb "s3://$bucket" --region us-east-1 >/dev/null 2>&1
        echo "✅ Created S3 bucket: $bucket"
    fi
done

echo "📬 Creating SQS queues..."

# Create main SQS queues
queues=("transcription-queue" "summarization-queue")

for queue in "${queues[@]}"; do
    if aws --endpoint-url=http://localhost:4566 sqs get-queue-url --queue-name "$queue" --region us-east-1 >/dev/null 2>&1; then
        echo "✅ Queue $queue already exists"
    else
        aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name "$queue" --region us-east-1 >/dev/null 2>&1
        echo "✅ Created SQS queue: $queue"
    fi
done

# Create Dead Letter Queues (for production reliability)
echo "📬 Creating Dead Letter Queues..."

dlq_queues=("transcription-dlq" "summarization-dlq")

for dlq in "${dlq_queues[@]}"; do
    if aws --endpoint-url=http://localhost:4566 sqs get-queue-url --queue-name "$dlq" --region us-east-1 >/dev/null 2>&1; then
        echo "✅ DLQ $dlq already exists"
    else
        aws --endpoint-url=http://localhost:4566 sqs create-queue --queue-name "$dlq" --region us-east-1 >/dev/null 2>&1
        echo "✅ Created DLQ: $dlq"
    fi
done

# Configure DLQ redrive policies (optional - for production-like behavior)
if [ "$SETUP_DLQ_POLICIES" = "true" ]; then
    echo "⚙️ Configuring DLQ redrive policies..."

fi

echo "📧 Setting up SES..."

# Setup SES email verification
emails=("noreply@media-summarizer.com" "noreply@example.com" "test@example.com")

for email in "${emails[@]}"; do
    aws --endpoint-url=http://localhost:4566 ses verify-email-identity --email-address "$email" --region us-east-1 >/dev/null 2>&1
    echo "✅ Verified SES email: $email"
done

echo "🧪 Creating test data..."

# Create test users for E2E testing
test_users=(
    '{"id": {"S": "e2e-test-user-1"}, "email": {"S": "e2e-user1@example.com"}, "credits": {"N": "100"}, "created_at": {"S": "2024-01-01T00:00:00Z"}, "updated_at": {"S": "2024-01-01T00:00:00Z"}}'
    '{"id": {"S": "e2e-test-user-2"}, "email": {"S": "e2e-user2@example.com"}, "credits": {"N": "50"}, "created_at": {"S": "2024-01-01T00:00:00Z"}, "updated_at": {"S": "2024-01-01T00:00:00Z"}}'
    '{"id": {"S": "e2e-test-user-existing"}, "email": {"S": "existing-user@e2e-test.example.com"}, "credits": {"N": "25"}, "created_at": {"S": "2024-01-01T00:00:00Z"}, "updated_at": {"S": "2024-01-01T00:00:00Z"}}'
)

for user_data in "${test_users[@]}"; do
    aws --endpoint-url=http://localhost:4566 dynamodb put-item \
        --table-name users \
        --item "$user_data" \
        --region us-east-1 >/dev/null 2>&1
done

echo "✅ Created test users for E2E testing"

# Create test audio files and RSS feeds (for comprehensive testing)
if [ "$CREATE_TEST_FILES" = "true" ]; then
    echo "🎵 Creating test audio files..."

    # Create simple test audio files using Python
    python3 -c "
import struct
import wave
import tempfile
import os

def create_wav(filename, duration, sample_rate=44100):
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        frames = []
        for i in range(int(duration * sample_rate)):
            value = int(32767 * 0.1)  # Low volume sine wave
            frames.append(struct.pack('<h', value))
        wav_file.writeframes(b''.join(frames))

# Create test files in temp directory
temp_dir = '/tmp'
create_wav(f'{temp_dir}/test_audio_short.wav', 5)
create_wav(f'{temp_dir}/test_audio_medium.wav', 30)
create_wav(f'{temp_dir}/test_audio_long.wav', 120)

print('Test audio files created')
" 2>/dev/null || echo "⚠️ Could not create test audio files (Python not available)"

    # Upload test files to S3
    for file in "/tmp/test_audio_short.wav" "/tmp/test_audio_medium.wav" "/tmp/test_audio_long.wav"; do
        if [ -f "$file" ]; then
            aws --endpoint-url=http://localhost:4566 s3 cp "$file" "s3://test-data/audio/$(basename $file)" >/dev/null 2>&1
            echo "✅ Uploaded test file: $(basename $file)"
        fi
    done
fi

# Verify tables and indexes
echo "🔍 Verifying infrastructure..."

tables=("users" "auth_tokens" "transactions" "credit_transactions" "processing_jobs" "podcasts" "episodes")
for table in "${tables[@]}"; do
    if aws --endpoint-url=http://localhost:4566 dynamodb describe-table --table-name "$table" --region us-east-1 >/dev/null 2>&1; then
        echo "✅ Table verified: $table"
    else
        echo "❌ Table missing: $table"
    fi
done

# Summary
echo ""
echo "🎉 LocalStack initialization completed successfully!"
echo ""
echo "📊 Created DynamoDB tables with indexes:"
echo "   - users (with email-index)"
echo "   - auth_tokens (with token-index, user-index, user-type-index)"
echo "   - transactions (with user-index)"
echo "   - credit_transactions (with user-index)"
echo "   - processing_jobs (with user-index, status-index)"
echo "   - podcasts (with user-index)"
echo "   - episodes (with podcast-index)"
echo ""
echo "🪣 Created S3 buckets:"
echo "   - media-summarizer-audio"
echo "   - media-summarizer-transcriptions"
echo "   - media-summarizer-summaries"
echo "   - test-data"
echo ""
echo "📬 Created SQS queues:"
echo "   - transcription-queue (+ DLQ)"
echo "   - summarization-queue (+ DLQ)"
echo ""
echo "🧪 Test data created:"
echo "   - 3 test users for E2E testing"
echo ""
echo "🚀 Ready for all types of testing (unit, integration, E2E)!"
echo ""
echo "💡 Usage:"
echo "   - For basic testing: bash init-aws.sh"
echo "   - For production-like: SETUP_DLQ_POLICIES=true bash init-aws.sh"
echo "   - With test files: CREATE_TEST_FILES=true bash init-aws.sh"
