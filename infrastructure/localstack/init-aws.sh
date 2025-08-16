#!/bin/bash

echo "Initializing LocalStack AWS services for Media Summarizer..."

# Wait for LocalStack to be ready
sleep 5

# Création des buckets S3
echo "Creating S3 buckets..."
awslocal s3 mb s3://media-summarizer-audio --region us-east-1
awslocal s3 mb s3://media-summarizer-transcriptions --region us-east-1
awslocal s3 mb s3://media-summarizer-summaries --region us-east-1

# Création des tables DynamoDB
echo "Creating DynamoDB tables..."

# Users table with email index
awslocal dynamodb create-table \
    --table-name users \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
        AttributeName=email,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --global-secondary-indexes \
        'IndexName=email-index,KeySchema=[{AttributeName=email,KeyType=HASH}],Projection={ProjectionType=ALL}' \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1

# Podcasts table
awslocal dynamodb create-table \
    --table-name podcasts \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1

# Episodes table with podcast index
awslocal dynamodb create-table \
    --table-name episodes \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
        AttributeName=podcast_id,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --global-secondary-indexes \
        'IndexName=podcast-index,KeySchema=[{AttributeName=podcast_id,KeyType=HASH}],Projection={ProjectionType=ALL}' \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1

# Credit transactions table with user index
awslocal dynamodb create-table \
    --table-name credit_transactions \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
        AttributeName=user_id,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --global-secondary-indexes \
        'IndexName=user-index,KeySchema=[{AttributeName=user_id,KeyType=HASH}],Projection={ProjectionType=ALL}' \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1

# Processing jobs table with user and status indexes
awslocal dynamodb create-table \
    --table-name processing_jobs \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
        AttributeName=user_id,AttributeType=S \
        AttributeName=job_status,AttributeType=S \
    --key-schema \
        AttributeName=id,KeyType=HASH \
    --global-secondary-indexes \
        'IndexName=user-index,KeySchema=[{AttributeName=user_id,KeyType=HASH}],Projection={ProjectionType=ALL}' \
        'IndexName=status-index,KeySchema=[{AttributeName=job_status,KeyType=HASH}],Projection={ProjectionType=ALL}' \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1

# Création des files SQS
echo "Creating SQS queues..."
awslocal sqs create-queue --queue-name audio-download-queue --region us-east-1
awslocal sqs create-queue --queue-name transcription-queue --region us-east-1
awslocal sqs create-queue --queue-name summarization-queue --region us-east-1
awslocal sqs create-queue --queue-name email-notification-queue --region us-east-1

# Configuration de SES (Simple Email Service)
echo "Configuring SES..."
awslocal ses verify-email-identity --email-address noreply@media-summarizer.com --region us-east-1
awslocal ses verify-email-identity --email-address test@example.com --region us-east-1

# Add test data for E2E testing
echo "Adding test data..."

# Create test data bucket
awslocal s3 mb s3://test-data --region us-east-1

# Create test users
awslocal dynamodb put-item \
    --table-name users \
    --region us-east-1 \
    --item '{
        "id": {"S": "e2e-test-user-1"},
        "email": {"S": "e2e-user1@example.com"},
        "credits": {"N": "100"},
        "created_at": {"S": "2024-01-01T00:00:00Z"},
        "updated_at": {"S": "2024-01-01T00:00:00Z"}
    }'

awslocal dynamodb put-item \
    --table-name users \
    --region us-east-1 \
    --item '{
        "id": {"S": "e2e-test-user-2"},
        "email": {"S": "e2e-user2@example.com"},
        "credits": {"N": "50"},
        "created_at": {"S": "2024-01-01T00:00:00Z"},
        "updated_at": {"S": "2024-01-01T00:00:00Z"}
    }'

# Create test audio files
echo "Creating test audio files..."
python3 -c "
import struct
import wave

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

create_wav('/tmp/test_audio_short.wav', 5)
create_wav('/tmp/test_audio_medium.wav', 30)
create_wav('/tmp/test_audio_long.wav', 120)
"

# Upload test audio files
awslocal s3 cp /tmp/test_audio_short.wav s3://test-data/audio/test_audio_short.wav
awslocal s3 cp /tmp/test_audio_medium.wav s3://test-data/audio/test_audio_medium.wav
awslocal s3 cp /tmp/test_audio_long.wav s3://test-data/audio/test_audio_long.wav

# Create test RSS feed
cat > /tmp/test_rss_feed.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
    <channel>
        <title>Test Podcast</title>
        <description>Test podcast for E2E testing</description>
        <link>https://example.com/test-podcast</link>
        <language>en-us</language>
        <itunes:author>Test Author</itunes:author>
        <itunes:category text="Technology"/>

        <item>
            <title>Test Episode 1</title>
            <description>First test episode</description>
            <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
            <enclosure url="http://localstack:4566/test-data/audio/test_audio_short.wav" type="audio/wav" length="441044"/>
            <guid>test-episode-1</guid>
            <itunes:duration>00:00:05</itunes:duration>
        </item>
    </channel>
</rss>
EOF

# Upload test RSS feed
awslocal s3 cp /tmp/test_rss_feed.xml s3://test-data/rss/test_feed.xml

echo "LocalStack AWS initialization completed successfully!"
echo "Services initialized:"
echo "  - S3 buckets: media-summarizer-audio, media-summarizer-transcriptions, media-summarizer-summaries, test-data"
echo "  - DynamoDB tables: users, podcasts, episodes, credit_transactions, processing_jobs"
echo "  - SQS queues: audio-download-queue, transcription-queue, summarization-queue, email-notification-queue"
echo "  - SES verified emails: noreply@media-summarizer.com, test@example.com"
echo "  - Test data: Test users, audio files, and RSS feeds for E2E testing"
