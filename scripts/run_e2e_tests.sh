#!/bin/bash

# Media Summarizer - End-to-End Test Runner
# This script runs E2E tests without coverage requirements

set -e  # Exit on any error

echo "🚀 Media Summarizer - End-to-End Test Runner"
echo "============================================="

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Virtual environment not activated. Activating..."
    source .venv/bin/activate
fi

# Check if required services are running
echo "🔍 Checking required services..."

# Check Docker Compose services
if ! docker compose -f docker-compose.dev.yml ps | grep -q "Up"; then
    echo "❌ Docker services not running. Please start them with:"
    echo "   docker compose -f docker-compose.dev.yml up -d"
    exit 1
fi

echo "✅ Docker services are running"

# List of required services
required_services=(
    "api"
    "localstack"
    "download-worker"
    "rss-worker"
    "summarize-worker"
    "email-worker"
    "whisper"
)

# Check each service
for service in "${required_services[@]}"; do
    if docker compose -f docker-compose.dev.yml ps | grep -q "${service}.*Up"; then
        echo "✅ $service is running"
    else
        echo "❌ $service is not running"
        exit 1
    fi
done

echo ""
echo "🧪 Running End-to-End Tests..."
echo "================================"

# Run E2E tests without coverage
pytest \
    media_summarizer/tests/end_to_end/ \
    -v \
    -s \
    --tb=short \
    --no-cov \
    --disable-warnings \
    -m "e2e" \
    --maxfail=1

echo ""
echo "🎉 End-to-End Tests Completed Successfully!"
echo "=========================================="
